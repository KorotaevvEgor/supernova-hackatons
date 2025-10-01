#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Простой и надежный OCR процессор
Работает стабильно, без зависаний, с базовой обработкой текста
"""

import logging
import io
from PIL import Image, ImageEnhance
from typing import Dict, List, Optional
import numpy as np
import re

logger = logging.getLogger(__name__)

class SimpleOCRProcessor:
    """Простой и стабильный OCR процессор с fallback на Tesseract"""
    
    def __init__(self):
        self.ocr_engine = None
        self.ocr_type = None  # 'paddle' или 'tesseract'
        self.is_initialized = False
    
    def _initialize_ocr(self):
        """Инициализация OCR с fallback (один раз)"""
        if self.is_initialized:
            return
        
        # Пытаемся сначала инициализировать PaddleOCR
        try:
            from paddleocr import PaddleOCR
            logger.info("🚀 Попытка инициализации PaddleOCR...")
            
            # Простая инициализация без проблемных параметров
            self.ocr_engine = PaddleOCR(lang='ru', show_log=False)
            self.ocr_type = 'paddle'
            self.is_initialized = True
            
            logger.info("✅ PaddleOCR успешно инициализирован!")
            return
            
        except Exception as paddle_error:
            logger.warning(f"⚠️ PaddleOCR недоступен: {str(paddle_error)}")
        
        # Fallback на Tesseract
        try:
            import pytesseract
            from PIL import Image
            
            logger.info("🚀 Переключение на Tesseract OCR...")
            
            # Проверяем доступность Tesseract
            try:
                pytesseract.get_tesseract_version()
                self.ocr_engine = pytesseract
                self.ocr_type = 'tesseract'
                self.is_initialized = True
                
                logger.info("✅ Tesseract OCR успешно инициализирован!")
                return
                
            except Exception as tesseract_version_error:
                logger.error(f"Tesseract не работает: {str(tesseract_version_error)}")
                
        except ImportError as tesseract_import_error:
            logger.error(f"pytesseract не установлен: {str(tesseract_import_error)}")
        except Exception as tesseract_error:
            logger.error(f"Ошибка Tesseract: {str(tesseract_error)}")
        
        # Оба движка недоступны
        raise Exception("Оба OCR движка (PaddleOCR и Tesseract) недоступны")
    
    def _prepare_image(self, image_data: bytes) -> np.ndarray:
        """Простая подготовка изображения"""
        try:
            # Открываем изображение
            img = Image.open(io.BytesIO(image_data))
            
            # Конвертируем в RGB
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Простое улучшение только для очень маленьких изображений
            width, height = img.size
            if width < 400 or height < 300:
                # Увеличиваем в 2 раза только маленькие изображения
                new_width = width * 2
                new_height = height * 2
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"Увеличено изображение: {width}x{height} → {new_width}x{new_height}")
            
            # Легкое улучшение контраста
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.2)
            
            # Конвертируем в numpy array
            img_array = np.array(img)
            
            logger.info(f"Подготовлено изображение: {img_array.shape}")
            return img_array
            
        except Exception as e:
            logger.error(f"Ошибка подготовки изображения: {str(e)}")
            # Возвращаем оригинал в случае ошибки
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return np.array(img)
    
    def process_document(self, image_data: bytes) -> Dict:
        """Главный метод обработки документа"""
        try:
            logger.info("🚀 Начало обработки документа")
            
            # Инициализируем OCR
            self._initialize_ocr()
            
            # Подготавливаем изображение
            processed_image = self._prepare_image(image_data)
            
            # Выполняем OCR в зависимости от движка
            logger.info(f"📶 Запуск распознавания через {self.ocr_type.upper()}...")
            
            if self.ocr_type == 'paddle':
                result = self.ocr_engine.ocr(processed_image, cls=False)
            elif self.ocr_type == 'tesseract':
                # Конвертируем numpy array в PIL Image
                from PIL import Image as PILImage
                pil_image = PILImage.fromarray(processed_image)
                # Используем русский язык для Tesseract
                text = self.ocr_engine.image_to_string(pil_image, lang='rus')
                result = text
            else:
                raise Exception(f"Неизвестный тип OCR: {self.ocr_type}")
            
            # Обрабатываем результат
            return self._process_ocr_result(result)
            
        except Exception as e:
            logger.error(f"Ошибка обработки документа: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'raw_text': '',
                'fields': {},
                'confidence': 0
            }
    
    def _process_ocr_result(self, ocr_result) -> Dict:
        """Обработка результата OCR (поддержка PaddleOCR и Tesseract)"""
        try:
            if not ocr_result:
                return {
                    'success': False,
                    'error': 'Пустой результат OCR',
                    'raw_text': '',
                    'fields': {},
                    'confidence': 0
                }
            
            # Извлекаем текст в зависимости от типа OCR
            if self.ocr_type == 'tesseract':
                # Tesseract возвращает простой текст
                if isinstance(ocr_result, str) and ocr_result.strip():
                    full_text = ocr_result.strip()
                    avg_confidence = 75  # Примерная оценка для Tesseract
                    ocr_service = 'Tesseract OCR'
                else:
                    return {
                        'success': False,
                        'error': 'Пустой текст от Tesseract',
                        'raw_text': '',
                        'fields': {},
                        'confidence': 0
                    }
                    
            elif self.ocr_type == 'paddle':
                # PaddleOCR возвращает словарь с данными
                recognized_texts = []
                confidences = []
                
                if isinstance(ocr_result, list) and len(ocr_result) > 0:
                    # Новый формат PaddleOCR
                    for page_result in ocr_result:
                        if page_result:  # Проверяем, что страница не пустая
                            for line in page_result:
                                if len(line) >= 2:
                                    text = line[1][0]  # Текст
                                    confidence = line[1][1]  # Конфиденс
                                    if text.strip():
                                        recognized_texts.append(text.strip())
                                        confidences.append(confidence)
                
                if not recognized_texts:
                    return {
                        'success': False,
                        'error': 'Текст не распознан PaddleOCR',
                        'raw_text': '',
                        'fields': {},
                        'confidence': 0
                    }
                
                full_text = '\n'.join(recognized_texts)
                avg_confidence = int(sum(confidences) / len(confidences) * 100) if confidences else 50
                ocr_service = 'PaddleOCR (Простой процессор)'
                
            else:
                return {
                    'success': False,
                    'error': f'Неизвестный тип OCR: {self.ocr_type}',
                    'raw_text': '',
                    'fields': {},
                    'confidence': 0
                }
            
            # Подчищаем распознанный текст
            clean_text = full_text.replace('\t', ' ').replace('\r', '\n')
            while '  ' in clean_text:
                clean_text = clean_text.replace('  ', ' ')
            
            # Извлекаем поля с помощью регексов
            extracted_fields = self._extract_simple_fields(clean_text)
            
            logger.info(f"✅ Успешно распознано через {self.ocr_type.upper()}")
            logger.info(f"📝 Текст: {clean_text[:100]}...") 
            logger.info(f"🎯 Уверенность: {avg_confidence}%")
            logger.info(f"📋 Найдено полей: {len(extracted_fields)}")
            if extracted_fields:
                logger.info(f"🔍 Поля: {extracted_fields}")
            
            return {
                'success': True,
                'raw_text': full_text,
                'fields': extracted_fields,
                'confidence': avg_confidence,
                'ocr_service': ocr_service
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки результата OCR: {str(e)}")
            return {
                'success': False,
                'error': f'Ошибка обработки результата: {str(e)}',
                'raw_text': '',
                'fields': {},
                'confidence': 0
            }
    
    def _extract_simple_fields(self, text: str) -> Dict:
        """Извлечение простых полей из текста"""
        fields = {}
        text_lower = text.lower()
        
        logger.info(f"🔍 Поиск полей в тексте: {text[:200]}...")
        
        # Определяем тип документа
        document_type = self._detect_document_type(text)
        logger.info(f"📄 Тип документа: {document_type}")
        
        try:
            if document_type == 'transport_waybill':
                patterns = self._get_transport_waybill_patterns()
            else:
                patterns = self._get_default_patterns()
            
            return self._extract_fields_with_patterns(text, patterns)
            
        except Exception as e:
            logger.error(f"Ошибка извлечения полей: {str(e)}")
            return {}
    
    def _detect_document_type(self, text: str) -> str:
        """Определяет тип документа по ключевым словам"""
        text_lower = text.lower()
        
        logger.info(f"🔍 Определение типа документа...")
        logger.info(f"📝 Текст (первые 200 символов): {text_lower[:200]}...")
        
        # Ключевые слова для транспортной накладной (расширенные)
        transport_keywords = [
            # Основные термины
            'транспортная накладная',
            'транспортная',
            'накладная',
            
            # Участники
            'грузоотправитель',
            'грузополучатель',
            'отправитель',
            'получатель',
            
            # Транспорт
            'автомобиль',
            'водитель',
            'тентованный прицеп',
            
            # Характеристики груза
            'масса нетто',
            'масса брутто',
            'нетто',
            'брутто',
            'тип владения',
            
            # Объем
            'объем',
            'м³',
            'м3'
        ]
        
        # Проверяем наличие ключевых слов транспортной накладной
        found_keywords = []
        transport_count = 0
        for keyword in transport_keywords:
            if keyword in text_lower:
                transport_count += 1
                found_keywords.append(keyword)
                logger.info(f"  ✅ Найдено: '{keyword}'")
            else:
                logger.info(f"  ❌ Не найдено: '{keyword}'")
        
        logger.info(f"📈 Найдено ключевых слов: {transport_count} из {len(transport_keywords)}")
        logger.info(f"🔑 Найденные слова: {found_keywords}")
        
        # Понижаем порог до 1 слова для лучшего распознавания
        if transport_count >= 1:  # Если найдено хотя бы 1 ключевое слово
            result = 'transport_waybill'
            logger.info(f"🚚 Тип документа: {result} (транспортная накладная)")
            return result
        
        result = 'default'
        logger.info(f"📄 Тип документа: {result} (обычная накладная)")
        return result
    
    def _get_transport_waybill_patterns(self) -> Dict:
        """Паттерны для транспортной накладной (адаптировано под реальный текст)"""
        return {
            # Номер накладной
            'document_number': [
                r'транспортная накладная\s*№\s*([\d/А-ЯЁ]+)',
                r'накладная\s*№\s*([\d/А-ЯЁ]+)',
                r'№\s*([\d/А-ЯЁ]+)',
            ],
            
            # Дата документа
            'delivery_date': [
                r'дата[:.]?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})',
                r'(\d{2}\.\d{2}\.\d{4})',
            ],
            
            # Поставщик (грузоотправитель)
            'supplier': [
                r'грузоотправитель[:.]?\s*([^\n]+?)(?=\s*ИНН|$)',
                r'отправитель[:.]?\s*([^\n]+)',
            ],
            
            # Количество (адаптировано под наш текст)
            'quantity': [
                r'количество[:.]?\s*(\d+)',
                r'(\d+)\s*тонн',
                r'(\d+)\s*шт',
            ],
            
            # Количество мест
            'package_count': [
                r'мест[:.]?\s*(\d+)',
                r'(\d+)\s*мест',
            ],
            
            # Описание/наименование груза
            'description': [
                r'наименование\s+груза[:.]?\s*([^\n]+)',
                r'(цемент\s*[^\n]*)',
                r'(бетон\s*[^\n]*)',
            ],
            
            # ИНН поставщика
            'supplier_inn': [
                r'инн[:.]?\s*(\d{10,12})',
            ],
            
            # Водитель
            'driver_name': [
                r'водитель[:.]?\s*([A-ЯЁ][a-яё]+\s+[A-ЯЁ][a-яё]+\s+[A-ЯЁ][a-яё]+)',
                r'водитель[:.]?\s*([A-ЯЁа-яё\s]+)',
            ],
            
            # Номер автомобиля
            'vehicle_number': [
                r'автомобиль[:.]?\s*([A-ЯЁ]\d{3}[A-ЯЁ]{1,2}\d{2,3})',
                r'([A-ЯЁ]\d{3}[A-ЯЁ]{1,2}\d{2,3})',
            ],
            
            # Вес груза (кг)
            'cargo_weight': [
                r'вес[:.]?\s*(\d{4,})\s*кг',
                r'(\d{4,})\s*кг',
            ],
            
            # Проект (дополнительное поле)
            'project': [
                r'проект[:.]?\s*([^\n]+)',
            ],
            
            # ==========================================================
            # ПОЛЯ ДЛЯ ПОЛНОЙ ТРАНСПОРТНОЙ НАКЛАДНОЙ
            # (оставляем на случай, если в будущем будут документы с большим количеством полей)
            # ==========================================================
            
            # Грузополучатель
            'recipient': [
                r'грузополучатель[:.]?\s*([^\n]+?)(?=\s*\d|$)',
                r'получатель[:.]?\s*([^\n]+)',
            ],
            
            # Адрес доставки
            'delivery_address': [
                r'г\s*\.?\s*москва[,\s]*([^\n]+?)(?=\s*\d|$)',
                r'поселок\s+([^,\n]+)',
                r'пр-кт\s+([^,\n]+)',
            ],
            
            # Объем
            'volume': [
                r'(\d+[,.]\d+)\s*м3',
                r'(\d+[,.]\d+)\s*м\s*3',
                r'/\s*(\d+[,.]\d+)\s*м3',
            ],
            
            # Масса нетто
            'cargo_weight_net': [
                r'нетто[:.]?\s*—?\s*(\d+[,.]\d+)\s*т',
                r'масса\s+нетто[:.]?\s*(\d+[,.]\d+)',
            ],
            
            # Масса брутто
            'cargo_weight_gross': [
                r'брутто[:.]?\s*—?\s*(\d+[,.]\d+)\s*т',
                r'масса\s+брутто[:.]?\s*(\d+[,.]\d+)',
            ],
            
            # Объем груза
            'cargo_volume': [
                r'объем[:.]?\s*(\d+[,.]\d+)\s*м',
                r'(\d+[,.]\d+)\s*м³',
            ],
            
            # Тип владения транспортом
            'ownership_type': [
                r'тип\s+владения[:.]?\s*(\d+)',
                r'владение[:.]?\s*(\d)',
            ],
        }
    
    def _get_default_patterns(self) -> Dict:
        """Стандартные паттерны для обычных накладных"""
        return {
            # Основная информация
            'quantity': [
                r'количество[:.]?\s*(\d+)',
                r'(\d+)\s+тонн',
                r'(\d+)\s*т\.',
                r'вес[:.]?\s*(\d+)',
            ],
            
            'package_count': [
                r'мест[:.]?\s*(\d+)',
                r'(\d+)\s+мест',
            ],
            
            'delivery_date': [
                r'дата[:.]?\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})',
                r'(\d{2}\.\d{2}\.\d{4})',
            ],
            
            'supplier': [
                r'ооо\s*["«]([^"»]+)["»]',
                r'грузоотправитель[:.]?\s*([^\n]+)',
                r'отправитель[:.]?\s*([^\n]+)',
            ],
            
            'document_number': [
                r'№\s*(\d{4,})',
                r'накладная\s*№\s*(\d{4,})',
                r'(\d{4,})(?=\s*$|\s*\n)',  # 4+ цифры в конце строки
            ],
            
            'supplier_inn': [
                r'инн[:.]?\s*(\d{10,12})',
            ],
            
            'driver_name': [
                r'водитель[:.]?\s*([A-ЯЁ][a-яё]+\s+[A-ЯЁ][a-яё]+\s+[A-ЯЁ][a-яё]+)',
                r'водитель[:.]?\s*([A-ЯЁа-яё\s]+)',
            ],
            
            'vehicle_number': [
                r'автомобиль[:.]?\s*([A-ЯЁ]\d{3}[A-ЯЁ]{1,2}\d{2,3})',
                r'([A-ЯЁ]\d{3}[A-ЯЁ]{1,2}\d{2,3})',
            ],
            
            'cargo_weight': [
                r'вес[:.]?\s*(\d{4,})\s*кг',
                r'(\d{4,})\s*кг',
            ],
            
            'description': [
                r'наименование\s+груза[:.]?\s*([^\n]+)',
                r'(цемент\s*[^\n]*)',
                r'(песок\s*[^\n]*)',
                r'(щебень\s*[^\n]*)',
            ],
        }
    
    def _extract_fields_with_patterns(self, text: str, patterns: Dict) -> Dict:
        """Извлечение полей с помощью паттернов"""
        fields = {}
        
        # Ищем соответствия
        for field, field_patterns in patterns.items():
            logger.info(f"🔍 Поиск поля '{field}'...")
            field_found = False
            
            for i, pattern in enumerate(field_patterns):
                try:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    logger.info(f"  Паттерн {i+1}: '{pattern}' -> {matches}")
                    
                    if matches:
                        # Берем первое найденное значение
                        value = str(matches[0]).strip()
                        if value and len(value) > 0:
                            # Постобработка для исправления частых ошибок OCR
                            value = self._fix_common_ocr_errors(value)
                            
                            # Дополнительная обработка для разных типов полей
                            value = self._postprocess_field_value(field, value)
                            
                            fields[field] = value
                            logger.info(f"  ✅ Найдено: {field} = '{value}'")
                            field_found = True
                            break  # Переходим к следующему полю
                except Exception as e:
                    logger.error(f"  ❌ Ошибка паттерна {i+1}: {e}")
            
            if not field_found:
                logger.warning(f"  ⚠️ Поле '{field}' не найдено")
        
        logger.info(f"🎆 Итог: найдено {len(fields)} полей: {list(fields.keys())}")
        return fields
    
    def _postprocess_field_value(self, field: str, value: str) -> str:
        """Дополнительная обработка значений полей"""
        if not value:
            return value
        
        # Обработка даты
        if field == 'delivery_date':
            # Преобразуем дд.мм.гггг в гггг-мм-дд
            if re.match(r'\d{2}\.\d{2}\.\d{4}', value):
                parts = value.split('.')
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
        
        # Обработка числовых значений
        if field in ['quantity', 'cargo_weight', 'package_count']:
            # Убираем все нецифровые символы
            clean_value = re.sub(r'[^\d]', '', value)
            return clean_value if clean_value else value
        
        # Обработка дробных чисел (вес, объем)
        if field in ['cargo_weight_net', 'cargo_weight_gross', 'volume', 'cargo_volume']:
            # Заменяем запятую на точку
            clean_value = value.replace(',', '.')
            # Оставляем только цифры и точку
            clean_value = re.sub(r'[^\d.]', '', clean_value)
            return clean_value if clean_value else value
        
        # Обработка текстовых полей
        if field in ['supplier', 'recipient', 'description', 'delivery_address']:
            # Убираем лишние пробелы и спецсимволы
            clean_value = re.sub(r'\s+', ' ', value.strip())
            clean_value = clean_value.strip('"\'«»')
            return clean_value
        
        return value.strip()
    
    def _fix_common_ocr_errors(self, text: str) -> str:
        """Исправляет частые ошибки OCR при распознавании кириллицы"""
        if not text:
            return text
            
        # Общие замены для кириллицы
        corrections = {
            # Ошибки в номерах документов
            r'/(\d)$': r'/Б',  # /6 на конце → /Б
            r'/6$': r'/Б',     # /6 → /Б
            r'/0$': r'/О',     # /0 → /О (нуль на О)
            r'/9$': r'/Р',     # /9 → /Р
            r'/8$': r'/В',     # /8 → /В
            r'/(\d)(\d)$': lambda m: f'/Б{m.group(2)}',  # /66 → /Б6
            
            # Ошибки в автономерах
            r'км': 'КМ',  # км → КМ
            r'кв': 'КМ',  # кв → КМ (ошибка М/В)
            r'км(\d)': r'КМ\1',  # км777 → КМ777
        }
        
        result = text
        for pattern, replacement in corrections.items():
            if callable(replacement):
                result = re.sub(pattern, replacement, result)
            else:
                result = re.sub(pattern, replacement, result)
        
        return result


# Глобальный экземпляр процессора
_simple_ocr_processor = None

def get_simple_ocr_processor():
    """Получить экземпляр простого OCR процессора"""
    global _simple_ocr_processor
    if _simple_ocr_processor is None:
        _simple_ocr_processor = SimpleOCRProcessor()
    return _simple_ocr_processor