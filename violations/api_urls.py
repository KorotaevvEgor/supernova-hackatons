from django.urls import path
from . import views

app_name = 'violations_api'

urlpatterns = [
    path('', views.violation_list_api, name='list'),
    path('items/', views.ViolationListCreateAPI.as_view(), name='items'),
    path('items/<int:pk>/resolve/', views.ViolationResolveAPI.as_view(), name='resolve'),
    path('items/<int:pk>/verify/', views.ViolationVerifyAPI.as_view(), name='verify'),
    # API для классификатора нарушений
    path('classifier/', views.ViolationClassifierListAPI.as_view(), name='classifier-list'),
    path('classifier/categories/', views.ViolationClassifierCategoriesAPI.as_view(), name='classifier-categories'),
]
