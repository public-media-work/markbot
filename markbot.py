#!/usr/bin/env python3
"""Your Helpful MarkBot! — a Slack alert hub for WPM workflows.

A single-identity CLI that posts Block Kit notifications to Slack (Bot Token
auth). Two families of commands:

  * Named alert recipes — `run-alert <name>` — pull data from other systems
    (AirTable, …) and post a message. Designed to be fired by a cloud scheduler
    (GitHub Actions cron / Claude scheduled routine), so nothing depends on a
    local machine. Add a recipe by dropping a module in recipes/.
  * Direct notification commands — transcribe-*, schedule-alert, ghost-import,
    post — for callers that build their own message.

Usage:
    # Run a scheduled alert recipe
    markbot.py run-alert program-of-the-day --channel C0XXXX
    markbot.py --dry-run run-alert program-of-the-day --channel C0XXXX

    # Generic posting (JSON string, or "-" to read stdin)
    markbot.py post --blocks-json '{"blocks":[...]}' --channel C0XXXX

    # --dry-run prints Block Kit JSON without posting; it works either before
    # the subcommand or after it.
    markbot.py --dry-run transcribe-start --episode "Test" --channel C0XXXX
"""

import argparse
import json
import re
import sys
from pathlib import Path

import config
from recipes import get_recipe, recipe_names
from slack_client import get_slack_client, post_blocks, resolve_post_channel


# ---------------------------------------------------------------------------
# Helpers — transcription
# ---------------------------------------------------------------------------

def extract_short_name(episode: str) -> str:
    """Extract short display name from episode string.

    '005 - Renee Bergland' -> 'Renee Bergland'
    'Some Episode'         -> 'Some Episode'
    """
    match = re.match(r"^\d+\s*[-–—]\s*(.+)$", episode)
    return match.group(1).strip() if match else episode


def extract_episode_number(episode: str) -> str:
    """Extract episode number prefix.

    '005 - Renee Bergland' -> '005'
    """
    match = re.match(r"^(\d+)\s*[-–—]", episode)
    return match.group(1) if match else ""


def extract_last_name(episode: str) -> str:
    """Extract guest last name from episode string.

    '005 - Renee Bergland' -> 'Bergland'
    """
    guest = extract_short_name(episode)
    parts = guest.split()
    return parts[-1] if parts else guest


def parse_chapters(chapters_path: str) -> list[str]:
    """Extract chapter lines from chapters.md.

    Looks for lines matching HH:MM:SS — Title pattern.
    """
    text = Path(chapters_path).read_text()
    chapters = []
    for line in text.splitlines():
        match = re.match(r"^\s*(\d{1,2}:\d{2}:\d{2})\s*[-–—]\s*(.+)$", line)
        if match:
            chapters.append(f"{match.group(1)} — {match.group(2).strip()}")
    return chapters


def extract_transcript_preview(transcript_path: str, max_chars: int = 200) -> str:
    """Extract first meaningful speaker line from formatted transcript.

    Skips YAML frontmatter and headers, finds the first '**Speaker:**' line.
    """
    text = Path(transcript_path).read_text()
    in_frontmatter = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped or stripped.startswith("#"):
            continue
        preview = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        if len(preview) > max_chars:
            preview = preview[:max_chars].rsplit(" ", 1)[0] + "…"
        return preview
    return ""


# ---------------------------------------------------------------------------
# Message builders — transcription
# ---------------------------------------------------------------------------

def build_start_blocks(episode: str) -> list[dict]:
    """Build Block Kit blocks for the transcription start message."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":studio_microphone: *Transcription started* — {episode}\n\n"
                    "Working on a transcript for editing. I'll post a link here "
                    "when it's ready (usually about 20 minutes)."
                ),
            },
        }
    ]


def build_ready_blocks(
    episode: str,
    doc_url: str,
    chapters: list[str] | None = None,
    preview: str | None = None,
    speaker_note: str | None = None,
) -> list[dict]:
    """Build Block Kit blocks for the transcript ready message."""
    ep_num = extract_episode_number(episode)
    last_name = extract_last_name(episode)
    short_name = extract_short_name(episode)
    doc_label = f"{ep_num} {last_name} — Edit Transcript" if ep_num else short_name

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: *Transcript ready to edit* — {short_name}\n\n"
                    f":page_facing_up: *<{doc_url}|{doc_label}>*\n"
                    "Open in Google Docs to start reviewing."
                ),
            },
        },
        {"type": "divider"},
    ]

    if chapters:
        chapter_text = "\n".join(chapters)
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Chapters:*\n{chapter_text}",
                },
            }
        )

    if preview:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Preview:*\n>{preview}",
                },
            }
        )

    if chapters or preview:
        blocks.append({"type": "divider"})

    if speaker_note:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":warning: {speaker_note}",
                    }
                ],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        "When editing, stick to speaker names and spelling corrections.\n"
                        "Structural changes can't sync back to the timed caption files.\n\n"
                        "Caption and chapter files were also generated for podcast platforms."
                    ),
                }
            ],
        }
    )

    return blocks


# ---------------------------------------------------------------------------
# Message builders — schedule alerts
# ---------------------------------------------------------------------------

def build_missing_blocks(
    show: str, slot_label: str, release_info: str,
) -> list[dict]:
    """Block Kit blocks for a missing-content alert."""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":rotating_light: ACTION NEEDED — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"No content found for the upcoming release.\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


def build_drafted_blocks(
    show: str, slot_label: str, release_info: str, title: str | None = None,
) -> list[dict]:
    """Block Kit blocks for a draft-needs-scheduling alert."""
    title_line = f'\n:page_facing_up: Draft: *"{title}"*' if title else ""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":warning: Draft Needs Scheduling — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"A draft exists but hasn't been scheduled yet.{title_line}\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


def build_scheduled_blocks(
    show: str,
    slot_label: str,
    release_info: str,
    title: str | None = None,
    url: str | None = None,
) -> list[dict]:
    """Block Kit blocks for an on-track scheduled alert."""
    title_line = f'\n:white_check_mark: *"{title}"*' if title else ""
    url_line = f"\n:link: <{url}|View post>" if url else ""
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":white_check_mark: On Track — {slot_label}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{show}* — *{slot_label}*\n"
                    f"Content is scheduled and ready to go.{title_line}{url_line}\n\n"
                    f":calendar: {release_info}"
                ),
            },
        },
        {"type": "divider"},
    ]


# ---------------------------------------------------------------------------
# Message builders — ghost import
# ---------------------------------------------------------------------------

def build_import_start_blocks(show: str, episode: str) -> list[dict]:
    """Block Kit blocks for import-started notification."""
    destination = f" into {config.PODCAST_SITE_URL}" if config.PODCAST_SITE_URL else ""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":incoming_envelope: *New episode importing* — {show}\n\n"
                    f"*{episode}*\n"
                    f"A new episode has been scheduled on PRX and is being "
                    f"imported{destination}."
                ),
            },
        },
    ]


def build_import_draft_blocks(show: str, episode: str, ghost_url: str) -> list[dict]:
    """Block Kit blocks for draft-ready notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":pencil2: *Draft ready for review* — {show}\n\n"
                    f"*{episode}*\n"
                    f"The episode has been imported as a draft. "
                    f"Review it before publishing.\n\n"
                    f":link: <{ghost_url}|Open in Ghost>"
                ),
            },
        },
    ]


def build_import_scheduled_blocks(
    show: str, episode: str, ghost_url: str, schedule_time: str
) -> list[dict]:
    """Block Kit blocks for post-scheduled notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":calendar: *Episode scheduled* — {show}\n\n"
                    f"*{episode}*\n"
                    f"Scheduled for release: {schedule_time}\n\n"
                    f":link: <{ghost_url}|Preview post>"
                ),
            },
        },
    ]


def build_import_failed_blocks(show: str, episode: str, error: str) -> list[dict]:
    """Block Kit blocks for import-failed notification."""
    if len(error) > 300:
        error = error[:297] + "..."
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":x: *Import failed* — {show}\n\n"
                    f"*{episode}*\n"
                    f"```{error}```\n"
                    f"Check the CLI output for full details."
                ),
            },
        },
    ]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_transcribe_start(args):
    """Send the 'job started' message. Prints thread_ts to stdout."""
    blocks = build_start_blocks(args.episode)

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    resp = post_blocks(
        client,
        channel=args.channel,
        blocks=blocks,
        text=f"Transcription started — {args.episode}",
    )
    print(resp["ts"])


def cmd_transcribe_ready(args):
    """Send the 'transcript ready' message as a threaded reply."""
    chapters = None
    if args.chapters_file and Path(args.chapters_file).exists():
        chapters = parse_chapters(args.chapters_file)

    preview = None
    if args.transcript_file and Path(args.transcript_file).exists():
        preview = extract_transcript_preview(args.transcript_file)

    speaker_note = args.speaker_note if args.speaker_note else None

    blocks = build_ready_blocks(
        episode=args.episode,
        doc_url=args.doc_url,
        chapters=chapters,
        preview=preview,
        speaker_note=speaker_note,
    )

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    short_name = extract_short_name(args.episode)
    post_blocks(
        client,
        channel=args.channel,
        blocks=blocks,
        text=f"Transcript ready to edit — {short_name}",
        thread_ts=args.thread_ts,
        reply_broadcast=True,
    )


def cmd_schedule_alert(args):
    """Send a release readiness alert."""
    builders = {
        "missing": build_missing_blocks,
        "drafted": build_drafted_blocks,
        "scheduled": build_scheduled_blocks,
    }

    builder = builders[args.state]

    if args.state == "missing":
        blocks = builder(args.show, args.slot, args.release_time)
    elif args.state == "drafted":
        blocks = builder(args.show, args.slot, args.release_time, title=args.title)
    elif args.state == "scheduled":
        blocks = builder(
            args.show, args.slot, args.release_time,
            title=args.title, url=args.url,
        )

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    state_labels = {
        "missing": "ACTION NEEDED",
        "drafted": "Draft Needs Scheduling",
        "scheduled": "On Track",
    }
    post_blocks(
        client,
        channel=args.channel,
        blocks=blocks,
        text=f"{state_labels[args.state]} — {args.show} — {args.slot}",
    )


def _parse_blocks(raw: str) -> list[dict]:
    """Parse a blocks payload: JSON string (or '-' for stdin); {"blocks":[...]} or bare [...]."""
    if raw == "-":
        raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "blocks" in payload:
        return payload["blocks"]
    print('Error: JSON must be a list or {"blocks": [...]}', file=sys.stderr)
    sys.exit(1)


def cmd_post(args):
    """Post raw Block Kit JSON to a channel."""
    blocks = _parse_blocks(args.blocks_json)

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    post_blocks(
        client,
        channel=args.channel,
        blocks=blocks,
        text=config.DEFAULT_POST_TEXT,
        thread_ts=args.thread_ts,
        reply_broadcast=args.reply_broadcast,
    )


def cmd_ghost_import(args):
    """Send a ghost import lifecycle notification."""
    builders = {
        "start": lambda: build_import_start_blocks(args.show, args.episode),
        "draft": lambda: build_import_draft_blocks(
            args.show, args.episode, args.ghost_url,
        ),
        "scheduled": lambda: build_import_scheduled_blocks(
            args.show, args.episode, args.ghost_url, args.schedule_time,
        ),
        "failed": lambda: build_import_failed_blocks(
            args.show, args.episode, args.error,
        ),
    }

    blocks = builders[args.state]()

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    client = get_slack_client()
    state_labels = {
        "start": f"Importing {args.episode}",
        "draft": f"Draft ready — {args.episode}",
        "scheduled": f"Scheduled — {args.episode}",
        "failed": f"Import failed — {args.episode}",
    }
    resp = post_blocks(
        client,
        channel=args.channel,
        blocks=blocks,
        text=state_labels[args.state],
        thread_ts=args.thread_ts,
        reply_broadcast=args.reply_broadcast,
    )
    # Print resp["ts"] for every state so callers can capture for later threading.
    print(resp["ts"])


def cmd_notify_record(args):
    """Post to the Slack channel a record routes to (record → project → channel).

    The channel is looked up from AirTable (unless --channel overrides it), then
    the channel name is resolved to an ID and the message is posted.
    """
    import airtable

    url = airtable.record_url(args.table, args.record)
    if args.blocks_json:
        blocks = _parse_blocks(args.blocks_json)
    else:
        headline = args.text or "New update"
        blocks = [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{headline}\n:card_index: <{url}|Open record in AirTable>",
            },
        }]

    # Resolve the routing channel name from AirTable unless overridden.
    channel_name = None
    if not args.channel:
        try:
            channel_name = airtable.pick_channel(
                airtable.channel_names_for_record(args.table, args.record)
            )
        except Exception as exc:  # network/credential/field issues
            if not args.dry_run:
                print(f"Error: could not resolve channel from AirTable — {exc}", file=sys.stderr)
                sys.exit(1)
            print(f"(dry-run) AirTable channel lookup skipped: {exc}", file=sys.stderr)

    if args.dry_run:
        routed = args.channel or (f"#{channel_name}" if channel_name else "(unresolved)")
        print(f"(dry-run) would post to {routed}", file=sys.stderr)
        print(json.dumps(blocks, indent=2))
        return

    target = args.channel or channel_name
    if not target:
        print(
            "Error: no channel resolved from the record and no --channel override",
            file=sys.stderr,
        )
        sys.exit(1)

    from slack_sdk.errors import SlackApiError

    client = get_slack_client()
    try:
        channel_id = resolve_post_channel(client, target)
    except (RuntimeError, SlackApiError) as exc:
        detail = exc.response.get("error", exc) if isinstance(exc, SlackApiError) else exc
        print(f"Error: could not resolve Slack channel — {detail}", file=sys.stderr)
        sys.exit(1)

    resp = post_blocks(client, channel=channel_id, blocks=blocks, text=args.text or config.DEFAULT_POST_TEXT)
    print(resp["ts"])


def cmd_run_alert(args):
    """Run a named alert recipe: build its blocks (fetching data) and post them."""
    recipe = get_recipe(args.recipe)
    if recipe is None:
        print(f"Error: unknown recipe {args.recipe!r}", file=sys.stderr)
        sys.exit(1)

    blocks = recipe.build_blocks(args)

    if args.dry_run:
        print(json.dumps(blocks, indent=2))
        return

    channel = args.channel or getattr(recipe, "DEFAULT_CHANNEL", None)
    if not channel:
        print(
            f"Error: no --channel provided and recipe {args.recipe!r} has no default",
            file=sys.stderr,
        )
        sys.exit(1)

    text = recipe.fallback_text(args) if hasattr(recipe, "fallback_text") else f"Alert: {args.recipe}"
    client = get_slack_client()
    resp = post_blocks(client, channel=channel, blocks=blocks, text=text)
    print(resp["ts"])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="markbot.py",
        description="Your Helpful MarkBot! — a Slack alert hub for WPM workflows",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print Block Kit JSON without posting to Slack",
    )

    # Lets --dry-run be given *after* the subcommand too. SUPPRESS means an
    # omitted sub-level flag doesn't clobber the top-level value.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--dry-run", action="store_true", default=argparse.SUPPRESS,
        help="Print Block Kit JSON without posting to Slack",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- transcribe-start ---
    p_ts = sub.add_parser(
        "transcribe-start", parents=[common], help="Post transcription-started message"
    )
    p_ts.add_argument("--episode", required=True, help='e.g. "005 - Renee Bergland"')
    p_ts.add_argument("--channel", required=True, help="Slack channel ID")

    # --- transcribe-ready ---
    p_tr = sub.add_parser(
        "transcribe-ready", parents=[common], help="Post transcript-ready message"
    )
    p_tr.add_argument("--episode", required=True, help='e.g. "005 - Renee Bergland"')
    p_tr.add_argument("--doc-url", required=True, help="Google Docs URL for transcript")
    p_tr.add_argument("--chapters-file", help="Path to chapters.md")
    p_tr.add_argument("--transcript-file", help="Path to formatted_transcript.md")
    p_tr.add_argument("--speaker-note", help="Optional QC note about speaker attribution")
    p_tr.add_argument("--channel", required=True, help="Slack channel ID")
    p_tr.add_argument("--thread-ts", required=True, help="Thread timestamp from start message")

    # --- schedule-alert ---
    p_sa = sub.add_parser(
        "schedule-alert", parents=[common], help="Post release readiness alert"
    )
    p_sa.add_argument(
        "--state", required=True, choices=["missing", "drafted", "scheduled"],
        help="Readiness state",
    )
    p_sa.add_argument("--show", required=True, help='Program/show name, e.g. "Weekly Program"')
    p_sa.add_argument("--slot", required=True, help='e.g. "Podcast Episode"')
    p_sa.add_argument("--release-time", required=True, help='e.g. "Saturday, March 7 at 6:00 AM CST (12h from now)"')
    p_sa.add_argument("--title", help="Ghost post title (for drafted/scheduled)")
    p_sa.add_argument("--url", help="Ghost post URL (for scheduled)")
    p_sa.add_argument("--channel", required=True, help="Slack channel ID")

    # --- post ---
    p_post = sub.add_parser("post", parents=[common], help="Post raw Block Kit JSON")
    p_post.add_argument(
        "--blocks-json", required=True,
        help='JSON string or "-" to read from stdin',
    )
    p_post.add_argument("--channel", required=True, help="Slack channel ID")
    p_post.add_argument("--thread-ts", help="Thread timestamp for reply")
    p_post.add_argument("--reply-broadcast", action="store_true", help="Broadcast threaded reply to channel")

    # --- ghost-import ---
    p_gi = sub.add_parser(
        "ghost-import", parents=[common], help="Ghost import lifecycle notification"
    )
    p_gi.add_argument(
        "--state", required=True,
        choices=["start", "draft", "scheduled", "failed"],
        help="Import lifecycle state",
    )
    p_gi.add_argument("--show", required=True, help='Program/show name, e.g. "Weekly Program"')
    p_gi.add_argument("--episode", required=True, help="Episode title")
    p_gi.add_argument("--ghost-url", help="Ghost editor or public URL (for draft/scheduled)")
    p_gi.add_argument("--schedule-time", help="Scheduled release time (for scheduled)")
    p_gi.add_argument("--error", help="Error message (for failed)")
    p_gi.add_argument("--channel", required=True, help="Slack channel ID")
    p_gi.add_argument("--thread-ts", help="Thread timestamp for threading replies")
    p_gi.add_argument(
        "--reply-broadcast", action="store_true",
        help="When threading, also broadcast the reply to the main channel feed",
    )

    # --- notify-record ---
    p_nr = sub.add_parser(
        "notify-record", parents=[common],
        help="Post to the channel an AirTable record routes to (record → project → channel)",
    )
    p_nr.add_argument("--record", required=True, help="AirTable record ID (rec…)")
    p_nr.add_argument("--table", required=True, help="AirTable table ID or name the record lives in")
    p_nr.add_argument("--text", help="Message text (used above the record link, or as fallback)")
    p_nr.add_argument("--blocks-json", help='Custom Block Kit ("blocks":[...] or bare [...]; "-" for stdin)')
    p_nr.add_argument("--channel", help="Override the resolved channel (ID or name)")

    # --- run-alert ---  (one nested subcommand per registered recipe)
    p_alert = sub.add_parser(
        "run-alert", parents=[common], help="Run a named alert recipe"
    )
    recipe_sub = p_alert.add_subparsers(dest="recipe", required=True)
    for name in recipe_names():
        recipe = get_recipe(name)
        rp = recipe_sub.add_parser(
            name, parents=[common], help=getattr(recipe, "HELP", ""),
        )
        rp.add_argument("--channel", help="Slack channel ID or configured name")
        recipe.add_arguments(rp)

    args = parser.parse_args()
    # --dry-run may be absent from the namespace if never passed (SUPPRESS).
    if not hasattr(args, "dry_run"):
        args.dry_run = False

    commands = {
        "transcribe-start": cmd_transcribe_start,
        "transcribe-ready": cmd_transcribe_ready,
        "schedule-alert": cmd_schedule_alert,
        "post": cmd_post,
        "ghost-import": cmd_ghost_import,
        "notify-record": cmd_notify_record,
        "run-alert": cmd_run_alert,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
