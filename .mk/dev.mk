##@ Development

# Override install-requirements to also install local skillberry-agent-lib
.PHONY: install-requirements-local
install-requirements-local:
	@echo "Installing local skillberry-agent-lib package..."
	@uv pip install -e shared/python/skillberry_agent_lib/

test-e2e: ## Test end-to-end the agent service
	@$(MAKE) install_requirements
	pytest -s tests/e2e

lint: ## Lint the agent service
	@$(MAKE) install_requirements
	black --check --diff --color agents config fast_api llm utils || \
		(echo "Lint Failed. Please run 'black agents config fast_api llm utils' to fix the issues" && exit 1)

# Made with Bob
