"""Safe Bash command detection.

Parses compound shell commands to extract individual command names, then checks
them against the active mode:

  denylist  (default) -- allow unless any command is in _UNSAFE.
  allowlist (legacy)  -- allow only if every command is in _SAFE.

Mode is set via the bash-safe rule's "mode" field in hook-rules.json.
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

_SAFE = frozenset({
    # Shell builtins
    "cd", "export", "source", ".", "set", "unset", "shift",
    "echo", "printf", "read", "true", "false", ":",
    "exit", "return", "break", "continue",
    "local", "declare", "typeset", "readonly",
    "alias", "unalias", "trap", "wait",
    "test", "[", "[[",
    # Text search and processing
    "grep", "egrep", "fgrep", "rg", "ag",
    "awk", "gawk", "sed", "cut", "tr", "col", "column",
    "sort", "uniq", "wc", "diff", "diff3", "patch", "comm", "cmp",
    # File reading / inspection
    "cat", "head", "tail", "less", "more", "strings", "hexdump",
    "file", "stat", "du", "df", "ls", "find", "locate", "fd",
    "realpath", "readlink", "dirname", "basename",
    # Environment / system info
    "env", "printenv", "which", "type", "where",
    "pwd", "date", "whoami", "hostname", "uname", "id", "groups",
    "nproc", "arch",
    # Stream / pipe utilities
    "xargs", "tee", "jq", "yq", "xmllint",
    "base64", "md5", "md5sum", "sha1sum", "sha256sum", "shasum",
    "bc", "expr", "seq", "numfmt",
    # Script runtimes
    "python3", "python", "node", "ruby", "perl",
    # Dev: version control
    "git", "gh",
    # Dev: package managers + build
    "npm", "yarn", "pnpm", "npx", "bun", "bunx",
    "pip", "pip3", "uv", "pipenv", "poetry", "pdm",
    "make", "cmake", "ninja", "rake", "ant", "mvn", "gradle",
    "go", "cargo", "rustc", "javac", "java",
    # Dev: test runners
    "pytest", "jest", "vitest", "mocha", "jasmine", "rspec",
    # Dev: linters / formatters / type checkers
    "eslint", "tslint", "prettier", "black", "ruff", "mypy", "pyright",
    "flake8", "pylint", "isort", "bandit",
    # Dev: bundlers / compilers
    "tsc", "webpack", "vite", "rollup", "esbuild", "turbo",
    # File management
    "cp", "mv", "mkdir", "touch", "chmod", "ln", "install",
    "tar", "gzip", "gunzip", "zip", "unzip", "bzip2", "xz", "zstd",
    # Network (API calls, downloads -- not execution)
    "curl", "wget", "http",
    # Process inspection (not management)
    "ps", "pgrep", "lsof",
    # Misc utilities
    "sleep", "timeout",
    "tput", "stty",
    "open", "pbcopy", "pbpaste",   # macOS
    "xdg-open", "xclip", "xsel",  # Linux
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

    mode="denylist" (default): allowed unless any command is in _UNSAFE.
    mode="allowlist" (legacy): allowed only if every command is in _SAFE.
    """
    if payload.get("tool_name") != "Bash":
        return False

    command = payload.get("tool_input", {}).get("command", "")
    if not command.strip():
        return False

    names = _extract_command_names(command)

    if not names:
        return False

    mode = (rule or {}).get("mode", "denylist")
    if mode == "allowlist":
        return all(name in _SAFE for name in names)
    else:  # denylist
        return not any(name in _UNSAFE for name in names)
