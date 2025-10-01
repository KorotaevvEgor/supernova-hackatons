"""
OCR процессор с использованием облачного сервиса OCR.space
Обеспечивает высокое качество распознавания текста на русском и английском языках
"""

import requests
import base64
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import re
from django.conf import settings
from PIL import Image, ImageEnhance, ImageFilter
import io
import fitz  # PyMuPDF для работы с PDF

logger = logging.getLogger(__name__)

class OCRSpaceProcessor:
    """
    Процессор для OCR через OCR.space API
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or getattr(settings, 'OCR_SPACE_API_KEY', '')
        self.api_url = "https://api.ocr.space/parse/image"
        
        # Оптимальные настройки для русского OCR с Engine 2 (как на сайте)
        self.default_params = {
            'apikey': self.api_key,
            'language': 'rus',              # Русский язык (основной)
            'OCREngine': '2',               # Engine 2 - лучше для кириллицы, цифр и спецсимволов
            'detectOrientation': 'true',    # Автоопределение ориентации
            'scale': 'true',                # Auto-enlarge content (рекомендуемо для low DPI) - как на сайте
            'isTable': 'true',              # Включаем режим таблиц для структурированных документов
            'isOverlayRequired': 'true',    # Включаем overlay для максимального качества
            'isSearchablePdfHideTextLayer': 'false',
            'isCreateSearchablePdf': 'false',
            'filetype': 'AUTO',             # Автоопределение типа файла
        }
        
        # Дополнительная конфигурация для смешанного режима (fallback)
        self.mixed_params = {
            'apikey': self.api_key,
            'language': 'eng',              # Английский как fallback (лучшая совместимость)
            'OCREngine': '2',               # Engine 2 - оптимален для цифр и спецсимволов
            'detectOrientation': 'true',
            'scale': 'true',                # Auto-enlarge content (рекомендуемо для low DPI) - как на веб-сайте
            'isTable': 'true',              # Режим таблиц для лучшего структурирования
            'isOverlayRequired': 'true',    # Включаем overlay для максимального качества
            'isSearchablePdfHideTextLayer': 'false',
            'isCreateSearchablePdf': 'false',
            'filetype': 'AUTO',             # Автоопределение типа файла
        }
        
        # Регулярные выражения для извлечения полей из транспортных документов
        self.field_patterns = {
            'delivery_date': [
                r'дата[:\s]*([\d]{1,2}[.\-/][\d]{1,2}[.\-/][\d]{2,4})',
                r'([\d]{1,2}[.\-/][\d]{1,2}[.\-/][\d]{4})(?!\d)',
                r'от\s+([\d]{1,2}[.\-/][\d]{1,2}[.\-/][\d]{4})',
            ],
            
            'document_number': [
                r'№\s*([\d]+[/\\][А-Яа-яA-Za-z]+)',
                r'№\s*([\d]+)',
                r'ттн\s*№?\s*([\d]+[/\\]?[А-Яа-яA-Za-z]*)',
                r'накладная\s*№?\s*([\d]+[/\\]?[А-Яа-яA-Za-z]*)',
            ],
            
            'supplier': [
                r'(?:грузоотправитель|отправитель)[:\s]*(ооо\s*["\«][^"\»\n]+["\»])',
                r'(?:грузоотправитель|отправитель)[:\s]*(зао\s*["\«][^"\»\n]+["\»])',
                r'(?:грузоотправитель|отправитель)[:\s]*(ип\s*[^\n]+)',
                r'(ооо\s*["\«][^"\»\n]+["\»])',
                r'(зао\s*["\«][^"\»\n]+["\»])',
                r'(ип\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            ],
            
            'material_type': [
                r'наименование[:\s\-]+([^,\nкол]+?)(?:,\s*\d+\s*шт|$)',
                r'груз[:\s]*наименование[:\s\-]+([^,\nкол]+?)(?:,|$)',
                r'(бортовой\s+камень[\s\dхx×мм\-]+)',
                r'(цемент[\s\w\d]+)',
                r'(песок[\s\w]+)',
                r'(щебень[\s\w\d\-]+)',
                r'(кирпич[\s\w]+)',
                r'(плитка[\s\w\dхx×мм]+)',
            ],
            
            'package_count': [
                r'(?:кол[\-\s]*во\s+мест|количество\s+мест)[:\s]*([\d]+)',
                r'мест[:\s]*([\d]+)',
                r'([\d]+)\s*мест',
            ],
            
            'quantity': [
                r'([\d]+)\s*шт',
                r'(?:количество|кол[\-\s]*во)[:\s]*([\d]+(?:[.,][\d]+)?)(?:\s*шт|\s*тонн?|\s*т\.|\s*кг|\s*м³?|\s*м²)?',
                r'([\d]+(?:[.,][\d]+)?)\s*(?:тонн|т\.)',
            ],
            
            'driver_name': [
                r'водитель[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                r'фио\s+водителя[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            ],
            
            'vehicle_number': [
                r'(?:автомобиль|гос[\.\s]*номер)[:\s]*([А-ЯЁ]\d{3}[А-ЯЁ]{1,2}\d{2,3})',
                r'([А-ЯЁ]\d{3}[А-ЯЁ]{1,2}\d{2,3})(?![\dхx])',
            ],
            
            'supplier_inn': [
                r'инн[:\s]*([\d]{10,12})(?!\d)',
            ],
            
            'cargo_weight': [
                r'(?:вес|масса)[:\s]*([\d]+(?:[.,][\d]+)?)\s*(?:кг|т)',
                r'([\d]+(?:[.,][\d]+)?)\s*(?:кг|тонн)',
            ],
        }
    
    def process_document(self, image_data: bytes, file_type: str = None) -> Dict[str, any]:
        """
        Основной метод обработки документа через OCR.space API с фолбэком
        Поддерживает как изображения, так и PDF файлы
        """
        try:
            logger.info("Начало обработки документа через OCR.space API")
            
            # Определяем тип файла
            detected_type = self._detect_file_type(image_data) if not file_type else file_type
            logger.info(f"Обнаружен тип файла: {detected_type}")
            
            # Конвертируем PDF в изображение если нужно
            if detected_type.lower() == 'pdf':
                # Получаем номер страницы из дополнительных параметров
                page_num = 0  # По умолчанию первая страница
                image_data = self._convert_pdf_to_image(image_data, page_num)
                logger.info(f"Конвертация PDF страницы {page_num + 1} в изображение завершена")
            
            # Предварительная обработка изображения
            enhanced_image_data = self._enhance_image_for_ocr(image_data)
            
            # Конвертируем улучшенное изображение в base64
            image_base64 = base64.b64encode(enhanced_image_data).decode('utf-8')
            
            # Сначала пробуем чисто русский режим
            result = self._try_ocr_with_config(image_base64, self.default_params, "русский")
            
            # Если результат недостаточно хороший, пробуем смешанный режим
            if (result.get('success') and 
                (len(result.get('raw_text', '')) < 50 or 
                 len(result.get('fields', {})) < 3 or
                 result.get('confidence', 0) < 60)):
                
                logger.info("Результат чисто русского режима недостаточен. Пробуем смешанный режим...")
                fallback_result = self._try_ocr_with_config(image_base64, self.mixed_params, "смешанный")
                
                # Выбираем лучший результат
                if (fallback_result.get('success') and
                    (len(fallback_result.get('fields', {})) > len(result.get('fields', {})) or
                     fallback_result.get('confidence', 0) > result.get('confidence', 0))):
                    logger.info("Смешанный режим показал лучшие результаты")
                    result = fallback_result
            
            return result
                
        except Exception as e:
            logger.error(f"Ошибка в process_document: {str(e)}")
            return {
                'success': False,
                'error': f"Ошибка обработки: {str(e)}",
                'fields': {},
                'confidence': 0,
                'raw_text': ''
            }
    
    def _try_ocr_with_config(self, image_base64: str, config: dict, mode_name: str) -> Dict[str, any]:
        """
        Попытка OCR с определенной конфигурацией
        """
        try:
            # Подготавливаем данные для API
            payload = config.copy()
            
            # Используем files parameter вместо base64 для лучшей совместимости
            import base64
            image_bytes = base64.b64decode(image_base64)
            files = {
                'file': ('document.png', image_bytes, 'image/png')
            }
            
            # Отладка: показываем параметры запроса
            logger.info(f"Отладка параметров ({mode_name}):")
            for key, value in payload.items():
                if key == 'apikey':
                    logger.info(f"  {key}: {value[:10]}...")
                else:
                    logger.info(f"  {key}: {value}")
            logger.info(f"  files: document.png ({len(image_bytes)} байт)")
            
            # Делаем запрос к OCR.space API
            logger.info(f"Отправка запроса к OCR.space API (режим: {mode_name})...")
            response = requests.post(self.api_url, data=payload, files=files, timeout=30)
            
            if response.status_code != 200:
                error_msg = f"API запрос неуспешен: статус {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'fields': {},
                    'confidence': 0,
                    'raw_text': ''
                }
            
            # Парсим ответ
            api_result = response.json()
            
            if not api_result.get('IsErroredOnProcessing', True):
                # Извлекаем текст из ответа
                parsed_results = api_result.get('ParsedResults', [])
                if not parsed_results:
                    return {
                        'success': False,
                        'error': 'Нет результатов распознавания',
                        'fields': {},
                        'confidence': 0,
                        'raw_text': ''
                    }
                
                # Берем первый результат (обычно основной)
                first_result = parsed_results[0]
                raw_text = first_result.get('ParsedText', '').strip()
                
                logger.info(f"Получен текст длиной {len(raw_text)} символов (режим: {mode_name})")
                
                # Извлекаем структурированные данные
                structured_data = self.extract_structured_data(raw_text)
                
                # Вычисляем confidence на основе найденных полей
                confidence = self.calculate_overall_confidence(structured_data['fields'])
                
                logger.info(f"Обработка завершена (режим: {mode_name}). Найдено полей: {len(structured_data['fields'])}, уверенность: {confidence}%")
                
                return {
                    'success': True,
                    'fields': structured_data['fields'],
                    'confidence': confidence,
                    'field_confidences': structured_data.get('field_confidences', {}),
                    'raw_text': raw_text,
                    'ocr_service': f'OCR.space ({mode_name})'
                }
            else:
                error_msg = api_result.get('ErrorMessage', ['Неизвестная ошибка OCR'])
                if isinstance(error_msg, list):
                    error_msg = '; '.join(error_msg)
                    
                logger.error(f"Ошибка OCR.space API (режим: {mode_name}): {error_msg}")
                return {
                    'success': False,
                    'error': f"OCR.space ошибка ({mode_name}): {error_msg}",
                    'fields': {},
                    'confidence': 0,
                    'raw_text': ''
                }
                
        except requests.exceptions.Timeout:
            error_msg = f"Превышено время ожидания ответа от OCR.space API ({mode_name})"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'fields': {},
                'confidence': 0,
                'raw_text': ''
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка сетевого запроса ({mode_name}): {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'fields': {},
                'confidence': 0,
                'raw_text': ''
            }
        except Exception as e:
            error_msg = f"Неожиданная ошибка ({mode_name}): {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'fields': {},
                'confidence': 0,
                'raw_text': ''
            }
    
    def extract_structured_data(self, text: str) -> Dict[str, any]:
        """
        Извлечение структурированных данных из текста
        """
        results = {}
        confidence_scores = {}
        
        # Предобработка текста (убираем лишние переносы и пробелы)
        text = re.sub(r'\r\n|\r|\n', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        logger.debug(f"Обработка текста: {text[:200]}...")
        
        for field, patterns in self.field_patterns.items():
            best_match = None
            best_confidence = 0
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    match = matches[0]
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Оценка уверенности на основе длины и содержания
                    confidence = self.calculate_field_confidence(field, match)
                    
                    if confidence > best_confidence:
                        best_match = match.strip()
                        best_confidence = confidence
            
            if best_match:
                # Постобработка поля
                processed_value = self.post_process_field(field, best_match)
                if processed_value:
                    results[field] = processed_value
                    confidence_scores[field] = best_confidence
        
        return {
            'fields': results,
            'field_confidences': confidence_scores
        }
    
    def calculate_field_confidence(self, field: str, value: str) -> float:
        """
        Вычисление уверенности для конкретного поля
        """
        if not value or len(value.strip()) < 2:
            return 0
        
        confidence = 70  # базовая уверенность для OCR.space Engine 2 (оптимален для цифр и спецсимволов)
        
        # Специфичные проверки для разных полей
        if field == 'supplier':
            if any(word in value.lower() for word in ['ооо', 'зао', 'ип', 'оао']):
                confidence += 25
            if len(value) > 10:
                confidence += 10
                
        elif field == 'quantity':
            if re.match(r'\d+([.,]\d+)?$', value):
                confidence += 30
                
        elif field == 'delivery_date':
            if re.match(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$', value):
                confidence += 30
                
        elif field == 'vehicle_number':
            if re.match(r'[А-ЯЁ]\d{3}[А-ЯЁ]{2}\d{2,3}$', value):
                confidence += 35
                
        elif field == 'supplier_inn':
            if re.match(r'\d{10,12}$', value):
                confidence += 35
                
        elif field == 'package_count':
            if re.match(r'\d+$', value) and int(value) > 0:
                confidence += 30
        
        return min(confidence, 100)
    
    def post_process_field(self, field: str, value: str) -> Optional[str]:
        """
        Постобработка извлеченных полей
        """
        if not value:
            return None
            
        value = value.strip()
        
        if field == 'quantity':
            # Нормализуем десятичные разделители
            value = value.replace(',', '.')
            try:
                float(value)
                return value
            except ValueError:
                return None
                
        elif field == 'delivery_date':
            # Нормализуем формат даты к стандартному ISO
            value = re.sub(r'[.\-/]', '.', value)
            try:
                parts = value.split('.')
                if len(parts) == 3:
                    day, month, year = parts
                    if len(year) == 2:
                        year = '20' + year
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
            return value
            
        elif field == 'cargo_weight':
            # Извлекаем только числовое значение
            match = re.search(r'\d+(?:[.,]\d+)?', value)
            if match:
                return match.group().replace(',', '.')
                
        elif field == 'supplier_inn':
            # Оставляем только цифры
            digits = re.sub(r'\D', '', value)
            if len(digits) in [10, 12]:
                return digits
                
        elif field == 'supplier':
            # Нормализуем организационно-правовые формы
            value = re.sub(r'\bооо\b', 'ООО', value, flags=re.IGNORECASE)
            value = re.sub(r'\bзао\b', 'ЗАО', value, flags=re.IGNORECASE)
            value = re.sub(r'\bоао\b', 'ОАО', value, flags=re.IGNORECASE)
            value = re.sub(r'\bип\b', 'ИП', value, flags=re.IGNORECASE)
                
        return value
    
    def calculate_overall_confidence(self, fields: Dict[str, any]) -> int:
        """
        Вычисляем общую уверенность на основе количества найденных полей
        """
        if not fields:
            return 0
        
        # Базовая уверенность за использование OCR.space Engine 2
        base_confidence = 75
        
        # Дополнительная уверенность за каждое найденное поле
        field_bonus = min(len(fields) * 3, 25)
        
        return min(base_confidence + field_bonus, 100)
    
    def _enhance_image_for_ocr(self, image_data: bytes) -> bytes:
        """
        Предварительная обработка изображения для улучшения OCR
        Как на сайте OCR.space - улучшаем контраст, резкость и масштаб
        """
        try:
            # Открываем изображение
            img = Image.open(io.BytesIO(image_data))
            
            # Преобразуем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 1. Оптимизируем размер для работы с Auto-enlarge API
            width, height = img.size
            # Поскольку API с scale=true сам увеличивает, мы делаем умеренное увеличение
            if width < 800 or height < 600:
                # Минимальное увеличение до приемлемого размера
                scale_factor = max(800 / width, 600 / height, 1.2)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Предварительное масштабирование: {width}x{height} -> {new_width}x{new_height}")
            
            # 2. Улучшаем контраст
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)  # Увеличиваем контраст на 20%
            
            # 3. Улучшаем резкость
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.1)  # Немного увеличиваем резкость
            
            # 4. Легкая очистка от шума
            img = img.filter(ImageFilter.MedianFilter(size=3))
            
            # 5. Сохраняем в высоком качестве
            output = io.BytesIO()
            img.save(output, format='PNG', optimize=False, quality=95)
            enhanced_data = output.getvalue()
            
            logger.info(f"Изображение улучшено: {len(image_data)} -> {len(enhanced_data)} байт")
            return enhanced_data
            
        except Exception as e:
            logger.warning(f"Ошибка при улучшении изображения: {str(e)}")
            # Возвращаем оригинальное изображение при ошибке
            return image_data
    
    def _detect_file_type(self, file_data: bytes) -> str:
        """
        Определяем тип файла по его сигнатуре
        """
        # Проверяем сигнатуры файлов
        if file_data.startswith(b'%PDF'):
            return 'pdf'
        elif file_data.startswith(b'\xff\xd8\xff'):
            return 'jpeg'
        elif file_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        elif file_data.startswith(b'GIF87a') or file_data.startswith(b'GIF89a'):
            return 'gif'
        elif file_data.startswith(b'BM'):
            return 'bmp'
        elif file_data.startswith(b'RIFF') and b'WEBP' in file_data[:12]:
            return 'webp'
        else:
            return 'unknown'
    
    def get_pdf_page_count(self, pdf_data: bytes) -> int:
        """
        Получаем количество страниц в PDF документе
        """
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            page_count = len(pdf_document)
            pdf_document.close()
            return page_count
        except Exception as e:
            logger.error(f"Ошибка при определении количества страниц PDF: {str(e)}")
            return 1  # По умолчанию считаем, что есть минимум 1 страница
    
    def _convert_pdf_to_image(self, pdf_data: bytes, page_num: int = 0, dpi: int = 200) -> bytes:
        """
        Конвертируем PDF в изображение
        
        Args:
            pdf_data: данные PDF файла
            page_num: номер страницы (по умолчанию первая)
            dpi: разрешение для конвертации
        
        Returns:
            bytes: данные изображения в формате PNG
        """
        try:
            # Открываем PDF из байтов
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            
            # Проверяем количество страниц
            page_count = len(pdf_document)
            logger.info(f"PDF содержит {page_count} страниц(ы)")
            
            # Ограничиваем номер страницы
            if page_num >= page_count:
                page_num = 0
                logger.warning(f"Запрошенная страница {page_num} не существует. Используем первую страницу.")
            
            # Получаем страницу
            page = pdf_document[page_num]
            
            # Конвертируем в изображение
            # Матрица масштабирования для указанного DPI
            zoom = dpi / 72  # 72 DPI - стандартное разрешение PDF
            mat = fitz.Matrix(zoom, zoom)
            
            # Получаем pixmap (растровое изображение)
            pix = page.get_pixmap(matrix=mat)
            
            # Конвертируем в PNG байты
            img_data = pix.tobytes("png")
            
            # Закрываем PDF
            pdf_document.close()
            
            logger.info(f"Конвертация PDF страницы {page_num + 1} завершена успешно")
            return img_data
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF: {str(e)}")
            raise Exception(f"Не удалось конвертировать PDF: {str(e)}")

# Создаем глобальный экземпляр процессора
ocr_space_processor = None

def get_ocr_space_processor():
    """
    Ленивая инициализация OCR.space процессора
    """
    global ocr_space_processor
    if ocr_space_processor is None:
        ocr_space_processor = OCRSpaceProcessor()
    return ocr_space_processor