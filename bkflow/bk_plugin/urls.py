from rest_framework.routers import DefaultRouter

from bkflow.bk_plugin import views

router = DefaultRouter()
router.register(r"auth", views.BKPluginAdminViewSet)
router.register(r"query", views.BKPluginViewSet)

urlpatterns = router.urls
