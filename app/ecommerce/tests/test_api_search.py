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
