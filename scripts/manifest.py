#!/usr/bin/env python3
"""Slack CLI `get-manifest` hook.

Prints the app manifest as JSON so the Slack CLI can manage the app from
versioned code (manifest-as-code). `manifest.json` is the human-editable source
of truth; this hook just feeds it to the CLI — no Bolt runtime involved.
"""

import json
from pathlib import Path


def main() -> None:
    manifest = Path(__file__).resolve().parent.parent / "manifest.json"
    # Re-emit compactly so the CLI receives a single JSON document on stdout.
    print(json.dumps(json.loads(manifest.read_text())))


if __name__ == "__main__":
    main()
