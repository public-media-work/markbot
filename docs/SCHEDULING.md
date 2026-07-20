# Scheduling alerts

markbot is **scheduler-agnostic**. An alert recipe is just a CLI invocation:

```bash
python markbot.py run-alert program-of-the-day --channel C0XXXX
```

Because markbot resolves its own secrets (env → the-lodge resolver) and fetches its own
data, *any* runner can fire it and none of them depend on your local machine.
Pick the scheduler per recipe:

| | GitHub Actions cron | Claude scheduled routine |
|---|---|---|
| Machine-independent | ✅ cloud | ✅ cloud |
| Best for | **deterministic** alerts (query → post link) | **agentic** alerts (summarize, decide, compose) |
| Cost / run | ~free CI minutes | full agent run (tokens) |
| Secrets | repo secrets/vars | routine's cloud env |
| Versioned with code | ✅ in-repo YAML | partial |

**Rule of thumb:** deterministic recipe → GitHub Actions; a recipe that needs
reasoning → Claude routine. Both call the same `run-alert`, so there's no lock-in.

## GitHub Actions (default)

`.github/workflows/alerts.yml` runs on a cron and via manual dispatch. Configure
under **Settings → Secrets and variables → Actions**:

- Secrets: `SLACK_BOT_TOKEN`, `AIRTABLE_PAT`
- Variables: `PROGRAM_ALERTS_CHANNEL` (default channel for the cron), plus
  `AIRTABLE_BASE_ID` / `AIRTABLE_TABLE` for the program-of-the-day recipe

Add a new schedule by copying the workflow or adding a `cron:` entry. Test
without waiting for the cron via the **Run workflow** (workflow_dispatch) button.

## Claude scheduled routines (for agentic recipes)

For alerts that need reasoning, schedule a Claude routine (`/schedule`) that runs
the same command. Provide `SLACK_BOT_TOKEN` (and any data-source keys) in the
routine's environment. Use this when the message content isn't a fixed
transform — e.g. "summarize this week's records and flag anything missing an air
date."

## Local (not recommended for production)

`launchd`/`cron` on your Mac works for quick tests but only fires while the
machine is awake — which defeats the decoupling goal. Prefer a cloud runner for
anything you rely on.
