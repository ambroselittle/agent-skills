"""Filesystem operation handlers: read-path, write-path, delete-path."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from resolver import matches_path_pattern, normalize_path

from operations.common import _split_subcommands, _strip_heredocs

_READ_COMMANDS = frozenset(
    [
        "cat",
        "head",
        "tail",
        "less",
        "more",
        "grep",
        "egrep",
        "fgrep",
        "rg",
        "ripgrep",
        "awk",
        "sed",
        "sort",
        "wc",
        "diff",
        "cut",
        "strings",
    ]
)

_WRITE_COMMANDS = frozenset(
    [
        "cp",
        "mv",
        "tee",
        "install",
    ]
)

_DELETE_COMMANDS = frozenset(
    [
        "rm",
        "rmdir",
        "unlink",
    ]
)

# Flags that consume the following token as their value, per command. A flag
# listed for one command must not be assumed for another: `-f` is a file for
# grep but "follow" for tail, and swallowing tail's file argument would hide it.
_GREP_VALUE_FLAGS = frozenset(
    [
        "-e",
        "--regexp",
        "-f",
        "--file",
        "-m",
        "--max-count",
        "-A",
        "--after-context",
        "-B",
        "--before-context",
        "-C",
        "--context",
        "-d",
        "--directories",
        "-D",
        "--devices",
        "--include",
        "--exclude",
        "--exclude-dir",
        "--exclude-from",
    ]
)
_RG_VALUE_FLAGS = _GREP_VALUE_FLAGS | frozenset(
    [
        "-g",
        "--glob",
        "--iglob",
        "-t",
        "--type",
        "-T",
        "--type-not",
        "--type-add",
        "-M",
        "--max-columns",
        "-j",
        "--threads",
        "-E",
        "--encoding",
        "--max-depth",
        "--max-filesize",
        "-r",
        "--replace",
        "--sort",
        "--sortr",
        "--pre",
        "--pre-glob",
        "--path-separator",
        "--context-separator",
        "--field-context-separator",
        "--field-match-separator",
    ]
)
_VALUE_FLAGS: dict[str, frozenset[str]] = {
    "grep": _GREP_VALUE_FLAGS,
    "egrep": _GREP_VALUE_FLAGS,
    "fgrep": _GREP_VALUE_FLAGS,
    "rg": _RG_VALUE_FLAGS,
    "ripgrep": _RG_VALUE_FLAGS,
    "sed": frozenset(["-e", "--expression", "-f", "--file", "-l", "--line-length"]),
    "awk": frozenset(["-f", "-v", "-F"]),
    "head": frozenset(["-n", "--lines", "-c", "--bytes"]),
    "tail": frozenset(["-n", "--lines", "-c", "--bytes", "-s", "--sleep-interval", "--pid"]),
    "sort": frozenset(
        [
            "-k",
            "--key",
            "-t",
            "--field-separator",
            "-o",
            "--output",
            "-S",
            "--buffer-size",
            "-T",
            "--temporary-directory",
            "--parallel",
        ]
    ),
    "cut": frozenset(
        ["-d", "--delimiter", "-f", "--fields", "-c", "--characters", "-b", "--bytes"]
    ),
    "diff": frozenset(
        [
            "-I",
            "--ignore-matching-lines",
            "-x",
            "--exclude",
            "-X",
            "--exclude-from",
            "-S",
            "--starting-file",
            "-W",
            "--width",
            "-F",
            "--show-function-line",
        ]
    ),
    "strings": frozenset(["-n", "--bytes", "-t", "--radix", "-e", "--encoding"]),
    "install": frozenset(["-m", "--mode", "-o", "--owner", "-g", "--group", "-S", "--suffix"]),
}

# Commands whose first positional argument is a pattern or program, not a file,
# unless the pattern was supplied through an explicit flag instead.
_PATTERN_FIRST: dict[str, frozenset[str]] = {
    "grep": frozenset(["-e", "--regexp", "-f", "--file"]),
    "egrep": frozenset(["-e", "--regexp", "-f", "--file"]),
    "fgrep": frozenset(["-e", "--regexp", "-f", "--file"]),
    "rg": frozenset(["-e", "--regexp", "-f", "--file"]),
    "ripgrep": frozenset(["-e", "--regexp", "-f", "--file"]),
    "sed": frozenset(["-e", "--expression", "-f", "--file"]),
    "awk": frozenset(["-f"]),
}

_GLOB_CHARS = ("*", "?", "[")
_PATH_PREFIXES = ("/", "~", ".")


def _flag_name(tok: str) -> str:
    """`--include=*.py` and `--include` share the flag name `--include`."""
    return tok.split("=", 1)[0]


def _positional_args(tokens: list[str]) -> list[str]:
    """Return the non-flag arguments of a command, minus any pattern/program argument.

    Values consumed by flags are dropped, `--` ends option parsing, and for
    grep/sed/awk-style commands the first positional is the pattern (unless the
    pattern came through an explicit flag), so it is dropped as well.
    """
    cmd = Path(tokens[0]).name
    value_flags = _VALUE_FLAGS.get(cmd, frozenset())
    pattern_flags = _PATTERN_FIRST.get(cmd)
    pattern_supplied = False
    positionals: list[str] = []
    skip_next = False
    options_done = False
    prev = ""

    for tok in tokens[1:]:
        if skip_next:
            skip_next = False
            prev = tok
            continue
        if not options_done and tok == "--":
            options_done = True
            prev = tok
            continue
        if not options_done and tok.startswith("-") and len(tok) > 1:
            name = _flag_name(tok)
            if pattern_flags and name in pattern_flags:
                pattern_supplied = True
            if name in value_flags and "=" not in tok:
                skip_next = True
            prev = tok
            continue
        # BSD sed's -i takes a mandatory (often empty) backup suffix as the next token.
        if cmd == "sed" and prev == "-i" and tok == "":
            prev = tok
            continue
        positionals.append(tok)
        prev = tok

    if pattern_flags and not pattern_supplied and positionals:
        positionals.pop(0)
    return positionals


def _looks_like_path(tok: str, cwd: str | None, allow_missing: bool) -> bool:
    """Decide whether a positional argument is a filesystem path.

    Anything with a path prefix, a slash, a glob character, or a leading dot
    (`.env`, `.npmrc`) is a path. Any other bare token is a path when it exists
    on disk. When `allow_missing` is set (writes
    and deletes, which may target files not yet created) a bare token containing
    a dot also counts, as it did before existence checks were introduced. The
    same fallback applies when the working directory is unknown, so an
    unresolvable `cd` never hides a read.
    """
    if not tok:
        return False
    if tok.startswith(_PATH_PREFIXES) or "/" in tok or any(c in tok for c in _GLOB_CHARS):
        return True
    if cwd is None or allow_missing:
        return "." in tok
    return os.path.lexists(normalize_path(tok, cwd))


def _path_args(tokens: list[str], cwd: str | None, allow_missing: bool) -> list[str]:
    return [t for t in _positional_args(tokens) if _looks_like_path(t, cwd, allow_missing)]


def _next_cwd(tokens: list[str], cwd: str | None) -> str | None:
    """Track `cd` across subcommands so bare file names resolve where the command runs.

    Returns None when the target cannot be resolved statically (variables,
    command substitution, `cd -`), which downstream treats as "unknown".
    """
    if not tokens or Path(tokens[0]).name not in ("cd", "pushd"):
        return cwd
    args = [t for t in tokens[1:] if not t.startswith("-") or t == "-"]
    if not args:
        return os.path.expanduser("~")
    target = args[0]
    if target == "-" or cwd is None or any(c in target for c in "$`"):
        return None
    return normalize_path(target, cwd)


def _redirect_targets(command: str) -> tuple[list[str], list[str]]:
    """Files read via `< file` and written via `> file` / `>> file`, for any command.

    Tokenizes with `<` and `>` as punctuation so an operator is only recognized
    when unquoted: a quoted XML tag stays one word, while `wc -l <file` splits
    into `<` and `file`. Heredocs (`<<`), here-strings (`<<<`), process
    substitution (`<(...)`), and fd duplication (`2>&1`) are not file targets.
    """
    lexer = shlex.shlex(_strip_heredocs(command), posix=True, punctuation_chars="<>")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return [], []

    reads: list[str] = []
    writes: list[str] = []
    pending: list[str] | None = None
    for tok in tokens:
        if pending is not None:
            if not tok.startswith(("&", "(")):
                pending.append(tok)
            pending = None
            continue
        if tok == "<":
            pending = reads
        elif tok in (">", ">>"):
            pending = writes
    return reads, writes


def _python_open_paths(command: str) -> list[str]:
    return re.findall(r"""open\s*\(\s*['"]([^'"]+)['"]""", command)


def _rule_ignore_case(rule: dict) -> bool:
    """Path matching is case-insensitive unless the rule sets "case-sensitive": true."""
    return not rule.get("case-sensitive", False)


def _any_path_matches(
    paths: list[str],
    rule_paths: list[str],
    repo_root: str | None,
    cwd: str,
    ignore_case: bool = True,
) -> bool:
    for p in paths:
        for pattern in rule_paths:
            if matches_path_pattern(p, pattern, repo_root, cwd, ignore_case=ignore_case):
                return True
    return False


def _bash_candidates(
    command: str, cwd: str, commands: frozenset[str], allow_missing: bool
) -> list[str]:
    """Collect path arguments of the given commands from a Bash command line.

    Heredoc bodies are stripped first so their content is never read as arguments.
    """
    candidates: list[str] = []
    effective_cwd: str | None = cwd or None
    for tokens in _split_subcommands(_strip_heredocs(command)):
        if not tokens:
            continue
        if Path(tokens[0]).name in commands:
            candidates.extend(_path_args(tokens, effective_cwd, allow_missing))
        effective_cwd = _next_cwd(tokens, effective_cwd)
    return candidates


def collect_bash_paths(command: str, cwd: str) -> list[str]:
    """Every path a Bash command reads, writes, or deletes.

    Uses the same extraction as the matchers, so a per-repo override sees exactly
    the paths that triggered the deny.
    """
    reads, writes = _redirect_targets(command)
    paths = _bash_candidates(command, cwd, _READ_COMMANDS, allow_missing=False)
    paths.extend(_bash_candidates(command, cwd, _WRITE_COMMANDS, allow_missing=True))
    paths.extend(_bash_candidates(command, cwd, _DELETE_COMMANDS, allow_missing=True))
    paths.extend(reads)
    paths.extend(writes)
    paths.extend(_python_open_paths(command))
    return paths


def matches_read_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])
    ignore_case = _rule_ignore_case(rule)

    if tool_name == "Read":
        fp = tool_input.get("file_path", "")
        return _any_path_matches([fp], rule_paths, repo_root, cwd, ignore_case)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates = _bash_candidates(command, cwd, _READ_COMMANDS, allow_missing=False)
        candidates.extend(_redirect_targets(command)[0])
        # Scan the unstripped command: a Python heredoc can open files too.
        candidates.extend(_python_open_paths(command))
        return _any_path_matches(candidates, rule_paths, repo_root, cwd, ignore_case)

    return False


def matches_write_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])
    ignore_case = _rule_ignore_case(rule)

    if tool_name in ("Edit", "Write"):
        fp = tool_input.get("file_path", "")
        return _any_path_matches([fp], rule_paths, repo_root, cwd, ignore_case)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        candidates = _bash_candidates(command, cwd, _WRITE_COMMANDS, allow_missing=True)
        candidates.extend(_redirect_targets(command)[1])
        return _any_path_matches(candidates, rule_paths, repo_root, cwd, ignore_case)

    return False


def matches_write_content(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    """Match writes to specific file paths whose content matches forbidden patterns.

    Rule format:
        {
            "operation": "write-content",
            "paths": ["**/package.json", "**/pyproject.toml"],
            "content_patterns": ["\"latest\"", "\"\\*\""],
            "action": "deny",
            "reason": "..."
        }

    Matches when BOTH the file path matches AND any content pattern is found.
    Checks Write (full content) and Edit (new_string only) tool calls.
    """
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])
    content_patterns = rule.get("content_patterns", [])

    if tool_name == "Write":
        fp = tool_input.get("file_path", "")
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        fp = tool_input.get("file_path", "")
        content = tool_input.get("new_string", "")
    else:
        return False

    if not _any_path_matches([fp], rule_paths, repo_root, cwd, _rule_ignore_case(rule)):
        return False

    for pattern in content_patterns:
        if re.search(pattern, content):
            return True

    return False


def matches_delete_path(payload: dict, rule: dict, repo_root: str | None, cwd: str) -> bool:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    rule_paths = rule.get("paths", [])

    if tool_name != "Bash":
        return False

    command = tool_input.get("command", "")
    candidates = _bash_candidates(command, cwd, _DELETE_COMMANDS, allow_missing=True)
    return _any_path_matches(candidates, rule_paths, repo_root, cwd, _rule_ignore_case(rule))
