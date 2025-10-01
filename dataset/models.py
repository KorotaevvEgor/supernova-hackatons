from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class ViolationClassifier(models.Model):
    """Классификатор нарушений из датасета ЛЦТ"""
    CATEGORY_CHOICES = [
        ('culture', 'Культура производства'),
        ('technical', 'Технические нарушения'),
        ('safety', 'Безопасность'),
        ('documentation', 'Документооборот'),
    ]
    
    TYPE_CHOICES = [
        ('fixable', 'Устранимое'),
        ('serious', 'Грубое'),
        ('critical', 'Критическое'),
    ]
    
    category = models.CharField('Категория', max_length=20, choices=CATEGORY_CHOICES)
    violation_type = models.CharField('Вид', max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField('Тип', max_length=20, default='fixable')
    name = models.TextField('Наименование нарушения')
    fix_period = models.IntegerField('Регламентный срок устранения (дни)')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Классификатор нарушений'
        verbose_name_plural = 'Классификаторы нарушений'
        ordering = ['category', 'severity', 'name']
    
    def __str__(self):
        return f"{self.get_category_display()}: {self.name[:50]}..."


class ProjectCoordinates(models.Model):
    """Координаты объектов ремонта"""
    name = models.CharField('Название объекта', max_length=200)
    address = models.CharField('Адрес', max_length=300)
    wkt_polygon = models.TextField('Полигон WKT')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Координаты объекта'
        verbose_name_plural = 'Координаты объектов'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.address}"


class WorkSpecification(models.Model):
    """Спецификации работ по объектам"""
    object_name = models.CharField('Объект', max_length=200)
    work_name = models.TextField('Наименование работы')
    quantity = models.FloatField('Количество')
    unit = models.CharField('Единица измерения', max_length=50)
    start_date = models.DateField('Дата начала', null=True, blank=True)
    end_date = models.DateField('Дата окончания', null=True, blank=True)
    address = models.CharField('Адрес', max_length=300, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Спецификация работ'
        verbose_name_plural = 'Спецификации работ'
        ordering = ['object_name', 'work_name']
    
    def __str__(self):
        return f"{self.object_name}: {self.work_name[:50]}..."


class NetworkSchedule(models.Model):
    """Сетевой график работ"""
    object_name = models.CharField('Объект', max_length=200)
    work_name = models.TextField('Наименование работы')
    kpgz_code = models.CharField('Код КПГЗ', max_length=20, blank=True)
    start_date = models.DateField('Дата начала', null=True, blank=True)
    end_date = models.DateField('Дата окончания', null=True, blank=True)
    work_essence = models.CharField('Сущность ГПР', max_length=200, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Сетевой график'
        verbose_name_plural = 'Сетевые графики'
        ordering = ['object_name', 'start_date']
    
    def __str__(self):
        return f"{self.object_name}: {self.work_name[:50]}..."


class TransportDocument(models.Model):
    """ТТН и паспорта качества"""
    document_number = models.CharField('Номер документа', max_length=50)
    date = models.DateField('Дата документа')
    sender = models.CharField('Грузоотправитель', max_length=300)
    receiver = models.CharField('Грузополучатель', max_length=300)
    material_name = models.CharField('Наименование материала', max_length=300)
    quantity_net = models.FloatField('Нетто, т')
    quantity_gross = models.FloatField('Брутто, т')
    volume = models.FloatField('Объем, м³')
    delivery_address = models.CharField('Адрес доставки', max_length=300)
    transport_number = models.CharField('Номер транспорта', max_length=50, blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Транспортный документ'
        verbose_name_plural = 'Транспортные документы'
        ordering = ['-date', 'document_number']
    
    def __str__(self):
        return f"ТТН {self.document_number} от {self.date}"


class CheckListTemplate(models.Model):
    """Шаблоны чек-листов"""
    FORM_TYPES = [
        ('opening', 'Форма №1 - Открытие объекта'),
        ('daily', 'Форма №2 - Ежедневный контроль'),
        ('quality', 'Форма №3 - Контроль качества'),
    ]
    
    name = models.CharField('Название', max_length=200)
    form_type = models.CharField('Тип формы', max_length=20, choices=FORM_TYPES)
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Шаблон чек-листа'
        verbose_name_plural = 'Шаблоны чек-листов'
        ordering = ['form_type', 'name']
    
    def __str__(self):
        return f"{self.get_form_type_display()}: {self.name}"


class CheckListItem(models.Model):
    """Элементы чек-листа"""
    template = models.ForeignKey(CheckListTemplate, on_delete=models.CASCADE, 
                               related_name='items', verbose_name='Шаблон')
    section = models.CharField('Раздел', max_length=200)
    item_number = models.CharField('Номер пункта', max_length=10)
    description = models.TextField('Описание проверки')
    regulatory_document = models.CharField('Нормативный документ', max_length=300, blank=True)
    order = models.IntegerField('Порядок', default=0)
    
    class Meta:
        verbose_name = 'Пункт чек-листа'
        verbose_name_plural = 'Пункты чек-листа'
        ordering = ['template', 'order', 'item_number']
    
    def __str__(self):
        return f"{self.template.name} - {self.item_number}: {self.description[:50]}..."


class ViolationPrescription(models.Model):
    """Предписания по нарушениям"""
    STATUS_CHOICES = [
        ('issued', 'Выдано'),
        ('in_progress', 'В работе'),
        ('fixed', 'Устранено'),
        ('not_fixed', 'Не устранено'),
        ('overdue', 'Просрочено'),
    ]
    
    number = models.CharField('Номер предписания', max_length=50)
    date_issued = models.DateField('Дата выдачи')
    violation = models.ForeignKey(ViolationClassifier, on_delete=models.CASCADE,
                                verbose_name='Нарушение')
    description = models.TextField('Описание выявленного нарушения')
    work_stopped = models.BooleanField('Остановка работ', default=False)
    fix_deadline = models.DateField('Срок устранения')
    actual_fix_date = models.DateField('Фактическая дата устранения', null=True, blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='issued')
    notes = models.TextField('Примечания', blank=True)
    inspector = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Инспектор')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Предписание'
        verbose_name_plural = 'Предписания'
        ordering = ['-date_issued', 'number']
    
    def __str__(self):
        return f"Предписание {self.number} от {self.date_issued}"
