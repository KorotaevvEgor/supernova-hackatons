from django.db import models
from django.conf import settings
from django.utils import timezone
from projects.models import Project
from materials.models import MaterialType


class ViolationType(models.Model):
    """Классификатор нарушений контрольного органа"""
    
    SEVERITY_CHOICES = [
        ('low', 'Низкая'),
        ('medium', 'Средняя'),
        ('high', 'Высокая'),
        ('critical', 'Критическая'),
    ]
    
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Код нарушения"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name="Наименование"
    )
    
    description = models.TextField(
        verbose_name="Описание",
        blank=True
    )
    
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium',
        verbose_name="Серьёзность"
    )
    
    mandatory_photo = models.BooleanField(
        default=False,
        verbose_name="Обязательно фото"
    )
    
    mandatory_location = models.BooleanField(
        default=True,
        verbose_name="Обязательна геолокация"
    )
    
    default_deadline_days = models.IntegerField(
        default=30,
        verbose_name="Срок устранения по умолчанию (дни)"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Тип нарушения"
        verbose_name_plural = "Типы нарушений"
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class InspectorViolation(models.Model):
    """Нарушения, выявленные инспектором контрольного органа"""
    
    STATUS_CHOICES = [
        ('detected', 'Выявлено'),
        ('notified', 'Уведомлено'),
        ('in_correction', 'На устранении'),
        ('corrected', 'Устранено'),
        ('verified', 'Проверено'),
        ('closed', 'Закрыто'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='inspector_violations',
        verbose_name="Проект"
    )
    
    violation_type = models.ForeignKey(
        ViolationType,
        on_delete=models.PROTECT,
        related_name='violations',
        null=True,
        blank=True,
        verbose_name="Тип нарушения"
    )
    
    violation_classifier = models.ForeignKey(
        'violations.ViolationClassifier',
        on_delete=models.PROTECT,
        related_name='inspector_violations',
        verbose_name="Классификатор нарушения",
        help_text="Тип замечания из классификатора производства работ"
    )
    
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='detected_violations',
        verbose_name="Инспектор"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Краткое описание"
    )
    
    description = models.TextField(
        verbose_name="Детальное описание"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='detected',
        verbose_name="Статус"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name="Приоритет"
    )
    
    # Геолокация нарушения
    location_lat = models.FloatField(
        null=True, blank=True,
        verbose_name="Широта"
    )
    
    location_lng = models.FloatField(
        null=True, blank=True,
        verbose_name="Долгота"
    )
    
    location_description = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Описание места"
    )
    
    # Верификация местонахождения инспектора
    VERIFICATION_METHOD_CHOICES = [
        ('qr_code', 'QR-код'),
        ('geolocation', 'Геолокация'),
    ]
    
    verification_method = models.CharField(
        max_length=20,
        choices=VERIFICATION_METHOD_CHOICES,
        null=True,
        blank=True,
        verbose_name="Метод подтверждения местонахождения"
    )
    
    qr_code_verified = models.ForeignKey(
        'projects.ProjectQRCode',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_violations',
        verbose_name="QR-код для верификации"
    )
    
    # Временные рамки
    detected_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время обнаружения"
    )
    
    deadline = models.DateField(
        verbose_name="Срок устранения"
    )
    
    corrected_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Время устранения"
    )
    
    verified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Время проверки"
    )
    
    # Ответственные за устранение
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_inspector_violations',
        verbose_name="Ответственный за устранение"
    )
    
    # Комментарии
    correction_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий об устранении"
    )
    
    inspector_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий инспектора при проверке"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Нарушение инспектора"
        verbose_name_plural = "Нарушения инспектора"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.violation_type.code}: {self.title} ({self.project.name})"
    
    @property
    def is_overdue(self):
        """Проверка просрочки устранения"""
        if self.status in ['corrected', 'verified', 'closed']:
            return False
        return timezone.now().date() > self.deadline
    
    @property
    def days_remaining(self):
        """Дни до истечения срока"""
        if self.status in ['corrected', 'verified', 'closed']:
            return 0
        delta = self.deadline - timezone.now().date()
        return max(0, delta.days)
    
    def can_be_corrected_by(self, user):
        """Проверка прав на устранение"""
        return (
            self.assigned_to == user or 
            (hasattr(user, 'user_type') and user.user_type == 'foreman' and 
             self.project.foreman == user)
        )
    
    def get_suggested_deadline_days(self):
        """Получить рекомендуемый срок устранения в днях"""
        # Приоритет: классификатор производства работ, затем тип нарушения, затем 30 дней
        if self.violation_classifier and self.violation_classifier.regulatory_deadline_days:
            return self.violation_classifier.regulatory_deadline_days
        elif self.violation_type and self.violation_type.default_deadline_days:
            return self.violation_type.default_deadline_days
        else:
            return 30  # по умолчанию
    
    def save(self, *args, **kwargs):
        # Автоматически вычисляем deadline при создании
        if not self.deadline:
            from datetime import timedelta
            suggested_days = self.get_suggested_deadline_days()
            self.deadline = self.detected_at.date() + timedelta(days=suggested_days)
        super().save(*args, **kwargs)


class ViolationPhoto(models.Model):
    """Фотографии к нарушениям"""
    
    PHOTO_TYPE_CHOICES = [
        ('violation', 'Фото нарушения'),
        ('correction', 'Фото устранения'),
        ('verification', 'Фото проверки'),
    ]
    
    violation = models.ForeignKey(
        InspectorViolation,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Нарушение"
    )
    
    photo = models.ImageField(
        upload_to='violation_photos/',
        verbose_name="Фотография"
    )
    
    photo_type = models.CharField(
        max_length=20,
        choices=PHOTO_TYPE_CHOICES,
        default='violation',
        verbose_name="Тип фото"
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Описание"
    )
    
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Автор фото"
    )
    
    taken_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время съёмки"
    )
    
    location_lat = models.FloatField(
        null=True, blank=True,
        verbose_name="Широта"
    )
    
    location_lng = models.FloatField(
        null=True, blank=True,
        verbose_name="Долгота"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Фото нарушения"
        verbose_name_plural = "Фото нарушений"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Фото {self.get_photo_type_display()} - {self.violation.title}"


class LabSampleRequest(models.Model):
    """Заявки на лабораторные пробы материалов"""
    
    STATUS_CHOICES = [
        ('requested', 'Запрошено'),
        ('scheduled', 'Запланировано'),
        ('sampling', 'Отбор проб'),
        ('testing', 'Тестирование'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]
    
    URGENCY_CHOICES = [
        ('normal', 'Обычная'),
        ('urgent', 'Срочная'),
        ('critical', 'Критическая'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='lab_sample_requests',
        verbose_name="Проект"
    )
    
    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
        related_name='lab_requests',
        verbose_name="Тип материала"
    )
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_samples',
        verbose_name="Заявитель"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='requested',
        verbose_name="Статус"
    )
    
    urgency = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        default='normal',
        verbose_name="Срочность"
    )
    
    # Детали заявки
    reason = models.TextField(
        verbose_name="Причина отбора проб"
    )
    
    required_tests = models.TextField(
        verbose_name="Требуемые анализы",
        help_text="Перечень необходимых лабораторных анализов"
    )
    
    sample_quantity = models.CharField(
        max_length=100,
        verbose_name="Количество образцов",
        help_text="Например: '3 образца по 1кг'"
    )
    
    # Местоположение отбора
    sampling_location_lat = models.FloatField(
        null=True, blank=True,
        verbose_name="Широта места отбора"
    )
    
    sampling_location_lng = models.FloatField(
        null=True, blank=True,
        verbose_name="Долгота места отбора"
    )
    
    sampling_location_description = models.CharField(
        max_length=500,
        verbose_name="Описание места отбора"
    )
    
    # Временные рамки
    requested_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Время заявки"
    )
    
    scheduled_sampling_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Запланированная дата отбора"
    )
    
    actual_sampling_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Фактическая дата отбора"
    )
    
    expected_results_date = models.DateField(
        null=True, blank=True,
        verbose_name="Ожидаемая дата результатов"
    )
    
    # Исполнители
    lab_organization = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Лаборатория"
    )
    
    lab_contact = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Контакт лаборатории"
    )
    
    sampling_specialist = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Специалист по отбору проб"
    )
    
    # Результаты
    results_summary = models.TextField(
        blank=True,
        verbose_name="Краткая сводка результатов"
    )
    
    results_file = models.FileField(
        upload_to='lab_results/',
        null=True, blank=True,
        verbose_name="Файл с результатами"
    )
    
    compliance_status = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Статус соответствия",
        help_text="Соответствует/Не соответствует нормам"
    )
    
    # Комментарии
    inspector_notes = models.TextField(
        blank=True,
        verbose_name="Примечания инспектора"
    )
    
    lab_notes = models.TextField(
        blank=True,
        verbose_name="Примечания лаборатории"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Заявка на лабораторные пробы"
        verbose_name_plural = "Заявки на лабораторные пробы"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Проба {self.material_type.name} - {self.project.name}"
    
    @property
    def is_overdue(self):
        """Проверка просрочки выполнения"""
        if self.status in ['completed', 'cancelled']:
            return False
        if self.expected_results_date:
            return timezone.now().date() > self.expected_results_date
        return False


class ProjectActivationApproval(models.Model):
    """Одобрения активации объектов инспектором"""
    
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('conditional', 'Условно одобрено'),
    ]
    
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='activation_approval',
        verbose_name="Проект"
    )
    
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_approvals',
        verbose_name="Инспектор"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    # Проверочный чек-лист
    site_preparation_checked = models.BooleanField(
        default=False,
        verbose_name="Подготовка площадки проверена"
    )
    
    safety_measures_checked = models.BooleanField(
        default=False,
        verbose_name="Меры безопасности проверены"
    )
    
    documentation_checked = models.BooleanField(
        default=False,
        verbose_name="Документация проверена"
    )
    
    environmental_compliance_checked = models.BooleanField(
        default=False,
        verbose_name="Экологические требования проверены"
    )
    
    # Комментарии и заключения
    inspector_conclusion = models.TextField(
        verbose_name="Заключение инспектора"
    )
    
    conditions = models.TextField(
        blank=True,
        verbose_name="Условия одобрения",
        help_text="Условия, которые должны быть выполнены"
    )
    
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Причина отклонения"
    )
    
    # Временные метки
    inspection_date = models.DateTimeField(
        verbose_name="Дата осмотра"
    )
    
    decision_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата решения"
    )
    
    valid_until = models.DateField(
        null=True, blank=True,
        verbose_name="Действительно до"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Одобрение активации проекта"
        verbose_name_plural = "Одобрения активации проектов"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Активация {self.project.name} - {self.get_status_display()}"
    
    @property
    def is_fully_checked(self):
        """Все ли пункты проверены"""
        return all([
            self.site_preparation_checked,
            self.safety_measures_checked,
            self.documentation_checked,
            self.environmental_compliance_checked
        ])
    
    def can_be_approved(self):
        """Может ли быть одобрено"""
        return self.is_fully_checked and self.inspector_conclusion.strip()


class ViolationComment(models.Model):
    """Комментарии к нарушениям"""
    
    violation = models.ForeignKey(
        InspectorViolation,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Нарушение"
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='violation_comments',
        verbose_name="Автор"
    )
    
    comment = models.TextField(
        verbose_name="Комментарий"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Комментарий к нарушению"
        verbose_name_plural = "Комментарии к нарушениям"
        ordering = ['-created_at']
    
    def __str__(self):
        author_name = self.author.get_full_name() or self.author.username
        return f"Комментарий {author_name} к {self.violation.title}"
    
    def get_author_role_display(self):
        """Получить читаемое название роли автора"""
        if hasattr(self.author, 'user_type') and self.author.user_type:
            return self.author.get_user_type_display()
        return "Пользователь"
