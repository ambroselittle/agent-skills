"""Scaffold a project from Jinja2 templates, and set up scaffolded projects.

Renders template files using a layered hierarchy, each overriding the previous:
  1. templates/__common/           — universal files (all templates)
  2. templates/__common/<platform>/ — platform-specific shared files (ts, python, etc.)
  3. templates/<base_template>/     — base template files (if 'extends' declared in template.json)
  4. templates/<template_name>/     — template-specific files

When a template declares ``"extends": "<base>"`` in its template.json, the base
template's files are rendered as layer 3 before the child template's own files.
Files matching any ``"exclude"`` glob patterns are skipped from the base layer.

The platform is determined by template.json in the template directory (or inherited
from the base template if the child doesn't declare one).

The ``setup_project()`` function handles everything needed to get a working project
AFTER templates are rendered: installing dependencies, running setup scripts,
starting docker/postgres, pushing database schemas, etc.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
COMMON_DIR_NAME = "__common"
J2_EXTENSION = ".j2"


def normalize_version_key(package_name: str) -> str:
    """Normalize an npm package name to a template variable key.

    Examples:
        @hono/node-server -> hono_node_server
        @prisma/client -> prisma_client
        @biomejs/biome -> biomejs_biome
        react -> react
    """
    key = package_name.lstrip("@")
    return key.replace("/", "_").replace("-", "_").replace(".", "_")


def normalize_versions(versions: dict) -> dict:
    """Accept versions in either npm-name or underscore-key format and normalize."""
    normalized = {}
    for key, value in versions.items():
        normalized[normalize_version_key(key)] = value
    return normalized


def to_pascal_case(kebab_name: str) -> str:
    """Convert a kebab-case name to PascalCase.

    Examples:
        my-app -> MyApp
        cool-project -> CoolProject
        single -> Single
        a -> A
    """
    return "".join(word.capitalize() for word in kebab_name.split("-"))


def build_context(project_name: str, versions: dict) -> dict:
    """Build the Jinja2 template context from project config."""
    # Derive the npm scope from the project name (e.g., my-app -> @my-app)
    scope = f"@{project_name}"
    return {
        "project_name": project_name,
        "scope": scope,
        "swift_project_name": to_pascal_case(project_name),
        "versions": normalize_versions(versions),
    }


_DIR_VAR_RE = re.compile(r"__([a-zA-Z_][a-zA-Z0-9_]*)__")


def _substitute_dir_vars(path: Path, context: dict) -> Path:
    """Substitute ``__variable_name__`` markers in path segments.

    For each segment containing ``__var__``, look up ``var`` in context.
    If found, replace the marker with the value. If not found, leave
    the segment unchanged (handles names like ``__pycache__``).
    """
    parts = list(path.parts)
    changed = False
    for i, part in enumerate(parts):
        if "__" not in part:
            continue

        def _replace(m: re.Match) -> str:
            var_name = m.group(1)
            if var_name in context:
                return str(context[var_name])
            return m.group(0)  # leave unchanged

        new_part = _DIR_VAR_RE.sub(_replace, part)
        if new_part != part:
            parts[i] = new_part
            changed = True

    return Path(*parts) if changed else path


def render_template_dir(
    env: Environment,
    source_dir: Path,
    output_dir: Path,
    context: dict,
    base_dir: Path,
    exclude_dirs: set[Path] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[Path]:
    """Render all files in a template directory tree.

    .j2 files are rendered through Jinja2; other files are copied as-is.
    Directories in exclude_dirs are skipped entirely.
    Files matching exclude_patterns (fnmatch globs against the relative path
    from base_dir) are skipped.

    Directory names containing ``__variable_name__`` markers are substituted
    from the context dict (e.g., ``Sources/__swift_project_name__/`` becomes
    ``Sources/MyApp/`` when ``context["swift_project_name"] == "MyApp"``).
    Unknown variables are left as-is (handles ``__pycache__`` etc.).

    Returns list of created file paths.
    """
    created: list[Path] = []
    exclude_dirs = exclude_dirs or set()
    exclude_patterns = exclude_patterns or []

    for source_path in sorted(source_dir.rglob("*")):
        if source_path.is_dir():
            continue
        # Skip files under excluded directories
        if any(source_path.is_relative_to(d) for d in exclude_dirs):
            continue
        # Skip scaffold metadata files
        if source_path.name == "template.json":
            continue

        rel_path = source_path.relative_to(base_dir)

        # Skip files matching exclude patterns
        if exclude_patterns and _matches_exclude(str(rel_path), exclude_patterns):
            continue

        # Substitute __variable_name__ markers in directory path segments
        rel_path = _substitute_dir_vars(rel_path, context)

        # Render the path itself (strip .j2 extension)
        if source_path.suffix == J2_EXTENSION:
            dest_path = output_dir / rel_path.with_suffix("")
        else:
            dest_path = output_dir / rel_path

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.suffix == J2_EXTENSION:
            # Render through Jinja2
            template_name = str(source_path.relative_to(env.loader.searchpath[0]))
            template = env.get_template(template_name)
            content = template.render(**context)
            dest_path.write_text(content)
        else:
            # Copy as-is
            shutil.copy2(source_path, dest_path)

        # Preserve executable bit
        if source_path.stat().st_mode & stat.S_IXUSR:
            dest_path.chmod(dest_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        created.append(dest_path)

    return created


@dataclass
class TemplateConfig:
    """Configuration read from a template's template.json."""

    platform: str | list[str] | None = None
    extends: str | None = None
    exclude: list[str] = field(default_factory=list)


def read_template_config(template_dir: Path) -> TemplateConfig:
    """Read configuration from a template's template.json."""
    template_json = template_dir / "template.json"
    if not template_json.exists():
        return TemplateConfig()
    data = json.loads(template_json.read_text())
    return TemplateConfig(
        platform=data.get("platform"),
        extends=data.get("extends"),
        exclude=data.get("exclude", []),
    )


def _matches_exclude(rel_path: str, exclude_patterns: list[str]) -> bool:
    """Check if a relative path matches any exclude glob pattern."""
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def scaffold(
    project_name: str,
    template_name: str,
    versions: dict,
    output_dir: Path,
) -> list[Path]:
    """Scaffold a project from templates.

    Renders up to 4 layers in order, each overriding the previous:
      1. __common/              — universal files
      2. __common/<platform>/   — platform-specific shared files
      3. <base_template>/       — base template files (if ``extends`` declared)
      4. <template_name>/       — template-specific files

    Returns list of all created file paths.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    common_dir = TEMPLATES_DIR / COMMON_DIR_NAME
    template_dir = TEMPLATES_DIR / template_name

    if not template_dir.is_dir():
        available = [
            d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir() and d.name != COMMON_DIR_NAME
        ]
        raise FileNotFoundError(f"Template '{template_name}' not found. Available: {available}")

    config = read_template_config(template_dir)

    # Resolve the base template if extends is declared
    base_dir: Path | None = None
    base_config: TemplateConfig | None = None
    if config.extends:
        base_dir = TEMPLATES_DIR / config.extends
        if not base_dir.is_dir():
            raise FileNotFoundError(
                f"Base template '{config.extends}' not found (extended by '{template_name}')"
            )
        # Reject chained extends — keep it simple for now
        base_config = read_template_config(base_dir)
        if base_config.extends:
            raise ValueError(
                f"Chained extends not supported: '{template_name}' extends "
                f"'{config.extends}' which extends '{base_config.extends}'"
            )

    # Inherit platform from base if child doesn't declare one
    platform = config.platform
    if not platform and base_config:
        platform = base_config.platform

    # Normalize platform to a list for uniform iteration
    if isinstance(platform, str):
        platforms = [platform]
    elif isinstance(platform, list):
        platforms = platform
    else:
        platforms = []

    context = build_context(project_name, versions)

    # Use the templates root as the Jinja2 search path so we can reference
    # all layers
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    created: list[Path] = []

    # Layer 1: Universal common files (exclude platform subdirectories)
    if common_dir.is_dir():
        platform_dirs = {
            d for d in common_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
        }
        created.extend(
            render_template_dir(
                env,
                common_dir,
                output_dir,
                context,
                common_dir,
                exclude_dirs=platform_dirs,
            )
        )

    # Layer 2: Platform-specific common files (e.g., __common/ts/, __common/python/)
    # When multiple platforms are declared, each is applied in order (later overrides earlier).
    for plat in platforms:
        platform_dir = common_dir / plat
        if platform_dir.is_dir():
            created.extend(
                render_template_dir(env, platform_dir, output_dir, context, platform_dir)
            )

    # Layer 3: Base template files (if extends), with exclude patterns applied
    if base_dir:
        created.extend(
            render_template_dir(
                env,
                base_dir,
                output_dir,
                context,
                base_dir,
                exclude_patterns=config.exclude,
            )
        )

    # Layer 4: Template-specific files
    created.extend(render_template_dir(env, template_dir, output_dir, context, template_dir))

    return created


# ---------------------------------------------------------------------------
# Setup: install deps, docker, db for a scaffolded project
# ---------------------------------------------------------------------------


@dataclass
class SetupStepResult:
    name: str
    passed: bool
    duration_s: float
    error: str | None = None


@dataclass
class SetupResult:
    steps: list[SetupStepResult] = field(default_factory=list)
    api_port: int = 3001
    web_port: int = 3000

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.steps)


def _run_setup_step(
    name: str, cmd: list[str], cwd: Path, timeout: int = 300, env: dict | None = None
) -> SetupStepResult:
    """Run a single setup step and return the result."""
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = time.monotonic() - start
        if proc.returncode != 0:
            parts = [s for s in (proc.stderr.strip(), proc.stdout.strip()) if s]
            error = "\n".join(parts) if parts else f"Exit code {proc.returncode}"
            if len(error) > 2000:
                error = error[:2000] + "\n... (truncated)"
            return SetupStepResult(name=name, passed=False, duration_s=elapsed, error=error)
        return SetupStepResult(name=name, passed=True, duration_s=elapsed)
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return SetupStepResult(
            name=name, passed=False, duration_s=elapsed, error=f"Timed out after {timeout}s"
        )
    except FileNotFoundError:
        elapsed = time.monotonic() - start
        return SetupStepResult(
            name=name, passed=False, duration_s=elapsed, error=f"Command not found: {cmd[0]}"
        )


def _read_dotenv(dotenv_file: Path) -> dict[str, str]:
    """Parse a .env file and return key-value pairs (ignores comments and blanks)."""
    if not dotenv_file.exists():
        return {}
    result: dict[str, str] = {}
    for line in dotenv_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _start_postgres_setup(project_dir: Path, result: SetupResult, skip_docker: bool) -> bool:
    """Start Postgres via docker compose if needed. Returns True if ready."""
    if skip_docker:
        return True

    step = _run_setup_step(
        "docker compose up", ["docker", "compose", "up", "-d"], project_dir, timeout=60
    )
    result.steps.append(step)
    if not step.passed:
        return False

    # Wait for Postgres health check
    step = _run_setup_step(
        "postgres health",
        ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
        project_dir,
        timeout=30,
    )
    for _ in range(5):
        if step.passed:
            break
        time.sleep(2)
        step = _run_setup_step(
            "postgres health",
            ["docker", "compose", "exec", "-T", "postgres", "pg_isready", "-U", "postgres"],
            project_dir,
            timeout=10,
        )
    result.steps.append(step)
    return step.passed


def _setup_node(project_dir: Path, skip_docker: bool) -> SetupResult:
    """Set up a Node/TypeScript project after scaffolding."""
    result = SetupResult()

    # Step 1: Install dependencies
    step = _run_setup_step("pnpm install", ["pnpm", "install"], project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Run project setup (port discovery + .env generation)
    setup_script = project_dir / "scripts" / "setup.ts"
    if setup_script.exists() and not skip_docker:
        step = _run_setup_step("setup", ["pnpm", "project:setup"], project_dir, timeout=30)
        result.steps.append(step)
        if not step.passed:
            return result

    # Read discovered ports
    ports_file = project_dir / ".env.ports"
    if ports_file.exists():
        for line in ports_file.read_text().splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                if key == "API_PORT":
                    result.api_port = int(val)
                elif key == "WEB_PORT":
                    result.web_port = int(val)

    # Step 3: Generate Prisma client + barrel exports
    step = _run_setup_step(
        "prisma generate",
        ["pnpm", "--filter", "**/db", "run", "generate"],
        project_dir,
        timeout=60,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 4: Auto-format with Biome (fix formatting drift from generation)
    step = _run_setup_step("biome format", ["pnpm", "lint:fix"], project_dir, timeout=60)
    result.steps.append(step)
    # Non-fatal — continue even if format step fails

    # Step 5: Start Postgres
    if not _start_postgres_setup(project_dir, result, skip_docker):
        return result

    # Step 6: Push database schema
    step = _run_setup_step("db push", ["pnpm", "db:push"], project_dir, timeout=60)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 7: Seed database (non-fatal)
    step = _run_setup_step("db seed", ["pnpm", "db:seed"], project_dir, timeout=60)
    result.steps.append(step)

    return result


def _setup_python(project_dir: Path, skip_docker: bool) -> SetupResult:
    """Set up a Python (FastAPI/uv) project after scaffolding."""
    result = SetupResult(api_port=8000)

    # Step 1: Install dependencies (prefer Python 3.13)
    uv_sync_cmd = ["uv", "sync"]
    try:
        subprocess.run(["uv", "python", "find", "3.13"], capture_output=True, check=True)
        uv_sync_cmd = ["uv", "sync", "--python", "3.13"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    step = _run_setup_step("uv sync", uv_sync_cmd, project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Run project setup (port discovery + .env generation)
    setup_script = project_dir / "scripts" / "setup.py"
    dotenv: dict[str, str] = {}
    if setup_script.exists() and not skip_docker:
        step = _run_setup_step(
            "setup", ["uv", "run", "python", "scripts/setup.py"], project_dir, timeout=30
        )
        result.steps.append(step)
        if not step.passed:
            return result

    # Read discovered ports
    dotenv = _read_dotenv(project_dir / ".env")
    if "API_PORT" in dotenv:
        result.api_port = int(dotenv["API_PORT"])

    # Step 3: Start Postgres
    if not _start_postgres_setup(project_dir, result, skip_docker):
        return result

    # Step 4: Run Alembic migrations
    alembic_dirs = list(project_dir.glob("apps/*/alembic.ini"))
    alembic_env = {**os.environ}
    if "DATABASE_URL" in dotenv:
        alembic_env["DATABASE_URL"] = dotenv["DATABASE_URL"]
    for alembic_ini in alembic_dirs:
        app_dir = alembic_ini.parent
        app_name = app_dir.name
        step = _run_setup_step(
            f"alembic upgrade ({app_name})",
            ["uv", "run", "alembic", "upgrade", "head"],
            app_dir,
            timeout=300,
            env=alembic_env,
        )
        result.steps.append(step)
        if not step.passed:
            return result

    return result


def _setup_fullstack_python(project_dir: Path, skip_docker: bool) -> SetupResult:
    """Set up a fullstack-python project (React frontend + FastAPI backend)."""
    result = SetupResult(api_port=8000)

    # Step 1a: Install Python dependencies (prefer Python 3.13)
    uv_sync_cmd = ["uv", "sync"]
    try:
        subprocess.run(["uv", "python", "find", "3.13"], capture_output=True, check=True)
        uv_sync_cmd = ["uv", "sync", "--python", "3.13"]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    step = _run_setup_step("uv sync", uv_sync_cmd, project_dir, timeout=120)
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 1b: Install web dependencies
    step = _run_setup_step(
        "pnpm install (web)",
        ["pnpm", "install", "--dir", "apps/web"],
        project_dir,
        timeout=120,
    )
    result.steps.append(step)
    if not step.passed:
        return result

    # Step 2: Run project setup (port discovery + .env generation)
    setup_script = project_dir / "scripts" / "setup.py"
    dotenv: dict[str, str] = {}
    if setup_script.exists() and not skip_docker:
        step = _run_setup_step(
            "setup", ["uv", "run", "python", "scripts/setup.py"], project_dir, timeout=30
        )
        result.steps.append(step)
        if not step.passed:
            return result

    # Read discovered ports
    dotenv = _read_dotenv(project_dir / ".env")
    if "API_PORT" in dotenv:
        result.api_port = int(dotenv["API_PORT"])
    if "WEB_PORT" in dotenv:
        result.web_port = int(dotenv["WEB_PORT"])

    # Step 3: Start Postgres
    if not _start_postgres_setup(project_dir, result, skip_docker):
        return result

    # Step 4: Run Alembic migrations
    alembic_dirs = list(project_dir.glob("apps/*/alembic.ini"))
    alembic_env = {**os.environ}
    if "DATABASE_URL" in dotenv:
        alembic_env["DATABASE_URL"] = dotenv["DATABASE_URL"]
    for alembic_ini in alembic_dirs:
        app_dir = alembic_ini.parent
        app_name = app_dir.name
        step = _run_setup_step(
            f"alembic upgrade ({app_name})",
            ["uv", "run", "alembic", "upgrade", "head"],
            app_dir,
            timeout=300,
            env=alembic_env,
        )
        result.steps.append(step)
        if not step.passed:
            return result

    return result


def setup_project(project_dir: Path, skip_docker: bool = False) -> SetupResult:
    """Set up a scaffolded project: install deps, docker, db.

    Detects the platform and runs the appropriate setup steps.
    This should be called AFTER scaffolding and BEFORE verification.

    Args:
        project_dir: Path to the scaffolded project.
        skip_docker: Skip docker compose (Postgres already available, e.g., CI).

    Returns:
        SetupResult with step-by-step pass/fail and discovered ports.
    """
    from scripts.verify import detect_platform

    project_dir = Path(project_dir).resolve()
    platform = detect_platform(project_dir)

    if platform in ("node", "swift-ts"):
        return _setup_node(project_dir, skip_docker)
    elif platform == "fullstack-python":
        return _setup_fullstack_python(project_dir, skip_docker)
    elif platform == "python":
        return _setup_python(project_dir, skip_docker)
    else:
        return _setup_node(project_dir, skip_docker)


def print_setup_results(result: SetupResult) -> None:
    """Print setup results as a formatted table."""
    if not result.steps:
        print("\nNo setup steps were run.")
        return

    name_width = max(len(s.name) for s in result.steps)

    print(f"\n{'Step':<{name_width}}  {'Time':>7}  Result")
    print(f"{'-' * name_width}  {'-' * 7}  {'-' * 10}")

    for s in result.steps:
        symbol = "\u2705" if s.passed else "\u274c"
        time_str = f"{s.duration_s:.1f}s"
        print(f"{s.name:<{name_width}}  {time_str:>7}  {symbol} {'pass' if s.passed else 'FAIL'}")
        if s.error:
            for line in s.error.split("\n")[:5]:
                print(f"  {line}")

    if result.passed:
        print("\nSetup completed successfully!")
    else:
        failed = [s.name for s in result.steps if not s.passed]
        print(f"\nSetup failed: {', '.join(failed)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a project from templates")

    # Setup mode: set up an already-scaffolded project
    parser.add_argument(
        "--setup",
        metavar="DIR",
        help="Set up an already-scaffolded project (install deps, docker, db)",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip docker compose (Postgres already available)",
    )

    # Scaffold mode: render templates
    parser.add_argument("--project-name", help="Project name (lowercase-hyphenated)")
    parser.add_argument("--template", help="Template name (e.g. fullstack-ts)")
    parser.add_argument("--versions", help="Path to versions.json")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove existing output directory before scaffolding",
    )

    args = parser.parse_args()

    # Handle --setup mode
    if args.setup:
        result = setup_project(Path(args.setup), skip_docker=args.skip_docker)
        print_setup_results(result)
        if not result.passed:
            sys.exit(1)
        return

    # Scaffold mode requires all rendering arguments
    if not args.project_name or not args.template or not args.versions or not args.output:
        parser.error("Scaffold mode requires: --project-name, --template, --versions, --output")

    if args.force:
        output = Path(args.output)
        if output.exists():
            shutil.rmtree(output)
            print(f"Removed existing {args.output}")

    with open(args.versions) as f:
        versions = json.load(f)

    try:
        created = scaffold(args.project_name, args.template, versions, Path(args.output))
        print(f"Scaffolded {len(created)} files to {args.output}")
    except (FileExistsError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
