##@ Setup & teardown as a process

# Override the run target to include local package installation
# run: install-requirements install-requirements-local 
# 	@$(MAKE) -f $(SB_COMMON_PATH)/.mk/process.mk run

clean-service-data: stop
	@true

# Made with Bob
