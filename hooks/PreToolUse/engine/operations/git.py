"""Git operation handlers: git-force-push, git-reset-hard, git-push-direct."""
import re
import shlex
from fnmatch import fnmatch
from pathlib import Path

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


def _is_git_subcommand(tokens: list[str], subcommand: str) -> bool:
    if not tokens or tokens[0] != "git":
        return False
    i = 1
    while i < len(tokens):
        if tokens[i] in ("-C", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if tokens[i].startswith("-"):
            i += 1
            continue
        return tokens[i] == subcommand
    return False


def _extract_push_branch(tokens: list[str]) -> str | None:
    push_idx = None
    for i, tok in enumerate(tokens):
        if tok == "push":
            push_idx = i
            break
    if push_idx is None:
        return None

    positional = []
    i = push_idx + 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--push-option", "-o", "--receive-pack", "--repo", "--signed"):
            i += 2
            continue
        if tok in ("--set-upstream", "-u", "--force-with-lease-ifvalue"):
            i += 1
            continue
        if tok.startswith("-"):
            i += 1
            continue
        positional.append(tok)
        i += 1

    if len(positional) < 2:
        return None

    refspec = positional[1]
    if ":" in refspec:
        refspec = refspec.split(":")[-1]
    refspec = re.sub(r"^refs/heads/", "", refspec)
    return refspec


def _is_force_flag(tokens: list[str]) -> bool:
    force_flags = {"--force", "-f", "--force-with-lease", "--force-if-includes"}
    for tok in tokens:
        if tok in force_flags:
            return True
        if tok.startswith("--force"):
            return True
    return False


def _branch_matches_any(branch: str, patterns: list[str]) -> bool:
    return any(fnmatch(branch, p) for p in patterns)


def matches_git_force_push(payload: dict, rule: dict) -> bool:
    if not _is_bash(payload):
        return False

    command = _command(payload)
    deny_branches = rule.get("deny-branches", [])
    allow_branches = rule.get("allow-branches", [])

    for tokens in _split_subcommands(command):
        if not _is_git_subcommand(tokens, "push"):
            continue
        if not _is_force_flag(tokens):
            continue

        branch = _extract_push_branch(tokens)

        if deny_branches:
            if branch is None:
                return True
            if _branch_matches_any(branch, deny_branches):
                return True

        if allow_branches:
            if branch is not None and _branch_matches_any(branch, allow_branches):
                return True

    return False


def matches_git_reset_hard(payload: dict, rule: dict) -> bool:
    if not _is_bash(payload):
        return False

    command = _command(payload)
    deny_targets = rule.get("deny-targets", [])
    allow_targets = rule.get("allow-targets", [])

    for tokens in _split_subcommands(command):
        if not _is_git_subcommand(tokens, "reset"):
            continue
        if "--hard" not in tokens:
            continue

        reset_idx = next((i for i, t in enumerate(tokens) if t == "reset"), None)
        if reset_idx is None:
            continue

        target = None
        for tok in tokens[reset_idx + 1:]:
            if not tok.startswith("-"):
                target = tok

        if deny_targets:
            if target is None:
                continue
            if _branch_matches_any(target, deny_targets):
                return True

        if allow_targets:
            if target is None:
                continue
            if _branch_matches_any(target, allow_targets):
                return True

    return False


def matches_git_push_direct(payload: dict, rule: dict) -> bool:
    if not _is_bash(payload):
        return False

    command = _command(payload)
    deny_branches = rule.get("deny-branches", [])

    if not deny_branches:
        return False

    for tokens in _split_subcommands(command):
        if not _is_git_subcommand(tokens, "push"):
            continue
        if _is_force_flag(tokens):
            continue

        branch = _extract_push_branch(tokens)
        if branch is None:
            continue

        if _branch_matches_any(branch, deny_branches):
            return True

    return False
