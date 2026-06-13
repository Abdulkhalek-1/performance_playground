from rest_framework import generics

from ecommerce.api.serializers import ProductDetailSerializer, ProductListSerializer
from ecommerce.models import Product

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
