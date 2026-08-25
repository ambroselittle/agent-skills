"""Tests for the settings.json primitives: every install has a working inverse."""

import json
from pathlib import Path

import pytest

import setup_config as sc

RULES = {
    "allow": ["Bash(rsync *)", "Read", "Write"],
    "deny": ["Bash(rm -rf /)"],
    "removed": ["mcp__*"],
}


@pytest.fixture
def settings_file(tmp_path) -> Path:
    return tmp_path / "settings.json"


@pytest.fixture
def rules_file(tmp_path) -> Path:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(RULES))
    return path


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, data: dict) -> str:
    sc.save_json(path, data)
    return path.read_text()


# --------------------------------------------------------------------------- #
# load/save formatting                                                        #
# --------------------------------------------------------------------------- #


def test_save_json_matches_legacy_heredoc_format(settings_file):
    """The inline heredocs wrote ``json.dump(indent=2)`` plus a trailing newline."""
    sc.save_json(settings_file, {"a": {"b": [1, 2]}, "c": "x"})
    assert settings_file.read_text() == json.dumps({"a": {"b": [1, 2]}, "c": "x"}, indent=2) + "\n"


def test_load_json_is_fail_open(settings_file):
    assert sc.load_json(settings_file) == {}
    settings_file.write_text("nope")
    assert sc.load_json(settings_file) == {}
    settings_file.write_text("[1]")
    assert sc.load_json(settings_file) == {}


# --------------------------------------------------------------------------- #
# hook                                                                        #
# --------------------------------------------------------------------------- #

HOOK = "~/.claude/hooks/message-display/swap.py"


def test_hook_register_then_unregister_restores_original(settings_file):
    original = write(settings_file, {"model": "opus"})
    assert (
        sc.main(["hook", "register", str(settings_file), "MessageDisplay", HOOK, "--timeout", "5"])
        == 0
    )
    assert read(settings_file)["hooks"]["MessageDisplay"] == [
        {"hooks": [{"type": "command", "command": HOOK, "timeout": 5}]}
    ]
    assert sc.main(["hook", "unregister", str(settings_file), "MessageDisplay", HOOK]) == 0
    assert settings_file.read_text() == original


def test_hook_register_is_idempotent_and_updates_in_place(settings_file, capsys):
    sc.main(["hook", "register", str(settings_file), "Stop", HOOK])
    first = settings_file.read_text()
    sc.main(["hook", "register", str(settings_file), "Stop", HOOK])
    assert settings_file.read_text() == first
    assert "already registered" in capsys.readouterr().out
    sc.main(["hook", "register", str(settings_file), "Stop", HOOK, "--timeout", "9"])
    assert read(settings_file)["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 9
    assert len(read(settings_file)["hooks"]["Stop"]) == 1


def test_hook_unregister_leaves_other_hooks_and_events(settings_file):
    write(
        settings_file,
        {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {"type": "command", "command": HOOK},
                            {"type": "command", "command": "~/mine.sh"},
                        ]
                    }
                ],
                "SessionStart": [{"hooks": [{"type": "command", "command": HOOK}]}],
                "Notification": [{"hooks": [{"type": "command", "command": "~/other.sh"}]}],
            }
        },
    )
    sc.main(["hook", "unregister", str(settings_file), "Stop", HOOK])
    sc.main(["hook", "unregister", str(settings_file), "SessionStart", HOOK])
    assert read(settings_file)["hooks"] == {
        "Stop": [{"hooks": [{"type": "command", "command": "~/mine.sh"}]}],
        "Notification": [{"hooks": [{"type": "command", "command": "~/other.sh"}]}],
    }


def test_hook_unregister_absent_is_noop(settings_file, capsys):
    original = write(
        settings_file, {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "~/x"}]}]}}
    )
    sc.main(["hook", "unregister", str(settings_file), "Stop", HOOK])
    sc.main(["hook", "unregister", str(settings_file), "Nope", HOOK])
    assert settings_file.read_text() == original
    assert "not present" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# permissions                                                                 #
# --------------------------------------------------------------------------- #


def test_permissions_merge_then_remove_restores_original(settings_file, rules_file):
    original = write(
        settings_file, {"permissions": {"allow": ["Bash(git *)"], "deny": ["WebFetch"]}}
    )
    assert sc.main(["permissions", "merge", str(settings_file), str(rules_file)]) == 0
    assert read(settings_file)["permissions"] == {
        "allow": sorted(["Bash(git *)", *RULES["allow"]]),
        "deny": sorted(["WebFetch", *RULES["deny"]]),
    }
    assert sc.main(["permissions", "remove", str(settings_file), str(rules_file)]) == 0
    assert settings_file.read_text() == original


def test_permissions_merge_subtracts_retired_rules(settings_file, rules_file, capsys):
    write(settings_file, {"permissions": {"allow": ["mcp__*", "Bash(git *)"]}})
    sc.main(["permissions", "merge", str(settings_file), str(rules_file)])
    assert "mcp__*" not in read(settings_file)["permissions"]["allow"]
    assert "1 retired rules removed" in capsys.readouterr().out


def test_permissions_merge_reports_already_present(settings_file, rules_file, capsys):
    sc.main(["permissions", "merge", str(settings_file), str(rules_file)])
    capsys.readouterr()
    sc.main(["permissions", "merge", str(settings_file), str(rules_file)])
    assert "All 3 allow + 1 deny rules already present" in capsys.readouterr().out


def test_permissions_remove_prunes_empty_permissions(settings_file, rules_file):
    original = write(settings_file, {"model": "opus"})
    sc.main(["permissions", "merge", str(settings_file), str(rules_file)])
    sc.main(["permissions", "remove", str(settings_file), str(rules_file)])
    assert settings_file.read_text() == original


def test_permissions_remove_without_ours_is_noop(settings_file, rules_file, capsys):
    original = write(settings_file, {"permissions": {"allow": ["Bash(git *)"]}})
    sc.main(["permissions", "remove", str(settings_file), str(rules_file)])
    assert settings_file.read_text() == original
    assert "No built-in permission rules present" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# statusline / env                                                            #
# --------------------------------------------------------------------------- #

STATUS = "~/.claude/statusline.sh"


def test_statusline_set_then_unset_restores_original(settings_file):
    original = write(settings_file, {"model": "opus"})
    sc.main(["statusline", "set", str(settings_file), STATUS])
    assert read(settings_file)["statusLine"] == {"type": "command", "command": STATUS}
    sc.main(["statusline", "unset", str(settings_file), STATUS])
    assert settings_file.read_text() == original


def test_statusline_unset_leaves_foreign_value(settings_file, capsys):
    original = write(settings_file, {"statusLine": {"type": "command", "command": "~/mine.sh"}})
    sc.main(["statusline", "unset", str(settings_file), STATUS])
    assert settings_file.read_text() == original
    assert "left alone" in capsys.readouterr().out


def test_env_set_then_unset_restores_original(settings_file):
    original = write(settings_file, {"env": {"FOO": "bar"}})
    sc.main(["env", "set", str(settings_file), "CLAUDE_CODE_DISABLE_TERMINAL_TITLE", "1"])
    assert read(settings_file)["env"]["CLAUDE_CODE_DISABLE_TERMINAL_TITLE"] == "1"
    sc.main(["env", "unset", str(settings_file), "CLAUDE_CODE_DISABLE_TERMINAL_TITLE", "1"])
    assert settings_file.read_text() == original


def test_env_unset_prunes_empty_env_and_leaves_foreign_value(settings_file):
    original = write(settings_file, {"model": "opus"})
    sc.main(["env", "set", str(settings_file), "K", "1"])
    sc.main(["env", "unset", str(settings_file), "K", "1"])
    assert settings_file.read_text() == original
    foreign = write(settings_file, {"env": {"K": "2"}})
    sc.main(["env", "unset", str(settings_file), "K", "1"])
    assert settings_file.read_text() == foreign


# --------------------------------------------------------------------------- #
# attribution                                                                 #
# --------------------------------------------------------------------------- #


def test_attribution_set_all_then_unset_all_restores_original(settings_file):
    original = write(settings_file, {"model": "opus"})
    sc.main(["attribution", "set", str(settings_file), "sessionUrl", "commit", "pr"])
    assert read(settings_file)["attribution"] == {"sessionUrl": False, "commit": "", "pr": ""}
    sc.main(["attribution", "unset", str(settings_file), "sessionUrl", "commit", "pr"])
    assert settings_file.read_text() == original


def test_attribution_is_per_key(settings_file):
    sc.main(["attribution", "set", str(settings_file), "commit", "pr"])
    assert read(settings_file)["attribution"] == {"commit": "", "pr": ""}
    sc.main(["attribution", "unset", str(settings_file), "commit"])
    assert read(settings_file)["attribution"] == {"pr": ""}


def test_attribution_unset_leaves_user_value(settings_file):
    original = write(settings_file, {"attribution": {"commit": "Made by me", "pr": ""}})
    sc.main(["attribution", "unset", str(settings_file), "commit"])
    assert settings_file.read_text() == original
    sc.main(["attribution", "unset", str(settings_file), "pr"])
    assert read(settings_file)["attribution"] == {"commit": "Made by me"}


def test_attribution_set_reports_already_disabled(settings_file, capsys):
    sc.main(["attribution", "set", str(settings_file), "sessionUrl"])
    capsys.readouterr()
    sc.main(["attribution", "set", str(settings_file), "sessionUrl"])
    assert "already disabled" in capsys.readouterr().out


def test_attribution_rejects_unknown_key(settings_file, capsys):
    assert sc.main(["attribution", "set", str(settings_file), "bogus"]) == 1
    assert "unknown attribution key" in capsys.readouterr().err
