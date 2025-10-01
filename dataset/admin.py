from django.contrib import admin
from .models import (
    ViolationClassifier, ProjectCoordinates, WorkSpecification,
    NetworkSchedule, TransportDocument, CheckListTemplate,
    CheckListItem, ViolationPrescription
)


@admin.register(ViolationClassifier)
class ViolationClassifierAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'violation_type', 'severity', 'fix_period']
    list_filter = ['category', 'violation_type', 'severity']
    search_fields = ['name']
    ordering = ['category', 'name']


@admin.register(ProjectCoordinates)
class ProjectCoordinatesAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'created_at']
    search_fields = ['name', 'address']
    ordering = ['name']


@admin.register(WorkSpecification)
class WorkSpecificationAdmin(admin.ModelAdmin):
    list_display = ['object_name', 'work_name', 'quantity', 'unit', 'start_date', 'end_date']
    list_filter = ['object_name', 'unit']
    search_fields = ['work_name', 'object_name']
    ordering = ['object_name', 'start_date']


@admin.register(NetworkSchedule)
class NetworkScheduleAdmin(admin.ModelAdmin):
    list_display = ['object_name', 'work_name', 'kpgz_code', 'start_date', 'end_date']
    list_filter = ['object_name', 'kpgz_code']
    search_fields = ['work_name', 'object_name']
    ordering = ['object_name', 'start_date']


@admin.register(TransportDocument)
class TransportDocumentAdmin(admin.ModelAdmin):
    list_display = ['document_number', 'date', 'material_name', 'quantity_net', 'sender']
    list_filter = ['date', 'material_name', 'sender']
    search_fields = ['document_number', 'material_name']
    ordering = ['-date', 'document_number']


class CheckListItemInline(admin.TabularInline):
    model = CheckListItem
    extra = 0
    ordering = ['order', 'item_number']


@admin.register(CheckListTemplate)
class CheckListTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'form_type', 'created_at']
    list_filter = ['form_type']
    search_fields = ['name', 'description']
    inlines = [CheckListItemInline]


@admin.register(ViolationPrescription)
class ViolationPrescriptionAdmin(admin.ModelAdmin):
    list_display = ['number', 'date_issued', 'violation', 'status', 'work_stopped', 'inspector']
    list_filter = ['status', 'work_stopped', 'date_issued', 'violation__category']
    search_fields = ['number', 'description']
    ordering = ['-date_issued', 'number']
    raw_id_fields = ['violation', 'inspector']
