.PHONY: init test test-hooks test-create-repo test-scaffolds lint format format-check check help

## Setup & daily use
help: ## Show available commands
	@printf "\n\033[1mAvailable commands:\033[0m\n\n"
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{ printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }'
	@printf "\n"

init: ## Install deps, link skills & hooks, sync envs
	@printf "\033[36mChecking uv...\033[0m\n"
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	@printf "\033[36mSyncing Python deps...\033[0m\n"
	@cd skills/create-repo && uv sync --group dev --quiet
	@printf "\033[36mRunning setup...\033[0m\n"
	@./setup.sh
	@main_repo=$$(git rev-parse --git-common-dir | sed 's|/\.git$$||'); \
	if [ "$$main_repo" = "$$(pwd)" ]; then \
		true; \
	elif [ -d "$$main_repo/.work" ]; then \
		rsync -a --delete "$$main_repo/.work/" .work/; \
		echo "Copied .work/ from $$main_repo"; \
	fi
	@$(MAKE) --no-print-directory help

## Testing
test: test-hooks test-create-repo ## Run all fast tests (~30s)

test-hooks: ## Run hook engine tests (~415 tests)
	@printf "\033[36mTesting hook engine...\033[0m\n"
	@cd hooks/PreToolUse && uvx pytest tests/ -q

test-create-repo: ## Run create-repo unit/structural tests
	@printf "\033[36mTesting create-repo...\033[0m\n"
	@cd skills/create-repo && uv run pytest tests/ -q -m "not e2e"
	@printf "\033[2m  (1 deselected test is e2e — run 'make test-scaffolds' for that)\033[0m\n"

test-scaffolds: ## Scaffold E2E (needs pnpm, node, Docker) [TEMPLATE=name|all] [KEEP=path]
	@printf "\033[36mRunning scaffold E2E...\033[0m\n"
	@cd skills/create-repo && uv run python ../../scripts/test-scaffolds.py $(TEMPLATE) $(if $(KEEP),--keep $(KEEP))

## Code quality
check: format lint ## Auto-fix formatting and lint

lint: ## Lint all Python code
	@printf "\033[36mLinting...\033[0m\n"
	@uvx ruff check .

format-check: ## Check formatting without modifying files
	@printf "\033[36mChecking formatting...\033[0m\n"
	@uvx ruff format --check .

format: ## Format all Python code
	@printf "\033[36mFormatting...\033[0m\n"
	@uvx ruff format .
	@uvx ruff check --fix .
