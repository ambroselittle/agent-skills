#!/usr/bin/env python3
"""Translate Codex hooks to the shared policy; never execute the pending tool.

PreToolUse enforces denials. PermissionRequest grants approvals. The two
events intentionally have different JSON output contracts. Unsupported input
and evaluation failures never produce an automatic approval.
"""

from __future__ import annotations

import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

from resolver import resolve_repo_root

from engine import evaluate, load_user_local_rules


def record_event(payload: dict, output: dict | None, error: str | None = None) -> None:
    """Bounded diagnostics: metadata only, never commands, file paths or content."""
    log = Path(__file__).resolve().parent.parent / "codex-events.jsonl"
    tool_input = payload.get("tool_input")
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "session_id": payload.get("session_id"),
        "event": payload.get("hook_event_name"),
        "tool": payload.get("tool_name"),
        "input_type": type(tool_input).__name__,
        "input_keys": sorted(tool_input) if isinstance(tool_input, dict) else [],
        "command_type": type(tool_input.get("command")).__name__
        if isinstance(tool_input, dict)
        else None,
        "decision": (output or {}).get("hookSpecificOutput", {}).get("decision", {}).get("behavior")
        or (output or {}).get("hookSpecificOutput", {}).get("permissionDecision")
        or "defer",
        "error": error,
    }
    try:
        if log.exists() and log.stat().st_size > 1_000_000:
            log.replace(log.with_suffix(".previous.jsonl"))
        with log.open("a") as stream:
            stream.write(json.dumps(record) + "\n")
    except OSError:
        pass  # Diagnostics must not change permission decisions.


def patch_calls(payload: dict) -> list[dict]:
    """Represent patch file operations using the engine's existing vocabulary.

    Write checks examine the added/replacement text, just as Claude Edit checks
    new_string. Moves check both paths; deletes go through delete-path rules.
    Unknown syntax raises rather than receiving the generic Edit/Write allowance.
    """
    command = payload.get("tool_input", {}).get("command", "")
    lines = command.splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("Unrecognized patch envelope")
    calls = []
    i = 1
    while i < len(lines) - 1:
        header = lines[i]
        kind = next(
            (
                kind
                for kind in ("Add", "Update", "Delete")
                if header.startswith(f"*** {kind} File: ")
            ),
            None,
        )
        if kind is None:
            raise ValueError("Unrecognized patch operation")
        path = header.split(": ", 1)[1]
        if not path:
            raise ValueError("Empty patch path")
        paths = [path]
        i += 1
        if kind == "Update" and lines[i].startswith("*** Move to: "):
            destination = lines[i].removeprefix("*** Move to: ")
            if not destination:
                raise ValueError("Empty move destination")
            paths.append(destination)
            i += 1
        content = []
        while i < len(lines) - 1 and not lines[i].startswith("*** "):
            line = lines[i]
            if kind == "Delete" or (line and not line.startswith(("+", "-", " ", "@@"))):
                raise ValueError("Unrecognized patch line")
            if line.startswith("+"):
                content.append(line[1:])
            i += 1
        if i < len(lines) - 1 and lines[i] == "*** End of File":
            i += 1
        if kind == "Delete" or len(paths) == 2:
            calls.append(
                {
                    **payload,
                    "tool_name": "Bash",
                    "tool_input": {"command": f"rm -- {shlex.quote(path)}"},
                }
            )
        if kind != "Delete":
            for file_path in paths:
                calls.append(
                    {
                        **payload,
                        "tool_name": "Write",
                        "tool_input": {"file_path": file_path, "content": "\n".join(content)},
                    }
                )
    if not calls:
        raise ValueError("Empty patch")
    return calls


def handle(payload: dict, rules: list) -> dict | None:
    event = payload.get("hook_event_name")
    if event not in ("PreToolUse", "PermissionRequest"):
        return None
    tool = payload.get("tool_name", "")
    if tool == "apply_patch":
        try:
            calls = patch_calls(payload)
        except (ValueError, TypeError, AttributeError, IndexError):
            if event == "PermissionRequest":
                return None
            return {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Unable to evaluate patch with agent-skills policy."
                    ),
                }
            }
    elif tool == "Bash":
        command = payload.get("tool_input", {}).get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        calls = [payload]
    elif tool.startswith("mcp__"):
        calls = [payload]
    else:
        return None

    root = resolve_repo_root(payload.get("cwd", ""))
    results = [evaluate(call, rules, repo_root=root) for call in calls]
    # Every operation must be allowed before a multi-file patch is approved.
    priority = {"allow": 0, "proceed": 1, "ask": 2, "deny": 3}
    result = max(results, key=lambda item: priority[item["decision"]])
    decision = result["decision"]
    reason = result.get("reason") or "Blocked by agent-skills policy."
    if event == "PermissionRequest":
        if decision not in ("allow", "deny"):
            return None
        output = {"behavior": decision}
        if decision == "deny":
            output["message"] = reason
        return {"hookSpecificOutput": {"hookEventName": event, "decision": output}}
    if decision not in ("deny", "ask"):
        return None
    if decision == "ask":
        reason += " This rule requires review; Codex PreToolUse cannot request approval."
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> None:
    event = None
    payload = {}
    try:
        payload = json.load(sys.stdin)
        event = payload.get("hook_event_name")
        root = Path(__file__).resolve().parent.parent
        rules_path = root / "hook-rules.json"
        if not rules_path.exists():
            rules_path = root / "rules.json"  # Running from the source checkout.
        rules = json.loads(rules_path.read_text())["hook-rules"]
        # Validate the optional overlay before using the existing loader. A
        # malformed private policy must not silently become a broad allowance.
        overlay = Path.home() / ".agent-skills/local-rules.json"
        if overlay.exists():
            private = json.loads(overlay.read_text())["hooks"]["PreToolUse"]["rules"]
            if not isinstance(private, list):
                raise ValueError("Invalid private policy")
        output = handle(payload, rules + load_user_local_rules())
        record_event(payload, output)
        if output:
            print(json.dumps(output))
    except Exception as error:
        # Exception messages and payloads can contain sensitive command data.
        print(f"Agent-skills policy unavailable ({type(error).__name__}).", file=sys.stderr)
        if isinstance(payload, dict):
            record_event(payload, None, type(error).__name__)
        if event == "PreToolUse":
            raise SystemExit(2) from None
        # No PermissionRequest decision: retain the normal approval prompt.


if __name__ == "__main__":
    main()
