from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
from .models import Project
from .notifications import Notification


class ProjectActivation(models.Model):
    """Процесс активации проекта"""
    
    ACTIVATION_STATUS_CHOICES = [
        ('pending', 'Ожидает активации'),
        ('foreman_assigned', 'Прораб назначен'),
        ('checklist_filling', 'Заполнение чек-листа'),
        ('inspector_review', 'На рассмотрении инспектора'),
        ('approved', 'Одобрено'),
        ('activated', 'Активирован'),
        ('rejected', 'Отклонено'),
    ]
    
    project = models.OneToOneField(
        Project, 
        on_delete=models.CASCADE,
        related_name='activation',
        verbose_name="Проект"
    )
    
    status = models.CharField(
        max_length=20,
        choices=ACTIVATION_STATUS_CHOICES,
        default='pending',
        verbose_name="Статус активации"
    )
    
    # Пользователи в процессе
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='initiated_activations',
        verbose_name="Инициировал активацию"
    )
    
    assigned_foreman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_activations',
        null=True, blank=True,
        verbose_name="Назначенный прораб"
    )
    
    reviewing_inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reviewed_activations',
        null=True, blank=True,
        verbose_name="Проверяющий инспектор"
    )
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True)
    foreman_assigned_at = models.DateTimeField(null=True, blank=True)
    checklist_completed_at = models.DateTimeField(null=True, blank=True)
    inspector_reviewed_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    
    # Дополнительные поля
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Причина отклонения"
    )
    
    inspector_notes = models.TextField(
        blank=True,
        verbose_name="Заметки инспектора"
    )
    
    activation_document = models.FileField(
        upload_to='activation_documents/',
        null=True, blank=True,
        verbose_name="Документ об активации"
    )
    
    class Meta:
        verbose_name = "Активация проекта"
        verbose_name_plural = "Активации проектов"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Активация: {self.project.name} ({self.get_status_display()})"
    
    def can_assign_foreman(self, user):
        """Может ли пользователь назначить прораба"""
        return (self.status == 'pending' and 
                user.user_type == 'construction_control' and
                self.initiated_by == user)
    
    def can_fill_checklist(self, user):
        """Может ли пользователь заполнять чек-лист"""
        return ((self.status == 'foreman_assigned' or self.status == 'rejected') and 
                user.user_type == 'construction_control' and
                self.initiated_by == user)
    
    def can_inspect(self, user):
        """Может ли пользователь проводить инспекцию"""
        return (self.status == 'inspector_review' and 
                user.user_type == 'inspector')
    
    def assign_foreman(self, foreman, assigned_by):
        """Назначить прораба"""
        self.assigned_foreman = foreman
        self.status = 'foreman_assigned'
        self.foreman_assigned_at = timezone.now()
        
        # Обновляем проект
        self.project.foreman = foreman
        self.project.save()
        
        self.save()
        
        # Отправляем уведомление
        Notification.objects.create_notification(
            recipient=foreman,
            title='Вы назначены ответственным прорабом',
            message=f'Вам назначен проект: {self.project.name}',
            notification_type='task',
            related_object=self
        )
    
    def complete_checklist(self, completed_by):
        """Завершить заполнение чек-листа"""
        self.status = 'inspector_review'
        self.checklist_completed_at = timezone.now()
        
        # Если это повторное заполнение после отклонения, очищаем предыдущие замечания
        if hasattr(self, 'rejection_reason') and self.rejection_reason:
            self.rejection_reason = ''
            self.inspector_notes = ''
            self.reviewing_inspector = None
            self.inspector_reviewed_at = None
        
        self.save()
        
        # Уведомляем инспекторов
        inspectors = User.objects.filter(user_type='inspector')
        for inspector in inspectors:
            Notification.objects.create_notification(
                recipient=inspector,
                title='Требуется проверка активации проекта',
                message=f'Проект готов к проверке: {self.project.name}',
                notification_type='inspection',
                related_object=self
            )
    
    def approve_activation(self, inspector, document=None):
        """Одобрить активацию"""
        self.reviewing_inspector = inspector
        self.status = 'approved'
        self.inspector_reviewed_at = timezone.now()
        
        if document:
            self.activation_document = document
        
        self.save()
        
        # Активируем проект
        self.project.status = 'active'
        self.project.actual_start_date = timezone.now().date()
        self.project.save()
        
        # Финальный статус активации
        self.status = 'activated'
        self.activated_at = timezone.now()
        self.save()
        
        # Уведомляем всех участников
        participants = [self.initiated_by, self.assigned_foreman]
        for user in participants:
            if user:
                Notification.objects.create_notification(
                    recipient=user,
                    title='Проект активирован',
                    message=f'Проект {self.project.name} успешно активирован и готов к работе',
                    notification_type='success',
                    related_object=self
                )


class ActivationChecklist(models.Model):
    """Чек-лист активации проекта"""
    
    # Варианты ответов
    ANSWER_CHOICES = [
        ('yes', 'ДА'),
        ('no', 'НЕТ'),
        ('not_required', 'Не требуется'),
    ]
    
    activation = models.OneToOneField(
        ProjectActivation,
        on_delete=models.CASCADE,
        related_name='checklist',
        verbose_name="Активация"
    )
    
    filled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="Заполнил"
    )
    
    filled_at = models.DateTimeField(auto_now_add=True)
    
    # 1. Наличие разрешительной, организационно-технологической, рабочей документации
    regulatory_documentation = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие разрешительной, организационно-технологической, рабочей документации"
    )
    regulatory_documentation_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по документации"
    )
    
    # 2. Наличие приказа на ответственное лицо, осуществляющего строительство
    construction_manager_order = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие приказа на ответственное лицо, осуществляющего строительство (производство работ)"
    )
    construction_manager_order_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по приказу на ответственного за строительство"
    )
    
    # 3. Наличие приказа на ответственное лицо, осуществляющее строительный контроль
    construction_control_order = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие приказа на ответственное лицо, осуществляющее строительный контроль (с указанием идентификационного номера в НРС в области строительства)"
    )
    construction_control_order_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по приказу на ответственного за строительный контроль"
    )
    
    # 4. Наличие приказа на ответственное лицо, осуществляющее подготовку проектной документации, авторский надзор
    project_supervision_order = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие приказа на ответственное лицо, осуществляющее подготовку проектной документации, авторский надзор"
    )
    project_supervision_order_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по приказу на ответственного за проектную документацию"
    )
    
    # 5. Наличие проектной документации со штампом «В производство работ»
    project_documentation_stamp = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие проектной документации со штампом «В производство работ»"
    )
    project_documentation_stamp_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по проектной документации"
    )
    
    # 6. Наличие проекта производства работ
    work_production_project = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие проекта производства работ (утвержденного руководителем подрядной организации, согласованного Заказчиком, проектировщиком, эксплуатирующей организацией)"
    )
    work_production_project_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по проекту производства работ"
    )
    
    # 7. Инженерная подготовка строительной площадки
    engineering_site_preparation = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Инженерная подготовка строительной площадки"
    )
    engineering_site_preparation_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по инженерной подготовке площадки"
    )
    
    # 8. Наличие акта геодезической разбивочной основы
    geodetic_breakdown_act = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие акта геодезической разбивочной основы, принятых знаков (реперов)"
    )
    geodetic_breakdown_act_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по геодезической разбивочной основе"
    )
    
    # 9. Наличие генерального плана (ситуационного плана)
    general_plan = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие генерального плана (ситуационного плана)"
    )
    general_plan_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по генеральному плану"
    )
    
    # 10. Фактическое размещение временной инженерной и бытовой инфраструктуры площадки
    temporary_infrastructure = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Фактическое размещение временной инженерной и бытовой инфраструктуры площадки (включая стоянку автотранспорта) согласно проекту организации. Соответствие размещённых временных инфраструктуры требованиям электробезопасности, пожарных, санитарно-эпидемиологических норм и правил"
    )
    temporary_infrastructure_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по временной инфраструктуре"
    )
    
    # 11. Наличие пунктов очистки или мойки колес транспортных средств
    vehicle_cleaning_points = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие пунктов очистки или мойки колес транспортных средств на выездах со строительной площадки"
    )
    vehicle_cleaning_points_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по пунктам очистки транспорта"
    )
    
    # 12. Наличие бункеров или контейнеров для сбора отдельно бытового и отдельно строительного мусора
    waste_containers = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие бункеров или контейнеров для сбора отдельно бытового и отдельно строительного мусора"
    )
    waste_containers_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по контейнерам для мусора"
    )
    
    # 13. Наличие информационных щитов (знаков)
    information_boards = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие информационных щитов (знаков) с указанием: наименование объекта; наименование Застройщика (технического Заказчика); наименование подрядной организации; наименование проектной организации; сроки строительства; контактные телефоны ответственных по приказу лиц по организации"
    )
    information_boards_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по информационным щитам"
    )
    
    # 14. Наличие стендов пожарной безопасности
    fire_safety_stands = models.CharField(
        max_length=15,
        choices=ANSWER_CHOICES,
        blank=True, null=True,
        verbose_name="Наличие стендов пожарной безопасности с указанием на схеме мест источников воды, средств пожаротушения"
    )
    fire_safety_stands_notes = models.TextField(
        blank=True,
        verbose_name="Примечания по стендам пожарной безопасности"
    )
    
    # Общая оценка
    overall_readiness = models.BooleanField(
        default=False,
        verbose_name="Объект готов к активации"
    )
    
    additional_notes = models.TextField(
        blank=True,
        verbose_name="Дополнительные примечания"
    )
    
    class Meta:
        verbose_name = "Чек-лист активации"
        verbose_name_plural = "Чек-листы активации"
    
    def __str__(self):
        return f"Чек-лист: {self.activation.project.name}"
    
    @property
    def completion_percentage(self):
        """Процент заполнения чек-листа"""
        fields = [
            self.regulatory_documentation,
            self.construction_manager_order,
            self.construction_control_order,
            self.project_supervision_order,
            self.project_documentation_stamp,
            self.work_production_project,
            self.engineering_site_preparation,
            self.geodetic_breakdown_act,
            self.general_plan,
            self.temporary_infrastructure,
            self.vehicle_cleaning_points,
            self.waste_containers,
            self.information_boards,
            self.fire_safety_stands,
        ]
        # Подсчитываем количество заполненных полей (не пустых)
        completed = sum(1 for field in fields if field and field.strip())
        return int((completed / len(fields)) * 100)
    
    @property 
    def is_complete(self):
        """Чек-лист полностью заполнен"""
        # Проверяем, что все поля заполнены и общая готовность отмечена
        fields = [
            self.regulatory_documentation,
            self.construction_manager_order,
            self.construction_control_order,
            self.project_supervision_order,
            self.project_documentation_stamp,
            self.work_production_project,
            self.engineering_site_preparation,
            self.geodetic_breakdown_act,
            self.general_plan,
            self.temporary_infrastructure,
            self.vehicle_cleaning_points,
            self.waste_containers,
            self.information_boards,
            self.fire_safety_stands,
        ]
        all_filled = all(field and field.strip() for field in fields)
        return all_filled and self.overall_readiness


class ActivationEvent(models.Model):
    """События в процессе активации"""
    
    EVENT_TYPES = [
        ('created', 'Создана заявка'),
        ('foreman_assigned', 'Назначен прораб'),
        ('checklist_started', 'Начато заполнение чек-листа'),
        ('checklist_completed', 'Чек-лист заполнен'),
        ('sent_for_review', 'Отправлено на проверку'),
        ('inspector_assigned', 'Назначен инспектор'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
        ('activated', 'Проект активирован'),
        ('comment_added', 'Добавлен комментарий'),
    ]
    
    activation = models.ForeignKey(
        ProjectActivation,
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name="Активация"
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Событие активации"
        verbose_name_plural = "События активации"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.activation.project.name}"