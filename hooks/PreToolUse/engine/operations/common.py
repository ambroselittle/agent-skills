"""Shared utilities for operation handlers."""

from __future__ import annotations

import re
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


_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?\n(?:.*\n)*?\1[ \t]*(?:\n|$)")


def _strip_heredocs(command: str) -> str:
    """Remove heredoc bodies from a shell command.

    Heredoc content is data, not arguments: a body that mentions a file name or a
    URL must not be mistaken for a path the command reads or writes.
    """
    return _HEREDOC_RE.sub("", command)
