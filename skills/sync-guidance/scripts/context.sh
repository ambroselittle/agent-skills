#!/bin/bash
# Pre-loads sync context: reads ~/.claude/CLAUDE.md and repo rules for the skill prompt

CLAUDE_MD="$HOME/.claude/CLAUDE.md"
REPO_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

case "$1" in
  claude-md)
    # Output the full CLAUDE.md with fence boundaries annotated as JSON
    if [ ! -f "$CLAUDE_MD" ]; then
      echo '{"error": "~/.claude/CLAUDE.md not found"}'
      exit 0
    fi
    python3 - "$CLAUDE_MD" <<'PYEOF'
import sys, json, re

path = sys.argv[1]
content = open(path).read()
lines = content.splitlines()

# Detect all fenced blocks — any <tag>...</tag> wrapping multiple lines
# Fence = opening tag on its own line, closing </tag> on its own line
fences = []
fence_stack = []
for i, line in enumerate(lines):
    open_match = re.match(r'^\s*<([a-zA-Z][a-zA-Z0-9_-]*)>\s*$', line)
    close_match = re.match(r'^\s*</([a-zA-Z][a-zA-Z0-9_-]*)>\s*$', line)
    if open_match:
        fence_stack.append((open_match.group(1), i))
    elif close_match and fence_stack:
        tag, start = fence_stack[-1]
        if tag == close_match.group(1):
            fence_stack.pop()
            fences.append({"tag": tag, "start_line": start + 1, "end_line": i + 1})

# Personal section = content after the last fence (or all content if no fences)
personal_start = 0
if fences:
    personal_start = max(f["end_line"] for f in fences)

personal_lines = lines[personal_start:]
# Strip leading blank lines
while personal_lines and not personal_lines[0].strip():
    personal_lines.pop(0)

print(json.dumps({
    "path": path,
    "total_lines": len(lines),
    "fences": fences,
    "personal_start_line": personal_start + 1,
    "personal_content": "\n".join(personal_lines),
    "full_content": content,
}))
PYEOF
    ;;

  repo-rules)
    # Output all rule files from .claude/rules/ as JSON
    python3 - "$REPO_DIR" <<'PYEOF'
import sys, json, os, re
from pathlib import Path

repo = Path(sys.argv[1])
rules_dir = repo / ".claude" / "rules"
templates_dir = repo / "templates"

rules = []
for f in sorted(rules_dir.glob("*.md")):
    content = f.read_text()
    # Extract paths frontmatter if present
    paths = None
    m = re.match(r'^---\s*\npaths:\s*(\[.*?\])\s*\n---\s*\n', content, re.DOTALL)
    if m:
        try:
            paths = json.loads(m.group(1))
        except Exception:
            pass
    rules.append({
        "file": str(f.relative_to(repo)),
        "paths": paths,
        "content": content,
    })

# Also include templates/user-claude.md as the shared base
user_template = templates_dir / "user-claude.md"
shared_content = user_template.read_text() if user_template.exists() else ""

print(json.dumps({
    "rules": rules,
    "shared_template": shared_content,
    "repo": str(repo),
}))
PYEOF
    ;;

  git-status)
    cd "$REPO_DIR" && git status --short 2>&1
    ;;

  *)
    echo "Usage: context.sh <claude-md|repo-rules|git-status>" >&2
    exit 1
    ;;
esac
