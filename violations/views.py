from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from .models import Violation, ViolationType, ViolationClassifier
from projects.models import Project
from accounts.models import Visit
from datetime import timedelta

# API Views
def violation_list_api(request):
    return JsonResponse({'message': 'Violations API endpoint'})

class _VisitMixin:
    def _has_recent_visit(self, user, project, minutes=120):
        visit = Visit.objects.filter(user=user, project=project).order_by('-created_at').first()
        if not visit:
            return False
        return timezone.now() - visit.created_at <= timedelta(minutes=minutes)

class ViolationListCreateAPI(APIView, _VisitMixin):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        items = Violation.objects.select_related('project','violation_type').order_by('-detected_at')[:100]
        data = []
        for v in items:
            data.append({
                'id': v.id,
                'title': v.title,
                'status': v.status,
                'project': v.project.name,
                'deadline': v.deadline,
                'type': v.violation_type.name,
            })
        return Response({'results': data})

    def post(self, request):
        user = request.user
        if user.user_type not in ['construction_control','inspector']:
            return Response({'detail':'Недостаточно прав'}, status=status.HTTP_403_FORBIDDEN)
        try:
            project = Project.objects.get(pk=request.data.get('project_id'))
        except Project.DoesNotExist:
            return Response({'detail':'Проект не найден'}, status=status.HTTP_404_NOT_FOUND)
        if not self._has_recent_visit(user, project):
            return Response({'detail': 'Нет актуальной отметки посещения'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            vtype = ViolationType.objects.get(pk=request.data.get('violation_type_id'))
        except ViolationType.DoesNotExist:
            return Response({'detail':'Тип нарушения не найден'}, status=status.HTTP_404_NOT_FOUND)
        v = Violation.objects.create(
            project=project,
            violation_type=vtype,
            title=request.data.get('title','Нарушение'),
            description=request.data.get('description',''),
            location=request.data.get('location','0,0'),
            status='open',
            priority=request.data.get('priority','medium'),
            created_by=user,
            detected_at=timezone.now(),
            deadline=timezone.now() + timedelta(days=vtype.regulatory_deadline_days),
        )
        return Response({'status':'ok','violation_id': v.id})

class ViolationResolveAPI(APIView, _VisitMixin):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        try:
            v = Violation.objects.get(pk=pk)
        except Violation.DoesNotExist:
            return Response({'detail':'Нарушение не найдено'}, status=status.HTTP_404_NOT_FOUND)
        if request.user.user_type != 'foreman':
            return Response({'detail': 'Только прораб может отмечать устранение'}, status=status.HTTP_403_FORBIDDEN)
        if not self._has_recent_visit(request.user, v.project):
            return Response({'detail': 'Нет актуальной отметки посещения'}, status=status.HTTP_400_BAD_REQUEST)
        v.status = 'resolved'
        v.resolved_at = timezone.now()
        v.save()
        return Response({'status':'ok'})

class ViolationVerifyAPI(APIView, _VisitMixin):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        try:
            v = Violation.objects.get(pk=pk)
        except Violation.DoesNotExist:
            return Response({'detail':'Нарушение не найдено'}, status=status.HTTP_404_NOT_FOUND)
        if request.user.user_type not in ['construction_control','inspector']:
            return Response({'detail': 'Недостаточно прав'}, status=status.HTTP_403_FORBIDDEN)
        if not self._has_recent_visit(request.user, v.project):
            return Response({'detail': 'Нет актуальной отметки посещения'}, status=status.HTTP_400_BAD_REQUEST)
        v.status = 'verified'
        v.verified_at = timezone.now()
        v.verified_by = request.user
        v.save()
        return Response({'status':'ok'})


class ViolationClassifierListAPI(APIView):
    """API для получения списка классификатора нарушений"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Параметры фильтрации
        category = request.query_params.get('category')
        kind = request.query_params.get('kind')
        type_name = request.query_params.get('type')
        search = request.query_params.get('search')
        
        # Базовый кверисет
        queryset = ViolationClassifier.objects.filter(is_active=True)
        
        # Фильтрация
        if category:
            queryset = queryset.filter(category=category)
        if kind:
            queryset = queryset.filter(kind=kind)
        if type_name:
            queryset = queryset.filter(type_name=type_name)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Пагинация
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        total_count = queryset.count()
        items = queryset.order_by('category', 'kind', 'type_name')[offset:offset + limit]
        
        data = []
        for item in items:
            data.append({
                'id': item.id,
                'category': item.category,
                'kind': item.kind,
                'type_name': item.type_name,
                'name': item.name,
                'regulatory_deadline_days': item.regulatory_deadline_days,
                'deadline_display': item.get_deadline_display(),
                'is_active': item.is_active,
                'created_at': item.created_at,
                'updated_at': item.updated_at
            })
        
        return Response({
            'results': data,
            'count': total_count,
            'limit': limit,
            'offset': offset
        })


class ViolationClassifierCategoriesAPI(APIView):
    """API для получения списка категорий, видов и типов"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Получаем уникальные значения
        categories = list(
            ViolationClassifier.objects
            .filter(is_active=True)
            .values_list('category', flat=True)
            .distinct()
            .order_by('category')
        )
        
        kinds = list(
            ViolationClassifier.objects
            .filter(is_active=True)
            .values_list('kind', flat=True)
            .distinct()
            .order_by('kind')
        )
        
        types = list(
            ViolationClassifier.objects
            .filter(is_active=True)
            .values_list('type_name', flat=True)
            .distinct()
            .order_by('type_name')
        )
        
        # Статистика по категориям
        from django.db import models
        category_stats = list(
            ViolationClassifier.objects
            .filter(is_active=True)
            .values('category')
            .annotate(count=models.Count('id'))
            .order_by('category')
        )
        
        return Response({
            'categories': categories,
            'kinds': kinds,
            'types': types,
            'category_stats': category_stats,
            'total_count': ViolationClassifier.objects.filter(is_active=True).count()
        })


def classifier_view(request):
    """Страница классификатора нарушений"""
    from django.shortcuts import render
    
    # Получаем данные для фильтров
    categories = ViolationClassifier.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('category')
    kinds = ViolationClassifier.objects.filter(is_active=True).values_list('kind', flat=True).distinct().order_by('kind')
    types = ViolationClassifier.objects.filter(is_active=True).values_list('type_name', flat=True).distinct().order_by('type_name')
    
    # Получаем все записи классификатора
    classifiers = ViolationClassifier.objects.filter(is_active=True).order_by('category', 'kind', 'type_name')
    
    context = {
        'categories': categories,
        'kinds': kinds,
        'types': types,
        'classifiers': classifiers,
        'total_count': classifiers.count(),
    }
    
    return render(request, 'violations/classifier.html', context)

# Frontend Views
def violation_list(request):
    """Страница нарушений: создание с геометкой, лента нарушений"""
    from projects.models import Project
    from .models import Violation, ViolationType
    projects = Project.objects.all().order_by('name')[:50]
    vtypes = ViolationType.objects.all().order_by('name')[:200]
    items = Violation.objects.select_related('project','violation_type').order_by('-detected_at')[:30]

    options_projects = ''.join([f'<option value="{p.id}">{p.name}</option>' for p in projects])
    options_types = ''.join([f'<option value="{t.id}">{t.name}</option>' for t in vtypes])

    from django.shortcuts import render
    base_context = {
        'all_projects': projects,
        'selected_project': None,
    }
    html_content = f"""
    <!DOCTYPE html>
    <html lang=\"ru\">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Нарушения и контроль - Система управления благоустройством</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-50">
        <script>
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/static/js/sw.js');
        </script>
        <div class="container mx-auto px-4 py-8">
            <div class="bg-white rounded-lg shadow-md p-6 mb-6">
                <div class="flex items-center justify-between mb-4">
                    <h1 class="text-2xl font-bold text-red-700">⚠️ Нарушения и контроль</h1>
                    <a href="/" class="text-blue-600 hover:underline">← На главную</a>
                </div>
                
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Создание нарушения -->
                    <div class="border rounded-lg p-4">
                        <h3 class="font-semibold mb-2">Добавить нарушение</h3>
                        <div class="text-xs text-gray-600 mb-2">Для создания требуется отметка посещения (кнопка ниже)</div>
                        <button onclick="markVisit()" class="mb-3 inline-flex items-center px-3 py-1.5 rounded bg-blue-600 text-white">Отметить посещение</button>
                        <form id="violation-form" class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div class="md:col-span-2">
                                <label class="block text-sm text-gray-700 mb-1">Проект</label>
                                <select id="v-project" class="w-full border rounded px-2 py-1" required>
                                    <option value="">Выберите проект</option>
                                    {options_projects}
                                </select>
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-sm text-gray-700 mb-1">Тип нарушения</label>
                                <select id="v-type" class="w-full border rounded px-2 py-1" required>
                                    <option value="">Выберите тип</option>
                                    {options_types}
                                </select>
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-sm text-gray-700 mb-1">Заголовок</label>
                                <input id="v-title" type="text" class="w-full border rounded px-2 py-1" required>
                            </div>
                            <div class="md:col-span-2">
                                <label class="block text-sm text-gray-700 mb-1">Описание</label>
                                <textarea id="v-desc" class="w-full border rounded px-2 py-1" rows="3"></textarea>
                            </div>
                            <div class="md:col-span-2">
                                <button type="submit" class="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">Создать нарушение</button>
                            </div>
                        </form>
                        <div id="v-status" class="text-sm mt-2"></div>
                    </div>

                    <!-- Лента нарушений -->
                    <div class="border rounded-lg p-4">
                        <h3 class="font-semibold mb-2">Последние нарушения</h3>
                        <div class="divide-y">
    """
    
    for v in items:
        html_content += f"""
                            <div class=\"py-2\">
                                <div class=\"flex items-center justify-between\">
                                    <div class=\"font-medium\">{v.title}</div>
                                    <span class=\"px-2 py-1 rounded text-xs bg-gray-100\">{v.get_status_display()}</span>
                                </div>
                                <div class=\"text-xs text-gray-600\">{v.project.name} • {v.violation_type.name}</div>
                            </div>
        """

    html_content += """
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            async function markVisit() {
                if (!navigator.geolocation) { alert('Геолокация недоступна'); return; }
                navigator.geolocation.getCurrentPosition(async (pos) => {
                    try {
                        const projectId = document.getElementById('v-project').value || (document.querySelector('#v-project option[value]')?.value);
                        const res = await fetch('/api/accounts/visit/', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ project_id: projectId, latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: Math.round(pos.coords.accuracy || 0) })
                        });
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.detail || 'Ошибка отметки');
                        alert('Посещение зафиксировано');
                    } catch (e) { alert('Ошибка: ' + e.message); }
                }, (err) => { alert('Геолокация: ' + err.message); });
            }

            const form = document.getElementById('violation-form');
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const payload = {
                    project_id: document.getElementById('v-project').value,
                    violation_type_id: document.getElementById('v-type').value,
                    title: document.getElementById('v-title').value,
                    description: document.getElementById('v-desc').value,
                    location: '0,0'
                };
                const res = await fetch('/api/violations/items/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const data = await res.json();
                const st = document.getElementById('v-status');
                if (res.ok) { st.textContent = 'Нарушение создано'; st.className = 'text-green-600 text-sm'; }
                else { st.textContent = 'Ошибка: ' + (data.detail || 'не удалось'); st.className = 'text-red-600 text-sm'; }
            });
        </script>
    </body>
    </html>
    """
    from django.http import HttpResponse
    return render(request, 'violations/list.html', { **base_context })
