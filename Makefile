export PYGAME_HIDE_SUPPORT_PROMPT := 1

.PHONY: install run debug clean lint lint-strict

install:
	uv venv
	uv pip install -r requirements.txt

run:
	uv run python viz.py $(ARGS)

debug:
	uv run python -m pdb viz.py $(ARGS)

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache

lint:
	uv run flake8 .
	uv run mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	uv run flake8 .
	uv run mypy . --strict