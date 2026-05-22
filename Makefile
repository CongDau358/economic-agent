# ── Economic Agent — Developer Makefile ───────────────────────────────────────
# Dùng: make <target>

PYTHON  ?= python
PIP     ?= pip
UVICORN ?= uvicorn
APP      = backend.main:app

.PHONY: help install dev test test-cov lint format typecheck \
        docker-up docker-down clean reset batch-predict schedule-ingest

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Economic Agent — Available commands:"
	@echo ""
	@echo "  make install          Cài tất cả dependencies"
	@echo "  make dev              Chạy server dev (auto-reload)"
	@echo "  make test             Chạy test suite"
	@echo "  make test-cov         Chạy tests + coverage report"
	@echo "  make lint             Kiểm tra code style (ruff)"
	@echo "  make format           Tự động format code (ruff)"
	@echo "  make typecheck        Kiểm tra type hints (mypy)"
	@echo "  make docker-up        Khởi động Docker (API + Redis + Frontend)"
	@echo "  make docker-down      Dừng Docker"
	@echo "  make batch-predict    Chạy batch predict với dữ liệu mẫu"
	@echo "  make schedule-ingest  Chạy ingestion pipeline một lần"
	@echo "  make clean            Xóa __pycache__, .pytest_cache"
	@echo "  make reset            Xóa toàn bộ data (vector store, raw, processed)"
	@echo ""

# ── Install ───────────────────────────────────────────────────────────────────
install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements.txt ruff mypy

# ── Dev server ────────────────────────────────────────────────────────────────
dev:
	$(UVICORN) $(APP) --reload --host 0.0.0.0 --port 8000

dev-log:
	LOG_LEVEL=debug $(UVICORN) $(APP) --reload --host 0.0.0.0 --port 8000

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v \
		--cov=backend \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-fail-under=60

test-fast:
	pytest tests/ -v -x --tb=short   # dừng ở lỗi đầu tiên

test-trend:
	pytest tests/test_trend_engine.py -v

test-services:
	pytest tests/test_services.py -v

# ── Code quality ──────────────────────────────────────────────────────────────
lint:
	ruff check backend/ tests/

format:
	ruff format backend/ tests/
	ruff check --fix backend/ tests/

typecheck:
	mypy backend/ --ignore-missing-imports --no-strict-optional

check: lint typecheck test  # chạy toàn bộ trước khi commit

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f api

docker-restart:
	docker compose restart api

# ── Pipelines ─────────────────────────────────────────────────────────────────
batch-predict:
	$(PYTHON) pipelines/batch_predict.py --sample

batch-predict-file:
	$(PYTHON) pipelines/batch_predict.py --input $(INPUT) --output data/batch_results

schedule-ingest:
	$(PYTHON) pipelines/schedule_ingest.py

schedule-ingest-cron:
	$(PYTHON) pipelines/schedule_ingest.py --scheduled --hours 6

# ── Utilities ─────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✓ Cleaned"

reset: clean
	@echo "⚠ Xóa toàn bộ data. Tiếp tục? [y/N]" && read ans && [ "$$ans" = "y" ]
	rm -rf data/vector data/raw data/processed data/batch_results
	mkdir -p data/vector data/raw data/processed
	@echo "✓ Data reset"

# ── Env setup ─────────────────────────────────────────────────────────────────
env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ .env tạo từ .env.example — hãy điền OPENAI_API_KEY"; \
	else \
		echo ".env đã tồn tại"; \
	fi