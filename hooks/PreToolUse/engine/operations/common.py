"""Shared utilities for operation handlers."""

from __future__ import annotations

import shlex

_COMPOUND_OPS = frozenset(["&&", "||", ";", "|"])


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _split_subcommands(command: str) -> list[list[str]]:
    tokens = _tokenize(command)
    subcommands: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok in _COMPOUND_OPS:
            if current:
                subcommands.append(current)
                current = []
        elif tok.endswith(";"):
            stripped = tok[:-1]
            if stripped:
                current.append(stripped)
            if current:
                subcommands.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        subcommands.append(current)
    return subcommands or [[]]


def _is_bash(payload: dict) -> bool:
    return payload.get("tool_name") == "Bash"


def _command(payload: dict) -> str:
    return payload.get("tool_input", {}).get("command", "")
