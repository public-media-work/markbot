"""markbot configuration — bot identity, channels, and message defaults.

Values are environment-overridable so the same code posts to different
channels/sites without edits (which is what lets a cloud scheduler run it).
No client or project names live here.
"""

import os

# App/bot display name (kept in sync with manifest.json — Slack rejects "!" in
# the manifest name field, so no exclamation here).
APP_NAME = "Your Helpful MarkBot"

# Fallback text on generic `post` messages (shown in notifications / a11y).
DEFAULT_POST_TEXT = os.environ.get("MARKBOT_DEFAULT_TEXT", "Notification from MarkBot")

# Optional site URL referenced by the podcast-import notifications. Empty by
# default; set PODCAST_SITE_URL to include "imported into <site>" in the copy.
PODCAST_SITE_URL = os.environ.get("PODCAST_SITE_URL", "")

# Friendly channel names → Slack channel IDs. Fill in as WPM channels are set
# up (use IDs, not names). Callers may pass either a friendly name (resolved
# here) or a raw channel ID (passed through unchanged).
CHANNELS: dict[str, str] = {
    # "program-alerts": "C0XXXXXXXXX",
}


def resolve_channel(value: str) -> str:
    """Map a friendly channel name to its ID, or pass a raw ID through unchanged."""
    return CHANNELS.get(value, value)
