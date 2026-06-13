from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health),
    path("api/", include("ecommerce.api.urls")),
]

if getattr(settings, "SILK_ENABLED", False):
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]
