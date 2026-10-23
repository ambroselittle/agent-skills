"""Read shared sources and all installed guidance without changing them."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def source_root() -> Path:
    installed = Path.home() / ".agent-skills/source"
    return installed.resolve() if installed.is_dir() else Path(__file__).resolve().parents[3]


def guidance_context(agent: str, path: Path) -> dict:
    content = path.read_text()
    lines = content.splitlines(keepends=True)
    stack = []
    fences = []
    for number, line in enumerate(lines, 1):
        opening = re.fullmatch(r"\s*<([a-zA-Z][a-zA-Z0-9_-]*)>\s*", line)
        closing = re.fullmatch(r"\s*</([a-zA-Z][a-zA-Z0-9_-]*)>\s*", line)
        if opening:
            stack.append((opening.group(1), number))
        elif closing and stack and closing.group(1) == stack[-1][0]:
            tag, start = stack.pop()
            fences.append({"tag": tag, "start_line": start, "end_line": number})
    # An incomplete managed fence is protected through EOF rather than writable.
    fences.extend({"tag": tag, "start_line": start, "end_line": len(lines)} for tag, start in stack)
    fences.sort(key=lambda fence: fence["start_line"])
    protected = {
        number for fence in fences for number in range(fence["start_line"], fence["end_line"] + 1)
    }
    ranges = []
    start = None
    for number in range(1, len(lines) + 2):
        unmanaged = number <= len(lines) and number not in protected
        if unmanaged and start is None:
            start = number
        elif not unmanaged and start is not None:
            ranges.append(
                {
                    "start_line": start,
                    "end_line": number - 1,
                    "content": "".join(lines[start - 1 : number - 1]),
                }
            )
            start = None
    return {
        "agent": agent,
        "path": str(path),
        "total_lines": len(lines),
        "fences": fences,
        "unmanaged_ranges": ranges,
        "full_content": content,
    }


def main() -> int:
    flag = sys.argv[1] if len(sys.argv) > 1 else "guidance"
    root = source_root()
    if flag in {"guidance", "claude-md"}:
        homes = {
            "claude": Path.home() / ".claude/CLAUDE.md",
            "codex": Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
            / "AGENTS.md",
        }
        if flag == "claude-md":
            homes = {"claude": homes["claude"]}
        records = [guidance_context(agent, path) for agent, path in homes.items() if path.is_file()]
        result = {"guidance": records}
    elif flag == "repo-rules":
        rules = []
        for path in sorted((root / ".claude/rules").glob("*.md")):
            content = path.read_text()
            paths = None
            match = re.match(r"^---\s*\npaths:\s*(\[.*?\])\s*\n---\s*\n", content, re.DOTALL)
            if match:
                try:
                    paths = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            rules.append({"file": str(path.relative_to(root)), "paths": paths, "content": content})
        result = {
            "repo": str(root),
            "rules": rules,
            "shared_template": (root / "templates/user-common.md").read_text().strip(),
            "integration_templates": {
                agent: (root / f"templates/user-{agent}.md").read_text().strip()
                for agent in ("claude", "codex")
            },
        }
    elif flag == "git-status":
        return subprocess.run(["git", "-C", str(root), "status", "--short"], check=False).returncode
    else:
        print("Usage: context.sh <guidance|repo-rules|git-status>", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
