from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """Расширенная модель пользователя"""
    
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='custom_user_set',
        help_text='The groups this user belongs to.',
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='custom_user_set',
        help_text='Specific permissions for this user.',
    )
    
    USER_TYPE_CHOICES = [
        ('construction_control', 'Служба строительного контроля'),
        ('foreman', 'Прораб'),
        ('inspector', 'Инспектор контрольного органа'),
    ]
    
    user_type = models.CharField(
        max_length=20, 
        choices=USER_TYPE_CHOICES,
        verbose_name="Тип пользователя"
    )
    
    phone = models.CharField(
        max_length=15, 
        blank=True, 
        verbose_name="Телефон"
    )
    
    organization = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Организация"
    )
    
    position = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name="Должность"
    )
    
    avatar = models.ImageField(
        upload_to='avatars/', 
        blank=True, 
        null=True,
        verbose_name="Аватар"
    )
    
    is_active_on_site = models.BooleanField(
        default=False,
        verbose_name="Активен на объекте"
    )
    
    last_location = models.CharField(
        max_length=100,
        null=True, 
        blank=True,
        verbose_name="Последнее местоположение",
        help_text="Координаты в формате 'lat,lng'"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_user_type_display()})"
    
    @property
    def can_manage_projects(self):
        """Может ли пользователь управлять проектами"""
        return self.user_type == 'construction_control'
    
    @property
    def can_control_materials(self):
        """Может ли пользователь контролировать материалы"""
        return self.user_type == 'foreman'
    
    @property
    def can_create_violations(self):
        """Может ли пользователь создавать нарушения"""
        return self.user_type in ['construction_control', 'inspector']
    


class UserSession(models.Model):
    """Сессии пользователей для отслеживания активности"""
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    
    location = models.CharField(
        max_length=100,
        verbose_name="Местоположение",
        help_text="Координаты в формате 'lat,lng'"
    )
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        null=True, blank=True,
        verbose_name="Проект"
    )
    
    session_start = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Начало сессии"
    )
    
    session_end = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Конец сессии"
    )
    
    is_verified = models.BooleanField(
        default=False,
        verbose_name="Подтверждено геолокацией"
    )
    
    class Meta:
        verbose_name = "Сессия пользователя"
        verbose_name_plural = "Сессии пользователей"
    
    def __str__(self):
        return f"{self.user.username} - {self.session_start}"


class Visit(models.Model):
    """Фиксация посещений объекта с геопозицией"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, verbose_name="Проект")
    latitude = models.DecimalField(max_digits=10, decimal_places=7, verbose_name="Широта")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, verbose_name="Долгота")
    accuracy = models.IntegerField(null=True, blank=True, verbose_name="Точность, м")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Посещение"
        verbose_name_plural = "Посещения"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} @ {self.project.name} ({self.latitude},{self.longitude})"

class Notification(models.Model):
    """Уведомления для пользователей"""
    
    NOTIFICATION_TYPES = [
        ('deadline_warning', 'Предупреждение о сроках'),
        ('violation_assigned', 'Назначено нарушение'),
        ('material_delivered', 'Доставлен материал'),
        ('work_verified', 'Работа подтверждена'),
        ('schedule_changed', 'Изменен график'),
    ]
    
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Получатель"
    )
    
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name="Тип уведомления"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок"
    )
    
    message = models.TextField(
        verbose_name="Сообщение"
    )
    
    is_read = models.BooleanField(
        default=False,
        verbose_name="Прочитано"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    
    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username}"


class QRToken(models.Model):
    """Временные QR-токены для подтверждения присутствия прораба на объекте"""
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Прораб (создатель)"
    )
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        verbose_name="Проект",
        help_text="Проект, на котором находится прораб"
    )
    
    token = models.CharField(
        max_length=64,
        unique=True,
        verbose_name="Токен"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создан"
    )
    
    expires_at = models.DateTimeField(
        verbose_name="Истекает"
    )
    
    is_used = models.BooleanField(
        default=False,
        verbose_name="Использован"
    )
    
    used_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Использован"
    )
    
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_qr_tokens',
        verbose_name="Подтвержден контролером"
    )
    
    verified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Время подтверждения"
    )
    
    class Meta:
        verbose_name = "QR-токен"
        verbose_name_plural = "QR-токены"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"QR-токен {self.token[:8]}... (прораб: {self.created_by.username}, проект: {self.project.name})"
    
    @property
    def is_expired(self):
        """Проверяет, истек ли токен"""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        """Проверяет, валиден ли токен"""
        return not self.is_expired and not self.is_used
    
    @property
    def is_verified(self):
        """Проверяет, подтвержден ли токен"""
        return self.verified_by is not None and self.verified_at is not None
    
    def verify(self, controller_user):
        """Подтверждает токен контролером"""
        from django.utils import timezone
        if self.is_valid and not self.is_verified:
            self.verified_by = controller_user
            self.verified_at = timezone.now()
            self.is_used = True
            self.used_at = timezone.now()
            self.save()
            return True
        return False
