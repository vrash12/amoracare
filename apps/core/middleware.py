#apps/core/middleware.py
from django.conf import settings
from django.http import JsonResponse


class LaravelApiKeyMiddleware:
    """
    Protects Django AI endpoints so random users cannot call them directly.

    Laravel must send:
    X-AmoraCare-API-Key: amoracare-local-dev-key
    """

    EXEMPT_PATHS = [
        "/admin/",
        "/api/health/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
            return self.get_response(request)

        if path.startswith("/api/"):
            api_key = request.headers.get("X-AmoraCare-API-Key")

            if api_key != settings.LARAVEL_API_KEY:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Unauthorized Django AI service request.",
                    },
                    status=401,
                )

        return self.get_response(request)