#!/usr/bin/env zsh
# claude-resume: Browse and resume Claude Code sessions with useful context.
# Uses fzf for interactive selection. Requires: python3, fzf.
#
# Usage:
#   claude-resume                  # Interactive picker with full-text search
#   claude-resume --all            # Include empty/aborted sessions
#   claude-resume frontend         # Filter to projects matching "frontend"
#   claude-resume --list           # Non-interactive list (no fzf)
#   claude-resume --no-cache       # Force full re-parse (ignore cache)
#
# Installation:
#   1. Copy or symlink to somewhere on your PATH:
#        ln -s /path/to/claude-resume.sh ~/.local/bin/claude-resume
#      Or add an alias in .zshrc:
#        alias claude-resume="/path/to/claude-resume.sh"
#
#   2. Requires: python3, fzf, claude CLI

set -euo pipefail

SHOW_ALL=false
LIST_ONLY=false
NO_CACHE=false
FILTER=""

for arg in "$@"; do
  case "$arg" in
    --all)      SHOW_ALL=true ;;
    --list)     LIST_ONLY=true ;;
    --no-cache) NO_CACHE=true ;;
    *)          FILTER="$arg" ;;
  esac
done

export CR_FILTER="$FILTER"
export CR_SHOW_ALL="$SHOW_ALL"
export CR_NO_CACHE="$NO_CACHE"

# ── Extract and cache session data ──────────────────────────────────────────
build_index() {
  python3 << 'PYEOF'
import json, glob, os, re
from datetime import datetime
from pathlib import Path

projects_dir = os.path.expanduser("~/.claude/projects")
cache_dir = os.path.expanduser("~/.claude/cache")
cache_file = os.path.join(cache_dir, "claude-resume-cache.json")
index_file = os.path.join(cache_dir, "claude-resume-index.jsonl")
name_filter = os.environ.get("CR_FILTER", "").lower()
show_all = os.environ.get("CR_SHOW_ALL", "false") == "true"
no_cache = os.environ.get("CR_NO_CACHE", "false") == "true"

os.makedirs(cache_dir, exist_ok=True)

# Load existing cache
cache = {}
if not no_cache and os.path.exists(cache_file):
    try:
        with open(cache_file) as f:
            cache = json.load(f)
    except Exception:
        cache = {}

NOISE_PATTERNS = [
    re.compile(r'^\s*$'),
    re.compile(r'^<'),                              # system/IDE tags
    re.compile(r'^Base directory for this skill:'),  # skill preambles
    re.compile(r'^# /'),                             # slash command headers
    re.compile(r'^\[Request interrupted'),            # interrupt markers
]
IMAGE_RE = re.compile(r'\[Image[^]]*\]\s*')

def clean_text(text):
    """Strip image refs and noise, return cleaned text or empty string."""
    t = text.strip()
    for pat in NOISE_PATTERNS:
        if pat.match(t):
            return ""
    t = IMAGE_RE.sub('', t).strip()
    return t

def shorten_project_name(name):
    """Make project directory names more readable."""
    home = os.path.expanduser("~").replace("/", "-").lstrip("-")
    # Strip home directory prefix (e.g., "-Users-alittle-" -> "~/")
    if name.startswith(home):
        name = "~/" + name[len(home):].lstrip("-")
    # Collapse common path segments
    name = name.replace("-", "/")
    # Trim leading slashes
    name = name.lstrip("/")
    # Keep last 2-3 meaningful segments for readability
    parts = name.split("/")
    if len(parts) > 3:
        name = "/".join(parts[-3:])
    return name

def parse_session(jsonl_path):
    """Parse a session JSONL, return metadata + all substantive user text."""
    ai_title = ""
    git_branch = ""
    cwd = ""
    entrypoint = ""
    first_timestamp = ""
    last_timestamp = ""
    all_text_parts = []

    with open(jsonl_path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = d.get("type", "")

            if msg_type == "ai-title":
                ai_title = d.get("aiTitle", "")

            elif msg_type == "user":
                ts = d.get("timestamp", "")
                if not first_timestamp:
                    first_timestamp = ts
                    git_branch = d.get("gitBranch", "")
                    cwd = d.get("cwd", "")
                    entrypoint = d.get("entrypoint", "")
                last_timestamp = ts

                content = d.get("message", {}).get("content", [])
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        cleaned = clean_text(c["text"])
                        if cleaned:
                            all_text_parts.append(cleaned)

    if not first_timestamp:
        return None

    try:
        dt = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        date_str = first_timestamp[:16]

    try:
        dt_last = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
        last_str = dt_last.strftime("%Y-%m-%d %H:%M")
    except Exception:
        last_str = last_timestamp[:16]

    return {
        "title": ai_title,
        "branch": git_branch,
        "cwd": cwd,
        "entrypoint": entrypoint,
        "started": date_str,
        "last_active": last_str,
        "msg_count": len(all_text_parts),
        "all_text": all_text_parts,
    }

cache_dirty = False
results = []

for project_dir in sorted(glob.glob(os.path.join(projects_dir, "*/"))):
    project_name = os.path.basename(project_dir.rstrip("/"))

    if name_filter and name_filter not in project_name.lower():
        continue

    for jsonl_path in glob.glob(os.path.join(project_dir, "*.jsonl")):
        session_id = Path(jsonl_path).stem
        cache_key = jsonl_path

        try:
            file_mtime = os.path.getmtime(jsonl_path)
            file_size = os.path.getsize(jsonl_path)
        except Exception:
            continue

        cached = cache.get(cache_key)
        if cached and cached.get("mtime") == file_mtime and cached.get("size") == file_size:
            data = cached["data"]
        else:
            try:
                data = parse_session(jsonl_path)
            except Exception:
                continue
            cache[cache_key] = {"mtime": file_mtime, "size": file_size, "data": data}
            cache_dirty = True

        if data is None:
            continue

        if not show_all and data["msg_count"] == 0:
            continue

        data["session_id"] = session_id
        data["project"] = shorten_project_name(project_name)
        data["file_mtime"] = file_mtime
        results.append(data)

# Save cache
if cache_dirty:
    try:
        with open(cache_file, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass

# Sort by most recently modified
results.sort(key=lambda r: r.get("file_mtime", 0), reverse=True)

with open(index_file, "w") as out:
    for r in results:
        sid = r["session_id"]
        title = r["title"] or "(no title)"
        branch = r["branch"] or "?"
        texts = r.get("all_text", [])

        # Best snippet for display: longest message from the first 5
        display_snippet = ""
        for t in sorted(texts[:5], key=len, reverse=True):
            candidate = t.replace("\n", " ").strip()[:120]
            if len(candidate) > len(display_snippet):
                display_snippet = candidate

        display = (
            f'{r["last_active"]}  {r["project"]}  [{branch}]  '
            f'{title}  |  {display_snippet}  '
            f'[{r["msg_count"]} msgs]'
        )

        # Search corpus: all user text joined, truncated for fzf performance
        search_corpus = " ".join(t.replace("\n", " ") for t in texts)[:2000]

        out.write(f'{sid}\t{display}\t{search_corpus}\n')

        # Preview data
        preview_lines = [
            f'PREVIEW\t{sid}\tTitle:    {title}',
            f'PREVIEW\t{sid}\tProject:  {r["project"]}',
            f'PREVIEW\t{sid}\tBranch:   {r["branch"]}',
            f'PREVIEW\t{sid}\tCwd:      {r["cwd"]}',
            f'PREVIEW\t{sid}\tStarted:  {r["started"]} UTC',
            f'PREVIEW\t{sid}\tLast:     {r["last_active"]} UTC',
            f'PREVIEW\t{sid}\tClient:   {r["entrypoint"]}',
            f'PREVIEW\t{sid}\tMessages: {r["msg_count"]}',
            f'PREVIEW\t{sid}\t',
            f'PREVIEW\t{sid}\t── Conversation highlights ──',
        ]

        highlights = []
        if texts:
            highlights.append(texts[0][:300])
            if len(texts) >= 5:
                highlights.append(texts[len(texts) // 2][:300])
            if len(texts) >= 3:
                tail = texts[-5:]
                highlights.append(max(tail, key=len)[:300])

        labels = ["Start:", "Mid:", "Late:"]
        for i, h in enumerate(highlights):
            label = labels[i] if i < len(labels) else f"[{i}]:"
            h_clean = h.replace("\n", " ↵ ")
            preview_lines.append(f'PREVIEW\t{sid}\t  {label} {h_clean}')

        if not highlights:
            preview_lines.append(f'PREVIEW\t{sid}\t  (no substantive messages)')

        for pl in preview_lines:
            out.write(pl + "\n")

print(index_file)
PYEOF
}

# ── Build index ──────────────────────────────────────────────────────────────
INDEX_FILE=$(build_index)

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "Failed to build session index."
  exit 1
fi

# Preview helper script (external to avoid zsh escaping issues with fzf --preview)
PREVIEW_SCRIPT=$(mktemp /tmp/claude-resume-prev-XXXXXX)
trap "rm -f ${PREVIEW_SCRIPT}" EXIT

cat > "$PREVIEW_SCRIPT" << 'PREVIEW_EOF'
#!/usr/bin/env bash
line="$1"
datafile="$2"
sid=$(echo "$line" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
if [[ -n "$sid" ]]; then
  grep "^PREVIEW	${sid}	" "$datafile" | cut -f3-
fi
PREVIEW_EOF
chmod +x "$PREVIEW_SCRIPT"

SELECTABLE=$(grep -v '^PREVIEW' "$INDEX_FILE")

if [[ -z "$SELECTABLE" ]]; then
  echo "No sessions found${FILTER:+ matching \"$FILTER\"}."
  [[ "$SHOW_ALL" == "false" ]] && echo "Try --all to include empty/aborted sessions."
  exit 1
fi

# ── List mode ────────────────────────────────────────────────────────────────
if [[ "$LIST_ONLY" == "true" ]]; then
  echo "$SELECTABLE" | cut -f2
  exit 0
fi

# ── Interactive fzf selection ────────────────────────────────────────────────
# fzf searches all fields (including hidden search corpus) but only displays field 2
SELECTED=$(echo "$SELECTABLE" | fzf \
  --no-sort \
  --reverse \
  --delimiter='\t' \
  --with-nth=2 \
  --height=80% \
  --header="Claude Code sessions  (type to search across all conversation text)" \
  --preview="bash ${PREVIEW_SCRIPT} {} ${INDEX_FILE}" \
  --preview-window=right:50%:wrap \
) || exit 0

SESSION_ID=$(echo "$SELECTED" | cut -f1)

if [[ -z "$SESSION_ID" ]]; then
  echo "Could not extract session ID."
  exit 1
fi

echo "Resuming session: ${SESSION_ID}"
command claude --resume "$SESSION_ID"
