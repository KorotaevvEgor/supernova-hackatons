from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class NotificationManager(models.Manager):
    def create_notification(self, recipient, title, message, notification_type='info', related_object=None):
        """Создание уведомления"""
        notification = self.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            related_object_type=related_object.__class__.__name__ if related_object else None,
            related_object_id=related_object.id if related_object else None
        )
        return notification
    
    def unread_for_user(self, user):
        """Получить непрочитанные уведомления для пользователя"""
        return self.filter(recipient=user, is_read=False).order_by('-created_at')
    
    def mark_all_read(self, user):
        """Отметить все уведомления как прочитанные"""
        return self.filter(recipient=user, is_read=False).update(is_read=True, read_at=timezone.now())


class Notification(models.Model):
    """Модель уведомлений для пользователей"""
    
    TYPE_CHOICES = [
        ('info', 'Информация'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
        ('success', 'Успех'),
        ('task', 'Задача'),
        ('inspection', 'Проверка'),
        ('violation', 'Нарушение'),
        ('project_update', 'Обновление проекта'),
    ]
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_notifications',
        verbose_name="Получатель"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок"
    )
    
    message = models.TextField(
        verbose_name="Сообщение"
    )
    
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='info',
        verbose_name="Тип уведомления"
    )
    
    related_object_type = models.CharField(
        max_length=100,
        null=True, blank=True,
        verbose_name="Тип связанного объекта"
    )
    
    related_object_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ID связанного объекта"
    )
    
    is_read = models.BooleanField(
        default=False,
        verbose_name="Прочитано"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    objects = NotificationManager()
    
    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} -> {self.recipient.username}"
    
    def mark_read(self):
        """Отметить как прочитанное"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


def notify_project_activation(project, activated_by):
    """Уведомление об активации проекта"""
    try:
        # Уведомляем прораба
        if project.foreman:
            Notification.objects.create_notification(
                recipient=project.foreman,
                title=f"Проект активирован: {project.name}",
                message=f"Проект был активирован службой строительного контроля. Вы назначены ответственным прорабом. Проверьте задачи и начните выполнение работ.",
                notification_type='project_update',
                related_object=project
            )
        
        # Уведомляем всех инспекторов
        inspectors = User.objects.filter(role='inspector', is_active=True)
        for inspector in inspectors:
            Notification.objects.create_notification(
                recipient=inspector,
                title=f"Новый активный проект: {project.name}",
                message=f"Проект готов к проверкам. Вы можете запланировать необходимые инспекции.",
                notification_type='project_update',
                related_object=project
            )
    except Exception as e:
        logger.error(f"Error sending project activation notifications: {str(e)}")


def notify_task_completion(task, completed_by):
    """Уведомление о выполнении задачи"""
    try:
        # Уведомляем строительный контроль
        if task.project.control_service:
            Notification.objects.create_notification(
                recipient=task.project.control_service,
                title=f"Задача выполнена: {task.title}",
                message=f"Прораб {completed_by.get_full_name() or completed_by.username} отметил задачу как выполненную в проекте {task.project.name}.",
                notification_type='task',
                related_object=task
            )
        
        # Если это критическая задача - уведомляем инспекторов
        if task.priority == 'critical':
            inspectors = User.objects.filter(role='inspector', is_active=True)
            for inspector in inspectors:
                Notification.objects.create_notification(
                    recipient=inspector,
                    title=f"Критическая задача выполнена: {task.title}",
                    message=f"Критическая задача была выполнена в проекте {task.project.name}. Рекомендуется провести проверку.",
                    notification_type='task',
                    related_object=task
                )
    except Exception as e:
        logger.error(f"Error sending task completion notifications: {str(e)}")


def notify_inspection_scheduled(inspection):
    """Уведомление о запланированной проверке"""
    try:
        # Уведомляем прораба
        if inspection.project.foreman:
            Notification.objects.create_notification(
                recipient=inspection.project.foreman,
                title=f"Запланирована проверка: {inspection.get_inspection_type_display()}",
                message=f"Инспектор {inspection.inspector.get_full_name() or inspection.inspector.username} запланировал проверку на {inspection.scheduled_date.strftime('%d.%m.%Y %H:%M')}",
                notification_type='inspection',
                related_object=inspection
            )
        
        # Уведомляем строительный контроль
        if inspection.project.control_service:
            Notification.objects.create_notification(
                recipient=inspection.project.control_service,
                title=f"Запланирована проверка проекта: {inspection.project.name}",
                message=f"Инспектор запланировал {inspection.get_inspection_type_display()} на {inspection.scheduled_date.strftime('%d.%m.%Y %H:%M')}",
                notification_type='inspection',
                related_object=inspection
            )
    except Exception as e:
        logger.error(f"Error sending inspection scheduled notifications: {str(e)}")


def notify_inspection_completed(inspection):
    """Уведомление о завершении проверки"""
    try:
        result_text = {
            'passed': 'успешно пройдена',
            'failed': 'не пройдена',
            'partial': 'пройдена частично'
        }.get(inspection.result, 'завершена')
        
        # Уведомляем прораба
        if inspection.project.foreman:
            Notification.objects.create_notification(
                recipient=inspection.project.foreman,
                title=f"Проверка завершена: {inspection.get_inspection_type_display()}",
                message=f"Проверка {result_text}. {inspection.notes if inspection.notes else ''}",
                notification_type='inspection',
                related_object=inspection
            )
        
        # Уведомляем строительный контроль
        if inspection.project.control_service:
            Notification.objects.create_notification(
                recipient=inspection.project.control_service,
                title=f"Результат проверки: {inspection.project.name}",
                message=f"{inspection.get_inspection_type_display()} {result_text}. Готовность проекта: {inspection.project.readiness_score}%",
                notification_type='inspection',
                related_object=inspection
            )
    except Exception as e:
        logger.error(f"Error sending inspection completed notifications: {str(e)}")


def notify_work_reported(work, reported_by):
    """Уведомление об отчете по работам"""
    try:
        # Уведомляем строительный контроль
        if work.project.control_service:
            status_text = {
                'in_progress': 'начата',
                'completed': 'завершена'
            }.get(work.status, 'обновлена')
            
            Notification.objects.create_notification(
                recipient=work.project.control_service,
                title=f"Отчет по работам: {work.name}",
                message=f"Прораб сообщает: работа {status_text}. Проект {work.project.name}, готовность: {work.project.completion_percentage}%",
                notification_type='project_update',
                related_object=work
            )
    except Exception as e:
        logger.error(f"Error sending work reported notifications: {str(e)}")


def notify_project_ready_for_completion(project):
    """Уведомление о готовности проекта к сдаче"""
    try:
        if project.readiness_score >= 95:
            # Уведомляем строительный контроль
            if project.control_service:
                Notification.objects.create_notification(
                    recipient=project.control_service,
                    title=f"Проект готов к сдаче: {project.name}",
                    message=f"Готовность проекта достигла {project.readiness_score}%. Проект может быть закрыт.",
                    notification_type='success',
                    related_object=project
                )
            
            # Уведомляем прораба
            if project.foreman:
                Notification.objects.create_notification(
                    recipient=project.foreman,
                    title=f"Проект готов к сдаче: {project.name}",
                    message=f"Поздравляем! Готовность проекта {project.readiness_score}%. Ожидайте окончательной приемки.",
                    notification_type='success',
                    related_object=project
                )
    except Exception as e:
        logger.error(f"Error sending project ready notifications: {str(e)}")


def notify_violation_created(violation):
    """Уведомление о создании нарушения"""
    try:
        # Уведомляем прораба
        if violation.project.foreman:
            severity_text = {
                'low': 'незначительное',
                'medium': 'среднее',
                'high': 'серьезное',
                'critical': 'критическое'
            }.get(violation.severity, '')
            
            Notification.objects.create_notification(
                recipient=violation.project.foreman,
                title=f"Обнаружено нарушение: {violation.title}",
                message=f"Инспектор зафиксировал {severity_text} нарушение. Требуется устранение до {violation.deadline.strftime('%d.%m.%Y') if violation.deadline else 'как можно скорее'}.",
                notification_type='violation',
                related_object=violation
            )
        
        # Уведомляем строительный контроль
        if violation.project.control_service:
            Notification.objects.create_notification(
                recipient=violation.project.control_service,
                title=f"Нарушение в проекте: {violation.project.name}",
                message=f"Зафиксировано нарушение: {violation.title}. Контролируйте процесс устранения.",
                notification_type='violation',
                related_object=violation
            )
    except Exception as e:
        logger.error(f"Error sending violation created notifications: {str(e)}")


def notify_violation_resolved(violation, resolved_by):
    """Уведомление об устранении нарушения"""
    try:
        # Уведомляем инспектора, создавшего нарушение
        if violation.created_by:
            Notification.objects.create_notification(
                recipient=violation.created_by,
                title=f"Нарушение устранено: {violation.title}",
                message=f"Прораб сообщает об устранении нарушения в проекте {violation.project.name}. Требуется проверка.",
                notification_type='violation',
                related_object=violation
            )
        
        # Уведомляем строительный контроль
        if violation.project.control_service:
            Notification.objects.create_notification(
                recipient=violation.project.control_service,
                title=f"Нарушение устранено: {violation.project.name}",
                message=f"Прораб сообщил об устранении нарушения: {violation.title}",
                notification_type='success',
                related_object=violation
            )
    except Exception as e:
        logger.error(f"Error sending violation resolved notifications: {str(e)}")


def get_user_notification_stats(user):
    """Получить статистику уведомлений пользователя"""
    try:
        unread_count = Notification.objects.filter(recipient=user, is_read=False).count()
        total_count = Notification.objects.filter(recipient=user).count()
        
        # Группировка по типам
        type_stats = {}
        for notification_type, _ in Notification.TYPE_CHOICES:
            count = Notification.objects.filter(
                recipient=user, 
                notification_type=notification_type, 
                is_read=False
            ).count()
            if count > 0:
                type_stats[notification_type] = count
        
        return {
            'unread_count': unread_count,
            'total_count': total_count,
            'type_stats': type_stats
        }
    except Exception as e:
        logger.error(f"Error getting notification stats for user {user.id}: {str(e)}")
        return {'unread_count': 0, 'total_count': 0, 'type_stats': {}}