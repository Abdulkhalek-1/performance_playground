from django.db.models import Q

from rest_framework import generics
from rest_framework.exceptions import ValidationError

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
