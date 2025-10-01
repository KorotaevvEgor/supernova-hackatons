from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, timedelta

# Временно импортируем модели (в будущем можно будет использовать настоящие)
try:
    from projects.models import Project
    from materials.models import MaterialDelivery 
    from violations.models import Violation
except ImportError:
    Project = None
    MaterialDelivery = None
    Violation = None

@login_required(login_url='login')
def dashboard(request):
    """Главная страница с дашбордом - перенаправляет на роль-специфичный дашборд""" 
    # Проверяем роль пользователя и перенаправляем
    if hasattr(request.user, 'user_type') and request.user.user_type:
        if request.user.user_type == 'construction_control':
            return redirect('dashboard_control')
        elif request.user.user_type == 'foreman':
            return redirect('foreman:dashboard')
        elif request.user.user_type == 'inspector':
            return redirect('inspector:dashboard')
        elif request.user.user_type == 'identifier':
            return redirect('/identifier/identifier/')
    
    # Fallback на обычный дашборд
    from projects.models import Project
    from materials.models import MaterialDelivery
    from violations.models import Violation
    import json
    
    # Получаем ID выбранного проекта
    selected_project_id = request.GET.get('project_id')
    selected_project = None
    
    # Получаем все проекты для селектора
    all_projects = Project.objects.all().order_by('name')
    
    if selected_project_id and selected_project_id != 'all':
        try:
            selected_project = Project.objects.select_related('control_service', 'foreman').get(id=selected_project_id)
        except Project.DoesNotExist:
            selected_project = None
    elif not selected_project_id and all_projects.exists():
        # Если проект не выбран и есть доступные проекты, выбираем первый
        selected_project = all_projects.select_related('control_service', 'foreman').first()
        selected_project_id = str(selected_project.id)
    
    # Получаем реальные данные (фильтруем по выбранному проекту если он выбран)
    if selected_project:
        # Статистика только по выбранному проекту
        stats = {
            'active_projects': 1 if selected_project.status == 'active' else 0,
            'total_projects': 1,
            'materials_delivered': MaterialDelivery.objects.filter(
                project=selected_project,
                status__in=['delivered', 'accepted']
            ).count(),
            'materials_today': MaterialDelivery.objects.filter(
                project=selected_project,
                delivery_date__date=timezone.now().date()
            ).count(),
            'active_violations': Violation.objects.filter(
                project=selected_project,
                status__in=['open', 'in_progress']
            ).count(),
            'overdue_violations': Violation.objects.filter(
                project=selected_project,
                status__in=['open', 'in_progress'],
                deadline__lt=timezone.now()
            ).count(),
        }
    else:
        # Общая статистика по всем проектам
        stats = {
            'active_projects': Project.objects.filter(status='active').count(),
            'total_projects': Project.objects.count(),
            'materials_delivered': MaterialDelivery.objects.filter(
                status__in=['delivered', 'accepted']
            ).count(),
            'materials_today': MaterialDelivery.objects.filter(
                delivery_date__date=timezone.now().date()
            ).count(),
            'active_violations': Violation.objects.filter(
                status__in=['open', 'in_progress']
            ).count(),
            'overdue_violations': Violation.objects.filter(
                status__in=['open', 'in_progress'],
                deadline__lt=timezone.now()
            ).count(),
        }
    
    # Подсчет общего прогресса
    if selected_project:
        stats['overall_progress'] = selected_project.completion_percentage
    else:
        active_projects = Project.objects.filter(status='active')
        if active_projects.exists():
            total_progress = sum(project.completion_percentage for project in active_projects)
            stats['overall_progress'] = int(total_progress / active_projects.count())
        else:
            stats['overall_progress'] = 0
    
    # Данные для карты (фильтруем по выбранному проекту)
    projects_for_map = []
    if selected_project:
        # Показываем только выбранный проект на карте
        projects_to_show = [selected_project]
    else:
        # Показываем все проекты (ограничиваем для производительности)
        projects_to_show = Project.objects.all()[:10]
        
    for project in projects_to_show:
        if project.coordinates:
            try:
                coordinates_data = json.loads(project.coordinates)
                projects_for_map.append({
                    'id': project.id,
                    'name': project.name,
                    'address': project.address,
                    'status': project.status,
                    'coordinates': coordinates_data,
                    'completion': project.completion_percentage,
                    'control_service': project.control_service.get_full_name() if project.control_service else None,
                    'foreman': project.foreman.get_full_name() if project.foreman else None,
                })
            except (json.JSONDecodeError, Exception):
                pass
    
    # Последние активности (фильтруем по выбранному проекту)
    recent_activities = []
    
    # Недавние поставки материалов
    deliveries_query = MaterialDelivery.objects.select_related('project', 'material_type')
    if selected_project:
        deliveries_query = deliveries_query.filter(project=selected_project)
    recent_deliveries = deliveries_query.order_by('-delivery_date')[:5]
    
    for delivery in recent_deliveries:
        recent_activities.append({
            'type': 'material_delivery',
            'title': f'Поставка материалов: {delivery.material_type.name}',
            'description': f'{delivery.quantity} {delivery.material_type.unit} на объект "{delivery.project.name}"',
            'date': delivery.delivery_date,
            'status': delivery.get_status_display()
        })
    
    # Недавние нарушения
    violations_query = Violation.objects.select_related('project', 'created_by')
    if selected_project:
        violations_query = violations_query.filter(project=selected_project)
    recent_violations = violations_query.order_by('-detected_at')[:5]
    
    for violation in recent_violations:
        recent_activities.append({
            'type': 'violation',
            'title': f'Нарушение: {violation.title}',
            'description': f'Объект "{violation.project.name}" - {violation.get_priority_display()} приоритет',
            'date': violation.detected_at,
            'status': violation.get_status_display()
        })
    
    # Сортируем по дате
    recent_activities.sort(key=lambda x: x['date'], reverse=True)
    recent_activities = recent_activities[:10]
    
    # Дополнительные данные для выбранного проекта
    work_specification = []
    work_schedule = []
    work_types_summary = []
    
    if selected_project:
        work_specification = selected_project.work_specification[:20]  # Ограничиваем для производительности
        work_schedule = selected_project.work_schedule_data
        work_types_summary = selected_project.work_types_summary
    
    context = {
        'stats': stats,
        'projects_for_map': json.dumps(projects_for_map),
        'recent_activities': recent_activities,
        'user': request.user if request.user.is_authenticated else None,
        'all_projects': all_projects,
        'selected_project': selected_project,
        'selected_project_id': selected_project_id,
        'work_specification': work_specification,
        'work_schedule': work_schedule,
        'work_types_summary': work_types_summary,
    }
    
    return render(request, 'dashboard.html', context)

@login_required(login_url='login')
def analytics_view(request):
    """Страница аналитики"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Аналитика - Система управления благоустройством</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <div class="container mx-auto px-4 py-8">
            <div class="bg-white rounded-lg shadow-md p-6">
                <h1 class="text-3xl font-bold text-purple-600 mb-6">📈 Аналитика и отчеты</h1>
                
                <div class="mb-6">
                    <a href="/" class="text-blue-600 hover:underline">← Вернуться на главную</a>
                </div>
                
                <div class="bg-purple-50 border-l-4 border-purple-500 p-4 mb-6">
                    <h2 class="text-lg font-semibold mb-2">📊 Отчеты и статистика</h2>
                    <p class="text-gray-700">Здесь отображается аналитика по проектам благоустройства Москвы.</p>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div class="border rounded-lg p-4">
                        <h3 class="font-semibold">Отчет по проектам</h3>
                        <p class="text-gray-600">Ежемесячный отчет о выполнении проектов</p>
                    </div>
                    <div class="border rounded-lg p-4">
                        <h3 class="font-semibold">Анализ расходов</h3>
                        <p class="text-gray-600">Статистика по расходам на материалы</p>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    from django.http import HttpResponse
    return HttpResponse(html_content)


def login_view(request):
    """Страница входа в систему"""
    from django.contrib.auth import authenticate, login
    from django.contrib import messages
    from django.shortcuts import redirect
    
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.get_full_name() or user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Неверное имя пользователя или пароль')
        else:
            messages.error(request, 'Пожалуйста, заполните все поля')
    
    # Получаем CSRF токен и список пользователей
    from django.middleware.csrf import get_token
    from django.contrib.auth import get_user_model
    
    csrf_token = get_token(request)
    User = get_user_model()
    demo_users = User.objects.filter(username__in=['stroy_control_1', 'foreman_1', 'foreman_2', 'inspector_1']).order_by('username')
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru" class="min-h-screen bg-gradient-to-br from-primary-dark via-secondary-blue to-accent-burgundy">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Вход в систему - Управление благоустройством</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{
                theme: {{
                    extend: {{
                        colors: {{
                            'primary-dark': '#151E3F',
                            'primary-blue': '#2942F9', 
                            'secondary-blue': '#384358',
                            'accent-peach': '#FFA586',
                            'accent-red': '#A51A2B',
                            'accent-burgundy': '#53143F',
                        }}
                    }}
                }}
            }}
        </script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            .glass {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }}
            
            /* Обеспечиваем полное покрытие фоном */
            html, body {{
                min-height: 100vh;
                background: linear-gradient(to bottom right, #151E3F, #384358, #53143F);
                background-attachment: fixed;
            }}
        </style>
    </head>
    <body class="min-h-screen bg-gradient-to-br from-primary-dark via-secondary-blue to-accent-burgundy">
        <div class="flex min-h-screen flex-col justify-center py-12 sm:px-6 lg:px-8">
            <div class="sm:mx-auto sm:w-full sm:max-w-md">
                <div class="flex justify-center">
                    <div class="h-16 w-16 rounded-full bg-gradient-to-r from-accent-peach to-primary-blue flex items-center justify-center">
                        <i class="fas fa-city text-2xl text-white"></i>
                    </div>
                </div>
                <h2 class="mt-6 text-center text-3xl font-bold tracking-tight text-white">
                    Вход в систему
                </h2>
                <p class="mt-2 text-center text-sm text-accent-peach">
                    Система управления благоустройством Москвы
                </p>
            </div>
            
            <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
                <div class="glass py-8 px-4 shadow-2xl rounded-2xl">
    """
    
    # Добавляем сообщения
    if hasattr(request, '_messages'):
        for message in messages.get_messages(request):
            message_class = 'bg-red-50 border-red-200 text-red-700' if message.tags == 'error' else 'bg-green-50 border-green-200 text-green-700'
            html_content += f"""
                    <div class="mb-4 border-l-4 p-4 {message_class}">
                        <p class="text-sm">{message}</p>
                    </div>
            """
    
    html_content += f"""
                    <form class="space-y-6" method="post">
                        <input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">
                        
                        <div>
                            <label for="username" class="block text-sm font-medium text-white">
                                Логин
                            </label>
                            <div class="mt-1">
                                <input id="username" name="username" type="text" required
                                    class="block w-full appearance-none rounded-lg bg-white/20 border border-white/30 px-3 py-2 placeholder-white/70 text-white shadow-sm focus:border-accent-peach focus:outline-none focus:ring-2 focus:ring-accent-peach/50 backdrop-blur-sm">
                            </div>
                        </div>
                        
                        <div>
                            <label for="password" class="block text-sm font-medium text-white">
                                Пароль
                            </label>
                            <div class="mt-1">
                                <input id="password" name="password" type="password" required
                                    class="block w-full appearance-none rounded-lg bg-white/20 border border-white/30 px-3 py-2 placeholder-white/70 text-white shadow-sm focus:border-accent-peach focus:outline-none focus:ring-2 focus:ring-accent-peach/50 backdrop-blur-sm">
                            </div>
                        </div>
                        
                        <div>
                            <button type="submit"
                                class="flex w-full justify-center rounded-lg border border-transparent bg-gradient-to-r from-primary-blue to-accent-peach py-3 px-4 text-sm font-medium text-white shadow-lg hover:from-primary-blue/90 hover:to-accent-peach/90 focus:outline-none focus:ring-2 focus:ring-accent-peach/50 focus:ring-offset-2 transition-all duration-200">
                                <i class="fas fa-sign-in-alt mr-2"></i>
                                Войти
                            </button>
                        </div>
                    </form>
                    
                    <!-- Аккаунты для входа -->
                    <div class="mt-6">
                        <div class="relative">
                            <div class="w-full h-px bg-gradient-to-r from-transparent via-white/50 to-transparent"></div>
                        </div>
                        
                        <div class="mt-3 text-center">
                            <span class="text-sm text-white font-medium">Демонстрационные аккаунты</span>
                        </div>
                        
                        <div class="mt-3 space-y-2">
    """
    
    # Добавляем пользователей для быстрого входа
    for user in demo_users:
        role_colors = {
            'construction_control': 'bg-gradient-to-r from-primary-blue/20 to-accent-peach/20 text-white border-primary-blue/30',
            'foreman': 'bg-gradient-to-r from-accent-peach/20 to-primary-blue/20 text-white border-accent-peach/30',
            'inspector': 'bg-gradient-to-r from-accent-red/20 to-accent-burgundy/20 text-white border-accent-red/30',
        }
        color_class = role_colors.get(user.user_type, 'bg-gradient-to-r from-secondary-blue/20 to-accent-burgundy/20 text-white border-secondary-blue/30')
        
        html_content += f"""
                            <button type="button" onclick="loginAs('{user.username}', 'demo123')" 
                                class="w-full text-left px-4 py-3 border {color_class} rounded-xl hover:scale-105 transition-all duration-200 backdrop-blur-sm">
                                <div class="flex items-center justify-between">
                                    <div>
                                        <p class="font-medium text-white">{user.get_full_name()}</p>
                                        <p class="text-xs text-white/80">{user.get_user_type_display()}</p>
                                    </div>
                                    <div class="text-right">
                                        <p class="text-xs text-white/60 font-mono">{user.username}</p>
                                    </div>
                                </div>
                            </button>
        """
    
    html_content += """
                        </div>
                        <p class="mt-4 text-xs text-accent-peach/80 text-center">
                            Пароль: <span class="font-mono font-medium text-white">demo123</span>
                        </p>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            function loginAs(username, password) {
                document.getElementById('username').value = username;
                document.getElementById('password').value = password;
                document.querySelector('form').submit();
            }
        </script>
    </body>
    </html>
    """
    
    from django.http import HttpResponse
    return HttpResponse(html_content)


def logout_view(request):
    """Выход из системы"""
    from django.contrib.auth import logout
    from django.contrib import messages
    from django.shortcuts import redirect
    
    # Очищаем все старые сообщения
    list(messages.get_messages(request))
    
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы')
    return redirect('login')


@login_required
def dashboard_control(request):
    """Мои объекты - страница строительного контроля"""
    try:
        from projects.models import Project
        from materials.models import MaterialDelivery
        from violations.models import Violation
    except ImportError:
        Project = None
        MaterialDelivery = None
        Violation = None
    import json
    
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'construction_control'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Получаем статистику
    today = timezone.now().date()
    
    # Общая статистика
    planned_projects_count = Project.objects.filter(status='planned').count() if Project else 0
    # Подсчитываем проекты, находящиеся на стадии верификации (завершенные проекты)
    pending_verification = Project.objects.filter(status='completed').count() if Project else 0
    
    stats = {
        'active_projects': Project.objects.filter(status='active').count() if Project else 0,
        'active_violations': Violation.objects.filter(status='open').count() if Violation else 0,
        'planned_projects': planned_projects_count,
        'pending_verification': pending_verification,
    }
    
    # Объекты требующие активации
    projects_to_activate = []
    if Project:
        projects_to_activate = Project.objects.filter(
            status='planned',
            planned_start_date__lte=today + timedelta(days=7)
        ).order_by('planned_start_date')[:10]
    
    
    # Получаем все доступные проекты для отображения в списке
    available_projects = Project.objects.all().select_related('foreman', 'control_service') if Project else []
    
    # Данные для карты (с преобразованием WKT в JSON)
    projects_for_map = []
    if Project:
        for project in Project.objects.filter(coordinates__isnull=False):
            try:
                # Используем метод модели для преобразования
                coordinates_data = project.get_coordinates_json()
                if coordinates_data:
                    projects_for_map.append({
                        'id': project.id,
                        'name': project.name,
                        'address': project.address or '',
                        'status': project.status,
                        'completion': project.completion_percentage,
                        'coordinates': coordinates_data
                    })
            except Exception:
                pass
    
    context = {
        'user': request.user,
        'stats': stats,
        'projects_to_activate': projects_to_activate,
        'projects_for_map': json.dumps(projects_for_map) if projects_for_map else '[]',
        'available_projects': available_projects
    }
    
    return render(request, 'dashboards/construction_control.html', context)


@login_required
def dashboard_foreman(request):
    """Дашборд прораба"""
    try:
        from projects.models import Project
        from materials.models import MaterialDelivery
        from violations.models import Violation
    except ImportError:
        Project = None
        MaterialDelivery = None
        Violation = None
    
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'foreman'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Объекты, назначенные на данного прораба
    assigned_projects = Project.objects.filter(foreman=request.user) if Project else []
    
    # Статистика
    stats = {
        'active_projects': assigned_projects.filter(status='active').count() if assigned_projects else 0,
        'pending_materials': MaterialDelivery.objects.filter(
            project__in=assigned_projects,
            status='pending'
        ).count() if MaterialDelivery and assigned_projects else 0,
        'today_tasks': 0,  # Будет реализовано позже
        'open_violations': Violation.objects.filter(
            project__in=assigned_projects,
            status='open'
        ).count() if Violation and assigned_projects else 0
    }
    
    # Нарушения для устранения
    violations_to_fix = []
    if Violation and assigned_projects:
        violations_to_fix = Violation.objects.filter(
            project__in=assigned_projects,
            status='open'
        ).order_by('-detected_at')[:10]
    
    # Сегодняшние задачи (заглушка)
    today_tasks = []
    
    context = {
        'assigned_projects': assigned_projects,
        'stats': stats,
        'violations_to_fix': violations_to_fix,
        'today_tasks': today_tasks
    }
    
    return render(request, 'dashboards/foreman.html', context)


@login_required
def dashboard_inspector(request):
    """Дашборд инспектора контрольного органа - перенаправляет на дашборд инспектора"""
    # Проверяем роль пользователя
    if not (hasattr(request.user, 'user_type') and request.user.user_type == 'inspector'):
        messages.error(request, 'У вас нет доступа к этому разделу')
        return redirect('dashboard')
    
    # Перенаправляем на дашборд инспектора
    return redirect('inspector:dashboard')
