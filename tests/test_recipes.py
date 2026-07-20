"""Tests for the alert-recipe registry and the program-of-the-day recipe."""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import recipes
from recipes import program_of_the_day as potd


def test_registry_discovers_program_of_the_day():
    assert "program-of-the-day" in recipes.recipe_names()
    mod = recipes.get_recipe("program-of-the-day")
    assert mod is potd


def test_get_recipe_unknown_returns_none():
    assert recipes.get_recipe("does-not-exist") is None


def _args(**kw):
    defaults = {"weekday": None, "base": "", "table": "", "view": "", "dry_run": False}
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def test_dry_run_uses_sample_without_credentials():
    """dry-run renders the format from sample data — no base/table/network needed."""
    blocks = potd.build_blocks(_args(weekday="Monday", dry_run=True))
    text = blocks[0]["text"]["text"]
    assert "Recording Monday" in text
    assert "airtable.com" in text


def test_live_without_config_raises():
    """A real run with no AirTable config fails loudly (never posts fake data)."""
    import pytest

    with pytest.raises(RuntimeError):
        potd.build_blocks(_args(weekday="Monday", dry_run=False))


def test_build_blocks_formats_fetched_records(monkeypatch):
    monkeypatch.setattr(
        potd, "_fetch",
        lambda args: [
            {"name": "Show A", "url": "https://airtable.com/app/tbl/rec1"},
            {"name": "Show B", "url": "https://airtable.com/app/tbl/rec2"},
        ],
    )
    text = potd.build_blocks(_args(weekday="Friday"))[0]["text"]["text"]
    assert "Recording Friday" in text
    assert "<https://airtable.com/app/tbl/rec1|Show A>" in text
    assert "Show B" in text


def test_build_blocks_empty(monkeypatch):
    monkeypatch.setattr(potd, "_fetch", lambda args: [])
    text = potd.build_blocks(_args(weekday="Sunday"))[0]["text"]["text"]
    assert "No programs record on Sunday" in text


def test_fallback_text():
    assert potd.fallback_text(_args(weekday="Wednesday")) == "Programs recording Wednesday"
