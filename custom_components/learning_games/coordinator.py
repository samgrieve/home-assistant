"""Profile coordinator: owns state, sessions, rollover, events and persistence."""
from __future__ import annotations

import logging
import random
import secrets
from datetime import date, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AVATAR,
    CONF_DAILY_GOAL,
    CONF_NAME,
    DEFAULT_DAILY_GOAL,
    EVENT_BADGE_EARNED,
    EVENT_CHALLENGE_COMPLETE,
    EVENT_DAILY_GOAL,
    EVENT_LEVEL_UP,
    EVENT_SESSION_COMPLETE,
    EVENT_STREAK_MILESTONE,
    SIGNAL_PROFILE_UPDATED,
    STREAK_MILESTONES,
)
from .engine import (
    ALL_SKILLS,
    BOSS_DEFEAT_THRESHOLD,
    BOSS_XP_MULTIPLIER,
    ENGLISH_SKILLS,
    MATHS_SKILLS,
    MODES,
    adaptive,
    arcade,
    challenges,
)
from .engine.badges import badge_public, check_badges
from .engine.models import SkillState
from .engine.session import GameSession, SessionError
from .engine.wordlists import WordBanks
from .storage import ProfileStore, _default_daily, _default_weekly

_LOGGER = logging.getLogger(__name__)

MAX_HISTORY = 30
MAX_FREEZES = 2
MAX_ACTIVE_SESSIONS = 4
MAX_ACTIVE_ARCADES = 2


def xp_to_next(level: int) -> int:
    return 100 + 50 * (level - 1)


def level_progress(total_xp: int) -> tuple[int, int, int]:
    """Return (level, xp_into_level, xp_to_next_level) for a total XP amount."""
    level = 1
    remaining = total_xp
    while remaining >= xp_to_next(level):
        remaining -= xp_to_next(level)
        level += 1
    return level, remaining, xp_to_next(level)


class ProfileCoordinator:
    """One per config entry (one per kid)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, banks: WordBanks) -> None:
        self.hass = hass
        self.entry = entry
        self.banks = banks
        self.store = ProfileStore(hass, entry.entry_id)
        self.data: dict = {}
        self.skills: dict[str, SkillState] = {}
        self.sessions: dict[str, GameSession] = {}
        self.arcades: dict[str, dict] = {}
        self._unsub_midnight = None

    # ------------------------------------------------------------------ config

    @property
    def profile_id(self) -> str:
        return self.entry.entry_id

    @property
    def name(self) -> str:
        return self.entry.data.get(CONF_NAME, "Player")

    @property
    def avatar(self) -> str:
        return self.entry.options.get(
            CONF_AVATAR, self.entry.data.get(CONF_AVATAR, "fox")
        )

    @property
    def daily_goal(self) -> int:
        return self.entry.options.get(
            CONF_DAILY_GOAL, self.entry.data.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL)
        )

    # ------------------------------------------------------------------ setup

    async def async_setup(self) -> None:
        today = self._today().isoformat()
        self.data = await self.store.async_load(self.name, self.avatar, today)
        self.skills = {
            skill: SkillState.from_dict(self.data["skills"].get(skill, {}))
            for skill in ALL_SKILLS
        }
        self._check_rollover()
        # A few seconds past midnight: roll the day over even while idle.
        self._unsub_midnight = async_track_time_change(
            self.hass, self._handle_midnight, hour=0, minute=0, second=5
        )

    async def async_unload(self) -> None:
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None
        self.sessions.clear()
        self._sync_skills()
        await self.store.async_save_now()

    @callback
    def _handle_midnight(self, _now) -> None:
        self._check_rollover()
        self._save()
        self._notify()

    # ------------------------------------------------------------------ time helpers

    def _today(self) -> date:
        return dt_util.now().date()

    def _check_rollover(self) -> None:
        """Lazily reset daily/weekly buckets and settle the streak."""
        today = self._today()
        today_iso = today.isoformat()
        yesterday_iso = (today - timedelta(days=1)).isoformat()

        daily = self.data["daily"]
        if daily["date"] != today_iso:
            streak = self.data["streak"]
            if streak["current"] > 0 and streak["last_goal_date"] not in (
                yesterday_iso,
                today_iso,
            ):
                # The chain broke. A freeze can bridge exactly one missed day.
                day_before = (today - timedelta(days=2)).isoformat()
                if streak["freezes"] > 0 and streak["last_goal_date"] == day_before:
                    streak["freezes"] -= 1
                    streak["freeze_log"].append(yesterday_iso)
                    streak["last_goal_date"] = yesterday_iso
                    _LOGGER.debug("Streak freeze used to cover %s", yesterday_iso)
                else:
                    streak["current"] = 0
            self.data["daily"] = _default_daily(today_iso)

        week_start = (today - timedelta(days=today.weekday())).isoformat()
        if self.data["weekly"]["week_start"] != week_start:
            self.data["weekly"] = _default_weekly(week_start)
        self._ensure_challenges()

    def _ensure_challenges(self) -> None:
        weekly = self.data["weekly"]
        expected_prefix = weekly["week_start"]
        current = weekly.get("challenges") or []
        if not current or not all(c["id"].startswith(expected_prefix) for c in current):
            weekly["challenges"] = challenges.generate_week(
                expected_prefix, self.profile_id
            )

    def _bump_challenges(self, events: list, deltas: dict[str, int]) -> None:
        """Advance weekly challenge progress; award XP/freeze on completion."""
        weekly = self.data["weekly"]
        for challenge in weekly.get("challenges", []):
            if challenge["done"]:
                continue
            if challenge["type"] == "modes":
                challenge["progress"] = len(set(weekly["modes_played"]))
            elif challenge["type"] in deltas:
                challenge["progress"] += deltas[challenge["type"]]
            if challenge["progress"] >= challenge["target"]:
                challenge["done"] = True
                self._add_xp(challenges.CHALLENGE_XP, events)
                all_done = all(c["done"] for c in weekly["challenges"])
                if all_done:
                    streak = self.data["streak"]
                    streak["freezes"] = min(MAX_FREEZES, streak["freezes"] + 1)
                events.append(
                    (
                        EVENT_CHALLENGE_COMPLETE,
                        {
                            "profile_id": self.profile_id,
                            "name": self.name,
                            "challenge": challenges.describe(challenge),
                            "all_done": all_done,
                        },
                    )
                )

    # ------------------------------------------------------------------ sessions

    def start_session(self, mode: str, length: int) -> dict:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode}")
        self._check_rollover()
        if len(self.sessions) >= MAX_ACTIVE_SESSIONS:
            # Drop the oldest abandoned session rather than leaking memory.
            self.sessions.pop(next(iter(self.sessions)))
        session_id = secrets.token_hex(8)
        session = GameSession(
            session_id, mode, length, self.skills, self.banks, random.Random(),
            xp_multiplier=BOSS_XP_MULTIPLIER if mode == "boss_battle" else 1.0,
        )
        self.sessions[session_id] = session
        question = session.next_question()
        return {
            "session_id": session_id,
            "total": session.length,
            "question": question.to_wire(session.index, session.length),
        }

    def submit_answer(self, session_id: str, question_id: str, answer: str,
                      elapsed_ms: int) -> dict:
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionError("session_not_found")
        self._check_rollover()

        outcome = session.submit(question_id, answer, elapsed_ms)
        response: dict[str, Any] = {
            "correct": outcome.correct,
            "correct_answer": outcome.correct_answer,
            "explain": outcome.explain,
            "xp_delta": outcome.xp_delta,
            "run_streak": outcome.run_streak,
            "speed_bonus": outcome.speed_bonus,
        }

        events: list[tuple[str, dict]] = []
        new_badges: list[str] = []
        self._apply_answer(session, outcome, events, new_badges)

        if outcome.done:
            results = session.results()
            round_dict = {
                "mode": results.mode,
                "total": results.total,
                "correct": results.correct,
                "xp_gained": results.xp_gained,
                "speed_bonuses": results.speed_bonuses,
                "best_run_streak": results.best_run_streak,
                "avg_ms": results.avg_ms,
                "skill_changes": results.skill_changes,
            }
            level_up = self._finish_round(session, round_dict, events, new_badges)
            level, _, _ = level_progress(self.data["xp"]["total"])
            round_dict["level_up"] = level_up
            round_dict["new_level"] = level
            round_dict["new_badges"] = [badge_public(b, "now") for b in new_badges]
            round_dict["daily_goal_met"] = self.data["daily"]["goal_met"]
            response["results"] = round_dict
            self.sessions.pop(session_id, None)
        else:
            question = session.next_question()
            response["next_question"] = question.to_wire(session.index, session.length)
            response["new_badges"] = [badge_public(b, "now") for b in new_badges]

        self._save()
        self._notify()
        for event_type, payload in events:
            self.hass.bus.async_fire(event_type, payload)
        return response

    def abandon_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self._save()

    # ------------------------------------------------------------------ Fly Snap arcade

    def start_arcade(self, category: str) -> dict:
        if category not in arcade.CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        self._check_rollover()
        if len(self.arcades) >= MAX_ACTIVE_ARCADES:
            self.arcades.pop(next(iter(self.arcades)))
        skill = arcade.skill_for_category(category)
        band = self.skills[skill].band
        rounds_data = arcade.build_game(category, band, self.banks, random.Random())
        arcade_id = secrets.token_hex(8)
        self.arcades[arcade_id] = {"category": category, "skill": skill}
        return {
            "arcade_id": arcade_id,
            "category": category,
            "skill": skill,
            "rounds": arcade.ROUNDS,
            "round_time_s": arcade.ROUND_TIME_S,
            "lives": arcade.LIVES,
            "travel_s": arcade.TRAVEL_S,
            "rounds_data": rounds_data,
        }

    def finish_arcade(self, arcade_id: str, rounds_completed: int, rounds_played: int,
                      correct: int, wrong: int, won: bool) -> dict:
        meta = self.arcades.pop(arcade_id, None)
        if meta is None:
            raise SessionError("arcade_not_found")
        self._check_rollover()

        # Clamp client-reported numbers to what's physically plausible.
        rounds_played = max(1, min(rounds_played, arcade.MAX_ROUNDS_PLAYED))
        rounds_completed = max(0, min(rounds_completed, arcade.ROUNDS, rounds_played))
        counted_correct = max(0, min(correct, arcade.MAX_SNAPS_PER_ROUND * rounds_played))
        counted_wrong = max(0, min(wrong, arcade.MAX_COUNTED_WRONG))
        won = bool(won) and rounds_completed >= arcade.ROUNDS

        # Feed the adaptive system a capped, proportionally-split sample so one
        # game can't monopolise the rolling window. Neutral time proxy.
        skill = meta["skill"]
        state = self.skills[skill]
        total = counted_correct + counted_wrong
        samples = min(total, arcade.MAX_ADAPTIVE_SAMPLES)
        if total:
            correct_samples = round(samples * counted_correct / total)
            proxy_ms = adaptive.target_ms(skill)
            for _ in range(correct_samples):
                adaptive.record_answer(state, skill, True, proxy_ms)
            for _ in range(samples - correct_samples):
                adaptive.record_answer(state, skill, False, proxy_ms)

        xp = (
            arcade.XP_SNAP * counted_correct
            + arcade.XP_ROUND_SURVIVED * rounds_completed
            + (arcade.XP_ARCADE_WIN if won else 0)
        )

        events: list[tuple[str, dict]] = []
        new_badges: list[str] = []
        daily = self.data["daily"]
        weekly = self.data["weekly"]
        questions = counted_correct + min(counted_wrong, 10)
        daily["questions"] += questions
        daily["correct"] += counted_correct
        daily["rounds"] += 1
        daily["xp_today"] += xp
        weekly["questions"] += questions
        weekly["correct"] += counted_correct
        weekly["rounds"] += 1
        per_day = weekly["per_day"].setdefault(daily["date"], {"q": 0, "c": 0})
        per_day["q"] += questions
        per_day["c"] += counted_correct
        for bucket in (daily, weekly):
            if "fly_snap" not in bucket["modes_played"]:
                bucket["modes_played"].append("fly_snap")

        level_up = self._add_xp(xp, events)

        stats = self.data["arcade"]
        stats["games"] += 1
        stats["best_round"] = max(stats["best_round"], rounds_completed)
        if won:
            stats["wins"] += 1
            if meta["category"] not in stats["categories_won"]:
                stats["categories_won"].append(meta["category"])

        history = self.data["history"]
        history.append(
            {
                "ts": dt_util.now().isoformat(),
                "mode": "fly_snap",
                "questions": questions,
                "correct": counted_correct,
                "xp": xp,
                "avg_ms": 0,
            }
        )
        del history[:-MAX_HISTORY]

        self._bump_challenges(
            events,
            {"arcade_games": 1, "questions": questions, "correct": counted_correct, "xp": xp},
        )
        if not daily["goal_met"] and daily["questions"] >= self.daily_goal:
            self._meet_daily_goal(events, new_badges)
        new_badges += self._check_badges({"trigger": "arcade"}, events)

        events.append(
            (
                EVENT_SESSION_COMPLETE,
                {
                    "profile_id": self.profile_id,
                    "name": self.name,
                    "mode": "fly_snap",
                    "correct": counted_correct,
                    "total": questions,
                    "xp_gained": xp,
                },
            )
        )

        self._save()
        self._notify()
        for event_type, payload in events:
            self.hass.bus.async_fire(event_type, payload)

        level, _, _ = level_progress(self.data["xp"]["total"])
        return {
            "xp_gained": xp,
            "correct_counted": counted_correct,
            "rounds_completed": rounds_completed,
            "won": won,
            "level_up": level_up,
            "new_level": level,
            "new_badges": [badge_public(b, "now") for b in new_badges],
            "daily_goal_met": daily["goal_met"],
        }

    # ------------------------------------------------------------------ scoring plumbing

    def _apply_answer(self, session: GameSession, outcome, events, new_badges) -> None:
        daily = self.data["daily"]
        weekly = self.data["weekly"]
        today_iso = daily["date"]

        daily["questions"] += 1
        weekly["questions"] += 1
        per_day = weekly["per_day"].setdefault(today_iso, {"q": 0, "c": 0})
        per_day["q"] += 1
        if outcome.correct:
            daily["correct"] += 1
            weekly["correct"] += 1
            per_day["c"] += 1
        daily["xp_today"] += outcome.xp_delta
        self._add_xp(outcome.xp_delta, events)
        self._sync_skills()

        deltas = {"questions": 1, "xp": outcome.xp_delta}
        if outcome.correct:
            deltas["correct"] = 1
            subject = outcome.skill.split(".", 1)[0]
            deltas[f"{subject}_correct"] = 1
        if outcome.speed_bonus:
            deltas["speed"] = 1
        self._bump_challenges(events, deltas)

        if not daily["goal_met"] and daily["questions"] >= self.daily_goal:
            self._meet_daily_goal(events, new_badges)

        new_badges += self._check_badges({"trigger": "answer"}, events)

    def _meet_daily_goal(self, events, new_badges) -> None:
        daily = self.data["daily"]
        streak = self.data["streak"]
        today = self._today()
        today_iso = today.isoformat()
        yesterday_iso = (today - timedelta(days=1)).isoformat()

        daily["goal_met"] = True
        daily["met_at"] = dt_util.now().isoformat()

        if streak["last_goal_date"] == yesterday_iso:
            streak["current"] += 1
        elif streak["last_goal_date"] != today_iso:
            streak["current"] = 1
        streak["last_goal_date"] = today_iso
        streak["best"] = max(streak["best"], streak["current"])
        if streak["current"] > 0 and streak["current"] % 7 == 0:
            streak["freezes"] = min(MAX_FREEZES, streak["freezes"] + 1)

        accuracy = (
            round(daily["correct"] / daily["questions"] * 100) if daily["questions"] else 0
        )
        events.append(
            (
                EVENT_DAILY_GOAL,
                {
                    "profile_id": self.profile_id,
                    "name": self.name,
                    "streak": streak["current"],
                    "questions": daily["questions"],
                    "accuracy": accuracy,
                },
            )
        )
        if streak["current"] in STREAK_MILESTONES:
            events.append(
                (
                    EVENT_STREAK_MILESTONE,
                    {
                        "profile_id": self.profile_id,
                        "name": self.name,
                        "streak": streak["current"],
                    },
                )
            )

        comeback = yesterday_iso in self.data["streak"].get("freeze_log", [])
        new_badges += self._check_badges({"trigger": "goal", "comeback": comeback}, events)

    def _finish_round(self, session: GameSession, round_dict: dict, events, new_badges) -> bool:
        daily = self.data["daily"]
        weekly = self.data["weekly"]
        daily["rounds"] += 1
        weekly["rounds"] += 1
        if session.mode_id not in daily["modes_played"]:
            daily["modes_played"].append(session.mode_id)
        if session.mode_id not in weekly["modes_played"]:
            weekly["modes_played"].append(session.mode_id)

        history = self.data["history"]
        history.append(
            {
                "ts": dt_util.now().isoformat(),
                "mode": session.mode_id,
                "questions": round_dict["total"],
                "correct": round_dict["correct"],
                "xp": round_dict["xp_gained"],
                "avg_ms": round_dict["avg_ms"],
            }
        )
        del history[:-MAX_HISTORY]

        if session.mode_id == "boss_battle":
            round_dict["boss_defeated"] = round_dict["correct"] >= BOSS_DEFEAT_THRESHOLD

        # Per-answer XP was already added; top up the round-completion bonus
        # (mirroring the session's multiplier so its XP total and ours agree).
        from math import ceil

        from .engine.session import XP_ROUND_COMPLETE

        bonus = ceil(XP_ROUND_COMPLETE * session.xp_multiplier)
        daily["xp_today"] += bonus
        level_up = self._add_xp(bonus, events)

        deltas = {"xp": bonus}
        if round_dict["correct"] == round_dict["total"] and round_dict["total"] >= 10:
            deltas["perfect_rounds"] = 1
        if round_dict.get("boss_defeated"):
            deltas["boss_wins"] = 1
        self._bump_challenges(events, deltas)

        events.append(
            (
                EVENT_SESSION_COMPLETE,
                {
                    "profile_id": self.profile_id,
                    "name": self.name,
                    "mode": session.mode_id,
                    "correct": round_dict["correct"],
                    "total": round_dict["total"],
                    "xp_gained": round_dict["xp_gained"],
                },
            )
        )
        new_badges += self._check_badges({"trigger": "round", "round": round_dict}, events)
        return level_up

    def _add_xp(self, amount: int, events) -> bool:
        xp = self.data["xp"]
        old_level, _, _ = level_progress(xp["total"])
        xp["total"] += amount
        new_level, _, _ = level_progress(xp["total"])
        xp["level"] = new_level
        if new_level > old_level:
            events.append(
                (
                    EVENT_LEVEL_UP,
                    {
                        "profile_id": self.profile_id,
                        "name": self.name,
                        "level": new_level,
                        "xp_total": xp["total"],
                    },
                )
            )
            return True
        return False

    def _check_badges(self, ctx: dict, events) -> list[str]:
        self._sync_skills()
        new = check_badges(self.data, ctx)
        now_iso = dt_util.now().isoformat()
        for badge_id in new:
            self.data["badges"][badge_id] = now_iso
            badge = badge_public(badge_id, now_iso)
            events.append(
                (
                    EVENT_BADGE_EARNED,
                    {
                        "profile_id": self.profile_id,
                        "name": self.name,
                        "badge_id": badge_id,
                        "badge_name": badge["name"],
                    },
                )
            )
        return new

    def _sync_skills(self) -> None:
        self.data["skills"] = {
            skill: state.to_dict() for skill, state in self.skills.items()
        }

    def _save(self) -> None:
        self._sync_skills()
        self.store.schedule_save()

    def _notify(self) -> None:
        async_dispatcher_send(
            self.hass, f"{SIGNAL_PROFILE_UPDATED}_{self.entry.entry_id}"
        )

    # ------------------------------------------------------------------ payloads for the card

    def profile_summary(self) -> dict:
        self._check_rollover()
        level, _, _ = level_progress(self.data["xp"]["total"])
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "avatar": self.avatar,
            "level": level,
            "streak": self.data["streak"]["current"],
        }

    def stats_payload(self) -> dict:
        self._check_rollover()
        xp = self.data["xp"]
        level, into, to_next = level_progress(xp["total"])
        daily = self.data["daily"]
        accuracy = (
            round(daily["correct"] / daily["questions"] * 100)
            if daily["questions"]
            else None
        )
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "avatar": self.avatar,
            "xp": {"total": xp["total"], "level": level, "into_level": into, "to_next": to_next},
            "streak": {
                "current": self.data["streak"]["current"],
                "best": self.data["streak"]["best"],
                "freezes": self.data["streak"]["freezes"],
            },
            "daily": {
                "questions": daily["questions"],
                "correct": daily["correct"],
                "rounds": daily["rounds"],
                "xp_today": daily["xp_today"],
                "goal": self.daily_goal,
                "goal_met": daily["goal_met"],
                "accuracy": accuracy,
            },
            "weekly": {
                "questions": self.data["weekly"]["questions"],
                "correct": self.data["weekly"]["correct"],
                "rounds": self.data["weekly"]["rounds"],
            },
            "skills": {
                skill: {"band": state.band, "mastery": round(state.mastery)}
                for skill, state in self.skills.items()
            },
            "modes": {
                mode_id: {
                    "name": mode["name"],
                    "subject": mode["subject"],
                    "emoji": mode["emoji"],
                    "skills": mode["skills"],
                }
                for mode_id, mode in MODES.items()
            },
            "history": list(reversed(self.data["history"][-5:])),
            "badge_count": len(self.data["badges"]),
            "challenges": [
                challenges.describe(c)
                for c in self.data["weekly"].get("challenges", [])
            ],
            "arcade": {
                "name": "Fly Snap",
                "emoji": "🐸",
                "categories": list(arcade.CATEGORIES),
                "games": self.data["arcade"]["games"],
                "wins": self.data["arcade"]["wins"],
                "best_round": self.data["arcade"]["best_round"],
            },
        }

    def badges_payload(self) -> dict:
        earned = [
            badge_public(badge_id, ts)
            for badge_id, ts in self.data["badges"].items()
        ]
        from .engine.badges import BADGES

        locked = [
            badge_public(b["id"])
            for b in BADGES
            if b["id"] not in self.data["badges"]
        ]
        return {"earned": earned, "locked": locked}

    # ------------------------------------------------------------------ sensor helpers

    def maths_mastery(self) -> tuple[float | None, dict]:
        return self._subject_mastery(MATHS_SKILLS)

    def english_mastery(self) -> tuple[float | None, dict]:
        return self._subject_mastery(ENGLISH_SKILLS)

    def _subject_mastery(self, skill_ids: list[str]) -> tuple[float | None, dict]:
        states = {s: self.skills[s] for s in skill_ids if s in self.skills}
        if not states:
            return None, {}
        mean = round(sum(s.mastery for s in states.values()) / len(states), 1)
        attrs = {
            skill.split(".", 1)[1]: {"band": state.band, "mastery": round(state.mastery, 1)}
            for skill, state in states.items()
        }
        return mean, attrs
