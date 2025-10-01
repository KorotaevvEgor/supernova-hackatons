from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
import json
import logging

from projects.models import Project, Work, Comment
from projects.activation_models import ProjectActivation
from materials.models import MaterialDelivery, MaterialType
from accounts.models import User
from accounts.views import foreman_identification, foreman_generate_qr

logger = logging.getLogger(__name__)


@login_required
def foreman_dashboard(request):
    """Главная страница дашборда прораба"""
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Получаем только назначенные проекты с информацией об активации
    assigned_projects = Project.objects.filter(
        foreman=request.user,
        status__in=['active', 'planned']
    ).prefetch_related('works', 'comments', 'material_deliveries')
    
    # Получаем активации проектов для прораба
    project_activations = ProjectActivation.objects.filter(
        assigned_foreman=request.user
    ).select_related('project').order_by('-created_at')
    
    # Создаем словарь для быстрого доступа к статусам активации
    activation_statuses = {activation.project.id: activation for activation in project_activations}
    
    # Статистика для прораба
    total_projects = assigned_projects.count()
    active_projects = assigned_projects.filter(status='active').count()
    
    # Замечания требующие внимания
    pending_comments = Comment.objects.filter(
        project__foreman=request.user,
        status__in=['pending', 'accepted'],
        assigned_to=request.user
    ).count()
    
    # Материалы ожидающие приемки
    pending_materials = MaterialDelivery.objects.filter(
        project__foreman=request.user,
        status='pending'
    ).count()
    
    # Работы на сегодня
    today = timezone.now().date()
    today_works = Work.objects.filter(
        project__foreman=request.user,
        planned_start_date__lte=today,
        planned_end_date__gte=today,
        status__in=['not_started', 'in_progress']
    ).select_related('project', 'work_type')
    
    # Просроченные работы
    overdue_works = Work.objects.filter(
        project__foreman=request.user,
        planned_end_date__lt=today,
        status__in=['not_started', 'in_progress']
    ).select_related('project', 'work_type')
    
    # Статистика по активациям
    activation_stats = {
        'total_activations': project_activations.count(),
        'pending_review': project_activations.filter(status='inspector_review').count(),
        'approved': project_activations.filter(status__in=['approved', 'activated']).count(),
        'rejected': project_activations.filter(status='rejected').count(),
    }
    
    context = {
        'assigned_projects': assigned_projects,
        'project_activations': project_activations,
        'activation_statuses': activation_statuses,
        'stats': {
            'total_projects': total_projects,
            'active_projects': active_projects,
            'pending_comments': pending_comments,
            'pending_materials': pending_materials,
            'today_works_count': today_works.count(),
            'overdue_works_count': overdue_works.count(),
        },
        'activation_stats': activation_stats,
        'today_works': today_works[:10],
        'overdue_works': overdue_works[:10],
    }
    
    return render(request, 'foreman/dashboard.html', context)


@login_required
def project_detail(request, project_id):
    """Детальная страница проекта для прораба"""
    # Проверяем роль и доступ к проекту
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    project = get_object_or_404(
        Project,
        id=project_id,
        foreman=request.user
    )
    
    # Получаем состав работ
    works = project.works.select_related('work_type').order_by('planned_start_date')
    
    # Получаем спецификацию работ
    work_specification = project.work_specification
    
    # Получаем сетевой график
    work_schedule_data = project.work_schedule_data
    
    # Материалы по проекту
    materials = project.material_deliveries.select_related('material_type').order_by('-delivery_date')
    
    # Замечания по проекту
    comments = project.comments.filter(
        Q(assigned_to=request.user) | Q(created_by=request.user)
    ).select_related('created_by').order_by('-created_at')
    
    context = {
        'project': project,
        'works': works,
        'work_specification': work_specification,
        'work_schedule_data': json.dumps(work_schedule_data),
        'materials': materials[:10],
        'comments': comments[:10],
        'can_edit_schedule': True,  # Прораб может редактировать график
    }
    
    return render(request, 'foreman/project_detail.html', context)


@login_required
def materials_control(request):
    """Страница входного контроля материалов"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    project_id = request.GET.get('project')
    status_filter = request.GET.get('status', 'all')
    
    # Базовый запрос
    materials = MaterialDelivery.objects.filter(
        project__foreman=request.user
    ).select_related('project', 'material_type', 'received_by').order_by('-delivery_date')
    
    if project_id and project_id != 'all':
        materials = materials.filter(project_id=project_id)
    
    if status_filter != 'all':
        materials = materials.filter(status=status_filter)
    
    # Пагинация
    paginator = Paginator(materials, 20)
    page = request.GET.get('page')
    materials_page = paginator.get_page(page)
    
    # Проекты для фильтра
    projects = Project.objects.filter(foreman=request.user)
    
    context = {
        'materials': materials_page,
        'projects': projects,
        'current_project': project_id,
        'current_status': status_filter,
        'material_types': MaterialType.objects.all(),
    }
    
    return render(request, 'foreman/materials_control.html', context)


@login_required
def add_material_delivery(request):
    """Добавление поставки материала - Перенаправление на новую систему входного контроля"""
    from django.contrib import messages
    from django.shortcuts import redirect
    
    # Перенаправляем на новую страницу входного контроля
    messages.info(request, 'Функционал добавления материалов перенесён в новую систему входного контроля с автоматическим OCR распознаванием.')
    
    return redirect('materials:incoming_control')

# Старый код закомментирован для совместимости
# OLD CODE COMMENTED OUT FOR MIGRATION TO NEW INCOMING CONTROL SYSTEM:
# if request.method == 'POST':
#     try:
#         # Получаем данные из формы
#         project_id = request.POST.get('project_id')
#         material_type_id = request.POST.get('material_type_id')
#         quantity = request.POST.get('quantity')
#         supplier = request.POST.get('supplier')
#         ttn_number = request.POST.get('ttn_number')
#         delivery_date = request.POST.get('delivery_date')
#         ttn_image = request.FILES.get('ttn_image')
#         quality_cert_image = request.FILES.get('quality_certificate_image')
#         manual_entry = request.POST.get('manual_entry') == 'true'
#         
#         # Валидация
#         project = get_object_or_404(Project, id=project_id, foreman=request.user)
#         material_type = get_object_or_404(MaterialType, id=material_type_id)
#         
#         # Создаем поставку
#         delivery = MaterialDelivery.objects.create(
#             project=project,
#             material_type=material_type,
#             supplier=supplier,
#             quantity=quantity,
#             delivery_date=delivery_date,
#             ttn_number=ttn_number,
#             ttn_image=ttn_image,
#             quality_certificate_image=quality_cert_image,
#             received_by=request.user,
#             manual_entry=manual_entry,
#             status='delivered'
#         )
#         
#         # Если есть геолокация, сохраняем
#         if 'latitude' in request.POST and 'longitude' in request.POST:
#             lat = request.POST.get('latitude')
#             lng = request.POST.get('longitude')
#             delivery.location = f"{lat},{lng}"
#             delivery.save()
#         
#         messages.success(request, 'Поставка материала успешно зарегистрирована')
#         return redirect('foreman:materials_control')
#         
#     except Exception as e:
#         logger.error(f"Error creating material delivery: {str(e)}")
#         messages.error(request, 'Ошибка при регистрации поставки')
#         return redirect('foreman:materials_control')
# 
# # GET запрос - показываем форму
# projects = Project.objects.filter(foreman=request.user)
# material_types = MaterialType.objects.all()
# 
# context = {
#     'projects': projects,
#     'material_types': material_types,
# }
# 
# return render(request, 'foreman/add_material_delivery.html', context)


@login_required
def work_progress(request):
    """Отметка выполненных работ и просмотр перечня работ"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    today = timezone.now().date()
    
    # Получаем проекты прораба для фильтрации
    foreman_projects = Project.objects.filter(foreman=request.user)
    
    # Фильтр по проекту
    selected_project_id = request.GET.get('project')
    selected_project = None
    
    if selected_project_id:
        try:
            selected_project = foreman_projects.get(id=selected_project_id)
        except Project.DoesNotExist:
            pass
    
    # Работы, которые можно отметить как выполненные
    works_filter = {
        'project__foreman': request.user,
        'status__in': ['not_started', 'in_progress'],
        'planned_start_date__lte': today
    }
    
    if selected_project:
        works_filter['project'] = selected_project
    
    available_works = Work.objects.filter(
        **works_filter
    ).select_related('project', 'work_type').order_by('planned_start_date')
    
    # Уже отмеченные работы (ожидающие верификации)
    verification_filter = {
        'project__foreman': request.user,
        'status': 'completed',
        'reported_by_foreman': True,
        'verified_by_control': False
    }
    
    if selected_project:
        verification_filter['project'] = selected_project
    
    pending_verification = Work.objects.filter(
        **verification_filter
    ).select_related('project', 'work_type').order_by('-updated_at')
    
    # Получаем спецификации работ
    work_specifications = []
    try:
        from documents.models import WorkSpecification
        
        specs_filter = {'project__foreman': request.user}
        if selected_project:
            specs_filter['project'] = selected_project
            
        work_specifications = WorkSpecification.objects.filter(
            **specs_filter
        ).select_related('project').prefetch_related('items')
        
    except ImportError:
        pass
    
    context = {
        'available_works': available_works,
        'pending_verification': pending_verification,
        'work_specifications': work_specifications,
        'foreman_projects': foreman_projects,
        'selected_project': selected_project,
        'today': today,
    }
    
    return render(request, 'foreman/work_progress.html', context)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def mark_work_completed(request):
    """API для отметки работы как выполненной"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    
    try:
        data = json.loads(request.body)
        work_id = data.get('work_id')
        notes = data.get('notes', '')
        
        work = get_object_or_404(
            Work,
            id=work_id,
            project__foreman=request.user,
            status__in=['not_started', 'in_progress']
        )
        
        # Отмечаем работу как выполненную
        work.status = 'completed'
        work.reported_by_foreman = True
        work.actual_end_date = timezone.now().date()
        
        if not work.actual_start_date:
            work.actual_start_date = timezone.now().date()
        
        work.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Работа отмечена как выполненная и отправлена на верификацию'
        })
        
    except Exception as e:
        logger.error(f"Error marking work as completed: {str(e)}")
        return JsonResponse({'error': 'Ошибка при отметке работы'}, status=500)


@login_required
def comments_management(request):
    """Управление замечаниями для прораба"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    status_filter = request.GET.get('status', 'pending')
    project_id = request.GET.get('project')
    
    # Базовый запрос - замечания назначенные прорабу или по его проектам
    comments = Comment.objects.filter(
        Q(assigned_to=request.user) | Q(project__foreman=request.user)
    ).select_related('project', 'created_by', 'assigned_to').order_by('-created_at')
    
    if status_filter != 'all':
        comments = comments.filter(status=status_filter)
    
    if project_id and project_id != 'all':
        comments = comments.filter(project_id=project_id)
    
    # Пагинация
    paginator = Paginator(comments, 20)
    page = request.GET.get('page')
    comments_page = paginator.get_page(page)
    
    # Проекты для фильтра
    projects = Project.objects.filter(foreman=request.user)
    
    context = {
        'comments': comments_page,
        'projects': projects,
        'current_status': status_filter,
        'current_project': project_id,
    }
    
    return render(request, 'foreman/comments_management.html', context)


@login_required
def resolve_comment(request, comment_id):
    """Отметка замечания как устраненного"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    comment = get_object_or_404(
        Comment,
        id=comment_id,
        assigned_to=request.user,
        status='accepted'
    )
    
    if request.method == 'POST':
        try:
            response_comment = request.POST.get('response_comment', '')
            
            # Отмечаем замечание как устраненное
            comment.status = 'resolved'
            comment.resolved_at = timezone.now()
            comment.response_comment = response_comment
            comment.save()
            
            # Создаем запись об изменении статуса
            from projects.models import CommentStatusChange
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='accepted',
                to_status='resolved',
                changed_by=request.user,
                reason=response_comment or 'Устранено прорабом'
            )
            
            messages.success(request, 'Замечание отмечено как устраненное')
            return redirect('foreman:comments_management')
            
        except Exception as e:
            logger.error(f"Error resolving comment: {str(e)}")
            messages.error(request, 'Ошибка при устранении замечания')
    
    context = {
        'comment': comment,
    }
    
    return render(request, 'foreman/resolve_comment.html', context)
