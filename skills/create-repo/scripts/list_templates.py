"""List available create-repo templates from their template.json files."""

import json
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_templates() -> list[tuple[str, str]]:
    templates = []
    for template_json in sorted(TEMPLATES_DIR.glob("*/template.json")):
        if template_json.parent.name.startswith("_"):
            continue
        with open(template_json) as f:
            data = json.load(f)
        name = template_json.parent.name
        description = data.get("description", "(no description)")
        templates.append((name, description))
    return templates


def main() -> None:
    human = "--human" in sys.argv
    templates = load_templates()

    if not templates:
        print("No templates found.", file=sys.stderr)
        sys.exit(1)

    if human:
        print("\nAvailable templates:\n")
        max_name = max(len(t[0]) for t in templates)
        for name, desc in templates:
            print(f"  \033[36m{name:<{max_name}}\033[0m  {desc}")
        print()
    else:
        for name, desc in templates:
            print(f"{name} — {desc}")


if __name__ == "__main__":
    main()
