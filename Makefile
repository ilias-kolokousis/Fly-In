export PYGAME_HIDE_SUPPORT_PROMPT := 1

MAP ?= maps/simple_fork.txt

.PHONY: install run headless debug lint clean

install:
	uv sync

run:
	uv run python -m fly_in $(MAP) $(ARGS)

headless:
	uv run python -m fly_in $(MAP) --no-gui

debug:
	uv run python -m pdb -m fly_in $(MAP) $(ARGS)

lint:
	uv run flake8 fly_in
	uv run mypy fly_in

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .mypy_cache
