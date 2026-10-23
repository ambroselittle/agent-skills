"""Run the public installer with isolated homes, never the user's config."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def install(tmp_path):
    from test_setup_runtime import RuntimeSandbox
    from test_setup_sh import CLAUDE_SHIM, GH_SHIM

    sandbox = RuntimeSandbox(tmp_path)
    for name, body in (("claude", CLAUDE_SHIM), ("gh", GH_SHIM)):
        path = sandbox.bin / name
        path.unlink(missing_ok=True)
        path.write_text(body)
        path.chmod(0o755)
    sandbox.env.update(
        {
            "CLAUDE_SHIM_LOG": str(tmp_path / "claude-calls.log"),
            "CLAUDE_SHIM_MCP": str(tmp_path / "mcp.txt"),
        }
    )

    def run(*args, env_override=None):
        return sandbox.run(*args, env=env_override)

    return sandbox.home, sandbox.codex, run


def test_codex_install_is_standalone_and_preserves_hooks(install):
    home, codex, run = install
    codex.mkdir()
    other = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other-hook"}]}]}}
    (codex / "hooks.json").write_text(json.dumps(other))
    result = run("--target", "codex", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads((codex / "hooks.json").read_text())
    assert data["hooks"]["Stop"] == other["hooks"]["Stop"]
    assert "PreToolUse" in data["hooks"]
    assert not (home / ".claude").exists()
    assert "trusted_hash" not in (codex / "hooks.json").read_text()
    p = subprocess.run(
        ["python3", str(codex / "hooks/agent-skills-permission-request.py")],
        input=json.dumps(
            {
                "hook_event_name": "PermissionRequest",
                "tool_name": "Bash",
                "tool_input": {"command": "git fetch origin"},
                "cwd": str(home),
            }
        ),
        env={**os.environ, "HOME": str(home)},
        text=True,
        capture_output=True,
    )
    assert p.returncode == 0 and p.stdout == ""


def test_repeat_install_and_exclusion_are_idempotent(install):
    _, codex, run = install
    run("--target", "codex", "pretooluse")
    before = (codex / "hooks.json").read_text()
    run("--target", "codex", "pretooluse")
    assert (codex / "hooks.json").read_text() == before
    result = run("--target", "codex", "pretooluse", "--without", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (codex / "hooks/agent-skills-permission-request.py").exists()
    result = run("--target", "codex", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (codex / "hooks/agent-skills-permission-request.py").exists()


def test_dry_run_writes_nothing_including_exclusions(install):
    home, _, run = install
    result = run("--target", "both", "--dry-run", "pretooluse", "--without", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(home.iterdir()) == []
    assert "remove" in result.stdout


def test_bad_target_changes_nothing(install):
    home, _, run = install
    result = run("--target", "typo", "pretooluse")
    assert result.returncode != 0
    assert list(home.iterdir()) == []


def test_malformed_hooks_not_overwritten(install):
    _, codex, run = install
    codex.mkdir()
    (codex / "hooks.json").write_text("{broken")
    result = run("--target", "codex", "pretooluse")
    assert result.returncode != 0
    assert (codex / "hooks.json").read_text() == "{broken"


def test_skill_collision_is_preserved(install):
    home, _, run = install
    skill = home / ".agents/skills/author-e2e"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("User-owned skill")
    result = run("--target", "codex", "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (skill / "SKILL.md").read_text() == "User-owned skill"
    assert "left alone" in result.stdout


def test_existing_claude_exclusions_are_respected(install):
    home, _, run = install
    (home / ".claude").mkdir()
    (home / ".claude/agent-skills.json").write_text(
        json.dumps({"exclude": {"skills": ["author-e2e"]}})
    )
    result = run("--target", "codex", "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (home / ".agents/skills/author-e2e").exists()


def test_guidance_preserves_personal_text_and_has_no_claude_tools(install):
    _, codex, run = install
    codex.mkdir()
    (codex / "AGENTS.md").write_text("Keep my personal note.\n")
    result = run("--target", "codex", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    text = (codex / "AGENTS.md").read_text()
    assert "Keep my personal note." in text
    assert "Agent Skills" in text
    assert "via the Skill tool" not in text
    assert "CLAUDE_CODE_SESSION_ID" not in text
    result = run("--target", "codex", "guidance", "--without", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (codex / "AGENTS.md").read_text() == "Keep my personal note.\n"


def test_title_install_removes_retired_renderer_and_preserves_other_hooks(install):
    _, codex, run = install
    (codex / "hooks").mkdir(parents=True)
    renderer = codex / "hooks/codex_terminal.py"
    renderer.write_text("obsolete renderer")
    foreign = {"hooks": [{"type": "command", "command": "other-hook"}]}
    old = {"hooks": [{"type": "command", "command": f"python3 {renderer}"}]}
    (codex / "hooks.json").write_text(
        json.dumps(
            {"hooks": {"SessionStart": [old], "UserPromptSubmit": [old], "Stop": [foreign, old]}}
        )
    )
    result = run("--target", "codex", "window-title")
    assert result.returncode == 0, result.stderr
    before = (codex / "hooks.json").read_text()
    assert "codex_terminal.py" not in before
    cached_call = subprocess.run(
        ["python3", str(renderer)], input="{}", text=True, capture_output=True
    )
    assert cached_call.returncode == 0
    assert cached_call.stdout == cached_call.stderr == ""
    assert json.loads(before)["hooks"]["Stop"] == [foreign]
    assert run("--target", "codex", "window-title").returncode == 0
    assert (codex / "hooks.json").read_text() == before
    result = run("--target", "codex", "window-title", "--without", "window-title")
    assert result.returncode == 0, result.stderr
    assert json.loads((codex / "hooks.json").read_text())["hooks"]["Stop"] == [foreign]


def test_retired_title_commands_never_spawn_app_server_or_nudge(install):
    _, codex, run = install
    (codex / "hooks").mkdir(parents=True)
    command = f"AGENT_SKILLS_HARNESS=codex bash {codex / 'hooks/window-nudge.sh'}"
    old = {"hooks": [{"type": "command", "command": command}]}
    (codex / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [old], "UserPromptSubmit": [old]}})
    )
    result = run("--target", "codex", "window-title", "guidance")
    assert result.returncode == 0, result.stderr
    hooks = (codex / "hooks.json").read_text()
    assert "window-nudge.sh" not in hooks
    cli = subprocess.run(
        [str(codex / "scripts/window-title"), "set", "Kafka expansion readiness"],
        env={"PATH": "/nonexistent"},
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 0
    assert "retired" in cli.stdout and "/rename" in cli.stdout
    assert cli.stderr == ""
    hook = subprocess.run(
        ["/bin/sh", str(codex / "hooks/window-nudge.sh")],
        input='{"hook_event_name":"UserPromptSubmit"}',
        capture_output=True,
        text=True,
    )
    assert hook.returncode == 0 and hook.stdout == hook.stderr == ""
    guidance = (codex / "AGENTS.md").read_text()
    assert "as soon as the topic is" not in guidance
    assert "Ignore\nold cached reminders" in guidance


def test_full_both_install_has_exact_portable_skills_and_is_idempotent(install):
    home, codex, run = install
    result = run("--target", "both")
    assert result.returncode == 0, result.stdout + result.stderr
    catalog = json.loads((ROOT / "skills/compatibility.json").read_text())
    expected = {name for name, info in catalog.items() if "codex" in info["supportedAgents"]}
    assert {path.name for path in (home / ".agents/skills").iterdir()} == expected | {"shared"}
    assert {p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").exists()} == set(
        catalog
    )
    for name in expected:
        assert (home / ".agents/skills" / name).resolve() == ROOT / "skills" / name
    before = (codex / "AGENTS.md").read_text()
    assert run("--target", "both").returncode == 0
    assert (codex / "AGENTS.md").read_text() == before
    assert before.count("<agent-skills-guidance>") == 1


def test_plain_setup_refreshes_both_installed_guidance_blocks(install):
    home, codex, run = install
    assert run("--target", "both", "guidance").returncode == 0
    paths = (home / ".claude/CLAUDE.md", codex / "AGENTS.md")
    expected = [path.read_text() for path in paths]
    for path in paths:
        path.write_text(
            "Personal prefix.\n"
            + path.read_text().replace("## Use Agents", "## Stale guidance")
            + "Personal suffix.\n"
        )
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    for path, content in zip(paths, expected, strict=True):
        assert path.read_text() == "Personal prefix.\n" + content + "Personal suffix.\n"


def test_plain_setup_does_not_install_codex_on_a_claude_only_machine(install):
    home, codex, run = install
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (home / ".claude/CLAUDE.md").exists()
    assert not codex.exists()
    assert not (home / ".agents").exists()


def test_codex_refreshes_installed_claude_guidance_without_overwriting_notes(install):
    home, codex, run = install
    assert run("--target", "both", "guidance").returncode == 0
    path = home / ".claude/CLAUDE.md"
    expected = path.read_text()
    path.write_text(path.read_text().replace("## Use Agents", "## Stale guidance") + "My note.\n")
    result = run("--target", "codex", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_text() == expected + "My note.\n"


@pytest.mark.parametrize("cached", [False, True])
def test_both_agents_select_the_personal_template(install, cached):
    home, codex, run = install
    if cached:
        (home / ".claude").mkdir()
        (home / ".claude/agent-skills.json").write_text(
            json.dumps({"gh_username": "ambroselittle"})
        )
    result = run(
        "--target",
        "both",
        "guidance",
        env_override={"AGENT_SKILLS_USER": None if cached else "ambroselittle"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    personal = (ROOT / "templates/ambroselittle.md").read_text().strip()
    assert personal in (home / ".claude/CLAUDE.md").read_text()
    assert personal in (codex / "AGENTS.md").read_text()


def test_claude_dry_run_reports_exclusions_as_removals(install):
    home, _, run = install
    result = run("--target", "claude", "--dry-run", "guidance", "--without", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "remove guidance" in result.stdout
    assert list(home.iterdir()) == []


def test_policy_reconciles_missing_matcher_and_obsolete_modules(install):
    _, codex, run = install
    assert run("--target", "codex", "pretooluse").returncode == 0
    hooks_path = codex / "hooks.json"
    hooks = json.loads(hooks_path.read_text())
    hooks["hooks"].pop("PreToolUse")
    hooks_path.write_text(json.dumps(hooks))
    obsolete = codex / "hooks/agent-skills-policy/engine/obsolete.py"
    obsolete.write_text("obsolete")
    assert run("--target", "codex", "pretooluse").returncode == 0
    hooks = json.loads(hooks_path.read_text())
    assert "PreToolUse" in hooks["hooks"]
    assert "PermissionRequest" not in hooks["hooks"]
    assert not obsolete.exists()


@pytest.mark.parametrize("event", ["PreToolUse", "PermissionRequest"])
@pytest.mark.parametrize(
    "failure", ["overlay-json", "overlay-schema", "installed-rules", "private-deny"]
)
def test_installed_policy_entry_handles_private_rules_and_failures(install, event, failure):
    home, codex, run = install
    assert run("--target", "codex", "pretooluse").returncode == 0
    overlay = home / ".agent-skills/local-rules.json"
    overlay.parent.mkdir(exist_ok=True)
    if failure == "overlay-json":
        overlay.write_text("{broken")
    elif failure == "overlay-schema":
        overlay.write_text(json.dumps({"hooks": {"PreToolUse": {"rules": {}}}}))
    elif failure == "installed-rules":
        (codex / "hooks/agent-skills-policy/hook-rules.json").write_text("{broken")
    else:
        overlay.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": {
                            "rules": [
                                {
                                    "pattern": "sensitive-fixture-command",
                                    "action": "deny",
                                    "reason": "Private rule",
                                }
                            ]
                        }
                    }
                }
            )
        )
    result = subprocess.run(
        ["python3", str(codex / "hooks/agent-skills-permission-request.py")],
        input=json.dumps(
            {
                "hook_event_name": event,
                "tool_name": "Bash",
                "tool_input": {"command": "sensitive-fixture-command"},
                "cwd": str(home),
            }
        ),
        env={**os.environ, "HOME": str(home), "CODEX_HOME": str(codex)},
        capture_output=True,
        text=True,
    )
    if event == "PermissionRequest":
        assert result.returncode == 0 and result.stdout == result.stderr == ""
        return
    if failure == "private-deny":
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    else:
        assert result.returncode == 2
        assert result.stdout == ""
        assert "policy unavailable" in result.stderr
    log = (codex / "hooks/agent-skills-policy/codex-events.jsonl").read_text()
    assert "sensitive-fixture-command" not in log + result.stdout + result.stderr


def test_tilde_config_path_preserves_existing_guidance_exclusions(install):
    home, _, run = install
    config = home / ".claude/custom.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"exclude": {"guidance": ["personal"]}}))
    result = run(
        "guidance",
        env_override={
            "AGENT_SKILLS_CONFIG": "~/.claude/custom.json",
            "AGENT_SKILLS_USER": "ambroselittle",
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "# Personal Preferences" not in (home / ".claude/CLAUDE.md").read_text()


@pytest.mark.parametrize("target", ["claude", "codex", "both"])
def test_non_object_exclusions_keep_legacy_warning_behavior(install, target):
    home, _, run = install
    config = home / ".claude/agent-skills.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"exclude": ["hooks"]}))
    result = run("--target", target, "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "exclude" in result.stderr
