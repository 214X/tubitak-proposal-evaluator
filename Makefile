SHELL := /bin/sh

RUNNER := scripts/run_dev.py

ifeq ($(OS),Windows_NT)
	PYTHON := py -3
else
	PYTHON := python3
endif

all: setup run

.PHONY: all help setup warmup backend frontend run clean

help:
	@printf '%s\n' \
		'make setup     Install backend and frontend dependencies' \
		'make warmup    Download and cache the BAAI/bge-m3 embedding model' \
		'make backend   Start the FastAPI backend' \
		'make frontend  Start the Next.js frontend' \
		'make run       Start backend and frontend together' \
		'make clean     Remove generated caches and local build artifacts'

setup:
	$(PYTHON) $(RUNNER) setup

warmup:
	$(PYTHON) $(RUNNER) warmup

backend:
	$(PYTHON) $(RUNNER) backend

frontend:
	$(PYTHON) $(RUNNER) frontend

run:
	$(PYTHON) $(RUNNER) run

clean:
	rm -rf backend/.venv
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/runtime
	rm -rf frontend/.next frontend/node_modules frontend/coverage frontend/.turbo frontend/.vercel
	rm -rf .pytest_cache .mypy_cache .ruff_cache .tmp .tmp-pdf-inspect
	find backend scripts -type d -name '__pycache__' -prune -exec rm -rf {} +
