#!/usr/bin/env python3
"""
Скрипт для импорта данных из Excel файлов с перечнями работ и сетевыми графиками

Использование:
    python import_excel_data.py
"""
import os
import sys
import django
import pandas as pd
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Настройка Django
sys.path.append('/Users/korotaevegor/Desktop/Хакатон/urban_construction_system')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'urban_construction_system.settings')
django.setup()

from projects.models import (
    Project, WorkType, ElectronicSpecification, SpecificationItem,
    NetworkSchedule, ScheduleTask
)


class ExcelDataImporter:
    """Импортер данных из Excel файлов"""
    
    def __init__(self):
        # Пути к папкам с данными
        self.works_folder = Path('/Users/korotaevegor/Desktop/Хакатон/Датасет ЛЦТ 2025/Эл. спец-ии и перечень работ')
        self.schedule_folder = Path('/Users/korotaevegor/Desktop/Хакатон/Датасет ЛЦТ 2025/Пример сетевого графика')
        
        # Статистика импорта
        self.stats = {
            'specifications': 0,
            'spec_items': 0,
            'schedules': 0,
            'schedule_tasks': 0,
            'errors': []
        }
    
    def parse_decimal(self, value):
        """Безопасный парсинг числовых значений"""
        if pd.isna(value) or value == '' or value is None:
            return None
        
        try:
            if isinstance(value, (int, float)):
                return Decimal(str(value))
            
            # Очистка от лишних символов
            clean_value = str(value).replace(',', '.').replace(' ', '')
            clean_value = re.sub(r'[^\d.-]', '', clean_value)
            
            if clean_value:
                return Decimal(clean_value)
        except (InvalidOperation, ValueError) as e:
            self.stats['errors'].append(f"Ошибка парсинга числа '{value}': {e}")
        
        return None
    
    def match_project_by_filename(self, filename):
        """Поиск проекта по имени файла (улучшенная версия)"""
        filename_lower = filename.lower()
        print(f"\n🔍 Поиск проекта для файла: {filename}")
        
        # Расширенный словарь соответствий
        mapping_rules = [
            # Каргопольская 18
            ('каргопольская', ['каргопольская', '18']),
            # Проспект Мира 194  
            ('проспект_мира_194', ['мира', '194']),
            ('мира', ['мира', '194']),
            # Путевой 38
            ('путевой', ['путевой', '38']),
            # Флотская 54
            ('флотская', ['флотская', '54']),
            # Бестужевых 27
            ('бестужевых', ['бестужевых', '27']),
            # Челобитьевское (пока нет в базе, но можно добавить)
            ('челобитьевское', ['челобитьевское'])
        ]
        
        # Пробуем найти по правилам
        for keyword, search_terms in mapping_rules:
            if keyword in filename_lower:
                print(f"  ℹ️ Найдено ключевое слово '{keyword}', ищем по: {search_terms}")
                
                for project in Project.objects.all():
                    project_text = (project.address + ' ' + project.name).lower()
                    matches = sum(1 for term in search_terms if term in project_text)
                    
                    if matches >= len(search_terms) * 0.5:  # Минимум 50% совпадений
                        print(f"    ✅ Найден: {project.name} ({matches}/{len(search_terms)} совпадений)")
                        return project
        
        # Если не нашли по правилам, пробуем общий поиск
        print(f"  ⚠️ Не найдено по правилам, пробуем общий поиск...")
        
        filename_words = re.findall(r'[a-zа-яё0-9]+', filename_lower)
        print(f"    Слова в имени файла: {filename_words}")
        
        best_project = None
        best_score = 0
        
        for project in Project.objects.all():
            project_words = re.findall(r'[a-zа-яё0-9]+', (project.address + ' ' + project.name).lower())
            common_words = set(filename_words) & set(project_words)
            score = len(common_words)
            
            print(f"    {project.name}: {score} общих слов ({common_words})")
            
            if score > best_score:
                best_score = score
                best_project = project
        
        if best_score > 0:
            print(f"  ✅ Лучший кандидат: {best_project.name} (скор {best_score})")
            return best_project
        
        print(f"  ❌ Проект не найден")
        return None
    
    def import_specifications(self):
        """Импорт электронных спецификаций"""
        print(f"\n📋 Импортируем перечни работ из {self.works_folder}")
        
        if not self.works_folder.exists():
            self.stats['errors'].append(f"Папка не найдена: {self.works_folder}")
            return
        
        excel_files = list(self.works_folder.glob("*.xlsx"))
        print(f"Найдено файлов: {len(excel_files)}")
        
        for file_path in excel_files:
            try:
                print(f"\n📄 Обрабатываем: {file_path.name}")
                
                # Поиск проекта
                project = self.match_project_by_filename(file_path.name)
                if not project:
                    error = f"Проект не найден для файла: {file_path.name}"
                    print(f"❌ {error}")
                    self.stats['errors'].append(error)
                    continue
                
                print(f"✅ Найден проект: {project.name}")
                
                # Чтение Excel файла
                try:
                    df = pd.read_excel(file_path, sheet_name=0)  # Первый лист
                except Exception as e:
                    error = f"Ошибка чтения файла {file_path.name}: {e}"
                    print(f"❌ {error}")
                    self.stats['errors'].append(error)
                    continue
                
                # Создание или получение спецификации
                spec, created = ElectronicSpecification.objects.get_or_create(
                    project=project,
                    defaults={'source_file': file_path.name}
                )
                
                if created:
                    print(f"✅ Создана новая спецификация")
                    self.stats['specifications'] += 1
                else:
                    # Очищаем существующие элементы
                    spec.items.all().delete()
                    print(f"🔄 Обновляем существующую спецификацию")
                
                # Импорт элементов спецификации
                items_created = 0
                for idx, row in df.iterrows():
                    if pd.isna(row.iloc[0]) and pd.isna(row.iloc[1]):  # Пропускаем пустые строки
                        continue
                    
                    # Определяем содержимое столбцов (могут быть разные форматы)
                    code = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ''
                    name = str(row.iloc[1]) if not pd.isna(row.iloc[1]) else ''
                    
                    if len(name) < 3:  # Слишком короткое название
                        continue
                    
                    # Попытка найти единицы измерения и количество в следующих столбцах
                    unit = ''
                    quantity = None
                    unit_price = None
                    total_price = None
                    category = ''
                    
                    if len(df.columns) > 2:
                        unit = str(row.iloc[2]) if not pd.isna(row.iloc[2]) else ''
                    if len(df.columns) > 3:
                        quantity = self.parse_decimal(row.iloc[3])
                    if len(df.columns) > 4:
                        unit_price = self.parse_decimal(row.iloc[4])
                    if len(df.columns) > 5:
                        total_price = self.parse_decimal(row.iloc[5])
                    
                    # Определение категории по коду или названию
                    if 'фундамент' in name.lower() or 'основание' in name.lower():
                        category = 'Фундаментные работы'
                    elif 'стена' in name.lower() or 'кладка' in name.lower():
                        category = 'Стеновые работы'
                    elif 'кровля' in name.lower() or 'крыш' in name.lower():
                        category = 'Кровельные работы'
                    elif 'отделк' in name.lower() or 'штукатур' in name.lower():
                        category = 'Отделочные работы'
                    elif 'благоустрой' in name.lower() or 'озелен' in name.lower():
                        category = 'Благоустройство'
                    
                    SpecificationItem.objects.create(
                        specification=spec,
                        code=code[:50],  # Ограничиваем длину
                        name=name[:500],
                        unit=unit[:20],
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                        category=category[:200],
                        order=idx
                    )
                    items_created += 1
                
                print(f"✅ Импортировано {items_created} элементов спецификации")
                self.stats['spec_items'] += items_created
                
            except Exception as e:
                error = f"Общая ошибка при обработке файла {file_path.name}: {e}"
                print(f"❌ {error}")
                self.stats['errors'].append(error)
    
    def import_schedules(self):
        """Импорт сетевых графиков"""
        print(f"\n📊 Импортируем сетевые графики из {self.schedule_folder}")
        
        if not self.schedule_folder.exists():
            self.stats['errors'].append(f"Папка не найдена: {self.schedule_folder}")
            return
        
        excel_files = list(self.schedule_folder.glob("*.xlsx"))
        print(f"Найдено файлов: {len(excel_files)}")
        
        for file_path in excel_files:
            try:
                print(f"\n📄 Обрабатываем: {file_path.name}")
                
                # Читаем все листы файла
                excel_file = pd.ExcelFile(file_path)
                print(f"Листы в файле: {excel_file.sheet_names}")
                
                # Привязываем к первому проекту (для демонстрации)
                # В реальности здесь должна быть логика определения проекта
                project = Project.objects.first()
                if not project:
                    error = "Нет проектов в базе данных"
                    print(f"❌ {error}")
                    self.stats['errors'].append(error)
                    continue
                
                print(f"✅ Используем проект: {project.name}")
                
                # Создание или получение графика
                schedule, created = NetworkSchedule.objects.get_or_create(
                    project=project,
                    defaults={'source_file': file_path.name}
                )
                
                if created:
                    print(f"✅ Создан новый сетевой график")
                    self.stats['schedules'] += 1
                else:
                    # Очищаем существующие задачи
                    schedule.tasks.all().delete()
                    print(f"🔄 Обновляем существующий график")
                
                # Ищем лист с задачами
                df = None
                for sheet_name in excel_file.sheet_names:
                    try:
                        temp_df = pd.read_excel(file_path, sheet_name=sheet_name)
                        # Проверяем, есть ли колонки, похожие на задачи
                        columns = [col.lower() for col in temp_df.columns]
                        if any(keyword in ' '.join(columns) for keyword in ['задач', 'работ', 'наименован', 'продолжит']):
                            df = temp_df
                            print(f"Используем лист: {sheet_name}")
                            break
                    except:
                        continue
                
                if df is None:
                    # Используем первый лист
                    df = pd.read_excel(file_path, sheet_name=0)
                
                # Импорт задач графика
                tasks_created = 0
                for idx, row in df.iterrows():
                    # Пропускаем заголовки и пустые строки
                    if idx < 2 or pd.isna(row.iloc[0]):
                        continue
                    
                    # Извлекаем данные задачи
                    task_id = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else f"T{idx}"
                    name = str(row.iloc[1]) if len(df.columns) > 1 and not pd.isna(row.iloc[1]) else f"Задача {task_id}"
                    
                    # Продолжительность
                    duration_days = 1
                    if len(df.columns) > 2 and not pd.isna(row.iloc[2]):
                        try:
                            duration_days = int(float(str(row.iloc[2]).replace(',', '.')))
                        except:
                            duration_days = 1
                    
                    # Начало и конец (примерные значения)
                    early_start = idx * 2  # Простая логика для демонстрации
                    early_finish = early_start + duration_days
                    
                    ScheduleTask.objects.create(
                        schedule=schedule,
                        task_id=task_id[:50],
                        name=name[:500],
                        duration_days=duration_days,
                        early_start=early_start,
                        early_finish=early_finish,
                        order=idx
                    )
                    tasks_created += 1
                
                print(f"✅ Импортировано {tasks_created} задач графика")
                self.stats['schedule_tasks'] += tasks_created
                
            except Exception as e:
                error = f"Общая ошибка при обработке файла {file_path.name}: {e}"
                print(f"❌ {error}")
                self.stats['errors'].append(error)
    
    def print_stats(self):
        """Вывод статистики импорта"""
        print(f"\n📈 СТАТИСТИКА ИМПОРТА:")
        print(f"   • Спецификации: {self.stats['specifications']}")
        print(f"   • Элементы спецификаций: {self.stats['spec_items']}")  
        print(f"   • Сетевые графики: {self.stats['schedules']}")
        print(f"   • Задачи графиков: {self.stats['schedule_tasks']}")
        
        if self.stats['errors']:
            print(f"\n❌ ОШИБКИ ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Показываем первые 10
                print(f"   • {error}")
            if len(self.stats['errors']) > 10:
                print(f"   • ... и ещё {len(self.stats['errors']) - 10} ошибок")
    
    def run(self):
        """Запуск полного импорта"""
        print("🚀 ЗАПУСК ИМПОРТА ДАННЫХ ИЗ EXCEL")
        print("=" * 50)
        
        self.import_specifications()
        self.import_schedules()
        
        print("\n" + "=" * 50)
        self.print_stats()
        print("✅ ИМПОРТ ЗАВЕРШЕН")


if __name__ == "__main__":
    importer = ExcelDataImporter()
    importer.run()