# Performance Playground — Phase 1B (Endpoints + Load-Testing Harness) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add six deliberately naive DRF endpoints to the e-commerce app, plus a Locust load-testing harness, gated django-silk profiling, a DB-throttle override, and a lab-notebook scaffold — so we can drive load, find limits, and record baselines.

**Architecture:** Hand-written DRF views + serializers live in a focused `ecommerce/api/` package. Serializers are intentionally naive (nested without `select_related`/`prefetch_related`; `LimitOffsetPagination`; `ILIKE` search; lock-free checkout) so Phase 1C has real bottlenecks to fix. django-silk is added but gated behind `DJANGO_SILK=1`. Locust runs as a `loadgen` Compose service; a `make baseline` target ramps a single endpoint headless and writes CSV stats into `docs/findings/baselines/`.

**Tech Stack:** Django 5.1, Django REST Framework, django-silk, Locust (official image), PostgreSQL 18, Docker Compose.

**Prerequisite:** Phase 1A is merged to `master`; the Compose stack (`db` + `web`) builds and the e-commerce models + seed exist. Work on branch `phase1b`. Run all docker/make commands with the Bash sandbox disabled (`dangerouslyDisableSandbox: true`).

---

## File Structure

```
app/
  requirements.txt                  # + djangorestframework, django-silk
  config/
    settings.py                     # + rest_framework, DRF pagination, gated silk, STATIC_URL
    urls.py                         # include ecommerce.api.urls under /api/; gated /silk/
  ecommerce/
    api/
      __init__.py                   # empty
      serializers.py                # naive serializers (built up across tasks)
      views.py                      # 6 endpoint views (built up across tasks)
      urls.py                       # /api/ routes (built up across tasks)
    tests/
      test_api_listing.py
      test_api_detail.py
      test_api_search.py
      test_api_checkout.py
      test_api_orders.py
      test_api_dashboard.py
docker-compose.yml                  # + DJANGO_SILK passthrough on web; + loadgen service
docker-compose.throttle.yml         # db CPU/RAM caps
loadtest/
  locustfile.py                     # user classes + step-load shape
docs/findings/
  TEMPLATE.md
  baselines/.gitkeep
Makefile                            # + throttle-up, silk-up, baseline targets
```

`serializers.py`, `views.py`, and `urls.py` are appended to across Tasks 2–7; each task shows exactly what to add.

---

### Task 1: Wire DRF + gated silk + the `api` package skeleton

**Files:**
- Modify: `app/requirements.txt`
- Modify: `app/config/settings.py`
- Modify: `app/config/urls.py`
- Modify: `docker-compose.yml` (add `DJANGO_SILK` passthrough to `web`)
- Create: `app/ecommerce/api/__init__.py` (empty)
- Create: `app/ecommerce/api/serializers.py` (empty for now)
- Create: `app/ecommerce/api/views.py` (empty for now)
- Create: `app/ecommerce/api/urls.py` (empty urlpatterns)

- [ ] **Step 1: Add dependencies to `app/requirements.txt`**

Append these two lines so the file reads:
```
Django==5.1.4
psycopg[binary]==3.2.3
gunicorn==23.0.0
Faker==33.1.0
djangorestframework==3.15.2
django-silk==5.3.2
```

- [ ] **Step 2: Update `app/config/settings.py`**

Replace the `INSTALLED_APPS` list and add the new config blocks. The full file becomes:
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
    "rest_framework",
    "ecommerce",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

# django-silk is opt-in: it instruments every request and would pollute load-test
# numbers, so it is only enabled when DJANGO_SILK=1.
SILK_ENABLED = os.environ.get("DJANGO_SILK", "0") == "1"
if SILK_ENABLED:
    INSTALLED_APPS.append("silk")
    MIDDLEWARE.insert(0, "silk.middleware.SilkyMiddleware")

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

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 20,
}

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
```

- [ ] **Step 3: Update `app/config/urls.py`**

```python
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("api/", include("ecommerce.api.urls")),
]

if getattr(settings, "SILK_ENABLED", False):
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]
```

- [ ] **Step 4: Create the `api` package skeleton**

`app/ecommerce/api/__init__.py`: empty.
`app/ecommerce/api/serializers.py`: empty.
`app/ecommerce/api/views.py`: empty.
`app/ecommerce/api/urls.py`:
```python
urlpatterns = []
```

- [ ] **Step 5: Add `DJANGO_SILK` passthrough to the `web` service in `docker-compose.yml`**

In the `web:` service block, add an `environment` key (keep `env_file: .env`). The `web` block becomes:
```yaml
  web:
    build: ./app
    env_file: .env
    environment:
      - DJANGO_SILK=${DJANGO_SILK:-0}
    command: ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
    ports:
      - "8000:8000"
    volumes:
      - ./app:/app
    depends_on:
      db:
        condition: service_healthy
```

- [ ] **Step 6: Rebuild, migrate, verify the stack still boots and DRF is installed**

Run (sandbox disabled):
```bash
docker compose up -d --build web
docker compose exec -T web python manage.py migrate
docker compose exec -T web python -c "import rest_framework, silk; print('drf+silk import ok')"
curl -s http://localhost:8000/health/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/products/
```
Expected: migrate OK; prints `drf+silk import ok`; health returns `{"status": "ok"}`; `/api/products/` returns `404` (no routes wired yet — correct for this task).

- [ ] **Step 7: Commit**

```bash
git add app/requirements.txt app/config app/ecommerce/api docker-compose.yml
git commit -m "feat: wire DRF + gated django-silk and api package skeleton"
```

---

### Task 2: Product listing endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_listing.py`
- Modify: `app/ecommerce/api/serializers.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_listing.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Product


class ProductListingTests(APITestCase):
    def setUp(self):
        self.cat_a = Category.objects.create(name="A")
        self.cat_b = Category.objects.create(name="B")
        for i in range(25):
            Product.objects.create(
                name=f"P{i}",
                description="d",
                price=Decimal("10.00") + i,
                category=self.cat_a if i % 2 == 0 else self.cat_b,
            )

    def test_list_returns_paginated_envelope(self):
        res = self.client.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 25)
        self.assertEqual(len(res.data["results"]), 20)  # default limit
        self.assertIn("category", res.data["results"][0])
        self.assertIn("name", res.data["results"][0]["category"])

    def test_filter_by_category(self):
        res = self.client.get(f"/api/products/?category={self.cat_a.id}")
        self.assertEqual(res.data["count"], 13)  # even i in 0..24

    def test_filter_by_price_range(self):
        res = self.client.get("/api/products/?min_price=15&max_price=20")
        self.assertEqual(res.data["count"], 6)  # prices 15..20

    def test_limit_offset_pagination(self):
        res = self.client.get("/api/products/?limit=5&offset=5")
        self.assertEqual(len(res.data["results"]), 5)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_listing -v2
```
Expected: FAIL — 404 responses (no route), so `res.data["count"]` raises `KeyError`/assertion error.

- [ ] **Step 3: Add serializers to `app/ecommerce/api/serializers.py`**

```python
from rest_framework import serializers

from ecommerce.models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "price", "category"]
```

- [ ] **Step 4: Add the view to `app/ecommerce/api/views.py`**

```python
from rest_framework import generics

from ecommerce.api.serializers import ProductListSerializer
from ecommerce.models import Product

ALLOWED_ORDERING = {"price", "-price", "name", "-name", "created_at", "-created_at"}


class ProductListView(generics.ListAPIView):
    """Naive: nested category serializer triggers N+1; filters/sort hit unindexed columns."""

    serializer_class = ProductListSerializer

    def get_queryset(self):
        qs = Product.objects.all().order_by("id")
        params = self.request.query_params
        category = params.get("category")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        ordering = params.get("ordering")
        if category:
            qs = qs.filter(category_id=category)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if ordering in ALLOWED_ORDERING:
            qs = qs.order_by(ordering)
        return qs
```

- [ ] **Step 5: Add the route to `app/ecommerce/api/urls.py`**

```python
from django.urls import path

from ecommerce.api import views

urlpatterns = [
    path("products/", views.ProductListView.as_view()),
]
```

- [ ] **Step 6: Run the test, confirm it PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_listing -v2
```
Expected: PASS (4 tests OK).

- [ ] **Step 7: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_listing.py
git commit -m "feat: naive product listing endpoint with filters and offset pagination"
```

---

### Task 3: Product detail endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_detail.py`
- Modify: `app/ecommerce/api/serializers.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_detail.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Customer, Product, ProductReview


class ProductDetailTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="A")
        self.customer = Customer.objects.create(email="c@e.com", full_name="C")
        self.product = Product.objects.create(
            name="Main", description="desc", price=Decimal("9.99"), category=self.cat
        )
        self.other = Product.objects.create(
            name="Other", description="d", price=Decimal("5.00"), category=self.cat
        )
        ProductReview.objects.create(
            product=self.product, customer=self.customer, rating=4, body="ok"
        )

    def test_detail_includes_reviews_and_related(self):
        res = self.client.get(f"/api/products/{self.product.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["id"], self.product.id)
        self.assertEqual(res.data["category"]["name"], "A")
        self.assertEqual(len(res.data["reviews"]), 1)
        self.assertEqual(res.data["reviews"][0]["rating"], 4)
        related_ids = [r["id"] for r in res.data["related_products"]]
        self.assertIn(self.other.id, related_ids)
        self.assertNotIn(self.product.id, related_ids)

    def test_detail_404_for_missing(self):
        res = self.client.get("/api/products/999999/")
        self.assertEqual(res.status_code, 404)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_detail -v2
```
Expected: FAIL — `/api/products/<id>/` returns 404 (no route), so the 200 assertion fails.

- [ ] **Step 3: Add serializers to `app/ecommerce/api/serializers.py`**

Append these classes (the file already imports `serializers`, `Category`, `Product`; add the `ProductReview` import to the existing model import line so it reads `from ecommerce.models import Category, Product, ProductReview`):
```python
class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = ["id", "rating", "body", "customer_id", "created_at"]


class RelatedProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "price"]


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    related_products = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "category",
            "reviews",
            "related_products",
        ]

    def get_related_products(self, obj):
        qs = Product.objects.filter(category_id=obj.category_id).exclude(id=obj.id)[:5]
        return RelatedProductSerializer(qs, many=True).data
```

- [ ] **Step 4: Add the view to `app/ecommerce/api/views.py`**

Append (and add `ProductDetailSerializer` to the existing serializers import so it reads `from ecommerce.api.serializers import ProductDetailSerializer, ProductListSerializer`):
```python
class ProductDetailView(generics.RetrieveAPIView):
    """Naive: reviews + related_products are extra queries with no prefetch."""

    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer
```

- [ ] **Step 5: Add the route to `app/ecommerce/api/urls.py`**

Add the detail route. Place it AFTER `products/` and after the search route will go (int converter prevents collision). The list becomes:
```python
urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
]
```

- [ ] **Step 6: Run the test, confirm it PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_detail -v2
```
Expected: PASS (2 tests OK).

- [ ] **Step 7: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_detail.py
git commit -m "feat: naive product detail endpoint with reviews and related products"
```

---

### Task 4: Search endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_search.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

(Reuses `ProductListSerializer` — no serializer change.)

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_search.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Product


class ProductSearchTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="A")
        Product.objects.create(
            name="Red Shoes", description="comfortable", price=Decimal("20"), category=self.cat
        )
        Product.objects.create(
            name="Blue Hat", description="warm wool", price=Decimal("15"), category=self.cat
        )

    def test_search_matches_name(self):
        res = self.client.get("/api/products/search/?q=shoes")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["name"], "Red Shoes")

    def test_search_matches_description(self):
        res = self.client.get("/api/products/search/?q=wool")
        self.assertEqual(res.data["count"], 1)

    def test_search_requires_q(self):
        res = self.client.get("/api/products/search/")
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_search -v2
```
Expected: FAIL — `/api/products/search/` returns 404 (no route).

- [ ] **Step 3: Add the view to `app/ecommerce/api/views.py`**

Append (add the imports `from django.db.models import Q` at the top of the file with the other imports, and `from rest_framework.exceptions import ValidationError`):
```python
class ProductSearchView(generics.ListAPIView):
    """Naive: ILIKE substring match on unindexed text columns -> sequential scan."""

    serializer_class = ProductListSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q")
        if not q:
            raise ValidationError({"q": "This query parameter is required."})
        return Product.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        ).order_by("id")
```

- [ ] **Step 4: Add the route to `app/ecommerce/api/urls.py`**

Add the search route BEFORE the `<int:pk>` route. The list becomes:
```python
urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/search/", views.ProductSearchView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
]
```

- [ ] **Step 5: Run the test, confirm it PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_search -v2
```
Expected: PASS (3 tests OK).

- [ ] **Step 6: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_search.py
git commit -m "feat: naive ILIKE product search endpoint"
```

---

### Task 5: Checkout endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_checkout.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_checkout.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Customer, Inventory, Order, OrderItem, Product


class CheckoutTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="A")
        self.customer = Customer.objects.create(email="c@e.com", full_name="C")
        self.p1 = Product.objects.create(
            name="P1", description="d", price=Decimal("10.00"), category=self.cat
        )
        self.p2 = Product.objects.create(
            name="P2", description="d", price=Decimal("2.50"), category=self.cat
        )
        Inventory.objects.create(product=self.p1, quantity=100)
        Inventory.objects.create(product=self.p2, quantity=100)

    def test_checkout_creates_order_and_decrements_inventory(self):
        payload = {
            "customer_id": self.customer.id,
            "items": [
                {"product_id": self.p1.id, "quantity": 3},
                {"product_id": self.p2.id, "quantity": 2},
            ],
        }
        res = self.client.post("/api/checkout/", payload, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["total"], "35.00")  # 3*10 + 2*2.50
        self.assertEqual(Inventory.objects.get(product=self.p1).quantity, 97)
        self.assertEqual(Inventory.objects.get(product=self.p2).quantity, 98)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 2)

    def test_checkout_requires_fields(self):
        res = self.client.post("/api/checkout/", {"items": []}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_checkout_unknown_product(self):
        payload = {
            "customer_id": self.customer.id,
            "items": [{"product_id": 999999, "quantity": 1}],
        }
        res = self.client.post("/api/checkout/", payload, format="json")
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_checkout -v2
```
Expected: FAIL — `/api/checkout/` returns 404 (no route).

- [ ] **Step 3: Add the view to `app/ecommerce/api/views.py`**

Append (add these imports at the top with the others: `from decimal import Decimal`, `from rest_framework import status`, `from rest_framework.response import Response`, `from rest_framework.views import APIView`, and extend the models import to include `Customer, Inventory, Order, OrderItem` so it reads `from ecommerce.models import Customer, Inventory, Order, OrderItem, Product`):
```python
class CheckoutView(APIView):
    """Naive: read-modify-write inventory with NO row locking (intentional contention bug
    to be fixed in Phase 1C). No surrounding transaction either."""

    def post(self, request):
        customer_id = request.data.get("customer_id")
        items = request.data.get("items")
        if not customer_id or not items:
            raise ValidationError({"detail": "customer_id and items are required."})
        if not Customer.objects.filter(id=customer_id).exists():
            raise ValidationError({"customer_id": "Unknown customer."})

        order = Order.objects.create(
            customer_id=customer_id, total=Decimal("0.00"), status="paid"
        )
        total = Decimal("0.00")
        response_items = []
        for item in items:
            product_id = item.get("product_id")
            quantity = int(item.get("quantity", 1))
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                raise ValidationError({"product_id": f"Unknown product {product_id}."})
            unit_price = product.price
            inventory = Inventory.objects.get(product_id=product_id)
            inventory.quantity = inventory.quantity - quantity
            inventory.save()
            OrderItem.objects.create(
                order=order,
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
            )
            total += unit_price * quantity
            response_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
            )
        order.total = total
        order.save()
        return Response(
            {"order_id": order.id, "total": str(total), "items": response_items},
            status=status.HTTP_201_CREATED,
        )
```

- [ ] **Step 4: Add the route to `app/ecommerce/api/urls.py`**

Add the checkout route. The list becomes:
```python
urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/search/", views.ProductSearchView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
]
```

- [ ] **Step 5: Run the test, confirm it PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_checkout -v2
```
Expected: PASS (3 tests OK).

- [ ] **Step 6: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_checkout.py
git commit -m "feat: naive lock-free checkout endpoint"
```

---

### Task 6: Order history endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_orders.py`
- Modify: `app/ecommerce/api/serializers.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_orders.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Customer, Order, OrderItem, Product


class OrderHistoryTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="A")
        self.customer = Customer.objects.create(email="c@e.com", full_name="C")
        self.product = Product.objects.create(
            name="P", description="d", price=Decimal("10.00"), category=self.cat
        )
        self.order = Order.objects.create(
            customer=self.customer, total=Decimal("20.00"), status="paid"
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=2, unit_price=Decimal("10.00")
        )

    def test_order_history_returns_orders_with_items(self):
        res = self.client.get(f"/api/customers/{self.customer.id}/orders/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["customer_id"], self.customer.id)
        self.assertEqual(len(res.data["orders"]), 1)
        self.assertEqual(res.data["orders"][0]["total"], "20.00")
        self.assertEqual(len(res.data["orders"][0]["items"]), 1)
        self.assertEqual(res.data["orders"][0]["items"][0]["quantity"], 2)

    def test_unknown_customer_400(self):
        res = self.client.get("/api/customers/999999/orders/")
        self.assertEqual(res.status_code, 400)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_orders -v2
```
Expected: FAIL — route returns 404.

- [ ] **Step 3: Add serializers to `app/ecommerce/api/serializers.py`**

Append (extend the model import to include `Order, OrderItem` so it reads `from ecommerce.models import Category, Order, OrderItem, Product, ProductReview`):
```python
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product_id", "quantity", "unit_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "status", "total", "created_at", "items"]
```

- [ ] **Step 4: Add the view to `app/ecommerce/api/views.py`**

Append (extend the serializers import to include `OrderSerializer`):
```python
class CustomerOrdersView(APIView):
    """Naive: nested items serializer triggers N+1 across the customer's orders."""

    def get(self, request, customer_id):
        if not Customer.objects.filter(id=customer_id).exists():
            raise ValidationError({"customer_id": "Unknown customer."})
        orders = Order.objects.filter(customer_id=customer_id).order_by("-created_at")
        data = OrderSerializer(orders, many=True).data
        return Response({"customer_id": int(customer_id), "orders": data})
```

- [ ] **Step 5: Add the route to `app/ecommerce/api/urls.py`**

```python
urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/search/", views.ProductSearchView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
    path("customers/<int:customer_id>/orders/", views.CustomerOrdersView.as_view()),
]
```

- [ ] **Step 6: Run the test, confirm it PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_orders -v2
```
Expected: PASS (2 tests OK).

- [ ] **Step 7: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_orders.py
git commit -m "feat: naive customer order-history endpoint"
```

---

### Task 7: Top-products dashboard endpoint (TDD)

**Files:**
- Create: `app/ecommerce/tests/test_api_dashboard.py`
- Modify: `app/ecommerce/api/views.py`
- Modify: `app/ecommerce/api/urls.py`

- [ ] **Step 1: Write the failing test — `app/ecommerce/tests/test_api_dashboard.py`**

```python
from decimal import Decimal

from rest_framework.test import APITestCase

from ecommerce.models import Category, Customer, Order, OrderItem, Product


class DashboardTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="A")
        self.customer = Customer.objects.create(email="c@e.com", full_name="C")
        self.popular = Product.objects.create(
            name="Popular", description="d", price=Decimal("10"), category=self.cat
        )
        self.meh = Product.objects.create(
            name="Meh", description="d", price=Decimal("10"), category=self.cat
        )
        order = Order.objects.create(customer=self.customer, total=Decimal("0"), status="paid")
        OrderItem.objects.create(
            order=order, product=self.popular, quantity=10, unit_price=Decimal("10")
        )
        OrderItem.objects.create(
            order=order, product=self.meh, quantity=3, unit_price=Decimal("10")
        )

    def test_top_products_ranked_by_quantity(self):
        res = self.client.get("/api/dashboard/top-products/")
        self.assertEqual(res.status_code, 200)
        top = res.data["top_products"]
        self.assertEqual(top[0]["product_id"], self.popular.id)
        self.assertEqual(top[0]["total_quantity"], 10)
        self.assertEqual(top[0]["name"], "Popular")

    def test_limit_param(self):
        res = self.client.get("/api/dashboard/top-products/?limit=1")
        self.assertEqual(len(res.data["top_products"]), 1)
```

- [ ] **Step 2: Run the test, confirm it FAILS**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce.tests.test_api_dashboard -v2
```
Expected: FAIL — route returns 404.

- [ ] **Step 3: Add the view to `app/ecommerce/api/views.py`**

Append (add `from django.db.models import Sum` to the top imports alongside the existing `from django.db.models import Q` — combine into `from django.db.models import Q, Sum`):
```python
class TopProductsView(APIView):
    """Naive: full GROUP BY + SUM aggregation over order_items, no precomputation."""

    def get(self, request):
        limit = int(request.query_params.get("limit", 10))
        rows = list(
            OrderItem.objects.values("product_id")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")[:limit]
        )
        product_ids = [r["product_id"] for r in rows]
        names = dict(
            Product.objects.filter(id__in=product_ids).values_list("id", "name")
        )
        top = [
            {
                "product_id": r["product_id"],
                "name": names.get(r["product_id"]),
                "total_quantity": r["total_quantity"],
            }
            for r in rows
        ]
        return Response({"top_products": top})
```

- [ ] **Step 4: Add the route to `app/ecommerce/api/urls.py`**

```python
urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/search/", views.ProductSearchView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
    path("customers/<int:customer_id>/orders/", views.CustomerOrdersView.as_view()),
    path("dashboard/top-products/", views.TopProductsView.as_view()),
]
```

- [ ] **Step 5: Run the full ecommerce test suite, confirm everything PASSES**

Run:
```bash
docker compose exec -T web python manage.py test ecommerce -v2
```
Expected: PASS — all tests (6 from 1A + the new API tests: 4+2+3+3+2+2 = 16) green.

- [ ] **Step 6: Commit**

```bash
git add app/ecommerce/api app/ecommerce/tests/test_api_dashboard.py
git commit -m "feat: naive top-products dashboard aggregation endpoint"
```

---

### Task 8: DB throttle override

**Files:**
- Create: `docker-compose.throttle.yml`

- [ ] **Step 1: Create `docker-compose.throttle.yml`**

```yaml
# Overlay that caps the db container to ~1 CPU / 512MB so bottlenecks appear fast.
# Use: docker compose -f docker-compose.yml -f docker-compose.throttle.yml up -d
services:
  db:
    cpus: 1.0
    mem_limit: 512m
```

- [ ] **Step 2: Verify the override applies**

Run (sandbox disabled):
```bash
docker compose -f docker-compose.yml -f docker-compose.throttle.yml up -d db
docker inspect performance_playground-db-1 --format '{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}'
```
Expected: prints `1000000000 536870912` (1.0 CPU in nano-CPUs, 512MB in bytes). If the container name differs, find it with `docker compose ps -q db | xargs docker inspect --format '{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}'`.

- [ ] **Step 3: Restore the un-throttled stack**

Run:
```bash
docker compose up -d db
```
Expected: db recreated without limits (so later tasks/tests aren't throttled).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.throttle.yml
git commit -m "feat: db throttle override (1 cpu / 512mb)"
```

---

### Task 9: Locust harness, loadgen service, lab notebook, Makefile targets

**Files:**
- Create: `loadtest/locustfile.py`
- Create: `docs/findings/TEMPLATE.md`
- Create: `docs/findings/baselines/.gitkeep`
- Modify: `docker-compose.yml` (add `loadgen` service)
- Modify: `Makefile` (add `throttle-up`, `silk-up`, `baseline`)
- Modify: `.gitignore` (ignore generated Locust CSVs)

- [ ] **Step 1: Create `loadtest/locustfile.py`**

```python
import os
import random

from locust import HttpUser, LoadTestShape, between, task

# ID ranges should match the seeded data volume so requests mostly hit real rows.
# Defaults match `make seed` defaults; override via env for other volumes.
MAX_PRODUCT_ID = int(os.environ.get("MAX_PRODUCT_ID", "100000"))
MAX_CUSTOMER_ID = int(os.environ.get("MAX_CUSTOMER_ID", "10000"))
SEARCH_TERMS = ["red", "blue", "pro", "smart", "eco", "premium", "classic", "ultra"]


class ListingUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def list_products(self):
        offset = random.choice([0, 100, 1000, 5000, 20000])
        self.client.get(
            f"/api/products/?limit=20&offset={offset}", name="/api/products/"
        )


class DetailUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def detail(self):
        pid = random.randint(1, MAX_PRODUCT_ID)
        self.client.get(f"/api/products/{pid}/", name="/api/products/[id]")


class SearchUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def search(self):
        q = random.choice(SEARCH_TERMS)
        self.client.get(f"/api/products/search/?q={q}", name="/api/products/search/")


class OrderHistoryUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task
    def orders(self):
        cid = random.randint(1, MAX_CUSTOMER_ID)
        self.client.get(
            f"/api/customers/{cid}/orders/", name="/api/customers/[id]/orders/"
        )


class DashboardUser(HttpUser):
    wait_time = between(0.5, 1.0)

    @task
    def dashboard(self):
        self.client.get(
            "/api/dashboard/top-products/", name="/api/dashboard/top-products/"
        )


class CheckoutUser(HttpUser):
    wait_time = between(0.2, 0.8)

    @task
    def checkout(self):
        payload = {
            "customer_id": random.randint(1, MAX_CUSTOMER_ID),
            "items": [
                {
                    "product_id": random.randint(1, MAX_PRODUCT_ID),
                    "quantity": random.randint(1, 3),
                }
            ],
        }
        self.client.post("/api/checkout/", json=payload, name="/api/checkout/")


class StepLoadShape(LoadTestShape):
    """Ramp concurrent users in steps so we can watch where p95 latency / errors break."""

    steps = [
        {"duration": 60, "users": 25, "spawn_rate": 25},
        {"duration": 120, "users": 50, "spawn_rate": 25},
        {"duration": 180, "users": 100, "spawn_rate": 50},
        {"duration": 240, "users": 200, "spawn_rate": 50},
        {"duration": 300, "users": 400, "spawn_rate": 100},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for step in self.steps:
            if run_time < step["duration"]:
                return (step["users"], step["spawn_rate"])
        return None
```

- [ ] **Step 2: Create `docs/findings/TEMPLATE.md`**

```markdown
# Finding: <short title>

**Date:** YYYY-MM-DD
**Endpoint(s):** <e.g. GET /api/products/>
**Throttle:** <on (1cpu/512mb) | off>  **Seed volume:** <products/customers/...>

## Hypothesis
<What I think is slow and why.>

## Baseline (before)
- Ramp: step shape (25 -> 400 users over 5m)
- Limit reached at: <N concurrent users>
- p50 / p95 / p99 latency: <ms / ms / ms>
- Throughput at limit: <RPS>
- Error rate: <%>
- Query evidence: <silk per-request query count, EXPLAIN ANALYZE excerpt, pg_stat_statements row>
- CSV: docs/findings/baselines/<file>_stats.csv

## The fix
<What I changed and the reasoning. Link the commit.>

## After
- p50 / p95 / p99 latency: <ms / ms / ms>
- Throughput: <RPS>  Error rate: <%>
- Query evidence: <new query count / plan>

## Lesson learned
<The transferable takeaway.>
```

- [ ] **Step 3: Create `docs/findings/baselines/.gitkeep`** (empty file)

- [ ] **Step 4: Add the `loadgen` service to `docker-compose.yml`**

Insert under `services:` (after `web`, before the top-level `volumes:` key):
```yaml
  loadgen:
    image: locustio/locust:2.32.4
    depends_on:
      - web
    environment:
      - MAX_PRODUCT_ID=${MAX_PRODUCT_ID:-100000}
      - MAX_CUSTOMER_ID=${MAX_CUSTOMER_ID:-10000}
    ports:
      - "8089:8089"
    volumes:
      - ./loadtest:/mnt/locust
      - ./docs/findings/baselines:/mnt/baselines
    command: -f /mnt/locust/locustfile.py --host http://web:8000
```

- [ ] **Step 5: Ignore generated Locust CSVs — append to `.gitignore`**

Append these lines:
```
docs/findings/baselines/*_stats.csv
docs/findings/baselines/*_stats_history.csv
docs/findings/baselines/*_failures.csv
docs/findings/baselines/*_exceptions.csv
```

- [ ] **Step 6: Replace `Makefile` with the full version including new targets**

```makefile
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
```

- [ ] **Step 7: Validate compose config and smoke-test the harness**

Run (sandbox disabled). This seeds a small dataset, then runs a 20-second ramp of `ListingUser` and checks a CSV was produced:
```bash
docker compose up -d --build web
docker compose exec -T web python manage.py migrate
docker compose exec -T web python manage.py seed --categories 20 --customers 200 --products 1000 --reviews 500 --orders 200
docker compose config >/dev/null && echo "compose config OK"
MAX_PRODUCT_ID=1000 MAX_CUSTOMER_ID=200 docker compose run --rm loadgen -f /mnt/locust/locustfile.py --host http://web:8000 --headless --run-time 20s --csv /mnt/baselines/smoke ListingUser
ls -1 docs/findings/baselines/smoke_stats.csv && head -2 docs/findings/baselines/smoke_stats.csv
```
Expected: `compose config OK`; Locust runs for ~20s and reports a non-zero request count with a low failure rate; `smoke_stats.csv` exists and its header row plus an aggregated row are printed. (The CSV is gitignored, so it won't be committed.)

- [ ] **Step 8: Remove the smoke CSVs and commit**

```bash
rm -f docs/findings/baselines/smoke_stats*.csv docs/findings/baselines/smoke_failures.csv docs/findings/baselines/smoke_exceptions.csv
git add loadtest docs/findings docker-compose.yml Makefile .gitignore
git commit -m "feat: locust load-test harness, loadgen service, lab notebook, make targets"
```

---

## Self-Review

**Spec coverage:**
- Six naive DRF endpoints with the specified contracts → Tasks 2–7. ✅ (Listing envelope + nested category; detail with reviews + related; search with required `q`; checkout 201 + lock-free inventory decrement; order history; dashboard top-N.)
- Built from scratch with DRF, intentionally naive → serializers have no `select_related`/`prefetch_related`; listing uses `LimitOffsetPagination`; search uses `icontains`; checkout has no locking. ✅
- django-silk gated behind `DJANGO_SILK=1` → Task 1 (settings + urls), Task 9 (`silk-up` target). ✅
- Throttle override (~1 CPU/512MB) → Task 8. ✅
- Locust harness + loadgen service + `make baseline` writing CSVs to `docs/findings/baselines/` → Task 9. ✅
- Lab notebook (`TEMPLATE.md` + `baselines/`) → Task 9. ✅
- DRF correctness tests per endpoint → Tasks 2–7 (`APITestCase`). ✅
- "Limit" defined as p95 > threshold OR error rate > 1%, found via a rising-user ramp → `StepLoadShape` + `TEMPLATE.md` records the crossover. ✅
- Out of scope (optimizations, Locust-on-Machine-2, Grafana) → not included. ✅

**Placeholder scan:** No TBD/TODO/"handle edge cases". `TEMPLATE.md` contains `<...>` fill-ins, but it is intentionally a blank template document, not plan placeholder text. Every code step shows complete code. ✅

**Type/name consistency:** View class names (`ProductListView`, `ProductDetailView`, `ProductSearchView`, `CheckoutView`, `CustomerOrdersView`, `TopProductsView`) are identical in `views.py` and `urls.py` across tasks. Serializer names (`CategorySerializer`, `ProductListSerializer`, `ReviewSerializer`, `RelatedProductSerializer`, `ProductDetailSerializer`, `OrderItemSerializer`, `OrderSerializer`) are consistent between definition and use. The incremental import lines are called out at each task where a file gains a new dependency. Locust user class names (`ListingUser`, etc.) match the `make baseline ENDPOINT=` usage. ✅

**Import-accumulation note for the implementer:** `views.py` and `serializers.py` grow their import lines across Tasks 2–7. Each task states the exact final import line to use. If you implement out of order, reconcile imports so every used name (`Q`, `Sum`, `Decimal`, `status`, `Response`, `APIView`, `ValidationError`, and all models/serializers) is imported exactly once at the top of the file.

---

## Next plan (not in scope here)

- **Phase 1C:** record naive baselines for each endpoint (using `make baseline`), then run optimization cycles — N+1 → `select_related`/`prefetch_related` (listing, order history), missing/composite indexes (listing filters, search), keyset pagination (listing), checkout row-locking (`select_for_update`), dashboard aggregation (materialized view / index) — each documented in `docs/findings/` with before/after numbers.
