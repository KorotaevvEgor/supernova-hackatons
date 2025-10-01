from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
import json
import logging

from .models import Project, Work, ProjectTask, ProjectInspection, WorkflowTransition, TaskPhoto
try:
    from violations.models import Violation
except ImportError:
    Violation = None
try:
    from materials.models import MaterialDelivery
except ImportError:
    MaterialDelivery = None

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def activate_project(request, project_id):
    """Активация проекта службой строительного контроля"""
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Проверка роли пользователя
        if not hasattr(request.user, 'role') or request.user.role != 'construction_control':
            return JsonResponse({'error': 'Нет прав для активации проекта'}, status=403)
        
        if not project.can_be_activated(request.user):
            return JsonResponse({'error': 'Проект не может быть активирован'}, status=400)
        
        data = json.loads(request.body)
        
        # Активируем проект
        if project.activate(request.user):
            # Создаем запись о переходе в workflow
            WorkflowTransition.objects.create(
                project=project,
                from_status='planned',
                to_status='active',
                performed_by=request.user,
                reason=data.get('reason', 'Проект активирован службой строительного контроля')
            )
            
            # Автоматически создаем базовые задачи для прораба если назначен
            if project.foreman:
                create_initial_foreman_tasks(project)
            
            return JsonResponse({
                'success': True,
                'message': 'Проект успешно активирован',
                'project_status': project.status,
                'workflow_status': project.workflow_status
            })
        else:
            return JsonResponse({'error': 'Ошибка при активации проекта'}, status=400)
            
    except Exception as e:
        logger.error(f"Error activating project {project_id}: {str(e)}")
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def complete_task(request, task_id):
    """Отметить задачу как выполненную"""
    try:
        task = get_object_or_404(ProjectTask, id=task_id)
        data = json.loads(request.body)
        
        # Получаем геолокацию если передана
        lat = data.get('latitude')
        lng = data.get('longitude')
        
        success, message = task.mark_completed(request.user, lat, lng)
        
        if success:
            # Сохраняем фотоотчеты если есть
            if 'photos' in data:
                for photo_data in data['photos']:
                    # В реальном приложении здесь бы была загрузка файлов
                    # Пока что просто логируем
                    logger.info(f"Photo uploaded for task {task_id}: {photo_data.get('description', 'No description')}")
            
            return JsonResponse({
                'success': True,
                'message': message,
                'task_status': task.status,
                'project_readiness': task.project.readiness_score
            })
        else:
            return JsonResponse({'error': message}, status=400)
            
    except Exception as e:
        logger.error(f"Error completing task {task_id}: {str(e)}")
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def create_inspection(request):
    """Создание проверки инспектором"""
    try:
        data = json.loads(request.body)
        
        # Проверка роли пользователя
        if not hasattr(request.user, 'role') or request.user.role != 'inspector':
            return JsonResponse({'error': 'Нет прав для создания проверки'}, status=403)
        
        project = get_object_or_404(Project, id=data['project_id'])
        
        inspection = ProjectInspection.objects.create(
            project=project,
            inspector=request.user,
            inspection_type=data['inspection_type'],
            scheduled_date=data['scheduled_date'],
            areas_to_check=data.get('areas_to_check', []),
            notes=data.get('notes', '')
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Проверка успешно создана',
            'inspection_id': inspection.id,
            'scheduled_date': inspection.scheduled_date.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error creating inspection: {str(e)}")
        return JsonResponse({'error': 'Ошибка при создании проверки'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def complete_inspection(request, inspection_id):
    """Завершение проверки с результатом"""
    try:
        inspection = get_object_or_404(ProjectInspection, id=inspection_id)
        data = json.loads(request.body)
        
        # Проверка прав доступа
        if inspection.inspector != request.user:
            return JsonResponse({'error': 'Нет прав для завершения данной проверки'}, status=403)
        
        result = data['result']  # 'passed', 'failed', 'partial'
        notes = data.get('notes', '')
        
        inspection.complete_inspection(result, notes)
        
        return JsonResponse({
            'success': True,
            'message': 'Проверка завершена',
            'result': result,
            'project_readiness': inspection.project.readiness_score
        })
        
    except Exception as e:
        logger.error(f"Error completing inspection {inspection_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при завершении проверки'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def report_work_progress(request, work_id):
    """Отчет прораба о выполнении работ"""
    try:
        work = get_object_or_404(Work, id=work_id)
        data = json.loads(request.body)
        
        # Проверка роли пользователя
        if not hasattr(request.user, 'role') or request.user.role != 'foreman':
            return JsonResponse({'error': 'Нет прав для отчета о работах'}, status=403)
        
        # Проверка принадлежности работы к проекту прораба
        if work.project.foreman != request.user:
            return JsonResponse({'error': 'Нет прав на данную работу'}, status=403)
        
        # Обновляем статус работы
        work.reported_by_foreman = True
        if data.get('completed', False):
            work.status = 'completed'
            work.actual_end_date = timezone.now().date()
        elif work.status == 'not_started':
            work.status = 'in_progress'
            work.actual_start_date = timezone.now().date()
        
        work.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Отчет о работах сохранен',
            'work_status': work.status,
            'project_completion': work.project.completion_percentage
        })
        
    except Exception as e:
        logger.error(f"Error reporting work progress {work_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при сохранении отчета'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def get_project_status(request, project_id):
    """Получение текущего статуса проекта и готовности"""
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Подсчитываем различные метрики
        total_works = project.works.count()
        completed_works = project.works.filter(status__in=['completed', 'verified']).count()
        
        total_tasks = project.tasks.count()
        completed_tasks = project.tasks.filter(status__in=['completed', 'verified']).count()
        
        total_inspections = project.inspections.count()
        completed_inspections = project.inspections.filter(status='completed').count()
        
        try:
            violations = project.violations.all()
            total_violations = violations.count()
            resolved_violations = violations.filter(status='resolved').count()
        except:
            total_violations = 0
            resolved_violations = 0
        
        return JsonResponse({
            'project_id': project.id,
            'name': project.name,
            'status': project.status,
            'workflow_status': project.workflow_status,
            'readiness_score': project.readiness_score,
            'completion_percentage': project.completion_percentage,
            'metrics': {
                'works': {
                    'total': total_works,
                    'completed': completed_works,
                    'percentage': int((completed_works / total_works) * 100) if total_works > 0 else 0
                },
                'tasks': {
                    'total': total_tasks,
                    'completed': completed_tasks,
                    'percentage': int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
                },
                'inspections': {
                    'total': total_inspections,
                    'completed': completed_inspections,
                    'percentage': int((completed_inspections / total_inspections) * 100) if total_inspections > 0 else 0
                },
                'violations': {
                    'total': total_violations,
                    'resolved': resolved_violations,
                    'percentage': int((resolved_violations / total_violations) * 100) if total_violations > 0 else 100
                }
            },
            'can_be_completed': project.readiness_score >= 95
        })
        
    except Exception as e:
        logger.error(f"Error getting project status {project_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при получении статуса проекта'}, status=500)


def create_initial_foreman_tasks(project):
    """Создание начальных задач для прораба при активации проекта"""
    initial_tasks = [
        {
            'title': 'Проверка готовности рабочего места',
            'description': 'Проверить готовность площадки к началу работ, наличие необходимых инструментов и материалов',
            'priority': 'high',
            'location_required': True
        },
        {
            'title': 'Входной контроль материалов',
            'description': 'Провести входной контроль всех материалов, проверить сертификаты качества',
            'priority': 'medium',
            'location_required': False
        },
        {
            'title': 'Организация безопасности труда',
            'description': 'Проверить соблюдение требований безопасности труда на объекте',
            'priority': 'critical',
            'location_required': True
        }
    ]
    
    for task_data in initial_tasks:
        ProjectTask.objects.create(
            project=project,
            title=task_data['title'],
            description=task_data['description'],
            assigned_to=project.foreman,
            created_by=project.control_service,
            priority=task_data['priority'],
            location_required=task_data['location_required'],
            due_date=timezone.now() + timezone.timedelta(days=3)
        )


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def upload_task_photo(request, task_id):
    """Загрузка фото для задачи"""
    try:
        task = get_object_or_404(ProjectTask, id=task_id)
        
        # Проверка прав доступа
        if task.assigned_to != request.user:
            return JsonResponse({'error': 'Нет прав на добавление фото к данной задаче'}, status=403)
        
        if 'photo' not in request.FILES:
            return JsonResponse({'error': 'Фото не передано'}, status=400)
        
        photo = request.FILES['photo']
        description = request.POST.get('description', '')
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        
        task_photo = TaskPhoto.objects.create(
            task=task,
            photo=photo,
            description=description,
            taken_by=request.user,
            location_lat=float(lat) if lat else None,
            location_lng=float(lng) if lng else None
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Фото успешно загружено',
            'photo_id': task_photo.id,
            'photo_url': task_photo.photo.url
        })
        
    except Exception as e:
        logger.error(f"Error uploading task photo {task_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при загрузке фото'}, status=500)


# ========== API для системы замечаний ==========

@csrf_exempt
@require_http_methods(["GET", "POST"])
@login_required
def comments_list_create(request):
    """Список замечаний и создание нового"""
    from .models import Comment, Work, CommentStatusChange
    from django.db.models import Q
    
    try:
        if request.method == 'GET':
            # Получение списка замечаний
            comments = Comment.objects.select_related('project', 'work', 'created_by', 'assigned_to').all()
            
            # Фильтруем по ролям
            if hasattr(request.user, 'user_type'):
                if request.user.user_type == 'foreman':
                    comments = comments.filter(
                        Q(assigned_to=request.user) | Q(project__foreman=request.user)
                    )
                elif request.user.user_type == 'construction_control':
                    comments = comments.filter(
                        Q(created_by=request.user) | Q(project__control_service=request.user)
                    )
            
            # Параметры запроса
            project_id = request.GET.get('project_id')
            status = request.GET.get('status')
            priority = request.GET.get('priority')
            limit = int(request.GET.get('limit', 20))
            
            if project_id:
                comments = comments.filter(project_id=project_id)
            if status:
                comments = comments.filter(status=status)
            if priority:
                comments = comments.filter(priority=priority)
            
            comments = comments.order_by('-created_at')[:limit]
            
            comments_data = []
            for comment in comments:
                comments_data.append({
                    'id': comment.id,
                    'title': comment.title,
                    'description': comment.description,
                    'status': comment.status,
                    'priority': comment.priority,
                    'project': {
                        'id': comment.project.id,
                        'name': comment.project.name
                    },
                    'work': {
                        'id': comment.work.id,
                        'name': comment.work.name
                    } if comment.work else None,
                    'created_by': comment.created_by.get_full_name(),
                    'assigned_to': comment.assigned_to.get_full_name() if comment.assigned_to else None,
                    'created_at': comment.created_at.isoformat(),
                    'due_date': comment.due_date.isoformat() if comment.due_date else None,
                    'is_overdue': comment.is_overdue,
                    'created_at_location': comment.created_at_location,
                })
            
            return JsonResponse({
                'success': True,
                'comments': comments_data,
                'count': len(comments_data)
            })
        
        elif request.method == 'POST':
            # Создание нового замечания
            if not (hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control'):
                return JsonResponse({'error': 'Только строительный контроль может создавать замечания'}, status=403)
            
            data = json.loads(request.body)
            
            project = get_object_or_404(Project, id=data['project_id'])
            
            work = None
            if data.get('work_id'):
                try:
                    work = Work.objects.get(id=data['work_id'], project=project)
                except Work.DoesNotExist:
                    pass
            
            # Проверяем геолокацию
            lat = float(data['latitude'])
            lng = float(data['longitude'])
            
            # Проверяем нахождение на объекте
            from .views import _parse_polygon_coords, _point_in_polygon
            polygon = _parse_polygon_coords(project.coordinates or '')
            at_location = False
            if polygon:
                at_location = _point_in_polygon(lng, lat, polygon)
            
            if not at_location and polygon:
                return JsonResponse({'error': 'Замечание можно создать только находясь на объекте'}, status=400)
            
            comment = Comment.objects.create(
                project=project,
                work=work,
                title=data['title'],
                description=data['description'],
                priority=data.get('priority', 'medium'),
                created_by=request.user,
                assigned_to=project.foreman,
                location_lat=lat,
                location_lng=lng,
                created_at_location=at_location,
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Замечание успешно создано',
                'comment_id': comment.id
            })
    
    except Exception as e:
        logger.error(f"Error in comments_list_create: {str(e)}")
        return JsonResponse({'error': 'Ошибка при обработке запроса'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
@login_required
def comment_detail_api(request, comment_id):
    """Получение детальной информации о замечании"""
    from .models import Comment, CommentPhoto, CommentStatusChange
    
    try:
        comment = get_object_or_404(Comment, id=comment_id)
        
        # Проверяем права доступа
        has_access = (
            comment.created_by == request.user or
            comment.assigned_to == request.user or
            (hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control' and comment.project.control_service == request.user) or
            (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman' and comment.project.foreman == request.user)
        )
        
        if not has_access:
            return JsonResponse({'error': 'Нет доступа к этому замечанию'}, status=403)
        
        # Получаем фотографии
        photos = CommentPhoto.objects.filter(comment=comment).select_related('taken_by').order_by('is_before', '-created_at')
        photos_data = []
        for photo in photos:
            photos_data.append({
                'id': photo.id,
                'photo_url': photo.photo.url,
                'description': photo.description,
                'is_before': photo.is_before,
                'taken_by': photo.taken_by.get_full_name(),
                'created_at': photo.created_at.isoformat()
            })
        
        # Получаем историю изменений
        status_changes = CommentStatusChange.objects.filter(comment=comment).select_related('changed_by').order_by('-created_at')
        changes_data = []
        for change in status_changes:
            changes_data.append({
                'id': change.id,
                'from_status': change.from_status,
                'to_status': change.to_status,
                'changed_by': change.changed_by.get_full_name(),
                'reason': change.reason,
                'created_at': change.created_at.isoformat()
            })
        
        comment_data = {
            'id': comment.id,
            'title': comment.title,
            'description': comment.description,
            'status': comment.status,
            'priority': comment.priority,
            'project': {
                'id': comment.project.id,
                'name': comment.project.name,
                'address': comment.project.address
            },
            'work': {
                'id': comment.work.id,
                'name': comment.work.name
            } if comment.work else None,
            'created_by': comment.created_by.get_full_name(),
            'assigned_to': comment.assigned_to.get_full_name() if comment.assigned_to else None,
            'location': {
                'lat': comment.location_lat,
                'lng': comment.location_lng,
                'at_location': comment.created_at_location
            },
            'created_at': comment.created_at.isoformat(),
            'due_date': comment.due_date.isoformat() if comment.due_date else None,
            'resolved_at': comment.resolved_at.isoformat() if comment.resolved_at else None,
            'response_comment': comment.response_comment,
            'is_overdue': comment.is_overdue,
            'photos': photos_data,
            'status_changes': changes_data
        }
        
        return JsonResponse({
            'success': True,
            'comment': comment_data
        })
    
    except Exception as e:
        logger.error(f"Error in comment_detail_api {comment_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при получении замечания'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def accept_comment_api(request, comment_id):
    """Принятие замечания к исполнению"""
    from .models import Comment, CommentStatusChange
    from datetime import datetime
    
    try:
        comment = get_object_or_404(Comment, id=comment_id)
        data = json.loads(request.body)
        
        # Проверяем права
        can_manage = (
            hasattr(request.user, 'user_type') and
            request.user.user_type in ['construction_control', 'foreman'] and
            (comment.project.control_service == request.user or comment.project.foreman == request.user)
        )
        
        if not can_manage:
            return JsonResponse({'error': 'Нет прав для управления этим замечанием'}, status=403)
        
        # Парсим дату срока устранения
        due_date = None
        if data.get('due_date'):
            try:
                due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Неверный формат даты'}, status=400)
        
        # Назначаем ответственного
        assigned_to = None
        if data.get('assigned_to_id'):
            from accounts.models import User
            try:
                assigned_to = User.objects.get(id=data['assigned_to_id'])
            except User.DoesNotExist:
                pass
        
        # Принимаем замечание
        if comment.accept(request.user, due_date, assigned_to):
            # Логируем изменение
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
                'new_status': comment.status
            })
        else:
            return JsonResponse({'error': 'Не удалось принять замечание'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in accept_comment_api {comment_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при принятии замечания'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def reject_comment_api(request, comment_id):
    """Отклонение замечания"""
    from .models import Comment, CommentStatusChange
    
    try:
        comment = get_object_or_404(Comment, id=comment_id)
        data = json.loads(request.body)
        
        # Проверяем права
        can_manage = (
            hasattr(request.user, 'user_type') and
            request.user.user_type in ['construction_control', 'foreman'] and
            (comment.project.control_service == request.user or comment.project.foreman == request.user)
        )
        
        if not can_manage:
            return JsonResponse({'error': 'Нет прав для управления этим замечанием'}, status=403)
        
        reason = data.get('reason', '')
        
        # Отклоняем замечание
        if comment.reject(request.user, reason):
            # Логируем изменение
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='pending',
                to_status='rejected',
                changed_by=request.user,
                reason=reason or 'Замечание отклонено'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Замечание отклонено',
                'new_status': comment.status
            })
        else:
            return JsonResponse({'error': 'Не удалось отклонить замечание'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in reject_comment_api {comment_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при отклонении замечания'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def resolve_comment_api(request, comment_id):
    """Отметка замечания как устраненного"""
    from .models import Comment, CommentStatusChange
    
    try:
        comment = get_object_or_404(Comment, id=comment_id)
        data = json.loads(request.body)
        
        # Проверяем права
        can_resolve = (
            comment.assigned_to == request.user or
            (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman' and comment.project.foreman == request.user)
        )
        
        if not can_resolve:
            return JsonResponse({'error': 'Нет прав для отметки этого замечания как устраненного'}, status=403)
        
        resolution_comment = data.get('comment', '')
        
        # Отмечаем как устраненное
        if comment.resolve(request.user, resolution_comment):
            # Логируем изменение
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='accepted',
                to_status='resolved',
                changed_by=request.user,
                reason=resolution_comment or 'Замечание устранено'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Замечание отмечено как устраненное',
                'new_status': comment.status
            })
        else:
            return JsonResponse({'error': 'Не удалось отметить замечание как устраненное'}, status=400)
    
    except Exception as e:
        logger.error(f"Error in resolve_comment_api {comment_id}: {str(e)}")
        return JsonResponse({'error': 'Ошибка при отметке замечания как устраненного'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def validate_location_for_comment(request):
    """Проверка нахождения пользователя на объекте для создания замечания"""
    try:
        data = json.loads(request.body)
        
        project = get_object_or_404(Project, id=data['project_id'])
        lat = float(data['latitude'])
        lng = float(data['longitude'])
        
        # Проверяем нахождение в полигоне
        from .views import _parse_polygon_coords, _point_in_polygon
        polygon = _parse_polygon_coords(project.coordinates or '')
        
        if not polygon:
            return JsonResponse({
                'valid': True,
                'message': 'Полигон объекта не определен, проверка местоположения не выполняется'
            })
        
        at_location = _point_in_polygon(lng, lat, polygon)
        
        return JsonResponse({
            'valid': at_location,
            'message': 'Вы находитесь на объекте' if at_location else 'Вы находитесь вне объекта',
            'coordinates': {'lat': lat, 'lng': lng},
            'project': {
                'id': project.id,
                'name': project.name,
                'address': project.address
            }
        })
    
    except Exception as e:
        logger.error(f"Error in validate_location_for_comment: {str(e)}")
        return JsonResponse({'error': 'Ошибка при проверке местоположения'}, status=500)
