"""
Модуль для OCR распознавания документов поставки материалов.
Использует Tesseract OCR с предобработкой изображений через OpenCV.
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
import re
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import io
import base64

logger = logging.getLogger(__name__)

class DocumentOCRProcessor:
    """
    Основной класс для обработки документов с помощью OCR
    """
    
    def __init__(self):
        # Продвинутая конфигурация Tesseract
        self.tesseract_configs = {
            'main': r'--oem 3 --psm 6 -l rus+eng -c tessedit_char_whitelist=АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЬЫЪЭЮЯабвгдеёжзийклмнопрстуфхцчшщьыъэюяABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?:;-\"/()%№«» ТТН',
            'numbers': r'--oem 3 --psm 8 -l eng -c tessedit_char_whitelist=0123456789./№-',
            'mixed': r'--oem 3 --psm 6 -l rus+eng',
            'single_block': r'--oem 3 --psm 7 -l rus+eng'
        }
        
        # Регулярные выражения для поиска различных полей транспортной накладной
        self.patterns = {
            # 1) Дата - пример [10.06.2014]
            'delivery_date': [
                r'дата[:\s]*(\d{1,2}[.]\d{1,2}[.]\d{4})',
                r'(\d{1,2}[.]\d{1,2}[.]\d{4})(?!\d)',
                r'от\s+(\d{1,2}[.]\d{1,2}[.]\d{4})',
            ],
            
            # 2) № - пример [18674/Б]
            'document_number': [
                r'№[\s:]*(\d+[/\\][А-Яа-яA-Za-z]+)',  # 18674/Б
                r'№[\s:]*(\d+)',  # простой номер
                r'ТТН[\s№:-]*(\d+[/\\][А-Яа-яA-Za-z]*)',
                r'накладная[\s№:]*(\d+[/\\]?[А-Яа-яA-Za-z]*)',
            ],
            
            # 3) Грузоотправитель - пример [ООО "БЕКАМ"]
            'supplier': [
                r'(?:грузоотправитель|отправитель)[:\s]*(ООО[\s"]*[^"\n]+["]*)',
                r'(?:грузоотправитель|отправитель)[:\s]*(ЗАО[\s"]*[^"\n]+["]*)',
                r'(?:грузоотправитель|отправитель)[:\s]*(ИП[\s]*[^\n]+)',
                r'(ООО[\s]*["«][^"»\n]+["»])',  # ООО "БЕКАМ"
                r'(ЗАО[\s]*["«][^"»\n]+["»])',
                r'(ИП[\s]*[А-Я][а-я]+[\s]+[А-Я][а-я]+[\s]*[А-Я][а-я]*)',
            ],
            
            # 4) Груз - пример [Наименование - Бортовой камень 1000х300х150, 198 шт]
            'material_type': [
                r'наименование[\s\-]+([^,\nКол]+?)(?:,\s*\d+\s*шт|$)',
                r'груз[:\s]*наименование[\s\-]+([^,\nКол]+?)(?:,|$)',
                # Специфичные материалы
                r'(бортовой\s+камень[\s\d×хxмм]+)',
                r'(цемент[\s\w\d]+)',
                r'(песок[\s\w]+)',
                r'(щебень[\s\w\d\-]+)',
                r'(кирпич[\s\w]+)',
                r'(плитка[\s\w\d×хxмм]+)',
            ],
            
            # 5) Кол-во мест - пример [11]
            'package_count': [
                r'(?:кол[\-\s]*во\s+мест|количество\s+мест)[:\s]*(\d+)',
                r'мест[:\s]*(\d+)',
                r'(\d+)\s*мест',
            ],
            
            # Количество штук из описания груза
            'quantity': [
                r'(\d+)\s*шт',  # 198 шт
                r'(?:количество|кол[\-\s]*во)[:\s]*(\d+(?:[.,]\d+)?)(?:\s*шт|\s*тонн?|\s*т\.|\s*кг|\s*м³?|\s*м²)?',
                r'(\d+(?:[.,]\d+)?)\s*(?:тонн|т\.)',
            ],
            
            # Дополнительные поля
            'driver_name': [
                r'водитель[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
                r'ФИО\s+водителя[:\s]*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)',
            ],
            
            'vehicle_number': [
                r'автомобиль[:\s]*([A-ЯЁКМНОПРСТУХ]\d{3}[A-ЯЁКМНОПРСТУХ]{1,2}\d{2,3})',
                r'([A-ЯЁКМНОПРСТУХ]\d{3}[A-ЯЁКМНОПРСТУХ]{1,2}\d{2,3})(?![\dхx])',
            ],
            
            'supplier_inn': [
                r'ИНН[:\s]*(\d{10,12})(?!\d)',
            ],
            
            'cargo_weight': [
                r'(?:вес|масса)[:\s]*(\d+(?:[.,]\d+)?)\s*(?:кг|т)',
                r'(\d+(?:[.,]\d+)?)\s*(?:кг|тонн)',
            ],
        }
    
    def preprocess_image(self, image_data: bytes) -> List[np.ndarray]:
        """
        Продвинутая предобработка с множественными вариантами
        """
        try:
            # Конвертируем байты в numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError("Не удалось декодировать изображение")
            
            # Увеличиваем разрешение, если изображение маленькое
            height, width = img.shape[:2]
            if width < 1000 or height < 800:
                scale_factor = max(1000/width, 800/height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            processed_images = []
            
            # Вариант 1: Адаптивная бинаризация
            adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            # Очищаем от шума
            kernel = np.ones((2, 2), np.uint8)
            adaptive_clean = cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel)
            adaptive_clean = cv2.morphologyEx(adaptive_clean, cv2.MORPH_OPEN, kernel)
            processed_images.append(adaptive_clean)
            
            # Вариант 2: CLAHE + Otsu
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            # Убираем шум
            denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
            _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(otsu)
            
            # Вариант 3: Морфологическая обработка
            # Убираем тонкие линии и шум
            kernel_horizontal = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            kernel_vertical = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            
            # Найдем и уберем горизонтальные линии
            horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel_horizontal)
            # Найдем и уберем вертикальные линии
            vertical_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel_vertical)
            
            # Удаляем линии из изображения
            img_no_lines = gray.copy()
            img_no_lines = cv2.subtract(img_no_lines, horizontal_lines)
            img_no_lines = cv2.subtract(img_no_lines, vertical_lines)
            
            # Бинаризация
            _, clean_binary = cv2.threshold(img_no_lines, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(clean_binary)
            
            return processed_images
            
        except Exception as e:
            logger.error(f"Ошибка предобработки изображения: {str(e)}")
            # Возвращаем базовую обработку
            nparr = np.frombuffer(image_data, np.uint8)
            basic = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            return [basic] if basic is not None else []
    
    def extract_text_from_images(self, processed_images: List[np.ndarray]) -> str:
        """
        Извлечение текста с помощью нескольких методов и конфигураций
        """
        best_text = ""
        max_length = 0
        
        try:
            for i, processed_image in enumerate(processed_images):
                if processed_image is None:
                    continue
                    
                # Конвертируем в PIL Image для Tesseract
                pil_image = Image.fromarray(processed_image)
                
                # Пробуем различные конфигурации
                configs_to_try = ['main', 'mixed', 'single_block']
                
                for config_name in configs_to_try:
                    try:
                        config = self.tesseract_configs.get(config_name, self.tesseract_configs['mixed'])
                        text = pytesseract.image_to_string(pil_image, config=config)
                        cleaned_text = self.clean_text(text)
                        
                        # Выбираем наиболее длинный результат
                        if len(cleaned_text) > max_length:
                            max_length = len(cleaned_text)
                            best_text = cleaned_text
                            logger.info(f"Лучший результат: вариант {i+1}, конфиг {config_name}, длина: {len(cleaned_text)}")
                    except Exception as e:
                        logger.warning(f"Ошибка с конфигом {config_name}: {str(e)}")
                        continue
            
            # Постобработка текста
            if best_text:
                best_text = self.post_process_text(best_text)
            
            logger.info(f"Окончательный результат: {len(best_text)} символов")
            return best_text
            
        except Exception as e:
            logger.error(f"Ошибка извлечения текста: {str(e)}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """
        Очистка извлеченного текста
        """
        # Убираем лишние пробелы и переносы
        cleaned = re.sub(r'\n+', '\n', text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Убираем спецсимволы, которые часто неправильно распознаются
        cleaned = re.sub(r'[|\\]', '', cleaned)
        
        return cleaned.strip()
    
    def post_process_text(self, text: str) -> str:
        """
        Постобработка текста для исправления ошибок OCR
        """
        if not text:
            return text
            
        # Словарь замен для частых ошибок OCR
        replacements = {
            # Ошибки в ключевых словах
            r'\btранспортная\b': 'ТРАНСПОРТНАЯ',
            r'\bнакладная\b': 'НАКЛАДНАЯ',
            r'\bгрузоотправитель\b': 'Грузоотправитель',
            r'\bбортовой\b': 'Бортовой',
            r'\bкамень\b': 'камень',
            
            # Ошибки латинско-кириллические
            r'\bООО\b': 'ООО',
            r'\bЗАО\b': 'ЗАО',
            r'\bИНН\b': 'ИНН',
            r'\bТТН\b': 'ТТН',
            
            # Частые ошибки в кириллице
            'rn': 'п',
            'rp': 'р',
            'c': 'с',
            'o': 'о',
            'a': 'а',
            'e': 'е',
            'p': 'р',
            'x': 'х',
            'y': 'у',
            'H': 'Н',
            'B': 'В',
            'P': 'Р',
            'C': 'С',
            'T': 'Т',
            'M': 'М',
            'K': 'К',
            
            # Очистка мусорных символов
            r'[~`@#$%^&*=+\[\]{}]': '',
            r'\s+': ' ',  # Множественные пробелы
        }
        
        # Дополнительная коррекция похожих символов в контексте
        context_corrections = {
            # Коррекция символа № (номер)
            r'\bN[eе][\s:]': '№ ',  # "Ne " -> "№ "
            r'\bNo[\s:]': '№ ',      # "No " -> "№ "
            r'\bNо[\s:]': '№ ',     # "Nо " -> "№ "
            
            # Коррекция номеров документов (часто Б/В путаются)
            r'(\d+)/В(?=\s|$)': r'\1/Б',  # если после номера идет /В, скорее всего это /Б
            r'(\d+)/в(?=\s|$)': r'\1/Б',  # то же для строчной
            
            # Коррекция автомобильных номеров (А/а в начале)
            r'(?:^|\s)а(\d{3}[А-ЯЁ]{1,2}\d{2,3})(?=\s|$)': r'А\1',  # а123ВВ77 -> А123ВВ77
            r'(?:^|\s)o(\d{3}[А-ЯЁ]{1,2}\d{2,3})(?=\s|$)': r'О\1',  # o123ВВ77 -> О123ВВ77
            
            # Коррекция в названиях организаций
            r'\bооо\b': 'ООО',
            r'\bзао\b': 'ЗАО',
            r'\bоао\b': 'ОАО',
        }
        
        processed = text
        
        # Применяем основные замены
        for pattern, replacement in replacements.items():
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
        
        # Применяем контекстные коррекции
        for pattern, replacement in context_corrections.items():
            processed = re.sub(pattern, replacement, processed)
        
        # Удаляем очень короткие слова (мусор)
        words = processed.split()
        cleaned_words = []
        for word in words:
            # Оставляем слова длиннее 1 символа или важные односимвольные
            if len(word) > 1 or word in ['№', 'г', 'д', 'с', 'м', 'кг', 'т', 'шт']:
                cleaned_words.append(word)
        
        return ' '.join(cleaned_words).strip()
    
    def extract_structured_data(self, text: str) -> Dict[str, any]:
        """
        Извлечение структурированных данных из текста
        """
        results = {}
        confidence_scores = {}
        
        for field, patterns in self.patterns.items():
            best_match = None
            best_confidence = 0
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    match = matches[0]
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    # Простая оценка уверенности на основе длины и содержания
                    confidence = self.calculate_field_confidence(field, match)
                    
                    if confidence > best_confidence:
                        best_match = match.strip()
                        best_confidence = confidence
            
            if best_match:
                # Постобработка полей
                processed_value = self.post_process_field(field, best_match)
                if processed_value:
                    results[field] = processed_value
                    confidence_scores[field] = best_confidence
        
        # Вычисляем общую уверенность
        overall_confidence = int(np.mean(list(confidence_scores.values()))) if confidence_scores else 0
        
        return {
            'fields': results,
            'confidence': overall_confidence,
            'field_confidences': confidence_scores,
            'raw_text': text
        }
    
    def calculate_field_confidence(self, field: str, value: str) -> float:
        """
        Вычисление уверенности для конкретного поля
        """
        if not value or len(value.strip()) < 2:
            return 0
        
        confidence = 50  # базовая уверенность
        
        # Специфичные проверки для разных полей
        if field == 'supplier':
            if any(word in value.lower() for word in ['ооо', 'зао', 'ип', 'оао']):
                confidence += 30
            if len(value) > 10:
                confidence += 10
                
        elif field == 'quantity':
            if re.match(r'\d+([.,]\d+)?$', value):
                confidence += 40
                
        elif field == 'delivery_date':
            if re.match(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}$', value):
                confidence += 40
                
        elif field == 'vehicle_number':
            if re.match(r'[А-Я]\d{3}[А-Я]{2}\d{2,3}$', value):
                confidence += 45
                
        elif field == 'supplier_inn':
            if re.match(r'\d{10,12}$', value):
                confidence += 45
                
        elif field == 'package_count':
            if re.match(r'\d+$', value) and int(value) > 0:
                confidence += 40
        
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
            # Нормализуем формат даты
            value = re.sub(r'[.\-/]', '.', value)
            try:
                # Пытаемся парсить дату
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
                
        return value
    
    def process_document(self, image_data: bytes) -> Dict[str, any]:
        """
        Основной метод обработки документа
        """
        try:
            logger.info("Начало обработки документа")
            
            # Предобработка изображения (несколько вариантов)
            processed_images = self.preprocess_image(image_data)
            
            if not processed_images:
                return {
                    'success': False,
                    'error': 'Не удалось обработать изображение',
                    'fields': {},
                    'confidence': 0
                }
            
            # Извлечение текста с помощью наилучшего метода
            extracted_text = self.extract_text_from_images(processed_images)
            
            if not extracted_text:
                return {
                    'success': False,
                    'error': 'Не удалось извлечь текст из изображения',
                    'fields': {},
                    'confidence': 0
                }
            
            # Извлечение структурированных данных
            structured_data = self.extract_structured_data(extracted_text)
            
            logger.info(f"Обработка завершена. Найдено полей: {len(structured_data['fields'])}")
            
            return {
                'success': True,
                'fields': structured_data['fields'],
                'confidence': structured_data['confidence'],
                'field_confidences': structured_data.get('field_confidences', {}),
                'raw_text': structured_data['raw_text']
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки документа: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'fields': {},
                'confidence': 0
            }

# Глобальный экземпляр процессора
ocr_processor = DocumentOCRProcessor()