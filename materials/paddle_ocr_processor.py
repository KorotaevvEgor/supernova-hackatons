"""
Локальный OCR процессор на базе PaddleOCR
Поддерживает русский язык, изображения и PDF файлы
Полностью автономное решение без зависимости от внешних API
"""

import logging
import os
import re
import fitz  # PyMuPDF для PDF
import io
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, List, Tuple, Optional
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class PaddleOCRProcessor:
    """
    Локальный OCR процессор на базе PaddleOCR
    Превосходная альтернатива внешним API сервисам
    """
    
    def __init__(self):
        self.ocr_engine = None
        self.supported_languages = ['ch', 'en', 'ru']  # Китайский, английский, русский
        
        # Регулярные выражения для извлечения полей из транспортных документов
        self.field_patterns = {
            'delivery_date': [
                r'дата[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
                r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})(?!\d)',
                r'от\s+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})',
                r'data[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})',
            ],
            
            'document_number': [
                r'№\s*(\d+[/\\][А-Яа-яA-Za-z]+)',
                r'№\s*(\d+)',
                r'no\.?\s*(\d+[/\\]?[А-Яа-яA-Za-z]*)',
                r'ттн\s*№?\s*(\d+[/\\]?[А-Яа-яA-Za-z]*)',
                r'накладная\s*№?\s*(\d+[/\\]?[А-Яа-яA-Za-z]*)',
            ],
            
            'supplier': [
                r'(?:грузоотправитель|отправитель)[:\s]*(ооо\s*["\«][^"\»\n]+["\»])',
                r'(?:грузоотправитель|отправитель)[:\s]*(зао\s*["\«][^"\»\n]+["\»])',
                r'(?:грузоотправитель|отправитель)[:\s]*(ип\s*[^\n]+)',
                r'(ооо\s*["\«][^"\»\n]+["\»])',
                r'(зао\s*["\«][^"\»\n]+["\»])',
                r'(ип\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                r'gruzootpravitel[:\s]*(ooo\s*["\«][^"\»\n]+["\»])',
            ],
            
            'material_type': [
                r'наименование[:\s\-]+([^,\nкол]+?)(?:,\s*\d+\s*шт|$)',
                r'груз[:\s]*наименование[:\s\-]+([^,\nкол]+?)(?:,|$)',
                r'(цемент[^\n,]+)',
                r'(песок[^\n,]*)',
                r'(щебень[^\n,]*)',
                r'(кирпич[^\n,]*)',
                r'naimenovanie[:\s\-]+([^,\nкол]+?)(?:,|$)',
                r'(cement[^\n,]*)',
            ],
            
            'quantity': [
                r'(\d+)\s*шт',
                r'(?:количество|кол[\-\s]*во)[:\s]*(\d+(?:[.,]\d+)?)(?:\s*шт|\s*тонн?|\s*т\.|\s*кг|\s*м³?|\s*м²)?',
                r'(\d+(?:[.,]\d+)?)\s*(?:тонн|т\.)',
                r'kolichestvo[:\s]*(\d+(?:[.,]\d+)?)',
            ],
            
            'driver_name': [
                r'водитель[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                r'фио\s+водителя[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                r'voditel[:\s]*([А-ЯЁA-Za-z][а-яёa-z]+\s+[А-ЯЁA-Za-z][а-яёa-z]+(?:\s+[А-ЯЁA-Za-z][а-яёa-z]+)?)',
            ],
            
            'vehicle_number': [
                r'(?:автомобиль|гос[\.\s]*номер)[:\s]*([А-ЯЁ]\d{3}[А-ЯЁ]{1,2}\d{2,3})',
                r'([А-ЯЁ]\d{3}[А-ЯЁ]{1,2}\d{2,3})(?![\dхx])',
                r'avtomobil[:\s]*([А-ЯЁA-Z]\d{3}[А-ЯЁA-Z]{1,2}\d{2,3})',
            ],
            
            'supplier_inn': [
                r'инн[:\s]*(\d{10,12})(?!\d)',
                r'inn[:\s]*(\d{10,12})(?!\d)',
            ],
            
            'cargo_weight': [
                r'(?:вес|масса)[:\s]*(\d+(?:[.,]\d+)?)\s*(?:кг|т)',
                r'(\d+(?:[.,]\d+)?)\s*(?:кг|тонн)',
                r'ves[:\s]*(\d+(?:[.,]\d+)?)',
                r'obshiy\s+ves[:\s]*(\d+(?:[.,]\d+)?)',
            ],
        }
    
    def _initialize_ocr(self):
        """Ленивая инициализация PaddleOCR"""
        if self.ocr_engine is None:
            try:
                from paddleocr import PaddleOCR
                
                # Инициализируем с поддержкой русского языка
                logger.info("Инициализация PaddleOCR с поддержкой русского языка...")
                
                # Минимальная инициализация PaddleOCR с только языком
                self.ocr_engine = PaddleOCR(lang='ru')
                
                logger.info("✅ PaddleOCR инициализирован успешно!")
                
            except Exception as e:
                logger.error(f"Ошибка инициализации PaddleOCR: {str(e)}")
                raise Exception(f"Не удалось инициализировать PaddleOCR: {str(e)}")
    
    def _detect_file_type(self, file_data: bytes) -> str:
        """Определяем тип файла по его сигнатуре"""
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
    
    def _convert_pdf_to_image(self, pdf_data: bytes, page_num: int = 0, dpi: int = 200) -> bytes:
        """Упрощенная стабильная конвертация PDF"""
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            page_count = len(pdf_document)
            
            if page_num >= page_count:
                page_num = 0
                
            page = pdf_document[page_num]
            
            # Стандартное разрешение для стабильности
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            # Простой рендеринг
            pix = page.get_pixmap(matrix=mat)
            
            img_data = pix.tobytes("png")
            pdf_document.close()
            
            logger.info(f"PDF страница {page_num + 1} конвертирована в изображение {dpi} DPI ({pix.width}x{pix.height})")
            return img_data
            
        except Exception as e:
            logger.error(f"Ошибка конвертации PDF: {str(e)}")
            raise Exception(f"Не удалось конвертировать PDF: {str(e)}")
    
    def _enhance_image_for_ocr(self, image_data: bytes) -> np.ndarray:
        """Упрощенная стабильная обработка изображения"""
        try:
            # Открываем изображение
            img = Image.open(io.BytesIO(image_data))
            
            # Преобразуем в RGB если нужно
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            original_width, original_height = img.size
            logger.info(f"Оригинальный размер: {original_width}x{original_height}")
            
            # Очень консервативное масштабирование для стабильности
            width, height = img.size
            if width < 800 or height < 600:
                # Умеренное увеличение только для маленьких изображений
                scale_factor = max(800 / width, 600 / height, 1.2)
                new_width = min(int(width * scale_factor), 1600)  # Макс 1600px
                new_height = min(int(height * scale_factor), 1200)  # Макс 1200px
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Масштабирование: {new_width}x{new_height}")
            
            # Минимальные улучшения
            # Легкое улучшение контраста
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)  # Минимальное улучшение
            
            # Конвертируем в numpy array для PaddleOCR
            img_array = np.array(img)
            
            logger.info(f"Итоговый размер для OCR: {img_array.shape}")
            return img_array
            
        except Exception as e:
            logger.warning(f"Ошибка при улучшении изображения: {str(e)}")
            # Возвращаем оригинальное изображение как numpy array
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return np.array(img)
    
    def process_document(self, image_data: bytes, file_type: str = None) -> Dict[str, any]:
        """
        Основной метод обработки документа через PaddleOCR
        Поддерживает как изображения, так и PDF файлы
        """
        try:
            logger.info("Начало обработки документа через PaddleOCR")
            
            # Инициализируем OCR если еще не сделали
            self._initialize_ocr()
            
            # Определяем тип файла
            detected_type = self._detect_file_type(image_data) if not file_type else file_type
            logger.info(f"Обнаружен тип файла: {detected_type}")
            
            # Конвертируем PDF в изображение если нужно
            if detected_type.lower() == 'pdf':
                image_data = self._convert_pdf_to_image(image_data)
                logger.info("Конвертация PDF в изображение завершена")
            
            # Предварительная обработка изображения
            enhanced_image = self._enhance_image_for_ocr(image_data)
            
            # Выполняем OCR распознавание
            logger.info("Запуск PaddleOCR распознавания...")
            ocr_result = self.ocr_engine.predict(enhanced_image)
            
            # Обрабатываем результат
            if not ocr_result or len(ocr_result) == 0:
                return {
                    'success': False,
                    'error': 'Не удалось распознать текст в документе',
                    'fields': {},
                    'confidence': 0,
                    'raw_text': ''
                }
            
            # Извлекаем текст и координаты
            raw_text_lines = []
            total_confidence = 0
            confidence_count = 0
            
            # Новый формат PaddleOCR - словарь с ключами rec_texts и rec_scores
            if isinstance(ocr_result, list) and len(ocr_result) > 0 and isinstance(ocr_result[0], dict):
                result_data = ocr_result[0]
                if 'rec_texts' in result_data and 'rec_scores' in result_data:
                    raw_text_lines = result_data['rec_texts']
                    confidences = result_data['rec_scores']
                    
                    for i, text in enumerate(raw_text_lines):
                        confidence = confidences[i] if i < len(confidences) else 0.8
                        total_confidence += confidence
                        confidence_count += 1
                else:
                    logger.warning("Неожиданный формат результата PaddleOCR")
                    return {
                        'success': False,
                        'error': 'Неожиданный формат результата',
                        'fields': {},
                        'confidence': 0,
                        'raw_text': ''
                    }
            elif isinstance(ocr_result, list) and len(ocr_result) > 0 and ocr_result[0]:
                # Старый формат - список кортежей
                for line in ocr_result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                        confidence = line[1][1] if isinstance(line[1], tuple) and len(line[1]) > 1 else 0.8
                        
                        raw_text_lines.append(text)
                        total_confidence += confidence
                        confidence_count += 1
            else:
                logger.warning("Пустой результат OCR")
                return {
                    'success': False,
                    'error': 'Пустой результат OCR',
                    'fields': {},
                    'confidence': 0,
                    'raw_text': ''
                }
            
            # Проверяем, что текст распознан
            if not raw_text_lines:
                return {
                    'success': False,
                    'error': 'Текст не распознан',
                    'fields': {},
                    'confidence': 0,
                    'raw_text': ''
                }
            
            raw_text = '\n'.join(raw_text_lines)
            overall_confidence = int((total_confidence / confidence_count * 100)) if confidence_count > 0 else 0
            
            logger.info(f"PaddleOCR распознал {len(raw_text_lines)} строк текста")
            logger.info(f"Средняя уверенность: {overall_confidence}%")
            
            # Извлекаем структурированные данные
            structured_data = self.extract_structured_data(raw_text)
            
            # Финальная уверенность с учетом найденных полей
            final_confidence = min(overall_confidence + len(structured_data['fields']) * 2, 100)
            
            logger.info(f"Обработка завершена. Найдено полей: {len(structured_data['fields'])}")
            
            return {
                'success': True,
                'fields': structured_data['fields'],
                'confidence': final_confidence,
                'field_confidences': structured_data.get('field_confidences', {}),
                'raw_text': raw_text,
                'ocr_service': 'PaddleOCR (Локальный)',
                'lines_count': len(raw_text_lines)
            }
            
        except Exception as e:
            logger.error(f"Ошибка в process_document: {str(e)}")
            return {
                'success': False,
                'error': f"Ошибка обработки: {str(e)}",
                'fields': {},
                'confidence': 0,
                'raw_text': ''
            }
    
    def extract_structured_data(self, text: str) -> Dict[str, any]:
        """Извлечение структурированных данных из текста"""
        results = {}
        confidence_scores = {}
        
        # Предобработка текста
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
                    
                    # Оценка уверенности
                    confidence = self.calculate_field_confidence(field, match)
                    
                    if confidence > best_confidence:
                        best_match = match.strip()
                        best_confidence = confidence
            
            if best_match:
                processed_value = self.post_process_field(field, best_match)
                if processed_value:
                    results[field] = processed_value
                    confidence_scores[field] = best_confidence
        
        return {
            'fields': results,
            'field_confidences': confidence_scores
        }
    
    def calculate_field_confidence(self, field: str, value: str) -> float:
        """Вычисление уверенности для конкретного поля"""
        if not value or len(value.strip()) < 2:
            return 0
        
        confidence = 75  # Базовая уверенность для PaddleOCR (высокая)
        
        # Специфичные проверки для разных полей
        if field == 'supplier':
            if any(word in value.lower() for word in ['ооо', 'зао', 'ип', 'ooo']):
                confidence += 20
            if len(value) > 10:
                confidence += 5
                
        elif field == 'quantity':
            if re.match(r'\d+([.,]\d+)?$', value):
                confidence += 20
                
        elif field == 'delivery_date':
            if re.match(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$', value):
                confidence += 20
                
        elif field == 'vehicle_number':
            if re.match(r'[А-ЯЁA-Z]\d{3}[А-ЯЁA-Z]{2}\d{2,3}$', value):
                confidence += 25
                
        elif field == 'supplier_inn':
            if re.match(r'\d{10,12}$', value):
                confidence += 25
        
        return min(confidence, 100)
    
    def post_process_field(self, field: str, value: str) -> Optional[str]:
        """Постобработка извлеченных полей"""
        if not value:
            return None
            
        value = value.strip()
        
        if field == 'delivery_date':
            # Нормализуем формат даты
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
            
        elif field == 'quantity' or field == 'cargo_weight':
            # Нормализуем числовые значения
            value = value.replace(',', '.')
            try:
                float(value)
                return value
            except ValueError:
                return None
                
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
    
    def get_pdf_page_count(self, pdf_data: bytes) -> int:
        """Получаем количество страниц в PDF документе"""
        try:
            pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
            page_count = len(pdf_document)
            pdf_document.close()
            return page_count
        except Exception as e:
            logger.error(f"Ошибка при определении количества страниц PDF: {str(e)}")
            return 1


# Создаем глобальный экземпляр процессора
paddle_ocr_processor = None

def get_paddle_ocr_processor():
    """Ленивая инициализация PaddleOCR процессора"""
    global paddle_ocr_processor
    if paddle_ocr_processor is None:
        paddle_ocr_processor = PaddleOCRProcessor()
    return paddle_ocr_processor