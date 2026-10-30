#!/usr/bin/env python3
"""Stable installed entry point for the shared Codex policy adapter."""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "agent-skills-policy" / "engine"))

if __name__ == "__main__":
    from codex_adapter import main

    main()
