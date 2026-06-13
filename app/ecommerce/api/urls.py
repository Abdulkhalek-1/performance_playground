from django.urls import path

from ecommerce.api import views

urlpatterns = [
    path("products/", views.ProductListView.as_view()),
    path("products/search/", views.ProductSearchView.as_view()),
    path("products/<int:pk>/", views.ProductDetailView.as_view()),
    path("checkout/", views.CheckoutView.as_view()),
]
