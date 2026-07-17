"""Tests for the env-first / get-secret.sh secret resolver."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import credentials


def test_env_takes_priority():
    calls = []
    resolved = credentials.resolve_secret(
        "AIRTABLE_PAT",
        env={"AIRTABLE_PAT": "from-env"},
        runner=lambda name: calls.append(name) or "from-resolver",
    )
    assert resolved == "from-env"
    assert calls == []  # the workspace resolver is never invoked when env has it


def test_delegates_to_resolver_when_env_missing():
    seen = {}

    def runner(name):
        seen["name"] = name
        return "resolved-secret"

    assert credentials.resolve_secret("AIRTABLE_PAT", env={}, runner=runner) == "resolved-secret"
    assert seen["name"] == "AIRTABLE_PAT"  # passes the canonical key through verbatim


def test_missing_everywhere_raises():
    with pytest.raises(credentials.SecretNotFound):
        credentials.resolve_secret("NOPE", env={}, runner=lambda name: None)


def test_missing_message_is_actionable():
    with pytest.raises(credentials.SecretNotFound) as exc:
        credentials.resolve_secret("SLACK_BOT_TOKEN", env={}, runner=lambda name: None)
    msg = str(exc.value)
    assert "SLACK_BOT_TOKEN" in msg
    assert "get-secret.sh" in msg
