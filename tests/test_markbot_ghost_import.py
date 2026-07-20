"""Tests for ghost-import Block Kit message builders."""

import sys
from pathlib import Path

# Add markbot to path so we can import it
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import markbot


def test_build_import_start_blocks():
    """Start blocks include show name and episode title."""
    blocks = markbot.build_import_start_blocks(
        show="Community Program",
        episode="A Conversation on the Living Earth",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "Community Program" in text
    assert "Living Earth" in text


def test_build_import_start_blocks_site_url_optional(monkeypatch):
    """Site URL appears only when configured (no client name hardcoded)."""
    monkeypatch.setattr(config, "PODCAST_SITE_URL", "")
    text = markbot.build_import_start_blocks("Show", "Ep")[0]["text"]["text"]
    assert "imported." in text  # no "into <site>"

    monkeypatch.setattr(config, "PODCAST_SITE_URL", "example.org")
    text = markbot.build_import_start_blocks("Show", "Ep")[0]["text"]["text"]
    assert "imported into example.org." in text


def test_build_import_draft_blocks():
    """Draft blocks include episode title and Ghost admin link."""
    blocks = markbot.build_import_draft_blocks(
        show="Community Program",
        episode="A Conversation on the Living Earth",
        ghost_url="https://example.ghost.io/ghost/#/editor/post/abc123",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "draft" in text.lower() or "review" in text.lower()
    assert "ghost.io" in text


def test_build_import_scheduled_blocks():
    """Scheduled blocks include episode title and public URL."""
    blocks = markbot.build_import_scheduled_blocks(
        show="Community Program",
        episode="A Conversation on the Living Earth",
        ghost_url="https://example.org/a-conversation/",
        schedule_time="Saturday, April 12 at 6:00 AM CDT",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "scheduled" in text.lower()
    assert "Saturday" in text


def test_build_import_failed_blocks():
    """Failed blocks include episode title and error message."""
    blocks = markbot.build_import_failed_blocks(
        show="Community Program",
        episode="A Conversation on the Living Earth",
        error="Validation error: feature_image_alt exceeds 191 characters",
    )
    assert len(blocks) >= 1
    text = blocks[0]["text"]["text"]
    assert "failed" in text.lower() or "error" in text.lower()
    assert "191 characters" in text


def test_build_import_failed_blocks_truncates_long_error():
    """Long error messages are truncated to keep Slack blocks readable."""
    long_error = "x" * 500
    blocks = markbot.build_import_failed_blocks(
        show="Community Program",
        episode="Test Episode",
        error=long_error,
    )
    text = blocks[0]["text"]["text"]
    assert len(text) < 3000
