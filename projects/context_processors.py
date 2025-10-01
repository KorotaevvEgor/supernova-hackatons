from django.db import models
from django.db.models import Q
from .models import Project


def projects_context(request):
    """
    Контекст-процессор для добавления списка проектов во все шаблоны
    Обеспечивает постоянную доступность выпадающего списка выбора проекта
    """
    if not request.user.is_authenticated:
        return {}
    
    try:
        # Фильтруем проекты в зависимости от роли пользователя
        if hasattr(request.user, 'user_type'):
            if request.user.user_type == 'construction_control':
                # Строительный контроль видит все проекты или только свои
                all_projects = Project.objects.filter(
                    Q(control_service=request.user) | 
                    Q(status__in=['planned', 'active'])
                ).select_related('foreman', 'control_service').order_by('name')
            elif request.user.user_type == 'inspector':
                # Инспекторы видят все активные проекты
                all_projects = Project.objects.filter(
                    status__in=['planned', 'active']
                ).select_related('foreman', 'control_service').order_by('name')
            elif request.user.user_type == 'foreman':
                # Прорабы видят только свои проекты
                all_projects = Project.objects.filter(
                    foreman=request.user
                ).select_related('foreman', 'control_service').order_by('name')
            else:
                # Для остальных ролей - все проекты
                all_projects = Project.objects.all().select_related('foreman', 'control_service').order_by('name')
        else:
            # Для пользователей без роли - все проекты
            all_projects = Project.objects.all().select_related('foreman', 'control_service').order_by('name')
        
        # Определяем текущий выбранный проект по URL
        selected_project = None
        if '/projects/' in request.path:
            try:
                # Извлекаем ID проекта из URL вида /projects/1/
                path_parts = request.path.strip('/').split('/')
                if len(path_parts) >= 2 and path_parts[0] == 'projects' and path_parts[1].isdigit():
                    project_id = int(path_parts[1])
                    selected_project = Project.objects.get(id=project_id)
            except (ValueError, Project.DoesNotExist):
                selected_project = None
        
        return {
            'all_projects': all_projects[:50],  # Ограничиваем количество для производительности
            'selected_project': selected_project
        }
    
    except Exception as e:
        # В случае ошибки возвращаем пустой словарь
        return {}