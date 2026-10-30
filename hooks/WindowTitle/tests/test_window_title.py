"""Exercise the Claude title CLI and reminder behavior."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]


@pytest.fixture
def session(tmp_path):
    harness = "claude"
    home = tmp_path / "home"
    directory = home / f".{harness}"
    (directory / "hooks").mkdir(parents=True)
    (directory / "scripts").mkdir()
    for filename in ("window-lib.sh", "window-nudge.sh"):
        shutil.copy2(SOURCE / filename, directory / "hooks" / filename)
    shutil.copy2(SOURCE / "window-title", directory / "scripts/window-title")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.jsonl"
    env = {
        **os.environ,
        "HOME": str(home),
        "AGENT_SKILLS_HARNESS": harness,
        "CLAUDE_CODE_SESSION_ID": "claude-test",
        "CODEX_THREAD_ID": "codex-test",
        "CODEX_HOME": str(home / ".codex"),
        "TERM": "xterm",
        "TITLE_CALLS": str(calls),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    if harness == "claude":
        env.pop("CODEX_THREAD_ID")
    env.pop("CI", None)
    transcript = home / ".claude/projects/test-project/claude-test.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)

    def cli(*args):
        return subprocess.run(
            ["bash", str(directory / "scripts/window-title"), *args],
            env=env,
            text=True,
            capture_output=True,
        )

    def hook(turn=1, event="UserPromptSubmit", source="startup"):
        transcript.write_text(
            "\n".join(
                json.dumps({"type": "user", "message": {"content": "hi"}}) for _ in range(turn)
            )
        )
        payload = {
            "session_id": f"{harness}-test",
            "hook_event_name": event,
            "source": source,
            "turn_id": f"turn-{turn}",
            "transcript_path": str(transcript),
        }
        return subprocess.run(
            ["bash", str(directory / "hooks/window-nudge.sh")],
            input=json.dumps(payload),
            env=env,
            text=True,
            capture_output=True,
        )

    return harness, directory, env, calls, cli, hook


def test_set_pin_unpin_show(session):
    _, _, _, _, cli, _ = session
    assert cli("set", "Shared agent setup").returncode == 0
    assert "Shared agent setup (auto)" in cli("show").stdout
    assert cli("pin", "PX-123 My title").returncode == 0
    assert "leaving it alone" in cli("set", "Something else").stdout
    assert "PX-123 My title (pinned)" in cli("show").stdout
    assert cli("unpin").returncode == 0
    assert cli("set", "New subject here").returncode == 0


def test_invalid_labels_do_not_call_renderer(session):
    _, _, _, calls, cli, _ = session
    for label in ("", "PX-123 work", "x" * 49):
        assert cli("set", label).returncode != 0
    assert not calls.exists()


def test_missing_title_nudges_then_backs_off(session):
    _, _, _, _, _, hook = session
    assert "no title yet" in hook(1).stdout
    for turn in range(2, 6):
        assert hook(turn).stdout == ""
    assert "no title yet" in hook(6).stdout


def test_stale_compacted_and_pinned(session):
    _, _, _, _, cli, hook = session
    hook(1)
    cli("set", "Shared agent setup")
    for turn in range(2, 11):
        assert hook(turn).stdout == ""
    assert "10 turns" in hook(11).stdout
    assert "compacted" in hook(11, "SessionStart", "compact").stdout
    cli("pin", "My label")
    assert hook(30).stdout == ""
    assert hook(30, "SessionStart", "compact").stdout == ""
