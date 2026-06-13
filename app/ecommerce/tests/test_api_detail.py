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
