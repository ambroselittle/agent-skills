"""Exercise installed portable context entry points from another project."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def portable_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    shared = home / ".agent-skills"
    shared.mkdir()
    (shared / "source").symlink_to(ROOT, target_is_directory=True)
    aliases = shared / "scripts"
    aliases.mkdir()
    (aliases / "python").symlink_to(sys.executable)
    for skill in ("sync-guidance", "wtf", "deploy-aws", "create-repo"):
        (aliases / skill).symlink_to(ROOT / "skills" / skill / "scripts", target_is_directory=True)
    resources = shared / "skills"
    resources.mkdir()
    (resources / "create-repo").symlink_to(ROOT / "skills/create-repo", target_is_directory=True)
    caller = tmp_path / "another-project"
    (caller / ".git").mkdir(parents=True)
    (caller / "templates").mkdir()
    (caller / "templates/user-common.md").write_text("Wrong project guidance.\n")
    codex = tmp_path / "custom-codex"
    env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(codex)}
    for key in (
        "AGENT_SKILLS_CONFIG",
        "AGENT_SKILLS_HARNESS",
        "CLAUDE_SESSION_ID",
        "CLAUDE_CODE_SESSION_ID",
        "CODEX_THREAD_ID",
    ):
        env.pop(key, None)
    return home, codex, caller, env


def run_alias(portable_home, skill, script, *args, harness=None):
    home, _, caller, env = portable_home
    if harness:
        env = {**env, "AGENT_SKILLS_HARNESS": harness}
    alias = home / ".agent-skills/scripts" / skill / script
    return subprocess.run(
        ["bash", str(alias), *args], cwd=caller, env=env, capture_output=True, text=True
    )


def test_sync_alias_resolves_source_instead_of_callers_repository(portable_home):
    result = run_alias(portable_home, "sync-guidance", "context.sh", "repo-rules")
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)
    assert Path(context["repo"]).resolve() == ROOT
    assert context["shared_template"] == (ROOT / "templates/user-common.md").read_text().strip()
    assert set(context["integration_templates"]) == {"claude", "codex"}
    assert (
        context["integration_templates"]["codex"]
        == (ROOT / "templates/user-codex.md").read_text().strip()
    )
    assert "Wrong project guidance" not in result.stdout


@pytest.mark.parametrize(
    ("flag", "module", "expected"),
    [
        ("list-templates", "scripts.list_templates", "api-ts — API template\n"),
        ("repo-home", "scripts.find_repo_home", '{"last_picked": "/example/repos"}\n'),
    ],
)
def test_create_repo_alias_runs_from_its_packaged_resources(
    portable_home, tmp_path, flag, module, expected
):
    _, _, _, env = portable_home
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "uv"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "package = Path.cwd()\n"
        "for option in ('--directory', '--project'):\n"
        "    if option in args:\n"
        "        package = Path(args[args.index(option) + 1])\n"
        "assert package.resolve() == Path(os.environ['EXPECTED_PACKAGE']).resolve(), str(package)\n"
        "assert os.environ['EXPECTED_MODULE'] in args, args\n"
        "sys.stdout.write(os.environ['EXPECTED_OUTPUT'])\n"
    )
    shim.chmod(0o755)
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "EXPECTED_PACKAGE": str(ROOT / "skills/create-repo"),
            "EXPECTED_MODULE": module,
            "EXPECTED_OUTPUT": expected,
        }
    )
    result = run_alias(portable_home, "create-repo", "context.sh", flag)
    assert result.returncode == 0, result.stderr
    assert result.stdout == expected


def test_guidance_context_exposes_both_agents_and_every_unmanaged_range(portable_home):
    home, codex, _, _ = portable_home
    claude = home / ".claude"
    claude.mkdir()
    codex.mkdir()
    text = (
        "Personal before.\n"
        "<employer>\n"
        "Employer guidance.\n"
        "</employer>\n"
        "Personal between.\n"
        "<agent-skills-guidance>\n"
        "Managed guidance.\n"
        "</agent-skills-guidance>\n"
        "Personal after.\n"
    )
    (claude / "CLAUDE.md").write_text(text)
    (codex / "AGENTS.md").write_text("Codex personal note.\n")
    result = run_alias(portable_home, "sync-guidance", "context.sh", "guidance")
    assert result.returncode == 0, result.stderr
    contexts = {item["agent"]: item for item in json.loads(result.stdout)["guidance"]}
    assert set(contexts) == {"claude", "codex"}
    assert contexts["claude"]["full_content"] == text
    assert contexts["claude"]["unmanaged_ranges"] == [
        {"start_line": 1, "end_line": 1, "content": "Personal before.\n"},
        {"start_line": 5, "end_line": 5, "content": "Personal between.\n"},
        {"start_line": 9, "end_line": 9, "content": "Personal after.\n"},
    ]
    assert contexts["claude"]["fences"] == [
        {"tag": "employer", "start_line": 2, "end_line": 4},
        {"tag": "agent-skills-guidance", "start_line": 6, "end_line": 8},
    ]
    assert contexts["codex"]["path"] == str(codex / "AGENTS.md")
    assert contexts["codex"]["unmanaged_ranges"] == [
        {"start_line": 1, "end_line": 1, "content": "Codex personal note.\n"}
    ]
    assert (claude / "CLAUDE.md").read_text() == text
    assert (codex / "AGENTS.md").read_text() == "Codex personal note.\n"


def test_codex_wtf_capture_does_not_claim_a_claude_session(portable_home):
    result = run_alias(
        portable_home, "wtf", "capture.sh", "Keep the correction verbatim.", harness="codex"
    )
    assert result.returncode == 0, result.stderr
    capture = Path(result.stdout.strip())
    assert capture.parent == portable_home[0] / ".agent-skills/wtf"
    text = capture.read_text()
    assert "agent: codex\n" in text
    assert "Keep the correction verbatim." in text
    assert "transcript unavailable" in text.lower()
    assert "CLAUDE_SESSION_ID" not in text


def test_wtf_capture_recognizes_native_claude_code_session_id(portable_home):
    portable_home[3]["CLAUDE_CODE_SESSION_ID"] = "native-session"
    result = run_alias(portable_home, "wtf", "capture.sh", "Keep the session identity.")
    assert result.returncode == 0, result.stderr
    text = Path(result.stdout.strip()).read_text()
    assert "agent: claude\n" in text
    assert "session_id: native-session\n" in text


def test_deployment_context_preserves_callers_config_without_exposing_credentials(portable_home):
    _, _, caller, _ = portable_home
    config = {
        "app": "portable-app",
        "region": "us-east-1",
        "services": {"api": {"url": "https://api.example.test"}},
        "database": {
            "endpoint": "postgres.example.test",
            "port": 5432,
            "username": "app",
            "password": "credential-value-never-print",
            "url": "postgresql://app:credential-value-never-print@postgres.example.test/app",
        },
    }
    path = caller / ".deploy-aws.json"
    path.write_text(json.dumps(config))
    result = run_alias(portable_home, "deploy-aws", "context.sh", "deploy-config")
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)
    assert context["app"] == config["app"]
    assert context["region"] == config["region"]
    assert context["services"] == config["services"]
    assert context["database"]["endpoint"] == config["database"]["endpoint"]
    assert "credential-value-never-print" not in result.stdout + result.stderr
    assert "postgresql://" not in result.stdout
    assert json.loads(path.read_text()) == config
