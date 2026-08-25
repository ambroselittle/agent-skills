"""End-to-end tests that run the real setup.sh against a throwaway HOME.

``claude`` and ``gh`` are shimmed on PATH so nothing touches the real CLI
config. Every run passes ``--no-clear`` so pytest's output survives.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SETUP = REPO / "setup.sh"

CLAUDE_SHIM = """#!/usr/bin/env bash
# Record every invocation; behave like a CLI with no servers registered.
printf '%s\\n' "$*" >> "$CLAUDE_SHIM_LOG"
case "$1 $2" in
  "mcp list") exit 0 ;;
  "mcp get") [[ -f "$CLAUDE_SHIM_MCP" ]] && cat "$CLAUDE_SHIM_MCP" && exit 0; exit 1 ;;
  "mcp add") exit 0 ;;
  "mcp remove") rm -f "$CLAUDE_SHIM_MCP"; exit 0 ;;
esac
exit 0
"""

GH_SHIM = """#!/usr/bin/env bash
[[ "$1 $2" == "api user" ]] && echo nobody-here
exit 0
"""


class Sandbox:
    def __init__(self, tmp_path: Path):
        self.home = tmp_path / "home"
        self.claude_dir = self.home / ".claude"
        self.claude_dir.mkdir(parents=True)
        self.config = self.claude_dir / "agent-skills.json"
        self.skills = self.claude_dir / "skills"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.shim_log = tmp_path / "claude-calls.log"
        self.shim_mcp = tmp_path / "claude-mcp-get.txt"
        for name, body in (("claude", CLAUDE_SHIM), ("gh", GH_SHIM)):
            shim = self.bin / name
            shim.write_text(body)
            shim.chmod(0o755)

    def write_config(self, data: dict) -> None:
        self.config.write_text(json.dumps(data, indent=2) + "\n")

    def read_config(self) -> dict:
        return json.loads(self.config.read_text())

    def run(self, *args: str) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "HOME": str(self.home),
            "AGENT_SKILLS_CONFIG": str(self.config),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "SHELL": "/bin/zsh",
            "CLAUDE_SHIM_LOG": str(self.shim_log),
            "CLAUDE_SHIM_MCP": str(self.shim_mcp),
        }
        return subprocess.run(
            ["bash", str(SETUP), *args, "--no-clear"],
            env=env,
            capture_output=True,
            text=True,
            cwd=REPO,
            check=False,
        )

    def claude_calls(self) -> list[str]:
        return self.shim_log.read_text().splitlines() if self.shim_log.exists() else []


@pytest.fixture
def box(tmp_path) -> Sandbox:
    return Sandbox(tmp_path)


# --------------------------------------------------------------------------- #
# --without persistence                                                       #
# --------------------------------------------------------------------------- #


def test_without_persists_to_config_and_reports_where(box):
    result = box.run("skills", "--without", "mcp")
    assert result.returncode == 0, result.stdout + result.stderr
    assert box.read_config()["exclude"] == {"mcp": ["all"]}
    assert "Persisting exclusions" in result.stdout
    assert str(box.config) in result.stdout


def test_without_is_idempotent_and_keeps_other_keys(box):
    box.write_config({"user_prefix": "me", "work_root": "/w"})
    box.run("skills", "--without", "pretooluse")
    first = box.config.read_text()
    result = box.run("skills", "--without", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    assert box.config.read_text() == first
    assert box.read_config() == {
        "user_prefix": "me",
        "work_root": "/w",
        "exclude": {"hooks": ["pretooluse"]},
    }


def test_without_still_rejects_unknown_names(box):
    result = box.run("skills", "--without", "widgets")
    assert result.returncode == 1
    assert "Unknown component" in result.stderr
    assert not box.config.exists()


def test_excluded_summary_is_shown(box):
    box.write_config({"exclude": {"skills": ["wtf"], "hooks": ["all"]}})
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Excluded" in result.stdout
    assert "hooks:all" in result.stdout
    assert "skills:wtf" in result.stdout


def test_malformed_config_does_not_abort(box):
    box.config.write_text("{oops")
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# skills reconciliation                                                       #
# --------------------------------------------------------------------------- #


def test_excluded_skill_symlink_into_repo_is_removed_but_foreign_link_survives(box, tmp_path):
    box.skills.mkdir()
    ours = box.skills / "wtf"
    ours.symlink_to(REPO / "skills" / "wtf")
    foreign_root = tmp_path / "org-skills" / "author-message"
    foreign_root.mkdir(parents=True)
    (foreign_root / "SKILL.md").write_text("---\nname: author-message\n---\n")
    foreign = box.skills / "author-message"
    foreign.symlink_to(foreign_root)

    box.write_config({"exclude": {"skills": ["wtf", "author-message"]}})
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr

    assert not ours.exists() and not ours.is_symlink()
    assert foreign.is_symlink() and foreign.resolve() == foreign_root.resolve()
    assert "removed wtf (excluded)" in result.stdout
    assert "author-message excluded, but" in result.stdout and "left alone" in result.stdout


def test_excluded_skill_is_not_linked_and_others_are(box):
    box.write_config({"exclude": {"skills": ["wtf"]}})
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (box.skills / "wtf").exists()
    assert (box.skills / "shared").is_symlink()
    assert (box.skills / "setup-agent-skills").is_symlink()


def test_un_excluding_relinks_on_next_run(box):
    box.write_config({"exclude": {"skills": ["wtf"]}})
    box.run("skills")
    assert not (box.skills / "wtf").exists()
    box.write_config({})
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (box.skills / "wtf").is_symlink()


def test_shared_cannot_be_excluded(box):
    box.write_config({"exclude": {"skills": ["shared"]}})
    result = box.run("skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (box.skills / "shared").is_symlink()
    assert '"shared" cannot be excluded' in result.stderr


# --------------------------------------------------------------------------- #
# mcp reconciliation                                                          #
# --------------------------------------------------------------------------- #


def test_excluded_mcp_server_with_our_command_is_removed(box):
    box.shim_mcp.write_text("playwright:\n  Command: npx\n  Args: @playwright/mcp@latest\n")
    box.write_config({"exclude": {"mcp": ["playwright"]}})
    result = box.run("mcp")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "mcp remove --scope user playwright" in box.claude_calls()
    assert "removed playwright (excluded)" in result.stdout


def test_excluded_mcp_server_with_foreign_command_is_left_alone(box):
    box.shim_mcp.write_text("playwright:\n  Command: my-own-server\n")
    box.write_config({"exclude": {"mcp": ["playwright"]}})
    result = box.run("mcp")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not any(call.startswith("mcp remove") for call in box.claude_calls())
    assert "left alone" in result.stdout


def test_excluded_mcp_server_is_not_registered(box):
    box.write_config({"exclude": {"mcp": ["all"]}})
    box.run("mcp")
    assert not any(call.startswith("mcp add") for call in box.claude_calls())


def test_mcp_server_is_registered_when_not_excluded(box):
    box.run("mcp")
    assert any(call.startswith("mcp add --scope user playwright") for call in box.claude_calls())


# --------------------------------------------------------------------------- #
# cli reconciliation                                                          #
# --------------------------------------------------------------------------- #


def test_cli_installs_link_and_alias_fence(box):
    rc = box.home / ".zshrc"
    rc.write_text("export A=1\n")
    result = box.run("cli")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (box.claude_dir / "scripts" / "claude-resume.sh").is_symlink()
    assert "# BEGIN agent-skills-aliases" in rc.read_text()
    assert 'alias reclaude="$HOME/.claude/scripts/claude-resume.sh"' in rc.read_text()


def test_excluded_cli_items_are_removed(box):
    rc = box.home / ".zshrc"
    rc.write_text("export A=1\n")
    box.run("cli")
    box.write_config({"exclude": {"cli": ["claude-resume", "reclaude"]}})
    result = box.run("cli")
    assert result.returncode == 0, result.stdout + result.stderr
    link = box.claude_dir / "scripts" / "claude-resume.sh"
    assert not link.exists() and not link.is_symlink()
    assert rc.read_text() == "export A=1\n"
    assert "removed claude-resume (excluded)" in result.stdout
    assert "Shell aliases removed" in result.stdout


def test_excluded_cli_leaves_foreign_link_alone(box, tmp_path):
    scripts = box.claude_dir / "scripts"
    scripts.mkdir()
    mine = tmp_path / "mine.sh"
    mine.write_text("#!/bin/sh\n")
    (scripts / "claude-resume.sh").symlink_to(mine)
    box.write_config({"exclude": {"cli": ["all"]}})
    result = box.run("cli")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (scripts / "claude-resume.sh").is_symlink()
    assert "not ours" in result.stdout


# --------------------------------------------------------------------------- #
# hooks reconciliation (settings.json-backed)                                 #
# --------------------------------------------------------------------------- #

IS_DARWIN = os.uname().sysname == "Darwin"


def hook_commands(settings: dict, event: str) -> list[str]:
    return [
        h["command"] for entry in settings.get("hooks", {}).get(event, []) for h in entry["hooks"]
    ]


def test_hooks_install_then_exclude_removes_only_the_excluded_ones(box):
    result = box.run("hooks")
    assert result.returncode == 0, result.stdout + result.stderr
    settings = json.loads((box.claude_dir / "settings.json").read_text())
    assert "~/.claude/hooks/message-display/swap.py" in hook_commands(settings, "MessageDisplay")
    assert "~/.claude/hooks/window-tag.sh" in hook_commands(settings, "Stop")
    assert settings["statusLine"]["command"] == "~/.claude/statusline.sh"
    assert settings["env"]["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"] == "1"
    assert "Bash(rsync *)" in settings["permissions"]["allow"]
    assert (box.claude_dir / "hooks" / "message-display" / "swap.py").exists()
    assert (box.claude_dir / "statusline.sh").exists()

    box.write_config({"exclude": {"hooks": ["message-display", "window-title"]}})
    result = box.run("hooks")
    assert result.returncode == 0, result.stdout + result.stderr
    settings = json.loads((box.claude_dir / "settings.json").read_text())

    assert "MessageDisplay" not in settings.get("hooks", {})
    for event in ("SessionStart", "UserPromptSubmit", "Stop"):
        assert "~/.claude/hooks/window-tag.sh" not in hook_commands(settings, event)
        assert "~/.claude/hooks/window-nudge.sh" not in hook_commands(settings, event)
    assert "statusLine" not in settings
    assert "env" not in settings
    assert not (box.claude_dir / "hooks" / "message-display").exists()
    for name in ("window-lib.sh", "window-tag.sh", "window-nudge.sh"):
        assert not (box.claude_dir / "hooks" / name).exists()
    assert not (box.claude_dir / "statusline.sh").exists()
    assert not (box.claude_dir / "scripts" / "window-title").exists()

    # pretooluse (and notification on macOS) are untouched.
    assert "~/.claude/hooks/pre-tool-use.sh" in hook_commands(settings, "PreToolUse")
    assert "Bash(rsync *)" in settings["permissions"]["allow"]
    assert (box.claude_dir / "hooks" / "pre-tool-use.sh").exists()
    if IS_DARWIN:
        assert "~/.claude/hooks/notify-attention.sh" in hook_commands(settings, "Notification")


def test_excluding_pretooluse_removes_engine_registration_and_permissions(box):
    box.run("pretooluse")
    box.write_config({"exclude": {"hooks": ["pretooluse"]}})
    result = box.run("pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    settings = json.loads((box.claude_dir / "settings.json").read_text())
    assert "PreToolUse" not in settings.get("hooks", {})
    assert "permissions" not in settings
    assert not (box.claude_dir / "hooks" / "pre-tool-use.sh").exists()
    assert not (box.claude_dir / "hooks" / "pre-tool-use").exists()


def test_excluding_every_hook_leaves_user_settings_untouched(box):
    (box.claude_dir / "settings.json").write_text(
        json.dumps({"model": "opus", "permissions": {"allow": ["Bash(git *)"]}}, indent=2) + "\n"
    )
    box.run("hooks")
    box.write_config({"exclude": {"hooks": ["all"]}})
    result = box.run("hooks")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((box.claude_dir / "settings.json").read_text()) == {
        "model": "opus",
        "permissions": {"allow": ["Bash(git *)"]},
    }


def test_bare_rerun_does_not_rewrite_settings(box):
    box.run("hooks", "attribution")
    before = (box.claude_dir / "settings.json").read_text()
    result = box.run("hooks", "attribution")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (box.claude_dir / "settings.json").read_text() == before


# --------------------------------------------------------------------------- #
# attribution / guidance reconciliation                                       #
# --------------------------------------------------------------------------- #


def test_attribution_is_per_key(box):
    box.run("attribution")
    settings = json.loads((box.claude_dir / "settings.json").read_text())
    assert settings["attribution"] == {"sessionUrl": False, "commit": "", "pr": ""}

    box.write_config({"exclude": {"attribution": ["commit"]}})
    result = box.run("attribution")
    assert result.returncode == 0, result.stdout + result.stderr
    settings = json.loads((box.claude_dir / "settings.json").read_text())
    assert settings["attribution"] == {"sessionUrl": False, "pr": ""}

    box.write_config({"exclude": {"attribution": ["all"]}})
    box.run("attribution")
    settings = json.loads((box.claude_dir / "settings.json").read_text())
    assert "attribution" not in settings


def test_guidance_core_excluded_removes_fence_and_keeps_user_text(box):
    md = box.claude_dir / "CLAUDE.md"
    md.write_text("My notes.\n")
    box.run("guidance")
    assert md.read_text().startswith("<agent-skills-guidance>\n")
    assert md.read_text().endswith("</agent-skills-guidance>\n\nMy notes.\n")

    box.write_config({"exclude": {"guidance": ["core"]}})
    result = box.run("guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert md.read_text() == "My notes.\n"


def test_guidance_personal_excluded_skips_personal_template(box):
    box.write_config({"exclude": {"guidance": ["personal"]}})
    result = box.run("guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Personal template excluded" in result.stdout
    assert (box.claude_dir / "CLAUDE.md").exists()
