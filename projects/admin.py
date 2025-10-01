from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import (
    Project, WorkType, Work, ScheduleChange, WorkSpecRow,
    ElectronicSpecification, SpecificationItem, 
    NetworkSchedule, ScheduleTask
)
from .activation_models import ProjectActivation, ActivationChecklist, ActivationEvent

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'status', 'control_service', 'foreman', 'planned_start_date')
    list_filter = ('status', 'planned_start_date')
    search_fields = ('name', 'address', 'contract_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'address', 'coordinates', 'description')
        }),
        ('Статус и ответственные', {
            'fields': ('status', 'control_service', 'foreman')
        }),
        ('Даты и документы', {
            'fields': ('contract_number', 'planned_start_date', 'planned_end_date', 
                      'actual_start_date', 'actual_end_date', 'opening_act', 'opening_checklist_completed')
        })
    )

@admin.register(WorkType)
class WorkTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')

@admin.register(Work) 
class WorkAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'work_type', 'status', 'planned_start_date', 'planned_end_date')
    list_filter = ('status', 'work_type', 'planned_start_date')
    search_fields = ('name', 'project__name')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ScheduleChange)
class ScheduleChangeAdmin(admin.ModelAdmin):
    list_display = ('work', 'status', 'requested_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('work__name', 'requested_by__username')
    readonly_fields = ('created_at', 'updated_at')


class SpecificationItemInline(admin.TabularInline):
    model = SpecificationItem
    extra = 0
    fields = ('code', 'name', 'unit', 'quantity', 'unit_price', 'total_price', 'category')
    readonly_fields = ()


@admin.register(ElectronicSpecification)
class ElectronicSpecificationAdmin(admin.ModelAdmin):
    list_display = ('project', 'source_file', 'imported_at')
    list_filter = ('imported_at',)
    search_fields = ('project__name', 'source_file')
    readonly_fields = ('imported_at',)
    inlines = [SpecificationItemInline]


@admin.register(SpecificationItem)
class SpecificationItemAdmin(admin.ModelAdmin):
    list_display = ('specification', 'code', 'name', 'unit', 'quantity', 'category')
    list_filter = ('specification__project', 'category', 'unit')
    search_fields = ('name', 'code', 'specification__project__name')
    list_select_related = ('specification', 'specification__project')


class ScheduleTaskInline(admin.TabularInline):
    model = ScheduleTask
    extra = 0
    fields = ('task_id', 'name', 'duration_days', 'early_start', 'early_finish', 'is_critical')
    readonly_fields = ()


@admin.register(NetworkSchedule)
class NetworkScheduleAdmin(admin.ModelAdmin):
    list_display = ('project', 'source_file', 'project_duration_days', 'imported_at')
    list_filter = ('imported_at',)
    search_fields = ('project__name', 'source_file')
    readonly_fields = ('imported_at',)
    inlines = [ScheduleTaskInline]


@admin.register(ScheduleTask)
class ScheduleTaskAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'task_id', 'name', 'duration_days', 'early_start', 'is_critical')
    list_filter = ('schedule__project', 'is_critical', 'work_type')
    search_fields = ('name', 'task_id', 'schedule__project__name')
    list_select_related = ('schedule', 'schedule__project', 'work_type')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('schedule', 'task_id', 'name', 'work_type')
        }),
        ('Временные параметры', {
            'fields': ('duration_days', 'early_start', 'early_finish', 'late_start', 'late_finish', 'is_critical')
        }),
        ('Зависимости и ресурсы', {
            'fields': ('predecessors', 'successors', 'resource_names')
        }),
    )


@admin.register(WorkSpecRow)
class WorkSpecRowAdmin(admin.ModelAdmin):
    list_display = ('project', 'code', 'name', 'unit', 'planned_volume')
    list_filter = ('project', 'unit')
    search_fields = ('name', 'code', 'project__name')
    list_select_related = ('project',)


# ========== АДМИНКА ДЛЯ АКТИВАЦИИ ПРОЕКТОВ ==========

class ActivationEventInline(admin.TabularInline):
    model = ActivationEvent
    extra = 0
    fields = ('event_type', 'user', 'description', 'created_at')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    def has_add_permission(self, request, obj=None):
        return False  # Только просмотр


@admin.register(ProjectActivation)
class ProjectActivationAdmin(admin.ModelAdmin):
    list_display = ('project', 'status_badge', 'initiated_by', 'assigned_foreman', 'reviewing_inspector', 'created_at')
    list_filter = ('status', 'created_at', 'foreman_assigned_at', 'checklist_completed_at', 'inspector_reviewed_at')
    search_fields = ('project__name', 'initiated_by__username', 'assigned_foreman__username')
    readonly_fields = ('created_at', 'foreman_assigned_at', 'checklist_completed_at', 'inspector_reviewed_at', 'activated_at')
    list_select_related = ('project', 'initiated_by', 'assigned_foreman', 'reviewing_inspector')
    inlines = [ActivationEventInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('project', 'status')
        }),
        ('Участники процесса', {
            'fields': ('initiated_by', 'assigned_foreman', 'reviewing_inspector')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'foreman_assigned_at', 'checklist_completed_at', 
                      'inspector_reviewed_at', 'activated_at'),
            'classes': ('collapse',)
        }),
        ('Решение инспектора', {
            'fields': ('rejection_reason', 'inspector_notes', 'activation_document'),
            'classes': ('collapse',)
        })
    )
    
    def status_badge(self, obj):
        """Отображает статус с цветовой индикацией"""
        colors = {
            'pending': 'gray',
            'foreman_assigned': 'blue',
            'checklist_filling': 'orange',
            'inspector_review': 'yellow',
            'approved': 'green',
            'activated': 'darkgreen',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'project', 'initiated_by', 'assigned_foreman', 'reviewing_inspector'
        )
    
    actions = ['approve_activations', 'reject_activations', 'assign_foreman_bulk']
    
    def approve_activations(self, request, queryset):
        """Массовое одобрение активаций"""
        count = 0
        for activation in queryset.filter(status='inspector_review'):
            activation.approve_activation(request.user)
            count += 1
        self.message_user(request, f'Одобрено {count} активаций.')
    approve_activations.short_description = 'Одобрить выбранные активации'
    
    def reject_activations(self, request, queryset):
        """Массовое отклонение активаций"""
        count = 0
        for activation in queryset.filter(status='inspector_review'):
            activation.status = 'rejected'
            activation.rejection_reason = 'Отклонено через админку'
            activation.reviewing_inspector = request.user
            activation.inspector_reviewed_at = timezone.now()
            activation.save()
            count += 1
        self.message_user(request, f'Отклонено {count} активаций.')
    reject_activations.short_description = 'Отклонить выбранные активации'


@admin.register(ActivationChecklist)
class ActivationChecklistAdmin(admin.ModelAdmin):
    list_display = ('activation_project', 'filled_by', 'completion_percentage', 'is_complete', 'filled_at')
    list_filter = ('filled_at', 'overall_readiness')
    search_fields = ('activation__project__name', 'filled_by__username')
    readonly_fields = ('filled_at', 'completion_percentage', 'is_complete')
    list_select_related = ('activation__project', 'filled_by')
    
    def activation_project(self, obj):
        return obj.activation.project.name
    activation_project.short_description = 'Проект'
    
    def completion_percentage(self, obj):
        percentage = obj.completion_percentage
        color = 'green' if percentage == 100 else 'orange' if percentage > 50 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} %</span>',
            color, percentage
        )
    completion_percentage.short_description = 'Заполнено'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('activation', 'filled_by', 'filled_at', 'overall_readiness')
        }),
        ('1. Документация', {
            'fields': ('regulatory_documentation', 'regulatory_documentation_notes')
        }),
        ('2. Приказы на ответственных лиц', {
            'fields': ('construction_manager_order', 'construction_manager_order_notes',
                      'construction_control_order', 'construction_control_order_notes',
                      'project_supervision_order', 'project_supervision_order_notes')
        }),
        ('3. Проектная документация и производство работ', {
            'fields': ('project_documentation_stamp', 'project_documentation_stamp_notes',
                      'work_production_project', 'work_production_project_notes')
        }),
        ('4. Подготовка площадки', {
            'fields': ('engineering_site_preparation', 'engineering_site_preparation_notes',
                      'geodetic_breakdown_act', 'geodetic_breakdown_act_notes',
                      'general_plan', 'general_plan_notes')
        }),
        ('5. Инфраструктура и безопасность', {
            'fields': ('temporary_infrastructure', 'temporary_infrastructure_notes',
                      'vehicle_cleaning_points', 'vehicle_cleaning_points_notes',
                      'waste_containers', 'waste_containers_notes',
                      'information_boards', 'information_boards_notes',
                      'fire_safety_stands', 'fire_safety_stands_notes')
        }),
        ('Заключение', {
            'fields': ('additional_notes',)
        })
    )


@admin.register(ActivationEvent)
class ActivationEventAdmin(admin.ModelAdmin):
    list_display = ('activation_project', 'event_type', 'user', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('activation__project__name', 'user__username', 'description')
    readonly_fields = ('created_at',)
    list_select_related = ('activation__project', 'user')
    ordering = ('-created_at',)
    
    def activation_project(self, obj):
        return obj.activation.project.name
    activation_project.short_description = 'Проект'
    
    def has_add_permission(self, request):
        return False  # События создаются автоматически
    
    def has_change_permission(self, request, obj=None):
        return False  # Только просмотр
    
    def has_delete_permission(self, request, obj=None):
        return False  # Нельзя удалять события
