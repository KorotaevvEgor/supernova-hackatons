from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class DocumentType(models.Model):
    """Типы документов"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    required_fields = models.JSONField(
        null=True, blank=True,
        verbose_name="Обязательные поля"
    )
    
    class Meta:
        verbose_name = "Тип документа"
        verbose_name_plural = "Типы документов"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Document(models.Model):
    """Документы по объектам благоустройства"""
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('pending_review', 'На рассмотрении'),
        ('approved', 'Утвержден'),
        ('rejected', 'Отклонен'),
        ('archived', 'В архиве'),
    ]
    
    document_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID документа"
    )
    
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='documents',
        verbose_name="Тип документа"
    )
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Объект"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Название"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        verbose_name="Файл"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Статус"
    )
    
    version = models.PositiveIntegerField(
        default=1,
        verbose_name="Версия"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_documents',
        verbose_name="Создал"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_documents',
        null=True, blank=True,
        verbose_name="Утвердил"
    )
    
    # Метаданные документа
    metadata = models.JSONField(
        null=True, blank=True,
        verbose_name="Метаданные"
    )
    
    # Геопозиция при создании
    creation_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        null=True, blank=True,
        verbose_name="Широта создания"
    )
    
    creation_longitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        null=True, blank=True,
        verbose_name="Долгота создания"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата утверждения"
    )
    
    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} v{self.version} ({self.project.name})"
    
    @property
    def file_size_mb(self):
        """Size of file in MB"""
        if self.file:
            return round(self.file.size / (1024 * 1024), 2)
        return 0


class DocumentComment(models.Model):
    """Комментарии к документам"""
    
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Документ"
    )
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Автор"
    )
    
    content = models.TextField(
        verbose_name="Комментарий"
    )
    
    is_internal = models.BooleanField(
        default=False,
        verbose_name="Внутренний комментарий"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Комментарий к документу"
        verbose_name_plural = "Комментарии к документам"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Комментарий к {self.document.title}"


class OpeningChecklistItem(models.Model):
    """Пункты чек-листа открытия объекта"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    is_required = models.BooleanField(
        default=True,
        verbose_name="Обязательно"
    )
    
    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Порядок"
    )
    
    class Meta:
        verbose_name = "Пункт чек-листа"
        verbose_name_plural = "Пункты чек-листа"
        ordering = ['order']
    
    def __str__(self):
        return self.name


class ProjectOpeningChecklist(models.Model):
    """Чек-лист открытия объекта"""
    
    project = models.OneToOneField(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='opening_checklist',
        verbose_name="Проект"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Создал"
    )
    
    approved_by_inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_checklists',
        null=True, blank=True,
        verbose_name="Одобрен инспектором"
    )
    
    is_completed = models.BooleanField(
        default=False,
        verbose_name="Завершен"
    )
    
    completion_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата завершения"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Чек-лист открытия"
        verbose_name_plural = "Чек-листы открытия"
    
    def __str__(self):
        return f"Чек-лист {self.project.name}"


class ChecklistItemCompletion(models.Model):
    """Выполнение пунктов чек-листа"""
    
    checklist = models.ForeignKey(
        ProjectOpeningChecklist,
        on_delete=models.CASCADE,
        related_name='item_completions',
        verbose_name="Чек-лист"
    )
    
    checklist_item = models.ForeignKey(
        OpeningChecklistItem,
        on_delete=models.CASCADE,
        verbose_name="Пункт чек-листа"
    )
    
    is_completed = models.BooleanField(
        default=False,
        verbose_name="Выполнено"
    )
    
    completion_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по выполнению"
    )
    
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Кем выполнено"
    )
    
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Когда выполнено"
    )
    
    photos = models.JSONField(
        null=True, blank=True,
        verbose_name="Фотографии"
    )
    
    class Meta:
        verbose_name = "Выполнение пункта чек-листа"
        verbose_name_plural = "Выполнения пунктов чек-листа"
        unique_together = ('checklist', 'checklist_item')
    
    def __str__(self):
        status = "Выполнено" if self.is_completed else "Не выполнено"
        return f"{self.checklist_item.name}: {status}"


class WorkSpecification(models.Model):
    """Спецификация работ по проекту"""
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='work_specifications',
        verbose_name="Проект"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    file_source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Источник файла"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Спецификация работ"
        verbose_name_plural = "Спецификации работ"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.project.name})"
    
    @property
    def total_cost(self):
        """Общая стоимость работ"""
        return sum(item.total_cost for item in self.items.all())
    
    @property
    def total_items_count(self):
        """Количество элементов в спецификации"""
        return self.items.count()


class WorkSpecificationItem(models.Model):
    """Элемент спецификации работ"""
    
    specification = models.ForeignKey(
        WorkSpecification,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Спецификация"
    )
    
    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Порядок"
    )
    
    name = models.CharField(
        max_length=500,
        verbose_name="Наименование работ"
    )
    
    unit = models.CharField(
        max_length=50,
        default="шт",
        verbose_name="Единица измерения"
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        default=0,
        verbose_name="Количество"
    )
    
    unit_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Стоимость за единицу"
    )
    
    total_cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Общая стоимость"
    )
    
    class Meta:
        verbose_name = "Элемент спецификации"
        verbose_name_plural = "Элементы спецификации"
        ordering = ['specification', 'order']
    
    def __str__(self):
        return f"{self.order}. {self.name[:50]}..."
    
    def save(self, *args, **kwargs):
        # Автоматически вычисляем общую стоимость
        if self.quantity and self.unit_cost:
            self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
