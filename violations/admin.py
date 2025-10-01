from django.contrib import admin
from .models import (
    ViolationClassifier,
    ViolationCategory,
    ViolationType,
    Violation,
    ViolationResolution
)


@admin.register(ViolationClassifier)
class ViolationClassifierAdmin(admin.ModelAdmin):
    list_display = [
        'category', 
        'kind', 
        'type_name', 
        'name_short', 
        'regulatory_deadline_days', 
        'is_active'
    ]
    list_filter = ['category', 'kind', 'type_name', 'is_active']
    search_fields = ['category', 'name', 'kind', 'type_name']
    list_editable = ['is_active']
    ordering = ['category', 'kind', 'type_name']
    
    def name_short(self, obj):
        return obj.name[:50] + "..." if len(obj.name) > 50 else obj.name
    name_short.short_description = 'Наименование'


@admin.register(ViolationCategory)
class ViolationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(ViolationType)
class ViolationTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'source', 'regulatory_deadline_days']
    list_filter = ['category', 'source']
    search_fields = ['code', 'name']


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    list_display = [
        'title', 
        'project', 
        'status', 
        'priority', 
        'detected_at', 
        'deadline', 
        'created_by'
    ]
    list_filter = ['status', 'priority', 'detected_at']
    search_fields = ['title', 'description', 'project__name']
    raw_id_fields = ['project', 'violation_type', 'violation_classifier']
    date_hierarchy = 'detected_at'


@admin.register(ViolationResolution)
class ViolationResolutionAdmin(admin.ModelAdmin):
    list_display = ['violation', 'resolved_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['violation__title', 'description']
    raw_id_fields = ['violation']
