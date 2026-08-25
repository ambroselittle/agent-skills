"""Tests for the ``exclude`` block: normalization and ``--without`` persistence."""

import json
from pathlib import Path

import pytest

import setup_config as sc


def write_config(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / "agent-skills.json"
    monkeypatch.setenv("AGENT_SKILLS_CONFIG", str(path))
    return path


# --------------------------------------------------------------------------- #
# normalize_exclusions                                                        #
# --------------------------------------------------------------------------- #


def test_no_exclude_key_is_empty():
    assert sc.normalize_exclusions({"user_prefix": "x"}) == {}


def test_lists_pass_through():
    result = sc.normalize_exclusions(
        {"exclude": {"hooks": ["message-display"], "skills": ["author-message", "do-work"]}}
    )
    assert result == {"hooks": {"message-display"}, "skills": {"author-message", "do-work"}}


def test_all_wins_over_other_entries():
    result = sc.normalize_exclusions({"exclude": {"hooks": ["pretooluse", "all"]}})
    assert result == {"hooks": {"all"}}


def test_bare_string_is_a_single_entry():
    assert sc.normalize_exclusions({"exclude": {"mcp": "playwright"}}) == {"mcp": {"playwright"}}


def test_unknown_key_warns_and_is_dropped(capsys):
    result = sc.normalize_exclusions({"exclude": {"widgets": ["x"], "cli": ["reclaude"]}})
    assert result == {"cli": {"reclaude"}}
    assert 'unknown exclude key "widgets"' in capsys.readouterr().err


def test_unknown_name_in_closed_set_warns_and_is_dropped(capsys):
    result = sc.normalize_exclusions({"exclude": {"hooks": ["message-display", "bogus"]}})
    assert result == {"hooks": {"message-display"}}
    assert 'unknown exclude.hooks entry "bogus"' in capsys.readouterr().err


def test_shared_skill_cannot_be_excluded(capsys):
    result = sc.normalize_exclusions({"exclude": {"skills": ["shared", "wtf"]}})
    assert result == {"skills": {"wtf"}}
    assert '"shared" cannot be excluded' in capsys.readouterr().err


def test_non_list_value_warns(capsys):
    assert sc.normalize_exclusions({"exclude": {"hooks": True}}) == {}
    assert "exclude.hooks must be a list" in capsys.readouterr().err


def test_non_object_exclude_warns(capsys):
    assert sc.normalize_exclusions({"exclude": ["hooks"]}) == {}
    assert "exclude must be an object" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# exclusions command (fail-open on the file)                                  #
# --------------------------------------------------------------------------- #


def test_exclusions_missing_file_prints_nothing(config_file, capsys):
    assert sc.main(["exclusions"]) == 0
    assert capsys.readouterr().out == ""


def test_exclusions_malformed_file_prints_nothing(config_file, capsys):
    config_file.write_text("{not json")
    assert sc.main(["exclusions"]) == 0
    assert capsys.readouterr().out == ""


def test_exclusions_prints_sorted_key_name_lines(config_file, capsys):
    write_config(
        config_file,
        {"exclude": {"skills": ["wtf", "author-message"], "hooks": ["all"], "mcp": ["playwright"]}},
    )
    assert sc.main(["exclusions"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "hooks=all",
        "mcp=playwright",
        "skills=author-message",
        "skills=wtf",
    ]


# --------------------------------------------------------------------------- #
# add-exclusion                                                               #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("component", "expected"),
    [
        ("pretooluse", {"hooks": ["pretooluse"]}),
        ("notification", {"hooks": ["notification"]}),
        ("message-display", {"hooks": ["message-display"]}),
        ("window-title", {"hooks": ["window-title"]}),
        ("skills", {"skills": ["all"]}),
        ("mcp", {"mcp": ["all"]}),
        ("guidance", {"guidance": ["all"]}),
        ("attribution", {"attribution": ["all"]}),
        ("cli", {"cli": ["all"]}),
    ],
)
def test_add_exclusion_maps_component_to_key(config_file, component, expected):
    assert sc.main(["add-exclusion", component]) == 0
    assert json.loads(config_file.read_text())["exclude"] == expected


def test_add_exclusion_hooks_group_adds_all_four(config_file):
    assert sc.main(["add-exclusion", "hooks"]) == 0
    assert json.loads(config_file.read_text())["exclude"]["hooks"] == list(sc.HOOK_NAMES)


def test_add_exclusion_preserves_other_keys_and_formatting(config_file):
    write_config(
        config_file,
        {"user_prefix": "ambrose", "team_repos": {"lc": "/x"}, "exclude": {"skills": ["wtf"]}},
    )
    assert sc.main(["add-exclusion", "mcp"]) == 0
    text = config_file.read_text()
    assert json.loads(text) == {
        "user_prefix": "ambrose",
        "team_repos": {"lc": "/x"},
        "exclude": {"skills": ["wtf"], "mcp": ["all"]},
    }
    assert text.endswith("}\n")
    assert '\n  "user_prefix"' in text  # indent=2


def test_add_exclusion_is_idempotent(config_file, capsys):
    assert sc.main(["add-exclusion", "pretooluse"]) == 0
    first = config_file.read_text()
    assert sc.main(["add-exclusion", "pretooluse"]) == 0
    assert config_file.read_text() == first
    assert "already excluded" in capsys.readouterr().out


def test_add_exclusion_all_replaces_existing_names(config_file):
    write_config(config_file, {"exclude": {"hooks": ["pretooluse"]}})
    assert sc.main(["add-exclusion", "hooks"]) == 0
    assert json.loads(config_file.read_text())["exclude"]["hooks"] == list(sc.HOOK_NAMES)


def test_add_exclusion_under_all_is_noop():
    config = {"exclude": {"skills": ["all"]}}
    assert sc.add_exclusions(config, [("skills", "wtf")]) == []
    assert config == {"exclude": {"skills": ["all"]}}


def test_add_exclusion_creates_missing_file(config_file):
    assert not config_file.exists()
    assert sc.main(["add-exclusion", "cli"]) == 0
    assert json.loads(config_file.read_text()) == {"exclude": {"cli": ["all"]}}
