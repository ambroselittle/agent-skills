## Python Module Conventions

- Use absolute imports from the package root (e.g., `from src.models import User`)
- Every package directory must have an `__init__.py` (can be empty)
- Avoid circular imports — if two modules depend on each other, extract shared types to a third module
- Group imports: stdlib → third-party → local, separated by blank lines
- Prefer explicit imports over `from module import *`
- Keep `__init__.py` files minimal — don't re-export everything, just the public API
