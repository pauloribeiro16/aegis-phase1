.PHONY: setup test lint typecheck format clean precommit

# ─── Setup ───────────────────────────────────────────────────────────
setup:
	pip install -e ".[all]"
	pre-commit install

# ─── Testing ─────────────────────────────────────────────────────────
test:
	pytest tests/unit/ -v --tb=short

test-all:
	pytest tests/ -v --tb=short

test-file:
	pytest $(FILE) -v --tb=short

test-coverage:
	pytest tests/unit/ --cov=src/aegis_phase1 --cov-report=term-missing

# ─── Linting ─────────────────────────────────────────────────────────
lint:
	ruff check src/ tests/

lint-fix:
	ruff check --fix src/ tests/

# ─── Type checking ───────────────────────────────────────────────────
typecheck:
	mypy src/aegis_phase1/

# ─── Formatting ──────────────────────────────────────────────────────
format:
	ruff format src/ tests/

format-check:
	ruff format --check src/ tests/

# ─── Pre-commit ──────────────────────────────────────────────────────
precommit:
	pre-commit run --all-files

# ─── Cleanup ─────────────────────────────────────────────────────────
clean:
	rm -rf .pytest_cache/ .coverage htmlcov/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ─── Smoke ───────────────────────────────────────────────────────────
smoke:
	python -c "from aegis_phase1.graph import run_phase1; print('OK: phase1 importable')"
