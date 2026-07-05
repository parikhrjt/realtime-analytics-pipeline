.PHONY: help install test lint run-api run-ui run-producer run-consumer migrate docker-up docker-down up down logs

help:
	@echo "Realtime Analytics Pipeline"
	@echo "  install        Create venv and install deps"
	@echo "  test           Run pytest"
	@echo "  docker-up      Start full Docker stack"
	@echo "  docker-down    Stop Docker stack"
	@echo "  run-api        Start FastAPI locally"
	@echo "  run-ui         Start Streamlit locally"

install:
	python3.11 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	PYTHONPATH=. .venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check app tests scripts

run-api:
	PYTHONPATH=. .venv/bin/uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	PYTHONPATH=. API_BASE_URL=http://localhost:8000 .venv/bin/streamlit run streamlit_app.py

run-producer:
	PYTHONPATH=. .venv/bin/python scripts/run_producer.py

run-consumer:
	PYTHONPATH=. .venv/bin/python scripts/run_consumer.py

migrate:
	PYTHONPATH=. .venv/bin/python scripts/migrate.py

docker-up up:
	docker compose up --build -d

docker-down down:
	docker compose down -v

logs:
	docker compose logs -f api consumer producer
