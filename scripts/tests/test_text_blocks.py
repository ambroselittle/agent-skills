"""Tests for the fenced text blocks: the CLAUDE.md guidance block and the shell rc alias fence."""

from pathlib import Path

import pytest

import setup_config as sc

CONTENT = "# Guidance\n\nBe good."
FENCED = f"{sc.GUIDANCE_OPEN_TAG}\n{CONTENT}\n{sc.GUIDANCE_CLOSE_TAG}"
BLOCK = (
    "# BEGIN agent-skills-aliases — managed by agent-skills setup, do not edit manually\n"
    'alias reclaude="$HOME/.claude/scripts/claude-resume.sh"\n'
    "# END agent-skills-aliases\n"
)


@pytest.fixture
def content_file(tmp_path) -> Path:
    path = tmp_path / "content.md"
    path.write_text(CONTENT)
    return path


@pytest.fixture
def block_file(tmp_path) -> Path:
    path = tmp_path / "block.sh"
    path.write_text(BLOCK)
    return path


# --------------------------------------------------------------------------- #
# guidance                                                                    #
# --------------------------------------------------------------------------- #


def test_guidance_upsert_creates_file(tmp_path, content_file, capsys):
    md = tmp_path / "CLAUDE.md"
    assert sc.main(["guidance", "upsert", str(md), str(content_file)]) == 0
    assert md.read_text() == FENCED + "\n"
    assert "Created guidance block" in capsys.readouterr().out


def test_guidance_upsert_prepends_to_existing_text(tmp_path, content_file, capsys):
    md = tmp_path / "CLAUDE.md"
    md.write_text("My own notes.\n")
    sc.main(["guidance", "upsert", str(md), str(content_file)])
    assert md.read_text() == FENCED + "\n\nMy own notes.\n"
    assert "Prepended guidance block" in capsys.readouterr().out


def test_guidance_upsert_replaces_existing_block_in_place(tmp_path, content_file, capsys):
    md = tmp_path / "CLAUDE.md"
    md.write_text(f"Top.\n\n{sc.GUIDANCE_OPEN_TAG}\nold\n{sc.GUIDANCE_CLOSE_TAG}\n\nBottom.\n")
    sc.main(["guidance", "upsert", str(md), str(content_file)])
    assert md.read_text() == f"Top.\n\n{FENCED}\n\nBottom.\n"
    assert "Updated guidance block" in capsys.readouterr().out


def test_guidance_upsert_orphaned_tag_warns_and_prepends(tmp_path, content_file, capsys):
    md = tmp_path / "CLAUDE.md"
    md.write_text(f"{sc.GUIDANCE_OPEN_TAG}\nbroken\n")
    sc.main(["guidance", "upsert", str(md), str(content_file)])
    assert md.read_text().startswith(FENCED + "\n\n")
    assert "Orphaned tag" in capsys.readouterr().err


def test_guidance_upsert_reads_content_from_stdin(tmp_path, monkeypatch):
    import io

    md = tmp_path / "CLAUDE.md"
    monkeypatch.setattr("sys.stdin", io.StringIO(CONTENT))
    sc.main(["guidance", "upsert", str(md), "-"])
    assert md.read_text() == FENCED + "\n"


@pytest.mark.parametrize(
    "original",
    ["My own notes.\n", "Top.\n\nBottom.\n", "# Heading\n\n- a\n- b\n"],
)
def test_guidance_remove_restores_original_after_prepend(tmp_path, content_file, original):
    md = tmp_path / "CLAUDE.md"
    md.write_text(original)
    sc.main(["guidance", "upsert", str(md), str(content_file)])
    assert sc.main(["guidance", "remove", str(md)]) == 0
    assert md.read_text() == original


def test_guidance_remove_restores_original_when_block_was_in_the_middle(tmp_path, content_file):
    md = tmp_path / "CLAUDE.md"
    md.write_text(f"Top.\n\n{sc.GUIDANCE_OPEN_TAG}\nold\n{sc.GUIDANCE_CLOSE_TAG}\n\nBottom.\n")
    sc.main(["guidance", "remove", str(md)])
    assert md.read_text() == "Top.\n\n\n\nBottom.\n"


def test_guidance_remove_deletes_file_we_created(tmp_path, content_file, capsys):
    md = tmp_path / "CLAUDE.md"
    sc.main(["guidance", "upsert", str(md), str(content_file)])
    sc.main(["guidance", "remove", str(md)])
    assert not md.exists()
    assert "held only the guidance block" in capsys.readouterr().out


def test_guidance_remove_without_block_is_noop(tmp_path, capsys):
    md = tmp_path / "CLAUDE.md"
    md.write_text("Mine.\n")
    sc.main(["guidance", "remove", str(md)])
    assert md.read_text() == "Mine.\n"
    assert "No guidance block" in capsys.readouterr().out


def test_guidance_remove_missing_file_is_noop(tmp_path, capsys):
    assert sc.main(["guidance", "remove", str(tmp_path / "CLAUDE.md")]) == 0
    assert "nothing to remove" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# rcfence                                                                     #
# --------------------------------------------------------------------------- #


def test_rcfence_upsert_appends_after_blank_line(tmp_path, block_file, capsys):
    rc = tmp_path / ".zshrc"
    rc.write_text("export A=1\n")
    assert sc.main(["rcfence", "upsert", str(rc), str(block_file)]) == 0
    assert rc.read_text() == "export A=1\n\n" + BLOCK
    assert "Shell aliases added" in capsys.readouterr().out


def test_rcfence_upsert_replaces_existing_fence_in_place(tmp_path, block_file, capsys):
    rc = tmp_path / ".zshrc"
    rc.write_text(
        "export A=1\n\n# BEGIN agent-skills-aliases — old\nalias old=1\n# END agent-skills-aliases\nexport B=2\n"
    )
    sc.main(["rcfence", "upsert", str(rc), str(block_file)])
    assert rc.read_text() == "export A=1\n\n" + BLOCK + "export B=2\n"
    assert "Shell aliases updated" in capsys.readouterr().out


def test_rcfence_upsert_is_idempotent(tmp_path, block_file, capsys):
    rc = tmp_path / ".zshrc"
    rc.write_text("export A=1\n")
    sc.main(["rcfence", "upsert", str(rc), str(block_file)])
    first = rc.read_text()
    capsys.readouterr()
    sc.main(["rcfence", "upsert", str(rc), str(block_file)])
    assert rc.read_text() == first
    assert "already current" in capsys.readouterr().out


@pytest.mark.parametrize("original", ["export A=1\n", "", "export A=1\n\nexport B=2\n"])
def test_rcfence_remove_restores_original(tmp_path, block_file, original):
    rc = tmp_path / ".zshrc"
    rc.write_text(original)
    sc.main(["rcfence", "upsert", str(rc), str(block_file)])
    assert sc.main(["rcfence", "remove", str(rc)]) == 0
    assert rc.read_text() == original


def test_rcfence_remove_keeps_content_after_fence(tmp_path):
    rc = tmp_path / ".zshrc"
    rc.write_text("export A=1\n\n" + BLOCK + "export B=2\n")
    sc.main(["rcfence", "remove", str(rc)])
    assert rc.read_text() == "export A=1\n\nexport B=2\n"


def test_rcfence_remove_without_fence_is_noop(tmp_path, capsys):
    rc = tmp_path / ".zshrc"
    rc.write_text("export A=1\n")
    sc.main(["rcfence", "remove", str(rc)])
    assert rc.read_text() == "export A=1\n"
    assert "No agent-skills aliases" in capsys.readouterr().out


def test_rcfence_missing_rcfile_is_noop(tmp_path, block_file, capsys):
    assert sc.main(["rcfence", "upsert", str(tmp_path / ".zshrc"), str(block_file)]) == 0
    assert "left alone" in capsys.readouterr().out
