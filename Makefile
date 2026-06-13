.PHONY: up down build migrate seed seed-small psql test logs throttle-up silk-up baseline

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

migrate:
	docker compose exec web python manage.py migrate

seed:
	docker compose exec web python manage.py seed

seed-small:
	docker compose exec web python manage.py seed --categories 20 --customers 200 --products 1000 --reviews 2000 --orders 1000

psql:
	docker compose exec db psql -U playground -d playground

test:
	docker compose exec web python manage.py test ecommerce -v2

logs:
	docker compose logs -f

# Bring the stack up with the DB throttled to ~1 CPU / 512MB.
throttle-up:
	docker compose -f docker-compose.yml -f docker-compose.throttle.yml up -d --build

# Bring the stack up with django-silk profiling enabled (off by default).
silk-up:
	DJANGO_SILK=1 docker compose up -d --build
	docker compose exec web python manage.py migrate

# Ramp one endpoint headless and write CSV baselines to docs/findings/baselines/.
# Usage: make baseline ENDPOINT=ListingUser
baseline:
	docker compose run --rm loadgen -f /mnt/locust/locustfile.py --host http://web:8000 --headless --run-time 5m --csv /mnt/baselines/$(ENDPOINT) $(ENDPOINT)
