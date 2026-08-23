.PHONY: install install-data install-web dev-api dev-web build test run docker-build

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

install:
	python -m venv .venv
	$(PIP) install -r requirements-dev.txt
	cd web && npm ci --no-audit --no-fund

install-data:
	$(PIP) install -r requirements.txt

install-web:
	cd web && npm ci --no-audit --no-fund

dev-api:
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	cd web && npm run dev

build:
	cd web && npm run build

test:
	$(PYTHON) -m ruff format --check app src scripts tests
	$(PYTHON) -m ruff check app src scripts tests
	$(PYTHON) -m pytest -q
	cd web && npm run typecheck

run: build
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port $${PORT:-8000}

docker-build:
	docker build -t cyclone-ai:mvp .
