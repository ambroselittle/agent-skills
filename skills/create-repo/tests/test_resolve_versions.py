"""Tests for the resolve_versions module."""

from __future__ import annotations

import pytest
from scripts.resolve_versions import (
    COMPAT_GROUPS,
    PACKAGE_REGISTRY,
    _major,
    check_compatibility,
    discover_required_keys,
)
from scripts.scaffold import TEMPLATES_DIR

# --- discover_required_keys ---


AVAILABLE_TEMPLATES = [
    d.name
    for d in TEMPLATES_DIR.iterdir()
    if d.is_dir() and d.name != "__common" and not d.name.startswith(".")
]


@pytest.mark.parametrize("template", AVAILABLE_TEMPLATES)
def test_discover_returns_nonempty_keys(template: str):
    """Every template should need at least some version keys."""
    keys = discover_required_keys(template)
    assert len(keys) > 0, f"Template '{template}' discovered no version keys"


@pytest.mark.parametrize("template", AVAILABLE_TEMPLATES)
def test_all_discovered_keys_are_in_registry(template: str):
    """Every version key used in templates must have a PACKAGE_REGISTRY entry."""
    keys = discover_required_keys(template)
    unmapped = keys - PACKAGE_REGISTRY.keys()
    assert not unmapped, (
        f"Template '{template}' uses version keys not in PACKAGE_REGISTRY: {sorted(unmapped)}. "
        "Add them to PACKAGE_REGISTRY in scripts/resolve_versions.py."
    )


def test_discover_fullstack_ts_has_expected_keys():
    """Spot-check: fullstack-ts should need react, hono, prisma, trpc, etc."""
    keys = discover_required_keys("fullstack-ts")
    expected = {"react", "hono", "prisma", "trpc_server", "typescript", "vite", "vitest"}
    assert expected.issubset(keys), f"Missing expected keys: {expected - keys}"


def test_discover_swift_ts_has_no_trpc():
    """swift-ts uses REST, not tRPC — should not require tRPC version keys."""
    keys = discover_required_keys("swift-ts")
    trpc_keys = {k for k in keys if "trpc" in k}
    assert not trpc_keys, f"swift-ts should not need tRPC keys: {trpc_keys}"


def test_discover_api_python_has_python_packages():
    """api-python should need fastapi, sqlmodel, etc."""
    keys = discover_required_keys("api-python")
    expected = {"fastapi", "sqlmodel", "pytest", "ruff"}
    assert expected.issubset(keys), f"Missing expected keys: {expected - keys}"


def test_discover_nonexistent_template_raises():
    with pytest.raises(FileNotFoundError):
        discover_required_keys("nonexistent-template")


# --- check_compatibility ---


def test_compat_all_matching():
    """No errors when all versions in a group share the same major."""
    versions = {"prisma": "7.6.0", "prisma_client": "7.6.0", "prisma_adapter_pg": "7.6.0"}
    assert check_compatibility(versions) == []


def test_compat_mismatch_detected():
    """Detect when major versions disagree within a group."""
    versions = {"prisma": "7.6.0", "prisma_client": "6.5.0", "prisma_adapter_pg": "7.6.0"}
    errors = check_compatibility(versions)
    assert len(errors) == 1
    assert "prisma" in errors[0]


def test_compat_ignores_absent_keys():
    """Groups with 0 or 1 present keys should not produce errors."""
    versions = {"prisma": "7.6.0"}  # Only one from the group
    assert check_compatibility(versions) == []


def test_compat_multiple_groups_checked():
    """Multiple groups can each report errors independently."""
    versions = {
        "prisma": "7.0.0",
        "prisma_client": "6.0.0",
        "react": "19.0.0",
        "react_dom": "18.0.0",
    }
    errors = check_compatibility(versions)
    assert len(errors) == 2


def test_compat_trpc_group():
    versions = {
        "trpc_server": "11.16.0",
        "trpc_client": "11.16.0",
        "trpc_react_query": "11.16.0",
    }
    assert check_compatibility(versions) == []


def test_compat_trpc_mismatch():
    versions = {
        "trpc_server": "11.16.0",
        "trpc_client": "10.5.0",
    }
    errors = check_compatibility(versions)
    assert len(errors) == 1


# --- _major ---


def test_major_simple():
    assert _major("19.2.4") == "19"


def test_major_zero():
    assert _major("0.4.2") == "0"


def test_major_single_digit():
    assert _major("7") == "7"


# --- PACKAGE_REGISTRY consistency ---


def test_registry_keys_are_normalized():
    """All registry keys should be valid underscore-format keys (no @, /, -)."""
    for key in PACKAGE_REGISTRY:
        assert "@" not in key, f"Key '{key}' contains @"
        assert "/" not in key, f"Key '{key}' contains /"
        assert "-" not in key, f"Key '{key}' contains -"


def test_registry_has_no_duplicate_package_names():
    """Two different keys should not map to the same package name."""
    seen: dict[str, str] = {}
    for key, (pkg, _registry) in PACKAGE_REGISTRY.items():
        assert pkg not in seen.values() or seen[pkg] == key, (
            f"Duplicate package '{pkg}' mapped by both '{seen[pkg]}' and '{key}'"
        )
        seen[pkg] = key


def test_compat_groups_reference_valid_registry_keys():
    """Every key in COMPAT_GROUPS should exist in PACKAGE_REGISTRY."""
    for group in COMPAT_GROUPS:
        for key in group:
            assert key in PACKAGE_REGISTRY, (
                f"COMPAT_GROUPS references '{key}' which is not in PACKAGE_REGISTRY"
            )
