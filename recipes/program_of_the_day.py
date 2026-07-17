"""Recipe: program-of-the-day.

Posts a link to the AirTable record for each program that records on a given
weekday. Deterministic (query → format → post), so it runs well as a scheduled
GitHub Actions job with no dependence on a local machine.

Configure via environment (or pass the flags):
    AIRTABLE_BASE_ID          base id (appXXXXXXXXXXXXXX)               — required for live runs
    AIRTABLE_TABLE            table id or name (e.g. "Content Calendar") — required for live runs
    AIRTABLE_VIEW             optional view name to scope the query
    AIRTABLE_RECORD_DAY_FIELD field holding the record weekday          (default "Record Day")
    AIRTABLE_NAME_FIELD       field holding the program name            (default "Name")
Secret (env → the-lodge get-secret.sh → 1Password):
    AIRTABLE_PAT              AirTable personal access token (registry: secret/airtable-api-key)

The record-day/name field names default to reasonable guesses — confirm them
against the actual Content Calendar schema before the first live run.
"""

from __future__ import annotations

import datetime
import os

from credentials import resolve_secret

NAME = "program-of-the-day"
HELP = "Post AirTable record links for programs recording on a given weekday"
DEFAULT_CHANNEL = None

_BASE = os.environ.get("AIRTABLE_BASE_ID", "")
_TABLE = os.environ.get("AIRTABLE_TABLE", "")
_VIEW = os.environ.get("AIRTABLE_VIEW", "")
_DAY_FIELD = os.environ.get("AIRTABLE_RECORD_DAY_FIELD", "Record Day")
_NAME_FIELD = os.environ.get("AIRTABLE_NAME_FIELD", "Name")

# Shown by --dry-run when AirTable isn't configured, so the message format is
# reviewable without credentials or network access.
_SAMPLE = [
    {"name": "Sample Program", "url": "https://airtable.com/appXXXX/tblXXXX/recSAMPLE"},
]


def add_arguments(parser):
    parser.add_argument("--weekday", help="Weekday to match (default: today, e.g. 'Monday')")
    parser.add_argument("--base", default=_BASE, help="AirTable base ID")
    parser.add_argument("--table", default=_TABLE, help="AirTable table id or name")
    parser.add_argument("--view", default=_VIEW, help="AirTable view name")


def _target_weekday(args) -> str:
    return args.weekday or datetime.date.today().strftime("%A")


def _record_url(base: str, table: str, record_id: str) -> str:
    return f"https://airtable.com/{base}/{table}/{record_id}"


def _fetch(args) -> list[dict]:
    """Return [{name, url}] for programs recording on the target weekday."""
    base, table = args.base, args.table
    if not base or not table:
        if getattr(args, "dry_run", False):
            return _SAMPLE
        raise RuntimeError(
            "AirTable base/table not configured — set AIRTABLE_BASE_ID and "
            "AIRTABLE_TABLE (or pass --base/--table)."
        )

    import requests

    api_key = resolve_secret("AIRTABLE_PAT")
    weekday = _target_weekday(args)
    params = {"filterByFormula": f"{{{_DAY_FIELD}}} = '{weekday}'"}
    if args.view:
        params["view"] = args.view

    resp = requests.get(
        f"https://api.airtable.com/v0/{base}/{table}",
        headers={"Authorization": f"Bearer {api_key}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return [
        {
            "name": rec.get("fields", {}).get(_NAME_FIELD, "(untitled)"),
            "url": _record_url(base, table, rec["id"]),
        }
        for rec in resp.json().get("records", [])
    ]


def build_blocks(args) -> list[dict]:
    weekday = _target_weekday(args)
    programs = _fetch(args)
    if not programs:
        return [{
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":calendar: No programs record on {weekday}."},
        }]
    lines = "\n".join(f":clapper: <{p['url']}|{p['name']}>" for p in programs)
    return [{
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Recording {weekday}*\n{lines}"},
    }]


def fallback_text(args) -> str:
    return f"Programs recording {_target_weekday(args)}"
