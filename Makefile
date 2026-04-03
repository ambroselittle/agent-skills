.PHONY: init

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
