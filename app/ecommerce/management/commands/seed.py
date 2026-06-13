import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from faker import Faker

from ecommerce.models import (
    Category,
    Customer,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductReview,
)

fake = Faker()


class Command(BaseCommand):
    help = "Seed the database with e-commerce data at a configurable volume."

    def add_arguments(self, parser):
        parser.add_argument("--categories", type=int, default=200)
        parser.add_argument("--customers", type=int, default=10_000)
        parser.add_argument("--products", type=int, default=100_000)
        parser.add_argument("--reviews", type=int, default=500_000)
        parser.add_argument("--orders", type=int, default=200_000)
        parser.add_argument("--batch", type=int, default=5_000)

    def handle(self, *args, **opts):
        batch = opts["batch"]
        log = self.stdout.write if opts["verbosity"] else (lambda *a, **k: None)

        log("Seeding categories...")
        Category.objects.bulk_create(
            [Category(name=f"{fake.word().title()}-{i}")
             for i in range(opts["categories"])],
            batch_size=batch,
        )
        category_ids = list(Category.objects.values_list("id", flat=True))

        log("Seeding customers...")
        Customer.objects.bulk_create(
            [Customer(email=f"user{i}@example.com", full_name=fake.name())
             for i in range(opts["customers"])],
            batch_size=batch,
        )
        customer_ids = list(Customer.objects.values_list("id", flat=True))

        log("Seeding products + inventory...")
        products = [
            Product(
                name=fake.catch_phrase()[:255],
                description=fake.text(max_nb_chars=300),
                price=Decimal(f"{random.uniform(1, 999):.2f}"),
                category_id=random.choice(category_ids),
            )
            for _ in range(opts["products"])
        ]
        Product.objects.bulk_create(products, batch_size=batch)
        product_ids = list(Product.objects.values_list("id", flat=True))
        Inventory.objects.bulk_create(
            [Inventory(product_id=pid, quantity=random.randint(0, 500))
             for pid in product_ids],
            batch_size=batch,
        )

        log("Seeding reviews...")
        ProductReview.objects.bulk_create(
            [
                ProductReview(
                    product_id=random.choice(product_ids),
                    customer_id=random.choice(customer_ids),
                    rating=random.randint(1, 5),
                    body=fake.sentence(),
                )
                for _ in range(opts["reviews"])
            ],
            batch_size=batch,
        )

        log("Seeding orders + order items...")
        orders = [
            Order(customer_id=random.choice(customer_ids),
                  total=Decimal("0.00"),
                  status=random.choice(["pending", "paid", "shipped"]))
            for _ in range(opts["orders"])
        ]
        Order.objects.bulk_create(orders, batch_size=batch)
        order_ids = list(Order.objects.values_list("id", flat=True))

        order_items = []
        for oid in order_ids:
            for _ in range(random.randint(1, 4)):
                order_items.append(
                    OrderItem(
                        order_id=oid,
                        product_id=random.choice(product_ids),
                        quantity=random.randint(1, 5),
                        unit_price=Decimal(f"{random.uniform(1, 999):.2f}"),
                    )
                )
        OrderItem.objects.bulk_create(order_items, batch_size=batch)

        log(self.style.SUCCESS("Seed complete."))
