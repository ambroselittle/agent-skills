"""Exercise portable workflow entry points from isolated installed locations."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (
    "plan-work",
    "do-work",
    "code-review",
    "do-fixes",
    "plan-review",
    "start-work",
    "super-work",
)


@pytest.fixture
def workflow_home(tmp_path):
    home = tmp_path / "home"
    common = home / ".agent-skills"
    common.mkdir(parents=True)
    (common / "source").symlink_to(ROOT, target_is_directory=True)
    (common / "skills").symlink_to(ROOT / "skills", target_is_directory=True)
    scripts = common / "scripts"
    scripts.mkdir()
    (scripts / "python").symlink_to(sys.executable)
    for name in ("shared", "plan-work", "code-review", "plan-review"):
        (scripts / name).symlink_to(ROOT / "skills" / name / "scripts", target_is_directory=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        '  "branch --show-current") echo ambrose/eng-42-sample ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n"
    )
    git.chmod(0o755)
    env = {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(home / "custom-codex"),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    env.pop("AGENT_SKILLS_CONFIG", None)
    for name in (
        "AGENT_SKILLS_HARNESS",
        "CLAUDE_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CODEX_THREAD_ID",
    ):
        env.pop(name, None)

    def config(data, relative=".agent-skills/config.json"):
        path = home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        return path

    def run(name, flag, *arguments, **overrides):
        result = subprocess.run(
            ["bash", str(scripts / name / "context.sh"), flag, *arguments],
            cwd=repo,
            env={**env, **overrides},
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout.strip()

    return home, repo, config, run


def test_shared_config_is_authoritative_over_legacy_claude_config(workflow_home):
    home, _, config, run = workflow_home
    config({"work_root": "~/shared-work", "user_prefix": "shared-user"})
    config(
        {"work_root": "~/old-work", "user_prefix": "old-user"},
        ".claude/agent-skills.json",
    )
    assert run("shared", "user-slug") == "shared-user"
    assert run("shared", "work-folder") == str(home / "shared-work/eng-42-sample")


def test_legacy_config_remains_readable_before_migration(workflow_home):
    home, _, config, run = workflow_home
    config(
        {"work_root": "~/old-work", "user_prefix": "old-user"},
        ".claude/agent-skills.json",
    )
    assert run("shared", "user-slug") == "old-user"
    assert run("shared", "work-folder") == str(home / "old-work/eng-42-sample")


def test_explicit_config_override_expands_tilde(workflow_home):
    home, _, config, run = workflow_home
    config({"work_root": "~/shared-work", "user_prefix": "shared-user"})
    config({"work_root": "~/chosen-work", "user_prefix": "chosen"}, "chosen.json")
    override = {"AGENT_SKILLS_CONFIG": "~/chosen.json"}
    assert run("shared", "user-slug", **override) == "chosen"
    assert run("shared", "work-folder", **override) == str(home / "chosen-work/eng-42-sample")


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_active_agent_overrides_share_the_same_context_contract(workflow_home, agent):
    home, _, config, run = workflow_home
    config(
        {
            "work_root": "~/shared-work",
            "user_prefix": "shared-user",
            "agents": {agent: {"work_root": f"~/{agent}-work", "user_prefix": agent}},
        }
    )
    override = {"AGENT_SKILLS_HARNESS": agent}
    assert run("shared", "user-slug", **override) == agent
    assert run("shared", "work-folder", **override) == str(home / f"{agent}-work/eng-42-sample")


def test_code_review_plan_uses_shared_work_folder_resolution(workflow_home):
    home, _, config, run = workflow_home
    config({"work_root": "~/shared-work"})
    plan = home / "shared-work/eng-42-existing-plan/plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Existing shared plan\n\nExpected plan context.\n")
    assert run("code-review", "work-plan") == plan.read_text().strip()
    assert run("shared", "work-folder") == str(plan.parent)


@pytest.mark.parametrize(
    ("session_env", "agent"),
    [
        ({"CLAUDE_SESSION_ID": "test-session"}, "claude"),
        ({"CLAUDE_CODE_SESSION_ID": "test-session"}, "claude"),
        ({"CODEX_THREAD_ID": "test-thread"}, "codex"),
    ],
)
def test_active_agent_is_inferred_from_session_environment(workflow_home, session_env, agent):
    _, _, config, run = workflow_home
    config({"user_prefix": "shared", "agents": {agent: {"user_prefix": agent}}})
    assert run("shared", "user-slug", **session_env) == agent


def test_codex_home_alone_does_not_select_agent_overrides(workflow_home):
    _, _, config, run = workflow_home
    config({"user_prefix": "shared", "agents": {"codex": {"user_prefix": "codex"}}})
    assert run("shared", "user-slug") == "shared"


def test_explicit_harness_wins_over_inferred_session(workflow_home):
    _, _, config, run = workflow_home
    config({"agents": {"claude": {"user_prefix": "claude"}, "codex": {"user_prefix": "codex"}}})
    assert (
        run(
            "shared",
            "user-slug",
            AGENT_SKILLS_HARNESS="codex",
            CLAUDE_CODE_SESSION_ID="test-session",
        )
        == "codex"
    )


@pytest.mark.parametrize(
    ("skill", "flag", "directory", "overridden", "other_builtin"),
    [
        ("code-review", "reviewer-agents", "reviewers", "security", "devdocs"),
        (
            "plan-review",
            "plan-reviewer-agents",
            "plan-reviewers",
            "architecture",
            "completeness",
        ),
    ],
)
def test_reviewers_resolve_resources_through_installed_script_symlink(
    workflow_home, skill, flag, directory, overridden, other_builtin
):
    _, repo, _, run = workflow_home
    legacy = repo / ".claude/agents" / directory
    legacy.mkdir(parents=True)
    (legacy / f"{overridden}.md").write_text("# Legacy override, selectable\n")
    (legacy / "custom.md").write_text("always: true\n\n# Custom reviewer\n")
    groups = dict(line.split(":", 1) for line in run(skill, flag).splitlines())
    always = groups["always-on"].split()
    selectable = groups["selectable"].split()
    assert other_builtin in always
    assert "custom" in always
    assert overridden in selectable
    assert overridden not in always
    assert len(always + selectable) == len(set(always + selectable))


def test_neutral_repo_reviewer_overrides_legacy_and_builtin(workflow_home):
    _, repo, _, run = workflow_home
    legacy = repo / ".claude/agents/reviewers"
    legacy.mkdir(parents=True)
    (legacy / "security.md").write_text("# Legacy selectable security\n")
    neutral = repo / ".agents/reviewers"
    neutral.mkdir(parents=True)
    (neutral / "security.md").write_text("always: true\n\n# Neutral security\n")
    groups = dict(line.split(":", 1) for line in run("code-review", "reviewer-agents").splitlines())
    assert groups["always-on"].split().count("security") == 1
    assert "security" not in groups["selectable"].split()


def test_config_set_preserves_symlink_and_unrelated_settings(workflow_home):
    home, _, config, run = workflow_home
    target = config({"user_prefix": "keep", "team_repos": {"other": "/existing"}}, "actual.json")
    link = home / ".agent-skills/config.json"
    link.symlink_to(target)
    run("shared", "config-set", "team_repos", "eng", '"/repos/with.period"')
    assert link.is_symlink()
    assert json.loads(target.read_text()) == {
        "user_prefix": "keep",
        "team_repos": {"other": "/existing", "eng": "/repos/with.period"},
    }


def test_config_set_preserves_agent_override_and_can_update_common_defaults(workflow_home):
    _, _, config, run = workflow_home
    path = config({"user_prefix": "shared", "agents": {"codex": {"user_prefix": "codex"}}})
    run("shared", "config-set", "user_prefix", '"changed"', CODEX_THREAD_ID="session")
    data = json.loads(path.read_text())
    assert data["user_prefix"] == "shared"
    assert data["agents"]["codex"]["user_prefix"] == "changed"
    run("shared", "config-set", "--shared", "user_prefix", '"common"', CODEX_THREAD_ID="session")
    data = json.loads(path.read_text())
    assert data["user_prefix"] == "common"
    assert data["agents"]["codex"]["user_prefix"] == "changed"


@pytest.mark.parametrize(
    ("filename", "quoted"),
    [
        ("src/quoted name.py", "src/quoted name.py"),
        ("src/café.py", r"src/caf\303\251.py"),
        ("src/line\nbreak.py", r"src/line\nbreak.py"),
    ],
)
def test_incremental_diff_filters_git_quoted_paths(workflow_home, filename, quoted):
    _, repo, _, run = workflow_home
    diff_file = repo / "fixture.diff"
    selected = (
        f'diff --git "a/{quoted}" "b/{quoted}"\n'
        f'--- "a/{quoted}"\n'
        f'+++ "b/{quoted}"\n'
        "@@ -1 +1 @@\n-before\n+after\n"
    )
    diff_file.write_text(
        "diff --git a/untouched.py b/untouched.py\n"
        "--- a/untouched.py\n+++ b/untouched.py\n@@ -1 +1 @@\n-old\n+new\n" + selected
    )
    changed = repo / "changed.txt"
    # Git quotes non-ASCII/control characters without -z; literal spaces alone
    # remain unquoted. NUL-delimited output carries each raw filename intact.
    changed.write_text((f'"{quoted}"' if filename != quoted else filename) + "\n")
    changed_nul = repo / "changed-nul.txt"
    changed_nul.write_bytes(filename.encode() + b"\0")
    bin_dir = repo.parent / "bin"
    (bin_dir / "git").write_text(
        '#!/bin/sh\nif [ "$1 $2" = "diff --name-only" ]; then '
        'if [ "$3" = "-z" ]; then cat "$WORKFLOW_CHANGED_NUL"; '
        'else cat "$WORKFLOW_CHANGED"; fi; '
        "else exit 1; fi\n"
    )
    gh = bin_dir / "gh"
    gh.write_text(
        '#!/bin/sh\nif [ "$1 $2" = "pr diff" ] && [ "$#" = 3 ]; then cat "$WORKFLOW_DIFF"; '
        "else exit 1; fi\n"
    )
    gh.chmod(0o755)
    env = {
        "WORKFLOW_CHANGED": str(changed),
        "WORKFLOW_CHANGED_NUL": str(changed_nul),
        "WORKFLOW_DIFF": str(diff_file),
    }
    assert run("code-review", "diff", "--pr", "72", "--since", "old-sha", **env) == selected.strip()
    assert (
        run("code-review", "reversed-diff", "--pr", "72", "--since", "old-sha", **env)
        == selected.strip()
    )


def test_project_instruction_context_includes_both_harnesses(workflow_home):
    _, repo, _, run = workflow_home
    (repo / "AGENTS.md").write_text("Codex instructions\n")
    (repo / "CLAUDE.md").write_text("Legacy instructions\n")
    (repo / ".agents/rules").mkdir(parents=True)
    (repo / ".claude/rules").mkdir(parents=True)
    assert set(run("plan-work", "project-instructions").splitlines()) == {
        "AGENTS.md",
        "CLAUDE.md",
        ".agents/rules",
        ".claude/rules",
    }


@pytest.mark.parametrize("name", WORKFLOWS)
def test_workflow_context_is_loaded_explicitly_for_either_harness(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text()
    assert "!`" not in text, "Claude preprocessing must not be required to gather context"
    assert "~/.agent-skills/scripts/shared/context.sh" in text
    assert "${CLAUDE_SKILL_DIR}" not in text
    assert "~/.claude/skills/" not in text


def test_shared_capability_reference_uses_tiers_instead_of_fixed_models():
    reference = ROOT / "skills/shared/references/harness-capabilities.md"
    assert reference.exists()
    text = reference.read_text().lower()
    for tier in ("low", "medium", "high"):
        assert tier in text
    for name in WORKFLOWS:
        skill = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert "harness-capabilities.md" in skill
        assert "model: sonnet" not in skill
        assert "/model opus" not in skill
