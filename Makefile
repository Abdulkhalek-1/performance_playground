.PHONY: up down build migrate seed seed-small psql test logs

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec web python manage.py migrate

# Large default volume for load testing (Phase 1 throttled deep-dive).
seed:
	docker compose exec web python manage.py seed

# Tiny volume for a quick smoke check.
seed-small:
	docker compose exec web python manage.py seed --categories 20 --customers 200 --products 1000 --reviews 2000 --orders 1000

psql:
	docker compose exec db psql -U playground -d playground

test:
	docker compose exec web python manage.py test ecommerce -v2

logs:
	docker compose logs -f
