from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(request):
    return JsonResponse({
        "success": True,
        "service": "AmoraCare Django AI Service",
        "message": "Django AI backend is running.",
        "available_endpoints": [
            "/api/health/",
            "/api/legal-guidance/ask/",
        ],
    })


urlpatterns = [
    path("", home, name="home"),

    path("admin/", admin.site.urls),

    path("api/", include("apps.core.urls")),

    path(
        "api/legal-guidance/",
        include("apps.legal_guidance.urls"),
    ),
]