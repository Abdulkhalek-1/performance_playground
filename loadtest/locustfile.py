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
