---
paths: ["**/pyproject.toml", "**/uv.lock"]
---

## Python Packaging with uv

### pyproject.toml structure

Always use this structure for new Python projects/skills:

```toml
[project]
name = "my-skill"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "some-package~=1.2",
]

[dependency-groups]
dev = [
    "pytest~=8.0",
]
```

**Never use `[tool.uv]` with `dev-dependencies`** — that field is deprecated and produces a warning on every `uv run`. Use `[dependency-groups]` instead.

### Dependency version ranges

All dependencies must have bounded version ranges — bare `>=` is blocked by the hook engine.

| Pattern | Use case |
|---|---|
| `~=1.2` | Allow patch + minor updates within major (preferred for most deps) |
| `~=1.2.3` | Pin to patch updates only (for unstable APIs) |
| `>=1.2,<2` | Explicit upper bound (equivalent to `~=1.2` but more verbose) |

**Never write:** `"boto3>=1.35"`, `"fastapi>=0.115"` — always add the upper bound.

### boto3 / botocore and AWS CLI auth

When using boto3 with AWS CLI SSO/IAM Identity Center auth (`aws login`), add `botocore[crt]` as a dependency — it provides the credential provider required for token-based auth. Without it, boto3 sessions silently fail to resolve credentials.

```toml
dependencies = [
    "boto3~=1.42",
    "botocore[crt]~=1.42",
]
```
