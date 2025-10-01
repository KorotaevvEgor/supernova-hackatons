from django.contrib import admin
from .models import (
    MaterialType, MaterialDelivery, TransportDocument, 
    DocumentPhoto, OCRResult
)
from projects.models import Project

# Настройка админки для типов материалов
@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'unit']
    list_filter = ['unit']
    search_fields = ['name', 'code', 'description']
    ordering = ['name']

# Настройка админки для поставок материалов
@admin.register(MaterialDelivery)
class MaterialDeliveryAdmin(admin.ModelAdmin):
    list_display = ['project', 'material_type', 'supplier', 'quantity', 'delivery_date', 'status']
    list_filter = ['status', 'delivery_date', 'material_type']
    search_fields = ['project__name', 'supplier', 'ttn_number']
    date_hierarchy = 'delivery_date'
    ordering = ['-delivery_date']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('project', 'material_type', 'quantity', 'supplier')
        }),
        ('Поставка', {
            'fields': ('delivery_date', 'status', 'ttn_number')
        }),
        ('Дополнительно', {
            'fields': ('received_by', 'spec_row', 'notes', 'manual_entry'),
            'classes': ('collapse',)
        })
    )

# Настройка админки для транспортных документов
@admin.register(TransportDocument)
class TransportDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_number', 'delivery', 'project_display', 'document_date', 'processing_status']
    list_filter = ['processing_status', 'document_date', 'project']
    search_fields = ['document_number', 'sender_name', 'receiver_name', 'delivery__project__name']
    date_hierarchy = 'document_date'
    ordering = ['-created_at']
    
    def project_display(self, obj):
        return obj.project.name if obj.project else obj.delivery.project.name
    project_display.short_description = 'Проект'
    
    fieldsets = (
        ('Документ', {
            'fields': ('document_number', 'document_date', 'delivery')
        }),
        ('Адрес доставки (Проект)', {
            'fields': ('project',),
            'description': 'Выберите проект - адрес будет заполнен автоматически'
        }),
        ('Отправитель', {
            'fields': ('sender_name', 'sender_address', 'sender_inn')
        }),
        ('Получатель', {
            'fields': ('receiver_name', 'receiver_address', 'receiver_inn'),
            'description': 'Поля заполняются автоматически при выборе проекта, но можно изменить вручную'
        }),
        ('Транспорт и водитель', {
            'fields': ('vehicle_number', 'driver_name', 'driver_license_number'),
            'classes': ('collapse',)
        }),
        ('Груз', {
            'fields': ('cargo_description', 'cargo_weight', 'cargo_volume', 'packages_count'),
            'classes': ('collapse',)
        }),
        ('Обработка', {
            'fields': ('processing_status', 'manual_verification_required', 'processed_by'),
            'classes': ('collapse',)
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Редактирование существующего объекта
            return ['processed_by', 'created_at']
        return ['processed_by']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Создание нового объекта
            obj.processed_by = request.user
        super().save_model(request, obj, form, change)
    
    class Media:
        js = ('materials/admin/transport_document_admin.js',)

# Настройка админки для фотографий документов
@admin.register(DocumentPhoto)
class DocumentPhotoAdmin(admin.ModelAdmin):
    list_display = ['transport_document', 'photo_type', 'processing_status', 'uploaded_at', 'uploaded_by']
    list_filter = ['photo_type', 'processing_status', 'uploaded_at']
    search_fields = ['transport_document__document_number']
    date_hierarchy = 'uploaded_at'
    ordering = ['-uploaded_at']
    
    readonly_fields = ['uploaded_at', 'ocr_confidence']

# Настройка админки для OCR результатов
@admin.register(OCRResult)
class OCRResultAdmin(admin.ModelAdmin):
    list_display = ['document_photo', 'validation_status', 'overall_confidence', 'created_at']
    list_filter = ['validation_status', 'created_at']
    search_fields = ['document_photo__transport_document__document_number']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    readonly_fields = ['created_at', 'overall_confidence']
