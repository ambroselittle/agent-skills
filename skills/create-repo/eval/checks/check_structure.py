"""Structural checks for scaffolded projects.

Verifies that the scaffolded output has the expected files, configuration,
and conventions without needing to install or run anything.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.models import CheckResult


def check_structure(project_dir: Path, template: str) -> list[CheckResult]:
    """Run all structural checks against a scaffolded project."""
    checks: list[CheckResult] = []

    # --- File existence checks ---

    # Common files (all templates)
    common_files = [
        "package.json",
        "pnpm-workspace.yaml",
        "turbo.json",
        ".gitignore",
        "biome.json",
        "docker-compose.yml",
        ".env.example",
        "CLAUDE.md",
        ".claude/rules/testing.md",
        ".claude/rules/modules.md",
        ".claude/rules/types.md",
        ".github/workflows/ci.yml",
        ".github/pull_request_template.md",
    ]
    for f in common_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # Shared fullstack files (both fullstack-ts and fullstack-graphql)
    fullstack_shared_files = [
        "tsconfig.json",
        "apps/web/package.json",
        "apps/web/src/main.tsx",
        "apps/web/src/App.tsx",
        "apps/web/vite.config.ts",
        "apps/web/__tests__/App.test.tsx",
        "apps/api/package.json",
        "apps/api/src/index.ts",
        "packages/db/package.json",
        "packages/db/prisma/schema.prisma",
        "packages/db/prisma/seed.ts",
        "packages/db/src/index.ts",
        "packages/types/package.json",
        "packages/types/src/index.ts",
        "packages/config/tsconfig.base.json",
    ]

    # Template-specific files
    if template == "fullstack-ts":
        ts_files = fullstack_shared_files + [
            "apps/web/src/lib/trpc.ts",
            "apps/api/src/router.ts",
            "apps/api/src/trpc.ts",
            "apps/api/__tests__/router.test.ts",
        ]
        for f in ts_files:
            path = project_dir / f
            checks.append(CheckResult(
                f"file: {f}",
                path.exists(),
                None if path.exists() else f"Missing: {f}",
            ))

    elif template == "fullstack-graphql":
        gql_files = fullstack_shared_files + [
            "apps/web/src/lib/apollo.ts",
            "apps/api/src/schema.ts",
            "apps/api/src/yoga.ts",
            "apps/api/src/context.ts",
            "apps/api/__tests__/schema.test.ts",
        ]
        for f in gql_files:
            path = project_dir / f
            checks.append(CheckResult(
                f"file: {f}",
                path.exists(),
                None if path.exists() else f"Missing: {f}",
            ))

    # --- Content checks ---

    # package.json has expected dependencies
    pkg_path = project_dir / "package.json"
    if pkg_path.exists():
        pkg = json.loads(pkg_path.read_text())
        has_biome = "@biomejs/biome" in pkg.get("devDependencies", {})
        checks.append(CheckResult(
            "root package.json has biome",
            has_biome,
            None if has_biome else "Missing @biomejs/biome in devDependencies",
        ))
        has_turbo = "turbo" in pkg.get("devDependencies", {})
        checks.append(CheckResult(
            "root package.json has turbo",
            has_turbo,
            None if has_turbo else "Missing turbo in devDependencies",
        ))

    # turbo.json has expected pipelines
    turbo_path = project_dir / "turbo.json"
    if turbo_path.exists():
        turbo = json.loads(turbo_path.read_text())
        tasks = turbo.get("tasks", {})
        expected_tasks = ["build", "dev", "test", "typecheck", "lint"]
        for task in expected_tasks:
            has_task = task in tasks
            checks.append(CheckResult(
                f"turbo.json has '{task}' task",
                has_task,
                None if has_task else f"Missing task: {task}",
            ))

    # biome.json has noExplicitAny
    biome_path = project_dir / "biome.json"
    if biome_path.exists():
        biome = json.loads(biome_path.read_text())
        no_any = (
            biome.get("linter", {})
            .get("rules", {})
            .get("suspicious", {})
            .get("noExplicitAny")
        )
        checks.append(CheckResult(
            "biome noExplicitAny is error",
            no_any == "error",
            None if no_any == "error" else f"noExplicitAny is '{no_any}', expected 'error'",
        ))

    # tsconfig has strict: true
    if template in ("fullstack-ts", "fullstack-graphql"):
        tsconfig_path = project_dir / "tsconfig.json"
        if tsconfig_path.exists():
            tsconfig = json.loads(tsconfig_path.read_text())
            strict = tsconfig.get("compilerOptions", {}).get("strict")
            checks.append(CheckResult(
                "tsconfig strict: true",
                strict is True,
                None if strict is True else f"strict is {strict}",
            ))

    # docker-compose.yml has postgres service
    dc_path = project_dir / "docker-compose.yml"
    if dc_path.exists():
        dc_content = dc_path.read_text()
        has_postgres = "postgres" in dc_content
        checks.append(CheckResult(
            "docker-compose has postgres",
            has_postgres,
        ))

    # At least one test file per app/package
    if template in ("fullstack-ts", "fullstack-graphql"):
        test_locations = [
            ("apps/web", "__tests__"),
            ("apps/api", "__tests__"),
        ]
        for app_path, test_dir in test_locations:
            test_path = project_dir / app_path / test_dir
            has_tests = test_path.exists() and any(test_path.iterdir())
            checks.append(CheckResult(
                f"{app_path} has tests",
                has_tests,
                None if has_tests else f"No test files in {app_path}/{test_dir}",
            ))

    # Seed script exists
    seed_path = project_dir / "packages" / "db" / "prisma" / "seed.ts"
    if template in ("fullstack-ts", "fullstack-graphql"):
        checks.append(CheckResult(
            "seed script exists",
            seed_path.exists(),
        ))

    # No unrendered Jinja2 in output files
    unrendered = []
    for f in project_dir.rglob("*"):
        if f.is_file() and f.suffix != ".j2":
            try:
                content = f.read_text(errors="ignore")
                if "{{" in content and "}}" in content:
                    # Check it's not a legitimate use (e.g., in a template literal)
                    # Simple heuristic: if {{ appears with a space after, it's likely Jinja2
                    if "{{ " in content:
                        unrendered.append(str(f.relative_to(project_dir)))
            except Exception:
                pass

    checks.append(CheckResult(
        "no unrendered Jinja2",
        len(unrendered) == 0,
        f"Found unrendered templates in: {', '.join(unrendered[:5])}" if unrendered else None,
    ))

    return checks
