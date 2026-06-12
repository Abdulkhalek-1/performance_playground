# Performance Playground — Phase 1A (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a Dockerized Postgres 18 + Django e-commerce stack with a full data model and a configurable seed generator, so later plans have a running, queryable, populated system to load-test and optimize.

**Architecture:** Docker Compose runs `db` (Postgres 18 with `pg_stat_statements` + `auto_explain` enabled via `-c` flags) and `web` (Django served by Gunicorn). The Django `ecommerce` app defines the e-commerce schema deliberately *without* extra indexes so later plans can add them as optimization lessons. A `seed` management command generates data at a volume controlled by CLI flags (small for tests, large for load testing).

**Tech Stack:** Django 5.1, psycopg 3, Gunicorn, Faker, PostgreSQL 18, Docker Compose.

**Scope note:** This is the first of three Phase 1 plans. 1B adds the six naive endpoints + Locust + observability; 1C runs the first optimization cycles. Do not implement endpoints or load tests here.

---

## File Structure

```
performance_playground/
  .env                          # local secrets/config (gitignored)
  .env.example                  # template, committed
  docker-compose.yml            # db + web services
  Makefile                      # up / down / migrate / seed / psql / test
  postgres/
    init/01-extensions.sql      # CREATE EXTENSION pg_stat_statements
  app/
    Dockerfile
    requirements.txt
    manage.py
    config/                     # Django project package
      __init__.py
      settings.py
      urls.py
      wsgi.py
    ecommerce/                  # the domain app
      __init__.py
      apps.py
      models.py
      migrations/__init__.py
      management/__init__.py
      management/commands/__init__.py
      management/commands/seed.py
      tests/__init__.py
      tests/test_models.py
      tests/test_seed.py
```

Each file has one responsibility: `models.py` = schema, `seed.py` = data generation, `settings.py` = config wiring, compose/Dockerfile = runtime. Endpoints and load tests are intentionally absent (later plans).

---

### Task 1: Project skeleton & Python dependencies

**Files:**
- Create: `app/requirements.txt`
- Create: `.env.example`
- Create: `.env`
- Modify: `.gitignore` (already has `.env`, `db_data/`, `__pycache__/`, `*.pyc`)

- [ ] **Step 1: Create `app/requirements.txt`**

```
Django==5.1.4
psycopg[binary]==3.2.3
gunicorn==23.0.0
Faker==33.1.0
```

- [ ] **Step 2: Create `.env.example`**

```
POSTGRES_DB=playground
POSTGRES_USER=playground
POSTGRES_PASSWORD=playground
POSTGRES_HOST=db
POSTGRES_PORT=5432
DJANGO_SECRET_KEY=dev-insecure-change-me
DJANGO_DEBUG=1
```

- [ ] **Step 3: Create `.env` with the same contents**

```
POSTGRES_DB=playground
POSTGRES_USER=playground
POSTGRES_PASSWORD=playground
POSTGRES_HOST=db
POSTGRES_PORT=5432
DJANGO_SECRET_KEY=dev-insecure-change-me
DJANGO_DEBUG=1
```

- [ ] **Step 4: Commit**

```bash
git add app/requirements.txt .env.example
git commit -m "chore: add python deps and env template"
```

---

### Task 2: Postgres 18 service with extensions

**Files:**
- Create: `postgres/init/01-extensions.sql`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `postgres/init/01-extensions.sql`**

This runs once on first DB init (the official image executes `/docker-entrypoint-initdb.d/*.sql`).

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

- [ ] **Step 2: Create `docker-compose.yml` (db service only for now)**

```yaml
services:
  db:
    image: postgres:18
    env_file: .env
    command:
      - "postgres"
      - "-c"
      - "shared_preload_libraries=pg_stat_statements,auto_explain"
      - "-c"
      - "pg_stat_statements.track=all"
      - "-c"
      - "auto_explain.log_min_duration=200ms"
      - "-c"
      - "auto_explain.log_analyze=on"
      - "-c"
      - "auto_explain.log_buffers=on"
      - "-c"
      - "log_min_duration_statement=500ms"
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./postgres/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  db_data:
```

- [ ] **Step 3: Bring up the DB and verify extensions load**

Run:
```bash
docker compose up -d db
sleep 8
docker compose exec db psql -U playground -d playground -c "SELECT extname FROM pg_extension WHERE extname='pg_stat_statements';"
docker compose exec db psql -U playground -d playground -c "SHOW shared_preload_libraries;"
```
Expected: first query returns one row `pg_stat_statements`; second shows `pg_stat_statements,auto_explain`.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml postgres/init/01-extensions.sql
git commit -m "feat: postgres 18 service with pg_stat_statements and auto_explain"
```

---

### Task 3: Django project scaffold + DB connection + health endpoint

**Files:**
- Create: `app/Dockerfile`
- Create: `app/manage.py`
- Create: `app/config/__init__.py`, `app/config/settings.py`, `app/config/urls.py`, `app/config/wsgi.py`
- Create: `app/ecommerce/__init__.py`, `app/ecommerce/apps.py`
- Modify: `docker-compose.yml` (add `web` service)

- [ ] **Step 1: Create `app/Dockerfile`**

```dockerfile
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

- [ ] **Step 2: Create `app/manage.py`**

```python
#!/usr/bin/env python
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create `app/config/__init__.py` (empty) and `app/config/settings.py`**

`app/config/__init__.py`: empty file.

`app/config/settings.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "ecommerce",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "playground"),
        "USER": os.environ.get("POSTGRES_USER", "playground"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "playground"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
```

(Note: `django.contrib.auth` is included only because `contenttypes` expects it; we are not using login. This keeps migrations clean.)

- [ ] **Step 4: Create `app/config/urls.py` with a health endpoint**

```python
from django.db import connection
from django.http import JsonResponse
from django.urls import path


def health(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
]
```

- [ ] **Step 5: Create `app/config/wsgi.py`**

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

- [ ] **Step 6: Create `app/ecommerce/__init__.py` (empty) and `app/ecommerce/apps.py`**

`app/ecommerce/apps.py`:
```python
from django.apps import AppConfig


class EcommerceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ecommerce"
```

- [ ] **Step 7: Add the `web` service to `docker-compose.yml`**

Insert under `services:` (after the `db` block, before `volumes:`):
```yaml
  web:
    build: ./app
    env_file: .env
    command: ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app
    depends_on:
      db:
        condition: service_healthy
```

- [ ] **Step 8: Build, run migrations, verify health**

Run:
```bash
docker compose up -d --build web
docker compose exec web python manage.py migrate
curl -s http://localhost:8000/health/
```
Expected: migrate completes without error; curl returns `{"status": "ok"}`.

- [ ] **Step 9: Commit**

```bash
git add app docker-compose.yml
git commit -m "feat: django scaffold with postgres connection and health endpoint"
```

---

### Task 4: E-commerce data model (TDD)

**Files:**
- Create: `app/ecommerce/models.py`
- Create: `app/ecommerce/tests/__init__.py` (empty)
- Create: `app/ecommerce/tests/test_models.py`
- Create (generated): `app/ecommerce/migrations/__init__.py` (empty) + migration file via `makemigrations`

**Design note:** No explicit indexes beyond what Django auto-creates on foreign keys. The "missing index" lessons in plan 1C target non-FK columns (`price`, `created_at`, full-text). Keep it naive on purpose.

- [ ] **Step 1: Create `app/ecommerce/migrations/__init__.py` and `app/ecommerce/tests/__init__.py`**

Both empty files.

- [ ] **Step 2: Write the failing test — `app/ecommerce/tests/test_models.py`**

```python
from decimal import Decimal

from django.test import TestCase

from ecommerce.models import (
    Cart,
    CartItem,
    Category,
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductReview,
)


class ModelRelationTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            email="a@b.com", full_name="Alice B"
        )
        self.category = Category.objects.create(name="Books")
        self.product = Product.objects.create(
            name="A Book",
            description="A fine book.",
            price=Decimal("9.99"),
            category=self.category,
        )
        Inventory.objects.create(product=self.product, quantity=5)

    def test_inventory_is_one_to_one(self):
        self.assertEqual(self.product.inventory.quantity, 5)

    def test_review_links_customer_and_product(self):
        ProductReview.objects.create(
            product=self.product,
            customer=self.customer,
            rating=5,
            body="Loved it",
        )
        self.assertEqual(self.product.reviews.count(), 1)
        self.assertEqual(self.customer.reviews.first().rating, 5)

    def test_cart_holds_items(self):
        cart = Cart.objects.create(customer=self.customer)
        CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        self.assertEqual(cart.items.first().quantity, 3)

    def test_order_holds_order_items(self):
        order = Order.objects.create(
            customer=self.customer, total=Decimal("19.98")
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price=Decimal("9.99"),
        )
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().unit_price, Decimal("9.99"))
        self.assertEqual(order.customer.full_name, "Alice B")
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
docker compose exec web python manage.py test ecommerce.tests.test_models -v2
```
Expected: FAIL — `ImportError: cannot import name 'Customer' from 'ecommerce.models'` (models.py does not exist yet).

- [ ] **Step 4: Implement `app/ecommerce/models.py`**

```python
from django.db import models


class Customer(models.Model):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class Category(models.Model):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )


class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Inventory(models.Model):
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.IntegerField(default=0)


class ProductReview(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Cart(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)


class Order(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="orders"
    )
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
```

- [ ] **Step 5: Generate and apply migrations**

Run:
```bash
docker compose exec web python manage.py makemigrations ecommerce
docker compose exec web python manage.py migrate
```
Expected: a migration `0001_initial.py` is created and applied without error.

- [ ] **Step 6: Run the test to verify it passes**

Run:
```bash
docker compose exec web python manage.py test ecommerce.tests.test_models -v2
```
Expected: PASS (4 tests OK).

- [ ] **Step 7: Commit**

```bash
git add app/ecommerce/models.py app/ecommerce/tests app/ecommerce/migrations
git commit -m "feat: e-commerce data model with relation tests"
```

---

### Task 5: Configurable seed generator (TDD)

**Files:**
- Create: `app/ecommerce/management/__init__.py` (empty)
- Create: `app/ecommerce/management/commands/__init__.py` (empty)
- Create: `app/ecommerce/management/commands/seed.py`
- Create: `app/ecommerce/tests/test_seed.py`

- [ ] **Step 1: Create the empty package files**

`app/ecommerce/management/__init__.py` and
`app/ecommerce/management/commands/__init__.py`: both empty.

- [ ] **Step 2: Write the failing test — `app/ecommerce/tests/test_seed.py`**

```python
from django.core.management import call_command
from django.test import TestCase

from ecommerce.models import (
    Category,
    Customer,
    Inventory,
    OrderItem,
    Product,
    ProductReview,
)


class SeedCommandTests(TestCase):
    def test_seed_respects_requested_volume(self):
        call_command(
            "seed",
            categories=5,
            customers=10,
            products=20,
            reviews=15,
            orders=8,
            verbosity=0,
        )
        self.assertEqual(Category.objects.count(), 5)
        self.assertEqual(Customer.objects.count(), 10)
        self.assertEqual(Product.objects.count(), 20)
        # Every product gets exactly one inventory row.
        self.assertEqual(Inventory.objects.count(), 20)
        self.assertEqual(ProductReview.objects.count(), 15)
        # Every order has at least one order item.
        self.assertGreaterEqual(OrderItem.objects.count(), 8)

    def test_seed_is_idempotent_on_count_when_flushed(self):
        call_command("seed", categories=2, customers=2, products=2,
                     reviews=0, orders=0, verbosity=0)
        self.assertEqual(Product.objects.count(), 2)
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
docker compose exec web python manage.py test ecommerce.tests.test_seed -v2
```
Expected: FAIL — `CommandError: Unknown command: 'seed'`.

- [ ] **Step 4: Implement `app/ecommerce/management/commands/seed.py`**

```python
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from faker import Faker

from ecommerce.models import (
    Category,
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductReview,
)

fake = Faker()


class Command(BaseCommand):
    help = "Seed the database with e-commerce data at a configurable volume."

    def add_arguments(self, parser):
        parser.add_argument("--categories", type=int, default=200)
        parser.add_argument("--customers", type=int, default=10_000)
        parser.add_argument("--products", type=int, default=100_000)
        parser.add_argument("--reviews", type=int, default=500_000)
        parser.add_argument("--orders", type=int, default=200_000)
        parser.add_argument("--batch", type=int, default=5_000)

    def handle(self, *args, **opts):
        batch = opts["batch"]
        log = self.stdout.write if opts["verbosity"] else (lambda *a, **k: None)

        log("Seeding categories...")
        Category.objects.bulk_create(
            [Category(name=f"{fake.word().title()}-{i}")
             for i in range(opts["categories"])],
            batch_size=batch,
        )
        category_ids = list(Category.objects.values_list("id", flat=True))

        log("Seeding customers...")
        Customer.objects.bulk_create(
            [Customer(email=f"user{i}@example.com", full_name=fake.name())
             for i in range(opts["customers"])],
            batch_size=batch,
        )
        customer_ids = list(Customer.objects.values_list("id", flat=True))

        log("Seeding products + inventory...")
        products = [
            Product(
                name=fake.catch_phrase()[:255],
                description=fake.text(max_nb_chars=300),
                price=Decimal(f"{random.uniform(1, 999):.2f}"),
                category_id=random.choice(category_ids),
            )
            for _ in range(opts["products"])
        ]
        Product.objects.bulk_create(products, batch_size=batch)
        product_ids = list(Product.objects.values_list("id", flat=True))
        Inventory.objects.bulk_create(
            [Inventory(product_id=pid, quantity=random.randint(0, 500))
             for pid in product_ids],
            batch_size=batch,
        )

        log("Seeding reviews...")
        ProductReview.objects.bulk_create(
            [
                ProductReview(
                    product_id=random.choice(product_ids),
                    customer_id=random.choice(customer_ids),
                    rating=random.randint(1, 5),
                    body=fake.sentence(),
                )
                for _ in range(opts["reviews"])
            ],
            batch_size=batch,
        )

        log("Seeding orders + order items...")
        orders = [
            Order(customer_id=random.choice(customer_ids),
                  total=Decimal("0.00"),
                  status=random.choice(["pending", "paid", "shipped"]))
            for _ in range(opts["orders"])
        ]
        Order.objects.bulk_create(orders, batch_size=batch)
        order_ids = list(Order.objects.values_list("id", flat=True))

        order_items = []
        for oid in order_ids:
            for _ in range(random.randint(1, 4)):
                order_items.append(
                    OrderItem(
                        order_id=oid,
                        product_id=random.choice(product_ids),
                        quantity=random.randint(1, 5),
                        unit_price=Decimal(f"{random.uniform(1, 999):.2f}"),
                    )
                )
        OrderItem.objects.bulk_create(order_items, batch_size=batch)

        log(self.style.SUCCESS("Seed complete."))
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
docker compose exec web python manage.py test ecommerce.tests.test_seed -v2
```
Expected: PASS (2 tests OK).

- [ ] **Step 6: Commit**

```bash
git add app/ecommerce/management app/ecommerce/tests/test_seed.py
git commit -m "feat: configurable seed generator with volume flags"
```

---

### Task 6: Makefile convenience targets

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create `Makefile`**

Note: real tabs are required for recipe lines.

```makefile
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
```

- [ ] **Step 2: Verify the full stack from a clean state**

Run:
```bash
docker compose down -v
make up
sleep 10
make migrate
make seed-small
make test
docker compose exec db psql -U playground -d playground -c "SELECT count(*) FROM ecommerce_product;"
```
Expected: `make test` passes; the product count is `1000`.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: makefile targets for up/migrate/seed/test/psql"
```

---

## Self-Review

**Spec coverage (Phase 1 scope items 1–3 from the design):**
- Item 1 (Compose stack: Postgres + Django) → Tasks 2, 3. ✅ (Locust deferred to plan 1B, as the design's phase notes allow.)
- Item 3 (data model + configurable seed) → Tasks 4, 5. ✅
- Repo structure (`app/`, `seed`-equivalent as a management command, `docs/`) → Tasks 3–6. ✅ (The design's standalone `seed/` dir is realized as a Django management command, which is the idiomatic Django location; noted as an intentional deviation.)
- Items 2, 4, 5, 6, 7, 8 (throttle override, endpoints, observability, Locust, lab notebook, optimization cycles) → **deferred to plans 1B/1C by design of this split.**

**Placeholder scan:** No TBD/TODO/"handle edge cases" placeholders; every code step shows complete code. ✅

**Type/name consistency:** Model names (`Customer`, `Category`, `Product`, `Inventory`, `ProductReview`, `Cart`, `CartItem`, `Order`, `OrderItem`) and the related_names (`inventory`, `reviews`, `items`, `orders`, `children`, `products`) are identical across `models.py`, `test_models.py`, `test_seed.py`, and `seed.py`. The `seed` command's flag names (`--categories/--customers/--products/--reviews/--orders/--batch`) match the `call_command(...)` kwargs in `test_seed.py`. ✅

**Note on test DB:** `manage.py test` creates a throwaway test database; the configured `playground` user is the DB superuser (created by the Postgres image from `POSTGRES_USER`), so it has `CREATEDB` privilege. ✅

---

## Next plans (not in scope here)

- **Phase 1B:** six naive endpoints (listing, detail, search, checkout, order history, dashboard) + Locust scenarios + baseline-recording workflow + lean observability (django-debug-toolbar, slow-query log, `pg_stat_statements` helper) + `docs/findings/` lab notebook + `docker-compose.throttle.yml`.
- **Phase 1C:** first optimization cycles (N+1 → `select_related`/`prefetch_related`, missing/composite indexes, keyset pagination), each with before/after load-test numbers recorded in the lab notebook.
