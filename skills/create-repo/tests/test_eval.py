"""Tests for the eval framework."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.run_eval import run_eval


def test_eval_fullstack_ts_passes():
    result = run_eval("fullstack-ts")
    assert result.passed, [
        f"{c.name}: {c.detail}" for c in result.checks if not c.passed
    ]
    assert result.pass_count > 40  # Expect at least 40 checks


def test_eval_unknown_template_fails():
    result = run_eval("not-a-template")
    assert not result.passed
    assert result.checks[0].name == "scaffold"
    assert not result.checks[0].passed
