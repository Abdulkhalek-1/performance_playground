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
