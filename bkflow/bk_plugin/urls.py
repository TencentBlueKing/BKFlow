from rest_framework.routers import DefaultRouter

from bkflow.bk_plugin import views

router = DefaultRouter()
router.register(r"manager", views.BKPluginManagerViewSet)
router.register(r"", views.BKPluginViewSet)

urlpatterns = router.urls
