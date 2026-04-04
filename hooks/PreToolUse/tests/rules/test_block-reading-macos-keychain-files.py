"""Tests for rule: Block reading macOS Keychain files."""
from pathlib import Path


from engine import evaluate

HOME = str(Path.home())
REPO = "/repo/myproject"

RULE_DESCRIPTION = "Block reading macOS Keychain files"
RULE_ID = "block-keychain-reads"


def _payload(tool_name, tool_input, cwd=REPO):
    return {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}


def test_match(rule):
    """Read tool on ~/Library/Keychains/login.keychain-db is denied."""
    payload = _payload("Read", {"file_path": f"{HOME}/Library/Keychains/login.keychain-db"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"
    assert "Keychain" in result["reason"]


def test_no_match(rule):
    """Read tool on a regular project file is not denied."""
    payload = _payload("Read", {"file_path": f"{REPO}/main.py"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_bash_cat(rule):
    """cat ~/Library/Keychains/login.keychain-db via Bash is also denied."""
    payload = _payload("Bash", {"command": f"cat {HOME}/Library/Keychains/login.keychain-db"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_system_keychain(rule):
    """Reads to /Library/Keychains/ (system keychain) are also denied."""
    payload = _payload("Read", {"file_path": "/Library/Keychains/System.keychain"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "deny"


def test_boundary_other_library_dir_allowed(rule):
    """Reading ~/Library/Preferences/ is not matched — only Keychains is blocked."""
    payload = _payload("Read", {"file_path": f"{HOME}/Library/Preferences/com.apple.finder.plist"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"


def test_boundary_hexdump_keychain_not_caught(rule):
    """hexdump via Bash falls through — read-path only extracts paths from cat.
    The security denylist in bash-safe catches the primary Keychain CLI vector."""
    payload = _payload("Bash", {"command": f"hexdump {HOME}/Library/Keychains/login.keychain-db"})
    result = evaluate(payload, [rule], repo_root=REPO)
    assert result["decision"] == "proceed"
