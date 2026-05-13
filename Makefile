SHELL := /bin/sh

RUNNER := scripts/run_dev.py

ifeq ($(OS),Windows_NT)
	PYTHON := py -3
else
	PYTHON := python3
endif

all: setup run

.PHONY: all setup backend frontend run

setup:
	$(PYTHON) $(RUNNER) setup

backend:
	$(PYTHON) $(RUNNER) backend

frontend:
	$(PYTHON) $(RUNNER) frontend

run:
	$(PYTHON) $(RUNNER) run
