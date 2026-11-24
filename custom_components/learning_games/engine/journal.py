"""Learning journal: subjects, daily entries and per-subject stats. Pure Python.

Storage shape (``data["journal"]``)::

    {
      "subjects": {slug: {"id", "name", "emoji", "created", "hidden", "merged_into"}},
      "entries":  {iso_date: {"date", "created_ts", "updated_ts", "mood",
                              "subjects": [{"id", "enjoy", "difficulty", "note"}],
                              "did", "enjoyed", "tricky", "xp_awarded",
                              "reviews": [...], "seen_reviews"}},
    }

Subjects are never deleted — only hidden or merged — so past entries always
resolve to a name.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher

EDITABLE_DAYS = 3  # today + 2 days back
MAX_TEXT = 500
MAX_NOTE = 140
MAX_SUBJECT_NAME = 30
MAX_SUBJECTS_PER_ENTRY = 15
MAX_COMMENT = 300
SIMILAR_RATIO = 0.85
JOURNAL_XP = 15

DIFFICULTIES = ("easy", "ok", "tricky")
REACTIONS = ("⭐", "❤️", "👏", "😂", "🌟", "🤩", "💪")

DEFAULT_SUBJECTS: tuple[tuple[str, str], ...] = (
    ("Reading", "📚"),
    ("Writing", "✏️"),
    ("Spelling", "🔤"),
    ("Maths", "🔢"),
    ("Science", "🔬"),
    ("History", "🏰"),
    ("Geography", "🌍"),
    ("Art", "🎨"),
    ("Music", "🎵"),
    ("PE/Sport", "⚽"),
    ("French", "🇫🇷"),
    ("Computing", "💻"),
)


class JournalError(ValueError):
    """Raised for invalid journal input; ``code`` is sent to the card."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# ---------------------------------------------------------------- subjects


def slugify(name: str) -> str:
    """Normalise a subject name to a stable id: 'P.E. / Sport' -> 'pe_sport'."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s/_-]", "", text)  # drop dots etc. so P.E. -> pe
    text = re.sub(r"[\s/_-]+", "_", text).strip("_")
    return text


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())[:MAX_SUBJECT_NAME]


def default_journal(created: str) -> dict:
    return {
        "subjects": {
            slugify(name): _subject(name, emoji, created) for name, emoji in DEFAULT_SUBJECTS
        },
        "entries": {},
    }


def _subject(name: str, emoji: str, created: str) -> dict:
    return {
        "id": slugify(name),
        "name": name,
        "emoji": emoji or "📘",
        "created": created,
        "hidden": False,
        "merged_into": None,
    }


def resolve(journal: dict, subject_id: str) -> str:
    """Follow merged_into links to the surviving subject id."""
    subjects = journal["subjects"]
    seen = set()
    while subject_id in subjects and subjects[subject_id].get("merged_into"):
        if subject_id in seen:  # defensive: never loop forever
            break
        seen.add(subject_id)
        subject_id = subjects[subject_id]["merged_into"]
    return subject_id


def active_subjects(journal: dict, include_hidden: bool = False) -> list[dict]:
    return [
        s for s in journal["subjects"].values()
        if not s.get("merged_into") and (include_hidden or not s.get("hidden"))
    ]


def find_similar(name: str, journal: dict) -> list[dict]:
    """Existing (unmerged) subjects whose name is close to ``name``."""
    slug = slugify(name)
    if not slug:
        return []
    out = []
    for subject in journal["subjects"].values():
        if subject.get("merged_into"):
            continue
        other = subject["id"]
        if other == slug:
            continue
        ratio = SequenceMatcher(None, slug, other).ratio()
        shorter = min(len(slug), len(other))
        prefix = shorter >= 3 and (slug.startswith(other) or other.startswith(slug))
        if ratio >= SIMILAR_RATIO or prefix:
            out.append(subject)
    return out


def add_subject(journal: dict, name: str, emoji: str, created: str,
                force: bool = False) -> dict:
    """Add a subject, or return the existing/similar ones.

    Returns ``{"status": "exists"|"similar"|"added", "subject": ..., "similar": [...]}``.
    """
    name = clean_name(name)
    slug = slugify(name)
    if not slug:
        raise JournalError("invalid_name", "Please type a subject name")
    subjects = journal["subjects"]
    if slug in subjects:
        target = subjects[resolve(journal, slug)]
        target["hidden"] = False
        return {"status": "exists", "subject": target, "similar": []}
    if not force:
        similar = find_similar(name, journal)
        if similar:
            return {"status": "similar", "subject": None, "similar": similar}
    subject = _subject(name, (emoji or "").strip()[:8], created)
    subjects[slug] = subject
    return {"status": "added", "subject": subject, "similar": []}


def update_subject(journal: dict, subject_id: str, name: str | None = None,
                   emoji: str | None = None, hidden: bool | None = None) -> dict:
    """Rename / re-emoji / hide. The id (slug) never changes, so history is safe."""
    subject = journal["subjects"].get(subject_id)
    if subject is None or subject.get("merged_into"):
        raise JournalError("unknown_subject")
    if name is not None:
        name = clean_name(name)
        if not slugify(name):
            raise JournalError("invalid_name", "Please type a subject name")
        clash = slugify(name)
        if clash != subject_id and clash in journal["subjects"]:
            raise JournalError("name_taken", "Another subject already has that name — merge instead")
        subject["name"] = name
    if emoji is not None:
        subject["emoji"] = emoji.strip()[:8] or subject["emoji"]
    if hidden is not None:
        subject["hidden"] = bool(hidden)
    return subject


def merge_subject(journal: dict, src: str, dst: str) -> dict:
    """Fold ``src`` into ``dst``: rewrite past entries and mark src merged."""
    subjects = journal["subjects"]
    if src == dst or src not in subjects or dst not in subjects:
        raise JournalError("unknown_subject")
    dst = resolve(journal, dst)
    if src == dst:
        raise JournalError("unknown_subject")
    for entry in journal["entries"].values():
        merged: list[dict] = []
        by_id: dict[str, dict] = {}
        for item in entry.get("subjects", []):
            sid = dst if item["id"] == src else item["id"]
            if sid in by_id:  # both ticked on one day — keep the first rating
                continue
            item = {**item, "id": sid}
            by_id[sid] = item
            merged.append(item)
        entry["subjects"] = merged
    subjects[src]["merged_into"] = dst
    subjects[src]["hidden"] = True
    return subjects[dst]


# ---------------------------------------------------------------- entries


def editable_dates(today: date) -> list[str]:
    return [(today - timedelta(days=i)).isoformat() for i in range(EDITABLE_DAYS)]


def _text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def validate_entry(journal: dict, payload: dict, today: date) -> dict:
    """Return a clean entry body from a card payload, or raise JournalError."""
    entry_date = payload.get("date")
    if entry_date not in editable_dates(today):
        raise JournalError("date_locked", "You can only write about today or the last 2 days")
    mood = payload.get("mood")
    if mood is not None and (not isinstance(mood, int) or not 1 <= mood <= 5):
        raise JournalError("invalid_mood")

    items: list[dict] = []
    seen: set[str] = set()
    for raw in payload.get("subjects") or []:
        sid = resolve(journal, str(raw.get("id", "")))
        if sid not in journal["subjects"]:
            raise JournalError("unknown_subject")
        if sid in seen:
            continue
        seen.add(sid)
        enjoy = raw.get("enjoy")
        if enjoy is not None and (not isinstance(enjoy, int) or not 1 <= enjoy <= 5):
            raise JournalError("invalid_rating")
        difficulty = raw.get("difficulty")
        if difficulty is not None and difficulty not in DIFFICULTIES:
            raise JournalError("invalid_rating")
        items.append(
            {
                "id": sid,
                "enjoy": enjoy,
                "difficulty": difficulty,
                "note": _text(raw.get("note"), MAX_NOTE),
            }
        )
    if len(items) > MAX_SUBJECTS_PER_ENTRY:
        raise JournalError("too_many_subjects")

    body = {
        "date": entry_date,
        "mood": mood,
        "subjects": items,
        "did": _text(payload.get("did"), MAX_TEXT),
        "enjoyed": _text(payload.get("enjoyed"), MAX_TEXT),
        "tricky": _text(payload.get("tricky"), MAX_TEXT),
    }
    if not items and not (body["did"] or body["enjoyed"] or body["tricky"]):
        raise JournalError("empty_entry", "Tick a subject or write something first")
    return body


def upsert_entry(journal: dict, body: dict, now_iso: str) -> tuple[dict, bool]:
    """Store ``body``; returns (entry, is_update)."""
    entries = journal["entries"]
    existing = entries.get(body["date"])
    if existing is None:
        entry = {
            **body,
            "created_ts": now_iso,
            "updated_ts": now_iso,
            "xp_awarded": False,
            "reviews": [],
            "seen_reviews": True,
        }
        entries[body["date"]] = entry
        return entry, False
    existing.update(body)
    existing["updated_ts"] = now_iso
    return existing, True


def add_review(entry: dict, user_id: str, user_name: str, reaction: str | None,
               comment: str, now_iso: str) -> dict:
    if reaction is not None and reaction not in REACTIONS:
        raise JournalError("invalid_reaction")
    comment = _text(comment, MAX_COMMENT)
    if not reaction and not comment:
        raise JournalError("empty_review", "Pick a sticker or write a comment")
    review = {
        "user_id": user_id,
        "user_name": user_name,
        "ts": now_iso,
        "reaction": reaction,
        "comment": comment,
    }
    entry.setdefault("reviews", []).append(review)
    entry["seen_reviews"] = False
    return review


def snippet(entry: dict, limit: int = 140) -> str:
    for key in ("did", "enjoyed", "tricky"):
        if entry.get(key):
            text = entry[key]
            return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
    notes = [s["note"] for s in entry.get("subjects", []) if s.get("note")]
    return notes[0][:limit] if notes else ""


def subject_names(journal: dict, entry: dict) -> list[str]:
    names = []
    for item in entry.get("subjects", []):
        subject = journal["subjects"].get(resolve(journal, item["id"]))
        if subject:
            names.append(subject["name"])
    return names


# ---------------------------------------------------------------- stats


def journal_streak(entries: dict, today: date) -> int:
    """Consecutive days with an entry, ending today (or yesterday)."""
    day = today if today.isoformat() in entries else today - timedelta(days=1)
    streak = 0
    while day.isoformat() in entries:
        streak += 1
        day -= timedelta(days=1)
    return streak


def subject_stats(journal: dict, today: date) -> list[dict]:
    """Per-subject usage + feelings, most-done first."""
    recent_cut = (today - timedelta(days=28)).isoformat()
    prior_cut = (today - timedelta(days=56)).isoformat()
    acc: dict[str, dict] = {}
    for iso, entry in journal["entries"].items():
        for item in entry.get("subjects", []):
            sid = resolve(journal, item["id"])
            s = acc.setdefault(
                sid,
                {"count": 0, "last_done": None, "enjoy": [], "recent": [], "prior": [],
                 "easy": 0, "ok": 0, "tricky": 0},
            )
            s["count"] += 1
            if s["last_done"] is None or iso > s["last_done"]:
                s["last_done"] = iso
            if item.get("enjoy"):
                s["enjoy"].append(item["enjoy"])
                if iso > recent_cut:
                    s["recent"].append(item["enjoy"])
                elif iso > prior_cut:
                    s["prior"].append(item["enjoy"])
            if item.get("difficulty") in DIFFICULTIES:
                s[item["difficulty"]] += 1

    def avg(values):
        return round(sum(values) / len(values), 1) if values else None

    out = []
    for subject in active_subjects(journal, include_hidden=True):
        s = acc.get(subject["id"])
        if not s:
            continue
        recent, prior = avg(s["recent"]), avg(s["prior"])
        trend = None
        if recent is not None and prior is not None:
            diff = recent - prior
            trend = "up" if diff >= 0.5 else "down" if diff <= -0.5 else "steady"
        out.append(
            {
                "id": subject["id"],
                "name": subject["name"],
                "emoji": subject["emoji"],
                "count": s["count"],
                "last_done": s["last_done"],
                "avg_enjoy": avg(s["enjoy"]),
                "easy": s["easy"],
                "ok": s["ok"],
                "tricky": s["tricky"],
                "trend": trend,
            }
        )
    out.sort(key=lambda x: (-x["count"], x["name"].lower()))
    return out


def distinct_subjects_logged(journal: dict) -> int:
    return len(
        {
            resolve(journal, item["id"])
            for entry in journal["entries"].values()
            for item in entry.get("subjects", [])
        }
    )
