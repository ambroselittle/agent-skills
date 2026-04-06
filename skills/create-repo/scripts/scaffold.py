"""Scaffold a project from Jinja2 templates.

Renders template files using a 3-layer hierarchy:
  1. templates/__common/           — universal files (all templates)
  2. templates/__common/<platform>/ — platform-specific shared files (ts, python, etc.)
  3. templates/<template_name>/     — template-specific files

Each layer overrides files from previous layers at the same path.
The platform is determined by template.json in the template directory.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
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


def build_context(project_name: str, versions: dict) -> dict:
    """Build the Jinja2 template context from project config."""
    # Derive the npm scope from the project name (e.g., my-app -> @my-app)
    scope = f"@{project_name}"
    return {
        "project_name": project_name,
        "scope": scope,
        "versions": normalize_versions(versions),
    }


def render_template_dir(
    env: Environment,
    source_dir: Path,
    output_dir: Path,
    context: dict,
    base_dir: Path,
    exclude_dirs: set[Path] | None = None,
) -> list[Path]:
    """Render all files in a template directory tree.

    .j2 files are rendered through Jinja2; other files are copied as-is.
    Directories in exclude_dirs are skipped entirely.
    Returns list of created file paths.
    """
    created: list[Path] = []
    exclude_dirs = exclude_dirs or set()

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


def read_template_platform(template_dir: Path) -> str | None:
    """Read the platform from a template's template.json, if it exists."""
    template_json = template_dir / "template.json"
    if template_json.exists():
        import json as _json
        data = _json.loads(template_json.read_text())
        return data.get("platform")
    return None


def scaffold(
    project_name: str,
    template_name: str,
    versions: dict,
    output_dir: Path,
) -> list[Path]:
    """Scaffold a project from templates.

    Renders up to 3 layers in order, each overriding the previous:
      1. __common/              — universal files
      2. __common/<platform>/   — platform-specific shared files (if template.json declares a platform)
      3. <template_name>/       — template-specific files

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
            d.name for d in TEMPLATES_DIR.iterdir()
            if d.is_dir() and d.name != COMMON_DIR_NAME
        ]
        raise FileNotFoundError(
            f"Template '{template_name}' not found. Available: {available}"
        )

    platform = read_template_platform(template_dir)
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
            d for d in common_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }
        created.extend(render_template_dir(
            env, common_dir, output_dir, context, common_dir,
            exclude_dirs=platform_dirs,
        ))

    # Layer 2: Platform-specific common files (e.g., __common/ts/, __common/python/)
    if platform:
        platform_dir = common_dir / platform
        if platform_dir.is_dir():
            created.extend(render_template_dir(env, platform_dir, output_dir, context, platform_dir))

    # Layer 3: Template-specific files
    created.extend(render_template_dir(env, template_dir, output_dir, context, template_dir))

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a project from templates")
    parser.add_argument("--project-name", required=True, help="Project name (lowercase-hyphenated)")
    parser.add_argument("--template", required=True, help="Template name (e.g. fullstack-ts)")
    parser.add_argument("--versions", required=True, help="Path to versions.json")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

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
