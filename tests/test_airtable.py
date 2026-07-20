"""Tests for AirTable record → project → channel-name traversal."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import airtable


def test_channel_names_from_lookup_field():
    """Content/SST records expose channel names directly via the lookup field."""
    def fake_get(table, rid):
        return {"fields": {"Slack Channel (from Project)": ["pbswi-proj-x", "pbswi-comm-y"]}}

    names = airtable.channel_names_for_record("tblSST", "rec1", get=fake_get)
    assert names == ["pbswi-proj-x", "pbswi-comm-y"]


def test_channel_names_from_link_field_dereferences_name():
    """Project records link to 🔊Slack Channels rows, dereferenced to Channel Name."""
    def fake_get(table, rid):
        if table == airtable.SLACK_CHANNELS_TABLE:
            return {"fields": {"Channel Name": "pbswi-proj-countyfairs"}}
        return {"fields": {"Slack Channel": ["recChan1"]}}

    names = airtable.channel_names_for_record("tblProjects", "recProj", get=fake_get)
    assert names == ["pbswi-proj-countyfairs"]


def test_lookup_field_wins_over_link_field():
    def fake_get(table, rid):
        return {"fields": {
            "Slack Channel (from Project)": ["pbswi-proj-x"],
            "Slack Channel": ["recShouldBeIgnored"],
        }}

    assert airtable.channel_names_for_record("t", "r", get=fake_get) == ["pbswi-proj-x"]


def test_channel_names_empty_when_no_fields():
    assert airtable.channel_names_for_record("t", "r", get=lambda t, r: {"fields": {}}) == []


def test_pick_channel_prefers_proj():
    assert airtable.pick_channel(["pbswi-comm-a", "pbswi-proj-b"]) == "pbswi-proj-b"


def test_pick_channel_falls_back_to_first():
    assert airtable.pick_channel(["pbswi-comm-a", "pbswi-unit-b"]) == "pbswi-comm-a"


def test_pick_channel_empty():
    assert airtable.pick_channel([]) is None


def test_record_url():
    assert airtable.record_url("tblX", "recY") == f"https://airtable.com/{airtable.BASE_ID}/tblX/recY"
