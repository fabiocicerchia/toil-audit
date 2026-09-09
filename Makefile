# toil-audit
#
# Arguments for `make run`, e.g. make run ARGS="--repo OWNER/REPO --since 2026-07-01"
ARGS ?= --help

# Every verb this repository exposes lives here; `make` on its own prints them.
# FC-GEN-057: the same eight verbs in every repo, each either wired or a
# declared no-op that says why. None of them exit 0 quietly.

.DEFAULT_GOAL := help

.PHONY: help setup install build run test lint format analyze clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install the dev dependencies and the pre-commit hook
	pip install -r requirements-dev.txt
	pre-commit install

run: ## Run the analyser (make run ARGS="--repo OWNER/REPO --since ...")
	python -m toilaudit $(ARGS)

test: ## Run the tests
	python -m pytest

lint: ## Run the whole gate — every hook, every file
	pre-commit run --all-files

format: ## Format the tree with ruff, the formatter the gate checks
	ruff format .

analyze: ## Scan the tree the way CI does — vulnerabilities, misconfig, secrets
	@command -v trivy >/dev/null 2>&1 || { \
		echo "analyze needs trivy: https://trivy.dev/latest/getting-started/installation/" >&2; \
		exit 69; }
	trivy fs --scanners vuln,misconfig,secret --severity CRITICAL,HIGH .

# Fetched API pages are cached here so re-analysing a repo costs no requests.
# Removing it is the only thing this repo accumulates.
clean: ## Remove the fetch cache
	rm -rf .toilaudit-cache

# --- Declared no-ops (FC-GEN-058) ---
# These exit 0 and say why. They are listed under "Not applicable" in the README.

install: ## Install the package (and its man page) with pip
	pip install .

build: ## Not applicable — nothing is compiled or packaged
	@echo "Nothing to build: a pure-Python package with no build step."
	@echo "See README > Not applicable."
