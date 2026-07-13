from django.urls import path
from .views import LegalGuidanceAskView

urlpatterns = [
    path("ask/", LegalGuidanceAskView.as_view(), name="legal-guidance-ask"),
]