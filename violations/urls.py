from django.urls import path
from . import views

app_name = 'violations'

# API URLs
api_urlpatterns = [
    path('', views.violation_list_api, name='api_list'),
]

# Frontend URLs
urlpatterns = [
    path('', views.violation_list, name='list'),
    path('classifier/', views.classifier_view, name='classifier'),
]
