from django.urls import path

from ecommerce.api import views

urlpatterns = [
    path("products/", views.ProductListView.as_view()),
]
