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
