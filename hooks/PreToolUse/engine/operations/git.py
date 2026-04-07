"""Git operation handlers: git-force-push, git-reset-hard, git-push-direct."""

from __future__ import annotations

import re
import subprocess
from fnmatch import fnmatch

from operations.common import _command, _is_bash, _split_subcommands


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


def _extract_git_cwd(tokens: list[str]) -> str | None:
    """Extract working directory from -C flag, e.g. git -C /path push ..."""
    i = 1
    while i < len(tokens):
        if tokens[i] == "-C" and i + 1 < len(tokens):
            return tokens[i + 1]
        if tokens[i].startswith("-") and not tokens[i].startswith("--"):
            i += 1
            continue
        break
    return None


def _extract_push_remote(tokens: list[str]) -> str | None:
    """Extract the remote name from push tokens (first positional arg after 'push')."""
    push_idx = next((i for i, t in enumerate(tokens) if t == "push"), None)
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
    return positional[0] if positional else None


def _remote_is_empty(remote: str, cwd: str | None) -> bool:
    """Return True if the remote has no refs (initial push to empty repo)."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", remote],
            cwd=cwd,
            capture_output=True,
            timeout=5,
        )
        # exit code 2 means no matching refs; empty stdout also means no refs
        return result.returncode == 2 or result.stdout.strip() == b""
    except Exception:
        return False


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
            # Only deny when we can positively identify the branch as denied.
            # branch=None means no explicit branch (pushes tracking branch) —
            # we can't confirm it's main, so don't assume the worst.
            if branch is not None and _branch_matches_any(branch, deny_branches):
                return True

        if allow_branches:
            # Wildcard: * means "any branch" — allow even when branch is
            # unspecified (tracking branch push), since deny already had
            # its chance to match on known-bad branches.
            if branch is None and "*" in allow_branches:
                return True
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
        for tok in tokens[reset_idx + 1 :]:
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

        if not _branch_matches_any(branch, deny_branches):
            continue

        # Allow initial pushes to empty remotes — no history to protect
        remote = _extract_push_remote(tokens)
        cwd = _extract_git_cwd(tokens)
        if remote and _remote_is_empty(remote, cwd):
            continue

        return True

    return False
