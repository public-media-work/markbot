# Your Helpful MarkBot — Setup Guide

markbot is a Slack bot that posts alerts and workflow notifications to your WPM
Slack workspace as a single bot identity. This guide creates and installs the
app with the **Slack CLI** (manifest-as-code), then sets the bot token.

## Prerequisites

```bash
pip install -r requirements.txt   # slack-sdk, requests
slack version                     # Slack CLI (https://api.slack.com/automation/cli)
op --version                      # 1Password CLI (used by the-lodge get-secret.sh)
```

## Step 1: Log in the Slack CLI

```bash
slack login   # authorize the CLI, then select your WPM workspace when prompted
```

## Step 2: Validate the manifest

The app is defined as code in [`manifest.json`](../manifest.json). The Slack CLI
reads it through the `get-manifest` hook in `.slack/hooks.json`.

```bash
slack manifest validate --source local   # → "App Manifest Validation Result: Valid"
```

## Step 3: Create & install the app

```bash
slack install    # create the app from manifest.json and install it to the workspace
```

Follow the prompts to select your WPM workspace and authorize. (Web fallback: at
[api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From a
manifest**, paste `manifest.json`.)

Scopes requested: `chat:write`, `chat:write.public`.

## Step 4: Set the bot token

markbot follows the workspace secrets standard (the-lodge
`conventions/SECRETS_MANAGEMENT.md`): **env var first, then `get-secret.sh`** (which
resolves from 1Password via `registry.yaml`). markbot never touches 1Password
directly. Env-first is what lets a cloud scheduler run it with no dependence on
your Mac. Secret keys use the-lodge canonical names.

**Slack bot token** (`SLACK_BOT_TOKEN`) — copy the **Bot User OAuth Token**
(`xoxb-…`) from the app's **OAuth & Permissions** page. It isn't in the-lodge
registry yet, so provide it as an env var (locally via `.claude/settings.local.json`
`env`, or a CI repo secret):

```bash
export SLACK_BOT_TOKEN=xoxb-...
```

(To bring it under the standard, register a 1Password item + a `registry.yaml`
entry in the-lodge, then it resolves through `get-secret.sh` like the rest.)

**AirTable PAT** (`AIRTABLE_PAT`) — already registered
(`secret/airtable-api-key` → `op://Workspace-PBSWI/AirTable/credential`). Local
resolution needs the-lodge resolver working (`lodge-doctor` installed, work
1Password account signed in). Otherwise export it:

```bash
export AIRTABLE_PAT=$(~/Developer/the-lodge/scripts/get-secret.sh AIRTABLE_PAT)
```

**CI:** set the secrets as GitHub Actions repo secrets (env-first picks them up),
or use a [1Password service account](https://developer.1password.com/docs/ci-cd/)
(`OP_SERVICE_ACCOUNT_TOKEN`). Point markbot at a different resolver with
`LODGE_GET_SECRET=/path/to/get-secret.sh`.

## Step 5: Upload the bot icon (optional)

The manifest can't set the icon image. In the app settings → **Basic Information
→ Display Information**, upload an icon, then **Save Changes**.

## Step 6: Test

```bash
# Dry run — no token or network needed
python3 markbot.py --dry-run run-alert program-of-the-day --channel C0XXXX
python3 markbot.py --dry-run post --blocks-json '{"blocks":[{"type":"section","text":{"type":"mrkdwn","text":"Hello"}}]}' --channel C0XXXX

# Live test — post to a test channel first (create #markbot-testing, use its ID)
python3 markbot.py run-alert program-of-the-day --channel YOUR_TEST_CHANNEL_ID
```

## Scheduling

See [SCHEDULING.md](SCHEDULING.md) — recipes are fired by GitHub Actions cron
(deterministic alerts) or Claude scheduled routines (agentic alerts). Both call
the same `run-alert`.

## Channel Reference

Use channel **IDs**, not names. Add friendly aliases in `config.py`'s `CHANNELS`
map as WPM channels are set up.

| Channel | ID | Purpose |
|---------|----|---------|
| _(add WPM channels here)_ | `C0XXXXXXXXX` | |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Secret 'SLACK_BOT_TOKEN' not found` | Export the env var (Step 4), or make it resolvable via `get-secret.sh` |
| `Secret 'AIRTABLE_PAT' not found` | Export it, or fix the-lodge resolver (`lodge-doctor` installed, work 1Password signed in) |
| `Slack API call failed — not_in_channel` | Bot needs `chat:write.public`, or invite it to the channel |
| `Slack API call failed — invalid_auth` | Token is wrong/expired — reinstall and re-copy the `xoxb-` token |
| Message posts as plain text (no formatting) | markbot always sends both `blocks` and a `text` fallback — this shouldn't happen |
