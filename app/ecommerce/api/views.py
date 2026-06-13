from decimal import Decimal

from django.db.models import Q

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.api.serializers import OrderSerializer, ProductDetailSerializer, ProductListSerializer
from ecommerce.models import Customer, Inventory, Order, OrderItem, Product

ALLOWED_ORDERING = {"price", "-price", "name", "-name", "created_at", "-created_at"}


class ProductListView(generics.ListAPIView):
    """Naive: nested category serializer triggers N+1; filters/sort hit unindexed columns."""

    serializer_class = ProductListSerializer

    def get_queryset(self):
        qs = Product.objects.all().order_by("id")
        params = self.request.query_params
        category = params.get("category")
        min_price = params.get("min_price")
        max_price = params.get("max_price")
        ordering = params.get("ordering")
        if category:
            qs = qs.filter(category_id=category)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if ordering in ALLOWED_ORDERING:
            qs = qs.order_by(ordering)
        return qs


class ProductDetailView(generics.RetrieveAPIView):
    """Naive: reviews + related_products are extra queries with no prefetch."""

    queryset = Product.objects.all()
    serializer_class = ProductDetailSerializer


class ProductSearchView(generics.ListAPIView):
    """Naive: ILIKE substring match on unindexed text columns -> sequential scan."""

    serializer_class = ProductListSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q")
        if not q:
            raise ValidationError({"q": "This query parameter is required."})
        return Product.objects.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        ).order_by("id")


class CheckoutView(APIView):
    """Naive: read-modify-write inventory with NO row locking (intentional contention bug
    to be fixed in Phase 1C). No surrounding transaction either."""

    def post(self, request):
        customer_id = request.data.get("customer_id")
        items = request.data.get("items")
        if not customer_id or not items:
            raise ValidationError({"detail": "customer_id and items are required."})
        if not Customer.objects.filter(id=customer_id).exists():
            raise ValidationError({"customer_id": "Unknown customer."})

        order = Order.objects.create(
            customer_id=customer_id, total=Decimal("0.00"), status="paid"
        )
        total = Decimal("0.00")
        response_items = []
        for item in items:
            product_id = item.get("product_id")
            quantity = int(item.get("quantity", 1))
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                raise ValidationError({"product_id": f"Unknown product {product_id}."})
            unit_price = product.price
            inventory = Inventory.objects.get(product_id=product_id)
            inventory.quantity = inventory.quantity - quantity
            inventory.save()
            OrderItem.objects.create(
                order=order,
                product_id=product_id,
                quantity=quantity,
                unit_price=unit_price,
            )
            total += unit_price * quantity
            response_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": str(unit_price),
                }
            )
        order.total = total
        order.save()
        return Response(
            {"order_id": order.id, "total": str(total), "items": response_items},
            status=status.HTTP_201_CREATED,
        )


class CustomerOrdersView(APIView):
    """Naive: nested items serializer triggers N+1 across the customer's orders."""

    def get(self, request, customer_id):
        if not Customer.objects.filter(id=customer_id).exists():
            raise ValidationError({"customer_id": "Unknown customer."})
        orders = Order.objects.filter(customer_id=customer_id).order_by("-created_at")
        data = OrderSerializer(orders, many=True).data
        return Response({"customer_id": int(customer_id), "orders": data})
