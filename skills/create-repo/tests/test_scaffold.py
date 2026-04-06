"""Tests for the scaffold engine."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.scaffold import (
    TEMPLATES_DIR,
    build_context,
    normalize_version_key,
    read_template_config,
    scaffold,
)

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
        "jsdom": "25.0.1",
        "testing_library_react": "16.3.2",
        "testing_library_jest_dom": "6.9.1",
        "dotenv": "17.4.1",
        "pnpm": "10.33.0",
        # GraphQL stack
        "graphql": "16.13.2",
        "graphql_yoga": "5.21.0",
        "pothos_core": "4.12.0",
        "apollo_client": "4.1.6",
        "graphql_codegen_cli": "6.2.1",
        "graphql_codegen_introspection": "5.0.1",
        "graphql_codegen_near_operation_file_preset": "5.0.0",
        "graphql_codegen_typed_document_node": "6.1.7",
        "graphql_codegen_typescript": "5.0.9",
        "graphql_codegen_typescript_operations": "5.0.9",
        "graphql_typed_document_node_core": "3.2.0",
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


def test_scaffold_fullstack_graphql_creates_expected_structure(tmp_path, versions):
    output = tmp_path / "my-app"
    created = scaffold("my-app", "fullstack-graphql", versions, output)

    assert len(created) > 0

    # Common files (inherited from templates/__common/ + __common/ts/)
    assert (output / "package.json").exists()
    assert (output / "pnpm-workspace.yaml").exists()
    assert (output / "turbo.json").exists()
    assert (output / "tsconfig.json").exists()
    assert (output / "biome.json").exists()
    assert (output / "docker-compose.yml").exists()
    assert (output / ".gitignore").exists()
    assert (output / "CLAUDE.md").exists()
    assert (output / ".github" / "workflows" / "ci.yml").exists()

    # GraphQL-specific API files
    assert (output / "apps" / "api" / "package.json").exists()
    assert (output / "apps" / "api" / "src" / "index.ts").exists()
    assert (output / "apps" / "api" / "src" / "schema.ts").exists()
    assert (output / "apps" / "api" / "src" / "yoga.ts").exists()
    assert (output / "apps" / "api" / "src" / "context.ts").exists()
    assert (output / "apps" / "api" / "__tests__" / "schema.test.ts").exists()

    # Codegen
    assert (output / "apps" / "api" / "scripts" / "print-schema.ts").exists()
    assert (output / "apps" / "web" / "codegen.ts").exists()

    # tRPC files should NOT exist
    assert not (output / "apps" / "api" / "src" / "router.ts").exists()
    assert not (output / "apps" / "api" / "src" / "trpc.ts").exists()
    assert not (output / "apps" / "api" / "__tests__" / "router.test.ts").exists()
    assert not (output / "apps" / "web" / "src" / "lib" / "trpc.ts").exists()

    # Apollo Client frontend
    assert (output / "apps" / "web" / "package.json").exists()
    assert (output / "apps" / "web" / "src" / "App.tsx").exists()
    assert (output / "apps" / "web" / "src" / "lib" / "apollo.ts").exists()
    assert (output / "apps" / "web" / "src" / "main.tsx").exists()
    assert (output / "apps" / "web" / "vite.config.ts").exists()
    assert (output / "apps" / "web" / "__tests__" / "App.test.tsx").exists()

    # E2E testing
    assert (output / "apps" / "web" / "playwright.config.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "smoke.test.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "users.test.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "pages" / "base.page.ts").exists()
    assert (output / "apps" / "web" / "e2e" / "pages" / "home.page.ts").exists()

    # Prisma 7 (shared with fullstack-ts)
    assert (output / "packages" / "db" / "package.json").exists()
    assert (output / "packages" / "db" / "prisma.config.ts").exists()
    assert (output / "packages" / "db" / "prisma" / "schema.prisma").exists()
    assert (output / "packages" / "db" / "prisma" / "seed.ts").exists()
    assert (output / "packages" / "db" / "src" / "index.ts").exists()

    # Scripts
    assert (output / "scripts" / "cleanup-samples.ts").exists()
    assert (output / "scripts" / "discover-ports.ts").exists()
    assert (output / "scripts" / "setup.ts").exists()


def test_scaffold_fullstack_graphql_renders_variables(tmp_path, versions):
    output = tmp_path / "gql-app"
    scaffold("gql-app", "fullstack-graphql", versions, output)

    # Root package.json should have the project name
    root_pkg = json.loads((output / "package.json").read_text())
    assert root_pkg["name"] == "gql-app"

    # Web package.json should use scope and Apollo deps
    web_pkg = json.loads((output / "apps" / "web" / "package.json").read_text())
    assert web_pkg["name"] == "@gql-app/web"
    assert "@apollo/client" in web_pkg["dependencies"]
    assert "graphql" in web_pkg["dependencies"]
    # Codegen devDependencies
    assert "@graphql-codegen/cli" in web_pkg.get("devDependencies", {})
    assert "@graphql-codegen/typed-document-node" in web_pkg.get("devDependencies", {})
    # Should NOT have tRPC deps
    assert "@trpc/client" not in web_pkg.get("dependencies", {})
    assert "@tanstack/react-query" not in web_pkg.get("dependencies", {})

    # API package.json should have GraphQL deps
    api_pkg = json.loads((output / "apps" / "api" / "package.json").read_text())
    assert "graphql-yoga" in api_pkg["dependencies"]
    assert "@pothos/core" in api_pkg["dependencies"]
    assert "graphql" in api_pkg["dependencies"]
    # Should NOT have tRPC deps
    assert "@trpc/server" not in api_pkg.get("dependencies", {})
    assert "@hono/trpc-server" not in api_pkg.get("dependencies", {})

    # Versions should be substituted
    assert versions["graphql_yoga"] in api_pkg["dependencies"]["graphql-yoga"]

    # Schema file should use the scope
    schema_ts = (output / "apps" / "api" / "src" / "schema.ts").read_text()
    assert "@gql-app/db" in schema_ts

    # Apollo client should reference /api/graphql
    apollo_ts = (output / "apps" / "web" / "src" / "lib" / "apollo.ts").read_text()
    assert "/api/graphql" in apollo_ts

    # App should use ApolloProvider and codegen graphql()
    app_tsx = (output / "apps" / "web" / "src" / "App.tsx").read_text()
    assert "ApolloProvider" in app_tsx
    assert "HealthDocument" in app_tsx
    assert "trpc" not in app_tsx.lower()

    # Cleanup script should target schema.ts not router.ts
    cleanup = (output / "scripts" / "cleanup-samples.ts").read_text()
    assert "schema.ts" in cleanup
    assert "router.ts" not in cleanup


def test_scaffold_template_overrides_common(tmp_path, versions):
    """Template-specific files should override common files with same path."""
    output = tmp_path / "my-app"
    scaffold("my-app", "fullstack-ts", versions, output)

    # Both __common/ and __common/ts/ provide files — platform layer wins
    # The .gitignore comes from __common/ (no TS override)
    gitignore = (output / ".gitignore").read_text()
    assert "node_modules/" in gitignore


# --- api-python scaffold ---


@pytest.fixture
def python_versions() -> dict:
    """Minimal versions dict for api-python testing."""
    return {
        "fastapi": "0.115.12",
        "sqlmodel": "0.0.24",
        "sqlalchemy": "2.0.40",
        "pydantic": "2.11.4",
        "uvicorn": "0.34.3",
        "alembic": "1.15.2",
        "pytest": "8.4.1",
        "httpx": "0.28.1",
        "ruff": "0.11.12",
    }


def test_scaffold_api_python_creates_expected_structure(tmp_path, python_versions):
    output = tmp_path / "my-api"
    created = scaffold("my-api", "api-python", python_versions, output)

    assert len(created) > 0

    # Root workspace files
    assert (output / "pyproject.toml").exists()
    assert (output / "justfile").exists()
    assert (output / ".gitignore").exists()
    assert (output / "docker-compose.yml").exists()
    assert (output / ".env.example").exists()
    assert (output / "CLAUDE.md").exists()
    assert (output / ".claude" / "rules" / "testing.md").exists()
    assert (output / ".claude" / "rules" / "modules.md").exists()
    assert (output / ".claude" / "rules" / "types.md").exists()
    assert (output / ".github" / "workflows" / "ci.yml").exists()
    assert (output / ".github" / "pull_request_template.md").exists()

    # API app
    assert (output / "apps" / "api" / "pyproject.toml").exists()
    assert (output / "apps" / "api" / "src" / "__init__.py").exists()
    assert (output / "apps" / "api" / "src" / "main.py").exists()
    assert (output / "apps" / "api" / "src" / "database.py").exists()
    assert (output / "apps" / "api" / "src" / "models.py").exists()
    assert (output / "apps" / "api" / "src" / "routes" / "__init__.py").exists()
    assert (output / "apps" / "api" / "src" / "routes" / "users.py").exists()

    # Tests
    assert (output / "apps" / "api" / "tests" / "__init__.py").exists()
    assert (output / "apps" / "api" / "tests" / "conftest.py").exists()
    assert (output / "apps" / "api" / "tests" / "test_health.py").exists()
    assert (output / "apps" / "api" / "tests" / "test_users.py").exists()

    # Alembic
    assert (output / "apps" / "api" / "alembic.ini").exists()
    assert (output / "apps" / "api" / "alembic" / "env.py").exists()
    assert (output / "apps" / "api" / "alembic" / "script.py.mako").exists()
    assert (output / "apps" / "api" / "alembic" / "versions" / "001_create_user_table.py").exists()

    # Should NOT have TS-specific files
    assert not (output / "package.json").exists()
    assert not (output / "biome.json").exists()
    assert not (output / "turbo.json").exists()
    assert not (output / "tsconfig.json").exists()
    assert not (output / "template.json").exists()


def test_scaffold_api_python_renders_jinja2_variables(tmp_path, python_versions):
    output = tmp_path / "cool-api"
    scaffold("cool-api", "api-python", python_versions, output)

    # Root pyproject.toml has project name and workspace config
    root_pyproject = (output / "pyproject.toml").read_text()
    assert 'name = "cool-api"' in root_pyproject
    assert "[tool.uv.workspace]" in root_pyproject

    # API pyproject.toml has versions substituted
    api_pyproject = (output / "apps" / "api" / "pyproject.toml").read_text()
    assert python_versions["fastapi"] in api_pyproject
    assert python_versions["sqlmodel"] in api_pyproject

    # CLAUDE.md has the project name
    claude_md = (output / "CLAUDE.md").read_text()
    assert "cool-api" in claude_md

    # docker-compose has project-specific db name
    docker_compose = (output / "docker-compose.yml").read_text()
    assert "cool-api_dev" in docker_compose

    # alembic.ini has project-specific db name
    alembic_ini = (output / "apps" / "api" / "alembic.ini").read_text()
    assert "cool-api_dev" in alembic_ini


def test_scaffold_api_python_has_python_gitignore(tmp_path, python_versions):
    output = tmp_path / "my-api"
    scaffold("my-api", "api-python", python_versions, output)

    gitignore = (output / ".gitignore").read_text()
    assert "__pycache__/" in gitignore
    assert ".venv/" in gitignore
    assert ".ruff_cache/" in gitignore
    # Should NOT have node_modules (overridden by python layer)
    assert "node_modules/" not in gitignore


def test_scaffold_api_python_ci_uses_uv(tmp_path, python_versions):
    output = tmp_path / "my-api"
    scaffold("my-api", "api-python", python_versions, output)

    ci = (output / ".github" / "workflows" / "ci.yml").read_text()
    assert "uv sync" in ci
    assert "just" in ci
    # Should NOT have pnpm/node steps
    assert "pnpm" not in ci


# --- extends / exclude ---


@pytest.fixture
def _setup_extends_templates(tmp_path, monkeypatch):
    """Create minimal base + child templates for extends/exclude tests.

    Patches TEMPLATES_DIR so scaffold() uses these instead of the real ones.
    """
    templates = tmp_path / "templates"
    templates.mkdir()

    # __common layer
    common = templates / "__common"
    common.mkdir()
    (common / "shared.txt").write_text("from-common")

    # Base template
    base = templates / "base-tmpl"
    base.mkdir(parents=True)
    (base / "template.json").write_text(json.dumps({"platform": None}))
    (base / "base-file.txt").write_text("from-base")
    (base / "override-me.txt").write_text("base-version")
    sub = base / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("base-deep")
    (sub / "excluded.txt").write_text("should-be-excluded")

    # Child template (extends base, excludes sub/excluded.txt)
    child = templates / "child-tmpl"
    child.mkdir(parents=True)
    (child / "template.json").write_text(json.dumps({
        "extends": "base-tmpl",
        "exclude": ["sub/excluded.txt"],
    }))
    (child / "child-file.txt").write_text("from-child")
    (child / "override-me.txt").write_text("child-version")

    monkeypatch.setattr("scripts.scaffold.TEMPLATES_DIR", templates)
    monkeypatch.setattr("scripts.scaffold.COMMON_DIR_NAME", "__common")

    return templates


def test_extends_pulls_files_from_base(_setup_extends_templates, tmp_path):
    output = tmp_path / "project"
    scaffold("test-proj", "child-tmpl", {}, output)

    # Base file should be inherited
    assert (output / "base-file.txt").exists()
    assert (output / "base-file.txt").read_text() == "from-base"
    # Deep base file should be inherited
    assert (output / "sub" / "deep.txt").exists()
    assert (output / "sub" / "deep.txt").read_text() == "base-deep"


def test_exclude_prevents_base_files(_setup_extends_templates, tmp_path):
    output = tmp_path / "project"
    scaffold("test-proj", "child-tmpl", {}, output)

    # Excluded file should NOT be present
    assert not (output / "sub" / "excluded.txt").exists()


def test_child_overrides_base_files(_setup_extends_templates, tmp_path):
    output = tmp_path / "project"
    scaffold("test-proj", "child-tmpl", {}, output)

    # Child's override-me.txt should win over base's
    assert (output / "override-me.txt").read_text() == "child-version"


def test_common_layers_still_apply_with_extends(_setup_extends_templates, tmp_path):
    output = tmp_path / "project"
    scaffold("test-proj", "child-tmpl", {}, output)

    # __common files should be present
    assert (output / "shared.txt").exists()
    assert (output / "shared.txt").read_text() == "from-common"


def test_child_specific_files_present(_setup_extends_templates, tmp_path):
    output = tmp_path / "project"
    scaffold("test-proj", "child-tmpl", {}, output)

    assert (output / "child-file.txt").exists()
    assert (output / "child-file.txt").read_text() == "from-child"


def test_chained_extends_raises(tmp_path, monkeypatch):
    """Extending a template that itself extends another should raise."""
    templates = tmp_path / "templates"
    templates.mkdir()

    # __common (required by scaffold)
    common = templates / "__common"
    common.mkdir()

    # Grandparent
    gp = templates / "grandparent"
    gp.mkdir()
    (gp / "template.json").write_text(json.dumps({}))
    (gp / "gp.txt").write_text("gp")

    # Parent (extends grandparent)
    parent = templates / "parent"
    parent.mkdir()
    (parent / "template.json").write_text(json.dumps({"extends": "grandparent"}))

    # Child (extends parent — should fail)
    child = templates / "child"
    child.mkdir()
    (child / "template.json").write_text(json.dumps({"extends": "parent"}))

    monkeypatch.setattr("scripts.scaffold.TEMPLATES_DIR", templates)
    monkeypatch.setattr("scripts.scaffold.COMMON_DIR_NAME", "__common")

    output = tmp_path / "out"
    with pytest.raises(ValueError, match="Chained extends not supported"):
        scaffold("test", "child", {}, output)


def test_exclude_glob_pattern(tmp_path, monkeypatch):
    """Glob patterns like 'apps/web/**' should exclude entire subtrees."""
    templates = tmp_path / "templates"
    templates.mkdir()

    common = templates / "__common"
    common.mkdir()

    base = templates / "base"
    base.mkdir()
    (base / "template.json").write_text(json.dumps({}))
    (base / "keep.txt").write_text("keep")
    web = base / "apps" / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<html>")
    (web / "app.js").write_text("app()")
    api = base / "apps" / "api"
    api.mkdir(parents=True)
    (api / "server.js").write_text("serve()")

    child = templates / "api-only"
    child.mkdir()
    (child / "template.json").write_text(json.dumps({
        "extends": "base",
        "exclude": ["apps/web/**"],
    }))

    monkeypatch.setattr("scripts.scaffold.TEMPLATES_DIR", templates)
    monkeypatch.setattr("scripts.scaffold.COMMON_DIR_NAME", "__common")

    output = tmp_path / "out"
    scaffold("test", "api-only", {}, output)

    assert (output / "keep.txt").exists()
    assert (output / "apps" / "api" / "server.js").exists()
    assert not (output / "apps" / "web").exists()


def test_extends_inherits_platform(tmp_path, monkeypatch):
    """Child without platform should inherit from base."""
    templates = tmp_path / "templates"
    templates.mkdir()

    common = templates / "__common"
    common.mkdir()
    ts_dir = common / "ts"
    ts_dir.mkdir()
    (ts_dir / "biome.json").write_text("{}")

    base = templates / "base"
    base.mkdir()
    (base / "template.json").write_text(json.dumps({"platform": "ts"}))
    (base / "base.txt").write_text("base")

    child = templates / "child"
    child.mkdir()
    # No platform declared — should inherit "ts" from base
    (child / "template.json").write_text(json.dumps({"extends": "base"}))

    monkeypatch.setattr("scripts.scaffold.TEMPLATES_DIR", templates)
    monkeypatch.setattr("scripts.scaffold.COMMON_DIR_NAME", "__common")

    output = tmp_path / "out"
    scaffold("test", "child", {}, output)

    # Platform files should be present (inherited from base's platform)
    assert (output / "biome.json").exists()


def test_extends_base_not_found(tmp_path, monkeypatch):
    """Extending a nonexistent template should raise FileNotFoundError."""
    templates = tmp_path / "templates"
    templates.mkdir()

    common = templates / "__common"
    common.mkdir()

    child = templates / "child"
    child.mkdir()
    (child / "template.json").write_text(json.dumps({"extends": "nonexistent"}))

    monkeypatch.setattr("scripts.scaffold.TEMPLATES_DIR", templates)
    monkeypatch.setattr("scripts.scaffold.COMMON_DIR_NAME", "__common")

    output = tmp_path / "out"
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        scaffold("test", "child", {}, output)
