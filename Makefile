.PHONY: install test lint build docker run clean help

help:
	@echo "ORF targets:"
	@echo "  install  - uv sync --all-extras"
	@echo "  test     - run pytest suite"
	@echo "  lint     - ruff check src/ tests/"
	@echo "  build    - uv build (wheel + sdist)"
	@echo "  docker   - build the Docker image (tag: orf:dev)"
	@echo "  run      - show orf --help via uv"
	@echo "  clean    - remove build artifacts and __pycache__ dirs"

install:
	uv sync --all-extras

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/ tests/

build:
	uv build

docker:
	docker build -t orf:dev .

run:
	uv run orf --help

clean:
	rm -rf .venv build/ dist/ *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
