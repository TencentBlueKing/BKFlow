from django.conf.urls import url
from django.urls import include
from rest_framework.routers import DefaultRouter

from bkflow.statistics.views import SpaceStatisticsViewSet, SystemStatisticsViewSet

router = DefaultRouter()
router.register(r"system", SystemStatisticsViewSet, basename="system_statistics")
router.register(r"spaces/(?P<space_id>\d+)", SpaceStatisticsViewSet, basename="space_statistics")

urlpatterns = [
    url(r"^", include(router.urls)),
]
