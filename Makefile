.PHONY: install test lint run-api run-ui run-producer run-consumer migrate up down logs

install:
	python3.11 -m venv .venv
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check app tests scripts

run-api:
	.venv/bin/uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

run-ui:
	.venv/bin/streamlit run streamlit_app.py

run-producer:
	.venv/bin/python scripts/run_producer.py

run-consumer:
	.venv/bin/python scripts/run_consumer.py

migrate:
	.venv/bin/python scripts/migrate.py

up:
	docker compose up --build -d

down:
	docker compose down -v

logs:
	docker compose logs -f api consumer producer
