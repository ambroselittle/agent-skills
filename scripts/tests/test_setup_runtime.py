"""Public-entry regressions for shared installs, discovery, and versioned upgrades."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class RuntimeSandbox:
    """Keep discovery and interpreter selection independent of the host install."""

    def __init__(self, tmp_path):
        self.home = tmp_path / "home"
        self.home.mkdir()
        self.codex = tmp_path / "codex-home"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.apps = tmp_path / "applications"
        self.apps.mkdir()
        for name in (
            "bash",
            "dirname",
            "pwd",
            "readlink",
            "mkdir",
            "cp",
            "ln",
            "rm",
            "find",
            "cat",
            "awk",
            "sed",
            "tr",
            "head",
            "uname",
            "clear",
            "tee",
            "chmod",
            "touch",
            "sort",
            "grep",
            "cut",
            "date",
            "which",
            "wc",
            "tail",
            "basename",
            "jq",
        ):
            source = shutil.which(name)
            if source:
                (self.bin / name).symlink_to(source)
        (self.bin / "python3").symlink_to(sys.executable)
        self.command("git", "exit 1")
        self.command("gh", 'case "$*" in "api user") printf "nobody-here\\n";; esac')
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex),
            "PATH": str(self.bin),
            "AGENT_SKILLS_APPLICATION_DIRS": str(self.apps),
            "AGENT_SKILLS_USER": "test-user-no-template",
            "SHELL": "/bin/zsh",
            "TERM": "xterm",
        }
        self.env.pop("AGENT_SKILLS_CONFIG", None)
        self.env.pop("PYTHONPATH", None)

    def command(self, name, body="exit 0"):
        path = self.bin / name
        path.unlink(missing_ok=True)
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def legacy(self, agent, data):
        path = (
            self.home / ".claude/agent-skills.json"
            if agent == "claude"
            else self.codex / "agent-skills.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    def run(self, *args, env=None):
        current_env = self.env.copy()
        for key, value in (env or {}).items():
            if value is None:
                current_env.pop(key, None)
            else:
                current_env[key] = value
        return subprocess.run(
            ["/bin/bash", str(ROOT / "setup.sh"), *args, "--no-clear"],
            env=current_env,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    @property
    def shared(self):
        return self.home / ".agent-skills"


@pytest.fixture
def runtime_box(tmp_path):
    return RuntimeSandbox(tmp_path)


@pytest.mark.parametrize("agents", [("claude",), ("codex",), ("claude", "codex")])
def test_default_setup_detects_available_commands_and_installs_only_those_agents(
    runtime_box, agents
):
    for agent in agents:
        runtime_box.command(agent)
    result = runtime_box.run("guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.home / ".claude/CLAUDE.md").exists() == ("claude" in agents)
    assert (runtime_box.codex / "AGENTS.md").exists() == ("codex" in agents)


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_default_setup_detects_configured_agent_without_its_cli(runtime_box, agent):
    if agent == "claude":
        path = runtime_box.home / ".claude/settings.json"
        content = '{"model":"configured-model"}\n'
    else:
        path = runtime_box.codex / "config.toml"
        content = 'model = "configured-model"\n'
    path.parent.mkdir(parents=True)
    path.write_text(content)
    result = runtime_box.run("guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    guidance = (
        runtime_box.home / ".claude/CLAUDE.md"
        if agent == "claude"
        else runtime_box.codex / "AGENTS.md"
    )
    assert guidance.exists()
    assert path.read_text() == content


@pytest.mark.parametrize(
    ("application", "agent"), [("Claude.app", "claude"), ("Codex.app", "codex")]
)
def test_default_setup_detects_desktop_app_in_configurable_search_roots(
    runtime_box, tmp_path, application, agent
):
    alternate = tmp_path / "other-applications"
    executable = alternate / application / "Contents/MacOS" / application.removesuffix(".app")
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    result = runtime_box.run(
        "guidance",
        env={
            "AGENT_SKILLS_APPLICATION_DIRS": os.pathsep.join(
                (str(runtime_box.apps), str(alternate))
            )
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.home / ".claude/CLAUDE.md").exists() == (agent == "claude")
    assert (runtime_box.codex / "AGENTS.md").exists() == (agent == "codex")


def test_no_supported_agent_is_a_clear_no_mutation_outcome(runtime_box):
    # Empty directories are not evidence of a configured harness.
    (runtime_box.home / ".claude").mkdir()
    runtime_box.codex.mkdir()
    result = runtime_box.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no supported agents" in result.stdout.lower()
    assert list((runtime_box.home / ".claude").iterdir()) == []
    assert list(runtime_box.codex.iterdir()) == []
    assert not runtime_box.shared.exists()
    assert not (runtime_box.home / ".agents").exists()


def test_chatgpt_desktop_alone_does_not_install_a_codex_harness(runtime_box):
    executable = runtime_box.apps / "ChatGPT.app/Contents/MacOS/ChatGPT"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    result = runtime_box.run("guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no supported agents" in result.stdout.lower()
    assert list(runtime_box.home.iterdir()) == []
    assert not runtime_box.codex.exists()


def test_claude_guidance_uses_agent_override_and_preserves_shared_preferences(runtime_box):
    runtime_box.shared.mkdir()
    path = runtime_box.shared / "config.json"
    config = {
        "user": "base-user-with-no-template",
        "exclude": {"guidance": ["all"]},
        "unknown_base": {"keep": [1, 2]},
        "agents": {
            "claude": {
                "user": "ambroselittle",
                "exclude": {"guidance": []},
                "unknown_claude": "keep",
            }
        },
    }
    path.write_text(json.dumps(config))
    result = runtime_box.run("--target", "claude", "guidance", env={"AGENT_SKILLS_USER": ""})
    assert result.returncode == 0, result.stdout + result.stderr
    guidance = (runtime_box.home / ".claude/CLAUDE.md").read_text()
    assert (ROOT / "templates/ambroselittle.md").read_text().strip() in guidance
    assert json.loads(path.read_text()) == config


def test_claude_user_selection_updates_only_its_agent_override(runtime_box):
    runtime_box.shared.mkdir()
    path = runtime_box.shared / "config.json"
    config = {
        "user": "shared-user",
        "unknown_base": True,
        "agents": {
            "claude": {"unknown_claude": ["keep"]},
            "codex": {"user": "codex-user", "unknown_codex": "keep"},
        },
    }
    path.write_text(json.dumps(config))
    result = runtime_box.run(
        "--target", "claude", "guidance", env={"AGENT_SKILLS_USER": "ambroselittle"}
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected = {
        **config,
        "agents": {
            **config["agents"],
            "claude": {**config["agents"]["claude"], "user": "ambroselittle"},
        },
    }
    assert json.loads(path.read_text()) == expected


@pytest.mark.parametrize(
    ("common_hooks", "claude_hooks", "installed"),
    [(["pretooluse"], [], True), ([], ["pretooluse"], False)],
)
def test_claude_shell_components_use_effective_agent_exclusions_without_rewriting_config(
    runtime_box, common_hooks, claude_hooks, installed
):
    runtime_box.shared.mkdir()
    path = runtime_box.shared / "config.json"
    config = {
        "exclude": {"hooks": common_hooks},
        "unknown_base": {"keep": True},
        "agents": {
            "claude": {"exclude": {"hooks": claude_hooks}, "unknown_claude": ["keep"]},
            "codex": {"exclude": {"skills": ["author-e2e"]}, "unknown_codex": True},
        },
    }
    path.write_text(json.dumps(config))
    result = runtime_box.run("--target", "claude", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.home / ".claude/hooks/pre-tool-use.sh").exists() == installed
    assert json.loads(path.read_text()) == config


def test_explicit_target_can_install_without_detection(runtime_box):
    result = runtime_box.run("--target", "codex", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.codex / "AGENTS.md").exists()
    assert not (runtime_box.home / ".claude").exists()


def old_python(box):
    return box.command(
        "python3",
        'case "$1" in\n'
        '  --version|-V) printf "Python 3.11.9\\n"; exit 0;;\n'
        '  -c) printf "3.11.9\\n"; exit 0;;\n'
        'esac\nprintf "unsupported interpreter must not execute setup\\n" >&2\nexit 91',
    )


def test_python_312_is_required_before_any_installer_mutation(runtime_box):
    old_python(runtime_box)
    result = runtime_box.run("--target", "codex", "guidance")
    assert result.returncode != 0
    assert "3.12" in result.stdout + result.stderr
    assert not runtime_box.shared.exists()
    assert not runtime_box.codex.exists()


def test_versioned_python_is_selected_and_installed_hooks_use_it(runtime_box, tmp_path):
    old = old_python(runtime_box)
    selected = runtime_box.bin / "python3.12"
    selected.symlink_to(sys.executable)
    result = runtime_box.run("--target", "both", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    runtime = runtime_box.shared / "scripts/python"
    assert runtime.is_symlink()
    assert runtime.resolve() == Path(sys.executable).resolve()
    assert runtime.resolve() != old.resolve()
    data = json.loads((runtime_box.codex / "hooks.json").read_text())
    handlers = [hook for entry in data["hooks"]["PreToolUse"] for hook in entry["hooks"]]
    command = shlex.split(handlers[0]["command"])
    assert command[0] == str(runtime)
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force origin main"},
            "cwd": str(tmp_path),
        }
    )
    hook = subprocess.run(
        command, input=payload, env=runtime_box.env, text=True, capture_output=True
    )
    assert hook.returncode == 0, hook.stderr
    assert json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    claude_hook = runtime_box.home / ".claude/hooks/pre-tool-use.sh"
    hook = subprocess.run(
        ["/bin/bash", str(claude_hook)],
        input=payload,
        env=runtime_box.env,
        text=True,
        capture_output=True,
    )
    assert hook.returncode == 0, hook.stderr
    assert json.loads(hook.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_legacy_configs_migrate_once_preserving_unknown_values_and_codex_overrides(runtime_box):
    claude_data = {
        "work_root": "/base-work",
        "user_prefix": "base",
        "future-option": {"nested": [1, "two"]},
        "exclude": {"skills": ["author-message"]},
    }
    codex_data = {
        "work_root": "/codex-work",
        "future-codex-option": ["keep-me"],
        "exclude": {"skills": ["author-e2e"]},
    }
    claude = runtime_box.legacy("claude", claude_data)
    codex = runtime_box.legacy("codex", codex_data)
    originals = {path: path.read_bytes() for path in (claude, codex)}
    result = runtime_box.run("--target", "both", "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    config_path = runtime_box.shared / "config.json"
    config = json.loads(config_path.read_text())
    assert {key: config[key] for key in claude_data} == claude_data
    assert config["agents"]["codex"] == codex_data
    assert all(path.read_bytes() == content for path, content in originals.items())
    assert not (runtime_box.home / ".claude/skills/author-message").exists()
    assert not (runtime_box.home / ".agents/skills/author-e2e").exists()
    assert (runtime_box.home / ".agents/skills/author-message").is_symlink()
    state_path = runtime_box.shared / "state.json"
    assert json.loads(state_path.read_text())["version"] >= 1
    before = (config_path.read_bytes(), state_path.read_bytes())
    claude.write_text(json.dumps({"work_root": "/stale-legacy-edit"}))
    codex.write_text(json.dumps({"work_root": "/stale-codex-edit"}))
    result = runtime_box.run("--target", "both", "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (config_path.read_bytes(), state_path.read_bytes()) == before


def test_existing_canonical_config_wins_during_version_zero_migration(runtime_box):
    runtime_box.legacy("claude", {"work_root": "/legacy", "legacy_unknown": True})
    runtime_box.legacy("codex", {"user_prefix": "legacy-codex", "codex_unknown": [1]})
    runtime_box.shared.mkdir()
    canonical = runtime_box.shared / "config.json"
    canonical.write_text(
        json.dumps(
            {
                "work_root": "/canonical",
                "canonical_unknown": "keep",
                "agents": {"codex": {"user_prefix": "canonical-codex", "local_unknown": True}},
            }
        )
    )
    result = runtime_box.run("--target", "codex", "guidance")
    assert result.returncode == 0, result.stdout + result.stderr
    config = json.loads(canonical.read_text())
    assert config["work_root"] == "/canonical"
    assert config["legacy_unknown"] is True
    assert config["canonical_unknown"] == "keep"
    assert config["agents"]["codex"] == {
        "user_prefix": "canonical-codex",
        "codex_unknown": [1],
        "local_unknown": True,
        "user": runtime_box.env["AGENT_SKILLS_USER"],
    }


def test_explicit_config_override_receives_changes_without_creating_default_config(runtime_box):
    runtime_box.legacy("claude", {"exclude": {"guidance": ["all"]}})
    override = runtime_box.home / "explicit.json"
    override.write_text(json.dumps({"work_root": "/explicit", "unknown": {"kept": True}}))
    result = runtime_box.run(
        "--target",
        "codex",
        "guidance",
        "--without",
        "mcp",
        env={"AGENT_SKILLS_CONFIG": str(override)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.codex / "AGENTS.md").exists()
    config = json.loads(override.read_text())
    assert config["work_root"] == "/explicit" and config["unknown"] == {"kept": True}
    assert config.get("agents", {}).get("codex", {}).get("exclude", {}).get("mcp") == ["all"]
    assert not (runtime_box.shared / "config.json").exists()


@pytest.mark.parametrize("target", ["claude", "codex", "both"])
def test_canonical_sources_scripts_and_exact_supported_agent_skills(runtime_box, target):
    catalog = json.loads((ROOT / "skills/compatibility.json").read_text())
    sources = {path.name for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").is_file()}
    assert sources == set(catalog)
    for name, entry in catalog.items():
        assert isinstance(entry["supportedAgents"], list), name
        assert set(entry["supportedAgents"]) <= {"claude", "codex"}, name
        if name != "make-skill":
            assert set(entry["supportedAgents"]) == {"claude", "codex"}, name
    result = runtime_box.run("--target", target, "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runtime_box.shared / "source").is_symlink()
    assert (runtime_box.shared / "source").resolve() == ROOT
    for name in sources | {"shared"}:
        canonical = runtime_box.shared / "skills" / name
        assert canonical.is_symlink() and canonical.resolve() == ROOT / "skills" / name
        scripts = ROOT / "skills" / name / "scripts"
        if scripts.is_dir():
            alias = runtime_box.shared / "scripts" / name
            assert alias.is_symlink() and alias.resolve() == scripts
    for agent, destination in (
        ("claude", runtime_box.home / ".claude/skills"),
        ("codex", runtime_box.home / ".agents/skills"),
    ):
        if target not in (agent, "both"):
            assert not destination.exists()
            continue
        expected = {
            name for name, entry in catalog.items() if agent in entry["supportedAgents"]
        } | {"shared"}
        assert {path.name for path in destination.iterdir()} == expected
        for name in expected:
            assert Path(os.readlink(destination / name)) == runtime_box.shared / "skills" / name


def test_migration_removes_only_owned_approval_hooks_and_preserves_trust(runtime_box):
    runtime_box.codex.mkdir()
    entry = runtime_box.codex / "hooks/agent-skills-permission-request.py"
    owned = {
        "matcher": "^Bash$",
        "hooks": [{"type": "command", "command": f"python3 {entry}", "timeout": 10}],
    }
    other = {
        "matcher": "^Bash$",
        "hooks": [{"type": "command", "command": "other-policy", "timeout": 10}],
    }
    path = runtime_box.codex / "hooks.json"
    path.write_text(
        json.dumps(
            {
                "hooks": {"PermissionRequest": [owned, other], "Stop": [other]},
                "unrecognized_top_level": {"retain": True},
            }
        )
    )
    trust = runtime_box.codex / "hook-trust.json"
    trust.write_text('{"reviewed-hash":"unchanged"}\n')
    result = runtime_box.run("--target", "codex", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    hooks = json.loads(path.read_text())
    assert hooks["hooks"]["PermissionRequest"] == [other]
    assert hooks["hooks"]["Stop"] == [other]
    assert hooks["unrecognized_top_level"] == {"retain": True}
    assert trust.read_text() == '{"reviewed-hash":"unchanged"}\n'
    assert "PreToolUse" in hooks["hooks"]


def test_installed_codex_policy_leaves_native_approvals_untouched(runtime_box):
    result = runtime_box.run("--target", "codex", "pretooluse")
    assert result.returncode == 0, result.stdout + result.stderr
    hooks = json.loads((runtime_box.codex / "hooks.json").read_text())["hooks"]
    assert "PermissionRequest" not in hooks
    handler = hooks["PreToolUse"][0]["hooks"][0]
    command = shlex.split(handler["command"])
    overlay = runtime_box.shared / "local-rules.json"
    overlay.write_text(
        json.dumps(
            {"hooks": {"PreToolUse": {"rules": [{"pattern": "needs-review", "action": "ask"}]}}}
        )
    )
    for action in ("git fetch origin", "needs-review", "unknown-fixture-command"):
        result = subprocess.run(
            command,
            input=json.dumps(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": action},
                    "cwd": str(runtime_box.home),
                }
            ),
            env=runtime_box.env,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""


def test_worktree_upgrade_relinks_changed_primary_skill_and_preserves_foreign_skill(
    runtime_box, tmp_path
):
    primary = tmp_path / "primary-checkout"
    common_git = primary / ".git"
    common_git.mkdir(parents=True)
    primary_skill = primary / "skills/author-e2e"
    primary_skill.mkdir(parents=True)
    (primary_skill / "SKILL.md").write_text("Primary checkout's older skill.\n")
    foreign = tmp_path / "other-owner/author-message"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("Keep this independently managed skill.\n")
    destination = runtime_box.home / ".claude/skills"
    destination.mkdir(parents=True)
    legacy = destination / "author-e2e"
    legacy.symlink_to(primary_skill)
    foreign_link = destination / "author-message"
    foreign_link.symlink_to(foreign)
    runtime_box.command(
        "git",
        'case "$*" in\n'
        f"  *'rev-parse --git-common-dir') printf '%s\\n' {shlex.quote(str(common_git))};;\n"
        "  *'diff --name-only main... -- skills/') printf 'skills/author-e2e/SKILL.md\\n';;\n"
        "esac",
    )
    result = runtime_box.run("--target", "claude", "skills")
    assert result.returncode == 0, result.stdout + result.stderr
    canonical = runtime_box.shared / "skills/author-e2e"
    assert canonical.is_symlink() and canonical.resolve() == ROOT / "skills/author-e2e"
    assert legacy.is_symlink() and legacy.readlink() == canonical
    assert legacy.resolve() == ROOT / "skills/author-e2e"
    assert foreign_link.is_symlink() and foreign_link.readlink() == foreign
    assert (foreign_link / "SKILL.md").read_text() == "Keep this independently managed skill.\n"
