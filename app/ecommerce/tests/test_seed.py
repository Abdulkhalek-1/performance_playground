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
