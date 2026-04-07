#!/usr/bin/env bash
# Check that python3 is available and meets a minimum version.
# Usage: check-python.sh [min_version]
# Default min_version: 3.9
#
# Exits 0 if OK, 1 if missing or too old. Prints a human-readable message on failure.

set -euo pipefail

MIN_VERSION="${1:-3.9}"
MIN_MAJOR="${MIN_VERSION%%.*}"
MIN_MINOR="${MIN_VERSION#*.}"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but not found."
    echo "Install it via: xcode-select --install (macOS) or your package manager."
    exit 1
fi

VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
MAJOR="${VERSION%%.*}"
MINOR="${VERSION#*.}"

if [ "$MAJOR" -lt "$MIN_MAJOR" ] || { [ "$MAJOR" -eq "$MIN_MAJOR" ] && [ "$MINOR" -lt "$MIN_MINOR" ]; }; then
    echo "python3 $VERSION found, but $MIN_VERSION+ is required."
    echo "Upgrade via: brew install python3 (or your package manager)."
    exit 1
fi
