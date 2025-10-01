from django.urls import path
from . import views

app_name = 'materials'

# API URLs
api_urlpatterns = [
    path('', views.material_list_api, name='api_list'),
    
    # API для работы с поставками материалов
    path('deliveries/', views.MaterialDeliveryListCreateAPI.as_view(), name='delivery_list_create'),
    path('deliveries/<int:pk>/link-spec/', views.MaterialLinkSpecAPI.as_view(), name='delivery_link_spec'),
    
    # OCR API (старый)
    path('ocr/', views.MaterialOCRAPIView.as_view(), name='ocr'),
    
    # Новые API для работы с ТТН
    path('ttn/upload/', views.TTNUploadAPI.as_view(), name='ttn_upload'),
    path('ttn/<int:transport_document_id>/status/', views.TTNProcessingStatusAPI.as_view(), name='ttn_status'),
    path('ttn/', views.TTNDataAPI.as_view(), name='ttn_list'),
    path('ttn/<int:transport_document_id>/update/', views.TTNDataAPI.as_view(), name='ttn_update'),
    
    # API для создания поставки с OCR
    path('delivery/create-with-ocr/', views.CreateDeliveryWithOCRAPI.as_view(), name='create_delivery_ocr'),
]

# Frontend URLs
urlpatterns = [
    path('', views.material_list, name='list'),
    path('delivery/<int:delivery_id>/', views.delivery_detail, name='delivery_detail'),
    
    # ========== СИСТЕМА ВХОДНОГО КОНТРОЛЯ С OCR ==========
    path('incoming-control/', views.incoming_control_page, name='incoming_control'),
    
    # Тестовая страница OCR автозаполнения (без аутентификации)
    path('ocr-test/', views.ocr_test_page, name='ocr_test'),
]
