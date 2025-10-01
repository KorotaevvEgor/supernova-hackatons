from django.urls import path
from . import views

app_name = 'demo'

urlpatterns = [
    path('ocr-api/demo/', views.ocr_demo, name='ocr_demo'),
    path('api/ocr/process/', views.process_ocr, name='process_ocr'),
]
