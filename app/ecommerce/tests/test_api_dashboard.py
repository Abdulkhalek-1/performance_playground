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
