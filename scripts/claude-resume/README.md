# claude-resume

Interactive session picker for Claude Code. Browse, search, and resume past sessions with useful context — not just the last message.

## Why

Claude Code's built-in `/resume` often resumes the most recent session without offering a choice, and when it does show a list, the session descriptions aren't very helpful for remembering what you were working on.

This script gives you an fzf-powered picker with:

- **Full-text search** across all your conversation text (type to filter)
- **Substantive snippets** in the list (skips skill preambles, image refs, system noise)
- **Preview pane** with metadata and conversation highlights
- **Caching** so subsequent runs are fast (only re-parses changed sessions)

## Requirements

- `python3`
- `fzf`
- `claude` CLI

## Installation

Symlink or alias it:

```bash
# Option A: symlink to PATH
ln -s "$(pwd)/claude-resume.sh" ~/.local/bin/claude-resume

# Option B: alias in .zshrc
alias claude-resume="/path/to/scripts/claude-resume/claude-resume.sh"
```

## Usage

```
claude-resume                  # Interactive picker
claude-resume frontend         # Filter to projects matching "frontend"
claude-resume --all            # Include empty/aborted sessions
claude-resume --list           # Non-interactive list (pipe-friendly)
claude-resume --no-cache       # Force full re-parse
```

### In the picker

- **Type** to fuzzy-search across all conversation text (not just what's visible)
- **Arrow keys** to navigate
- **Enter** to resume the selected session
- **Esc** to cancel
- **Preview pane** (right side) shows full metadata and conversation highlights

## How it works

1. Scans `~/.claude/projects/*/` for session JSONL files
2. Extracts metadata (title, branch, timestamps, client) and all user messages
3. Filters out noise (system tags, skill preambles, image-only messages, interrupts)
4. Caches results in `~/.claude/cache/claude-resume-cache.json` (keyed by file mtime + size)
5. Presents sessions in fzf with a hidden search corpus field for full-text matching
6. Resumes the selected session via `claude --resume <session-id>`
