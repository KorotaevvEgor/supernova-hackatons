from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
import json

from .models import Project
from .activation_models import (
    ProjectActivation, 
    ActivationChecklist, 
    Notification,
    ActivationEvent
)

User = get_user_model()


# @login_required
# def projects_list_with_activation(request):
#     """Список проектов с индикацией готовых к активации - УДАЛЕНО ПО ЗАПРОСУ"""
#     pass


@login_required 
def initiate_project_activation(request, project_id):
    """Начать процесс активации проекта"""
    
    project = get_object_or_404(Project, id=project_id)
    
    # Проверяем права
    if (request.user.user_type != 'construction_control' or 
        project.control_service != request.user):
        messages.error(request, 'У вас нет прав на активацию этого проекта')
        return redirect('projects:construction_control_dashboard')
    
    # Проверяем статус проекта
    if project.status != 'planned':
        messages.error(request, 'Проект уже активирован или завершен')
        return redirect('projects:construction_control_dashboard')
    
    # Проверяем, не создана ли уже активация
    if hasattr(project, 'activation'):
        messages.warning(request, 'Процесс активации уже запущен')
        return redirect('projects:activation_detail', activation_id=project.activation.id)
    
    # Создаем процесс активации
    with transaction.atomic():
        activation = ProjectActivation.objects.create(
            project=project,
            initiated_by=request.user,
            status='pending'
        )
        
        # Создаем событие
        ActivationEvent.objects.create(
            activation=activation,
            event_type='created',
            user=request.user,
            description=f'Создан процесс активации проекта {project.name}'
        )
    
    messages.success(request, f'Процесс активации проекта "{project.name}" создан')
    return redirect('projects:assign_foreman', activation_id=activation.id)


@login_required
def assign_foreman(request, activation_id):
    """Назначить прораба для активации проекта"""
    
    activation = get_object_or_404(ProjectActivation, id=activation_id)
    
    if not activation.can_assign_foreman(request.user):
        messages.error(request, 'У вас нет прав назначать прораба для этого проекта')
        return redirect('projects:construction_control_dashboard')
    
    if request.method == 'POST':
        foreman_id = request.POST.get('foreman_id')
        if foreman_id:
            foreman = get_object_or_404(User, id=foreman_id, user_type='foreman')
            
            with transaction.atomic():
                activation.assign_foreman(foreman, request.user)
                
                # Создаем событие
                ActivationEvent.objects.create(
                    activation=activation,
                    event_type='foreman_assigned',
                    user=request.user,
                    description=f'Назначен прораб: {foreman.get_full_name()}'
                )
            
            messages.success(request, f'Прораб {foreman.get_full_name()} назначен')
            return redirect('projects:checklist_form', activation_id=activation.id)
        else:
            messages.error(request, 'Выберите прораба')
    
    # Получаем доступных прорабов
    available_foremen = User.objects.filter(
        user_type='foreman',
        is_active=True
    )
    
    context = {
        'activation': activation,
        'available_foremen': available_foremen,
    }
    
    return render(request, 'projects/assign_foreman.html', context)


@login_required
def checklist_form(request, activation_id):
    """Форма заполнения чек-листа активации"""
    
    activation = get_object_or_404(ProjectActivation, id=activation_id)
    
    if not activation.can_fill_checklist(request.user):
        messages.error(request, 'У вас нет прав заполнять чек-лист для этого проекта')
        return redirect('projects:construction_control_dashboard')
    
    # Проверяем, является ли это повторным заполнением после отклонения
    is_refill_after_rejection = activation.status == 'rejected'
    
    # Получаем или создаем чек-лист
    checklist, created = ActivationChecklist.objects.get_or_create(
        activation=activation,
        defaults={'filled_by': request.user}
    )
    
    if request.method == 'POST':
        # Обновляем поля чек-листа (новые поля)
        checklist.regulatory_documentation = request.POST.get('regulatory_documentation', '')
        checklist.construction_manager_order = request.POST.get('construction_manager_order', '')
        checklist.construction_control_order = request.POST.get('construction_control_order', '')
        checklist.project_supervision_order = request.POST.get('project_supervision_order', '')
        checklist.project_documentation_stamp = request.POST.get('project_documentation_stamp', '')
        checklist.work_production_project = request.POST.get('work_production_project', '')
        checklist.engineering_site_preparation = request.POST.get('engineering_site_preparation', '')
        checklist.geodetic_breakdown_act = request.POST.get('geodetic_breakdown_act', '')
        checklist.general_plan = request.POST.get('general_plan', '')
        checklist.temporary_infrastructure = request.POST.get('temporary_infrastructure', '')
        checklist.vehicle_cleaning_points = request.POST.get('vehicle_cleaning_points', '')
        checklist.waste_containers = request.POST.get('waste_containers', '')
        checklist.information_boards = request.POST.get('information_boards', '')
        checklist.fire_safety_stands = request.POST.get('fire_safety_stands', '')
        checklist.overall_readiness = request.POST.get('overall_readiness') == 'on'
        
        # Примечания (новые поля)
        checklist.regulatory_documentation_notes = request.POST.get('regulatory_documentation_notes', '')
        checklist.construction_manager_order_notes = request.POST.get('construction_manager_order_notes', '')
        checklist.construction_control_order_notes = request.POST.get('construction_control_order_notes', '')
        checklist.project_supervision_order_notes = request.POST.get('project_supervision_order_notes', '')
        checklist.project_documentation_stamp_notes = request.POST.get('project_documentation_stamp_notes', '')
        checklist.work_production_project_notes = request.POST.get('work_production_project_notes', '')
        checklist.engineering_site_preparation_notes = request.POST.get('engineering_site_preparation_notes', '')
        checklist.geodetic_breakdown_act_notes = request.POST.get('geodetic_breakdown_act_notes', '')
        checklist.general_plan_notes = request.POST.get('general_plan_notes', '')
        checklist.temporary_infrastructure_notes = request.POST.get('temporary_infrastructure_notes', '')
        checklist.vehicle_cleaning_points_notes = request.POST.get('vehicle_cleaning_points_notes', '')
        checklist.waste_containers_notes = request.POST.get('waste_containers_notes', '')
        checklist.information_boards_notes = request.POST.get('information_boards_notes', '')
        checklist.fire_safety_stands_notes = request.POST.get('fire_safety_stands_notes', '')
        checklist.additional_notes = request.POST.get('additional_notes', '')
        
        # Обновляем время заполнения при повторном заполнении
        if is_refill_after_rejection:
            checklist.filled_at = timezone.now()
        
        checklist.save()
        
        # Если чек-лист полностью заполнен, отправляем на проверку
        if 'submit_for_review' in request.POST and checklist.is_complete:
            with transaction.atomic():
                activation.complete_checklist(request.user)
                
                # Создаем событие
                event_description = 'Чек-лист повторно заполнен и отправлен на проверку' if is_refill_after_rejection else 'Чек-лист заполнен и отправлен на проверку'
                ActivationEvent.objects.create(
                    activation=activation,
                    event_type='checklist_completed',
                    user=request.user,
                    description=event_description
                )
            
            success_message = 'Исправленный чек-лист отправлен на повторную проверку' if is_refill_after_rejection else 'Чек-лист отправлен на проверку инспектору'
            messages.success(request, success_message)
            return redirect('projects:activation_detail', activation_id=activation.id)
        
        messages.success(request, 'Чек-лист сохранен')
    
    context = {
        'activation': activation,
        'checklist': checklist,
        'is_refill_after_rejection': is_refill_after_rejection,
    }
    
    return render(request, 'projects/checklist_form.html', context)


@login_required
def inspector_review(request, activation_id):
    """Страница проверки активации инспектором"""
    
    activation = get_object_or_404(ProjectActivation, id=activation_id)
    
    if not activation.can_inspect(request.user):
        messages.error(request, 'У вас нет прав проверять этот проект')
        return redirect('projects:inspector_activations')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Загрузка документа
            document = request.FILES.get('activation_document')
            notes = request.POST.get('inspector_notes', '')
            
            with transaction.atomic():
                activation.inspector_notes = notes
                activation.approve_activation(request.user, document)
                
                # Создаем событие
                ActivationEvent.objects.create(
                    activation=activation,
                    event_type='approved',
                    user=request.user,
                    description=f'Активация одобрена инспектором'
                )
            
            messages.success(request, f'Проект "{activation.project.name}" активирован!')
            return redirect('projects:activation_detail', activation_id=activation.id)
        
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            
            with transaction.atomic():
                activation.status = 'rejected'
                activation.rejection_reason = reason
                activation.reviewing_inspector = request.user
                activation.inspector_reviewed_at = timezone.now()
                activation.save()
                
                # Создаем событие
                ActivationEvent.objects.create(
                    activation=activation,
                    event_type='rejected',
                    user=request.user,
                    description=f'Активация отклонена: {reason}'
                )
                
                # Уведомляем инициатора
                Notification.objects.create_notification(
                    recipient=activation.initiated_by,
                    title='Активация проекта отклонена',
                    message=f'Проект {activation.project.name} отклонен. Причина: {reason}',
                    notification_type='warning',
                    related_object=activation
                )
            
            messages.success(request, 'Активация отклонена')
            return redirect('projects:activation_detail', activation_id=activation.id)
    
    context = {
        'activation': activation,
        'checklist': activation.checklist,
    }
    
    return render(request, 'projects/inspector_review.html', context)


@login_required
def activation_detail(request, activation_id):
    """Детальная информация о процессе активации"""
    
    activation = get_object_or_404(ProjectActivation, id=activation_id)
    
    # Проверяем права доступа
    if not (activation.initiated_by == request.user or 
            activation.assigned_foreman == request.user or
            activation.reviewing_inspector == request.user or
            request.user.is_staff):
        raise Http404
    
    # Получаем события активации
    events = activation.events.all()[:10]
    
    context = {
        'activation': activation,
        'events': events,
    }
    
    return render(request, 'projects/activation_detail.html', context)


@login_required
def inspector_dashboard_activations(request):
    """Дашборд инспектора с проектами на активацию"""
    
    if request.user.user_type != 'inspector':
        return redirect('/')
    
    # Проекты ожидающие проверки
    pending_activations = ProjectActivation.objects.filter(
        status='inspector_review'
    )
    
    # Проекты, проверенные этим инспектором
    from django.db.models import Q
    
    # Показываем только активации, которые имеют дату проверки
    reviewed_activations = ProjectActivation.objects.filter(
        Q(inspector_reviewed_at__isnull=False) |  # С датой проверки
        Q(activated_at__isnull=False)  # Или с датой активации
    ).filter(
        # Фильтруем по инспектору или статусу
        Q(reviewing_inspector=request.user) | 
        Q(status__in=['approved', 'activated', 'rejected'])
    ).order_by('-inspector_reviewed_at', '-activated_at')[:10]
    
    context = {
        'pending_activations': pending_activations,
        'reviewed_activations': reviewed_activations,
    }
    
    return render(request, 'projects/inspector_activations.html', context)


@login_required
def notifications_api(request):
    """API для получения уведомлений пользователя"""
    
    notifications = request.user.project_notifications.filter(
        is_read=False
    ).order_by('-created_at')[:10]
    
    data = []
    for notification in notifications:
        # Проверяем, является ли связанный объект активацией
        activation_id = None
        if (notification.related_object_type == 'ProjectActivation' and 
            notification.related_object_id):
            activation_id = notification.related_object_id
            
        data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'created_at': notification.created_at.isoformat(),
            'activation_id': activation_id
        })
    
    return JsonResponse({'notifications': data})


@csrf_exempt
@login_required
def mark_notification_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    
    if request.method == 'POST':
        try:
            notification = request.user.project_notifications.get(id=notification_id)
            notification.mark_read()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'})
    
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def get_project_activation_status(project):
    """Вспомогательная функция для определения статуса активации проекта"""
    
    if project.status != 'planned':
        return None
    
    today = timezone.now().date()
    
    if project.planned_start_date <= today:
        if hasattr(project, 'activation'):
            return {
                'can_activate': False,
                'status': project.activation.get_status_display(),
                'activation_id': project.activation.id
            }
        else:
            return {
                'can_activate': True,
                'status': 'Доступна активация объекта',
                'activation_id': None
            }
    
    return {
        'can_activate': False,
        'status': f'Активация с {project.planned_start_date.strftime("%d.%m.%Y")}',
        'activation_id': None
    }