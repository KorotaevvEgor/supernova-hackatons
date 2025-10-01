from django.db import models
from django.conf import settings
from django.utils import timezone


class MaterialType(models.Model):
    """Типы материалов"""
    
    name = models.CharField(
        max_length=255,
        verbose_name="Название материала"
    )
    
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Код материала"
    )
    
    unit = models.CharField(
        max_length=20,
        verbose_name="Единица измерения"
    )
    
    description = models.TextField(
        blank=True,
        verbose_name="Описание"
    )
    
    quality_requirements = models.TextField(
        blank=True,
        verbose_name="Требования к качеству"
    )
    
    class Meta:
        verbose_name = "Тип материала"
        verbose_name_plural = "Типы материалов"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class MaterialDelivery(models.Model):
    """Поставка материалов на объект"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидается'),
        ('delivered', 'Доставлено'),
        ('accepted', 'Принято'),
        ('rejected', 'Отклонено'),
        ('quality_control', 'На контроле качества'),
    ]
    
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='material_deliveries',
        verbose_name="Объект"
    )
    
    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
        verbose_name="Тип материала"
    )
    
    supplier = models.CharField(
        max_length=255,
        verbose_name="Поставщик"
    )
    
    quantity = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Количество"
    )
    
    delivery_date = models.DateTimeField(
        verbose_name="Дата и время поставки"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    
    ttn_number = models.CharField(
        max_length=100,
        verbose_name="Номер ТТН"
    )
    
    ttn_image = models.ImageField(
        upload_to='ttn_images/',
        null=True, blank=True,
        verbose_name="Фото ТТН"
    )
    
    quality_certificate = models.FileField(
        upload_to='quality_certificates/',
        null=True, blank=True,
        verbose_name="Паспорт качества"
    )
    
    quality_certificate_image = models.ImageField(
        upload_to='quality_cert_images/',
        null=True, blank=True,
        verbose_name="Фото паспорта качества"
    )
    
    location = models.CharField(
        max_length=100,
        null=True, blank=True,
        verbose_name="Место приемки",
        help_text="Координаты в формате 'lat,lng'"
    )

    # Связка с электронной спецификацией (при необходимости)
    spec_row = models.ForeignKey(
        'projects.WorkSpecRow',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries',
        verbose_name="Строка спецификации"
    )
    
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='received_materials',
        verbose_name="Принял"
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Примечания"
    )
    
    # OCR распознанные данные
    ocr_recognized_data = models.JSONField(
        null=True, blank=True,
        verbose_name="Распознанные данные OCR"
    )
    
    ocr_confidence = models.FloatField(
        null=True, blank=True,
        verbose_name="Уверенность распознавания"
    )
    
    manual_entry = models.BooleanField(
        default=False,
        verbose_name="Ручной ввод"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Поставка материала"
        verbose_name_plural = "Поставки материалов"
        ordering = ['-delivery_date']
    
    def __str__(self):
        return f"{self.material_type.name} - {self.quantity} {self.material_type.unit} ({self.project.name})"
    
    @property
    def is_overdue(self):
        """Просрочена ли поставка"""
        if self.status == 'pending':
            return timezone.now() > self.delivery_date
        return False


class MaterialQualityControl(models.Model):
    """Контроль качества материалов"""
    
    CONTROL_STATUS_CHOICES = [
        ('scheduled', 'Запланирован'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершен'),
        ('failed', 'Не прошел'),
    ]
    
    material_delivery = models.ForeignKey(
        MaterialDelivery,
        on_delete=models.CASCADE,
        related_name='quality_controls',
        verbose_name="Поставка материала"
    )
    
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='quality_inspections',
        verbose_name="Инспектор"
    )
    
    control_date = models.DateTimeField(
        verbose_name="Дата контроля"
    )
    
    status = models.CharField(
        max_length=20,
        choices=CONTROL_STATUS_CHOICES,
        default='scheduled',
        verbose_name="Статус контроля"
    )
    
    test_results = models.JSONField(
        null=True, blank=True,
        verbose_name="Результаты испытаний"
    )
    
    laboratory_report = models.FileField(
        upload_to='lab_reports/',
        null=True, blank=True,
        verbose_name="Отчет лаборатории"
    )
    
    photos = models.JSONField(
        null=True, blank=True,
        verbose_name="Фотографии образцов"
    )
    
    conclusion = models.TextField(
        verbose_name="Заключение"
    )
    
    recommendations = models.TextField(
        blank=True,
        verbose_name="Рекомендации"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Контроль качества материала"
        verbose_name_plural = "Контроль качества материалов"
        ordering = ['-control_date']
    
    def __str__(self):
        return f"Контроль качества {self.material_delivery.material_type.name} - {self.control_date}"


# ========== МОДЕЛИ ДЛЯ СИСТЕМЫ ВХОДНОГО КОНТРОЛЯ С OCR ==========

class TransportDocument(models.Model):
    """Модель для товарно-транспортных накладных (ТТН) с OCR-обработкой"""
    delivery = models.OneToOneField(
        MaterialDelivery, 
        on_delete=models.CASCADE, 
        verbose_name='Поставка',
        related_name='transport_document'
    )
    
    # Прямая связь с проектом (для админки и фильтрации)
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name='Проект (адрес доставки)',
        related_name='transport_documents',
        help_text='Адрес доставки будет автоматически заполнен из выбранного проекта'
    )
    
    # Основная информация о ТТН
    document_number = models.CharField(max_length=100, verbose_name='Номер ТТН')
    document_date = models.DateField(verbose_name='Дата ТТН')
    
    # Данные отправителя
    sender_name = models.CharField(max_length=255, verbose_name='Наименование отправителя')
    sender_address = models.TextField(verbose_name='Адрес отправителя')
    sender_inn = models.CharField(max_length=12, blank=True, verbose_name='ИНН отправителя')
    
    # Данные получателя
    receiver_name = models.CharField(max_length=255, verbose_name='Наименование получателя')
    receiver_address = models.TextField(verbose_name='Адрес получателя')
    receiver_inn = models.CharField(max_length=12, blank=True, verbose_name='ИНН получателя')
    
    # Транспортные данные
    vehicle_number = models.CharField(max_length=20, verbose_name='Номер ТС')
    driver_name = models.CharField(max_length=255, verbose_name='ФИО водителя')
    driver_license_number = models.CharField(max_length=20, blank=True, verbose_name='Номер в/у')
    
    # Данные о грузе
    cargo_description = models.TextField(verbose_name='Описание груза')
    cargo_weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Вес груза (кг)')
    cargo_volume = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Объем груза (м³)')
    packages_count = models.IntegerField(blank=True, null=True, verbose_name='Количество мест')
    
    # Статус обработки
    PROCESSING_STATUS_CHOICES = [
        ('uploaded', 'Загружено'),
        ('processing', 'Обрабатывается'),
        ('processed', 'Обработано'),
        ('verified', 'Проверено'),
        ('error', 'Ошибка обработки'),
    ]
    processing_status = models.CharField(
        max_length=20, 
        choices=PROCESSING_STATUS_CHOICES, 
        default='uploaded',
        verbose_name='Статус обработки'
    )
    
    # Отметки о качестве распознавания
    ocr_confidence = models.FloatField(
        blank=True, 
        null=True, 
        verbose_name='Уверенность OCR (%)',
        help_text='Процент уверенности системы распознавания текста'
    )
    manual_verification_required = models.BooleanField(
        default=False, 
        verbose_name='Требует ручной проверки'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Обработал'
    )
    
    class Meta:
        verbose_name = 'Товарно-транспортная накладная'
        verbose_name_plural = 'Товарно-транспортные накладные'
        ordering = ['-created_at']
    
    def __str__(self):
        project_name = self.project.name if self.project else 'Не указан'
        return f'ТТН №{self.document_number} от {self.document_date} - {project_name}'
    
    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического заполнения адреса доставки"""
        if self.project and not self.receiver_address:
            # Автоматически заполняем адрес получателя из проекта
            self.receiver_address = self.project.address
        
        if self.project and not self.receiver_name:
            # Автоматически заполняем название получателя
            self.receiver_name = f'Проект: {self.project.name}'
        
        super().save(*args, **kwargs)


class DocumentPhoto(models.Model):
    """Модель для фотографий документов (ТТН и дополнительных документов)"""
    transport_document = models.ForeignKey(
        TransportDocument,
        on_delete=models.CASCADE,
        verbose_name='ТТН',
        related_name='photos'
    )
    
    PHOTO_TYPE_CHOICES = [
        ('ttn_main', 'Основная страница ТТН'),
        ('ttn_additional', 'Дополнительная страница ТТН'),
        ('quality_certificate', 'Сертификат качества'),
        ('passport_material', 'Паспорт материала'),
        ('invoice', 'Счет-фактура'),
        ('other', 'Другой документ'),
    ]
    photo_type = models.CharField(
        max_length=20,
        choices=PHOTO_TYPE_CHOICES,
        default='ttn_main',
        verbose_name='Тип документа'
    )
    
    # Файл документа (изображение или PDF)
    image = models.FileField(
        upload_to='transport_documents/%Y/%m/%d/',
        verbose_name='Файл документа',
        help_text='Поддерживаются форматы: JPG, PNG, PDF'
    )
    
    # Метаданные файла
    file_size = models.PositiveIntegerField(blank=True, null=True, verbose_name='Размер файла (байт)')
    image_width = models.PositiveIntegerField(blank=True, null=True, verbose_name='Ширина изображения')
    image_height = models.PositiveIntegerField(blank=True, null=True, verbose_name='Высота изображения')
    
    # Метаданные для PDF
    file_type = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Тип файла',
        help_text='Определяется автоматически по расширению'
    )
    pages_count = models.PositiveIntegerField(
        blank=True, 
        null=True, 
        verbose_name='Количество страниц',
        help_text='Для PDF документов'
    )
    
    # Результаты обработки
    ocr_text = models.TextField(blank=True, verbose_name='Распознанный текст')
    ocr_confidence = models.FloatField(
        blank=True, 
        null=True, 
        verbose_name='Уверенность распознавания (%)',
        help_text='Средняя уверенность распознавания текста на изображении'
    )
    
    PROCESSING_STATUS_CHOICES = [
        ('uploaded', 'Загружено'),
        ('processing', 'Обрабатывается'),
        ('processed', 'Обработано'),
        ('error', 'Ошибка обработки'),
    ]
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS_CHOICES,
        default='uploaded',
        verbose_name='Статус обработки'
    )
    
    # Ошибки обработки
    processing_error = models.TextField(
        blank=True,
        verbose_name='Ошибка обработки',
        help_text='Подробное описание ошибки, если обработка не удалась'
    )
    
    # Метаданные
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружено')
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name='Обработано')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Загрузил'
    )
    
    class Meta:
        verbose_name = 'Фотография документа'
        verbose_name_plural = 'Фотографии документов'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f'{self.get_photo_type_display()} - {self.transport_document}'
    
    @property
    def is_pdf(self):
        """Проверяет, является ли файл PDF"""
        return self.file_type == 'pdf'
    
    @property 
    def is_image(self):
        """Проверяет, является ли файл изображением"""
        return self.file_type == 'image'
    
    def get_file_extension(self):
        """Получает расширение файла"""
        if self.image and self.image.name:
            import os
            return os.path.splitext(self.image.name)[1].lower()
        return None
    
    def save(self, *args, **kwargs):
        # Автоматически сохраняем метаданные файла
        if self.image and hasattr(self.image, 'file'):
            try:
                import os
                
                # Размер файла
                self.file_size = self.image.size
                
                # Определяем тип файла по расширению
                file_name = self.image.name
                if file_name:
                    file_extension = os.path.splitext(file_name)[1].lower()
                    if file_extension == '.pdf':
                        self.file_type = 'pdf'
                        # Для PDF файлов попытаемся определить количество страниц
                        try:
                            import fitz  # PyMuPDF
                            with fitz.open(self.image.file) as doc:
                                self.pages_count = len(doc)
                        except (ImportError, Exception):
                            self.pages_count = None
                    elif file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                        self.file_type = 'image'
                        self.pages_count = 1
                        # Размеры изображения
                        try:
                            from PIL import Image
                            with Image.open(self.image.file) as img:
                                self.image_width, self.image_height = img.size
                        except Exception:
                            pass
                    else:
                        self.file_type = 'other'
                        
            except ImportError:
                # Если библиотеки не установлены
                pass
        
        super().save(*args, **kwargs)


class OCRResult(models.Model):
    """Модель для хранения структурированных результатов OCR"""
    document_photo = models.OneToOneField(
        DocumentPhoto,
        on_delete=models.CASCADE,
        verbose_name='Фотография документа',
        related_name='ocr_result'
    )
    
    # Извлеченные данные
    extracted_fields = models.JSONField(
        default=dict,
        verbose_name='Извлеченные поля',
        help_text='Структурированные данные, извлеченные из документа'
    )
    
    # Координаты найденного текста (для подсветки на изображении)
    text_coordinates = models.JSONField(
        default=dict,
        verbose_name='Координаты текста',
        help_text='Координаты найденных текстовых блоков на изображении'
    )
    
    # Метрики качества
    overall_confidence = models.FloatField(
        blank=True,
        null=True,
        verbose_name='Общая уверенность (%)',
        help_text='Средняя уверенность распознавания всех полей'
    )
    
    field_confidences = models.JSONField(
        default=dict,
        verbose_name='Уверенность по полям',
        help_text='Уверенность распознавания для каждого поля отдельно'
    )
    
    # Статус валидации
    VALIDATION_STATUS_CHOICES = [
        ('pending', 'Ожидает проверки'),
        ('valid', 'Данные корректны'),
        ('invalid', 'Данные некорректны'),
        ('partial', 'Частично корректны'),
    ]
    validation_status = models.CharField(
        max_length=20,
        choices=VALIDATION_STATUS_CHOICES,
        default='pending',
        verbose_name='Статус валидации'
    )
    
    validation_errors = models.JSONField(
        default=list,
        verbose_name='Ошибки валидации',
        help_text='Список найденных ошибок при валидации данных'
    )
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    validated_at = models.DateTimeField(blank=True, null=True, verbose_name='Проверено')
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Проверил'
    )
    
    class Meta:
        verbose_name = 'Результат OCR'
        verbose_name_plural = 'Результаты OCR'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'OCR результат для {self.document_photo}'
    
    def get_field_value(self, field_name, default=None):
        """Получить значение поля из извлеченных данных"""
        return self.extracted_fields.get(field_name, default)
    
    def get_field_confidence(self, field_name, default=0.0):
        """Получить уверенность распознавания поля"""
        return self.field_confidences.get(field_name, default)
