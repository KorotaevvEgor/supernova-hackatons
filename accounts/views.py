from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import secrets
import qrcode
import io
import base64
from .models import Visit, QRToken
from projects.models import Project

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({'message': 'User profile endpoint', 'user': request.user.username})

class VisitCreateView(APIView):
    """Создание записи посещения объекта с геопозицией"""
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            project_id = request.data.get('project_id')
            lat = request.data.get('latitude')
            lng = request.data.get('longitude')
            accuracy = request.data.get('accuracy')
            if not all([project_id, lat, lng]):
                return Response({'detail': 'project_id, latitude, longitude обязательны'}, status=status.HTTP_400_BAD_REQUEST)
            project = Project.objects.get(pk=project_id)
            visit = Visit.objects.create(
                user=request.user,
                project=project,
                latitude=lat,
                longitude=lng,
                accuracy=accuracy or None,
            )
            return Response({'status': 'ok', 'visit_id': visit.id, 'timestamp': timezone.localtime(visit.created_at).isoformat()})
        except Project.DoesNotExist:
            return Response({'detail': 'Проект не найден'}, status=status.HTTP_404_NOT_FOUND)




@login_required
def foreman_identification(request):
    """Страница идентификации для прораба"""
    # Проверяем, что пользователь - прораб
    if request.user.user_type != 'foreman':
        return redirect('login')
    
    from projects.models import Project
    
    # Получаем проекты прораба
    user_projects = Project.objects.filter(foreman=request.user)
    
    # Получаем статистику QR-токенов
    total_tokens = QRToken.objects.filter(created_by=request.user).count()
    active_tokens = QRToken.objects.filter(
        created_by=request.user,
        expires_at__gt=timezone.now(),
        is_used=False
    ).count()
    verified_tokens = QRToken.objects.filter(
        created_by=request.user,
        verified_by__isnull=False
    ).count()
    
    context = {
        'user': request.user,
        'user_projects': user_projects,
        'stats': {
            'total_tokens': total_tokens,
            'active_tokens': active_tokens,
            'verified_tokens': verified_tokens,
        }
    }
    
    return render(request, 'foreman/identification.html', context)


@login_required
@require_http_methods(["POST"])
def foreman_generate_qr(request):
    """Генерация QR-кода прорабом"""
    if request.user.user_type != 'foreman':
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        project_id = data.get('project_id')
        
        if not project_id:
            return JsonResponse({'error': 'Не указан проект'}, status=400)
        
        from projects.models import Project
        
        # Проверяем, что прораб назначен на этот проект
        try:
            project = Project.objects.get(id=project_id, foreman=request.user)
        except Project.DoesNotExist:
            return JsonResponse({'error': 'Проект не найден или вы не назначены на него'}, status=404)
        
        # Генерируем уникальный токен
        token = secrets.token_urlsafe(32)
        
        # Вычисляем время истечения (15 секунд)
        expires_at = timezone.now() + timezone.timedelta(seconds=15)
        
        # Создаем запись в базе данных
        qr_token = QRToken.objects.create(
            created_by=request.user,
            project=project,
            token=token,
            expires_at=expires_at
        )
        
        # Создаем QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Данные для QR-кода
        qr_data = {
            'type': 'foreman_presence',
            'token': token,
            'foreman_id': request.user.id,
            'foreman_name': request.user.get_full_name() or request.user.username,
            'project_id': project.id,
            'project_name': project.name,
            'expires_at': expires_at.isoformat(),
        }
        
        qr.add_data(str(qr_data))
        qr.make(fit=True)
        
        # Создаем изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертируем в base64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return JsonResponse({
            'success': True,
            'qr_code': f'data:image/png;base64,{img_str}',
            'token': token,
            'project_name': project.name,
            'expires_at': expires_at.isoformat(),
            'expires_in': 15  # секунд
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Ошибка генерации QR-кода: {str(e)}'}, status=500)


@login_required
def control_verify_identity(request):
    """Страница подтверждения идентификации для контроля"""
    # Проверяем, что пользователь - строительный контроль
    if request.user.user_type != 'construction_control':
        return redirect('login')
    
    # Получаем статистику проверок
    total_verifications = QRToken.objects.filter(verified_by=request.user).count()
    today_verifications = QRToken.objects.filter(
        verified_by=request.user,
        verified_at__date=timezone.now().date()
    ).count()
    
    # Последние проверки
    recent_verifications = QRToken.objects.filter(
        verified_by=request.user
    ).select_related('created_by', 'project').order_by('-verified_at')[:10]
    
    context = {
        'user': request.user,
        'stats': {
            'total_verifications': total_verifications,
            'today_verifications': today_verifications,
        },
        'recent_verifications': recent_verifications,
    }
    
    return render(request, 'control/verify_identity.html', context)


@login_required
@require_http_methods(["POST"])
def verify_qr_token(request):
    """Подтверждение QR-токена контролем"""
    if request.user.user_type != 'construction_control':
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    try:
        import json
        data = json.loads(request.body)
        token = data.get('token')
        
        if not token:
            return JsonResponse({'error': 'Не указан токен'}, status=400)
        
        # Ищем токен в базе
        try:
            qr_token = QRToken.objects.select_related('created_by', 'project').get(token=token)
        except QRToken.DoesNotExist:
            return JsonResponse({'error': 'Токен не найден'}, status=404)
        
        # Проверяем валидность
        if qr_token.is_expired:
            return JsonResponse({
                'error': 'Токен истек',
                'expired': True
            }, status=400)
        
        if qr_token.is_verified:
            return JsonResponse({
                'error': 'Токен уже был подтвержден',
                'already_verified': True,
                'verified_by': qr_token.verified_by.get_full_name() or qr_token.verified_by.username,
                'verified_at': qr_token.verified_at.isoformat()
            }, status=400)
        
        # Подтверждаем токен
        if qr_token.verify(request.user):
            return JsonResponse({
                'success': True,
                'message': 'Присутствие подтверждено',
                'foreman_name': qr_token.created_by.get_full_name() or qr_token.created_by.username,
                'project_name': qr_token.project.name,
                'verified_at': qr_token.verified_at.isoformat()
            })
        else:
            return JsonResponse({'error': 'Ошибка подтверждения'}, status=500)
        
    except Exception as e:
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)
