from django.urls import path
from . import views
from .ocr_api_views import (
    DocumentUploadAPIView,
    ProcessDocumentAPIView, 
    ValidateExtractedDataAPIView,
    UpdateExtractedDataAPIView,
    DocumentStatusAPIView,
    DeliveryDocumentsAPIView,
    ExportTTNDataAPIView,
    BulkProcessDocumentsAPIView,
    project_deliveries_for_ocr,
    upload_document_legacy
)

app_name = 'materials_api'

urlpatterns = [
    # Существующие API
    path('', views.material_list_api, name='list'),
    path('deliveries/', views.MaterialDeliveryListCreateAPI.as_view(), name='deliveries'),
    path('deliveries/<int:pk>/link-spec/', views.MaterialLinkSpecAPI.as_view(), name='delivery-link-spec'),
    path('ocr/', views.MaterialOCRAPIView.as_view(), name='ocr'),
    
    # ========== API ДЛЯ СИСТЕМЫ ВХОДНОГО КОНТРОЛЯ С OCR ==========
    
    # API для создания поставки с OCR
    path('delivery/create-with-ocr/', views.CreateDeliveryWithOCRAPI.as_view(), name='create_delivery_ocr'),
    
    # Новое API для реального OCR распознавания
    path('ocr/process-document/', views.ProcessDocumentOCRAPI.as_view(), name='process_document_ocr'),
    
    # Новый API для загрузки ТТН (c project_id)
    path('ttn/upload/', views.TTNUploadAPI.as_view(), name='ttn_upload_new'),
    
    # Старый API для загрузки ТТН (с delivery_id) - для обратной совместимости
    path('ttn/upload-old/', DocumentUploadAPIView.as_view(), name='upload_ttn_document'),
    path('ttn/photos/<int:photo_id>/process/', ProcessDocumentAPIView.as_view(), name='process_ttn_document'),
    path('ttn/photos/<int:photo_id>/status/', DocumentStatusAPIView.as_view(), name='ttn_document_status'),
    
    # Новые API для статуса и обновления ТТН
    path('ttn/<int:transport_document_id>/status/', views.TTNProcessingStatusAPI.as_view(), name='ttn_status_new'),
    path('ttn/<int:transport_document_id>/update/', views.TTNDataAPI.as_view(), name='ttn_update_new'),
    path('ttn/', views.TTNDataAPI.as_view(), name='ttn_list_new'),
    
    # Работа с OCR результатами (старые)
    path('ttn/ocr-results/<int:ocr_result_id>/validate/', ValidateExtractedDataAPIView.as_view(), name='validate_ttn_ocr'),
    path('ttn/ocr-results/<int:ocr_result_id>/update/', UpdateExtractedDataAPIView.as_view(), name='update_ttn_ocr'),
    
    # Документы поставок
    path('deliveries/<int:delivery_id>/ttn-documents/', DeliveryDocumentsAPIView.as_view(), name='delivery_ttn_documents'),
    path('projects/<int:project_id>/deliveries-ocr/', project_deliveries_for_ocr, name='project_deliveries_ocr'),
    
    # Экспорт данных ТТН
    path('ttn/export/<str:format_type>/', ExportTTNDataAPIView.as_view(), name='export_ttn_data'),
    path('ttn/export/', ExportTTNDataAPIView.as_view(), {'format_type': 'csv'}, name='export_ttn_csv'),
    
    # Массовая обработка документов
    path('ttn/bulk-process/', BulkProcessDocumentsAPIView.as_view(), name='bulk_process_ttn'),
    
    # Legacy поддержка для совместимости
    path('ttn/upload-legacy/', upload_document_legacy, name='upload_ttn_legacy'),
]
