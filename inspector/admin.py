from django.contrib import admin
from .models import (
    ViolationType, InspectorViolation, ViolationPhoto, ViolationComment,
    LabSampleRequest, ProjectActivationApproval
)


@admin.register(ViolationType)
class ViolationTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'severity', 'default_deadline_days', 'is_active']
    list_filter = ['severity', 'is_active', 'mandatory_photo', 'mandatory_location']
    search_fields = ['code', 'name']
    list_editable = ['is_active']
    ordering = ['code']


@admin.register(InspectorViolation)
class InspectorViolationAdmin(admin.ModelAdmin):
    list_display = [
        'project', 
        'violation_type', 
        'violation_classifier',
        'title', 
        'status', 
        'priority', 
        'inspector',
        'deadline',
        'detected_at'
    ]
    list_filter = ['status', 'priority', 'detected_at', 'deadline']
    search_fields = ['title', 'description', 'project__name']
    raw_id_fields = ['project', 'violation_type', 'violation_classifier', 'inspector', 'assigned_to']
    date_hierarchy = 'detected_at'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('project', 'violation_type', 'violation_classifier', 'inspector', 'title', 'description')
        }),
        ('Параметры', {
            'fields': ('status', 'priority', 'deadline', 'assigned_to')
        }),
        ('Местоположение', {
            'fields': ('location_lat', 'location_lng', 'location_description')
        }),
        ('Временные метки', {
            'fields': ('detected_at', 'corrected_at', 'verified_at', 'created_at', 'updated_at')
        }),
        ('Комментарии', {
            'fields': ('correction_comment', 'inspector_comment')
        }),
    )


@admin.register(ViolationPhoto)
class ViolationPhotoAdmin(admin.ModelAdmin):
    list_display = ['violation', 'photo_type', 'taken_by', 'taken_at']
    list_filter = ['photo_type', 'taken_at']
    search_fields = ['violation__title', 'description']
    raw_id_fields = ['violation', 'taken_by']


@admin.register(LabSampleRequest)
class LabSampleRequestAdmin(admin.ModelAdmin):
    list_display = [
        'project', 
        'material_type', 
        'status', 
        'urgency', 
        'requested_by',
        'requested_at'
    ]
    list_filter = ['status', 'urgency', 'requested_at']
    search_fields = ['project__name', 'reason', 'material_type__name']
    raw_id_fields = ['project', 'material_type', 'requested_by']
    date_hierarchy = 'requested_at'


@admin.register(ProjectActivationApproval)
class ProjectActivationApprovalAdmin(admin.ModelAdmin):
    list_display = [
        'project', 
        'inspector', 
        'status', 
        'inspection_date',
        'decision_date'
    ]
    list_filter = ['status', 'inspection_date', 'decision_date']
    search_fields = ['project__name', 'inspector__username']
    raw_id_fields = ['project', 'inspector']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('project', 'inspector', 'status', 'inspection_date', 'decision_date')
        }),
        ('Проверка', {
            'fields': (
                'site_preparation_checked',
                'safety_measures_checked',
                'documentation_checked',
                'environmental_compliance_checked'
            )
        }),
        ('Заключения', {
            'fields': ('inspector_conclusion', 'conditions', 'rejection_reason')
        }),
        ('Временные метки', {
            'fields': ('valid_until', 'created_at', 'updated_at')
        }),
    )


@admin.register(ViolationComment)
class ViolationCommentAdmin(admin.ModelAdmin):
    list_display = ['violation', 'author', 'created_at', 'comment_preview']
    list_filter = ['created_at', 'violation__status']
    search_fields = ['comment', 'violation__title', 'author__username']
    raw_id_fields = ['violation', 'author']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    
    def comment_preview(self, obj):
        return obj.comment[:100] + '...' if len(obj.comment) > 100 else obj.comment
    comment_preview.short_description = 'Комментарий'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('violation', 'author', 'comment')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )
