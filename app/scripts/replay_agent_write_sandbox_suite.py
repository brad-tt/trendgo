#!/usr/bin/env python3
"""Unified regression suite for Agent write-path sandboxes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent

SUITE = [
    "validate_agent_indexes.py",
    "replay_agent_context_api.py",
    "replay_agent_workflow_intake_api.py",
    "replay_agent_trade_lifecycle_samples.py",
    "replay_agent_nl_open_intake_sandbox.py",
    "replay_agent_nl_close_intake_sandbox.py",
    "replay_agent_nl_rule_event_intake_sandbox.py",
    "replay_agent_nl_review_intake_sandbox.py",
    "replay_agent_open_write_sandbox.py",
    "replay_agent_close_write_sandbox.py",
    "replay_agent_rule_event_write_sandbox.py",
    "replay_agent_observation_sandbox.py",
    "replay_agent_review_write_sandbox.py",
    "replay_agent_validation_write_sandbox.py",
    "replay_agent_acceptance_write_sandbox.py",
]


def main() -> int:
    print("Agent write sandbox suite started.")
    print(f"- steps: {len(SUITE)}")
    for index, script_name in enumerate(SUITE, start=1):
        script_path = SCRIPT_DIR / script_name
        print(f"\n[{index}/{len(SUITE)}] {script_name}")
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=SCRIPT_DIR.parent,
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)
        if completed.returncode != 0:
            print(f"\nSuite failed at {script_name}.", file=sys.stderr)
            return completed.returncode

    print("\nAgent write sandbox suite passed.")
    print("- scope: indexes, context, workflow intake, lifecycle dry-run, natural-language open/close/rule-event/review intake, open, close, rule-event, review, validation, acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
