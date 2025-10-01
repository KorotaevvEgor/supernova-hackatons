from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .forms import ViolationCommentForm
import json
import logging
from datetime import datetime, timedelta

from projects.models import Project, Work, Comment, ProjectQRCode, QRVerification
from projects.activation_models import ProjectActivation
from materials.models import MaterialDelivery, MaterialType
from accounts.models import User
from .models import (
    ViolationType, InspectorViolation, ViolationPhoto, ViolationComment,
    LabSampleRequest, ProjectActivationApproval
)
from dataset.models import ViolationClassifier, WorkSpecification

logger = logging.getLogger(__name__)


@login_required
def inspector_dashboard(request):
    """Главная страница дашборда инспектора контрольного органа"""
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Статистика нарушений
    my_violations = InspectorViolation.objects.filter(inspector=request.user)
    total_violations = my_violations.count()
    active_violations = my_violations.exclude(status__in=['verified', 'closed']).count()
    overdue_violations = my_violations.filter(
        deadline__lt=timezone.now().date(),
        status__in=['detected', 'notified', 'in_correction']
    ).count()
    
    # Лабораторные пробы
    my_lab_requests = LabSampleRequest.objects.filter(requested_by=request.user)
    pending_lab_requests = my_lab_requests.exclude(status__in=['completed', 'cancelled']).count()
    
    # Одобрения активации проектов
    pending_approvals = ProjectActivation.objects.filter(
        status='inspector_review'
    ).count()
    
    # Все проекты доступные для инспектора (в активном статусе)
    available_projects = Project.objects.filter(
        status__in=['planned', 'active']
    ).select_related('foreman', 'control_service')
    
    # Недавние нарушения
    recent_violations = my_violations.select_related(
        'project', 'violation_type', 'assigned_to'
    ).order_by('-created_at')[:10]
    
    # Последние заявки на пробы
    recent_lab_requests = my_lab_requests.select_related(
        'project', 'material_type'
    ).order_by('-created_at')[:5]
    
    # Проекты требующие одобрения активации
    projects_awaiting_approval = Project.objects.filter(
        activation__status='inspector_review'
    ).select_related('activation')[:5]
    
    context = {
        'stats': {
            'total_violations': total_violations,
            'active_violations': active_violations,
            'overdue_violations': overdue_violations,
            'pending_lab_requests': pending_lab_requests,
            'pending_approvals': pending_approvals,
            'available_projects_count': available_projects.count(),
        },
        'available_projects': available_projects[:8],
        'recent_violations': recent_violations,
        'recent_lab_requests': recent_lab_requests,
        'projects_awaiting_approval': projects_awaiting_approval,
    }
    
    return render(request, 'inspector/dashboard.html', context)


@login_required
def violation_classifier(request):
    """Классификатор нарушений из датасета ЛЦТ"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    category_filter = request.GET.get('category', 'all')
    violation_type_filter = request.GET.get('violation_type', 'all')
    search_query = request.GET.get('search', '')
    
    # Базовый запрос
    violations = ViolationClassifier.objects.all()
    
    if category_filter != 'all':
        violations = violations.filter(category=category_filter)
    
    if violation_type_filter != 'all':
        violations = violations.filter(violation_type=violation_type_filter)
    
    if search_query:
        violations = violations.filter(
            Q(name__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(violations.order_by('category', 'name'), 50)
    page = request.GET.get('page')
    violations_page = paginator.get_page(page)
    
    # Статистика по категориям
    stats_by_category = ViolationClassifier.objects.values('category', 'category').annotate(
        count=Count('id')
    ).order_by('category')
    
    # Статистика по типам
    stats_by_type = ViolationClassifier.objects.values('violation_type', 'violation_type').annotate(
        count=Count('id')
    ).order_by('violation_type')
    
    context = {
        'violations': violations_page,
        'categories': ViolationClassifier.CATEGORY_CHOICES,
        'violation_types': ViolationClassifier.TYPE_CHOICES,
        'current_category': category_filter,
        'current_violation_type': violation_type_filter,
        'search_query': search_query,
        'stats_by_category': stats_by_category,
        'stats_by_type': stats_by_type,
        'total_violations': ViolationClassifier.objects.count(),
    }
    
    return render(request, 'inspector/violation_classifier.html', context)


@login_required
def work_specifications(request):
    """Спецификации работ по объектам"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    object_filter = request.GET.get('object', 'all')
    unit_filter = request.GET.get('unit', 'all')
    search_query = request.GET.get('search', '')
    
    # Базовый запрос
    specifications = WorkSpecification.objects.all()
    
    if object_filter != 'all':
        specifications = specifications.filter(object_name=object_filter)
    
    if unit_filter != 'all':
        specifications = specifications.filter(unit=unit_filter)
    
    if search_query:
        specifications = specifications.filter(
            Q(work_name__icontains=search_query) |
            Q(object_name__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    
    # Пагинация
    paginator = Paginator(specifications.order_by('object_name', 'work_name'), 25)
    page = request.GET.get('page')
    specifications_page = paginator.get_page(page)
    
    # Списки для фильтров
    objects_list = WorkSpecification.objects.values_list('object_name', flat=True).distinct().order_by('object_name')
    units_list = WorkSpecification.objects.values_list('unit', flat=True).distinct().order_by('unit')
    
    # Статистика
    total_specifications = WorkSpecification.objects.count()
    objects_count = WorkSpecification.objects.values('object_name').distinct().count()
    
    context = {
        'specifications': specifications_page,
        'objects_list': objects_list,
        'units_list': units_list,
        'current_object': object_filter,
        'current_unit': unit_filter,
        'search_query': search_query,
        'total_specifications': total_specifications,
        'objects_count': objects_count,
    }
    
    return render(request, 'inspector/work_specifications.html', context)


@login_required
def violations_list(request):
    """Список всех нарушений инспектора"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    project_id = request.GET.get('project')
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    overdue_only = request.GET.get('overdue') == 'true'
    
    # Базовый запрос
    violations = InspectorViolation.objects.filter(
        inspector=request.user
    ).select_related(
        'project', 'violation_type', 'assigned_to'
    ).prefetch_related('photos')
    
    if project_id and project_id != 'all':
        violations = violations.filter(project_id=project_id)
    
    if status_filter != 'all':
        violations = violations.filter(status=status_filter)
    
    if priority_filter != 'all':
        violations = violations.filter(priority=priority_filter)
    
    if overdue_only:
        violations = violations.filter(
            deadline__lt=timezone.now().date(),
            status__in=['detected', 'notified', 'in_correction']
        )
    
    # Пагинация
    paginator = Paginator(violations.order_by('-created_at'), 20)
    page = request.GET.get('page')
    violations_page = paginator.get_page(page)
    
    # Проекты для фильтра
    projects = Project.objects.all()
    
    context = {
        'violations': violations_page,
        'projects': projects,
        'current_project': project_id,
        'current_status': status_filter,
        'current_priority': priority_filter,
        'overdue_only': overdue_only,
        'violation_statuses': InspectorViolation.STATUS_CHOICES,
        'violation_priorities': InspectorViolation.PRIORITY_CHOICES,
    }
    
    return render(request, 'inspector/violations_list.html', context)


@login_required
def add_violation(request):
    """Добавление нового нарушения"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            project_id = request.POST.get('project_id')
            violation_classifier_id = request.POST.get('violation_classifier_id')
            title = request.POST.get('title')
            description = request.POST.get('description')
            priority = request.POST.get('priority', 'medium')
            location_description = request.POST.get('location_description', '')
            assigned_to_id = request.POST.get('assigned_to')
            
            # Данные верификации
            verification_type = request.POST.get('verification_type')
            qr_code_id = request.POST.get('qr_code_id')
            
            # Проверка подтверждения местонахождения
            if not verification_type or verification_type not in ['qr_code', 'geolocation']:
                messages.error(request, 'Необходимо подтвердить ваше нахождение на объекте через QR-код или геолокацию')
                raise ValueError('Нет подтверждения местонахождения')
            
            # Валидация
            project = get_object_or_404(Project, id=project_id)
            
            # Классификатор (обязательно)
            from violations.models import ViolationClassifier
            violation_classifier = get_object_or_404(ViolationClassifier, id=violation_classifier_id, is_active=True)
            
            # Получаем дефолтный тип нарушения для обратной совместимости
            violation_type = ViolationType.objects.filter(is_active=True).first()
            if not violation_type:
                # Создаем дефолтный тип нарушения
                violation_type = ViolationType.objects.create(
                    code='DEFAULT',
                    name='Общий тип нарушения',
                    description='Автоматически созданный тип',
                    severity='medium',
                    default_deadline_days=30,
                    is_active=True
                )
            
            # Вычисляем срок устранения
            # Приоритет: классификатор, затем тип нарушения, затем 30 дней
            if violation_classifier.regulatory_deadline_days:
                suggested_days = violation_classifier.regulatory_deadline_days
            elif violation_type:
                suggested_days = violation_type.default_deadline_days
            else:
                suggested_days = 30
            
            deadline_days = int(request.POST.get('deadline_days', suggested_days))
            deadline = timezone.now().date() + timedelta(days=deadline_days)
            
            # Создаем нарушение
            violation = InspectorViolation.objects.create(
                project=project,
                violation_type=violation_type,
                violation_classifier=violation_classifier,
                inspector=request.user,
                title=title,
                description=description,
                priority=priority,
                location_description=location_description,
                deadline=deadline,
                status='detected'
            )
            
            # Обработка верификации местонахождения
            if verification_type == 'qr_code' and qr_code_id:
                try:
                    # Проверяем, что QR-код существует и активен
                    qr_code = get_object_or_404(ProjectQRCode, id=qr_code_id, is_active=True)
                    
                    # Сохраняем ссылку на QR-код
                    violation.qr_code_verified = qr_code
                    violation.verification_method = 'qr_code'
                    
                    # Используем координаты места размещения QR-кода
                    if qr_code.location_lat and qr_code.location_lng:
                        violation.location_lat = qr_code.location_lat
                        violation.location_lng = qr_code.location_lng
                    
                    violation.save()
                    
                except Exception as e:
                    logger.error(f"Error processing QR verification: {str(e)}")
                    messages.error(request, 'Ошибка при обработке QR-верификации')
                    
            elif verification_type == 'geolocation':
                # Геолокация
                if 'latitude' in request.POST and 'longitude' in request.POST:
                    try:
                        lat = float(request.POST.get('latitude'))
                        lng = float(request.POST.get('longitude'))
                        violation.location_lat = lat
                        violation.location_lng = lng
                        violation.verification_method = 'geolocation'
                        violation.save()
                    except (TypeError, ValueError):
                        messages.error(request, 'Ошибка при обработке координат')
                        raise ValueError('Неверные координаты')
            
            # Назначаем ответственного
            if assigned_to_id:
                try:
                    assigned_to = User.objects.get(id=assigned_to_id)
                    violation.assigned_to = assigned_to
                    violation.status = 'notified'
                    violation.save()
                except User.DoesNotExist:
                    pass
            
            # Сохраняем фотографии
            for i, photo_file in enumerate(request.FILES.getlist('photos')):
                photo_desc = request.POST.get(f'photo_description_{i}', '')
                ViolationPhoto.objects.create(
                    violation=violation,
                    photo=photo_file,
                    photo_type='violation',
                    description=photo_desc,
                    taken_by=request.user
                )
            
            messages.success(request, 'Нарушение успешно зафиксировано')
            return redirect('inspector:violations_list')
            
        except Exception as e:
            logger.error(f"Error creating violation: {str(e)}")
            messages.error(request, 'Ошибка при создании нарушения')
    
    # GET запрос - показываем форму
    projects = Project.objects.filter(status__in=['planned', 'active'])
    potential_assignees = User.objects.filter(
        user_type__in=['foreman', 'construction_control']
    )
    
    # Классификатор нарушений
    from violations.models import ViolationClassifier
    violation_classifiers = ViolationClassifier.objects.filter(is_active=True).order_by('category', 'name')
    
    context = {
        'projects': projects,
        'violation_classifiers': violation_classifiers,
        'potential_assignees': potential_assignees,
        'priorities': InspectorViolation.PRIORITY_CHOICES,
    }
    
    return render(request, 'inspector/add_violation.html', context)


@login_required
def violation_detail(request, violation_id):
    """Детальная страница нарушения"""
    # Отладочная информация при необходимости
    # print(f"🔍 violation_detail called: method={request.method}, violation_id={violation_id}")
    # print(f"🔍 Request user: {request.user}, user_type: {getattr(request.user, 'user_type', 'None')}")
    
    # Получаем нарушение
    violation = get_object_or_404(
        InspectorViolation.objects.select_related(
            'project', 'violation_type', 'violation_classifier', 
            'inspector', 'assigned_to'
        ).prefetch_related('photos', 'comments__author'),
        id=violation_id
    )
    
    # Проверяем права доступа
    has_access = False
    user_type = getattr(request.user, 'user_type', None)
    
    if user_type == 'inspector':
        # Инспектор может смотреть все нарушения
        has_access = True
    elif user_type == 'foreman':
        # Прораб может смотреть нарушения по своим проектам
        has_access = (
            violation.project.foreman == request.user or 
            violation.assigned_to == request.user
        )
    elif user_type == 'construction_control':
        # Строительный контроль может смотреть нарушения по своим проектам
        has_access = violation.project.control_service == request.user
    
    if not has_access:
        messages.error(request, 'У вас нет доступа к этому нарушению')
        return redirect('dashboard')
    
    # Обработка POST запросов
    
    # Добавление комментария (доступно всем ролям)
    if request.method == 'POST' and 'add_comment' in request.POST:
        comment_form = ViolationCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.violation = violation
            comment.author = request.user
            comment.save()
            messages.success(request, 'Комментарий успешно добавлен')
            return redirect('inspector:violation_detail', violation_id=violation.id)
        else:
            messages.error(request, f'Ошибка при добавлении комментария: {comment_form.errors}')
    
    # Отметка нарушения как исправленного (для прорабов)
    elif request.method == 'POST' and 'mark_corrected' in request.POST and user_type == 'foreman':
        if violation.status == 'in_correction' and (
            violation.assigned_to == request.user or violation.project.foreman == request.user
        ):
            correction_comment = request.POST.get('correction_comment', '')
            violation.status = 'corrected'
            violation.corrected_at = timezone.now()
            violation.correction_comment = correction_comment
            violation.save()
            messages.success(request, 'Нарушение отмечено как устраненное')
            return redirect('inspector:violation_detail', violation_id=violation.id)
    
    # Проверка исправления (только для инспекторов)
    elif request.method == 'POST' and 'verify_correction' in request.POST and user_type == 'inspector':
        if violation.status == 'corrected':
            inspector_comment = request.POST.get('inspector_comment', '')
            action = request.POST.get('verification_action')
            
            if action == 'approve':
                violation.status = 'verified'
                violation.verified_at = timezone.now()
                violation.inspector_comment = inspector_comment
                violation.save()
                messages.success(request, 'Устранение нарушения подтверждено')
            elif action == 'reject':
                violation.status = 'in_correction'
                violation.inspector_comment = inspector_comment
                violation.save()
                messages.warning(request, 'Устранение нарушения отклонено, требует доработки')
            
            return redirect('inspector:violation_detail', violation_id=violation.id)
    
    # Форма для нового комментария
    comment_form = ViolationCommentForm()
    
    # Группируем фотографии по типу
    all_photos = violation.photos.select_related('taken_by').order_by('-created_at')
    photos_by_type = {
        'violation': all_photos.filter(photo_type='violation'),
        'correction': all_photos.filter(photo_type='correction'),
        'verification': all_photos.filter(photo_type='verification'),
    }
    
    # Получаем комментарии к нарушению
    comments = violation.comments.select_related('author').order_by('-created_at')
    
    # Определяем возможности пользователя
    can_verify = user_type == 'inspector'  # Инспектор может проверять исправления
    can_mark_corrected = (
        user_type == 'foreman' and 
        violation.status == 'in_correction' and 
        (violation.assigned_to == request.user or violation.project.foreman == request.user)
    )
    can_add_photos = user_type in ['foreman', 'inspector']  # Можно добавлять фото
    
    # Данные для карты - преобразуем координаты проекта в JSON
    project_coordinates_json = None
    if violation.project and violation.project.coordinates:
        try:
            # Используем метод модели для преобразования WKT в JSON
            coordinates_data = violation.project.get_coordinates_json()
            if coordinates_data:
                import json
                project_coordinates_json = json.dumps(coordinates_data)
        except Exception as e:
            print(f"Error getting project coordinates for violation {violation.id}: {e}")
    
    context = {
        'violation': violation,
        'all_photos': all_photos,
        'photos_by_type': photos_by_type,
        'violation_photo_types': ViolationPhoto.PHOTO_TYPE_CHOICES,
        'status_choices': InspectorViolation.STATUS_CHOICES,
        'priority_choices': InspectorViolation.PRIORITY_CHOICES,
        'comment_form': comment_form,
        'comments': comments,
        'user_type': user_type,
        'can_verify': can_verify,
        'can_mark_corrected': can_mark_corrected,
        'can_add_photos': can_add_photos,
        'project_coordinates_json': project_coordinates_json,  # Добавляем координаты для карты
    }
    
    return render(request, 'inspector/violation_detail.html', context)


@login_required 
def lab_requests(request):
    """Управление заявками на лабораторные пробы"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    project_id = request.GET.get('project')
    status_filter = request.GET.get('status', 'all')
    urgency_filter = request.GET.get('urgency', 'all')
    
    # Базовый запрос
    requests_qs = LabSampleRequest.objects.filter(
        requested_by=request.user
    ).select_related('project', 'material_type')
    
    if project_id and project_id != 'all':
        requests_qs = requests_qs.filter(project_id=project_id)
    
    if status_filter != 'all':
        requests_qs = requests_qs.filter(status=status_filter)
    
    if urgency_filter != 'all':
        requests_qs = requests_qs.filter(urgency=urgency_filter)
    
    # Пагинация
    paginator = Paginator(requests_qs.order_by('-created_at'), 15)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    # Данные для фильтров
    projects = Project.objects.all()
    
    # Статистика по статусам (общая, без фильтров)
    all_requests = LabSampleRequest.objects.filter(requested_by=request.user)
    
    # Счетчики для карточек
    from django.db.models import Q
    
    stats = {
        'total_requests': all_requests.count(),
        'testing_count': all_requests.filter(status='testing').count(),
        'completed_count': all_requests.filter(status='completed').count(),
        'overdue_count': all_requests.filter(
            expected_results_date__isnull=False,
            expected_results_date__lt=timezone.now().date(),
            status__in=['requested', 'scheduled', 'sampling', 'testing']
        ).count(),
    }
    
    context = {
        'lab_requests': requests_page,
        'projects': projects,
        'current_project': project_id,
        'current_status': status_filter,
        'current_urgency': urgency_filter,
        'request_statuses': LabSampleRequest.STATUS_CHOICES,
        'urgency_levels': LabSampleRequest.URGENCY_CHOICES,
        'stats': stats,
    }
    
    return render(request, 'inspector/lab_requests.html', context)


@login_required
def create_lab_request(request):
    """Создание заявки на лабораторные пробы"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Получаем данные формы
            project_id = request.POST.get('project_id')
            material_type_id = request.POST.get('material_type_id')
            reason = request.POST.get('reason')
            required_tests = request.POST.get('required_tests')
            sample_quantity = request.POST.get('sample_quantity')
            urgency = request.POST.get('urgency', 'normal')
            sampling_location_description = request.POST.get('sampling_location_description')
            
            # Валидация
            project = get_object_or_404(Project, id=project_id)
            material_type = get_object_or_404(MaterialType, id=material_type_id)
            
            # Создаем заявку
            lab_request = LabSampleRequest.objects.create(
                project=project,
                material_type=material_type,
                requested_by=request.user,
                reason=reason,
                required_tests=required_tests,
                sample_quantity=sample_quantity,
                urgency=urgency,
                sampling_location_description=sampling_location_description,
                status='requested'
            )
            
            # Геолокация места отбора
            if 'sampling_latitude' in request.POST and 'sampling_longitude' in request.POST:
                try:
                    lat = float(request.POST.get('sampling_latitude'))
                    lng = float(request.POST.get('sampling_longitude'))
                    lab_request.sampling_location_lat = lat
                    lab_request.sampling_location_lng = lng
                    lab_request.save()
                except (TypeError, ValueError):
                    pass
            
            # Ожидаемая дата результатов
            if request.POST.get('expected_results_date'):
                try:
                    expected_date = datetime.strptime(
                        request.POST.get('expected_results_date'), 
                        '%Y-%m-%d'
                    ).date()
                    lab_request.expected_results_date = expected_date
                    lab_request.save()
                except ValueError:
                    pass
            
            messages.success(request, 'Заявка на лабораторные пробы создана')
            return redirect('inspector:lab_requests')
            
        except Exception as e:
            logger.error(f"Error creating lab request: {str(e)}")
            messages.error(request, 'Ошибка при создании заявки')
    
    # GET запрос
    projects = Project.objects.filter(status__in=['planned', 'active'])
    material_types = MaterialType.objects.all()
    
    context = {
        'projects': projects,
        'material_types': material_types,
        'urgency_levels': LabSampleRequest.URGENCY_CHOICES,
    }
    
    return render(request, 'inspector/create_lab_request.html', context)


@login_required
def lab_request_detail(request, request_id):
    """Детальная страница заявки на лабораторную пробу"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Получаем заявку с связанными объектами
    lab_request = get_object_or_404(
        LabSampleRequest.objects.select_related(
            'project', 'material_type', 'requested_by'
        ),
        id=request_id,
        requested_by=request.user
    )
    
    # Обновление статуса заявки (если нужно)
    if request.method == 'POST' and 'update_status' in request.POST:
        new_status = request.POST.get('status')
        if new_status in dict(LabSampleRequest.STATUS_CHOICES):
            lab_request.status = new_status
            lab_request.save()
            messages.success(request, 'Статус заявки обновлен')
            return redirect('inspector:lab_request_detail', request_id=lab_request.id)
    
    # Обновление примечаний
    elif request.method == 'POST' and 'update_notes' in request.POST:
        inspector_notes = request.POST.get('inspector_notes', '')
        lab_request.inspector_notes = inspector_notes
        lab_request.save()
        messages.success(request, 'Примечания обновлены')
        return redirect('inspector:lab_request_detail', request_id=lab_request.id)
    
    # Обновление результатов
    elif request.method == 'POST' and 'update_results' in request.POST:
        results_summary = request.POST.get('results_summary', '')
        compliance_status = request.POST.get('compliance_status', '')
        lab_request.results_summary = results_summary
        lab_request.compliance_status = compliance_status
        lab_request.save()
        messages.success(request, 'Результаты анализа обновлены')
        return redirect('inspector:lab_request_detail', request_id=lab_request.id)
    
    context = {
        'lab_request': lab_request,
        'status_choices': LabSampleRequest.STATUS_CHOICES,
        'urgency_levels': LabSampleRequest.URGENCY_CHOICES,
    }
    
    return render(request, 'inspector/lab_request_detail.html', context)


@login_required
def project_approvals(request):
    """Одобрения активации проектов"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Фильтры
    status_filter = request.GET.get('status', 'all')
    
    # Базовый запрос
    approvals = ProjectActivationApproval.objects.filter(
        inspector=request.user
    ).select_related('project')
    
    if status_filter != 'all':
        approvals = approvals.filter(status=status_filter)
    
    # Пагинация
    paginator = Paginator(approvals.order_by('-created_at'), 15)
    page = request.GET.get('page')
    approvals_page = paginator.get_page(page)
    
    # Проекты, готовые к активации (без одобрения от этого инспектора)
    projects_awaiting = Project.objects.filter(
        status='planned',
        opening_checklist_completed=True
    ).annotate(
        has_approval=Exists(
            ProjectActivationApproval.objects.filter(
                project=OuterRef('pk'),
                inspector=request.user
            )
        )
    ).filter(has_approval=False)
    
    context = {
        'approvals': approvals_page,
        'projects_awaiting': projects_awaiting,
        'current_status': status_filter,
        'approval_statuses': ProjectActivationApproval.STATUS_CHOICES,
    }
    
    return render(request, 'inspector/project_approvals.html', context)


@login_required
def create_project_approval(request, project_id):
    """Создание одобрения активации проекта"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    project = get_object_or_404(Project, id=project_id, status='planned')
    
    # Проверяем, что уже нет одобрения от этого инспектора
    existing_approval = ProjectActivationApproval.objects.filter(
        project=project,
        inspector=request.user
    ).first()
    
    if existing_approval:
        messages.info(request, 'Одобрение для этого проекта уже существует')
        return redirect('inspector:approval_detail', approval_id=existing_approval.id)
    
    if request.method == 'POST':
        try:
            # Получаем данные формы
            site_preparation_checked = request.POST.get('site_preparation_checked') == 'on'
            safety_measures_checked = request.POST.get('safety_measures_checked') == 'on'
            documentation_checked = request.POST.get('documentation_checked') == 'on'
            environmental_compliance_checked = request.POST.get('environmental_compliance_checked') == 'on'
            
            inspector_conclusion = request.POST.get('inspector_conclusion')
            conditions = request.POST.get('conditions', '')
            rejection_reason = request.POST.get('rejection_reason', '')
            
            status = request.POST.get('status', 'pending')
            inspection_date_str = request.POST.get('inspection_date')
            
            # Парсим дату осмотра
            try:
                inspection_date = datetime.strptime(inspection_date_str, '%Y-%m-%dT%H:%M')
            except:
                inspection_date = timezone.now()
            
            # Создаем одобрение
            approval = ProjectActivationApproval.objects.create(
                project=project,
                inspector=request.user,
                site_preparation_checked=site_preparation_checked,
                safety_measures_checked=safety_measures_checked,
                documentation_checked=documentation_checked,
                environmental_compliance_checked=environmental_compliance_checked,
                inspector_conclusion=inspector_conclusion,
                conditions=conditions,
                rejection_reason=rejection_reason,
                status=status,
                inspection_date=inspection_date
            )
            
            if status in ['approved', 'rejected', 'conditional']:
                approval.decision_date = timezone.now()
                approval.save()
            
            messages.success(request, 'Одобрение активации проекта создано')
            return redirect('inspector:project_approvals')
            
        except Exception as e:
            logger.error(f"Error creating project approval: {str(e)}")
            messages.error(request, 'Ошибка при создании одобрения')
    
    context = {
        'project': project,
        'approval_statuses': ProjectActivationApproval.STATUS_CHOICES,
    }
    
    return render(request, 'inspector/create_project_approval.html', context)


@login_required
def approval_detail(request, approval_id):
    """Детальная страница одобрения активации"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    approval = get_object_or_404(
        ProjectActivationApproval,
        id=approval_id,
        inspector=request.user
    )
    
    # Обновление одобрения
    if request.method == 'POST':
        try:
            approval.site_preparation_checked = request.POST.get('site_preparation_checked') == 'on'
            approval.safety_measures_checked = request.POST.get('safety_measures_checked') == 'on'
            approval.documentation_checked = request.POST.get('documentation_checked') == 'on'
            approval.environmental_compliance_checked = request.POST.get('environmental_compliance_checked') == 'on'
            
            approval.inspector_conclusion = request.POST.get('inspector_conclusion')
            approval.conditions = request.POST.get('conditions', '')
            approval.rejection_reason = request.POST.get('rejection_reason', '')
            
            new_status = request.POST.get('status')
            if new_status != approval.status:
                approval.status = new_status
                if new_status in ['approved', 'rejected', 'conditional']:
                    approval.decision_date = timezone.now()
            
            approval.save()
            messages.success(request, 'Одобрение обновлено')
            
        except Exception as e:
            logger.error(f"Error updating approval: {str(e)}")
            messages.error(request, 'Ошибка при обновлении одобрения')
    
    context = {
        'approval': approval,
        'approval_statuses': ProjectActivationApproval.STATUS_CHOICES,
    }
    
    return render(request, 'inspector/approval_detail.html', context)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def update_violation_status(request):
    """АPI для обновления статуса нарушения"""
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        return JsonResponse({'error': 'Нет доступа'}, status=403)
    
    try:
        data = json.loads(request.body)
        violation_id = data.get('violation_id')
        new_status = data.get('status')
        comment = data.get('comment', '')
        
        violation = get_object_or_404(
            InspectorViolation,
            id=violation_id,
            inspector=request.user
        )
        
        # Обновляем статус
        violation.status = new_status
        
        if new_status == 'verified':
            violation.verified_at = timezone.now()
            violation.inspector_comment = comment
        elif new_status == 'closed':
            violation.inspector_comment = comment
        
        violation.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Статус нарушения изменён на "{violation.get_status_display()}"'
        })
        
    except Exception as e:
        logger.error(f"Error updating violation status: {str(e)}")
        return JsonResponse({'error': 'Ошибка при обновлении статуса'}, status=500)
