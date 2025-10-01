from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ViolationClassifierViewSet, WorkSpecificationViewSet

app_name = 'dataset'

router = DefaultRouter()
router.register(r'violations', ViolationClassifierViewSet)
router.register(r'specifications', WorkSpecificationViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]