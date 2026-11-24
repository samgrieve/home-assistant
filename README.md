# Learning Games for Home Assistant

Fun, adaptive **maths and English games** for kids, built right into Home Assistant.
Designed for a tablet on the kitchen side: big touch buttons, confetti, XP, levels,
daily streaks and badges — with real HA sensors and events so you can wire her
progress up to real-world rewards (lights, announcements, TV time).

Aimed at UK Year 5 (ages 9–10) but every skill adapts across five difficulty
bands based on accuracy and speed, so it stays challenging as she grows.

## What's inside

**10 question modes** (each round is 10 quick questions):

| Maths | English |
|---|---|
| ⚡ Times Table Blitz — ×/÷ facts to 12 | ⭐ Spelling Star — correct spelling, missing letters, unscramble |
| 🔢 Number Crunch — add, subtract, place value, rounding | 🧙 Word Wizard — synonyms, antonyms, definitions |
| ✖️ Big Multiply — long multiplication, division with remainders | 🔍 Word Detective — word classes, punctuation |
| 🧪 Fraction Lab — fractions, decimals, negative numbers | 👯 Tricky Twins — homophones (their/there/they're…) |
| 🛒 Shop Keeper — money: totals, change, coins, best value (UK £/p) | 🧱 Word Builder — prefixes, suffixes, root words |

**Plus the Challenges row:**
- 🎯 **Today's Focus** — a mixed round aimed at what she most needs: about 70% of questions come from her weakest topics, untried topics and anything she marked as *tricky* in her journal in the last fortnight. The other 30% are easy wins from her strongest topics, so it stays fun. The tile says why ("Fractions — you said it was tricky"), and the results show how each focus topic moved
- 👾 **Boss Battle** — 10 questions drawn from her four weakest skills, at 1.5× XP, with a boss HP bar that drops with every correct answer. Score 7+ to make the boss flee!
- 🐸 **Fly Snap** — a real-time arcade game: a frog sits on a lilypad with a word above it while six flies drift inward, each carrying a word. Tap the fly that matches (synonyms, antonyms or homophones). Survive 60 seconds to clear a round, beat 6 speeding-up rounds to win, and don't let a fly reach the lilypad — you have 3 lives.

**📊 Statistics** (tap *Statistics* on the home screen)
- Score summary: level, best streak, questions and accuracy over the last 30 days, active days and total XP
- A GitHub-style **heat map** of daily usage across the last 30 days
- **Strongest** and **keep practising** areas, ranked from per-skill mastery and accuracy

**📔 Learning Journal** (tap *My Journal* on the home screen)
- Each day she ticks the subjects she did *outside* the games (12 starter subjects, add your own)
- Every ticked subject gets a quick rating: how much she enjoyed it (5 faces) and how hard it was (Easy / OK / Tricky), plus an optional note
- **Which bit was tricky?** If she marks Maths, Spelling, Reading or Writing as Tricky, she can tap the exact game topics (for example Fractions or Long multiplication). Those topics get extra practice in Today's Focus and come up a little more in the other games and the Boss Battle. Parents can link any subject to game topics in the 🗂️ Subjects manager
- Three short prompts: *What did I do? What did I enjoy? What was easy or tricky?*
- She can write about today or catch up on the last 2 days; older entries are locked
- Adding a subject always shows the existing list first and asks "Did you mean Science?" for near-duplicates. Parents can rename, hide or **merge** subjects, and merging moves past entries across
- Per-subject history: how often each subject is done, average enjoyment, the easy-to-tricky split and the enjoyment trend
- +15 XP for her first entry each day. It does **not** count toward the daily question goal
- Parents (set in the integration options) can react with a sticker and leave a note, and she sees "💌 Dad sent you ⭐" on her home screen

**📅 Weekly summary**
- `sensor.<name>_weekly_summary`: its state is the week's start date. Its attributes cover the week's questions, accuracy, days played, days the goal was met, XP, badges, topics that improved, topics that need work and topics not practised. They also include journal highlights (subjects, what she loved, what was tricky) and ready-made `parent_title` / `parent_text` / `kid_title` / `kid_text` for notifications. Her own journal writing is never included
- The Statistics screen has a **This week** section, with a comparison against last week. The last 12 weeks are kept for trends
- Deep link `?lg=stats` opens Statistics directly

**🎒 Grows with her**
- Set her **School year** in the integration options. It moves up automatically every 1 September and appears in the card header, the summary and the `level` sensor's `school_year` attribute
- Topics she hasn't tried yet start at the right level for her year. Bands she has already earned are never lowered
- Today's question content spans roughly Years 4–6. Year 7 / KS3 content (algebra, ratio, harder spelling) is planned for a later release

**Progression & engagement**
- XP for every answer, speed bonuses, streak bonuses, levels
- Daily goal (configurable) and a daily streak with ❄️ streak-freeze tokens
- **3 weekly challenges** (deterministic per week, e.g. "Score 10/10 in 2 rounds") worth +100 XP each — complete all three for a bonus streak freeze
- 27 badges to collect, per-skill mastery stars on every game tile
- Adaptive difficulty: each of the 17 tracked skills moves up/down 5 bands automatically

**For parents**
- Sensors: level, streak, questions today, accuracy, maths/English mastery (per-skill detail in attributes), last badge, weekly summary
- `binary_sensor.<name>_daily_goal_met` — the prime automation hook
- Events: `learning_games_daily_goal`, `learning_games_level_up`, `learning_games_badge_earned`, `learning_games_streak_milestone`, `learning_games_session_complete`, `learning_games_challenge_complete`, `learning_games_journal_entry`, `learning_games_journal_reviewed`
- `sensor.<name>_journal`: state is the date of the latest entry; attributes are `total_entries`, `entries_this_week`, `journal_streak`, `unreviewed_count`, `last_entry` and a per-subject summary. Journal text is never put in attributes, so it stays out of the recorder
- `sensor.<name>_weekly_challenges_done` (0–3) with the full challenge list in attributes
- All answers are checked server-side — no peeking at the answer in the browser

## Installation

### HACS (recommended)
1. HACS → ⋮ → *Custom repositories* → add this repo as type **Integration**
2. Install **Learning Games**, restart Home Assistant

### Manual
Copy `custom_components/learning_games/` into your `config/custom_components/`
folder and restart.

## Setup

1. **Settings → Devices & services → Add integration → Learning Games**
2. Enter your child's name, pick an avatar and a daily goal → one profile is
   created per child (add the integration again for siblings)
3. Add the card to a dashboard (the card is served automatically — no resource
   registration needed):

```yaml
type: custom:learning-games-card
# optional:
# profile: Maya      # only needed with more than one profile
# sounds: false      # turn off the bleeps
```

4. **Settings → Devices & services → Learning Games → Configure**: set her
   **School year**, and tick the Home Assistant users who are parents. Parents
   can react to and reply to journal entries, and manage the subject list.

A panel-view dashboard works best on a tablet:
Dashboard → ⋮ → Edit → ⋮ → *Raw configuration editor*, or just place the card
in a single-column view.

## Reward automation recipes

**Sunday summary** (send `kid_title`/`kid_text` to her own devices in a second action):

```yaml
automation:
  - alias: Learning Games - Sunday summary (parents)
    triggers:
      - trigger: time
        at: "18:00:00"
    conditions:
      - condition: time
        weekday: sun
    actions:
      - action: notify.mobile_app_parent_phone
        data:
          title: "{{ state_attr('sensor.maya_s_learning_games_weekly_summary', 'parent_title') }}"
          message: "{{ state_attr('sensor.maya_s_learning_games_weekly_summary', 'parent_text') }}"
          data:
            url: /learning-games/0?lg=stats
```

**Notify parents when a journal entry is written** (tapping the notification
opens that entry in the card):

```yaml
automation:
  - alias: Learning journal - new entry
    mode: queued
    triggers:
      - trigger: event
        event_type: learning_games_journal_entry
        event_data:
          is_update: false
    actions:
      - action: notify.mobile_app_parent_phone
        data:
          title: "📔 {{ trigger.event.data.name }} wrote in their journal"
          message: >-
            {{ trigger.event.data.mood_emoji }} {{ trigger.event.data.subjects | join(', ') }}
            {{ trigger.event.data.snippet }}
          data:
            url: "/learning-games/0{{ trigger.event.data.url }}"
            clickAction: "/learning-games/0{{ trigger.event.data.url }}"
```

**Announce the daily goal on a speaker:**

```yaml
automation:
  - alias: "Learning goal — announce"
    trigger:
      - platform: event
        event_type: learning_games_daily_goal
    action:
      - service: tts.speak
        target: { entity_id: tts.home_assistant_cloud }
        data:
          media_player_entity_id: media_player.kitchen_speaker
          message: >
            Amazing work {{ trigger.event.data.name }}!
            That's a {{ trigger.event.data.streak }} day streak!
```

**Unlock TV time when the goal is met:**

```yaml
automation:
  - alias: "Learning goal — unlock TV"
    trigger:
      - platform: state
        entity_id: binary_sensor.maya_s_learning_games_daily_goal_met
        to: "on"
    action:
      - service: input_boolean.turn_on
        target: { entity_id: input_boolean.tv_unlocked }
```

**Flash the lights on a level-up:**

```yaml
automation:
  - alias: "Learning level up — light show"
    trigger:
      - platform: event
        event_type: learning_games_level_up
    action:
      - service: light.turn_on
        target: { entity_id: light.living_room }
        data: { flash: short, rgb_color: [108, 92, 231] }
```

## Development

```bash
pip install -r requirements_test.txt
pytest
```

The game engine (`custom_components/learning_games/engine/`) is pure Python with
no Home Assistant imports — question generators are deterministic under a seeded
RNG and fuzz-tested across every skill and difficulty band.

To try it in a throwaway Home Assistant:

```bash
mkdir -p ~/ha-test/config
cp -r custom_components ~/ha-test/config/
docker run -d --name ha-test -p 8123:8123 \
  -v ~/ha-test/config:/config ghcr.io/home-assistant/home-assistant:stable
# open http://localhost:8123, onboard, add the integration, add the card
```

## License

MIT
