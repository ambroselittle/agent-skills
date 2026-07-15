"""Tests for the MessageDisplay phrase-swap engine."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK_DIR = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = HOOK_DIR / "swap.py"
sys.path.insert(0, str(HOOK_DIR))

import swap  # noqa: E402

RULES = swap.compile_rules({"load-bearing": "important", "you're absolutely right": "you're right"})


def apply(text: str) -> str:
    """Swap a whole delta with the default test rules, starting outside a fence."""
    swapped, _ = swap.swap_delta(text, RULES, in_fence=False)
    return swapped


# --------------------------------------------------------------------------- #
# Phrase matching                                                             #
# --------------------------------------------------------------------------- #


def test_swaps_a_phrase():
    assert apply("That line is load-bearing.") == "That line is important."


def test_matches_across_hyphen_or_space():
    assert apply("that call is load bearing here") == "that call is important here"


def test_matches_curly_apostrophe():
    assert apply("You’re absolutely right.") == "You’re right."


def test_is_case_insensitive_when_matching():
    assert apply("LOAD-BEARING assumption") == "IMPORTANT assumption"


def test_preserves_leading_capital():
    assert apply("Load-bearing, that one.") == "Important, that one."


def test_lowercase_stays_lowercase():
    assert apply("a load-bearing wall") == "a important wall"


def test_respects_word_boundaries():
    assert apply("preload-bearingish") == "preload-bearingish"


def test_leaves_unmatched_text_alone():
    text = "Nothing to see here."
    assert apply(text) == text


def test_longest_phrase_wins():
    rules = swap.compile_rules(
        {"absolutely right": "right", "you're absolutely right": "you're right"}
    )
    swapped, _ = swap.swap_delta("You're absolutely right.", rules, in_fence=False)
    assert swapped == "You're right."


def test_replacement_is_not_rescanned():
    rules = swap.compile_rules({"a": "b", "b": "c"})
    swapped, _ = swap.swap_delta("a", rules, in_fence=False)
    assert swapped == "b"


# --------------------------------------------------------------------------- #
# Code protection — a swapped word inside code would be a lie the user copies  #
# --------------------------------------------------------------------------- #


def test_skips_inline_code():
    assert (
        apply("the `load-bearing` flag is load-bearing") == "the `load-bearing` flag is important"
    )


def test_skips_fenced_block_within_one_delta():
    text = "load-bearing prose\n```\nload-bearing code\n```\nload-bearing prose\n"
    assert apply(text) == "important prose\n```\nload-bearing code\n```\nimportant prose\n"


def test_fence_state_carries_across_deltas():
    first, in_fence = swap.swap_delta("```py\n", RULES, in_fence=False)
    assert in_fence is True
    second, in_fence = swap.swap_delta("x = 'load-bearing'\n", RULES, in_fence=in_fence)
    assert second == "x = 'load-bearing'\n"
    third, in_fence = swap.swap_delta("```\nload-bearing\n", RULES, in_fence=in_fence)
    assert in_fence is False
    assert third == "```\nimportant\n"


def test_tilde_fences_are_honored():
    text = "~~~\nload-bearing\n~~~\nload-bearing\n"
    assert apply(text) == "~~~\nload-bearing\n~~~\nimportant\n"


def test_preserves_missing_trailing_newline():
    assert apply("load-bearing") == "important"
    assert apply("load-bearing\n") == "important\n"


# --------------------------------------------------------------------------- #
# Config loading                                                              #
# --------------------------------------------------------------------------- #


def test_comment_keys_are_ignored():
    rules = swap.compile_rules({"// note": "ignored", "load-bearing": "important"})
    assert len(rules) == 1


def test_null_disables_a_phrase():
    merged = swap.merge_swaps({"load-bearing": "important"}, {"load-bearing": None})
    assert merged == {}


def test_local_overlay_overrides_and_extends():
    merged = swap.merge_swaps(
        {"load-bearing": "important"}, {"load-bearing": "critical", "seam": "boundary"}
    )
    assert merged == {"load-bearing": "critical", "seam": "boundary"}


def test_shipped_phrases_file_is_valid():
    swaps = swap.load_swaps(swap.PHRASES_FILE, local_path=Path("/nonexistent"))
    assert swaps, "shipped phrases.json should define at least one swap"
    assert swap.compile_rules(swaps)


# --------------------------------------------------------------------------- #
# End-to-end through the hook contract                                        #
# --------------------------------------------------------------------------- #


@pytest.fixture
def hook(tmp_path):
    """Run the hook as Claude Code does — JSON on stdin, JSON on stdout.

    HOME and TMPDIR are redirected into the tmp dir so a personal
    local-phrases.json can't change what these tests see, and so fence state
    lands somewhere disposable.
    """

    def run(delta: str, *, index: int = 0, final: bool = True, message_id: str = "m", **kw):
        payload = {
            "hook_event_name": "MessageDisplay",
            "messageId": message_id,
            "index": index,
            "final": final,
            "delta": delta,
            **kw,
        }
        proc = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
            env={"HOME": str(tmp_path), "TMPDIR": str(tmp_path), "PATH": "/usr/bin:/bin"},
        )
        return proc.stdout.strip()

    return run


def display_content(stdout: str) -> str:
    return json.loads(stdout)["hookSpecificOutput"]["displayContent"]


def test_hook_emits_display_content(hook):
    parsed = json.loads(hook("This is load-bearing."))
    assert parsed["hookSpecificOutput"] == {
        "hookEventName": "MessageDisplay",
        "displayContent": "This is important.",
    }


def test_hook_stays_silent_when_nothing_changes(hook):
    assert hook("nothing here") == ""


def test_hook_survives_garbage_input():
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input="not json",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_hook_tracks_fence_state_across_flushes(hook):
    assert hook("```\n", index=0, final=False) == ""
    assert hook("load-bearing\n", index=1, final=False) == ""  # inside the fence — untouched
    assert display_content(hook("```\nload-bearing\n", index=2)) == "```\nimportant\n"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
