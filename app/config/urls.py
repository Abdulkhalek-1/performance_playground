from django.db import connection
from django.http import JsonResponse
from django.urls import path


def health(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
]
