from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            "success": True,
            "service": "AmoraCare Django AI Service",
            "status": "running",
        })