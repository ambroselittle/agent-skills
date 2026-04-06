"""Tests for the eval framework."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eval.run_eval import run_eval


def test_eval_fullstack_ts_passes():
    result = run_eval("fullstack-ts")
    assert result.passed, [
        f"{c.name}: {c.detail}" for c in result.checks if not c.passed
    ]
    assert result.pass_count > 40  # Expect at least 40 checks


def test_eval_api_python_passes():
    result = run_eval("api-python")
    assert result.passed, [
        f"{c.name}: {c.detail}" for c in result.checks if not c.passed
    ]
    assert result.pass_count > 15  # Expect at least 15 checks


def test_eval_unknown_template_fails():
    result = run_eval("not-a-template")
    assert not result.passed
    assert result.checks[0].name == "scaffold"
    assert not result.checks[0].passed


@pytest.mark.e2e
def test_eval_fullstack_ts_full_verify(tmp_path):
    """Scaffold a fullstack-ts project and run the full verification pipeline.

    Requires: pnpm, node, and either Docker (local) or DATABASE_URL env var (CI).
    Run with: uv run pytest tests/ -v -m e2e

    Uses tmp_path so the scaffolded project (~200MB with node_modules) is
    auto-cleaned by pytest instead of accumulating in .eval-runs/.
    """
    # Use skip_docker when DATABASE_URL is set (CI provides Postgres as a service)
    skip_docker = "DATABASE_URL" in os.environ

    output_dir = tmp_path / "eval-project"
    result = run_eval("fullstack-ts", output_dir=output_dir, full=True, skip_docker=skip_docker)
    assert result.passed, [
        f"{c.name}: {c.detail}" for c in result.checks if not c.passed
    ]

    # Should have structural checks + verify steps
    verify_checks = [c for c in result.checks if c.name.startswith("verify:")]
    assert len(verify_checks) > 0, "Expected verify steps to run"
