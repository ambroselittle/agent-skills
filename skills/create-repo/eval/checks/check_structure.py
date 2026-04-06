"""Structural checks for scaffolded projects.

Verifies that the scaffolded output has the expected files, configuration,
and conventions without needing to install or run anything. Platform-aware:
checks differ for Node/TS vs Python projects.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.models import CheckResult


def _detect_platform(project_dir: Path) -> str:
    """Detect platform from scaffolded output."""
    # Mixed platform: both Python and Node files present
    if (project_dir / "pyproject.toml").exists() and (project_dir / "package.json").exists():
        return "fullstack-python"
    if (project_dir / "pyproject.toml").exists():
        return "python"
    return "node"


def check_structure(project_dir: Path, template: str) -> list[CheckResult]:
    """Run all structural checks against a scaffolded project."""
    checks: list[CheckResult] = []
    platform = _detect_platform(project_dir)

    # --- Universal file checks (all templates) ---

    universal_files = [
        ".gitignore",
        "docker-compose.yml",
        ".env.example",
        "CLAUDE.md",
        ".claude/rules/testing.md",
        ".github/workflows/ci.yml",
        ".github/pull_request_template.md",
    ]
    for f in universal_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # --- Platform-specific common checks ---

    if platform == "node":
        node_common_files = [
            "package.json",
            "pnpm-workspace.yaml",
            "turbo.json",
            "biome.json",
            ".claude/rules/modules.md",
            ".claude/rules/types.md",
        ]
        for f in node_common_files:
            path = project_dir / f
            checks.append(CheckResult(
                f"file: {f}",
                path.exists(),
                None if path.exists() else f"Missing: {f}",
            ))

    elif platform == "python":
        python_common_files = [
            "pyproject.toml",
            "justfile",
            ".claude/rules/modules.md",
            ".claude/rules/types.md",
        ]
        for f in python_common_files:
            path = project_dir / f
            checks.append(CheckResult(
                f"file: {f}",
                path.exists(),
                None if path.exists() else f"Missing: {f}",
            ))

    elif platform == "fullstack-python":
        # Mixed platform: both Python and Node common files
        mixed_common_files = [
            "pyproject.toml",
            "justfile",
            "package.json",
            "pnpm-workspace.yaml",
            "biome.json",
            ".claude/rules/modules.md",
            ".claude/rules/types.md",
        ]
        for f in mixed_common_files:
            path = project_dir / f
            checks.append(CheckResult(
                f"file: {f}",
                path.exists(),
                None if path.exists() else f"Missing: {f}",
            ))
        # turbo.json should NOT exist
        turbo_path = project_dir / "turbo.json"
        checks.append(CheckResult(
            "no turbo.json",
            not turbo_path.exists(),
            "turbo.json exists but should not for fullstack-python" if turbo_path.exists() else None,
        ))

    # --- Template-specific checks ---

    if template == "fullstack-ts":
        _check_fullstack_ts(project_dir, checks)
    elif template == "fullstack-graphql":
        _check_fullstack_graphql(project_dir, checks)
    elif template == "api-ts":
        _check_api_ts(project_dir, checks)
    elif template == "api-python":
        _check_api_python(project_dir, checks)
    elif template == "fullstack-python":
        _check_fullstack_python(project_dir, checks)

    # --- Content checks (universal) ---

    # docker-compose.yml has postgres service
    dc_path = project_dir / "docker-compose.yml"
    if dc_path.exists():
        dc_content = dc_path.read_text()
        has_postgres = "postgres" in dc_content
        checks.append(CheckResult(
            "docker-compose has postgres",
            has_postgres,
        ))

    # No unrendered Jinja2 in output files
    unrendered = []
    for f in project_dir.rglob("*"):
        if f.is_file() and f.suffix != ".j2":
            try:
                content = f.read_text(errors="ignore")
                if "{{" in content and "}}" in content:
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


def _check_node_ts_common(project_dir: Path, checks: list[CheckResult]) -> None:
    """Shared checks for Node/TS fullstack templates (fullstack-ts, fullstack-graphql)."""
    # package.json content checks
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

    # turbo.json pipelines
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

    # biome.json noExplicitAny
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

    # tsconfig strict
    tsconfig_path = project_dir / "tsconfig.json"
    if tsconfig_path.exists():
        tsconfig = json.loads(tsconfig_path.read_text())
        strict = tsconfig.get("compilerOptions", {}).get("strict")
        checks.append(CheckResult(
            "tsconfig strict: true",
            strict is True,
            None if strict is True else f"strict is {strict}",
        ))

    # Test files per app (only check apps that exist)
    for app_name in ("web", "api"):
        app_path = f"apps/{app_name}"
        test_dir = "__tests__"
        if (project_dir / app_path).exists():
            test_path = project_dir / app_path / test_dir
            has_tests = test_path.exists() and any(test_path.iterdir())
            checks.append(CheckResult(
                f"{app_path} has tests",
                has_tests,
                None if has_tests else f"No test files in {app_path}/{test_dir}",
            ))

    # Seed script
    seed_path = project_dir / "packages" / "db" / "prisma" / "seed.ts"
    checks.append(CheckResult(
        "seed script exists",
        seed_path.exists(),
    ))


def _check_fullstack_ts(project_dir: Path, checks: list[CheckResult]) -> None:
    """Template-specific checks for fullstack-ts."""
    ts_files = [
        "tsconfig.json",
        "apps/web/package.json",
        "apps/web/src/main.tsx",
        "apps/web/src/App.tsx",
        "apps/web/src/lib/trpc.ts",
        "apps/web/vite.config.ts",
        "apps/web/__tests__/App.test.tsx",
        "apps/api/package.json",
        "apps/api/src/index.ts",
        "apps/api/src/router.ts",
        "apps/api/src/trpc.ts",
        "apps/api/__tests__/router.test.ts",
        "packages/db/package.json",
        "packages/db/prisma/schema.prisma",
        "packages/db/prisma/seed.ts",
        "packages/db/src/index.ts",
        "packages/types/package.json",
        "packages/types/src/index.ts",
        "packages/config/tsconfig.base.json",
    ]
    for f in ts_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    _check_node_ts_common(project_dir, checks)


def _check_fullstack_graphql(project_dir: Path, checks: list[CheckResult]) -> None:
    """Template-specific checks for fullstack-graphql."""
    gql_files = [
        "tsconfig.json",
        "apps/web/package.json",
        "apps/web/src/main.tsx",
        "apps/web/src/App.tsx",
        "apps/web/src/lib/apollo.ts",
        "apps/web/vite.config.ts",
        "apps/web/__tests__/App.test.tsx",
        "apps/web/codegen.ts",
        "apps/api/package.json",
        "apps/api/src/index.ts",
        "apps/api/src/schema.ts",
        "apps/api/src/yoga.ts",
        "apps/api/src/context.ts",
        "apps/api/__tests__/schema.test.ts",
        "apps/api/scripts/print-schema.ts",
        "packages/db/package.json",
        "packages/db/prisma/schema.prisma",
        "packages/db/prisma/seed.ts",
        "packages/db/src/index.ts",
        "packages/types/package.json",
        "packages/types/src/index.ts",
        "packages/config/tsconfig.base.json",
    ]
    for f in gql_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    _check_node_ts_common(project_dir, checks)


def _check_api_ts(project_dir: Path, checks: list[CheckResult]) -> None:
    """Template-specific checks for api-ts."""
    api_ts_files = [
        "tsconfig.json",
        "apps/api/package.json",
        "apps/api/src/index.ts",
        "apps/api/src/router.ts",
        "apps/api/src/trpc.ts",
        "apps/api/__tests__/router.test.ts",
        "apps/api/playwright.config.ts",
        "apps/api/e2e/smoke.test.ts",
        "apps/api/e2e/users.test.ts",
        "packages/db/package.json",
        "packages/db/prisma/schema.prisma",
        "packages/db/prisma/seed.ts",
        "packages/db/src/index.ts",
        "packages/types/package.json",
        "packages/types/src/index.ts",
        "packages/config/tsconfig.base.json",
        "scripts/setup.ts",
        "scripts/discover-ports.ts",
    ]
    for f in api_ts_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # apps/web should NOT exist
    web_dir = project_dir / "apps" / "web"
    checks.append(CheckResult(
        "no apps/web directory",
        not web_dir.exists(),
        "apps/web/ exists but should not for api-ts template" if web_dir.exists() else None,
    ))

    # api package.json should have Playwright and test:e2e
    api_pkg_path = project_dir / "apps" / "api" / "package.json"
    if api_pkg_path.exists():
        api_pkg = json.loads(api_pkg_path.read_text())
        has_playwright = "@playwright/test" in api_pkg.get("devDependencies", {})
        checks.append(CheckResult(
            "api has @playwright/test",
            has_playwright,
            None if has_playwright else "Missing @playwright/test in api devDependencies",
        ))
        has_e2e_script = "test:e2e" in api_pkg.get("scripts", {})
        checks.append(CheckResult(
            "api has test:e2e script",
            has_e2e_script,
            None if has_e2e_script else "Missing test:e2e script in api package.json",
        ))

    _check_node_ts_common(project_dir, checks)


def _check_api_python(project_dir: Path, checks: list[CheckResult]) -> None:
    """Template-specific checks for api-python."""
    python_files = [
        "apps/api/pyproject.toml",
        "apps/api/src/__init__.py",
        "apps/api/src/main.py",
        "apps/api/src/database.py",
        "apps/api/src/models.py",
        "apps/api/src/routes/__init__.py",
        "apps/api/src/routes/users.py",
        "apps/api/tests/__init__.py",
        "apps/api/tests/conftest.py",
        "apps/api/tests/test_health.py",
        "apps/api/tests/test_users.py",
        "apps/api/alembic.ini",
        "apps/api/alembic/env.py",
    ]
    for f in python_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # Root pyproject.toml has uv workspace config
    root_pyproject = project_dir / "pyproject.toml"
    if root_pyproject.exists():
        content = root_pyproject.read_text()
        has_workspace = "[tool.uv.workspace]" in content
        checks.append(CheckResult(
            "root pyproject.toml has uv workspace",
            has_workspace,
            None if has_workspace else "Missing [tool.uv.workspace] in root pyproject.toml",
        ))

    # apps/api/pyproject.toml has expected dependencies
    api_pyproject = project_dir / "apps" / "api" / "pyproject.toml"
    if api_pyproject.exists():
        content = api_pyproject.read_text()
        for dep in ("fastapi", "sqlmodel"):
            has_dep = dep in content
            checks.append(CheckResult(
                f"api pyproject.toml has {dep}",
                has_dep,
                None if has_dep else f"Missing {dep} in apps/api/pyproject.toml",
            ))

    # Test files exist
    test_dir = project_dir / "apps" / "api" / "tests"
    has_tests = test_dir.exists() and any(f for f in test_dir.iterdir() if f.name.startswith("test_"))
    checks.append(CheckResult(
        "apps/api has tests",
        has_tests,
        None if has_tests else "No test_*.py files in apps/api/tests/",
    ))


def _check_fullstack_python(project_dir: Path, checks: list[CheckResult]) -> None:
    """Template-specific checks for fullstack-python."""
    # Web app files (inherited from fullstack-ts + overrides)
    web_files = [
        "apps/web/package.json",
        "apps/web/src/main.tsx",
        "apps/web/src/App.tsx",
        "apps/web/src/lib/api.ts",
        "apps/web/vite.config.ts",
        "apps/web/__tests__/App.test.tsx",
        "apps/web/playwright.config.ts",
        "apps/web/e2e/smoke.test.ts",
        "apps/web/e2e/users.test.ts",
        "apps/web/e2e/pages/base.page.ts",
        "apps/web/e2e/pages/home.page.ts",
    ]
    for f in web_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # Python API files
    api_files = [
        "apps/api/pyproject.toml",
        "apps/api/src/__init__.py",
        "apps/api/src/main.py",
        "apps/api/src/database.py",
        "apps/api/src/models.py",
        "apps/api/src/routes/__init__.py",
        "apps/api/src/routes/users.py",
        "apps/api/tests/__init__.py",
        "apps/api/tests/conftest.py",
        "apps/api/tests/test_health.py",
        "apps/api/tests/test_users.py",
        "apps/api/alembic.ini",
        "apps/api/alembic/env.py",
    ]
    for f in api_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"file: {f}",
            path.exists(),
            None if path.exists() else f"Missing: {f}",
        ))

    # tRPC files should NOT exist
    trpc_files = [
        "apps/web/src/lib/trpc.ts",
        "apps/api/src/router.ts",
        "apps/api/src/trpc.ts",
    ]
    for f in trpc_files:
        path = project_dir / f
        checks.append(CheckResult(
            f"no tRPC: {f}",
            not path.exists(),
            f"{f} exists but should not for fullstack-python" if path.exists() else None,
        ))

    # No packages/ directory (Prisma not used)
    packages_dir = project_dir / "packages"
    checks.append(CheckResult(
        "no packages/ directory",
        not packages_dir.exists(),
        "packages/ exists but should not for fullstack-python" if packages_dir.exists() else None,
    ))

    # Root pyproject.toml has uv workspace config
    root_pyproject = project_dir / "pyproject.toml"
    if root_pyproject.exists():
        content = root_pyproject.read_text()
        has_workspace = "[tool.uv.workspace]" in content
        checks.append(CheckResult(
            "root pyproject.toml has uv workspace",
            has_workspace,
            None if has_workspace else "Missing [tool.uv.workspace] in root pyproject.toml",
        ))

    # API deps check
    api_pyproject = project_dir / "apps" / "api" / "pyproject.toml"
    if api_pyproject.exists():
        content = api_pyproject.read_text()
        for dep in ("fastapi", "sqlmodel"):
            has_dep = dep in content
            checks.append(CheckResult(
                f"api pyproject.toml has {dep}",
                has_dep,
                None if has_dep else f"Missing {dep} in apps/api/pyproject.toml",
            ))

    # Vite proxy defaults to port 8000
    vite_config = project_dir / "apps" / "web" / "vite.config.ts"
    if vite_config.exists():
        content = vite_config.read_text()
        has_8000 = '"8000"' in content
        checks.append(CheckResult(
            "vite proxy defaults to port 8000",
            has_8000,
            None if has_8000 else "vite.config.ts should default API_PORT to 8000",
        ))
