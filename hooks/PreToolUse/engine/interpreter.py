#!/usr/bin/env python3
"""Pre-tool-use hook interpreter.

Reads tool call JSON from stdin, evaluates hook rules, writes JSON decision to stdout.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from resolver import resolve_repo_root

from engine import evaluate

HOOK_RULES_PATH = Path(__file__).parent.parent / "hook-rules.json"


def load_hook_rules() -> list:
    with open(HOOK_RULES_PATH) as f:
        data = json.load(f)
    return data.get("hook-rules", [])


def main() -> None:
    payload = json.loads(sys.stdin.read())
    cwd = payload.get("cwd", "")

    rules = load_hook_rules()
    repo_root = resolve_repo_root(cwd)

    result = evaluate(payload, rules, repo_root=repo_root)

    decision = result["decision"]
    if decision == "proceed":
        return

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if reason := result.get("reason"):
        output["hookSpecificOutput"]["permissionDecisionReason"] = reason

    print(json.dumps(output))


if __name__ == "__main__":
    main()
