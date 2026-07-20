# markbot

**Your Helpful MarkBot** — a Slack alert hub for WPM workflows.

markbot posts scheduled, data-driven alerts and workflow notifications to Slack
as a single bot identity (`slack-sdk`, Bot Token auth). It is **outbound only**.

## Structure

A small package fronted by a single entrypoint:

| Path | Role |
|------|------|
| `markbot.py` | CLI entrypoint — argparse dispatch, direct-notification commands, `run-alert` |
| `config.py` | Bot identity, channel map (`resolve_channel`), message defaults — no client names |
| `credentials.py` | `resolve_secret` — env var first, then the-lodge `get-secret.sh` |
| `slack_client.py` | `get_slack_client` + `post_blocks` (shared by CLI and recipes; `SlackApiError` handling) |
| `recipes/` | One module per alert recipe; auto-discovered by the registry |
| `manifest.json` | Slack app manifest (manifest-as-code; read by the Slack CLI via `.slack/hooks.json`) |
| `scripts/manifest.py` | `get-manifest` hook — prints `manifest.json` to the Slack CLI |

## Non-Claude Agents: Workspace Isolation Rules

**If you are NOT Claude Code** (e.g., Gemini CLI, Codex, Copilot, Cursor, or any other LLM agent), you MUST follow these isolation rules to avoid interfering with Claude agent work:

1. **Always work in a git worktree.** Never modify files on the current branch directly. Create a worktree before making any changes:
   ```bash
   git worktree add .worktrees/<your-agent-name>-<feature> -b <your-agent-name>/<feature-description>
   ```
2. **Always commit to a feature branch.** Your branch name must include your agent identifier (e.g., `gemini/fix-typo`, `codex/add-tests`, `copilot/refactor-utils`). Never commit to `main` or any branch you did not create.
3. **Never force-push, rebase, or modify branches you did not create.** Treat all existing branches as read-only references.
4. **Clean up after yourself.** When your work is complete, leave the worktree in place for human review. Do not merge your own branches.
5. **Follow all other rules in this file.** The conventions below (commit format, secrets management, attribution, etc.) apply to all agents equally.

> Claude Code agents are exempt from the worktree requirement because they are the primary agents for this workspace and coordinate directly with the user.

## Commands

| Command | Purpose |
|---------|---------|
| `run-alert <name>` | Run a named alert recipe (pull data → build message → post). Scheduler-fired. |
| `post` | Generic Block Kit poster (JSON arg or `-` for stdin) |
| `transcribe-start` / `transcribe-ready` | Transcription lifecycle (prints `thread_ts`) |
| `schedule-alert` | Release readiness (missing / drafted / scheduled) |
| `ghost-import` | Publishing import lifecycle (start / draft / scheduled / failed) |

Recipes: `program-of-the-day` (AirTable Content Calendar → record links).

## Adding a recipe

Drop a module in `recipes/` exposing `NAME`, `HELP`, `add_arguments(parser)`,
`build_blocks(args) -> list[dict]`, and `fallback_text(args) -> str` (optional
`DEFAULT_CHANNEL`). It's auto-registered — no wiring. In `--dry-run`, a recipe
should render sample data without needing credentials or network.

## Secrets

Resolved **env var → the-lodge `get-secret.sh`** (the workspace standard; see
the-lodge `conventions/SECRETS_MANAGEMENT.md`). markbot never resolves credentials
directly — `get-secret.sh` walks env → 1Password (driven by the-lodge
`registry.yaml`, the single source of truth) → legacy fallback. markbot checks the
environment itself first so it works in CI/cloud (repo secrets) where the-lodge
checkout isn't present; override the resolver path with `LODGE_GET_SECRET`. Keys
use the-lodge canonical names — `AIRTABLE_PAT` (registry `secret/airtable-api-key`,
`op://Workspace-PBSWI/AirTable/credential`) and `SLACK_BOT_TOKEN` (env-var; not yet
registered). Never a committed `.env`.

## Scheduling

Scheduler-agnostic. GitHub Actions cron (`.github/workflows/alerts.yml`) for
deterministic recipes; Claude scheduled routines for agentic ones. See
`docs/SCHEDULING.md`.

## Slack app lifecycle (Slack CLI)

`manifest.json` is the source of truth. `slack manifest validate --source local`
checks it; `slack install` creates/installs the app to the workspace. markbot is
**not** a Bolt app — the hooks provide `get-manifest` only, no socket-mode
runtime. See `docs/SETUP.md`.

## Conventions

- `markbot.py` is the entrypoint of a small package (config / credentials / slack_client / recipes).
- `--dry-run` prints Block Kit JSON without posting; works before *or* after the subcommand.
- `transcribe-start` and `ghost-import` print `thread_ts` to stdout for caller capture.
- `post` accepts `{"blocks": [...]}` or a bare `[...]`.
- Channel IDs (or friendly names mapped in `config.CHANNELS`) for `--channel`.
- Type hints; ruff for lint; pytest via `python3 -m pytest`.

## Environment

- `SLACK_BOT_TOKEN` — Bot User OAuth Token (`xoxb-`)
- `AIRTABLE_PAT` — for AirTable-backed recipes (the-lodge canonical name)
- `PODCAST_SITE_URL` — optional; referenced by ghost-import notifications
