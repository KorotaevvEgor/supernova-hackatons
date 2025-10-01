from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta

from .models import Notification


@login_required
@require_http_methods(["GET"])
def user_notifications(request):
    """API для получения уведомлений пользователя"""
    try:
        # Получаем уведомления текущего пользователя
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')
        
        # Фильтр по статусу прочтения
        is_read = request.GET.get('is_read')
        if is_read is not None:
            is_read = is_read.lower() == 'true'
            notifications = notifications.filter(is_read=is_read)
        
        # Пагинация
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        paginator = Paginator(notifications, page_size)
        notifications_page = paginator.get_page(page)
        
        # Формируем ответ
        notifications_data = []
        for notification in notifications_page:
            notifications_data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'time_ago': get_time_ago(notification.created_at)
            })
        
        # Подсчет непрочитанных уведомлений
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'data': {
                'notifications': notifications_data,
                'unread_count': unread_count,
                'has_next': notifications_page.has_next(),
                'has_previous': notifications_page.has_previous(),
                'page': page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """API для отметки уведомления как прочитанного"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        
        notification.is_read = True
        notification.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Уведомление отмечено как прочитанное'
        })
        
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Уведомление не найдено'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """API для отметки всех уведомлений как прочитанных"""
    try:
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse({
            'success': True,
            'message': f'Отмечено {updated_count} уведомлений как прочитанные'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def get_time_ago(timestamp):
    """Возвращает читаемое время в формате 'X минут назад'"""
    now = timezone.now()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} дн. назад"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} ч. назад"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} мин. назад"
    else:
        return "Только что"