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
