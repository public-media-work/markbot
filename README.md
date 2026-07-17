# Your Helpful MarkBot

A single-identity Slack **alert hub** for WPM workflows. It posts scheduled,
data-driven alerts and workflow notifications to Slack as one consistent sender,
and gives other CLI/LLM workflows a simple Block Kit notifier. Outbound only.

## Quick Start

```bash
pip install -r requirements.txt

# Dry run (no token or network — prints the Block Kit JSON)
python3 markbot.py --dry-run run-alert program-of-the-day --channel C0XXXX

# Live run (token via env var or the-lodge resolver — see docs/SETUP.md)
export SLACK_BOT_TOKEN=xoxb-your-token
python3 markbot.py run-alert program-of-the-day --channel C0XXXX
```

`--dry-run` works before *or* after the subcommand.

## Two kinds of commands

**Alert recipes** — `run-alert <name>` — pull data from other systems and post a
message. They're fired by a cloud scheduler (GitHub Actions cron or a Claude
scheduled routine), so nothing depends on your local machine. Add one by dropping
a module in [`recipes/`](recipes/).

- **`program-of-the-day`** — links the AirTable record for each program recording
  on a given weekday.

**Direct notifications** — for callers that build their own message:

- **`post`** — generic Block Kit poster (JSON arg or `-` for stdin)
- **`transcribe-start` / `transcribe-ready`** — transcription lifecycle (prints `thread_ts`)
- **`schedule-alert`** — release readiness (missing / drafted / scheduled)
- **`ghost-import`** — publishing import lifecycle (start / draft / scheduled / failed)

## Docs

- [docs/SETUP.md](docs/SETUP.md) — create & install the Slack app with the Slack CLI, and set the token
- [docs/SCHEDULING.md](docs/SCHEDULING.md) — how to schedule recipes (GitHub Actions vs Claude routines)

## Secrets

Resolved **env var first, then the-lodge resolver** (`get-secret.sh` → registry →
1Password) — env-first is what lets a cloud runner fire markbot with no dependence
on your machine. Keys match the-lodge registry (`AIRTABLE_PAT`, `SLACK_BOT_TOKEN`).
See [docs/SETUP.md](docs/SETUP.md).
