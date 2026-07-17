"""Slack client factory and a safe post helper, shared by CLI commands and recipes.

Kept separate from markbot.py so recipes can import it without a circular
dependency. `slack_sdk` is imported lazily so --dry-run needs neither the
dependency nor a token.
"""

from __future__ import annotations

import re
import sys

import config
from credentials import SecretNotFound, resolve_secret

# A Slack channel/group/DM ID (e.g. C0ABC123). Names are lowercase + hyphens.
_CHANNEL_ID_RE = re.compile(r"^[CGD][A-Z0-9]{6,}$")


def get_slack_client():
    """Build a slack_sdk WebClient, resolving SLACK_BOT_TOKEN (env → the-lodge resolver)."""
    from slack_sdk import WebClient

    try:
        token = resolve_secret("SLACK_BOT_TOKEN")
    except SecretNotFound as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    return WebClient(token=token)


def post_blocks(
    client,
    *,
    channel: str,
    blocks: list[dict],
    text: str,
    thread_ts: str | None = None,
    reply_broadcast: bool = False,
):
    """Post Block Kit to Slack with friendly error handling.

    Resolves friendly channel names via config.resolve_channel, surfaces
    SlackApiError codes (not_in_channel, invalid_auth, …) to stderr, and exits
    non-zero on failure. Returns the API response on success.
    """
    from slack_sdk.errors import SlackApiError

    kwargs = {
        "channel": config.resolve_channel(channel),
        "blocks": blocks,
        "text": text,
    }
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    if reply_broadcast:
        kwargs["reply_broadcast"] = True

    try:
        return client.chat_postMessage(**kwargs)
    except SlackApiError as exc:
        error = exc.response.get("error", "unknown_error") if exc.response else "unknown_error"
        print(f"Error: Slack API call failed — {error}", file=sys.stderr)
        sys.exit(1)


# --- channel name → ID resolution (for AirTable-routed posts) ----------------
# AirTable stores channel *names*; chat.postMessage wants IDs. We page
# conversations.list once and cache the whole name→id map for the process.

_channel_cache: dict[str, str] = {}
_channel_cache_loaded = False


def _load_channels(client) -> None:
    global _channel_cache_loaded
    cursor = None
    while True:
        resp = client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=1000,
            cursor=cursor,
        )
        for channel in resp["channels"]:
            _channel_cache[channel["name"]] = channel["id"]
        cursor = (resp.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break
    _channel_cache_loaded = True


def channel_id_for_name(client, name: str) -> str:
    """Resolve a Slack channel *name* to its ID via a cached conversations.list."""
    name = name.lstrip("#")
    if not _channel_cache_loaded:
        _load_channels(client)
    try:
        return _channel_cache[name]
    except KeyError:
        raise RuntimeError(
            f"Slack channel '#{name}' not found via conversations.list — check the "
            f"name, that channels:read/groups:read are granted, and that the bot is "
            f"a member if the channel is private."
        )


def resolve_post_channel(client, value: str) -> str:
    """Turn a channel reference into a postable ID.

    A raw ID (or a config alias mapping to one) passes through; a channel name is
    resolved via Slack. Lets callers pass IDs, friendly aliases, or bare names.
    """
    value = config.resolve_channel(value)
    if _CHANNEL_ID_RE.match(value):
        return value
    return channel_id_for_name(client, value)
