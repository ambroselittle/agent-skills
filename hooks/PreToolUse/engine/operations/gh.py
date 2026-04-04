"""GitHub CLI operation handlers: gh-pr-merge, gh-api."""
import re
import shlex
from fnmatch import fnmatch

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


def _is_gh_command(tokens: list[str], *subcommands: str) -> bool:
    if not tokens or tokens[0] != "gh":
        return False
    for i, sub in enumerate(subcommands, start=1):
        if i >= len(tokens) or tokens[i] != sub:
            return False
    return True


def _get_flag_value(tokens: list[str], *flags: str) -> str | None:
    for i, tok in enumerate(tokens):
        if tok in flags and i + 1 < len(tokens):
            return tokens[i + 1]
        for flag in flags:
            if tok.startswith(f"{flag}="):
                return tok.split("=", 1)[1]
    return None


def matches_gh_pr_merge(payload: dict, rule: dict) -> bool:
    if not _is_bash(payload):
        return False

    command = _command(payload)
    deny_branches = rule.get("deny-base-branches", [])
    if not deny_branches:
        return False

    for tokens in _split_subcommands(command):
        if not _is_gh_command(tokens, "pr", "merge"):
            continue

        base_branch = _get_flag_value(tokens, "--base", "-B")

        if base_branch is None:
            return True

        if any(fnmatch(base_branch, p) for p in deny_branches):
            return True

    return False


def matches_gh_api(payload: dict, rule: dict) -> bool:
    if not _is_bash(payload):
        return False

    command = _command(payload)
    deny_methods = rule.get("deny-methods", [])
    deny_patterns = rule.get("deny-patterns", [])

    for tokens in _split_subcommands(command):
        if not _is_gh_command(tokens, "api"):
            continue

        if deny_methods:
            method = _get_flag_value(tokens, "--method", "-X")
            if method and method.upper() in [m.upper() for m in deny_methods]:
                return True

        if deny_patterns:
            api_idx = next((i for i, t in enumerate(tokens) if t == "api"), None)
            if api_idx is not None:
                url = None
                i = api_idx + 1
                while i < len(tokens):
                    tok = tokens[i]
                    if tok in ("--method", "-X", "--field", "-f", "--input",
                               "--header", "-H", "--paginate", "--preview",
                               "--cache", "--hostname", "--jq", "-q",
                               "--template", "-t", "--include", "-i"):
                        i += 2
                        continue
                    if tok.startswith("-"):
                        i += 1
                        continue
                    url = tok
                    break

                if url:
                    for pattern in deny_patterns:
                        if re.search(pattern, url):
                            return True

    return False
