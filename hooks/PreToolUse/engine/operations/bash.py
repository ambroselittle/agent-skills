"""Safe Bash command detection.

Parses compound shell commands to extract individual command names, then checks
them against _UNSAFE (denylist): allow unless any command is in _UNSAFE.
"""
import re
from typing import Optional

_CONTROL_FLOW = frozenset({
    "for", "while", "until", "if", "then", "else", "elif", "fi",
    "do", "done", "case", "esac", "in", "select", "function",
    "time", "coproc", "!",
})

_UNSAFE = frozenset({
    # Privilege escalation
    "sudo", "su", "doas",
    # Arbitrary code execution
    "eval", "exec",
    # Block device / disk destruction
    "dd", "shred", "fdisk", "parted", "mkfs",
    # Remote execution
    "ssh", "scp", "sftp",
    # Network listeners / raw sockets
    "nc", "netcat", "ncat",
    # macOS Keychain access
    "security",
})


def _extract_command_names(command: str) -> list[str]:
    """
    Extract bare command names from a compound shell command.
    """
    cmd = re.sub(r"\\\n\s*", " ", command)

    cmd = re.sub(
        r"<<-?\s*['\"]?(\w+)['\"]?\n(?:.*\n)*?\1[ \t]*(?:\n|$)",
        "",
        cmd,
    )

    cmd = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', cmd)
    cmd = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", cmd)

    cmd = re.sub(r"\bfor\s+\w[\w.-]*\s+in\b[^;{\n]*", "", cmd)

    segments = re.split(r"\|\||\||&&|[;\n]", cmd)

    names: list[str] = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        seg = re.sub(r"\d?>>?\s*\S+", "", seg)
        seg = re.sub(r"\d?<[<&]?\s*\S+", "", seg).strip()
        if not seg:
            continue

        _standalone_subshell = re.match(r"^\s*\w+=\$\(([^)]*)\)\s*$", seg)
        seg = re.sub(r"^\s*(?:\w+=(?:\$\([^)]*\)|\S*)\s*)+", "", seg).strip()
        if not seg:
            if _standalone_subshell:
                seg = _standalone_subshell.group(1).strip()
            if not seg:
                continue

        words = seg.split()
        if not words:
            continue

        cmd_word = None
        for word in words:
            if word not in _CONTROL_FLOW:
                cmd_word = word
                break

        if cmd_word is not None:
            names.append(cmd_word)

    return names


def matches_bash_safe(payload: dict, rule: Optional[dict] = None) -> bool:
    """
    True if the Bash command should be silently allowed.

    Allowed unless any extracted command name is in _UNSAFE.
    """
    if payload.get("tool_name") != "Bash":
        return False

    command = payload.get("tool_input", {}).get("command", "")
    if not command.strip():
        return False

    names = _extract_command_names(command)

    if not names:
        return False

    return not any(name in _UNSAFE for name in names)
