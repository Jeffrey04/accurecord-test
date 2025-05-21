.PHONY: build test

build:
	docker build -t accurecord-test-backend -f podman/backend/Dockerfile .

test:
	uv run pytest tests/test_background.py
	uv run pytest tests/test_web.py
