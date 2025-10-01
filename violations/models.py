from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class ViolationClassifier(models.Model):
    """Классификатор нарушений производства работ"""
    
    category = models.CharField(
        max_length=255,
        verbose_name="Категория",
        help_text="Основная категория нарушения"
    )
    
    kind = models.CharField(
        max_length=255,
        verbose_name="Вид",
        help_text="Вид нарушения (Устранимое, Неустранимое и т.д.)"
    )
    
    type_name = models.CharField(
        max_length=255,
        verbose_name="Тип",
        help_text="Тип нарушения (Грубое, Значительное и т.д.)"
    )
    
    name = models.TextField(
        verbose_name="Наименование",
        help_text="Полное наименование нарушения"
    )
    
    regulatory_deadline_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Регламентный срок устранения (дни)",
        help_text="Количество дней на устранение нарушения"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Классификатор нарушения"
        verbose_name_plural = "Классификатор нарушений"
        ordering = ['category', 'kind', 'type_name']
        unique_together = [['category', 'kind', 'type_name', 'name']]
    
    def __str__(self):
        return f"{self.category} - {self.name[:50]}..."
    
    def get_deadline_display(self):
        """Возвращает удобочитаемый формат срока устранения"""
        if self.regulatory_deadline_days is None:
            return "Не установлен"
        elif self.regulatory_deadline_days == 1:
            return "1 день"
        elif self.regulatory_deadline_days < 5:
            return f"{self.regulatory_deadline_days} дня"
        else:
            return f"{self.regulatory_deadline_days} дней"


class ViolationCategory(models.Model):
    """Категории нарушений"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название категории"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    class Meta:
        verbose_name = "Категория нарушения"
        verbose_name_plural = "Категории нарушений"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class ViolationType(models.Model):
    """Типы нарушений (на основе классификатора)"""
    
    SOURCE_CHOICES = [
        ('construction_control', 'Служба строительного контроля'),
        ('inspector', 'Контрольный орган'),
    ]
    
    category = models.ForeignKey(
        ViolationCategory,
        on_delete=models.PROTECT,
        related_name='violation_types',
        verbose_name="Категория"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код нарушения"
    )
    
    name = models.CharField(
        max_length=500,
        verbose_name="Наименование нарушения"
    )
    
    type_field = models.CharField(
        max_length=255,
        verbose_name="Тип"
    )
    
    kind = models.CharField(
        max_length=255,
        verbose_name="Вид"
    )
    
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        verbose_name="Источник классификатора"
    )
    
    regulatory_deadline_days = models.IntegerField(
        verbose_name="Регламентный срок устранения (дни)"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    class Meta:
        verbose_name = "Тип нарушения"
        verbose_name_plural = "Типы нарушений"
        ordering = ['category', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Violation(models.Model):
    """нарушения на объектах благоустройства"""
    
    STATUS_CHOICES = [
        ('open', 'Открыто'),
        ('in_progress', 'В работе'),
        ('resolved', 'Устранено'),
        ('verified', 'Проверено'),
        ('rejected', 'Отклонено'),
        ('overdue', 'Просрочено'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критичный'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='violations',
        verbose_name="Объект"
    )
    
    violation_type = models.ForeignKey(
        ViolationType,
        on_delete=models.PROTECT,
        verbose_name="Тип нарушения"
    )
    
    violation_classifier = models.ForeignKey(
        ViolationClassifier,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Классификатор нарушения",
        help_text="Классификатор производства работ"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок"
    )
    
    description = models.TextField(
        verbose_name="Описание нарушения"
    )
    
    location = models.CharField(
        max_length=100,
        verbose_name="Место нарушения",
        help_text="Координаты в формате 'lat,lng'"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='open',
        verbose_name="Статус"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name="Приоритет"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_violations',
        verbose_name="Создал"
    )
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_violations',
        null=True, blank=True,
        verbose_name="Ответственный за устранение"
    )
    
    detected_at = models.DateTimeField(
        verbose_name="Дата и время обнаружения"
    )
    
    deadline = models.DateTimeField(
        verbose_name="Срок устранения"
    )
    
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата устранения"
    )
    
    verified_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата проверки"
    )
    
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='verified_violations',
        null=True, blank=True,
        verbose_name="Проверил"
    )
    
    photos = models.JSONField(
        null=True, blank=True,
        verbose_name="Фотографии"
    )
    
    documents = models.JSONField(
        null=True, blank=True,
        verbose_name="Документы"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )
    
    worker_count = models.IntegerField(
        null=True, blank=True,
        verbose_name="Количество рабочих"
    )
    
    equipment_count = models.IntegerField(
        null=True, blank=True,
        verbose_name="Количество техники"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Нарушение"
        verbose_name_plural = "Нарушения"
        ordering = ['-detected_at']
    
    def __str__(self):
        return f"{self.title} ({self.project.name})"
    
    def save(self, *args, **kwargs):
        # Автоматическое вычисление срока устранения
        if not self.deadline and self.detected_at:
            # Приоритет: классификатор производства работ, затем старый классификатор
            if self.violation_classifier and self.violation_classifier.regulatory_deadline_days:
                self.deadline = self.detected_at + timedelta(days=self.violation_classifier.regulatory_deadline_days)
            elif self.violation_type:
                self.deadline = self.detected_at + timedelta(days=self.violation_type.regulatory_deadline_days)
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Просрочено ли нарушение"""
        if self.status not in ['resolved', 'verified']:
            return timezone.now() > self.deadline
        return False
    
    @property
    def days_overdue(self):
        """Количество дней просрочки"""
        if self.is_overdue:
            delta = timezone.now() - self.deadline
            return delta.days
        return 0
    
    @property
    def days_until_deadline(self):
        """Количество дней до срока устранения"""
        if self.status not in ['resolved', 'verified'] and not self.is_overdue:
            delta = self.deadline - timezone.now()
            return delta.days
        return 0


class ViolationResolution(models.Model):
    """Устранение нарушений"""
    
    violation = models.ForeignKey(
        Violation,
        on_delete=models.CASCADE,
        related_name='resolutions',
        verbose_name="Нарушение"
    )
    
    description = models.TextField(
        verbose_name="Описание мер по устранению"
    )
    
    photos = models.JSONField(
        null=True, blank=True,
        verbose_name="Фотографии устранения"
    )
    
    documents = models.JSONField(
        null=True, blank=True,
        verbose_name="Документы"
    )
    
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='resolved_violations',
        verbose_name="Кто устранил"
    )
    
    location = models.CharField(
        max_length=100,
        null=True, blank=True,
        verbose_name="Место устранения",
        help_text="Координаты в формате 'lat,lng'"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Устранение нарушения"
        verbose_name_plural = "Устранения нарушений"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Устранение: {self.violation.title}"
