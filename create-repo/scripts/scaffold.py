"""Scaffold a project from Jinja2 templates.

Renders template files from templates/<template_name>/ and templates/common/,
substituting project name, versions, and other variables. Produces a complete
directory structure ready for install and verification.
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
J2_EXTENSION = ".j2"


def build_context(project_name: str, versions: dict) -> dict:
    """Build the Jinja2 template context from project config."""
    # Derive the npm scope from the project name (e.g., my-app -> @my-app)
    scope = f"@{project_name}"
    return {
        "project_name": project_name,
        "scope": scope,
        "versions": versions,
    }


def render_template_dir(
    env: Environment,
    source_dir: Path,
    output_dir: Path,
    context: dict,
    base_dir: Path,
) -> list[Path]:
    """Render all files in a template directory tree.

    .j2 files are rendered through Jinja2; other files are copied as-is.
    Returns list of created file paths.
    """
    created: list[Path] = []

    for source_path in sorted(source_dir.rglob("*")):
        if source_path.is_dir():
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


def scaffold(
    project_name: str,
    template_name: str,
    versions: dict,
    output_dir: Path,
) -> list[Path]:
    """Scaffold a project from templates.

    Renders templates/common/ first, then templates/<template_name>/ on top.
    Template-specific files override common files if they share the same path.

    Returns list of all created file paths.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    common_dir = TEMPLATES_DIR / "common"
    template_dir = TEMPLATES_DIR / template_name

    if not template_dir.is_dir():
        raise FileNotFoundError(
            f"Template '{template_name}' not found. "
            f"Available: {[d.name for d in TEMPLATES_DIR.iterdir() if d.is_dir() and d.name != 'common']}"
        )

    context = build_context(project_name, versions)

    # Use the templates root as the Jinja2 search path so we can reference
    # both common/ and template-specific files
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    created: list[Path] = []

    # Render common templates first
    if common_dir.is_dir():
        created.extend(render_template_dir(env, common_dir, output_dir, context, common_dir))

    # Render template-specific files (may override common files)
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
