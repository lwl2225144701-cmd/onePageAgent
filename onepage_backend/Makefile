.PHONY: build up down logs shell-api shell-worker migrate seed init-infra test lint

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker-llm bash

migrate:
	docker compose run --rm api alembic upgrade head

migration-create:
	docker compose run --rm api alembic revision --autogenerate -m "$(NAME)"

seed:
	docker compose run --rm api python scripts/seed_materials.py

rebuild-materials:
	docker compose run --rm api python scripts/seed_materials.py

init-infra:
	docker exec training-postgres psql -U training -c "CREATE DATABASE onepage;" || true
	docker run --rm --network infra_default minio/mc:latest /bin/sh -c "mc alias set local http://training-minio:9000 minioadmin minioadmin && mc mb --ignore-existing local/onepage-uploads && mc mb --ignore-existing local/onepage-materials"

test:
	docker compose run --rm api python -m pytest

lint:
	docker compose run --rm api ruff check app/
