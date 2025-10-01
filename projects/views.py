from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Project, ScheduleChange, Work

# API Views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from urban_control_system.permissions import IsConstructionControl, IsForeman, IsInspector
from rest_framework import status
from .models import Project, Work
from documents.models import OpeningChecklistItem, ProjectOpeningChecklist, ChecklistItemCompletion
from accounts.models import Visit
import json
from datetime import timedelta
from django.utils import timezone
from django.db import models


@login_required
def construction_control_dashboard(request):
    """Дашборд строительного контроля с выбором объектов"""
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type in ['construction_control', 'inspector']):
        messages.error(request, 'У вас нет доступа к разделу строительного контроля')
        return redirect('dashboard:dashboard')
    
    # Получаем все доступные проекты для строительного контроля
    if request.user.user_type == 'construction_control':
        # Строительный контроль видит все проекты или только свои
        available_projects = Project.objects.filter(
            models.Q(control_service=request.user) | models.Q(status__in=['planned', 'active'])
        ).select_related('foreman', 'control_service')
    else:
        # Инспекторы видят все активные проекты
        available_projects = Project.objects.filter(
            status__in=['planned', 'active']
        ).select_related('foreman', 'control_service')
    
    # Статистика по проектам
    total_projects = available_projects.count()
    active_projects = available_projects.filter(status='active').count()
    planned_projects = available_projects.filter(status='planned').count()
    delayed_projects = available_projects.filter(
        status='active',
        planned_end_date__lt=timezone.now().date()
    ).count()
    
    # Проекты с замечаниями
    from .models import Comment
    projects_with_comments = available_projects.annotate(
        active_comments_count=models.Count('comments', filter=models.Q(comments__status__in=['pending', 'accepted']))
    ).filter(active_comments_count__gt=0)[:10]
    
    # Недавние работы
    recent_works = Work.objects.filter(
        project__in=available_projects
    ).select_related('project', 'work_type').order_by('-updated_at')[:15]
    
    # Проекты готовые к активации (с наступающей или прошедшей датой)
    today = timezone.now().date()
    if request.user.user_type == 'construction_control':
        projects_to_activate = available_projects.filter(
            status='planned',
            planned_start_date__lte=today,
            control_service=request.user
        )
    else:
        projects_to_activate = Project.objects.none()
    
    # Проекты для карты с GeoJSON координатами
    projects_for_map = []
    for project in available_projects:
        if project.coordinates:
            try:
                coords_data = json.loads(project.coordinates)
                projects_for_map.append({
                    'id': project.id,
                    'name': project.name,
                    'address': project.address,
                    'status': project.status,
                    'completion': project.completion_percentage,
                    'coordinates': coords_data
                })
            except (json.JSONDecodeError, ValueError):
                continue
    
    context = {
        'user': request.user,
        'available_projects': available_projects.order_by('-updated_at')[:20],
        'projects_to_activate': projects_to_activate,
        'projects_for_map': json.dumps(projects_for_map),
        'planned_projects_count': planned_projects,
        'stats': {
            'total_projects': total_projects,
            'active_projects': active_projects,
            'planned_projects': planned_projects,
            'delayed_projects': delayed_projects,
        },
        'projects_with_comments': projects_with_comments,
        'recent_works': recent_works,
    }
    
    return render(request, 'projects/construction_control_dashboard.html', context)


def _parse_wkt_polygon(wkt_str):
    """Парсит WKT строку полигона и возвращает список координат"""
    import re
    try:
        # Ищем координаты в WKT формате: POLYGON ((lng lat,lng lat,...))
        match = re.search(r'POLYGON\s*\(\(([^)]+)\)\)', wkt_str)
        if match:
            coords_str = match.group(1)
            coords = []
            for pair in coords_str.split(','):
                parts = pair.strip().split()
                if len(parts) >= 2:
                    lng, lat = float(parts[0]), float(parts[1])
                    coords.append([lng, lat])
            return coords
    except Exception as e:
        print(f'Ошибка парсинга WKT: {e}')
    return []

def _parse_polygon_coords(coordinates_str):
    """Парсит строку полигона (JSON или WKT) и возвращает список точек [[lng, lat], ...]"""
    if not coordinates_str:
        return []
    
    # Сначала пробуем WKT формат
    if coordinates_str.strip().upper().startswith('POLYGON'):
        return _parse_wkt_polygon(coordinates_str)
    
    # Потом пробуем JSON формат
    try:
        data = json.loads(coordinates_str)
        # Ожидаем GeoJSON с type=Polygon
        if isinstance(data, dict) and data.get('type') == 'Polygon':
            return data.get('coordinates', [[]])[0]
        # Если это Feature
        if isinstance(data, dict) and data.get('type') == 'Feature':
            geom = data.get('geometry', {})
            if geom.get('type') == 'Polygon':
                return geom.get('coordinates', [[]])[0]
    except Exception:
        pass
    return []


def _point_in_polygon(lng, lat, polygon):
    """Проверка, лежит ли точка в многоугольнике (ray casting)"""
    x = float(lng)
    y = float(lat)
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) if (yj - yi) != 0 else 1e-9) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def _require_recent_visit(user, project, max_age_minutes=120):
    """Проверяет, что у пользователя есть недавний визит в границах полигона проекта"""
    visit = Visit.objects.filter(user=user, project=project).order_by('-created_at').first()
    if not visit:
        return False, 'Не зафиксировано посещение объекта'
    if timezone.now() - visit.created_at > timedelta(minutes=max_age_minutes):
        return False, 'Визит просрочен, создайте новую отметку посещения'
    polygon = _parse_polygon_coords(project.coordinates or '')
    if polygon:
        if not _point_in_polygon(float(visit.longitude), float(visit.latitude), polygon):
            return False, 'Геопозиция вне полигона объекта'
    # Если полигона нет, не блокируем
    return True, None


class ProjectListAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        projects = Project.objects.select_related('control_service', 'foreman').all()
        data = []
        for p in projects:
            data.append({
                'id': p.id,
                'name': p.name,
                'address': p.address,
                'status': p.status,
                'planned_start_date': p.planned_start_date,
                'planned_end_date': p.planned_end_date,
                'completion_percentage': p.completion_percentage,
            })
        return Response({'results': data})

class ProjectDetailAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        p = get_object_or_404(Project, pk=pk)
        data = {
            'id': p.id,
            'name': p.name,
            'address': p.address,
            'status': p.status,
            'coordinates': p.coordinates,
            'planned_start_date': p.planned_start_date,
            'planned_end_date': p.planned_end_date,
            'actual_start_date': p.actual_start_date,
            'actual_end_date': p.actual_end_date,
            'description': p.description,
            'completion_percentage': p.completion_percentage,
        }
        return Response(data)

class ProjectActivateAPI(APIView):
    """Активация объекта: создание чек-листа и смена статуса"""
    permission_classes = [IsAuthenticated, IsConstructionControl]
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if request.user.user_type != 'construction_control':
            return Response({'detail': 'Недостаточно прав'}, status=status.HTTP_403_FORBIDDEN)
        if project.status != 'planned':
            return Response({'detail': 'Проект уже активирован или в другом статусе'}, status=status.HTTP_400_BAD_REQUEST)
        # Проверка посещения
        ok, msg = _require_recent_visit(request.user, project)
        if not ok:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        project.status = 'active'
        project.actual_start_date = timezone.now().date()
        project.save()
        # Создаем чек-лист
        if not hasattr(project, 'opening_checklist'):
            checklist = ProjectOpeningChecklist.objects.create(project=project, created_by=request.user)
            items = OpeningChecklistItem.objects.all().order_by('order')
            for it in items:
                ChecklistItemCompletion.objects.create(checklist=checklist, checklist_item=it, is_completed=False)
        return Response({'status': 'ok', 'project_id': project.id, 'new_status': project.status})

class WorkReportCompletionAPI(APIView):
    permission_classes = [IsAuthenticated, IsForeman]
    def post(self, request, pk):
        work = get_object_or_404(Work, pk=pk)
        project = work.project
        if request.user.user_type != 'foreman':
            return Response({'detail': 'Только прораб может отмечать выполнение работ'}, status=status.HTTP_403_FORBIDDEN)
        # Проверка посещения
        ok, msg = _require_recent_visit(request.user, project)
        if not ok:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        work.reported_by_foreman = True
        if work.status == 'not_started':
            work.status = 'in_progress'
        # опционально финализация
        if request.data.get('complete'):
            work.status = 'completed'
            work.actual_end_date = timezone.now().date()
        work.save()
        return Response({'status': 'ok', 'work_id': work.id, 'new_status': work.status})

class WorkSpecListAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        from .models import WorkSpecRow
        project = get_object_or_404(Project, pk=pk)
        rows = WorkSpecRow.objects.filter(project=project).order_by('order','name')
        data = [
            {
                'id': r.id,
                'code': r.code,
                'name': r.name,
                'unit': r.unit,
                'planned_volume': float(r.planned_volume) if r.planned_volume is not None else None,
            }
            for r in rows
        ]
        return Response({'results': data})

class ProjectKPIAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        from .models import WorkSpecRow, Work
        from materials.models import MaterialDelivery
        project = get_object_or_404(Project, pk=pk)
        planned_total = sum([float(r.planned_volume) for r in WorkSpecRow.objects.filter(project=project) if r.planned_volume])
        delivered_total = 0.0
        for d in MaterialDelivery.objects.filter(project=project):
            try:
                delivered_total += float(d.quantity)
            except Exception:
                pass
        works = Work.objects.filter(project=project)
        delayed = sum([1 for w in works if w.is_delayed])
        data = {
            'project_id': project.id,
            'completion_percentage': project.completion_percentage,
            'planned_total_volume': planned_total,
            'delivered_total_quantity': delivered_total,
            'delayed_works': delayed,
            'works_count': works.count(),
        }
        return Response(data)

class MaterialsExportCSVAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        import csv
        from io import StringIO
        from materials.models import MaterialDelivery
        project = get_object_or_404(Project, pk=pk)
        deliveries = MaterialDelivery.objects.filter(project=project).select_related('material_type','spec_row')
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Project','Material','Quantity','Unit','Status','Delivery Date','Spec Code','Spec Name'])
        for d in deliveries:
            writer.writerow([
                project.name,
                d.material_type.name,
                d.quantity,
                d.material_type.unit,
                d.get_status_display(),
                d.delivery_date.isoformat() if d.delivery_date else '',
                d.spec_row.code if d.spec_row else '',
                d.spec_row.name if d.spec_row else '',
            ])
        from django.http import HttpResponse
        resp = HttpResponse(output.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="materials_{project.id}.csv"'
        return resp

class WorksExportCSVAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        import csv
        from io import StringIO
        from .models import Work
        project = get_object_or_404(Project, pk=pk)
        works = Work.objects.filter(project=project).select_related('work_type')
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Work Name','Type Code','Planned Start','Planned End','Actual End','Status','Volume','Unit'])
        for w in works:
            writer.writerow([
                w.name,
                w.work_type.code,
                w.planned_start_date,
                w.planned_end_date,
                w.actual_end_date or '',
                w.get_status_display(),
                w.volume,
                w.unit,
            ])
        from django.http import HttpResponse
        resp = HttpResponse(output.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="works_{project.id}.csv"'
        return resp

@login_required(login_url='login')
def work_schedule(request):
    """Сетевой график работ - доступен только для строительного контроля"""
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        from django.contrib import messages
        messages.error(request, 'Доступ к сетевому графику работ разрешен только строительному контролю')
        return redirect('/')
    
    # Получаем все проекты с их данными сетевого графика
    projects = Project.objects.select_related('control_service', 'foreman').all()
    
    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Фильтрация по конкретному проекту
    project_filter = request.GET.get('project')
    selected_project = None
    if project_filter:
        try:
            selected_project = Project.objects.get(id=project_filter)
            projects = projects.filter(id=project_filter)
        except Project.DoesNotExist:
            pass
    
    # Подготавливаем данные для отображения
    projects_data = []
    all_works = []
    
    for project in projects:
        # Получаем данные сетевого графика для проекта
        schedule_data = project.work_schedule_data
        
        # Получаем критический путь
        critical_path = project.get_critical_path()
        critical_work_ids = [w.id for w in critical_path]
        
        # Статистика по проекту
        total_works = len(schedule_data)
        completed_works = len([w for w in schedule_data if w['status'] in ['completed', 'verified']])
        delayed_works = len([w for w in schedule_data if w['is_delayed']])
        
        project_info = {
            'project': project,
            'schedule_data': schedule_data,
            'critical_path_ids': critical_work_ids,
            'stats': {
                'total_works': total_works,
                'completed_works': completed_works,
                'delayed_works': delayed_works,
                'completion_percentage': project.completion_percentage,
                'readiness_score': project.readiness_score,
            },
            'work_types_summary': project.work_types_summary,
        }
        
        projects_data.append(project_info)
        all_works.extend(schedule_data)
    
    # Сортируем работы по дате начала
    all_works.sort(key=lambda x: x['planned_start'] if x['planned_start'] else timezone.now().date())
    
    # Общая статистика
    total_all_works = len(all_works)
    completed_all_works = len([w for w in all_works if w['status'] in ['completed', 'verified']])
    delayed_all_works = len([w for w in all_works if w['is_delayed']])
    
    # Проверяем проекты, которые нужно активировать
    from datetime import date
    today = date.today()
    projects_to_activate = projects.filter(
        status='planned',
        planned_start_date__lte=today
    ).count()
    
    overall_stats = {
        'total_projects': projects.count(),
        'total_works': total_all_works,
        'completed_works': completed_all_works,
        'delayed_works': delayed_all_works,
        'projects_to_activate': projects_to_activate,
        'overall_completion': int((completed_all_works / total_all_works * 100)) if total_all_works > 0 else 0,
    }
    
    # Получаем изменения в графике
    schedule_changes = ScheduleChange.objects.select_related(
        'work__project', 'requested_by', 'reviewed_by'
    ).order_by('-created_at')[:20]
    
    context = {
        'projects_data': projects_data,
        'selected_project': selected_project,
        'all_projects': Project.objects.all().order_by('name'),
        'all_works': all_works,
        'overall_stats': overall_stats,
        'schedule_changes': schedule_changes,
        'status_filter': status_filter,
        'user': request.user,
        'status_counts': {
            'active': Project.objects.filter(status='active').count(),
            'completed': Project.objects.filter(status='completed').count(),
            'suspended': Project.objects.filter(status='suspended').count(),
            'planned': Project.objects.filter(status='planned').count(),
        },
    }
    
    return render(request, 'projects/work_schedule.html', context)

@login_required(login_url='login')
def project_activation(request, project_id):
    """Процесс активации объекта строительным контролем"""
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        from django.contrib import messages
        messages.error(request, 'Доступ к активации объектов разрешен только строительному контролю')
        return redirect('projects:project_detail', project_id=project_id)
    
    project = get_object_or_404(Project, id=project_id)
    from documents.models import ProjectOpeningChecklist, ChecklistItemCompletion, OpeningChecklistItem
    from accounts.models import User
    from django.contrib import messages
    import json
    
    # Получаем список прорабов
    foremen = User.objects.filter(user_type='foreman')
    
    # Получаем или создаем чек-лист
    checklist = None
    checklist_items = []
    try:
        checklist = ProjectOpeningChecklist.objects.get(project=project)
        checklist_items = ChecklistItemCompletion.objects.filter(
            checklist=checklist
        ).select_related('checklist_item').order_by('checklist_item__order')
    except ProjectOpeningChecklist.DoesNotExist:
        pass
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'assign_foreman':
            # Назначаем прораба
            foreman_id = request.POST.get('foreman_id')
            if foreman_id:
                try:
                    foreman = User.objects.get(id=foreman_id, user_type='foreman')
                    old_foreman = project.foreman
                    project.foreman = foreman
                    project.save()
                    
                    # Создаем событие
                    from .models import log_foreman_assignment
                    log_foreman_assignment(project, request.user, foreman, is_new=(old_foreman is None))
                    
                    messages.success(request, f'Прораб {foreman.get_full_name()} назначен на объект')
                except User.DoesNotExist:
                    messages.error(request, 'Прораб не найден')
            else:
                messages.error(request, 'Необходимо выбрать прораба')
        
        elif action == 'create_checklist':
            # Создаем чек-лист
            if not checklist:
                checklist = ProjectOpeningChecklist.objects.create(
                    project=project,
                    created_by=request.user
                )
                # Создаем элементы чек-листа
                items = OpeningChecklistItem.objects.all().order_by('order')
                for item in items:
                    ChecklistItemCompletion.objects.create(
                        checklist=checklist,
                        checklist_item=item,
                        is_completed=False
                    )
                messages.success(request, 'Чек-лист открытия объекта создан')
                return redirect('projects:project_activation', project_id=project.id)
        
        elif action == 'update_checklist':
            # Обновляем чек-лист
            if checklist:
                updated_items = 0
                for completion in checklist_items:
                    item_id = completion.checklist_item.id
                    is_completed = request.POST.get(f'item_{item_id}') == 'on'
                    notes = request.POST.get(f'notes_{item_id}', '')
                    
                    if completion.is_completed != is_completed or completion.completion_notes != notes:
                        completion.is_completed = is_completed
                        completion.completion_notes = notes
                        completion.completed_by = request.user if is_completed else None
                        completion.completed_at = timezone.now() if is_completed else None
                        completion.save()
                        updated_items += 1
                
                # Проверяем завершенность чек-листа
                total_items = checklist_items.count()
                completed_items = checklist_items.filter(is_completed=True).count()
                
                if total_items > 0 and completed_items == total_items:
                    checklist.is_completed = True
                    checklist.completion_date = timezone.now()
                    checklist.save()
                    project.opening_checklist_completed = True
                    project.save()
                    messages.success(request, 'Чек-лист полностью заполнен!')
                elif updated_items > 0:
                    messages.success(request, f'Обновлено пунктов: {updated_items}')
        
        elif action == 'upload_act':
            # Загружаем акт открытия
            act_file = request.FILES.get('opening_act')
            if act_file:
                project.opening_act = act_file
                project.save()
                messages.success(request, 'Акт открытия объекта загружен')
            else:
                messages.error(request, 'Не выбран файл для загрузки')
        
        elif action == 'activate':
            # Активируем проект
            if project.status != 'planned':
                messages.error(request, 'Объект уже активирован или находится в другом статусе')
            elif not project.foreman:
                messages.error(request, 'Необходимо назначить прораба')
            elif not project.opening_checklist_completed:
                messages.error(request, 'Необходимо завершить заполнение чек-листа')
            else:
                # Активируем
                old_status = project.status
                project.status = 'active'
                project.actual_start_date = timezone.now().date()
                project.control_service = request.user
                project.save()
                
                # Создаем событие об активации
                from .models import log_status_change
                log_status_change(project, request.user, old_status, 'active')
                
                # Отправляем уведомление инспекторам
                inspectors = User.objects.filter(user_type='inspector')
                for inspector in inspectors:
                    # Здесь можно добавить отправку уведомлений/email
                    pass
                
                messages.success(
                    request, 
                    f'Объект “{project.name}” успешно активирован! '
                    f'Ответственный прораб: {project.foreman.get_full_name()}'
                )
                return redirect('projects:project_detail', project_id=project.id)
        
        return redirect('projects:project_activation', project_id=project.id)
    
    # Обновляем данные чек-листа после POST-запроса
    if checklist:
        checklist_items = ChecklistItemCompletion.objects.filter(
            checklist=checklist
        ).select_related('checklist_item').order_by('checklist_item__order')
    
    # Проверяем состояние активации
    activation_status = {
        'can_activate': (
            project.status == 'planned' and 
            project.foreman and 
            project.opening_checklist_completed
        ),
        'has_foreman': bool(project.foreman),
        'has_checklist': bool(checklist),
        'checklist_completed': project.opening_checklist_completed,
        'has_opening_act': bool(project.opening_act),
        'is_already_active': project.status != 'planned'
    }
    
    context = {
        'project': project,
        'foremen': foremen,
        'checklist': checklist,
        'checklist_items': checklist_items,
        'activation_status': activation_status,
        'user': request.user,
    }
    
    return render(request, 'projects/project_activation.html', context)

class ProjectWorksAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        works = Work.objects.filter(project=project).select_related('work_type').order_by('planned_start_date')
        data = []
        for w in works:
            data.append({
                'id': w.id,
                'name': w.name,
                'type_code': w.work_type.code,
                'planned_start_date': w.planned_start_date.isoformat() if w.planned_start_date else None,
                'planned_end_date': w.planned_end_date.isoformat() if w.planned_end_date else None,
                'actual_start_date': w.actual_start_date.isoformat() if w.actual_start_date else None,
                'actual_end_date': w.actual_end_date.isoformat() if w.actual_end_date else None,
                'status': w.status,
            })
        return Response({'results': data})

class ScheduleChangeCreateAPI(APIView):
    permission_classes = [IsAuthenticated, IsForeman]
    def post(self, request, pk):
        from datetime import datetime
        work = get_object_or_404(Work, pk=pk)
        project = work.project
        ok, msg = _require_recent_visit(request.user, project)
        if not ok:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        try:
            new_start = request.data.get('new_start_date')
            new_end = request.data.get('new_end_date')
            reason = request.data.get('reason','Изменение графика')
            if not (new_start and new_end):
                return Response({'detail': 'new_start_date и new_end_date обязательны'}, status=status.HTTP_400_BAD_REQUEST)
            new_start_dt = datetime.fromisoformat(new_start).date()
            new_end_dt = datetime.fromisoformat(new_end).date()
        except Exception:
            return Response({'detail': 'Неверный формат дат (используйте YYYY-MM-DD)'}, status=status.HTTP_400_BAD_REQUEST)
        sc = ScheduleChange.objects.create(
            work=work,
            previous_start_date=work.planned_start_date,
            previous_end_date=work.planned_end_date,
            new_start_date=new_start_dt,
            new_end_date=new_end_dt,
            reason=reason,
            requested_by=request.user,
            status='pending'
        )
        return Response({'status':'ok','schedule_change_id': sc.id})

class ScheduleChangeReviewAPI(APIView):
    permission_classes = [IsAuthenticated, IsConstructionControl]
    def post(self, request, pk):
        sc = get_object_or_404(ScheduleChange, pk=pk)
        project = sc.work.project
        ok, msg = _require_recent_visit(request.user, project)
        if not ok:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        decision = request.data.get('decision')  # 'approved' or 'rejected'
        comment = request.data.get('comment','')
        if decision not in ['approved','rejected']:
            return Response({'detail': 'decision должен быть approved или rejected'}, status=status.HTTP_400_BAD_REQUEST)
        sc.status = decision
        sc.reviewed_by = request.user
        sc.comment = comment
        sc.save()
        if decision == 'approved':
            sc.apply_changes()
        return Response({'status':'ok'})

class WorkVerifyAPI(APIView):
    permission_classes = [IsAuthenticated, IsConstructionControl]
    def post(self, request, pk):
        work = get_object_or_404(Work, pk=pk)
        project = work.project
        if request.user.user_type != 'construction_control':
            return Response({'detail': 'Только стройконтроль может верифицировать работы'}, status=status.HTTP_403_FORBIDDEN)
        ok, msg = _require_recent_visit(request.user, project)
        if not ok:
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        work.verified_by_control = True
        work.status = 'verified'
        if not work.actual_end_date:
            work.actual_end_date = timezone.now().date()
        work.save()
        return Response({'status': 'ok', 'work_id': work.id, 'new_status': work.status})
def test_js(request):
    """Тестовая страница для проверки JavaScript без авторизации"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Тест JavaScript</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            'moscow-blue': '#003366',
                            'moscow-red': '#DC143C', 
                            'moscow-gold': '#FFD700',
                            'moscow-green': '#228B22',
                        }
                    }
                }
            }
        </script>
    </head>
    <body class="bg-gray-50 p-8">
        <div class="max-w-4xl mx-auto">
            <h1 class="text-3xl font-bold text-moscow-blue mb-6">Тест JavaScript</h1>
            
            <div class="bg-white p-6 rounded-lg shadow mb-6">
                <h2 class="text-xl font-semibold mb-4">Статус</h2>
                <div id="status" class="text-green-600 font-medium">JavaScript загружен успешно! ✅</div>
            </div>
            
            <div class="bg-white p-6 rounded-lg shadow mb-6">
                <h2 class="text-xl font-semibold mb-4">Тест MapBox</h2>
                <div id="map-container" class="border rounded-lg">
                    <div id="map-loading" class="flex items-center justify-center h-64 bg-gray-100">
                        <div class="text-center">
                            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-moscow-blue mx-auto mb-2"></div>
                            <p class="text-gray-600">Загрузка карты...</p>
                        </div>
                    </div>
                    <div id="map" class="h-64 hidden"></div>
                </div>
            </div>
        </div>
        
        <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
        <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
        
        <script>
            console.log('Тест JavaScript запущен');
            
            // Проверка доступности MapBox
            if (typeof mapboxgl !== 'undefined') {
                console.log('MapBox GL доступен');
                document.getElementById('status').innerHTML += '<br/>MapBox GL загружен ✅';
                
                try {
                    // Инициализация тестовой карты
                    const map = new mapboxgl.Map({
                        container: 'map',
                        style: {
                            version: 8,
                            sources: {
                                'raster-tiles': {
                                    type: 'raster',
                                    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                                    tileSize: 256
                                }
                            },
                            layers: [{
                                id: 'simple-tiles',
                                type: 'raster',
                                source: 'raster-tiles'
                            }]
                        },
                        center: [37.6173, 55.7558],
                        zoom: 10
                    });
                    
                    map.on('load', function() {
                        console.log('Карта загружена!');
                        document.getElementById('map-loading').classList.add('hidden');
                        document.getElementById('map').classList.remove('hidden');
                        document.getElementById('status').innerHTML += '<br/>Карта инициализирована ✅';
                        
                        // Добавляем маркер
                        new mapboxgl.Marker()
                            .setLngLat([37.6173, 55.7558])
                            .addTo(map);
                    });
                    
                    map.on('error', function(e) {
                        console.error('Ошибка карты:', e);
                        document.getElementById('status').innerHTML += '<br/>❌ Ошибка карты: ' + e.error.message;
                    });
                    
                } catch (error) {
                    console.error('Ошибка инициализации:', error);
                    document.getElementById('status').innerHTML += '<br/>❌ Ошибка инициализации: ' + error.message;
                }
            } else {
                document.getElementById('status').innerHTML += '<br/>❌ MapBox GL недоступен';
            }
        </script>
    </body>
    </html>
    """
    from django.http import HttpResponse

# Frontend Views
@login_required(login_url='login')
def project_list(request):
    """Страница списка проектов с разным интерфейсом для ролей"""
    projects = Project.objects.select_related('control_service', 'foreman').all()
    
    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        projects = projects.filter(status=status_filter)
    
    # Фильтрация по ролям
    if hasattr(request.user, 'user_type') and request.user.user_type == 'foreman':
        # Прораб видит только назначенные ему проекты
        projects = projects.filter(foreman=request.user).select_related('activation')
        
        context = {
            'projects': projects,
            'user': request.user,
            'is_foreman': True,
            'total_count': projects.count(),
            'status_counts': {
                'active': projects.filter(status='active').count(),
                'completed': projects.filter(status='completed').count(),
                'suspended': projects.filter(status='suspended').count(),
                'planned': projects.filter(status='planned').count(),
            },
        }
        return render(request, 'projects/foreman_list.html', context)
    
    # Для строительного контроля показываем только его объекты
    elif hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control':
        from datetime import date
        from django.db.models import Q
        # Показываем объекты где пользователь ответственный + новые объекты для активации
        today = date.today()
        
        projects = projects.filter(
            Q(control_service=request.user) |  # Объекты под контролем
            Q(status='planned', planned_start_date__lte=today) |  # Объекты готовые к активации
            Q(status='planned', control_service__isnull=True)  # Новые объекты без ответственного
        )
        
        # Расширенные данные для карточек
        projects_data = []
        for project in projects:
            # Получаем состав работ
            works = project.works.select_related('work_type').all()[:5]  # Первые 5 работ
            work_types_summary = project.work_types_summary
            schedule_data = project.work_schedule_data[:3]  # Первые 3 работы в графике
            
            # Проверяем необходимость активации
            needs_activation = (
                project.status == 'planned' and 
                project.planned_start_date <= today
            )
            
            projects_data.append({
                'project': project,
                'works': works,
                'work_types_summary': work_types_summary,
                'schedule_preview': schedule_data,
                'needs_activation': needs_activation,
                'can_edit': project.control_service == request.user or project.control_service is None,
            })
        
        context = {
            'projects_data': projects_data,
            'user': request.user,
            'is_construction_control': True,
            'total_count': projects.count(),
            'status_counts': {
                'active': projects.filter(status='active').count(),
                'completed': projects.filter(status='completed').count(),
                'suspended': projects.filter(status='suspended').count(),
                'planned': projects.filter(status='planned').count(),
            },
            # 'all_projects': projects.order_by('name'),  # Теперь предоставляется контекст-процессором
        }
        # Переключаем на современный дашборд по умолчанию
        modern = request.GET.get('modern', '1')  # По умолчанию современный
        if modern == '1':
            return render(request, 'projects/modern_construction_control.html', context)
        else:
            return render(request, 'projects/construction_control_dashboard.html', context)
    
    # Для остальных ролей - обычный список
    context = {
        'projects': projects,
        'user': request.user,
        'total_count': Project.objects.count(),
        'status_counts': {
            'active': Project.objects.filter(status='active').count(),
            'completed': Project.objects.filter(status='completed').count(),
            'suspended': Project.objects.filter(status='suspended').count(),
            'planned': Project.objects.filter(status='planned').count(),
        },
        # 'all_projects': Project.objects.order_by('name'),  # Теперь предоставляется контекст-процессором
        # 'selected_project': None,  # Теперь определяется автоматически
    }
    return render(request, 'projects/list.html', context)

@login_required(login_url='login')
def project_detail(request, project_id):
    """Страница детального просмотра проекта"""
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        from materials.models import MaterialDelivery
    except ImportError:
        logger.warning("MaterialDelivery model not available")
        MaterialDelivery = None
        
    try:
        from violations.models import Violation
    except ImportError:
        logger.warning("Violation model not available")
        Violation = None
        
    from .models import Work, ScheduleChange, ProjectEvent
    
    # Получаем проект или 404
    project = get_object_or_404(Project, id=project_id)
    
    
    # Получаем связанные данные (безопасно)
    materials = []
    materials_queryset = None
    materials_count = 0
    materials_delivered_count = 0
    
    if MaterialDelivery:
        try:
            materials_queryset = MaterialDelivery.objects.filter(project=project).select_related('material_type')
            materials_count = materials_queryset.count()  # Подсчитываем сразу
            materials_delivered_count = materials_queryset.filter(status__in=['delivered', 'accepted']).count()
            materials = list(materials_queryset.order_by('-delivery_date')[:10])  # Преобразуем в список
        except Exception as e:
            logger.error(f"Error fetching materials: {e}")
            materials = []
    
    # Получаем комментарии (замечания) по проекту сначала
    comments = []
    comments_count = 0
    open_comments_count = 0
    
    try:
        from .models import Comment
        comments = Comment.objects.filter(
            project=project
        ).select_related('created_by', 'assigned_to', 'work').order_by('-created_at')[:10]
        comments_count = Comment.objects.filter(project=project).count()
        open_comments_count = Comment.objects.filter(
            project=project, 
            status__in=['pending', 'accepted']
        ).count()
    except Exception as e:
        logger.error(f"Error fetching comments: {e}")
        comments = []
        comments_count = 0
        open_comments_count = 0
    
    # Получаем нарушения инспектора
    violations = []
    violations_count = 0
    violations_open_count = 0
    
    try:
        from inspector.models import InspectorViolation
        
        inspector_violations = InspectorViolation.objects.filter(
            project=project
        ).select_related('inspector', 'assigned_to', 'violation_type', 'violation_classifier')
        
        violations_count = inspector_violations.count()
        violations_open_count = inspector_violations.filter(
            status__in=['detected', 'notified', 'in_correction']
        ).count()
        
        # Преобразуем в список для отображения
        violations = list(inspector_violations.order_by('-detected_at')[:10])
        
    except Exception as e:
        logger.error(f"Error fetching inspector violations: {e}")
        violations = []
    
    # Дополнительно получаем старые нарушения, если они есть
    if Violation:
        try:
            old_violations = Violation.objects.filter(project=project).select_related('created_by')
            violations_count += old_violations.count()
            violations_open_count += old_violations.filter(status__in=['open', 'in_progress']).count()
            violations.extend(list(old_violations.order_by('-detected_at')[:5]))
        except Exception as e:
            logger.error(f"Error fetching old violations: {e}")

    # Работы по проекту
    works = []
    try:
        works = Work.objects.filter(project=project).select_related('work_type').order_by('planned_start_date')[:20]
    except Exception as e:
        logger.error(f"Error fetching works: {e}")
        works = []
    
    # Подготавливаем данные для карты
    project_for_map = None
    
    logger.info(f'🗺️ Подготовка данных карты для проекта {project.id}: {project.name}')
    logger.info(f'📍 Координаты: {project.coordinates[:100] if project.coordinates else "Отсутствуют"}')
    
    if project.coordinates:
        try:
            # Используем метод модели для преобразования WKT в JSON
            coordinates_data = project.get_coordinates_json()
            if coordinates_data:
                logger.info(f'✅ Координаты успешно преобразованы')
                logger.info(f'🔍 Тип: {coordinates_data.get("type", "неизвестный")}')
                
                project_for_map = {
                    'id': project.id,
                    'name': project.name,
                    'address': project.address,
                    'status': project.status,
                    'coordinates': coordinates_data,
                    'completion': project.completion_percentage,
                    'control_service': project.control_service.get_full_name() if project.control_service else None,
                    'foreman': project.foreman.get_full_name() if project.foreman else None,
                }
                logger.info(f'✅ Объект для карты создан: {project_for_map["name"]}')
            else:
                logger.warning(f'⚠️ Не удалось преобразовать координаты')
            
        except Exception as e:
            logger.error(f'❌ Ошибка обработки координат: {e}')
    else:
        logger.warning(f'⚠️ Координаты отсутствуют для проекта {project.id}')
    
    # Статистика по проекту (уже подсчитана выше)
    
    # Собираем статистику из уже подсчитанных значений
    stats = {
        'materials_total': materials_count,
        'materials_delivered': materials_delivered_count,
        'violations_total': violations_count + comments_count,
        'violations_open': violations_open_count + open_comments_count,
        'completion': project.completion_percentage,
    }
    
    # all_projects теперь предоставляется контекст-процессором
    
    # Подготавливаем данные для карты в JSON формате
    map_data_json = json.dumps([project_for_map] if project_for_map else [])
    
    logger.info(f'📊 Финальные данные для карты: {len([project_for_map] if project_for_map else [])} объект(ов)')
    if project_for_map:
        logger.info(f'📍 Передаём на карту: {project_for_map["name"]} (статус: {project_for_map["status"]})')
    else:
        logger.warning('⚠️ На карту не передаём никакие данные!')
    
    # Получаем состав работ (спецификацию)
    work_specification = project.work_specification
    
    # Получаем данные сетевого графика
    schedule_data = project.work_schedule_data
    
    # Сводка по типам работ
    work_types_summary = project.work_types_summary
    
    # JSON данные для визуализации сетевого графика
    schedule_json = json.dumps(schedule_data) if schedule_data else '[]'
    
    # Получаем электронную спецификацию из Excel файлов
    electronic_specification = None
    specification_items = []
    try:
        if hasattr(project, 'electronic_specification'):
            electronic_specification = project.electronic_specification
            specification_items = electronic_specification.items.all().order_by('order', 'name')[:50]
    except Exception as e:
        logger.error(f"Error fetching electronic specification: {e}")
    
    # Получаем сетевой график из Excel файлов  
    network_schedule = None
    network_tasks = []
    critical_path_tasks = []
    try:
        if hasattr(project, 'network_schedule'):
            network_schedule = project.network_schedule
            network_tasks = network_schedule.tasks.all().order_by('early_start', 'order')[:50]
            critical_path_tasks = network_tasks.filter(is_critical=True)
    except Exception as e:
        logger.error(f"Error fetching network schedule: {e}")
    
    # Подготавливаем данные для диаграммы Ганта
    gantt_data = []
    if network_tasks:
        for task in network_tasks:
            gantt_data.append({
                'id': task.task_id,
                'name': task.name,
                'start': task.early_start,
                'duration': task.duration_days,
                'critical': task.is_critical,
                'resources': task.get_resource_list(),
                'predecessors': task.get_predecessor_list(),
            })
    
    gantt_json = json.dumps(gantt_data)
    
    # Объединяем комментарии и нарушения для отображения
    all_violations = list(violations) + list(comments)
    all_violations.sort(key=lambda x: x.created_at if hasattr(x, 'created_at') else x.detected_at, reverse=True)
    
    # Получаем события проекта
    events = ProjectEvent.objects.filter(
        project=project
    ).select_related('user').order_by('-created_at')[:20]
    
    context = {
        'project': project,
        'materials': materials,
        'violations': all_violations,
        'comments': comments,
        'open_violations_count': violations_open_count + open_comments_count,
        'comments_count': comments_count,
        'works': works,
        'work_specification': work_specification,
        'work_types_summary': work_types_summary,
        'schedule_data': schedule_data,
        'schedule_json': schedule_json,
        'stats': stats,
        'project_for_map': map_data_json,
        'user': request.user,
        # Новые данные из Excel файлов
        'electronic_specification': electronic_specification,
        'specification_items': specification_items,
        'network_schedule': network_schedule, 
        'network_tasks': network_tasks,
        'critical_path_tasks': critical_path_tasks,
        'gantt_data': gantt_data,
        'gantt_json': gantt_json,
        # События проекта
        'events': events,
        # all_projects и selected_project теперь предоставляются контекст-процессором
    }
    
    logger.info(f'🚀 Отправляем контекст на шаблон projects/detail.html')
    return render(request, 'projects/detail.html', context)


# ========== Views для системы замечаний и нарушений ==========

@login_required(login_url='login')
def comments_list(request):
    """Список всех нарушений и замечаний"""
    from .models import Comment
    from inspector.models import InspectorViolation
    from django.db.models import Q
    from itertools import chain
    from operator import attrgetter
    
    # Создаем объединенный список нарушений и замечаний
    
    # Получаем замечания
    comments = Comment.objects.select_related('project', 'work', 'created_by', 'assigned_to').all()
    
    # Получаем нарушения инспектора
    violations = InspectorViolation.objects.select_related(
        'project', 'inspector', 'assigned_to', 'violation_type', 'violation_classifier'
    ).all()
    
    # Фильтруем в зависимости от роли
    if hasattr(request.user, 'user_type') and request.user.user_type == 'foreman':
        # Для прораба - только назначенные ему и по его проектам
        comments = comments.filter(
            Q(assigned_to=request.user) | Q(project__foreman=request.user)
        )
        violations = violations.filter(
            Q(assigned_to=request.user) | Q(project__foreman=request.user)
        )
    
    elif hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control':
        # Для строительного контроля
        comments = comments.filter(
            Q(created_by=request.user) | Q(project__control_service=request.user)
        )
        violations = violations.filter(
            Q(project__control_service=request.user)
        )
    
    # Фильтры
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    project_filter = request.GET.get('project')
    
    # Применяем фильтры к замечаниям
    if status_filter:
        comments = comments.filter(status=status_filter)
    if priority_filter:
        comments = comments.filter(priority=priority_filter)
    if project_filter:
        comments = comments.filter(project_id=project_filter)
    
    # Применяем фильтры к нарушениям (с маппингом статусов)
    if status_filter:
        # Маппим статусы замечаний на статусы нарушений
        violation_status_mapping = {
            'pending': ['detected', 'notified'],
            'accepted': ['in_correction'],
            'resolved': ['corrected', 'verified', 'closed'],
            'rejected': []  # Нет соответствующего статуса для нарушений
        }
        if status_filter in violation_status_mapping:
            violation_statuses = violation_status_mapping[status_filter]
            if violation_statuses:
                violations = violations.filter(status__in=violation_statuses)
            else:
                violations = violations.none()  # Пустой queryset
    
    if priority_filter:
        violations = violations.filter(priority=priority_filter)
    if project_filter:
        violations = violations.filter(project_id=project_filter)
    
    # Объединяем и сортируем
    comments_list = list(comments.order_by('-created_at')[:25])
    violations_list = list(violations.order_by('-created_at')[:25])
    
    # Создаем объединенный список с меткой типа
    all_items = []
    for comment in comments_list:
        comment.item_type = 'comment'
        all_items.append(comment)
    for violation in violations_list:
        violation.item_type = 'violation'
        all_items.append(violation)
    
    # Сортируем по дате создания
    all_items.sort(key=lambda x: x.created_at if hasattr(x, 'created_at') else x.detected_at, reverse=True)
    all_items = all_items[:50]  # Ограничиваем общим количеством
    
    # Обновленная статистика (включая нарушения)
    all_comments = Comment.objects.all()
    all_violations = InspectorViolation.objects.all()
    
    # Применяем тот же ролевой фильтр для статистики
    if hasattr(request.user, 'user_type') and request.user.user_type == 'foreman':
        all_comments = all_comments.filter(
            Q(assigned_to=request.user) | Q(project__foreman=request.user)
        )
        all_violations = all_violations.filter(
            Q(assigned_to=request.user) | Q(project__foreman=request.user)
        )
    elif hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control':
        all_comments = all_comments.filter(
            Q(created_by=request.user) | Q(project__control_service=request.user)
        )
        all_violations = all_violations.filter(
            Q(project__control_service=request.user)
        )
    
    stats = {
        'total': all_comments.count() + all_violations.count(),
        'pending': (
            all_comments.filter(status='pending').count() + 
            all_violations.filter(status__in=['detected', 'notified']).count()
        ),
        'accepted': (
            all_comments.filter(status='accepted').count() + 
            all_violations.filter(status='in_correction').count()
        ),
        'resolved': (
            all_comments.filter(status='resolved').count() + 
            all_violations.filter(status__in=['corrected', 'verified', 'closed']).count()
        ),
        'overdue': (
            len([c for c in all_comments if c.is_overdue]) + 
            len([v for v in all_violations if v.is_overdue])
        ),
    }
    
    context = {
        'comments': all_items,  # Объединенный список нарушений и замечаний
        'stats': stats,
        'all_projects': Project.objects.all().order_by('name'),
        'user': request.user,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'project_filter': project_filter,
    }
    
    return render(request, 'projects/comments_list.html', context)


@login_required(login_url='login')
def comment_detail(request, comment_id):
    """Детальный просмотр замечания"""
    from .models import Comment, CommentPhoto, CommentStatusChange
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права доступа
    has_access = (
        comment.created_by == request.user or
        comment.assigned_to == request.user or
        (hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control' and comment.project.control_service == request.user) or
        (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman' and comment.project.foreman == request.user)
    )
    
    if not has_access:
        from django.contrib import messages
        messages.error(request, 'У вас нет доступа к этому замечанию')
        return redirect('projects:comments_list')
    
    # Получаем фотографии и историю изменений
    photos = CommentPhoto.objects.filter(comment=comment).select_related('taken_by').order_by('is_before', '-created_at')
    status_changes = CommentStatusChange.objects.filter(comment=comment).select_related('changed_by').order_by('-created_at')[:10]
    
    context = {
        'comment': comment,
        'photos': photos,
        'status_changes': status_changes,
        'user': request.user,
        'can_manage': (
            hasattr(request.user, 'user_type') and
            request.user.user_type in ['construction_control', 'foreman'] and
            (comment.project.control_service == request.user or comment.project.foreman == request.user)
        ),
    }
    
    return render(request, 'projects/comment_detail.html', context)


@login_required(login_url='login')
def create_comment(request, project_id):
    """Создание нового замечания"""
    from .models import Comment, Work
    from django.contrib import messages
    
    project = get_object_or_404(Project, id=project_id)
    
    # Проверяем права - только строительный контроль может создавать замечания
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control'):
        messages.error(request, 'Только строительный контроль может создавать замечания')
        return redirect('projects:project_detail', project_id=project_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'medium')
        work_id = request.POST.get('work_id')
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')
        
        if not all([title, description, lat, lng]):
            messages.error(request, 'Все поля обязательны для заполнения, включая геолокацию')
            return redirect('projects:create_comment', project_id=project_id)
        
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            messages.error(request, 'Неверный формат координат')
            return redirect('projects:create_comment', project_id=project_id)
        
        # Проверяем нахождение на объекте
        polygon = _parse_polygon_coords(project.coordinates or '')
        at_location = False
        if polygon:
            at_location = _point_in_polygon(lng, lat, polygon)
        
        if not at_location and polygon:  # Если есть полигон, но пользователь не в нём
            messages.error(request, 'Замечание можно создать только находясь на объекте')
            return redirect('projects:create_comment', project_id=project_id)
        
        # Создаем замечание
        work = None
        if work_id:
            try:
                work = Work.objects.get(id=work_id, project=project)
            except Work.DoesNotExist:
                pass
        
        comment = Comment.objects.create(
            project=project,
            work=work,
            title=title,
            description=description,
            priority=priority,
            created_by=request.user,
            assigned_to=project.foreman,
            location_lat=lat,
            location_lng=lng,
            created_at_location=at_location,
        )
        
        # Создаем событие о добавлении замечания
        from .models import log_comment_added
        log_comment_added(project, request.user, title)
        
        messages.success(request, f'Замечание "{title}" успешно создано')
        return redirect('projects:comment_detail', comment_id=comment.id)
    
    # GET запрос - показываем форму
    works = Work.objects.filter(project=project).select_related('work_type').order_by('planned_start_date')
    
    context = {
        'project': project,
        'works': works,
        'user': request.user,
    }
    
    return render(request, 'projects/create_comment.html', context)


@login_required(login_url='login')
def accept_comment(request, comment_id):
    """Принятие замечания к исполнению"""
    from .models import Comment, CommentStatusChange
    from django.contrib import messages
    from datetime import timedelta, date
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права
    can_manage = (
        hasattr(request.user, 'user_type') and
        request.user.user_type in ['construction_control', 'foreman'] and
        (comment.project.control_service == request.user or comment.project.foreman == request.user)
    )
    
    if not can_manage:
        messages.error(request, 'У вас нет прав для управления этим замечанием')
        return redirect('projects:comment_detail', comment_id=comment_id)
    
    if request.method == 'POST':
        due_date_str = request.POST.get('due_date')
        assigned_to_id = request.POST.get('assigned_to')
        
        due_date = None
        if due_date_str:
            from datetime import datetime
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Неверный формат даты')
                return redirect('projects:comment_detail', comment_id=comment_id)
        
        assigned_to = None
        if assigned_to_id:
            from accounts.models import User
            try:
                assigned_to = User.objects.get(id=assigned_to_id)
            except User.DoesNotExist:
                pass
        
        # Принимаем замечание
        if comment.accept(request.user, due_date, assigned_to):
            # Логируем изменение статуса
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='pending',
                to_status='accepted',
                changed_by=request.user,
                reason='Принято к исполнению'
            )
            messages.success(request, 'Замечание принято к исполнению')
        else:
            messages.error(request, 'Не удалось принять замечание')
    
    return redirect('projects:comment_detail', comment_id=comment_id)


@login_required(login_url='login')
def reject_comment(request, comment_id):
    """Отклонение замечания"""
    from .models import Comment, CommentStatusChange
    from django.contrib import messages
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права
    can_manage = (
        hasattr(request.user, 'user_type') and
        request.user.user_type in ['construction_control', 'foreman'] and
        (comment.project.control_service == request.user or comment.project.foreman == request.user)
    )
    
    if not can_manage:
        messages.error(request, 'У вас нет прав для управления этим замечанием')
        return redirect('projects:comment_detail', comment_id=comment_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        # Отклоняем замечание
        if comment.reject(request.user, reason):
            # Логируем изменение статуса
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='pending',
                to_status='rejected',
                changed_by=request.user,
                reason=reason or 'Замечание отклонено'
            )
            messages.success(request, 'Замечание отклонено')
        else:
            messages.error(request, 'Не удалось отклонить замечание')
    
    return redirect('projects:comment_detail', comment_id=comment_id)


@login_required(login_url='login')
def resolve_comment(request, comment_id):
    """Отметка замечания как устраненного"""
    from .models import Comment, CommentStatusChange
    from django.contrib import messages
    
    comment = get_object_or_404(Comment, id=comment_id)
    
    # Проверяем права - только назначенный или прораб проекта
    can_resolve = (
        comment.assigned_to == request.user or
        (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman' and comment.project.foreman == request.user)
    )
    
    if not can_resolve:
        messages.error(request, 'У вас нет прав для отметки этого замечания как устраненного')
        return redirect('projects:comment_detail', comment_id=comment_id)
    
    if request.method == 'POST':
        resolution_comment = request.POST.get('comment', '')
        
        # Отмечаем как устраненное
        if comment.resolve(request.user, resolution_comment):
            # Логируем изменение статуса
            CommentStatusChange.objects.create(
                comment=comment,
                from_status='accepted',
                to_status='resolved',
                changed_by=request.user,
                reason=resolution_comment or 'Замечание устранено'
            )
            messages.success(request, 'Замечание отмечено как устраненное')
        else:
            messages.error(request, 'Не удалось отметить замечание как устраненное')
    
    return redirect('projects:comment_detail', comment_id=comment_id)


# ========== Views для работы с нарушениями инспектора ==========

@login_required(login_url='login')
def mark_violation_corrected(request, violation_id):
    """Отметка нарушения как исправленного прорабом"""
    from inspector.models import InspectorViolation, ViolationPhoto, ViolationComment
    from django.contrib import messages
    from django.utils import timezone
    import json
    
    violation = get_object_or_404(InspectorViolation, id=violation_id)
    
    # Проверяем права - только прораб или назначенный ответственный
    can_correct = violation.can_be_corrected_by(request.user)
    
    if not can_correct:
        if request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'error': 'У вас нет прав для исправления этого нарушения'}, status=403)
        messages.error(request, 'У вас нет прав для исправления этого нарушения')
        return redirect('projects:comments_list')
    
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                correction_comment = data.get('comment', '')
                photos_data = data.get('photos', [])
            else:
                correction_comment = request.POST.get('comment', '')
                photos_data = []
            
            # Обновляем статус нарушения
            violation.status = 'corrected'
            violation.corrected_at = timezone.now()
            violation.correction_comment = correction_comment
            violation.save()
            
            # Обработка загруженных фотографий
            if request.FILES:
                for file_key in request.FILES:
                    uploaded_file = request.FILES[file_key]
                    
                    # Создаем запись фотографии исправления
                    ViolationPhoto.objects.create(
                        violation=violation,
                        photo=uploaded_file,
                        photo_type='correction',
                        description=f'Фото исправления - {uploaded_file.name}',
                        taken_by=request.user
                    )
            
            # Добавляем комментарий об исправлении
            if correction_comment:
                ViolationComment.objects.create(
                    violation=violation,
                    author=request.user,
                    comment=f"Нарушение исправлено: {correction_comment}"
                )
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True, 
                    'message': 'Нарушение отмечено как исправленное',
                    'new_status': 'Исправлено'
                })
            
            messages.success(request, f'Нарушение "{violation.title}" отмечено как исправленное')
            
        except Exception as e:
            if request.content_type == 'application/json':
                return JsonResponse({'error': f'Ошибка при исправлении нарушения: {str(e)}'}, status=500)
            
            messages.error(request, f'Ошибка при исправлении нарушения: {str(e)}')
    
    return redirect('projects:comments_list')


# ========== Views для работы с QR-кодами ==========

@login_required(login_url='login')
def generate_qr_code(request, project_id):
    """Генерация QR-кода для проекта"""
    from .models import ProjectQRCode
    from django.contrib import messages
    
    project = get_object_or_404(Project, id=project_id)
    
    # Проверяем права - только прораб или стройконтроль могут создавать QR-коды
    can_generate = (
        hasattr(request.user, 'user_type') and 
        request.user.user_type in ['foreman', 'construction_control'] and
        (project.foreman == request.user or project.control_service == request.user)
    )
    
    if not can_generate:
        messages.error(request, 'У вас нет прав для генерации QR-кодов для этого проекта')
        return redirect('projects:project_detail', project_id=project_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', 'Основной QR-код')
        location_description = request.POST.get('location_description', '')
        
        # Создаем QR-код
        qr_code = ProjectQRCode.objects.create(
            project=project,
            name=name,
            location_description=location_description,
            created_by=request.user
        )
        
        messages.success(request, f'QR-код "{name}" успешно создан')
        return redirect('projects:qr_code_detail', project_id=project_id, qr_id=qr_code.id)
    
    # Получаем существующие QR-коды
    qr_codes = ProjectQRCode.objects.filter(project=project, is_active=True).order_by('-created_at')
    
    context = {
        'project': project,
        'qr_codes': qr_codes,
        'user': request.user,
    }
    
    return render(request, 'projects/generate_qr.html', context)


@login_required(login_url='login')
def qr_code_detail(request, project_id, qr_id):
    """Детальная страница QR-кода"""
    from .models import ProjectQRCode, QRVerification
    
    project = get_object_or_404(Project, id=project_id)
    qr_code = get_object_or_404(ProjectQRCode, id=qr_id, project=project)
    
    # Проверяем права доступа
    can_view = (
        hasattr(request.user, 'user_type') and 
        request.user.user_type in ['foreman', 'construction_control', 'inspector'] and
        (
            project.foreman == request.user or 
            project.control_service == request.user or
            request.user.user_type == 'inspector'
        )
    )
    
    if not can_view:
        from django.contrib import messages
        messages.error(request, 'У вас нет доступа к этому QR-коду')
        return redirect('projects:project_detail', project_id=project_id)
    
    # Получаем историю верификаций
    verifications = QRVerification.objects.filter(
        qr_code=qr_code
    ).select_related('user').order_by('-verified_at')[:20]
    
    context = {
        'project': project,
        'qr_code': qr_code,
        'verifications': verifications,
        'user': request.user,
        'qr_image': qr_code.generate_qr_image(),
    }
    
    return render(request, 'projects/qr_detail.html', context)


def verify_qr_code(request, code):
    """Верификация QR-кода"""
    from .models import ProjectQRCode, QRVerification
    from django.http import JsonResponse
    import json
    
    try:
        qr_code = ProjectQRCode.objects.select_related('project').get(
            code=code, is_active=True
        )
        
        if qr_code.is_expired:
            return JsonResponse({
                'success': False,
                'error': 'QR-код истек',
                'expired': True
            })
        
        # Если пользователь авторизован, создаем запись о верификации
        if request.user.is_authenticated:
            # Получаем IP адрес
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Создаем запись о верификации
            QRVerification.objects.create(
                qr_code=qr_code,
                user=request.user,
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return JsonResponse({
            'success': True,
            'project_id': qr_code.project.id,
            'project_name': qr_code.project.name,
            'qr_name': qr_code.name,
            'location_description': qr_code.location_description,
            'verification_time': timezone.now().isoformat()
        })
        
    except ProjectQRCode.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Недействительный QR-код',
            'invalid': True
        })


# ========== Weather Analysis Views ==========

@login_required(login_url='login')
def weather_analysis_detail(request, project_id):
    """Детальная страница погодной аналитики для проекта"""
    # ВАЖНО: Функция всегда строит прогноз начиная с ТЕКУЩЕЙ даты
    from .models import WeatherWorkRecommendation, WeatherForecast, WorkType
    import requests
    from datetime import datetime, timedelta
    from django.db.models import Q
    
    project = get_object_or_404(Project, id=project_id)
    
    # Проверяем права доступа
    can_view = (
        project.is_user_member(request.user) or 
        (hasattr(request.user, 'user_type') and request.user.user_type in ['construction_control', 'foreman', 'inspector'])
    )
    
    if not can_view:
        messages.error(request, 'У вас нет доступа к погодной аналитике этого проекта')
        return redirect('projects:project_detail', project_id=project_id)
    
    # Получаем или создаем прогноз погоды
    weather_data = get_or_create_weather_forecast(project)
    
    # Получаем все работы проекта с их типами
    works = project.works.select_related('work_type').filter(
        status__in=['not_started', 'in_progress']
    ).order_by('planned_start_date')
    
    # Анализируем работы по дням
    work_weather_analysis = []
    
    for i in range(14):  # Прогноз на 14 дней начиная с СЕГОДНЯ
        forecast_date = timezone.now().date() + timedelta(days=i)  # ВСЕГДА от текущей даты
        
        # Получаем прогноз погоды на день
        try:
            forecast = WeatherForecast.objects.get(
                project=project,
                forecast_date=forecast_date
            )
        except WeatherForecast.DoesNotExist:
            # Создаем заглушку если нет данных
            forecast = WeatherForecast(
                project=project,
                forecast_date=forecast_date,
                temperature=10,
                weather_main='Clouds',
                weather_description='облачно',
                wind_speed=5,
                humidity=70,
                precipitation=0
            )
        
        # Находим работы запланированные на этот день
        day_works = works.filter(
            Q(planned_start_date__lte=forecast_date) & 
            Q(planned_end_date__gte=forecast_date)
        )
        
        work_recommendations = []
        weather_condition = forecast.get_weather_condition_code()
        
        for work in day_works:
            try:
                recommendation = WeatherWorkRecommendation.objects.get(
                    work_type=work.work_type,
                    weather_condition=weather_condition
                )
            except WeatherWorkRecommendation.DoesNotExist:
                # Создаем базовую рекомендацию
                recommendation = get_default_weather_recommendation(work.work_type, weather_condition, forecast)
            
            work_recommendations.append({
                'work': work,
                'recommendation': recommendation
            })
        
        work_weather_analysis.append({
            'date': forecast_date,
            'forecast': forecast,
            'weather_condition': weather_condition,
            'works': work_recommendations,
            'risk_level': calculate_day_risk_level(work_recommendations)
        })
    
    # Статистика по типам работ
    work_types_stats = []
    for work_type in WorkType.objects.filter(works__project=project).distinct():
        total_recommendations = WeatherWorkRecommendation.objects.filter(work_type=work_type)
        risky_conditions = total_recommendations.filter(risk_level__in=['high', 'critical']).count()
        
        work_types_stats.append({
            'work_type': work_type,
            'total_conditions': total_recommendations.count(),
            'risky_conditions': risky_conditions,
            'risk_percentage': int((risky_conditions / total_recommendations.count() * 100)) if total_recommendations.count() > 0 else 0
        })
    
    context = {
        'project': project,
        'work_weather_analysis': work_weather_analysis,
        'work_types_stats': work_types_stats,
        'weather_data': weather_data,
        'user': request.user,
    }
    
    return render(request, 'projects/weather_analysis_detail.html', context)


def get_or_create_weather_forecast(project):
    """Получает прогноз погоды из API или создает тестовые данные с учетом текущей даты"""
    from .models import WeatherForecast
    from datetime import datetime, timedelta
    from django.utils import timezone
    import random
    
    # ВСЕГДА используем текущую дату как точку отсчета
    today = timezone.now().date()
    
    # Проверяем есть ли актуальный прогноз начиная с сегодня
    existing_forecasts = WeatherForecast.objects.filter(
        project=project,
        forecast_date__gte=today,
        forecast_date__lte=today + timedelta(days=13)  # 14 дней вперед
    ).count()
    
    # Если прогнозов меньше 14 или они устарели, пересоздаем
    if existing_forecasts < 14:
        # Удаляем все старые прогнозы для этого проекта
        WeatherForecast.objects.filter(project=project).delete()
        
        # Создаем свежие данные прогноза на 14 дней вперед
        weather_conditions = ['Clear', 'Clouds', 'Rain', 'Snow']
        descriptions = {
            'Clear': 'ясно',
            'Clouds': 'облачно с прояснениями', 
            'Rain': 'дождь',
            'Snow': 'снег'
        }
        
        forecasts = []
        for i in range(14):
            forecast_date = today + timedelta(days=i)
            
            # Создаем новый прогноз с актуальной датой
            weather_main = random.choice(weather_conditions)
            
            # Более реалистичная температура в зависимости от времени года
            month = forecast_date.month
            if month in [12, 1, 2]:  # Зима
                base_temp = random.randint(-10, 5)
            elif month in [3, 4, 5]:  # Весна
                base_temp = random.randint(5, 20)
            elif month in [6, 7, 8]:  # Лето
                base_temp = random.randint(15, 30)
            else:  # Осень
                base_temp = random.randint(0, 15)
            
            forecast = WeatherForecast.objects.create(
                project=project,
                forecast_date=forecast_date,
                temperature=base_temp,
                weather_main=weather_main,
                weather_description=descriptions[weather_main],
                wind_speed=random.uniform(2, 15),
                humidity=random.randint(40, 90),
                precipitation=random.uniform(0, 10) if weather_main == 'Rain' else 0
            )
            forecasts.append(forecast)
        
        return forecasts
    
    # Возвращаем существующие актуальные прогнозы
    return WeatherForecast.objects.filter(
        project=project,
        forecast_date__gte=today
    ).order_by('forecast_date')[:14]


def get_default_weather_recommendation(work_type, weather_condition, forecast):
    """Создает базовую рекомендацию для типа работ при определенных погодных условиях"""
    from .models import WeatherWorkRecommendation
    
    # Базовые правила для разных типов работ
    work_rules = {
        'earthworks': {  # Земляные работы
            'rain': {'allowed': False, 'risk': 'high', 'delay': 24, 'reason': 'Земляные работы невозможны при дожде'},
            'snow': {'allowed': False, 'risk': 'high', 'delay': 48, 'reason': 'Земляные работы осложнены при снеге'},
            'extreme_cold': {'allowed': False, 'risk': 'critical', 'delay': 72, 'reason': 'Земляные работы запрещены при температуре ниже -15°C'},
        },
        'concrete': {  # Бетонные работы
            'rain': {'allowed': False, 'risk': 'critical', 'delay': 48, 'reason': 'Бетонирование запрещено при осадках'},
            'extreme_cold': {'allowed': False, 'risk': 'critical', 'delay': 72, 'reason': 'Бетонные работы невозможны при морозе'},
            'extreme_heat': {'allowed': True, 'risk': 'medium', 'delay': 0, 'reason': 'Требуется дополнительный уход за бетоном'},
        },
        'asphalt': {  # Асфальтирование
            'rain': {'allowed': False, 'risk': 'critical', 'delay': 24, 'reason': 'Асфальтирование невозможно при дожде'},
            'extreme_cold': {'allowed': False, 'risk': 'critical', 'delay': 48, 'reason': 'Асфальтирование запрещено при температуре ниже +5°C'},
        },
        'painting': {  # Покрасочные работы
            'rain': {'allowed': False, 'risk': 'high', 'delay': 24, 'reason': 'Покрасочные работы невозможны при осадках'},
            'high_wind': {'allowed': False, 'risk': 'high', 'delay': 12, 'reason': 'Покраска затруднена при сильном ветре'},
        }
    }
    
    # Определяем тип работ по коду
    work_code = work_type.code.lower() if work_type.code else work_type.name.lower()
    
    # Ищем подходящее правило
    rule = None
    for rule_type, conditions in work_rules.items():
        if rule_type in work_code:
            rule = conditions.get(weather_condition)
            break
    
    # Если правило не найдено, создаем базовое
    if not rule:
        if weather_condition in ['rain', 'thunderstorm']:
            rule = {'allowed': True, 'risk': 'medium', 'delay': 0, 'reason': 'Рекомендуется соблюдать осторожность при дожде'}
        elif weather_condition == 'extreme_cold':
            rule = {'allowed': False, 'risk': 'high', 'delay': 24, 'reason': 'Работы затруднены при низких температурах'}
        elif weather_condition == 'high_wind':
            rule = {'allowed': True, 'risk': 'medium', 'delay': 0, 'reason': 'Соблюдайте меры безопасности при сильном ветре'}
        else:
            rule = {'allowed': True, 'risk': 'low', 'delay': 0, 'reason': 'Благоприятные условия для работ'}
    
    # Создаем объект рекомендации (не сохраняем в БД)
    return WeatherWorkRecommendation(
        work_type=work_type,
        weather_condition=weather_condition,
        is_work_allowed=rule['allowed'],
        risk_level=rule['risk'],
        delay_hours=rule['delay'],
        recommendation=rule['reason']
    )


def calculate_day_risk_level(work_recommendations):
    """Вычисляет общий уровень риска для дня на основе рекомендаций по работам"""
    if not work_recommendations:
        return 'low'
    
    risk_scores = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
    total_score = 0
    
    for work_rec in work_recommendations:
        total_score += risk_scores.get(work_rec['recommendation'].risk_level, 1)
    
    avg_score = total_score / len(work_recommendations)
    
    if avg_score <= 1.5:
        return 'low'
    elif avg_score <= 2.5:
        return 'medium'
    elif avg_score <= 3.5:
        return 'high'
    else:
        return 'critical'
