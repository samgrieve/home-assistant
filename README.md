# Learning Games for Home Assistant

Fun, adaptive **maths and English games** for kids, built right into Home Assistant.
Designed for a tablet on the kitchen side: big touch buttons, confetti, XP, levels,
daily streaks and badges — with real HA sensors and events so you can wire her
progress up to real-world rewards (lights, announcements, TV time).

Aimed at UK Year 5 (ages 9–10) but every skill adapts across five difficulty
bands based on accuracy and speed, so it stays challenging as she grows.

## What's inside

**8 game modes** (each round is 10 quick questions):

| Maths | English |
|---|---|
| ⚡ Times Table Blitz — ×/÷ facts to 12 | ⭐ Spelling Star — correct spelling, missing letters, unscramble |
| 🔢 Number Crunch — add, subtract, place value, rounding | 🧙 Word Wizard — synonyms, antonyms, definitions |
| ✖️ Big Multiply — long multiplication, division with remainders | 🔍 Word Detective — word classes, punctuation |
| 🧪 Fraction Lab — fractions, decimals, negative numbers | 👯 Tricky Twins — homophones (their/there/they're…) |

**Progression & engagement**
- XP for every answer, speed bonuses, streak bonuses, levels
- Daily goal (configurable) and a daily streak with ❄️ streak-freeze tokens
- 16 badges to collect, per-skill mastery stars on every game tile
- Adaptive difficulty: each of the 15 tracked skills moves up/down 5 bands automatically

**For parents**
- Sensors: level, streak, questions today, accuracy, maths/English mastery (per-skill detail in attributes), last badge, weekly summary
- `binary_sensor.<name>_daily_goal_met` — the prime automation hook
- Events: `learning_games_daily_goal`, `learning_games_level_up`, `learning_games_badge_earned`, `learning_games_streak_milestone`, `learning_games_session_complete`
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

A panel-view dashboard works best on a tablet:
Dashboard → ⋮ → Edit → ⋮ → *Raw configuration editor*, or just place the card
in a single-column view.

## Reward automation recipes

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
