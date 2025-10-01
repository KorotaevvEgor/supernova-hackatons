from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from projects.models import Project, Work
from accounts.models import Visit
import json

@login_required(login_url='login')
def verification_list(request):
    """Список работ для верификации"""
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        messages.error(request, 'Доступ к верификации работ разрешен только строительному контролю')
        return redirect('/')
    
    # Получаем проекты под контролем пользователя
    projects = Project.objects.filter(
        control_service=request.user,
        status='active'
    ).select_related('foreman')
    
    # Получаем работы, которые нужно верифицировать
    works_to_verify = []
    for project in projects:
        works = Work.objects.filter(
            project=project,
            reported_by_foreman=True,
            verified_by_control=False,
            status__in=['completed', 'in_progress']
        ).select_related('work_type').order_by('planned_end_date')
        
        for work in works:
            works_to_verify.append({
                'work': work,
                'project': project,
                'days_since_reported': (timezone.now().date() - work.updated_at.date()).days,
                'priority': 'high' if work.is_delayed else 'normal'
            })
    
    # Сортируем по приоритету
    works_to_verify.sort(key=lambda x: (x['priority'] != 'high', x['days_since_reported']))
    
    context = {
        'works_to_verify': works_to_verify,
        'user': request.user,
        'projects_count': projects.count(),
        'total_works': len(works_to_verify),
    }
    
    return render(request, 'verification/verification_list.html', context)

@login_required(login_url='login')
def project_verification(request, project_id):
    """Верификация работ на конкретном проекте"""
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        messages.error(request, 'Доступ к верификации работ разрешен только строительному контролю')
        return redirect('/')
    
    project = get_object_or_404(Project, id=project_id)
    
    # Проверяем, что пользователь ответственный за проект
    if project.control_service != request.user:
        messages.error(request, 'Вы не являетесь ответственным за этот проект')
        return redirect('verification:verification_list')
    
    # Получаем координаты из GET параметров (если пришли с кнопки на карточке)
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    
    # Получаем работы для верификации
    works = Work.objects.filter(
        project=project,
        reported_by_foreman=True,
        verified_by_control=False
    ).select_related('work_type').order_by('planned_start_date')
    
    context = {
        'project': project,
        'works': works,
        'user': request.user,
        'user_lat': lat,
        'user_lng': lng,
    }
    
    return render(request, 'verification/project_verification.html', context)

@login_required(login_url='login')
def verify_work(request, work_id):
    """Верификация конкретной работы"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST запросы'}, status=405)
    
    # Проверяем права доступа
    if not hasattr(request.user, 'user_type') or request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    
    work = get_object_or_404(Work, id=work_id)
    
    # Проверяем, что пользователь ответственный за проект
    if work.project.control_service != request.user:
        return JsonResponse({'error': 'Вы не ответственный за этот проект'}, status=403)
    
    try:
        data = json.loads(request.body)
        lat = data.get('latitude')
        lng = data.get('longitude')
        verification_notes = data.get('notes', '')
        
        if not lat or not lng:
            return JsonResponse({'error': 'Требуется геолокация'}, status=400)
        
        # Проверяем, что пользователь находится в пределах полигона проекта
        if work.project.coordinates:
            from projects.views import _parse_polygon_coords, _point_in_polygon
            polygon = _parse_polygon_coords(work.project.coordinates)
            if polygon and not _point_in_polygon(lng, lat, polygon):
                return JsonResponse({'error': 'Вы находитесь вне территории объекта'}, status=400)
        
        # Создаем визит
        visit = Visit.objects.create(
            user=request.user,
            project=work.project,
            latitude=lat,
            longitude=lng
        )
        
        # Верифицируем работу
        work.verified_by_control = True
        work.status = 'verified'
        if not work.actual_end_date:
            work.actual_end_date = timezone.now().date()
        work.save()
        
        # Добавляем примечания к верификации (можно расширить модель Work)
        if verification_notes:
            # Здесь можно добавить модель для хранения заметок верификации
            pass
        
        return JsonResponse({
            'success': True,
            'message': f'Работа "{work.name}" успешно верифицирована',
            'work_status': work.get_status_display(),
            'visit_id': visit.id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)