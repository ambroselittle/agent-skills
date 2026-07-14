#!/usr/bin/env python3
"""MessageDisplay hook — swap tired phrases out of Claude's on-screen text.

Claude Code fires MessageDisplay with each batch of newly completed lines while
an assistant message streams, and displays whatever the hook returns. The swap
is *display-only*: the stored transcript and the model's own context keep the
original wording, so this changes what you read, not what Claude thinks.

stdin:  {"messageId": ..., "index": 0, "final": false, "delta": "...", ...}
stdout: {"hookSpecificOutput": {"hookEventName": "MessageDisplay",
                                "displayContent": "..."}}

Emitting nothing leaves the delta as-is, so every failure path here is silent.

Unlike the other hooks in this repo there is no bash entry point: Claude Code
awaits this hook before painting each delta, and dropping the wrapper takes a
flush from ~50ms to ~36ms.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

HOOK_EVENT = "MessageDisplay"

PHRASES_FILE = Path(__file__).resolve().parent / "phrases.json"
LOCAL_PHRASES_FILE = Path.home() / ".agent-skills" / "local-phrases.json"

STATE_TTL_SECONDS = 3600

# A fence opener/closer per CommonMark: up to three spaces of indent, then ``` or ~~~.
FENCE_RE = re.compile(r"^ {0,3}(?:```|~~~)")
# Inline code spans, including the ``x`` form used to embed a literal backtick.
INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")
# Straight and curly apostrophes are interchangeable when matching a phrase.
APOSTROPHES = "'’"


# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #


def _read_swaps(path: Path) -> dict:
    """Read a phrases file. A missing or malformed file contributes nothing."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    swaps = data.get("swaps") if isinstance(data, dict) else None
    return swaps if isinstance(swaps, dict) else {}


def merge_swaps(base: dict, local: dict) -> dict:
    """Overlay personal swaps onto the shipped ones. A null value drops a phrase."""
    merged = dict(base)
    merged.update(local)
    return {
        phrase: replacement
        for phrase, replacement in merged.items()
        if replacement is not None and not phrase.startswith("//")
    }


def load_swaps(path: Path = PHRASES_FILE, local_path: Path = LOCAL_PHRASES_FILE) -> dict:
    return merge_swaps(_read_swaps(path), _read_swaps(local_path))


def _phrase_pattern(phrase: str) -> str:
    """Match a phrase across any run of spaces/hyphens, either apostrophe, any case."""
    words = [re.escape(word) for word in re.split(r"[\s\-]+", phrase.strip()) if word]
    pattern = r"[\s\-]+".join(words)
    pattern = re.sub(rf"[{APOSTROPHES}]", f"[{APOSTROPHES}]", pattern)
    return rf"\b{pattern}\b"


class Rules:
    """Every phrase as one alternation, matched in a single left-to-right pass.

    One pass is what keeps a replacement from being fed back through the other
    rules ('a' -> 'b' -> 'c'). Phrases are ordered longest-first so that at any
    given position the fullest phrase wins ("you're absolutely right" over
    "absolutely right").
    """

    def __init__(self, swaps: dict):
        ordered = sorted(
            (
                (phrase, replacement)
                for phrase, replacement in swaps.items()
                if phrase and not phrase.startswith("//") and isinstance(replacement, str)
            ),
            key=lambda item: len(item[0]),
            reverse=True,
        )
        self.replacements = [replacement for _, replacement in ordered]
        alternation = "|".join(
            f"(?P<p{i}>{_phrase_pattern(phrase)})" for i, (phrase, _) in enumerate(ordered)
        )
        self.pattern = re.compile(alternation, re.IGNORECASE) if alternation else None

    def __len__(self) -> int:
        return len(self.replacements)

    def apply(self, text: str) -> str:
        if self.pattern is None:
            return text
        return self.pattern.sub(self._replace, text)

    def _replace(self, match: re.Match) -> str:
        replacement = self.replacements[int(match.lastgroup[1:])]
        return _match_style(match.group(0), replacement)


def compile_rules(swaps: dict) -> Rules:
    return Rules(swaps)


# --------------------------------------------------------------------------- #
# Swapping                                                                    #
# --------------------------------------------------------------------------- #


def _match_style(matched: str, replacement: str) -> str:
    """Carry the matched text's capitalization and apostrophe style to the replacement."""
    if "’" in matched:
        replacement = replacement.replace("'", "’")
    if matched.isupper() and len(matched) > 1:
        return replacement.upper()
    if matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _swap_line(line: str, rules: Rules) -> str:
    """Swap prose while leaving inline code spans byte-for-byte intact."""
    out: list[str] = []
    cursor = 0
    for code in INLINE_CODE_RE.finditer(line):
        out.append(rules.apply(line[cursor : code.start()]))
        out.append(code.group(0))
        cursor = code.end()
    out.append(rules.apply(line[cursor:]))
    return "".join(out)


def swap_delta(delta: str, rules: Rules, in_fence: bool) -> tuple[str, bool]:
    """Swap phrases in one delta, skipping fenced code. Returns the new fence state.

    Code is never touched: a doctored command or identifier is one the user would
    copy and run.
    """
    out: list[str] = []
    for line in delta.splitlines(keepends=True):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
        elif in_fence:
            out.append(line)
        else:
            out.append(_swap_line(line, rules))
    return "".join(out), in_fence


# --------------------------------------------------------------------------- #
# Fence state — deltas are whole lines, but a code block spans several deltas  #
# --------------------------------------------------------------------------- #


def _state_dir() -> Path:
    return Path(tempfile.gettempdir()) / "claude-phrase-swap"


def _state_file(message_id: str) -> Path:
    return _state_dir() / re.sub(r"[^A-Za-z0-9_-]", "", message_id)[:64]


def read_fence_state(message_id: str, index: int) -> bool:
    """A message's first flush always starts outside a fence."""
    if index == 0 or not message_id:
        return False
    try:
        return _state_file(message_id).read_text() == "1"
    except OSError:
        return False


def write_fence_state(message_id: str, in_fence: bool, final: bool) -> None:
    if not message_id:
        return
    path = _state_file(message_id)
    try:
        if final:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("1" if in_fence else "0")
        _prune_state(path.parent)
    except OSError:
        pass


def _prune_state(directory: Path) -> None:
    """Drop state from messages that never reached their final flush."""
    cutoff = time.time() - STATE_TTL_SECONDS
    try:
        for entry in os.scandir(directory):
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                Path(entry.path).unlink(missing_ok=True)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    delta = payload.get("delta") or ""
    if not isinstance(delta, str):
        return 0

    message_id = str(payload.get("messageId") or "")
    index = payload.get("index") if isinstance(payload.get("index"), int) else 0
    final = bool(payload.get("final"))

    rules = compile_rules(load_swaps())
    if not rules:
        return 0

    in_fence = read_fence_state(message_id, index)
    swapped, in_fence = swap_delta(delta, rules, in_fence)
    write_fence_state(message_id, in_fence, final)

    # Silence means "display the original" — say nothing unless we changed something.
    if swapped != delta:
        json.dump(
            {"hookSpecificOutput": {"hookEventName": HOOK_EVENT, "displayContent": swapped}},
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — a display tweak must never break the display
        sys.exit(0)
