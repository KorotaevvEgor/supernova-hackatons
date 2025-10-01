from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
import uuid
import qrcode
from io import BytesIO
import base64
import requests
from datetime import datetime, timedelta


class Project(models.Model):
    """Объект благоустройства"""
    
    STATUS_CHOICES = [
        ('planned', 'Запланирован'),
        ('active', 'Активен'),
        ('completed', 'Завершен'),
        ('suspended', 'Приостановлен'),
    ]
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название объекта"
    )
    
    address = models.CharField(
        max_length=500,
        verbose_name="Адрес"
    )
    
    coordinates = models.TextField(
        verbose_name="Координаты полигона",
        help_text="JSON с координатами полигона",
        blank=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='planned',
        verbose_name="Статус"
    )
    
    control_service = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='controlled_projects',
        verbose_name="Ответственный от стройконтроля",
        null=True, blank=True
    )
    
    foreman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_projects',
        verbose_name="Ответственный прораб",
        null=True, blank=True
    )
    
    contract_number = models.CharField(
        max_length=100,
        verbose_name="Номер контракта"
    )
    
    planned_start_date = models.DateField(
        verbose_name="Плановая дата начала"
    )
    
    planned_end_date = models.DateField(
        verbose_name="Плановая дата завершения"
    )
    
    actual_start_date = models.DateField(
        null=True, blank=True,
        verbose_name="Фактическая дата начала"
    )
    
    actual_end_date = models.DateField(
        null=True, blank=True,
        verbose_name="Фактическая дата завершения"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    opening_act = models.FileField(
        upload_to='opening_acts/',
        null=True, blank=True,
        verbose_name="Акт открытия объекта"
    )
    
    opening_checklist_completed = models.BooleanField(
        default=False,
        verbose_name="Чек-лист открытия заполнен"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Объект благоустройства"
        verbose_name_plural = "Объекты благоустройства"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def is_delayed(self):
        if self.status == 'active' and self.planned_end_date:
            return timezone.now().date() > self.planned_end_date
        return False
    
    @property
    def completion_percentage(self):
        """Процент завершения работ"""
        total_works = self.works.count()
        if total_works == 0:
            return 0
        completed_works = self.works.filter(status__in=['completed', 'verified']).count()
        return int((completed_works / total_works) * 100)
    
    @property
    def readiness_score(self):
        """Комплексная оценка готовности проекта (0-100%)"""
        # Базовый вес - выполненные работы (60%)
        works_score = self.completion_percentage * 0.6
        
        # Проверки и одобрения (25%)
        if hasattr(self, 'inspections'):
            total_inspections = self.inspections.count()
            completed_inspections = self.inspections.filter(status='completed').count()
            if total_inspections > 0:
                inspections_score = (completed_inspections / total_inspections) * 25
            else:
                inspections_score = 0
        else:
            inspections_score = 0
        
        # Устраненные нарушения (15%)
        if hasattr(self, 'violations'):
            total_violations = self.violations.count()
            if total_violations > 0:
                resolved_violations = self.violations.filter(status='resolved').count()
                violations_score = (resolved_violations / total_violations) * 15
            else:
                violations_score = 15  # Если нарушений нет - это хорошо
        else:
            violations_score = 15
        
        return min(100, int(works_score + inspections_score + violations_score))
    
    @property
    def workflow_status(self):
        """Статус в workflow процессе"""
        if self.status == 'planned':
            return 'Ожидает активации'
        elif self.status == 'active':
            readiness = self.readiness_score
            if readiness < 30:
                return 'Начальный этап'
            elif readiness < 70:
                return 'В процессе выполнения'
            elif readiness < 95:
                return 'Подготовка к сдаче'
            else:
                return 'Готов к сдаче'
        elif self.status == 'completed':
            return 'Завершен'
        elif self.status == 'suspended':
            return 'Приостановлен'
        return 'Неизвестный статус'
    
    def is_user_member(self, user):
        """Проверяет, является ли пользователь участником проекта"""
        return (
            self.control_service == user or 
            self.foreman == user or
            user.is_staff
        )
    
    def can_be_activated(self, user):
        """Проверка возможности активации проекта"""
        if hasattr(user, 'role') and user.role == 'construction_control':
            return self.status == 'planned' and self.opening_checklist_completed
        return False
    
    def get_coordinates_json(self):
        """Преобразует координаты в JSON формат для JavaScript"""
        import re
        import json
        
        if not self.coordinates:
            return None
            
        # Если уже JSON - возвращаем как есть
        if self.coordinates.strip().startswith('{'):
            try:
                return json.loads(self.coordinates)
            except:
                pass
        
        # Парсим WKT формат
        if self.coordinates.strip().upper().startswith('POLYGON'):
            try:
                match = re.search(r'POLYGON\s*\(\(([^)]+)\)\)', self.coordinates)
                if match:
                    coords_str = match.group(1)
                    coords = []
                    for pair in coords_str.split(','):
                        parts = pair.strip().split()
                        if len(parts) >= 2:
                            lng, lat = float(parts[0]), float(parts[1])
                            coords.append([lng, lat])
                    
                    # Возвращаем GeoJSON-подобный объект
                    return {
                        'type': 'Polygon',
                        'coordinates': [coords]  # Обратите внимание на двойное обёртывание
                    }
            except Exception as e:
                print(f'Ошибка парсинга WKT: {e}')
                
        return None
    
    def activate(self, user):
        """Активация проекта строительным контролем"""
        if self.can_be_activated(user):
            self.status = 'active'
            self.actual_start_date = timezone.now().date()
            self.control_service = user
            self.save()
            return True
        return False
    
    @property
    def work_specification(self):
        """Получение спецификации работ по проекту"""
        return self.work_spec_rows.all().order_by('order', 'name')
    
    @property
    def work_schedule_data(self):
        """Получение данных сетевого графика работ"""
        works = self.works.select_related('work_type').order_by('planned_start_date')
        schedule_data = []
        
        for work in works:
            schedule_data.append({
                'id': work.id,
                'name': work.name,
                'work_type': work.work_type.name if work.work_type else '',
                'work_type_code': work.work_type.code if work.work_type else '',
                'planned_start': work.planned_start_date.isoformat() if work.planned_start_date else None,
                'planned_end': work.planned_end_date.isoformat() if work.planned_end_date else None,
                'actual_start': work.actual_start_date.isoformat() if work.actual_start_date else None,
                'actual_end': work.actual_end_date.isoformat() if work.actual_end_date else None,
                'status': work.status,
                'volume': str(work.volume),
                'unit': work.unit,
                'is_delayed': work.is_delayed,
                'days_remaining': work.days_remaining,
                'duration_days': (work.planned_end_date - work.planned_start_date).days + 1 if work.planned_start_date and work.planned_end_date else 0,
                'progress_percentage': 100 if work.status in ['completed', 'verified'] else (
                    50 if work.status == 'in_progress' else 0
                )
            })
        
        return schedule_data
    
    @property 
    def work_types_summary(self):
        """Сводка по типам работ в проекте"""
        from django.db.models import Count, Avg
        
        work_types = self.works.select_related('work_type').values(
            'work_type__name',
            'work_type__code'
        ).annotate(
            total_works=Count('id'),
            completed_works=Count('id', filter=Q(status__in=['completed', 'verified'])),
        ).order_by('work_type__code')
        
        summary = []
        for wt in work_types:
            completion_rate = 0
            if wt['total_works'] > 0:
                completion_rate = int((wt['completed_works'] / wt['total_works']) * 100)
            
            summary.append({
                'name': wt['work_type__name'],
                'code': wt['work_type__code'], 
                'total_works': wt['total_works'],
                'completed_works': wt['completed_works'],
                'completion_rate': completion_rate
            })
        
        return summary
    
    def get_critical_path(self):
        """Определение критического пути проекта (упрощенная версия)"""
        works = list(self.works.order_by('planned_start_date'))
        if not works:
            return []
        
        # Простая эвристика: самая длинная последовательность работ
        critical_path = []
        current_date = works[0].planned_start_date
        
        for work in works:
            if work.planned_start_date <= current_date:
                critical_path.append(work)
                current_date = work.planned_end_date
        
        return critical_path


class WorkType(models.Model):
    """Типы работ на объекте"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название типа работ"
    )
    
    code = models.CharField(
        max_length=50,
        verbose_name="Код работ",
        unique=True
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    class Meta:
        verbose_name = "Тип работ"
        verbose_name_plural = "Типы работ"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Work(models.Model):
    """Работы на объекте благоустройства"""
    
    STATUS_CHOICES = [
        ('not_started', 'Не начата'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершена'),
        ('verified', 'Проверена'),
        ('suspended', 'Приостановлена'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='works',
        verbose_name="Объект"
    )
    
    work_type = models.ForeignKey(
        WorkType,
        on_delete=models.PROTECT,
        related_name='works',
        verbose_name="Тип работ"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название работ"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started',
        verbose_name="Статус"
    )
    
    planned_start_date = models.DateField(
        verbose_name="Плановая дата начала"
    )
    
    planned_end_date = models.DateField(
        verbose_name="Плановая дата завершения"
    )
    
    actual_start_date = models.DateField(
        null=True, blank=True,
        verbose_name="Фактическая дата начала"
    )
    
    actual_end_date = models.DateField(
        null=True, blank=True,
        verbose_name="Фактическая дата завершения"
    )
    
    volume = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Объем работ"
    )
    
    unit = models.CharField(
        max_length=20,
        verbose_name="Единица измерения"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    reported_by_foreman = models.BooleanField(
        default=False,
        verbose_name="Отмечено прорабом как выполнено"
    )
    
    verified_by_control = models.BooleanField(
        default=False,
        verbose_name="Подтверждено стройконтролем"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Работа"
        verbose_name_plural = "Работы"
        ordering = ['planned_start_date']
    
    def __str__(self):
        return f"{self.name} ({self.project.name})"
    
    @property
    def is_delayed(self):
        if self.status != 'completed' and self.status != 'verified' and self.planned_end_date:
            return timezone.now().date() > self.planned_end_date
        return False
        
    @property
    def days_remaining(self):
        if self.planned_end_date and self.status not in ['completed', 'verified']:
            delta = self.planned_end_date - timezone.now().date()
            return delta.days
        return 0


class WorkSpecRow(models.Model):
    """Строка электронной спецификации/перечня работ с плановыми объемами"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='work_spec_rows', verbose_name="Проект")
    code = models.CharField(max_length=100, verbose_name="Код работ/материала", blank=True)
    name = models.CharField(max_length=500, verbose_name="Наименование")
    unit = models.CharField(max_length=20, verbose_name="Единица измерения", blank=True)
    planned_volume = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Плановый объем", null=True, blank=True)
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Строка спецификации"
        verbose_name_plural = "Строки спецификации"
        ordering = ['project', 'order', 'name']
        unique_together = ('project', 'code', 'name')

    def __str__(self):
        return f"{self.project.name} — {self.code} {self.name}"


class ScheduleChange(models.Model):
    """Изменения в графике работ"""
    
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    ]
    
    work = models.ForeignKey(
        Work,
        on_delete=models.CASCADE,
        related_name='schedule_changes',
        verbose_name="Работа"
    )
    
    previous_start_date = models.DateField(
        verbose_name="Предыдущая дата начала"
    )
    
    previous_end_date = models.DateField(
        verbose_name="Предыдущая дата окончания"
    )
    
    new_start_date = models.DateField(
        verbose_name="Новая дата начала"
    )
    
    new_end_date = models.DateField(
        verbose_name="Новая дата окончания"
    )
    
    reason = models.TextField(
        verbose_name="Причина изменения"
    )
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_changes',
        verbose_name="Инициатор изменения"
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='reviewed_changes',
        null=True, blank=True,
        verbose_name="Рассмотрено"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Изменение графика"
        verbose_name_plural = "Изменения графика"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Изменение графика {self.work.name}"
    
    def apply_changes(self):
        """Применить изменения к работе"""
        if self.status == 'approved':
            self.work.planned_start_date = self.new_start_date
            self.work.planned_end_date = self.new_end_date
            self.work.save()
            return True
        return False


class ProjectTask(models.Model):
    """Задачи в рамках проекта (для workflow)"""
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('in_progress', 'В процессе'),
        ('completed', 'Выполнено'),
        ('verified', 'Проверено'),
        ('cancelled', 'Отменено'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name="Проект"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Название задачи"
    )
    
    description = models.TextField(
        verbose_name="Описание",
        blank=True
    )
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_tasks',
        verbose_name="Ответственный"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tasks',
        verbose_name="Создатель"
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name="Приоритет"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    due_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Крайний срок"
    )
    
    completed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата выполнения"
    )
    
    location_required = models.BooleanField(
        default=False,
        verbose_name="Требуется геолокация"
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
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ['-priority', 'due_date']
    
    def __str__(self):
        return f"{self.title} ({self.project.name})"
    
    def mark_completed(self, user, lat=None, lng=None):
        """Отметить задачу как выполненную"""
        if self.assigned_to == user:
            if self.location_required and (lat is None or lng is None):
                return False, "Требуется геолокация"
            
            self.status = 'completed'
            self.completed_at = timezone.now()
            if lat and lng:
                self.location_lat = lat
                self.location_lng = lng
            self.save()
            return True, "Задача отмечена как выполненная"
        return False, "Нет прав на выполнение данной задачи"


class TaskPhoto(models.Model):
    """Фотоотчеты по задачам"""
    
    task = models.ForeignKey(
        ProjectTask,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Задача"
    )
    
    photo = models.ImageField(
        upload_to='task_photos/',
        verbose_name="Фото"
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
        verbose_name = "Фото задачи"
        verbose_name_plural = "Фото задач"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Фото для {self.task.title}"


class WorkflowTransition(models.Model):
    """Лог переходов между этапами workflow"""
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='workflow_transitions',
        verbose_name="Проект"
    )
    
    from_status = models.CharField(
        max_length=50,
        verbose_name="Из статуса"
    )
    
    to_status = models.CharField(
        max_length=50,
        verbose_name="В статус"
    )
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Выполнил"
    )
    
    reason = models.TextField(
        blank=True,
        verbose_name="Причина"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Переход workflow"
        verbose_name_plural = "Переходы workflow"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project.name}: {self.from_status} -> {self.to_status}"


class ProjectInspection(models.Model):
    """Проверки проектов инспекторами"""
    
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    ]
    
    TYPE_CHOICES = [
        ('quality', 'Контроль качества'),
        ('safety', 'Контроль безопасности'),
        ('compliance', 'Соответствие нормам'),
        ('final', 'Окончательная приемка'),
    ]
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='inspections',
        verbose_name="Проект"
    )
    
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='inspections',
        verbose_name="Инспектор"
    )
    
    inspection_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Тип проверки"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name="Статус"
    )
    
    scheduled_date = models.DateTimeField(
        verbose_name="Плановая дата"
    )
    
    completed_date = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Фактическая дата"
    )
    
    areas_to_check = models.JSONField(
        default=list,
        verbose_name="Области контроля",
        blank=True
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )
    
    result = models.CharField(
        max_length=20,
        choices=[
            ('passed', 'Пройдено'),
            ('failed', 'Не пройдено'),
            ('partial', 'Частично'),
        ],
        null=True, blank=True,
        verbose_name="Результат"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Проверка проекта"
        verbose_name_plural = "Проверки проектов"
        ordering = ['-scheduled_date']
    
    def __str__(self):
        return f"Проверка {self.project.name} ({self.get_inspection_type_display()})"
    
    def complete_inspection(self, result, notes=''):
        """Завершить проверку"""
        self.status = 'completed'
        self.completed_date = timezone.now()
        self.result = result
        if notes:
            self.notes = notes
        self.save()
        return True


class ProjectEvent(models.Model):
    """События в жизненном цикле проекта"""
    
    EVENT_TYPES = [
        ('created', 'Проект создан'),
        ('status_changed', 'Изменен статус'),
        ('foreman_assigned', 'Назначен прораб'),
        ('foreman_changed', 'Изменен прораб'),
        ('work_started', 'Начаты работы'),
        ('work_completed', 'Завершены работы'),
        ('comment_added', 'Добавлено замечание'),
        ('violation_added', 'Зарегистрировано нарушение'),
        ('material_delivered', 'Доставлены материалы'),
        ('inspection_passed', 'Пройдена проверка'),
        ('document_uploaded', 'Загружен документ'),
        ('schedule_changed', 'Изменен график'),
        ('milestone_reached', 'Достигнута веха'),
        ('budget_updated', 'Обновлен бюджет'),
        ('completion_updated', 'Обновлен процент готовности'),
    ]
    
    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name="Проект"
    )
    
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        verbose_name="Тип события"
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Пользователь"
    )
    
    description = models.TextField(
        verbose_name="Описание события"
    )
    
    # Дополнительные поля для контекста
    old_value = models.TextField(
        blank=True,
        verbose_name="Старое значение"
    )
    
    new_value = models.TextField(
        blank=True,
        verbose_name="Новое значение"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Дополнительные данные"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Событие проекта"
        verbose_name_plural = "События проекта"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.project.name} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"
    
    @classmethod
    def create_event(cls, project, event_type, user, description, old_value=None, new_value=None, **metadata):
        """Создать событие проекта"""
        return cls.objects.create(
            project=project,
            event_type=event_type,
            user=user,
            description=description,
            old_value=old_value or '',
            new_value=new_value or '',
            metadata=metadata
        )


# Хелперы для создания событий
def create_project_event(project, event_type, user, description, **kwargs):
    """Универсальная функция для создания событий проекта"""
    return ProjectEvent.create_event(project, event_type, user, description, **kwargs)


def log_project_creation(project, user):
    """Создание проекта"""
    return create_project_event(
        project=project,
        event_type='created',
        user=user,
        description=f'Проект "{project.name}" был создан'
    )


def log_status_change(project, user, old_status, new_status):
    """Изменение статуса"""
    status_mapping = {
        'planned': 'Планируемый',
        'active': 'Активный',
        'completed': 'Завершенный',
        'suspended': 'Приостановленный',
        'cancelled': 'Отмененный'
    }
    
    old_display = status_mapping.get(old_status, old_status)
    new_display = status_mapping.get(new_status, new_status)
    
    return create_project_event(
        project=project,
        event_type='status_changed',
        user=user,
        description=f'Статус проекта изменен с "{old_display}" на "{new_display}"',
        old_value=old_display,
        new_value=new_display
    )


def log_foreman_assignment(project, user, foreman, is_new=True):
    """Назначение прораба"""
    event_type = 'foreman_assigned' if is_new else 'foreman_changed'
    action = 'Назначен' if is_new else 'Изменен'
    
    return create_project_event(
        project=project,
        event_type=event_type,
        user=user,
        description=f'{action} прораб: {foreman.get_full_name()}',
        new_value=foreman.get_full_name()
    )


def log_comment_added(project, user, comment_title):
    """Добавление замечания"""
    return create_project_event(
        project=project,
        event_type='comment_added',
        user=user,
        description=f'Добавлено замечание: "{comment_title}"'
    )


def log_work_status_change(project, user, work_name, old_status, new_status):
    """Изменение статуса работы"""
    status_mapping = {
        'planned': 'Планируемая',
        'in_progress': 'В процессе',
        'completed': 'Завершена',
        'verified': 'Проверена'
    }
    
    if old_status == 'planned' and new_status == 'in_progress':
        event_type = 'work_started'
        description = f'Начаты работы: "{work_name}"'
    elif new_status in ['completed', 'verified']:
        event_type = 'work_completed' 
        description = f'Завершены работы: "{work_name}"'
    else:
        event_type = 'status_changed'
        old_display = status_mapping.get(old_status, old_status)
        new_display = status_mapping.get(new_status, new_status) 
        description = f'Статус работ "{work_name}" изменен с "{old_display}" на "{new_display}"'
    
    return create_project_event(
        project=project,
        event_type=event_type,
        user=user,
        description=description
    )


def log_completion_update(project, user, old_percentage, new_percentage):
    """Обновление процента готовности"""
    return create_project_event(
        project=project,
        event_type='completion_updated',
        user=user,
        description=f'Обновлен процент готовности: {new_percentage}%',
        old_value=f'{old_percentage}%',
        new_value=f'{new_percentage}%'
    )


class Comment(models.Model):
    """Замечания по проекту"""
    
    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('accepted', 'Принято к исполнению'),
        ('rejected', 'Отклонено'),
        ('resolved', 'Устранено'),
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
        related_name='comments',
        verbose_name="Проект"
    )
    
    work = models.ForeignKey(
        Work,
        on_delete=models.CASCADE,
        related_name='comments',
        null=True, blank=True,
        verbose_name="Связанная работа"
    )
    
    title = models.CharField(
        max_length=255,
        verbose_name="Заголовок замечания"
    )
    
    description = models.TextField(
        verbose_name="Описание замечания"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
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
        on_delete=models.CASCADE,
        related_name='created_comments',
        verbose_name="Создал замечание"
    )
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_comments',
        null=True, blank=True,
        verbose_name="Ответственный за устранение"
    )
    
    location_lat = models.FloatField(
        verbose_name="Широта местоположения",
        help_text="GPS координата при создании замечания"
    )
    
    location_lng = models.FloatField(
        verbose_name="Долгота местоположения",
        help_text="GPS координата при создании замечания"
    )
    
    created_at_location = models.BooleanField(
        default=False,
        verbose_name="Создано на объекте",
        help_text="Подтверждение нахождения на объекте при создании"
    )
    
    due_date = models.DateField(
        null=True, blank=True,
        verbose_name="Срок устранения"
    )
    
    resolved_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата устранения"
    )
    
    response_comment = models.TextField(
        blank=True,
        verbose_name="Комментарий к ответу"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Замечание"
        verbose_name_plural = "Замечания"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.project.name})"
    
    @property
    def is_overdue(self):
        """Проверка просрочки устранения замечания"""
        if self.due_date and self.status not in ['resolved', 'rejected']:
            return timezone.now().date() > self.due_date
        return False
    
    def accept(self, user, due_date=None, assigned_to=None):
        """Принять замечание к исполнению"""
        if self.status == 'pending':
            self.status = 'accepted'
            if due_date:
                self.due_date = due_date
            if assigned_to:
                self.assigned_to = assigned_to
            self.save()
            return True
        return False
    
    def reject(self, user, reason=''):
        """Отклонить замечание"""
        if self.status == 'pending':
            self.status = 'rejected'
            self.response_comment = reason
            self.save()
            return True
        return False
    
    def resolve(self, user, comment=''):
        """Отметить замечание как устраненное"""
        if self.status == 'accepted':
            self.status = 'resolved'
            self.resolved_at = timezone.now()
            if comment:
                self.response_comment = comment
            self.save()
            return True
        return False


class CommentPhoto(models.Model):
    """Фотоматериалы к замечаниям"""
    
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='photos',
        verbose_name="Замечание"
    )
    
    photo = models.ImageField(
        upload_to='comment_photos/',
        verbose_name="Фото"
    )
    
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Описание фото"
    )
    
    is_before = models.BooleanField(
        default=True,
        verbose_name="Фото до устранения",
        help_text="True - фото проблемы, False - фото после устранения"
    )
    
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Автор фото"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Фото замечания"
        verbose_name_plural = "Фото замечаний"
        ordering = ['is_before', '-created_at']
    
    def __str__(self):
        status = "до" if self.is_before else "после"
        return f"Фото {status} устранения ({self.comment.title})"


class CommentStatusChange(models.Model):
    """Лог изменений статусов замечаний"""
    
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='status_changes',
        verbose_name="Замечание"
    )
    
    from_status = models.CharField(
        max_length=20,
        verbose_name="Предыдущий статус"
    )
    
    to_status = models.CharField(
        max_length=20,
        verbose_name="Новый статус"
    )
    
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Изменил статус"
    )
    
    reason = models.TextField(
        blank=True,
        verbose_name="Причина изменения"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Изменение статуса замечания"
        verbose_name_plural = "Изменения статусов замечаний"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.comment.title}: {self.from_status} -> {self.to_status}"


class ElectronicSpecification(models.Model):
    """Электронная спецификация проекта из Excel файлов"""
    
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='electronic_specification',
        verbose_name="Проект"
    )
    
    source_file = models.CharField(
        max_length=255,
        verbose_name="Исходный файл",
        help_text="Название Excel файла"
    )
    
    imported_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата импорта")
    
    class Meta:
        verbose_name = "Электронная спецификация"
        verbose_name_plural = "Электронные спецификации"
    
    def __str__(self):
        return f"Спецификация {self.project.name}"


class SpecificationItem(models.Model):
    """Элемент электронной спецификации (строка из Excel)"""
    
    specification = models.ForeignKey(
        ElectronicSpecification,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Спецификация"
    )
    
    code = models.CharField(
        max_length=50,
        verbose_name="Код работ/материала",
        blank=True
    )
    
    name = models.CharField(
        max_length=500,
        verbose_name="Наименование работ/материала"
    )
    
    unit = models.CharField(
        max_length=20,
        verbose_name="Единица измерения",
        blank=True
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        verbose_name="Количество",
        null=True, blank=True
    )
    
    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Цена за единицу",
        null=True, blank=True
    )
    
    total_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Общая стоимость",
        null=True, blank=True
    )
    
    category = models.CharField(
        max_length=200,
        verbose_name="Категория работ",
        blank=True
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок в спецификации"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )
    
    class Meta:
        verbose_name = "Элемент спецификации"
        verbose_name_plural = "Элементы спецификации"
        ordering = ['specification', 'order', 'name']
    
    def __str__(self):
        return f"{self.code} {self.name} ({self.specification.project.name})"


class NetworkSchedule(models.Model):
    """Сетевой график проекта из Excel файла"""
    
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name='network_schedule',
        verbose_name="Проект"
    )
    
    source_file = models.CharField(
        max_length=255,
        verbose_name="Исходный файл графика",
        help_text="Название Excel файла с графиком"
    )
    
    project_duration_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Общая продолжительность (дни)"
    )
    
    critical_path_duration = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Продолжительность критического пути (дни)"
    )
    
    imported_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата импорта")
    
    class Meta:
        verbose_name = "Сетевой график"
        verbose_name_plural = "Сетевые графики"
    
    def __str__(self):
        return f"График {self.project.name}"


class ScheduleTask(models.Model):
    """Задача в сетевом графике"""
    
    schedule = models.ForeignKey(
        NetworkSchedule,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name="График"
    )
    
    task_id = models.CharField(
        max_length=50,
        verbose_name="ID задачи в графике"
    )
    
    name = models.CharField(
        max_length=500,
        verbose_name="Наименование задачи"
    )
    
    duration_days = models.PositiveIntegerField(
        verbose_name="Продолжительность (дни)"
    )
    
    early_start = models.PositiveIntegerField(
        verbose_name="Раннее начало (день)",
        help_text="День от начала проекта"
    )
    
    early_finish = models.PositiveIntegerField(
        verbose_name="Раннее окончание (день)"
    )
    
    late_start = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Позднее начало (день)"
    )
    
    late_finish = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Позднее окончание (день)"
    )
    
    is_critical = models.BooleanField(
        default=False,
        verbose_name="Задача на критическом пути"
    )
    
    resource_names = models.TextField(
        blank=True,
        verbose_name="Ресурсы",
        help_text="Список ресурсов через запятую"
    )
    
    predecessors = models.TextField(
        blank=True,
        verbose_name="Предшествующие задачи",
        help_text="ID предшествующих задач через запятую"
    )
    
    successors = models.TextField(
        blank=True,
        verbose_name="Последующие задачи",
        help_text="ID последующих задач через запятую"
    )
    
    work_type = models.ForeignKey(
        WorkType,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Тип работ"
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок в графике"
    )
    
    class Meta:
        verbose_name = "Задача графика"
        verbose_name_plural = "Задачи графика"
        ordering = ['schedule', 'early_start', 'order']
        unique_together = ('schedule', 'task_id')
    
    def __str__(self):
        return f"{self.task_id}: {self.name} ({self.schedule.project.name})"
    
    @property
    def float_days(self):
        """Резерв времени (количество дней)"""
        if self.late_start is not None and self.early_start is not None:
            return self.late_start - self.early_start
        return 0
    
    def get_predecessor_list(self):
        """Получить список ID предшествующих задач"""
        if self.predecessors:
            return [tid.strip() for tid in self.predecessors.split(',') if tid.strip()]
        return []
    
    def get_successor_list(self):
        """Получить список ID последующих задач"""
        if self.successors:
            return [tid.strip() for tid in self.successors.split(',') if tid.strip()]
        return []
    
    def get_resource_list(self):
        """Получить список ресурсов"""
        if self.resource_names:
            return [res.strip() for res in self.resource_names.split(',') if res.strip()]
        return []


class ProjectQRCode(models.Model):
    """Коды QR для подтверждения нахождения на объекте"""
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='qr_codes',
        verbose_name="Проект"
    )
    
    code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        verbose_name="Уникальный код",
        help_text="Код, зашитый в QR-код"
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name="Название кода",
        help_text="Описание места размещения QR-кода"
    )
    
    location_description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Описание места",
        help_text="Описание места, где расположен QR-код"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Создал код"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    
    expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Дата истечения",
        help_text="Оставьте пустым для постоянного кода"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "QR-код проекта"
        verbose_name_plural = "QR-коды проектов"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['project', '-created_at']),
        ]
    
    def __str__(self):
        return f"QR-код {self.name} ({self.project.name})"
    
    @property
    def is_expired(self):
        """Проверка истечения кода"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def generate_qr_image(self):
        """Генерация QR-кода в виде base64 строки"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Данные QR-кода
        qr_data = {
            'type': 'project_verification',
            'project_id': self.project.id,
            'code': str(self.code),
            'name': self.name
        }
        
        qr.add_data(str(qr_data))
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Преобразуем в base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def get_verification_url(self):
        """Получить URL для верификации"""
        from django.urls import reverse
        return reverse('projects:verify_qr', kwargs={'code': self.code})


class QRVerification(models.Model):
    """История верификаций по QR-кодам"""
    
    qr_code = models.ForeignKey(
        ProjectQRCode,
        on_delete=models.CASCADE,
        related_name='verifications',
        verbose_name="QR-код"
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    
    verified_at = models.DateTimeField(auto_now_add=True)
    
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name="IP-адрес"
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent"
    )
    
    class Meta:
        verbose_name = "Верификация QR-кода"
        verbose_name_plural = "Верификации QR-кодов"
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['qr_code', '-verified_at']),
            models.Index(fields=['user', '-verified_at']),
        ]
    
    def __str__(self):
        return f"Верификация {self.user.get_full_name()} - {self.qr_code.name}"


class WeatherWorkRecommendation(models.Model):
    """
    Модель для хранения рекомендаций по проведению работ в зависимости от погоды
    """
    
    WEATHER_CONDITIONS = [
        ('clear', 'Ясно'),
        ('clouds', 'Облачно'),
        ('rain', 'Дождь'),
        ('snow', 'Снег'),
        ('thunderstorm', 'Гроза'),
        ('mist', 'Туман'),
        ('extreme_cold', 'Экстремальный холод'),
        ('extreme_heat', 'Экстремальная жара'),
        ('high_wind', 'Сильный ветер'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Низкий риск'),
        ('medium', 'Средний риск'),
        ('high', 'Высокий риск'),
        ('critical', 'Критический риск'),
    ]
    
    work_type = models.ForeignKey(
        WorkType,
        on_delete=models.CASCADE,
        related_name='weather_recommendations',
        verbose_name="Тип работ"
    )
    
    weather_condition = models.CharField(
        max_length=20,
        choices=WEATHER_CONDITIONS,
        verbose_name="Погодные условия"
    )
    
    min_temperature = models.IntegerField(
        null=True, blank=True,
        verbose_name="Мин. температура (°C)"
    )
    
    max_temperature = models.IntegerField(
        null=True, blank=True,
        verbose_name="Макс. температура (°C)"
    )
    
    max_wind_speed = models.IntegerField(
        null=True, blank=True,
        verbose_name="Макс. скорость ветра (м/с)"
    )
    
    risk_level = models.CharField(
        max_length=10,
        choices=RISK_LEVELS,
        verbose_name="Уровень риска"
    )
    
    recommendation = models.TextField(
        verbose_name="Рекомендация"
    )
    
    is_work_allowed = models.BooleanField(
        default=True,
        verbose_name="Работы разрешены"
    )
    
    delay_hours = models.IntegerField(
        default=0,
        verbose_name="Рекомендуемая задержка (часы)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Погодная рекомендация для работ"
        verbose_name_plural = "Погодные рекомендации для работ"
        unique_together = ('work_type', 'weather_condition')
    
    def __str__(self):
        return f"{self.work_type.name} - {self.get_weather_condition_display()}"


class WeatherForecast(models.Model):
    """
    Модель для хранения прогноза погоды для проектов
    """
    
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='weather_forecasts',
        verbose_name="Проект"
    )
    
    forecast_date = models.DateField(
        verbose_name="Дата прогноза"
    )
    
    temperature = models.IntegerField(
        verbose_name="Температура (°C)"
    )
    
    weather_main = models.CharField(
        max_length=50,
        verbose_name="Основные погодные условия"
    )
    
    weather_description = models.CharField(
        max_length=100,
        verbose_name="Описание погоды"
    )
    
    wind_speed = models.FloatField(
        default=0,
        verbose_name="Скорость ветра (м/с)"
    )
    
    humidity = models.IntegerField(
        default=0,
        verbose_name="Влажность (%)"
    )
    
    precipitation = models.FloatField(
        default=0,
        verbose_name="Осадки (мм)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Прогноз погоды"
        verbose_name_plural = "Прогнозы погоды"
        unique_together = ('project', 'forecast_date')
        ordering = ['forecast_date']
    
    def __str__(self):
        return f"{self.project.name} - {self.forecast_date}"
    
    def get_weather_condition_code(self):
        """Преобразует weather_main в код для рекомендаций"""
        weather_mapping = {
            'Clear': 'clear',
            'Clouds': 'clouds',
            'Rain': 'rain',
            'Drizzle': 'rain',
            'Snow': 'snow',
            'Thunderstorm': 'thunderstorm',
            'Mist': 'mist',
            'Fog': 'mist',
            'Haze': 'mist',
        }
        
        # Проверяем экстремальные температуры
        if self.temperature <= -15:
            return 'extreme_cold'
        elif self.temperature >= 35:
            return 'extreme_heat'
        
        # Проверяем сильный ветер
        if self.wind_speed >= 10:
            return 'high_wind'
        
        return weather_mapping.get(self.weather_main, 'clouds')


# Импортируем модели активации проектов
from .activation_models import (
    ProjectActivation,
    ActivationChecklist, 
    Notification,
    ActivationEvent
)
