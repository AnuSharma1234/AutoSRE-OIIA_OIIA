.PHONY: up down logs ps restart build clean dev prod

all: dev

up:
	docker compose up -d

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

prod:
	docker compose -f docker-compose.yml up -d

down:
	docker compose down

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

logs-postgres:
	docker compose logs -f postgres

logs-redis:
	docker compose logs -f redis

ps:
	docker compose ps

restart-backend:
	docker compose restart backend

restart-frontend:
	docker compose restart frontend

restart-postgres:
	docker compose restart postgres

restart-redis:
	docker compose restart redis

build:
	docker compose build --no-cache

rebuild:
	docker compose build

clean:
	docker compose down -v

exec-backend:
	docker compose exec backend ${cmd}

exec-postgres:
	docker compose exec postgres psql -U autosre -d autosre

migrate:
	docker compose exec backend alembic upgrade head

migrate-down:
	docker compose exec backend alembic downgrade -1

migrate-create:
	docker compose exec backend alembic revision --autogenerate -m "${msg}"

test:
	docker compose exec backend pytest

shell-backend:
	docker compose exec backend /bin/sh

shell-postgres:
	docker compose exec postgres /bin/sh
