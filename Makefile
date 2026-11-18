.PHONY: venv install run run-noplot test lint typecheck check clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e ".[dev]"

run:
	$(VENV)/bin/sensor-sim

run-noplot:
	$(VENV)/bin/sensor-sim --no-plot

test:
	$(VENV)/bin/pytest -q

lint:
	$(VENV)/bin/ruff check .

typecheck:
	$(VENV)/bin/mypy src

check: lint typecheck test

clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache .mypy_cache src/*.egg-info
	find . -name "__pycache__" -not -path "./$(VENV)/*" -exec rm -rf {} +
