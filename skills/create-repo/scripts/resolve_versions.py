"""Resolve current package versions for a template.

Scans template .j2 files for {{ versions.* }} references, maps underscore keys
back to canonical package names, resolves latest stable versions via npm/PyPI,
and writes a versions.json file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC
from pathlib import Path

from .scaffold import COMMON_DIR_NAME, TEMPLATES_DIR, read_template_config

# Canonical mapping from underscore key -> package name + registry.
# The normalization is lossy (@hono/node-server -> hono_node_server), so we
# maintain a manual table. Add entries here when templates use new packages.
PACKAGE_REGISTRY: dict[str, tuple[str, str]] = {
    # --- npm packages ---
    # Core
    "react": ("react", "npm"),
    "react_dom": ("react-dom", "npm"),
    "typescript": ("typescript", "npm"),
    "vite": ("vite", "npm"),
    "vitest": ("vitest", "npm"),
    "pnpm": ("pnpm", "npm"),
    # Hono
    "hono": ("hono", "npm"),
    "hono_node_server": ("@hono/node-server", "npm"),
    "hono_trpc_server": ("@hono/trpc-server", "npm"),
    "hono_zod_openapi": ("@hono/zod-openapi", "npm"),
    # tRPC
    "trpc_server": ("@trpc/server", "npm"),
    "trpc_client": ("@trpc/client", "npm"),
    "trpc_react_query": ("@trpc/react-query", "npm"),
    "tanstack_react_query": ("@tanstack/react-query", "npm"),
    # Prisma
    "prisma": ("prisma", "npm"),
    "prisma_client": ("@prisma/client", "npm"),
    "prisma_adapter_pg": ("@prisma/adapter-pg", "npm"),
    # Tailwind
    "tailwindcss": ("tailwindcss", "npm"),
    "tailwindcss_vite": ("@tailwindcss/vite", "npm"),
    # React types
    "types_react": ("@types/react", "npm"),
    "types_react_dom": ("@types/react-dom", "npm"),
    # Build / dev
    "vitejs_plugin_react": ("@vitejs/plugin-react", "npm"),
    "biomejs_biome": ("@biomejs/biome", "npm"),
    "playwright": ("playwright", "npm"),
    "playwright_test": ("@playwright/test", "npm"),
    # Testing
    "testing_library_react": ("@testing-library/react", "npm"),
    "testing_library_jest_dom": ("@testing-library/jest-dom", "npm"),
    "jsdom": ("jsdom", "npm"),
    "dotenv": ("dotenv", "npm"),
    "tsx": ("tsx", "npm"),
    "tsup": ("tsup", "npm"),
    # GraphQL
    "graphql": ("graphql", "npm"),
    "graphql_yoga": ("graphql-yoga", "npm"),
    "pothos_core": ("@pothos/core", "npm"),
    "apollo_client": ("@apollo/client", "npm"),
    "graphql_codegen_cli": ("@graphql-codegen/cli", "npm"),
    "graphql_codegen_introspection": ("@graphql-codegen/introspection", "npm"),
    "graphql_codegen_near_operation_file_preset": (
        "@graphql-codegen/near-operation-file-preset",
        "npm",
    ),
    "graphql_codegen_typed_document_node": (
        "@graphql-codegen/typed-document-node",
        "npm",
    ),
    "graphql_codegen_typescript": ("@graphql-codegen/typescript", "npm"),
    "graphql_codegen_typescript_operations": (
        "@graphql-codegen/typescript-operations",
        "npm",
    ),
    "graphql_typed_document_node_core": ("@graphql-typed-document-node/core", "npm"),
    # --- PyPI packages ---
    "fastapi": ("fastapi", "pypi"),
    "sqlmodel": ("sqlmodel", "pypi"),
    "sqlalchemy": ("sqlalchemy", "pypi"),
    "pydantic": ("pydantic", "pypi"),
    "uvicorn": ("uvicorn", "pypi"),
    "alembic": ("alembic", "pypi"),
    "pytest": ("pytest", "pypi"),
    "httpx": ("httpx", "pypi"),
    "ruff": ("ruff", "pypi"),
}

# Regex to find {{ versions.KEY }} in Jinja2 templates
_VERSION_REF_RE = re.compile(r"\{\{\s*versions\.(\w+)\s*\}\}")


def discover_required_keys(template_name: str) -> set[str]:
    """Scan all .j2 files that a template would render and extract version keys."""
    template_dir = TEMPLATES_DIR / template_name
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Template '{template_name}' not found")

    config = read_template_config(template_dir)

    # Normalize platform to a list
    if isinstance(config.platform, str):
        platforms = [config.platform]
    elif isinstance(config.platform, list):
        platforms = config.platform
    else:
        platforms = []

    # Resolve base template
    base_dir: Path | None = None
    base_config = None
    if config.extends:
        base_dir = TEMPLATES_DIR / config.extends
        base_config = read_template_config(base_dir)
        if not platforms and base_config.platform:
            if isinstance(base_config.platform, str):
                platforms = [base_config.platform]
            elif isinstance(base_config.platform, list):
                platforms = base_config.platform

    dirs_to_scan: list[Path] = []

    # Layer 1: Universal common (exclude platform subdirs — we add them explicitly)
    common_dir = TEMPLATES_DIR / COMMON_DIR_NAME
    if common_dir.is_dir():
        dirs_to_scan.append(common_dir)

    # Layer 2: Platform-specific common
    for plat in platforms:
        platform_dir = common_dir / plat
        if platform_dir.is_dir():
            dirs_to_scan.append(platform_dir)

    # Layer 3: Base template
    if base_dir and base_dir.is_dir():
        dirs_to_scan.append(base_dir)

    # Layer 4: Template-specific
    dirs_to_scan.append(template_dir)

    keys: set[str] = set()
    for scan_dir in dirs_to_scan:
        for j2_file in scan_dir.rglob("*.j2"):
            # Skip excluded files from base layer
            if base_dir and scan_dir == base_dir and config.exclude:
                rel = str(j2_file.relative_to(base_dir))
                if any(__import__("fnmatch").fnmatch(rel, pat) for pat in config.exclude):
                    continue
            content = j2_file.read_text()
            keys.update(_VERSION_REF_RE.findall(content))

    return keys


def resolve_npm_version(package_name: str) -> str | None:
    """Get the latest stable version of an npm package."""
    try:
        proc = subprocess.run(
            ["npm", "view", package_name, "version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def resolve_pypi_version(package_name: str) -> str | None:
    """Get the latest stable version of a PyPI package."""
    try:
        proc = subprocess.run(
            ["uv", "pip", "compile", "--no-deps", "-", "--quiet"],
            input=f"{package_name}\n",
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            # Output is like: package-name==1.2.3
            for line in proc.stdout.strip().splitlines():
                if "==" in line:
                    return line.split("==")[1].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    # Fallback: try pip index
    try:
        proc = subprocess.run(
            ["pip", "index", "versions", package_name],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            match = re.search(r"LATEST:\s+(\S+)", proc.stdout)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


# Groups of packages whose major versions must match.
# Each group is a list of underscore keys. If any are present in the resolved
# versions, their major versions must be identical.
COMPAT_GROUPS: list[list[str]] = [
    # Prisma ecosystem
    ["prisma", "prisma_client", "prisma_adapter_pg"],
    # tRPC ecosystem
    ["trpc_server", "trpc_client", "trpc_react_query"],
    # React core
    ["react", "react_dom"],
    # Tailwind + vite plugin
    ["tailwindcss", "tailwindcss_vite"],
    # Playwright
    ["playwright", "playwright_test"],
    # GraphQL codegen (all @graphql-codegen/* should share major)
    [
        "graphql_codegen_cli",
        "graphql_codegen_introspection",
        "graphql_codegen_near_operation_file_preset",
        "graphql_codegen_typed_document_node",
        "graphql_codegen_typescript",
        "graphql_codegen_typescript_operations",
    ],
]


def _major(version: str) -> str:
    """Extract the major version component."""
    return version.split(".")[0]


def check_compatibility(versions: dict[str, str]) -> list[str]:
    """Check that interdependent packages have compatible major versions.

    Returns a list of error messages (empty if all good).
    """
    errors: list[str] = []
    for group in COMPAT_GROUPS:
        present = {k: versions[k] for k in group if k in versions}
        if len(present) < 2:
            continue
        majors = {k: _major(v) for k, v in present.items()}
        unique_majors = set(majors.values())
        if len(unique_majors) > 1:
            details = ", ".join(f"{k}={v}" for k, v in present.items())
            errors.append(f"Major version mismatch in [{', '.join(group[:2])}...]: {details}")
    return errors


def resolve_versions(
    template_name: str,
    cache_path: Path | None = None,
    fresh: bool = False,
) -> dict[str, str]:
    """Discover and resolve all versions needed for a template.

    Returns a dict of {underscore_key: version_string}.
    """
    import time

    # Check cache first
    if cache_path and cache_path.exists() and not fresh:
        try:
            cache = json.loads(cache_path.read_text())
            cached_at = cache.get("cached_at", 0)
            if time.time() - cached_at < 86400:  # 24 hours
                cached_versions = cache["versions"]
                # Validate cache covers everything the template actually needs.
                # New version keys added to templates after the cache was written
                # would cause a Jinja2 UndefinedError at render time — catch it here.
                required_keys = discover_required_keys(template_name)
                missing = required_keys - set(cached_versions.keys())
                if not missing:
                    print(
                        f"Using cached versions from {cache.get('cached_at_human', 'unknown')}. "
                        "Pass --fresh to re-resolve.",
                        file=sys.stderr,
                    )
                    return cached_versions
                else:
                    print(
                        f"Cache missing {len(missing)} key(s)"
                        f" ({', '.join(sorted(missing))}) — re-resolving fresh.",
                        file=sys.stderr,
                    )
                    # Fall through to full fresh resolution below
        except (json.JSONDecodeError, KeyError):
            pass  # Corrupted cache, re-resolve

    required_keys = discover_required_keys(template_name)

    # Check for unmapped keys
    unmapped = required_keys - PACKAGE_REGISTRY.keys()
    if unmapped:
        print(
            f"WARNING: Unknown version keys (add to PACKAGE_REGISTRY): {sorted(unmapped)}",
            file=sys.stderr,
        )

    versions: dict[str, str] = {}
    failed: list[str] = []

    for key in sorted(required_keys):
        if key not in PACKAGE_REGISTRY:
            failed.append(key)
            continue

        package_name, registry = PACKAGE_REGISTRY[key]
        print(f"  Resolving {package_name}...", end=" ", flush=True, file=sys.stderr)

        if registry == "npm":
            version = resolve_npm_version(package_name)
        elif registry == "pypi":
            version = resolve_pypi_version(package_name)
        else:
            version = None

        if version:
            versions[key] = version
            print(version, file=sys.stderr)
        else:
            failed.append(key)
            print("FAILED", file=sys.stderr)

    if failed:
        print(f"\nFailed to resolve: {', '.join(failed)}", file=sys.stderr)
        print("Add missing packages to PACKAGE_REGISTRY or check network.", file=sys.stderr)
        sys.exit(1)

    # Validate compatibility constraints (warnings, not hard failures —
    # the real gate is the verify step which builds and tests the project)
    compat_warnings = check_compatibility(versions)
    if compat_warnings:
        print("\nCompatibility warnings:", file=sys.stderr)
        for warn in compat_warnings:
            print(f"  ⚠ {warn}", file=sys.stderr)
        print(
            "\nThese packages usually share major versions. If the build fails, "
            "try pinning the newer package to match the older one.",
            file=sys.stderr,
        )

    # Save to cache
    if cache_path:
        from datetime import datetime

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_data = {
            "cached_at": time.time(),
            "cached_at_human": datetime.now(UTC).isoformat(),
            "template": template_name,
            "versions": versions,
        }
        cache_path.write_text(json.dumps(cache_data, indent=2) + "\n")

    return versions


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve current package versions for a template")
    parser.add_argument(
        "--template",
        required=True,
        help="Template name (e.g., fullstack-ts, swift-ts)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write versions.json",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore cache and resolve fresh versions",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Just print required version keys without resolving",
    )
    args = parser.parse_args()

    if args.discover_only:
        keys = discover_required_keys(args.template)
        for key in sorted(keys):
            pkg_info = PACKAGE_REGISTRY.get(key)
            if pkg_info:
                print(f"  {key} -> {pkg_info[0]} ({pkg_info[1]})")
            else:
                print(f"  {key} -> UNMAPPED")
        return

    cache_dir = Path.home() / ".agent-skills" / ".version-cache"
    cache_path = cache_dir / f"{args.template}.json"

    versions = resolve_versions(args.template, cache_path, fresh=args.fresh)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(versions, indent=2) + "\n")
    print(f"\nWrote {len(versions)} versions to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
