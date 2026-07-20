"""Tests for Slack channel name→ID resolution (the AirTable-routing bridge)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import slack_client


class FakeConvClient:
    """Stand-in for a slack_sdk client's conversations_list pagination."""

    def __init__(self, pages):
        self.pages = pages  # list of (channels, next_cursor)
        self.calls = 0

    def conversations_list(self, **kwargs):
        channels, cursor = self.pages[self.calls]
        self.calls += 1
        return {"channels": channels, "response_metadata": {"next_cursor": cursor or ""}}


def _reset_cache():
    slack_client._channel_cache.clear()
    slack_client._channel_cache_loaded = False


def test_resolves_name_and_caches():
    _reset_cache()
    client = FakeConvClient([([
        {"name": "pbswi-proj-x", "id": "C1"},
        {"name": "comm-y", "id": "C2"},
    ], None)])
    assert slack_client.channel_id_for_name(client, "pbswi-proj-x") == "C1"
    assert slack_client.channel_id_for_name(client, "#comm-y") == "C2"  # strips leading '#'
    assert client.calls == 1  # second lookup served from cache, no extra API call


def test_paginates_until_found():
    _reset_cache()
    client = FakeConvClient([
        ([{"name": "a", "id": "C1"}], "cursor2"),
        ([{"name": "b", "id": "C2"}], None),
    ])
    assert slack_client.channel_id_for_name(client, "b") == "C2"
    assert client.calls == 2


def test_unknown_channel_raises():
    _reset_cache()
    client = FakeConvClient([([{"name": "a", "id": "C1"}], None)])
    with pytest.raises(RuntimeError):
        slack_client.channel_id_for_name(client, "missing")


def test_resolve_post_channel_passes_ids_through():
    _reset_cache()
    # A raw channel ID needs no Slack lookup (client unused → None is fine).
    assert slack_client.resolve_post_channel(None, "C09QUBVE0DR") == "C09QUBVE0DR"


def test_resolve_post_channel_uses_config_alias(monkeypatch):
    _reset_cache()
    monkeypatch.setattr(config, "CHANNELS", {"alerts": "C0ALIAS"})
    assert slack_client.resolve_post_channel(None, "alerts") == "C0ALIAS"


def test_resolve_post_channel_resolves_a_name():
    _reset_cache()
    client = FakeConvClient([([{"name": "pbswi-proj-x", "id": "C1"}], None)])
    assert slack_client.resolve_post_channel(client, "pbswi-proj-x") == "C1"
