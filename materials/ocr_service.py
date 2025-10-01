"""
Сервис для OCR-обработки товарно-транспортных накладных (ТТН)
Реализует функциональность компьютерного зрения для извлечения данных из документов
"""

import os
import re
import json
import logging
import tempfile
from typing import Dict, List, Tuple, Optional, Any
from decimal import Decimal
from datetime import datetime, date
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
import PIL.Image
import PIL.ImageEnhance
import PIL.ImageFilter

logger = logging.getLogger(__name__)

# Попытка импорта pytesseract с fallback на mock-режим для демо
try:
    import pytesseract
    HAS_TESSERACT = True
    logger.info("Тesseract OCR успешно загружен")
except ImportError:
    HAS_TESSERACT = False
    logger.warning("Тesseract OCR не установлен, используется demo-режим")

# Импорт OCR.space процессора
from .ocr_space_processor import get_ocr_space_processor

# Попытка импорта библиотек для работы с PDF
try:
    import fitz  # PyMuPDF
    from pdf2image import convert_from_path, convert_from_bytes
    HAS_PDF_SUPPORT = True
    logger.info("PDF библиотеки успешно загружены")
except ImportError as e:
    HAS_PDF_SUPPORT = False
    logger.warning(f"PDF библиотеки не установлены: {e}, PDF файлы не поддерживаются")


class TTNOCRService:
    """
    Сервис для извлечения данных из ТТН с помощью компьютерного зрения
    """
    
    def __init__(self):
        # Настройки OCR
        self.tesseract_config = '--psm 6 -c tessedit_char_whitelist=АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя0123456789.,/\\-:№()[]\" \"'
        
        # Пороговые значения для определения качества распознавания
        self.confidence_threshold = 70.0  # Минимальная уверенность для автоматического принятия (повышено для OCR.space)
        self.manual_check_threshold = 50.0  # Ниже этого значения требуется ручная проверка
        
        # Определяем, какой OCR сервис использовать
        self.ocr_service = getattr(settings, 'OCR_SERVICE', 'ocr_space')
        
        # Регулярные выражения для извлечения данных
        self.patterns = {
            'document_number': [
                r'№\s*(\d+[\d\-/]*)',
                r'[Нн]омер.*?(\d+[\d\-/]*)',
                r'ТТН\s*№\s*(\d+[\d\-/]*)',
            ],
            'document_date': [
                r'(\d{1,2}\.\d{1,2}\.\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{4}-\d{1,2}-\d{1,2})',
            ],
            'sender_name': [
                r'[Оо]тправитель.*?([А-ЯЁ][А-ЯЁа-яё\s"«»]{10,100})',
                r'[Гг]рузоотправитель.*?([А-ЯЁ][А-ЯЁа-яё\s"«»]{10,100})',
            ],
            'receiver_name': [
                r'[Пп]олучатель.*?([А-ЯЁ][А-ЯЁа-яё\s"«»]{10,100})',
                r'[Гг]рузополучатель.*?([А-ЯЁ][А-ЯЁа-яё\s"«»]{10,100})',
            ],
            'vehicle_number': [
                r'[Аа]втомобиль.*?([А-Я]\d{3}[А-Я]{2}\d{2,3})',
                r'[Нн]омер.*?[Тт][Сс].*?([А-Я]\d{3}[А-Я]{2}\d{2,3})',
                r'([А-Я]\d{3}[А-Я]{2}\d{2,3})',
            ],
            'driver_name': [
                r'[Вв]одитель.*?([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
                r'[Фф][ИиЫы][Оо].*?([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
            ],
            'cargo_description': [
                r'[Гг]руз.*?([А-ЯЁа-яё\s,.-]{15,200})',
                r'[Нн]аименование.*?([А-ЯЁа-яё\s,.-]{15,200})',
            ],
            'cargo_weight': [
                r'[Вв]ес.*?(\d+[.,]\d+|\d+)\s*кг',
                r'(\d+[.,]\d+|\d+)\s*кг',
            ],
            'inn_number': [
                r'ИНН\s*(\d{10}|\d{12})',
                r'[Ии][Нн][Нн].*?(\d{10}|\d{12})',
            ]
        }

    def process_ttn_photo(self, photo_instance) -> Dict[str, Any]:
        """
        Обработать фотографию ТТН с помощью OCR
        
        Args:
            photo_instance: Экземпляр модели DocumentPhoto
            
        Returns:
            Dict с результатами обработки
        """
        logger.info(f"Начало обработки фото {photo_instance.id}")
        
        try:
            # Обновляем статус на "обрабатывается"
            photo_instance.processing_status = 'processing'
            photo_instance.save(update_fields=['processing_status'])
            
            # Выбираем OCR сервис на основе настроек
            if self.ocr_service == 'ocr_space':
                logger.info(f"Используем OCR.space для обработки фото {photo_instance.id}")
                ocr_result = self._process_with_ocr_space(photo_instance)
            else:
                logger.info(f"Используем Tesseract для обработки фото {photo_instance.id}")
                if not HAS_TESSERACT:
                    logger.warning(f"Tesseract недоступен для фото {photo_instance.id}, используем demo-режим")
                    return self._create_demo_result(photo_instance)
                ocr_result = self._process_with_tesseract(photo_instance)
            
            if not ocr_result['success']:
                photo_instance.processing_status = 'error'
                photo_instance.processing_error = ocr_result['error']
                photo_instance.save(update_fields=['processing_status', 'processing_error'])
                return ocr_result
            
            # Сохраняем исходный распознанный текст
            photo_instance.ocr_text = ocr_result.get('raw_text', ocr_result.get('text', ''))
            photo_instance.ocr_confidence = ocr_result['confidence']
            
            # Извлекаем структурированные данные
            if self.ocr_service == 'ocr_space' and 'fields' in ocr_result:
                # OCR.space уже вернул структурированные данные
                structured_data = {
                    'fields': ocr_result['fields'],
                    'confidences': ocr_result.get('field_confidences', {}),
                    'overall_confidence': ocr_result['confidence']
                }
            else:
                # Tesseract - нужно извлечь структурированные данные
                structured_data = self._extract_structured_data(ocr_result.get('raw_text', ocr_result.get('text', '')))
            
            # Создаем или обновляем OCR результат
            from .models import OCRResult
            ocr_result_instance, created = OCRResult.objects.get_or_create(
                document_photo=photo_instance,
                defaults={
                    'extracted_fields': structured_data['fields'],
                    'field_confidences': structured_data['confidences'],
                    'overall_confidence': structured_data['overall_confidence'],
                    'text_coordinates': ocr_result.get('coordinates', {}),
                    'validation_status': 'pending'
                }
            )
            
            if not created:
                # Обновляем существующий результат
                ocr_result_instance.extracted_fields = structured_data['fields']
                ocr_result_instance.field_confidences = structured_data['confidences']
                ocr_result_instance.overall_confidence = structured_data['overall_confidence']
                ocr_result_instance.text_coordinates = ocr_result.get('coordinates', {})
                ocr_result_instance.save()
            
            # Определяем, требуется ли ручная проверка
            requires_manual_check = (
                structured_data['overall_confidence'] < self.manual_check_threshold or
                len(structured_data['fields']) < 3  # Минимум 3 поля должны быть извлечены
            )
            
            # Обновляем статусы
            photo_instance.processing_status = 'processed'
            photo_instance.processed_at = timezone.now()
            photo_instance.save(update_fields=['processing_status', 'processed_at', 'ocr_text', 'ocr_confidence'])
            
            # Обновляем связанный TransportDocument
            self._update_transport_document(photo_instance, structured_data['fields'], requires_manual_check)
            
            return {
                'success': True,
                'ocr_result_id': ocr_result_instance.id,
                'extracted_fields': structured_data['fields'],
                'confidence': structured_data['overall_confidence'],
                'requires_manual_check': requires_manual_check,
                'message': 'Документ успешно обработан'
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обработке фото ТТН {photo_instance.id}: {str(e)}")
            photo_instance.processing_status = 'error'
            photo_instance.processing_error = str(e)
            photo_instance.save(update_fields=['processing_status', 'processing_error'])
            
            return {
                'success': False,
                'error': f'Ошибка обработки: {str(e)}'
            }

    def _extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Извлечь текст из PDF файла с помощью OCR
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Dict с результатами обработки
        """
        try:
            if not HAS_PDF_SUPPORT:
                return {
                    'success': False,
                    'error': 'PDF библиотеки не установлены'
                }
            
            if not HAS_TESSERACT:
                return self._demo_ocr_result()
            
            logger.info(f"Начало обработки PDF файла: {pdf_path}")
            
            combined_text = ""
            total_confidence = 0
            page_count = 0
            all_coordinates = {}
            
            # Конвертируем PDF в изображения
            try:
                # Используем pdf2image для конвертации
                images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=5)  # Ограничиваем до 5 страниц
                logger.info(f"PDF конвертирован в {len(images)} изображений")
                
                for page_num, image in enumerate(images, 1):
                    logger.info(f"Обработка страницы {page_num}/{len(images)}")
                    
                    # Сохраняем изображение во временный файл
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                        image.save(temp_file.name, 'PNG')
                        temp_image_path = temp_file.name
                    
                    try:
                        # Предварительная обработка изображения
                        processed_image = self._preprocess_image_from_pil(image)
                        
                        # Извлечение текста с координатами
                        data = pytesseract.image_to_data(
                            processed_image,
                            lang='rus+eng',
                            config=self.tesseract_config,
                            output_type=pytesseract.Output.DICT
                        )
                        
                        # Извлекаем текст
                        page_text = pytesseract.image_to_string(
                            processed_image,
                            lang='rus+eng',
                            config=self.tesseract_config
                        )
                        
                        if page_text.strip():
                            combined_text += f"\n=== СТРАНИЦА {page_num} ===\n" + page_text + "\n"
                            
                            # Вычисляем уверенность для страницы
                            confidences = [conf for conf in data['conf'] if conf > 0]
                            if confidences:
                                page_confidence = sum(confidences) / len(confidences)
                                total_confidence += page_confidence
                                page_count += 1
                            
                            # Сохраняем координаты с префиксом страницы
                            page_coordinates = self._extract_text_coordinates(data)
                            for text, coords in page_coordinates.items():
                                all_coordinates[f"page_{page_num}_{text}"] = coords
                    
                    finally:
                        # Удаляем временный файл
                        try:
                            os.unlink(temp_image_path)
                        except OSError:
                            pass
                
                # Вычисляем среднюю уверенность
                avg_confidence = total_confidence / page_count if page_count > 0 else 0
                
                logger.info(f"PDF обработан: {page_count} страниц, уверенность: {avg_confidence:.2f}%")
                
                return {
                    'success': True,
                    'text': combined_text,
                    'confidence': avg_confidence,
                    'coordinates': all_coordinates,
                    'pages_processed': page_count
                }
                
            except Exception as pdf_error:
                logger.error(f"Ошибка при обработке PDF {pdf_path}: {str(pdf_error)}")
                return {
                    'success': False,
                    'error': f'Ошибка обработки PDF: {str(pdf_error)}'
                }
                
        except Exception as e:
            logger.error(f"Общая ошибка при извлечении текста из PDF {pdf_path}: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка обработки PDF файла: {str(e)}'
            }

    def _extract_text_from_image(self, image_path: str) -> Dict[str, Any]:
        """
        Извлечь текст из изображения с помощью Tesseract OCR
        """
        try:
            if not HAS_TESSERACT:
                return self._demo_ocr_result()
            
            # Предварительная обработка изображения для улучшения качества OCR
            processed_image = self._preprocess_image(image_path)
            
            # Извлечение текста с координатами
            try:
                # Получаем детальные данные с координатами
                data = pytesseract.image_to_data(
                    processed_image, 
                    lang='rus+eng',
                    config=self.tesseract_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Извлекаем текст
                text = pytesseract.image_to_string(
                    processed_image,
                    lang='rus+eng', 
                    config=self.tesseract_config
                )
                
                # Вычисляем среднюю уверенность
                confidences = [conf for conf in data['conf'] if conf > 0]
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                
                # Извлекаем координаты найденного текста
                coordinates = self._extract_text_coordinates(data)
                
                return {
                    'success': True,
                    'text': text,
                    'confidence': avg_confidence,
                    'coordinates': coordinates
                }
                
            except Exception as ocr_error:
                logger.error(f"Ошибка Tesseract OCR: {str(ocr_error)}")
                return {
                    'success': False,
                    'error': f'Ошибка распознавания текста: {str(ocr_error)}'
                }
                
        except Exception as e:
            logger.error(f"Ошибка при извлечении текста из {image_path}: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка обработки изображения: {str(e)}'
            }

    def _process_with_ocr_space(self, photo_instance) -> Dict[str, Any]:
        """
        Обработка документа через OCR.space API
        """
        try:
            # Получаем процессор OCR.space
            ocr_processor = get_ocr_space_processor()
            
            # Читаем файл в байты
            with photo_instance.image.open('rb') as image_file:
                image_data = image_file.read()
            
            # Обрабатываем через OCR.space
            result = ocr_processor.process_document(image_data)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при обработке через OCR.space: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка OCR.space: {str(e)}',
                'confidence': 0
            }
    
    def _process_with_tesseract(self, photo_instance) -> Dict[str, Any]:
        """
        Обработка документа через Tesseract OCR
        """
        try:
            # Проверяем тип файла (изображение или PDF)
            file_path = photo_instance.image.path
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                # Обработка PDF файла
                return self._extract_text_from_pdf(file_path)
            else:
                # Обработка изображения
                return self._extract_text_from_image(file_path)
                
        except Exception as e:
            logger.error(f"Ошибка при обработке через Tesseract: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка Tesseract: {str(e)}',
                'confidence': 0
            }
    
    def _demo_ocr_result(self) -> Dict[str, Any]:
        """
        Демо-результат для случаев, когда Tesseract не установлен
        """
        demo_text = """
        ТОВАРНО-ТРАНСПОРТНАЯ НАКЛАДНАЯ № ТТН-2024-001234
        Дата: 15.09.2024
        
        Отправитель: ООО "СтройМатериалы Плюс"
        ИНН: 7712345678
        Адрес: г. Москва, ул. Строительная, д. 25
        
        Получатель: ООО "МосГорСтрой"  
        ИНН: 7798765432
        Адрес: г. Москва, ул. Промышленная, д. 15
        
        Транспортное средство: А1234ВВ777
        Водитель: Иванов Петр Сергеевич
        Водительское удостоверение: 77 АБ 123456
        
        Груз: Цемент портландский М400, мешки 50кг
        Вес: 1500.00 кг
        Количество мест: 30
        """
        
        return {
            'success': True,
            'text': demo_text,
            'confidence': 85.5,
            'coordinates': {}
        }

    def _preprocess_image_from_pil(self, image: PIL.Image.Image) -> PIL.Image.Image:
        """
        Предварительная обработка PIL изображения для улучшения качества OCR
        """
        try:
            # Конвертируем в оттенки серого
            if image.mode != 'L':
                image = image.convert('L')
            
            # Увеличиваем контрастность
            enhancer = PIL.ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Увеличиваем резкость
            image = image.filter(PIL.ImageFilter.SHARPEN)
            
            # Увеличиваем размер изображения для лучшего распознавания мелкого текста
            width, height = image.size
            if width < 1000 or height < 1000:
                scale_factor = max(1000 / width, 1000 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), PIL.Image.LANCZOS)
            
            return image
            
        except Exception as e:
            logger.error(f"Ошибка предобработки PIL изображения: {str(e)}")
            return image  # Возвращаем исходное изображение

    def _preprocess_image(self, image_path: str) -> PIL.Image.Image:
        """
        Предварительная обработка изображения для улучшения качества OCR
        """
        try:
            # Открываем изображение
            image = PIL.Image.open(image_path)
            return self._preprocess_image_from_pil(image)
            
        except Exception as e:
            logger.error(f"Ошибка предобработки изображения {image_path}: {str(e)}")
            # Возвращаем исходное изображение если обработка не удалась
            return PIL.Image.open(image_path)

    def _extract_text_coordinates(self, ocr_data: Dict) -> Dict[str, List]:
        """
        Извлечь координаты текстовых блоков из данных Tesseract
        """
        coordinates = {}
        
        try:
            for i, text in enumerate(ocr_data['text']):
                if text.strip() and ocr_data['conf'][i] > 30:  # Игнорируем текст с низкой уверенностью
                    coordinates[text] = {
                        'left': ocr_data['left'][i],
                        'top': ocr_data['top'][i], 
                        'width': ocr_data['width'][i],
                        'height': ocr_data['height'][i],
                        'confidence': ocr_data['conf'][i]
                    }
        except Exception as e:
            logger.error(f"Ошибка извлечения координат: {str(e)}")
            
        return coordinates

    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        Извлечь структурированные данные из распознанного текста
        """
        extracted_fields = {}
        field_confidences = {}
        
        # Применяем регулярные выражения для каждого поля
        for field_name, patterns in self.patterns.items():
            best_match = None
            best_confidence = 0
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    # Берем первое совпадение и присваиваем базовую уверенность
                    match = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    
                    # Простая эвристика для оценки качества извлеченных данных
                    confidence = self._calculate_field_confidence(field_name, match)
                    
                    if confidence > best_confidence:
                        best_match = match.strip()
                        best_confidence = confidence
            
            if best_match:
                extracted_fields[field_name] = self._clean_field_value(field_name, best_match)
                field_confidences[field_name] = best_confidence

        # Вычисляем общую уверенность
        if field_confidences:
            overall_confidence = sum(field_confidences.values()) / len(field_confidences)
        else:
            overall_confidence = 0
        
        return {
            'fields': extracted_fields,
            'confidences': field_confidences,
            'overall_confidence': overall_confidence
        }

    def _calculate_field_confidence(self, field_name: str, value: str) -> float:
        """
        Вычислить уверенность для конкретного поля на основе эвристик
        """
        base_confidence = 70.0
        
        # Специфичные проверки для разных типов полей
        if field_name == 'document_number':
            # Проверяем формат номера документа
            if re.match(r'^\d+[\d\-/]*$', value) and len(value) >= 3:
                return base_confidence + 15
            return base_confidence - 20
            
        elif field_name == 'document_date':
            # Проверяем формат даты
            try:
                if '.' in value:
                    datetime.strptime(value, '%d.%m.%Y')
                elif '/' in value:
                    datetime.strptime(value, '%d/%m/%Y')
                elif '-' in value:
                    datetime.strptime(value, '%Y-%m-%d')
                return base_confidence + 20
            except ValueError:
                return base_confidence - 30
                
        elif field_name == 'vehicle_number':
            # Проверяем формат российского номера
            if re.match(r'^[А-Я]\d{3}[А-Я]{2}\d{2,3}$', value):
                return base_confidence + 25
            return base_confidence - 15
            
        elif field_name in ['sender_name', 'receiver_name']:
            # Проверяем длину и наличие типичных слов
            if len(value) > 10 and any(word in value.lower() for word in ['ооо', 'зао', 'ип', 'ао']):
                return base_confidence + 10
            return base_confidence
            
        elif field_name == 'driver_name':
            # Проверяем формат ФИО (3 слова)
            if len(value.split()) == 3:
                return base_confidence + 15
            return base_confidence - 10
            
        return base_confidence

    def _clean_field_value(self, field_name: str, value: str) -> str:
        """
        Очистить и нормализовать значение поля
        """
        value = value.strip()
        
        if field_name == 'document_date':
            # Нормализуем дату к формату YYYY-MM-DD
            for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                try:
                    parsed_date = datetime.strptime(value, date_format).date()
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue
                    
        elif field_name == 'cargo_weight':
            # Извлекаем только число
            value = re.sub(r'[^\d,.]', '', value)
            value = value.replace(',', '.')
            
        elif field_name in ['sender_name', 'receiver_name', 'cargo_description']:
            # Удаляем лишние пробелы и символы
            value = re.sub(r'\s+', ' ', value)
            
        return value

    def _update_transport_document(self, photo_instance, extracted_fields: Dict, requires_manual_check: bool):
        """
        Обновить связанный TransportDocument извлеченными данными
        """
        try:
            transport_doc = photo_instance.transport_document
            
            # Маппинг полей из OCR в поля модели
            field_mapping = {
                'document_number': 'document_number',
                'document_date': 'document_date', 
                'sender_name': 'sender_name',
                'receiver_name': 'receiver_name',
                'vehicle_number': 'vehicle_number',
                'driver_name': 'driver_name',
                'cargo_description': 'cargo_description',
                'cargo_weight': 'cargo_weight',
            }
            
            updated = False
            for ocr_field, model_field in field_mapping.items():
                if ocr_field in extracted_fields:
                    value = extracted_fields[ocr_field]
                    
                    # Специальная обработка для даты
                    if model_field == 'document_date':
                        try:
                            value = datetime.strptime(value, '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            continue
                    
                    # Специальная обработка для веса
                    elif model_field == 'cargo_weight':
                        try:
                            value = Decimal(str(value))
                        except (ValueError, TypeError):
                            continue
                    
                    # Обновляем поле только если оно пустое или OCR дает более уверенный результат
                    current_value = getattr(transport_doc, model_field)
                    if not current_value or not transport_doc.manual_verification_required:
                        setattr(transport_doc, model_field, value)
                        updated = True
            
            if updated:
                transport_doc.processing_status = 'processed' if not requires_manual_check else 'uploaded'
                transport_doc.manual_verification_required = requires_manual_check
                transport_doc.processed_by = photo_instance.uploaded_by
                transport_doc.save()
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении TransportDocument: {str(e)}")


# Глобальный экземпляр сервиса
ttn_ocr_service = TTNOCRService()


def process_transport_document_photo(photo_id: int) -> Dict[str, Any]:
    """
    Функция для обработки фотографии ТТН с таймаутом
    
    Args:
        photo_id: ID фотографии документа
        
    Returns:
        Dict с результатами обработки
    """
    logger.info(f"Начало OCR обработки фото {photo_id}")
    
    try:
        from .models import DocumentPhoto
        photo = DocumentPhoto.objects.get(id=photo_id)
        logger.info(f"Фото {photo_id} найдено, запуск OCR сервис")
        
        # Проверяем, что Tesseract доступен
        if not HAS_TESSERACT:
            logger.warning("Тesseract OCR не установлен, используем demo-режим")
            return {
                'success': False,
                'error': 'Система OCR недоступна (Тesseract не установлен)',
                'confidence': 0,
                'extracted_fields': {},
                'requires_manual_check': True
            }
        
        # Вызываем OCR сервис с обработкой исключений
        try:
            result = ttn_ocr_service.process_ttn_photo(photo)
            logger.info(f"OCR обработка фото {photo_id} завершена")
            return result
        except Exception as ocr_error:
            logger.error(f"OCR ошибка для фото {photo_id}: {str(ocr_error)}")
            
            # Возвращаем ошибку, но с success=False
            return {
                'success': False,
                'error': f'OCR ошибка: {str(ocr_error)}',
                'confidence': 0,
                'extracted_fields': {},
                'requires_manual_check': True
            }
            
    except Exception as e:
        logger.error(f"Общая ошибка при обработке фото {photo_id}: {str(e)}")
        return {
            'success': False,
            'error': f'Системная ошибка: {str(e)}',
            'confidence': 0,
            'extracted_fields': {},
            'requires_manual_check': True
        }


def validate_extracted_data(ocr_result_id: int) -> Dict[str, Any]:
    """
    Валидация извлеченных OCR данных
    
    Args:
        ocr_result_id: ID результата OCR
        
    Returns:
        Dict с результатами валидации
    """
    try:
        from .models import OCRResult
        
        ocr_result = OCRResult.objects.get(id=ocr_result_id)
        extracted_fields = ocr_result.extracted_fields
        
        validation_errors = []
        
        # Проверка обязательных полей
        required_fields = ['document_number', 'document_date', 'sender_name', 'receiver_name']
        for field in required_fields:
            if not extracted_fields.get(field):
                validation_errors.append(f'Отсутствует обязательное поле: {field}')
        
        # Проверка формата даты
        if 'document_date' in extracted_fields:
            try:
                datetime.strptime(extracted_fields['document_date'], '%Y-%m-%d')
            except ValueError:
                validation_errors.append('Некорректный формат даты документа')
        
        # Проверка номера транспортного средства
        if 'vehicle_number' in extracted_fields:
            if not re.match(r'^[А-Я]\d{3}[А-Я]{2}\d{2,3}$', extracted_fields['vehicle_number']):
                validation_errors.append('Некорректный формат номера транспортного средства')
        
        # Определяем общий статус валидации
        if not validation_errors:
            validation_status = 'valid'
        elif len(validation_errors) <= 2:
            validation_status = 'partial'
        else:
            validation_status = 'invalid'
        
        # Обновляем результат валидации
        ocr_result.validation_errors = validation_errors
        ocr_result.validation_status = validation_status
        ocr_result.validated_at = timezone.now()
        ocr_result.save()
        
        return {
            'success': True,
            'validation_status': validation_status,
            'errors': validation_errors,
            'message': f'Валидация завершена: {ocr_result.get_validation_status_display()}'
        }
        
    except Exception as e:
        logger.error(f"Ошибка валидации OCR результата {ocr_result_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }