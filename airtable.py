"""Read-only AirTable client + record → project → Slack-channel routing.

AirTable is the source of truth for which Slack channel a project posts to:
🔊Slack Channels.`Channel Name`, linked from 📈Projects.`Slack Channel`, and
surfaced on content tables (SST, Events, …) as the lookup `Slack Channel
(from Project)`. This module resolves a record to its channel *name(s)*;
`slack_client.channel_id_for_name` turns a name into the ID chat.postMessage
needs.

Read-only — this module never writes (AirTable SST is write-approval-gated).
Defaults target the WPM "Project Management" base but every id/field is
environment-overridable.
"""

from __future__ import annotations

import os

from credentials import resolve_secret

# WPM has a single "Project Management" base, so defaulting to it is intentional
# (not a silent guess) — this tool is WPM-only. Override with AIRTABLE_BASE_ID.
BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "appZ2HGwhiifQToB6")
SLACK_CHANNELS_TABLE = os.environ.get("AIRTABLE_SLACK_CHANNELS_TABLE", "tbluUMsElANyKl3Nc")

# Lookup field carrying channel names directly (SST, Events, and any table with
# a linked Project). Preferred when present.
CHANNEL_LOOKUP_FIELD = os.environ.get(
    "AIRTABLE_CHANNEL_LOOKUP_FIELD", "Slack Channel (from Project)"
)
# Link field on 📈Projects pointing at 🔊Slack Channels records.
CHANNEL_LINK_FIELD = os.environ.get("AIRTABLE_CHANNEL_LINK_FIELD", "Slack Channel")
# Name field on 🔊Slack Channels.
CHANNEL_NAME_FIELD = os.environ.get("AIRTABLE_CHANNEL_NAME_FIELD", "Channel Name")

_API = "https://api.airtable.com/v0"


def _get_record(table: str, record_id: str) -> dict:
    """Fetch one record. Injected into resolvers so tests can avoid the network."""
    import requests

    api_key = resolve_secret("AIRTABLE_PAT")
    resp = requests.get(
        f"{_API}/{BASE_ID}/{table}/{record_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def record_url(table: str, record_id: str) -> str:
    return f"https://airtable.com/{BASE_ID}/{table}/{record_id}"


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def channel_names_for_record(table: str, record_id: str, *, get=_get_record) -> list[str]:
    """Return the Slack channel name(s) a record routes to.

    Two shapes are handled:
      * a lookup field (`Slack Channel (from Project)`) already holding names —
        present on SST, Events, and other project-linked tables; and
      * a link field (`Slack Channel`) to 🔊Slack Channels records (on Projects),
        which are dereferenced to their `Channel Name`.
    """
    fields = get(table, record_id).get("fields", {})

    names = [n for n in _as_list(fields.get(CHANNEL_LOOKUP_FIELD)) if n]
    if names:
        return names

    resolved = []
    for rid in _as_list(fields.get(CHANNEL_LINK_FIELD)):
        name = get(SLACK_CHANNELS_TABLE, rid).get("fields", {}).get(CHANNEL_NAME_FIELD)
        if name:
            resolved.append(name)
    return resolved


def pick_channel(names: list[str]) -> str | None:
    """Choose one channel when a project links several — prefer a `-proj-` channel."""
    if not names:
        return None
    for name in names:
        if "-proj-" in name:
            return name
    return names[0]
