VENV = .venv
PYTHON = $(VENV)/bin/python
UV = uv

.PHONY: runserver install freeze

runserver:
	source $(VENV)/bin/activate && uvicorn app.main:app --reload

install:
	$(UV) sync

freeze:
	$(UV) export --format requirements-txt --no-hashes -o requirements.txt
