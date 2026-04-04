"""Tests for the scaffold engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.scaffold import build_context, normalize_version_key, scaffold

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def versions() -> dict:
    """Minimal versions dict for testing."""
    return {
        "react": "19.1.0",
        "react_dom": "19.1.0",
        "typescript": "5.8.3",
        "vite": "6.3.0",
        "vitest": "3.1.1",
        "hono": "4.7.6",
        "hono_node_server": "1.19.12",
        "tailwindcss": "4.1.3",
        "tailwindcss_vite": "4.1.3",
        "prisma": "7.5.0",
        "prisma_client": "7.5.0",
        "biomejs_biome": "2.0.0",
        "trpc_server": "11.1.0",
        "trpc_client": "11.1.0",
        "trpc_react_query": "11.1.0",
        "hono_trpc_server": "0.3.2",
        "tanstack_react_query": "5.74.4",
        "types_react": "19.1.2",
        "types_react_dom": "19.1.2",
        "vitejs_plugin_react": "4.4.1",
        "playwright": "1.59.1",
        "playwright_test": "1.59.1",
        "prisma_adapter_pg": "7.5.0",
        "pnpm": "10.33.0",
    }


# --- normalize_version_key ---


def test_normalize_version_key_scoped():
    assert normalize_version_key("@hono/node-server") == "hono_node_server"
    assert normalize_version_key("@prisma/client") == "prisma_client"
    assert normalize_version_key("@biomejs/biome") == "biomejs_biome"


def test_normalize_version_key_simple():
    assert normalize_version_key("react") == "react"
    assert normalize_version_key("typescript") == "typescript"


def test_normalize_version_key_already_normalized():
    assert normalize_version_key("hono_node_server") == "hono_node_server"


def test_build_context_normalizes_versions():
    ctx = build_context("my-app", {"@prisma/client": "6.0.0", "react": "19.0.0"})
    assert ctx["versions"]["prisma_client"] == "6.0.0"
    assert ctx["versions"]["react"] == "19.0.0"


# --- build_context ---


def test_build_context():
    ctx = build_context("my-app", {"react": "19.0.0"})
    assert ctx["project_name"] == "my-app"
    assert ctx["scope"] == "@my-app"
    assert ctx["versions"]["react"] == "19.0.0"


# --- scaffold ---


def test_scaffold_fullstack_ts_creates_expected_structure(tmp_path, versions):
    output = tmp_path / "my-app"
    created = scaffold("my-app", "fullstack-ts", versions, output)

    assert len(created) > 0

    # Check key files exist
    assert (output / "package.json").exists()
    assert (output / "pnpm-workspace.yaml").exists()
    assert (output / "turbo.json").exists()
    assert (output / "tsconfig.json").exists()
    assert (output / "biome.json").exists()
    assert (output / "docker-compose.yml").exists()
    assert (output / ".gitignore").exists()
    assert (output / ".env.example").exists()
    assert (output / "CLAUDE.md").exists()
    assert (output / ".claude" / "rules" / "testing.md").exists()
    assert (output / ".claude" / "rules" / "modules.md").exists()
    assert (output / ".claude" / "rules" / "types.md").exists()
    assert (output / ".github" / "workflows" / "ci.yml").exists()
    assert (output / ".github" / "pull_request_template.md").exists()

    # Apps
    assert (output / "apps" / "web" / "package.json").exists()
    assert (output / "apps" / "web" / "src" / "App.tsx").exists()
    assert (output / "apps" / "web" / "src" / "main.tsx").exists()
    assert (output / "apps" / "web" / "vite.config.ts").exists()
    assert (output / "apps" / "web" / "__tests__" / "App.test.tsx").exists()
    assert (output / "apps" / "api" / "package.json").exists()
    assert (output / "apps" / "api" / "src" / "index.ts").exists()
    assert (output / "apps" / "api" / "src" / "router.ts").exists()
    assert (output / "apps" / "api" / "__tests__" / "router.test.ts").exists()

    # E2E testing
    assert (output / "apps" / "web" / "playwright.config.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "pages" / "base.page.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "pages" / "home.page.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "smoke.test.ts").exists()
    assert (output / ".claude" / "rules" / "e2e-testing.md").exists()
    assert (output / ".claude" / "rules" / "flakiness-practices.md").exists()

    # Prisma 7 files
    assert (output / "packages" / "db" / "prisma.config.ts").exists()
    assert (output / "packages" / "db" / "scripts" / "generate-barrel.ts").exists()

    # Scripts
    assert (output / "scripts" / "cleanup-samples.ts").exists()
    assert (output / "scripts" / "discover-ports.ts").exists()
    assert (output / "scripts" / "setup.ts").exists()

    # Vite
    assert (output / "apps" / "web" / "src" / "vite-env.d.ts").exists()

    # Packages
    assert (output / "packages" / "db" / "package.json").exists()
    assert (output / "packages" / "db" / "prisma" / "schema.prisma").exists()
    assert (output / "packages" / "db" / "prisma" / "seed.ts").exists()
    assert (output / "packages" / "db" / "src" / "index.ts").exists()
    assert (output / "packages" / "types" / "package.json").exists()
    assert (output / "packages" / "types" / "src" / "index.ts").exists()
    assert (output / "packages" / "config" / "tsconfig.base.json").exists()


def test_scaffold_renders_jinja2_variables(tmp_path, versions):
    output = tmp_path / "cool-project"
    scaffold("cool-project", "fullstack-ts", versions, output)

    # Root package.json should have the project name
    root_pkg = json.loads((output / "package.json").read_text())
    assert root_pkg["name"] == "cool-project"

    # Web package.json should use the scope
    web_pkg = json.loads((output / "apps" / "web" / "package.json").read_text())
    assert web_pkg["name"] == "@cool-project/web"

    # Versions should be substituted
    assert versions["react"] in web_pkg["dependencies"]["react"]

    # CLAUDE.md should have the project name
    claude_md = (output / "CLAUDE.md").read_text()
    assert "cool-project" in claude_md

    # docker-compose should use project-specific db name
    docker_compose = (output / "docker-compose.yml").read_text()
    assert "cool-project_dev" in docker_compose


def test_scaffold_copies_non_template_files_as_is(tmp_path, versions):
    output = tmp_path / "my-app"
    scaffold("my-app", "fullstack-ts", versions, output)

    # .gitignore should be copied without modification (no .j2 rendering)
    gitignore = (output / ".gitignore").read_text()
    assert "node_modules/" in gitignore
    assert "{{" not in gitignore  # No unrendered Jinja2


def test_scaffold_j2_extension_stripped(tmp_path, versions):
    output = tmp_path / "my-app"
    scaffold("my-app", "fullstack-ts", versions, output)

    # .j2 files should have the extension stripped
    assert not (output / "package.json.j2").exists()
    assert (output / "package.json").exists()
    assert not (output / "docker-compose.yml.j2").exists()
    assert (output / "docker-compose.yml").exists()


def test_scaffold_rejects_non_empty_output_dir(tmp_path, versions):
    output = tmp_path / "my-app"
    output.mkdir()
    (output / "existing-file.txt").write_text("hello")

    with pytest.raises(FileExistsError):
        scaffold("my-app", "fullstack-ts", versions, output)


def test_scaffold_unknown_template(tmp_path, versions):
    with pytest.raises(FileNotFoundError, match="not-a-template"):
        scaffold("my-app", "not-a-template", versions, tmp_path / "out")


def test_scaffold_template_overrides_common(tmp_path, versions):
    """Template-specific files should override common files with same path."""
    output = tmp_path / "my-app"
    scaffold("my-app", "fullstack-ts", versions, output)

    # Both common and fullstack-ts provide files — template-specific wins
    # The .gitignore comes from common (fullstack-ts doesn't override it)
    gitignore = (output / ".gitignore").read_text()
    assert "node_modules/" in gitignore
