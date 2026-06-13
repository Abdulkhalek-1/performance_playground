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
