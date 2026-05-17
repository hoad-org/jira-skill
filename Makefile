.PHONY: help install test test-verbose coverage lint format type-check clean

help:
	@echo "Jira Skill - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run tests"
	@echo "  make test-verbose  Run tests with verbose output"
	@echo "  make coverage      Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          Lint code (ruff)"
	@echo "  make format        Format code (black)"
	@echo "  make type-check    Type checking (mypy)"
	@echo "  make check         Run all checks (lint + type-check)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean         Remove build artifacts"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

test-verbose:
	pytest tests/ -vv -s

coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

lint:
	ruff check src/ tests/

format:
	black src/ tests/ --line-length 100

format-check:
	black src/ tests/ --check --line-length 100

type-check:
	mypy src/ --ignore-missing-imports

check: format-check lint type-check
	@echo "✅ All checks passed!"

clean:
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.DEFAULT_GOAL := help

.PHONY: install-hooks
install-hooks:
	@echo "Installing git hooks..."
	@mkdir -p .git-hooks-local
	@if [ -f .claude/pre-commit-hook-template.sh ]; then \
		cp .claude/pre-commit-hook-template.sh .git-hooks-local/pre-commit; \
		chmod +x .git-hooks-local/pre-commit; \
		git config core.hooksPath .git-hooks-local; \
		echo "✅ Git hooks installed"; \
	else \
		echo "⚠️  Hook template not found at .claude/pre-commit-hook-template.sh"; \
	fi

.PHONY: setup
setup: install-hooks
	@echo "✅ Development environment ready"
