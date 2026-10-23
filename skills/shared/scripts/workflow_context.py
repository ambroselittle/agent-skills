"""Portable workflow context and configuration, invoked by installed shell commands."""

from __future__ import annotations

import codecs
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]


def active_agent() -> str | None:
    explicit = os.environ.get("AGENT_SKILLS_HARNESS")
    if explicit:
        if explicit not in {"claude", "codex"}:
            raise ValueError("AGENT_SKILLS_HARNESS must be claude or codex")
        return explicit
    if os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return "claude"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    return None


def config_path() -> Path:
    override = os.environ.get("AGENT_SKILLS_CONFIG")
    if override:
        return Path(override).expanduser()
    shared = Path.home() / ".agent-skills/config.json"
    if shared.exists():
        return shared
    legacy = Path.home() / ".claude/agent-skills.json"
    return legacy if legacy.exists() else shared


def raw_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a configuration object in {path}")
    return value


def merge(base: dict, overlay: dict) -> dict:
    result = base.copy()
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def config() -> dict:
    value = raw_config()
    agent = active_agent()
    agents = value.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("Expected an object for agents")
    overrides = agents.get(agent, {}) if agent else {}
    if not isinstance(overrides, dict):
        raise ValueError(f"Expected an object for agents.{agent}")
    return merge(value, overrides)


def set_config(args: list[str]) -> None:
    common_only = bool(args and args[0] == "--shared")
    if common_only:
        args = args[1:]
    if len(args) < 2:
        raise ValueError("config-set requires key components followed by a JSON value")
    *keys, encoded = args
    value = json.loads(encoded)
    data = raw_config()
    destination = data
    agent = active_agent()
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise ValueError("Expected an object for agents")
    overrides = agents.get(agent, {}) if agent else {}
    if not isinstance(overrides, dict):
        raise ValueError(f"Expected an object for agents.{agent}")
    if not common_only and keys[0] in overrides:
        destination = overrides
    for key in keys[:-1]:
        child = destination.setdefault(key, {})
        if not isinstance(child, dict):
            raise ValueError(f"Cannot store a child value below non-object key {key}")
        destination = child
    destination[keys[-1]] = value
    # Reuse the installer's atomic write and symlink-referent preservation.
    sys.path.insert(0, str(SKILLS.parent / "scripts"))
    from setup_config import save_json

    save_json(config_path(), data)


def command(*args: str, required: bool = False, strip_output: bool = True) -> str:
    result = subprocess.run(args, text=True, capture_output=True)
    if required and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(args)}")
    if result.returncode:
        return ""
    return result.stdout.strip() if strip_output else result.stdout


def branch() -> str:
    return command("git", "branch", "--show-current")


def work_folder() -> str:
    root = config().get("work_root")
    if not root:
        return "needs-setup"
    current = branch()
    if current in {"", "main", "master"}:
        return "none"
    root = Path(root).expanduser()
    slug = current.partition("/")[2] or current
    ticket = re.search(r"[a-z]+-\d+", slug, re.IGNORECASE)
    if ticket and root.is_dir():
        token = ticket.group().lower()
        matches = sorted(
            p for p in root.iterdir() if p.is_dir() and p.name.lower().startswith(token + "-")
        )
        if not matches:
            matches = sorted(p for p in root.iterdir() if p.is_dir() and p.name.lower() == token)
        if matches:
            return str(matches[0])
    return str(root / slug)


def reviewer_files(skill: str) -> dict[str, Path]:
    group = "reviewers" if skill == "code-review" else "plan-reviewers"
    files: dict[str, Path] = {}
    # Later entries override earlier ones by exact slug; each reviewer runs once.
    for directory in (
        SKILLS / skill / "agents",
        Path(".claude/agents") / group,
        Path(".agents") / group,
    ):
        for path in sorted(directory.glob("*.md")):
            files[path.stem] = path
    return files


def reviewers(skill: str) -> None:
    groups: dict[str, list[str]] = {"always-on": [], "selectable": []}
    for name, path in sorted(reviewer_files(skill).items()):
        always = re.search(r"^always:\s*true\s*$", path.read_text(), re.MULTILINE)
        groups["always-on" if always else "selectable"].append(name)
    for name, members in groups.items():
        print(f"{name}: {' '.join(members)}")


def decode_git_path(value: str) -> str:
    """Decode Git's C-quoted UTF-8 path representation, leaving plain paths intact."""
    if value.startswith('"') and value.endswith('"'):
        raw, _ = codecs.escape_decode(value[1:-1].encode("utf-8"))
        return os.fsdecode(raw)
    return value


def block_path(block: str) -> str:
    lines = block.splitlines()
    for line in lines[1:]:
        if line.startswith("+++ ") and line != "+++ /dev/null":
            return decode_git_path(line[4:]).removeprefix("b/")
        if line.startswith("rename to "):
            return decode_git_path(line[len("rename to ") :])
    # Deletions have no destination file. Match their original path instead.
    for line in lines[1:]:
        if line.startswith("--- "):
            return decode_git_path(line[4:]).removeprefix("a/")
    quoted = re.fullmatch(r'diff --git "(?:\\.|[^"\\])*" ("(?:\\.|[^"\\])*")', lines[0])
    if quoted:
        return decode_git_path(quoted.group(1)).removeprefix("b/")
    return lines[0].rsplit(" b/", 1)[-1]


def diff(args: list[str], reverse: bool) -> str:
    pr = ""
    since = ""
    files = []
    while args:
        argument, *args = args
        if argument in {"--pr", "--since"}:
            if not args:
                raise ValueError(f"Missing value for {argument}")
            value, *args = args
            if argument == "--pr":
                pr = value
            else:
                since = value
        else:
            files.append(argument)
    if since:
        raw_names = command(
            "git", "diff", "--name-only", "-z", f"{since}..HEAD", required=True, strip_output=False
        )
        files = [name for name in raw_names.split("\0") if name]
        if not files:
            return ""
    if not pr:
        pr = command("gh", "pr", "view", "--json", "number", "--jq", ".number")
    if pr:
        raw = command("gh", "pr", "diff", pr, required=True)
    else:
        command("git", "fetch", "origin", "main", required=True)
        base = command("git", "merge-base", "HEAD", "origin/main", required=True)
        raw = command("git", "diff", f"{base}...HEAD", required=True)
    blocks = re.split(r"(?=^diff --git )", raw, flags=re.MULTILINE)
    blocks = [block for block in blocks if block.strip()]
    if files:
        wanted = set(files)
        selected = []
        for block in blocks:
            if block_path(block) in wanted:
                selected.append(block)
        blocks = selected
    if reverse:
        blocks.reverse()
    return "".join(block if block.endswith("\n") else block + "\n" for block in blocks)


def shared(flag: str, args: list[str]) -> None:
    if flag == "current-branch":
        print(branch() or "not in a git repo")
    elif flag == "open-pr":
        raw = command("gh", "pr", "view", "--json", "number,url,title")
        value = json.loads(raw) if raw else {}
        print(f"{value['number']}: {value['title']} — {value['url']}" if value else "none")
    elif flag == "user-slug":
        value = config().get("user_prefix")
        legacy = Path.home() / ".claude/user-slug"
        if not value and legacy.exists():
            value = legacy.read_text().strip()
        if not value:
            name = command("git", "config", "user.name").split()
            value = name[0].lower() if name else "unknown"
        print(value)
    elif flag == "repo-remote":
        remote = command("git", "remote", "get-url", "origin")
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
        print(match.group(1) if match else remote or "unknown")
    elif flag == "uncommitted-changes":
        print(command("git", "status", "--short") or "clean")
    elif flag == "head-sha":
        print(command("git", "rev-parse", "--short", "HEAD") or "unknown")
    elif flag == "recent-commits":
        print(command("git", "log", "--oneline", "-5") or "no commits")
    elif flag == "work-folder":
        print(work_folder())
    elif flag == "ticket-id":
        match = re.search(r"[a-z]+-\d+", branch().partition("/")[2] or branch(), re.IGNORECASE)
        print(match.group().upper() if match else "none")
    elif flag == "plans-in-progress":
        root = config().get("work_root")
        paths = sorted(Path(root).expanduser().glob("*/plan.md")) if root else []
        names = [path.parent.name for path in paths if not path.parent.name.startswith("done")]
        print(" ".join(names) or "none")
    elif flag == "unpushed":
        print(command("git", "log", "--oneline", "@{u}.."))
    elif flag == "pr-template":
        print("found" if Path(".github/pull_request_template.md").exists() else "none")
    elif flag == "config":
        print(json.dumps(config(), indent=2) if config_path().exists() else "needs-setup")
    elif flag == "config-path":
        print(config_path())
    elif flag == "config-set":
        set_config(args)
    elif flag == "project-instructions":
        for path in (Path("AGENTS.md"), Path("CLAUDE.md")):
            if path.is_file():
                print(path)
        for directory in (Path(".agents/rules"), Path(".claude/rules")):
            if directory.is_dir():
                print(directory)
    else:
        raise ValueError(f"Unknown shared context flag: {flag}")


def main() -> None:
    scope, flag, *args = sys.argv[1:]
    if scope == "shared":
        shared(flag, args)
    elif flag in {"reviewer-agents", "plan-reviewer-agents"}:
        reviewers(scope)
    elif scope == "code-review" and flag == "ci-status":
        print("YES" if os.environ.get("CI") == "true" else "no")
    elif scope == "code-review" and flag == "work-plan":
        directory = work_folder()
        path = Path(directory) / "plan.md"
        if directory not in {"none", "needs-setup"} and path.is_file():
            print("\n".join(path.read_text().splitlines()[:30]))
    elif scope == "code-review" and flag in {"diff", "reversed-diff"}:
        print(diff(args, reverse=flag == "reversed-diff"), end="")
    elif scope == "plan-work" and flag == "project-instructions":
        shared(flag, args)
    elif scope == "plan-work" and flag == "claude-md-exists":
        print("yes" if Path("CLAUDE.md").is_file() else "no")
    else:
        raise ValueError(f"Unknown context command: {scope} {flag}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Workflow context unavailable: {error}", file=sys.stderr)
        raise SystemExit(1) from error
