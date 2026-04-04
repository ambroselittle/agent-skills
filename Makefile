.PHONY: init test test-hooks test-create-repo test-scaffolds

# Copy .work/ from the main repo into this worktree.
# Safe to run in the main repo too — it no-ops when source == destination.
init:
	@main_repo=$$(git rev-parse --git-common-dir | sed 's|/\.git$$||'); \
	if [ "$$main_repo" = "$$(pwd)" ]; then \
		echo ".work/ already local — nothing to copy."; \
	elif [ -d "$$main_repo/.work" ]; then \
		rsync -a --delete "$$main_repo/.work/" .work/; \
		echo "Copied .work/ from $$main_repo"; \
	else \
		echo "No .work/ found in $$main_repo — skipping."; \
	fi

# Run all fast tests (hook engine + create-repo unit/structural)
test: test-hooks test-create-repo

test-hooks:
	cd hooks/PreToolUse && uvx pytest tests/ -v

test-create-repo:
	cd skills/create-repo && uv run pytest tests/ -v -m "not e2e"

# Full scaffold E2E — interactive picker, needs pnpm, node, Docker (or DATABASE_URL)
# Usage: make test-scaffolds [TEMPLATE=fullstack-ts]
test-scaffolds:
	cd skills/create-repo && uv run python ../../scripts/test-scaffolds.py $(TEMPLATE)
