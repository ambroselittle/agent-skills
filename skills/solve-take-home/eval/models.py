"""Shared data models for the eval framework."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str | None = None


@dataclass
class EvalResult:
    fixture: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)
