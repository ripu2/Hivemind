VENV = .venv
PYTHON = $(VENV)/bin/python
UV = uv

.PHONY: runserver install freeze docker-build docker-run docker-up docker-down

runserver:
	source $(VENV)/bin/activate && uvicorn app.main:app --reload

install:
	$(UV) sync

freeze:
	$(UV) export --format requirements-txt --no-hashes -o requirements.txt

docker-build:
	docker build -t hivemind .

docker-run:
	docker run --env-file .env -p 8000:8000 hivemind

docker-up:
	docker compose up --build

docker-down:
	docker compose down
