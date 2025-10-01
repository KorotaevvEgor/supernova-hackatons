from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from projects.models import Project, Work, ScheduleChange, Comment
from violations.models import Violation
from accounts.models import Visit
import json
from datetime import datetime, date

def create_demo_projects(user):
    """Создаем демо-проекты для дашборда"""
    from projects.models import Project
    from datetime import datetime, timedelta
    
    # Проверяем, что проекты еще не созданы
    if Project.objects.count() > 0:
        return Project.objects.all().select_related('foreman').prefetch_related('work_set')
    
    # Создаем демо-проекты
    demo_projects = [
        {
            'name': 'Проект благоустройства: Парк "Лужники"',
            'address': 'Москва, Лужники',
            'status': 'active',
            'description': 'Комплексное благоустройство парковой зоны с установкой нового оборудования и освещения.',
            'contract_number': 'PK-2024-001',
        },
        {
            'name': 'Проект благоустройства: Площадь Революции',
            'address': 'Москва, Площадь Революции, 1',
            'status': 'planned',
            'description': 'Реконструкция исторической площади с сохранением архитектурных особенностей.',
            'contract_number': 'PL-2024-002',
        },
        {
            'name': 'Проект благоустройства: Набережная Москвы-реки',
            'address': 'Москва, Кремлевская набережная',
            'status': 'completed',
            'description': 'Обновление променадной зоны набережной с созданием современной инфраструктуры.',
            'contract_number': 'NB-2024-003',
        },
        {
            'name': 'Проект благоустройства: Сквер у МКАД',
            'address': 'Москва, ул. Кибальчича, 1',
            'status': 'active',
            'description': 'Создание современной рекреационной зоны для студентов и посетителей академии.',
            'contract_number': 'SK-2024-004',
        },
    ]
    
    created_projects = []
    today = datetime.now().date()
    
    for i, project_data in enumerate(demo_projects):
        project = Project.objects.create(
            name=project_data['name'],
            address=project_data['address'],
            status=project_data['status'],
            description=project_data['description'],
            contract_number=project_data['contract_number'],
            planned_start_date=today - timedelta(days=30 - i*10),
            planned_end_date=today + timedelta(days=60 + i*20),
            control_service=user if hasattr(user, 'user_type') and user.user_type == 'construction_control' else None,
            # Координаты Москвы (примерные)
            coordinates='[[[37.6176, 55.7558], [37.6186, 55.7558], [37.6186, 55.7568], [37.6176, 55.7568], [37.6176, 55.7558]]]' if i == 0 else ''
        )
        created_projects.append(project)
    
    return Project.objects.all().select_related('foreman').prefetch_related('work_set')

@login_required
def profile_dashboard(request):
    """Главная страница личного кабинета строительного контроля"""
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        messages.error(request, 'Доступ к личному кабинету разрешен только строительному контролю')
        return redirect('/')
    
    # Получаем проекты под контролем пользователя
    projects = Project.objects.filter(control_service=request.user)
    
    # Статистика
    pending_remarks = Violation.objects.filter(
        project__control_service=request.user,
        status='open'
    ).count()
    
    # Новые замечания (новая система)
    pending_comments = Comment.objects.filter(
        project__control_service=request.user,
        status='pending'
    ).count()
    
    accepted_comments = Comment.objects.filter(
        project__control_service=request.user,
        status='accepted'
    ).count()
    
    pending_schedule_changes = ScheduleChange.objects.filter(
        work__project__control_service=request.user,
        status='pending'
    ).count()
    
    works_to_verify = Work.objects.filter(
        project__control_service=request.user,
        reported_by_foreman=True,
        verified_by_control=False
    ).count()
    
    # Последние визиты
    recent_visits = Visit.objects.filter(
        user=request.user
    ).select_related('project').order_by('-created_at')[:5]
    
    # Активные проекты
    active_projects = projects.filter(status='active')
    
    # Получаем недавние замечания
    recent_comments = Comment.objects.filter(
        project__control_service=request.user,
        status__in=['pending', 'accepted']
    ).select_related('project', 'created_by', 'assigned_to').order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'projects_count': projects.count(),
        'active_projects_count': active_projects.count(),
        'pending_remarks': pending_remarks,
        'pending_comments': pending_comments,
        'accepted_comments': accepted_comments,
        'pending_schedule_changes': pending_schedule_changes,
        'works_to_verify': works_to_verify,
        'recent_visits': recent_visits,
        'active_projects': active_projects[:5],  # Первые 5 активных проектов
        'recent_comments': recent_comments,
    }
    
    return render(request, 'profile/dashboard.html', context)

@login_required
def modern_dashboard(request):
    """Современный дашборд в стиле показанного интерфейса"""
    context = {
        'today': date.today(),
        'user': request.user,
    }
    
    return render(request, 'modern_dashboard.html', context)

@login_required
def construction_control_dashboard(request):
    """Дашборд строительного контроля (тот же шаблон, что используется в templates/dashboards/construction_control.html)"""
    
    # Импортируем необходимые модели
    from projects.models import Project, Work, ActivationRequest
    from violations.models import Violation
    
    # Отладочная информация
    print(f"\n=== DEBUG: construction_control_dashboard ===")
    print(f"User: {request.user}")
    print(f"User authenticated: {request.user.is_authenticated}")
    print(f"User type: {getattr(request.user, 'user_type', 'NO_USER_TYPE')}")
    print(f"Total projects in DB: {Project.objects.count()}")
    
    # Получаем проекты для пользователя строительного контроля
    if hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control':
        # Показываем все проекты для демонстрации, пока не настроим назначения
        available_projects = Project.objects.all().select_related('foreman').prefetch_related('work_set')
        print(f"Construction control user - showing all projects: {available_projects.count()}")
        
        # Если нет проектов вообще, создаем демо-проекты
        if available_projects.count() == 0:
            available_projects = create_demo_projects(request.user)
            print(f"Created demo projects: {available_projects.count()}")
    else:
        # Для других ролей показываем все проекты
        available_projects = Project.objects.all().select_related('foreman').prefetch_related('work_set')
        print(f"Non-construction control user - showing all projects: {available_projects.count()}")
        
        # Если нет проектов, создаем демо-проекты и для других ролей  
        if available_projects.count() == 0:
            available_projects = create_demo_projects(request.user)
            print(f"Created demo projects for non-control user: {available_projects.count()}")
    
    # Отладочная информация о проектах
    print(f"Final available_projects count: {available_projects.count()}")
    for project in available_projects:
        print(f"- {project.name} ({project.status})")
    
    # Статистика
    total_projects = available_projects.count()
    active_projects = available_projects.filter(status='active').count()
    planned_projects = available_projects.filter(status='planned').count()
    delayed_projects = available_projects.filter(
        status__in=['active', 'planned'],
        planned_end_date__lt=timezone.now().date()
    ).count()
    
    # Проекты на верификации
    pending_verification = Work.objects.filter(
        project__in=available_projects,
        reported_by_foreman=True,
        verified_by_control=False
    ).count()
    
    # Активные нарушения
    active_violations = Violation.objects.filter(
        project__in=available_projects,
        status='open'
    ).count()
    
    # Подготавливаем данные проектов для карты
    projects_for_map = []
    for project in available_projects:
        if project.coordinates:
            projects_for_map.append({
                'id': project.id,
                'name': project.name,
                'address': project.address or 'Адрес не указан',
                'status': project.status,
                'completion': project.completion_percentage,
                'coordinates': {
                    'type': 'Polygon',
                    'coordinates': [project.coordinates] if project.coordinates else []
                }
            })
    
    # Отладка перед отправкой в шаблон
    print(f"\nContext debug:")
    print(f"available_projects type: {type(available_projects)}")
    print(f"available_projects count: {available_projects.count()}")
    print(f"available_projects list: {list(available_projects.values('name', 'status'))}")
    print(f"====")
    
    context = {
        'user': request.user,
        'today': timezone.now().date(),
        'available_projects': available_projects,  # Оставляем QuerySet
        'projects_for_map': projects_for_map,
        'planned_projects_count': planned_projects,
        'pending_verification': pending_verification,
        'stats': {
            'total_projects': total_projects,
            'active_projects': active_projects,
            'planned_projects': planned_projects,
            'delayed_projects': delayed_projects,
            'pending_verification': pending_verification,
            'active_violations': active_violations,
        }
    }
    
    return render(request, 'dashboards/construction_control.html', context)

@login_required
def manage_remarks(request):
    """Управление замечаниями"""
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        messages.error(request, 'Недостаточно прав')
        return redirect('/')
    
    # Получаем замечания по проектам пользователя
    violations = Violation.objects.filter(
        project__control_service=request.user
    ).select_related('project', 'violation_type', 'created_by').order_by('-created_at')
    
    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        violations = violations.filter(status=status_filter)
    
    context = {
        'violations': violations,
        'status_filter': status_filter,
        'user': request.user,
        'status_counts': {
            'open': violations.filter(status='open').count(),
            'in_progress': violations.filter(status='in_progress').count(),
            'resolved': violations.filter(status='resolved').count(),
        }
    }
    
    return render(request, 'profile/manage_remarks.html', context)

@login_required
def manage_schedule_changes(request):
    """Управление изменениями в графике"""
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        messages.error(request, 'Недостаточно прав')
        return redirect('/')
    
    # Получаем изменения графика по проектам пользователя
    schedule_changes = ScheduleChange.objects.filter(
        work__project__control_service=request.user
    ).select_related('work__project', 'work__work_type', 'requested_by').order_by('-created_at')
    
    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        schedule_changes = schedule_changes.filter(status=status_filter)
    
    context = {
        'schedule_changes': schedule_changes,
        'status_filter': status_filter,
        'user': request.user,
        'status_counts': {
            'pending': schedule_changes.filter(status='pending').count(),
            'approved': schedule_changes.filter(status='approved').count(),
            'rejected': schedule_changes.filter(status='rejected').count(),
        }
    }
    
    return render(request, 'profile/manage_schedule_changes.html', context)

@login_required
def approve_remark(request, remark_id):
    """Одобрить замечание"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    violation = get_object_or_404(Violation, id=remark_id)
    
    # Проверяем, что пользователь ответственный за проект
    if violation.project.control_service != request.user:
        return JsonResponse({'error': 'Вы не ответственный за этот проект'}, status=403)
    
    try:
        data = json.loads(request.body)
        comment = data.get('comment', '')
        
        violation.status = 'in_progress'
        violation.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Замечание принято в работу',
            'status': violation.get_status_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def reject_remark(request, remark_id):
    """Отклонить замечание"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    violation = get_object_or_404(Violation, id=remark_id)
    
    # Проверяем, что пользователь ответственный за проект
    if violation.project.control_service != request.user:
        return JsonResponse({'error': 'Вы не ответственный за этот проект'}, status=403)
    
    try:
        data = json.loads(request.body)
        comment = data.get('comment', '')
        
        if not comment:
            return JsonResponse({'error': 'Требуется комментарий для отклонения'}, status=400)
        
        violation.status = 'resolved'  # Или можно добавить статус 'rejected'
        violation.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Замечание отклонено',
            'status': violation.get_status_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def approve_schedule_change(request, change_id):
    """Одобрить изменение графика"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    schedule_change = get_object_or_404(ScheduleChange, id=change_id)
    
    # Проверяем, что пользователь ответственный за проект
    if schedule_change.work.project.control_service != request.user:
        return JsonResponse({'error': 'Вы не ответственный за этот проект'}, status=403)
    
    try:
        data = json.loads(request.body)
        comment = data.get('comment', '')
        
        schedule_change.status = 'approved'
        schedule_change.reviewed_by = request.user
        schedule_change.comment = comment
        schedule_change.save()
        
        # Применяем изменения к работе
        schedule_change.apply_changes()
        
        return JsonResponse({
            'success': True,
            'message': f'Изменение графика для работы "{schedule_change.work.name}" одобрено',
            'status': schedule_change.get_status_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def reject_schedule_change(request, change_id):
    """Отклонить изменение графика"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    schedule_change = get_object_or_404(ScheduleChange, id=change_id)
    
    # Проверяем, что пользователь ответственный за проект
    if schedule_change.work.project.control_service != request.user:
        return JsonResponse({'error': 'Вы не ответственный за этот проект'}, status=403)
    
    try:
        data = json.loads(request.body)
        comment = data.get('comment', '')
        
        if not comment:
            return JsonResponse({'error': 'Требуется комментарий для отклонения'}, status=400)
        
        schedule_change.status = 'rejected'
        schedule_change.reviewed_by = request.user
        schedule_change.comment = comment
        schedule_change.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Изменение графика для работы "{schedule_change.work.name}" отклонено',
            'status': schedule_change.get_status_display()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ========== Управление новыми замечаниями ==========

@login_required
def manage_comments(request):
    """Управление замечаниями (новая система)"""
    if not hasattr(request.user, 'user_type') or request.user.user_type not in ['construction_control', 'foreman']:
        messages.error(request, 'Недостаточно прав')
        return redirect('/')
    
    # Получаем замечания по проектам пользователя
    if request.user.user_type == 'construction_control':
        comments = Comment.objects.filter(
            project__control_service=request.user
        ).select_related('project', 'created_by', 'assigned_to', 'work').order_by('-created_at')
    else:  # foreman
        from django.db.models import Q
        comments = Comment.objects.filter(
            Q(assigned_to=request.user) | Q(project__foreman=request.user)
        ).select_related('project', 'created_by', 'assigned_to', 'work').order_by('-created_at')
    
    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        comments = comments.filter(status=status_filter)
    
    context = {
        'comments': comments[:20],  # Ограничиваем количество
        'status_filter': status_filter,
        'user': request.user,
        'status_counts': {
            'pending': comments.filter(status='pending').count(),
            'accepted': comments.filter(status='accepted').count(),
            'resolved': comments.filter(status='resolved').count(),
            'rejected': comments.filter(status='rejected').count(),
        }
    }
    
    return render(request, 'profile/manage_comments.html', context)


@login_required
def approve_comment(request, comment_id):
    """Одобрить замечание"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type not in ['construction_control', 'foreman']:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права доступа
    has_permission = (
        (request.user.user_type == 'construction_control' and comment.project.control_service == request.user) or
        (request.user.user_type == 'foreman' and comment.project.foreman == request.user)
    )
    
    if not has_permission:
        return JsonResponse({'error': 'Нет прав для управления этим замечанием'}, status=403)
    
    try:
        data = json.loads(request.body)
        due_date_str = data.get('due_date')
        
        due_date = None
        if due_date_str:
            from datetime import datetime
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Неверный формат даты'}, status=400)
        
        if comment.accept(request.user, due_date, comment.assigned_to or comment.project.foreman):
            from projects.models import CommentStatusChange
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='pending',
                to_status='accepted',
                changed_by=request.user,
                reason='Принято к исполнению'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Замечание принято к исполнению',
                'status': comment.get_status_display()
            })
        else:
            return JsonResponse({'error': 'Не удалось принять замечание'}, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def reject_comment(request, comment_id):
    """Отклонить замечание"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    if not hasattr(request.user, 'user_type') or request.user.user_type not in ['construction_control', 'foreman']:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права доступа
    has_permission = (
        (request.user.user_type == 'construction_control' and comment.project.control_service == request.user) or
        (request.user.user_type == 'foreman' and comment.project.foreman == request.user)
    )
    
    if not has_permission:
        return JsonResponse({'error': 'Нет прав для управления этим замечанием'}, status=403)
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '')
        
        if not reason:
            return JsonResponse({'error': 'Требуется причина отклонения'}, status=400)
        
        if comment.reject(request.user, reason):
            from projects.models import CommentStatusChange
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='pending',
                to_status='rejected',
                changed_by=request.user,
                reason=reason
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Замечание отклонено',
                'status': comment.get_status_display()
            })
        else:
            return JsonResponse({'error': 'Не удалось отклонить замечание'}, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
