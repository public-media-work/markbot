"""Secret resolution for markbot — env var first, then the workspace resolver.

Follows the workspace standard (the-lodge `conventions/SECRETS_MANAGEMENT.md`):
**code never resolves credentials directly** — it delegates to `get-secret.sh`,
which walks env → 1Password (registry-driven) → legacy fallback.
markbot checks the environment itself first so it still works in CI / the cloud,
where the-lodge checkout isn't present and secrets arrive as env vars (repo
secrets). No secret references are hardcoded here; the-lodge `registry.yaml` is
the single source of truth.

Secret keys use the-lodge canonical names (e.g. `AIRTABLE_PAT`, `SLACK_BOT_TOKEN`).
"""

from __future__ import annotations

import os
import subprocess

# The-lodge canonical resolver. Override the path with LODGE_GET_SECRET; if the
# script isn't present (e.g. in CI) only the environment is consulted.
GET_SECRET = os.environ.get(
    "LODGE_GET_SECRET",
    os.path.expanduser("~/Developer/the-lodge/scripts/get-secret.sh"),
)


class SecretNotFound(RuntimeError):
    """Raised when a secret is in neither the environment nor the workspace resolver."""


def _get_secret_sh(name: str) -> str | None:
    """Resolve `name` via the-lodge get-secret.sh. None if unavailable/unresolved."""
    if not (GET_SECRET and os.path.exists(GET_SECRET) and os.access(GET_SECRET, os.X_OK)):
        return None
    try:
        result = subprocess.run(
            [GET_SECRET, name], capture_output=True, text=True, timeout=30
        )
    except Exception:
        return None
    return (result.stdout.strip() or None) if result.returncode == 0 else None


def resolve_secret(name: str, *, env=None, runner=None) -> str:
    """Return secret ``name`` from the environment, else the workspace resolver.

    `env` and `runner` are injectable for testing; they default to ``os.environ``
    and the get-secret.sh delegator.
    """
    env = os.environ if env is None else env
    value = env.get(name)
    if value:
        return value

    reader = _get_secret_sh if runner is None else runner
    value = reader(name)
    if value:
        return value

    raise SecretNotFound(
        f"Secret {name!r} not found. Set the {name} environment variable, or make it "
        f"resolvable via the-lodge get-secret.sh (registry → 1Password). Override the "
        f"resolver path with LODGE_GET_SECRET=/path/to/get-secret.sh."
    )
