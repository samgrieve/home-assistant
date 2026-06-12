"""Constants for the Learning Games integration."""

DOMAIN = "learning_games"
VERSION = "1.1.0"

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1

CONF_NAME = "name"
CONF_AVATAR = "avatar"
CONF_DAILY_GOAL = "daily_goal"

DEFAULT_DAILY_GOAL = 20

AVATARS = ["fox", "owl", "cat", "dragon", "unicorn", "robot", "panda", "rocket"]

FRONTEND_URL_BASE = "/learning_games_files"
CARD_FILENAME = "learning-games-card.js"

# Events fired on the HA bus for parent automations.
EVENT_DAILY_GOAL = "learning_games_daily_goal"
EVENT_LEVEL_UP = "learning_games_level_up"
EVENT_BADGE_EARNED = "learning_games_badge_earned"
EVENT_STREAK_MILESTONE = "learning_games_streak_milestone"
EVENT_SESSION_COMPLETE = "learning_games_session_complete"
EVENT_CHALLENGE_COMPLETE = "learning_games_challenge_complete"

STREAK_MILESTONES = (3, 7, 14, 30, 50, 100)

SIGNAL_PROFILE_UPDATED = f"{DOMAIN}_profile_updated"
