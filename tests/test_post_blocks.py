"""Tests for the shared post_blocks helper (channel resolution + error handling)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import slack_client


class FakeClient:
    def __init__(self, response=None, raise_error=None):
        self.response = response if response is not None else {"ts": "1.1"}
        self.raise_error = raise_error
        self.calls = []

    def chat_postMessage(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_error:
            raise self.raise_error
        return self.response


def test_success_returns_response_and_resolves_channel(monkeypatch):
    monkeypatch.setattr(config, "CHANNELS", {"alerts": "C0REAL"})
    client = FakeClient({"ts": "9.9"})
    resp = slack_client.post_blocks(client, channel="alerts", blocks=[{"x": 1}], text="t")
    assert resp["ts"] == "9.9"
    assert client.calls[0]["channel"] == "C0REAL"


def test_passes_thread_and_broadcast():
    client = FakeClient()
    slack_client.post_blocks(
        client, channel="C0X", blocks=[], text="t",
        thread_ts="123.456", reply_broadcast=True,
    )
    call = client.calls[0]
    assert call["thread_ts"] == "123.456"
    assert call["reply_broadcast"] is True


def test_omits_thread_when_absent():
    client = FakeClient()
    slack_client.post_blocks(client, channel="C0X", blocks=[], text="t")
    call = client.calls[0]
    assert "thread_ts" not in call
    assert "reply_broadcast" not in call


def test_slack_error_exits_nonzero_with_message(capsys):
    from slack_sdk.errors import SlackApiError

    err = SlackApiError("boom", {"ok": False, "error": "not_in_channel"})
    client = FakeClient(raise_error=err)
    with pytest.raises(SystemExit) as exc:
        slack_client.post_blocks(client, channel="C0X", blocks=[], text="t")
    assert exc.value.code == 1
    assert "not_in_channel" in capsys.readouterr().err
