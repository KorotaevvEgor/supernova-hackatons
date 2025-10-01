#!/usr/bin/env python3
"""
Расширенный скрипт для импорта данных из Excel файлов с улучшенным сопоставлением

Использование:
    python import_excel_data_enhanced.py
"""
import os
import sys
import django
import pandas as pd
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
import random

# Настройка Django
sys.path.append('/Users/korotaevegor/Desktop/Хакатон/urban_construction_system')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'urban_construction_system.settings')
django.setup()

from projects.models import (
    Project, WorkType, ElectronicSpecification, SpecificationItem,
    NetworkSchedule, ScheduleTask
)


class EnhancedExcelDataImporter:
    """Расширенный импортер данных из Excel файлов"""
    
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
            'errors': [],
            'matched_files': []
        }
        
        # Улучшенные правила сопоставления
        self.mapping_rules = {
            'каргопольская': {'keywords': ['каргопольская', '18'], 'address_parts': ['каргопольская']},
            'проспект': {'keywords': ['мира', '194'], 'address_parts': ['мира', 'проспект']},
            'мира': {'keywords': ['мира', '194'], 'address_parts': ['мира']},
            'путевой': {'keywords': ['путевой', '38'], 'address_parts': ['путевой']},
            'флотская': {'keywords': ['флотская', '54'], 'address_parts': ['флотская']},
            'бестужевых': {'keywords': ['бестужевых', '27'], 'address_parts': ['бестужевых']},
            'челобитьевское': {'keywords': ['челобитьевское'], 'address_parts': ['челобитьевское']}
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
        except (InvalidOperation, ValueError):
            # Убираем логирование ошибок парсинга дат как чисел
            pass
        
        return None

    def advanced_project_matching(self, filename):
        """Продвинутое сопоставление проектов с файлами"""
        filename_lower = filename.lower()
        print(f"\n🔍 Продвинутый поиск проекта для файла: {filename}")
        
        # Получаем все проекты
        all_projects = list(Project.objects.all())
        print(f"Доступные проекты:")
        for p in all_projects:
            print(f"  • ID {p.id}: {p.name} - {p.address}")
        
        # Пробуем найти по правилам
        for rule_key, rule_data in self.mapping_rules.items():
            if rule_key in filename_lower:
                print(f"  ℹ️ Найдено ключевое слово '{rule_key}'")
                
                # Ищем по ключевым словам
                for project in all_projects:
                    project_text = (project.address + ' ' + project.name).lower()
                    matches = sum(1 for keyword in rule_data['keywords'] if keyword in project_text)
                    
                    if matches > 0:
                        print(f"    ✅ Найден: {project.name} ({matches} совпадений)")
                        return project
        
        # Общий поиск по словам
        filename_words = re.findall(r'[a-zа-яё0-9]+', filename_lower)
        print(f"  Слова в файле: {filename_words}")
        
        best_project = None
        best_score = 0
        
        for project in all_projects:
            project_words = re.findall(r'[a-zа-яё0-9]+', (project.address + ' ' + project.name).lower())
            common_words = set(filename_words) & set(project_words)
            score = len(common_words)
            
            if score > 0:
                print(f"    {project.name}: {score} общих слов ({common_words})")
            
            if score > best_score:
                best_score = score
                best_project = project
        
        if best_project and best_score > 0:
            print(f"  ✅ Лучший кандидат: {best_project.name} (скор {best_score})")
            return best_project
        
        print(f"  ❌ Автоматическое сопоставление не удалось")
        return None

    def import_specifications_enhanced(self):
        """Расширенный импорт спецификаций"""
        print(f"\n📋 РАСШИРЕННЫЙ ИМПОРТ СПЕЦИФИКАЦИЙ")
        print(f"Папка: {self.works_folder}")
        
        if not self.works_folder.exists():
            self.stats['errors'].append(f"Папка не найдена: {self.works_folder}")
            return
        
        excel_files = list(self.works_folder.glob("*.xlsx"))
        print(f"Найдено файлов: {len(excel_files)}")
        
        # Сначала пробуем автоматическое сопоставление
        matched_pairs = []
        unmatched_files = []
        
        for file_path in excel_files:
            project = self.advanced_project_matching(file_path.name)
            if project:
                matched_pairs.append((file_path, project))
                self.stats['matched_files'].append(f"{file_path.name} -> {project.name}")
            else:
                unmatched_files.append(file_path)
        
        print(f"\n✅ Автоматически сопоставлено: {len(matched_pairs)} файлов")
        print(f"⚠️ Не сопоставлено: {len(unmatched_files)} файлов")
        
        # Для несопоставленных файлов делаем случайное сопоставление с оставшимися проектами
        remaining_projects = list(Project.objects.exclude(
            id__in=[pair[1].id for pair in matched_pairs]
        ))
        
        print(f"\nОставшиеся проекты без спецификаций: {len(remaining_projects)}")
        for project in remaining_projects:
            print(f"  • {project.name}")
        
        # Случайное сопоставление оставшихся файлов
        for file_path in unmatched_files[:len(remaining_projects)]:
            if remaining_projects:
                project = remaining_projects.pop(0)
                matched_pairs.append((file_path, project))
                print(f"🎲 Случайно сопоставлено: {file_path.name} -> {project.name}")
                self.stats['matched_files'].append(f"{file_path.name} -> {project.name} (случайно)")
        
        # Импортируем все сопоставленные пары
        for file_path, project in matched_pairs:
            self.import_single_specification(file_path, project)

    def import_single_specification(self, file_path, project):
        """Импорт одной спецификации"""
        try:
            print(f"\n📄 Импортируем спецификацию: {file_path.name} -> {project.name}")
            
            # Чтение Excel файла
            try:
                df = pd.read_excel(file_path, sheet_name=0)
                print(f"  📊 Прочитано строк: {len(df)}, столбцов: {len(df.columns)}")
            except Exception as e:
                error = f"Ошибка чтения файла {file_path.name}: {e}"
                print(f"  ❌ {error}")
                self.stats['errors'].append(error)
                return
            
            # Создание или получение спецификации
            spec, created = ElectronicSpecification.objects.get_or_create(
                project=project,
                defaults={'source_file': file_path.name}
            )
            
            if created:
                print(f"  ✅ Создана новая спецификация")
                self.stats['specifications'] += 1
            else:
                # Очищаем существующие элементы
                old_count = spec.items.count()
                spec.items.all().delete()
                print(f"  🔄 Обновлена спецификация (удалено {old_count} старых элементов)")
            
            # Импорт элементов спецификации
            items_created = 0
            for idx, row in df.iterrows():
                # Пропускаем совсем пустые строки
                if all(pd.isna(row.iloc[i]) for i in range(min(3, len(row)))):
                    continue
                
                # Определяем содержимое столбцов
                code = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else ''
                name = str(row.iloc[1]) if len(row) > 1 and not pd.isna(row.iloc[1]) else f'Позиция {idx}'
                
                # Пропускаем слишком короткие названия или заголовки
                if len(name) < 3 or 'наименование' in name.lower():
                    continue
                
                # Пытаемся извлечь дополнительные данные
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
                
                # Умная категоризация
                category = self.categorize_work(name, code)
                
                SpecificationItem.objects.create(
                    specification=spec,
                    code=code[:50],
                    name=name[:500],
                    unit=unit[:20],
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    category=category,
                    order=idx
                )
                items_created += 1
            
            print(f"  ✅ Импортировано {items_created} элементов спецификации")
            self.stats['spec_items'] += items_created
            
        except Exception as e:
            error = f"Ошибка обработки {file_path.name}: {e}"
            print(f"  ❌ {error}")
            self.stats['errors'].append(error)

    def categorize_work(self, name, code):
        """Умная категоризация работ"""
        name_lower = name.lower()
        code_lower = code.lower()
        text = f"{name_lower} {code_lower}"
        
        # Категории работ
        if any(word in text for word in ['фундамент', 'основание', 'бетон', 'армирование']):
            return 'Фундаментные работы'
        elif any(word in text for word in ['стена', 'кладка', 'кирпич', 'блок']):
            return 'Стеновые работы'
        elif any(word in text for word in ['кровля', 'крыш', 'покрытие', 'металлочерепиц']):
            return 'Кровельные работы'
        elif any(word in text for word in ['отделк', 'штукатур', 'покраск', 'обои']):
            return 'Отделочные работы'
        elif any(word in text for word in ['окн', 'двер', 'проем']):
            return 'Столярные работы'
        elif any(word in text for word in ['электр', 'проводк', 'освещен', 'розетк']):
            return 'Электромонтажные работы'
        elif any(word in text for word in ['водопровод', 'канализац', 'отопление', 'сантехник']):
            return 'Сантехнические работы'
        elif any(word in text for word in ['благоустрой', 'озелен', 'дорожк', 'тротуар']):
            return 'Благоустройство'
        elif any(word in text for word in ['земляные', 'выемк', 'засыпк', 'грунт']):
            return 'Земляные работы'
        else:
            return 'Общестроительные работы'

    def create_schedules_for_all_projects(self):
        """Создание сетевых графиков для всех проектов"""
        print(f"\n📊 СОЗДАНИЕ СЕТЕВЫХ ГРАФИКОВ ДЛЯ ВСЕХ ПРОЕКТОВ")
        
        # Читаем базовый график из файла
        base_schedule_data = self.read_base_schedule()
        
        projects = Project.objects.all()
        print(f"Найдено проектов: {projects.count()}")
        
        for project in projects:
            print(f"\n🏗️ Создаем график для проекта: {project.name}")
            
            # Проверяем, есть ли уже график
            existing_schedule = NetworkSchedule.objects.filter(project=project).first()
            if existing_schedule:
                print(f"  🔄 Обновляем существующий график")
                existing_schedule.tasks.all().delete()
                schedule = existing_schedule
            else:
                print(f"  ✅ Создаем новый график")
                schedule = NetworkSchedule.objects.create(
                    project=project,
                    source_file='Генерированный график',
                    project_duration_days=120
                )
                self.stats['schedules'] += 1
            
            # Создаем задачи на основе спецификации проекта или шаблона
            tasks_created = self.create_tasks_for_project(schedule, project, base_schedule_data)
            print(f"  ✅ Создано {tasks_created} задач")
            self.stats['schedule_tasks'] += tasks_created

    def read_base_schedule(self):
        """Чтение базового графика из Excel файла"""
        schedule_files = list(self.schedule_folder.glob("*.xlsx"))
        if not schedule_files:
            return self.get_default_schedule_template()
        
        try:
            file_path = schedule_files[0]
            print(f"📖 Читаем базовый график из: {file_path.name}")
            
            excel_file = pd.ExcelFile(file_path)
            
            # Пробуем найти подходящий лист
            df = None
            for sheet_name in excel_file.sheet_names:
                temp_df = pd.read_excel(file_path, sheet_name=sheet_name)
                if len(temp_df) > 5:  # Есть данные
                    df = temp_df
                    print(f"  Используем лист: {sheet_name}")
                    break
            
            if df is None:
                df = pd.read_excel(file_path, sheet_name=0)
            
            # Извлекаем задачи
            tasks = []
            for idx, row in df.iterrows():
                if idx < 2 or pd.isna(row.iloc[0]):  # Пропускаем заголовки
                    continue
                
                task_id = str(row.iloc[0]) if not pd.isna(row.iloc[0]) else f"T{idx}"
                name = str(row.iloc[1]) if len(row) > 1 and not pd.isna(row.iloc[1]) else f"Задача {task_id}"
                
                # Продолжительность
                duration = 5  # По умолчанию
                if len(row) > 2 and not pd.isna(row.iloc[2]):
                    try:
                        duration = max(1, int(float(str(row.iloc[2]).replace(',', '.'))))
                    except:
                        duration = 5
                
                tasks.append({
                    'task_id': task_id[:50],
                    'name': name[:500],
                    'duration_days': duration
                })
            
            print(f"  📋 Извлечено {len(tasks)} базовых задач")
            return tasks
            
        except Exception as e:
            print(f"  ⚠️ Ошибка чтения базового графика: {e}")
            return self.get_default_schedule_template()

    def get_default_schedule_template(self):
        """Шаблон графика по умолчанию"""
        return [
            {'task_id': 'T001', 'name': 'Подготовительные работы', 'duration_days': 5},
            {'task_id': 'T002', 'name': 'Земляные работы', 'duration_days': 10},
            {'task_id': 'T003', 'name': 'Фундаментные работы', 'duration_days': 15},
            {'task_id': 'T004', 'name': 'Стеновые работы', 'duration_days': 20},
            {'task_id': 'T005', 'name': 'Кровельные работы', 'duration_days': 12},
            {'task_id': 'T006', 'name': 'Инженерные системы', 'duration_days': 18},
            {'task_id': 'T007', 'name': 'Отделочные работы', 'duration_days': 25},
            {'task_id': 'T008', 'name': 'Благоустройство', 'duration_days': 15},
        ]

    def create_tasks_for_project(self, schedule, project, base_tasks):
        """Создание задач для конкретного проекта"""
        tasks_created = 0
        current_start = 1
        
        # Если есть спецификация проекта, используем её для создания задач
        if hasattr(project, 'electronic_specification'):
            spec = project.electronic_specification
            if spec.items.exists():
                print(f"  📋 Создаем задачи на основе спецификации ({spec.items.count()} элементов)")
                
                # Группируем элементы спецификации по категориям
                categories = {}
                for item in spec.items.all():
                    category = item.category or 'Общие работы'
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(item)
                
                # Создаем задачи для каждой категории
                task_counter = 1
                for category, items in categories.items():
                    duration = max(5, len(items) * 2)  # 2 дня на элемент, минимум 5 дней
                    is_critical = category in ['Фундаментные работы', 'Стеновые работы'] or task_counter <= 3
                    
                    # Используем уникальный task_id для каждого проекта
                    unique_task_id = f"{project.id:02d}S{task_counter:03d}"  # S для спецификации
                    
                    ScheduleTask.objects.create(
                        schedule=schedule,
                        task_id=unique_task_id,
                        name=category,
                        duration_days=duration,
                        early_start=current_start,
                        early_finish=current_start + duration - 1,
                        is_critical=is_critical,
                        resource_names=f"Бригада {category.split()[0]}",
                        order=task_counter
                    )
                    
                    current_start += duration
                    tasks_created += 1
                    task_counter += 1
        
        # Если нет спецификации или мало задач, используем базовый шаблон
        if tasks_created < 3:
            print(f"  🏗️ Создаем задачи на основе шаблона")
            task_counter = tasks_created + 1
            
            for base_task in base_tasks:
                # Добавляем вариативность в продолжительность
                duration = base_task['duration_days'] + random.randint(-2, 3)
                duration = max(1, duration)
                
                is_critical = task_counter <= 4 or 'фундамент' in base_task['name'].lower()
                
                # Используем уникальный task_id для каждого проекта
                unique_task_id = f"{project.id:02d}T{task_counter:03d}"
                
                ScheduleTask.objects.create(
                    schedule=schedule,
                    task_id=unique_task_id,
                    name=base_task['name'],
                    duration_days=duration,
                    early_start=current_start,
                    early_finish=current_start + duration - 1,
                    late_start=current_start + random.randint(0, 2),
                    late_finish=current_start + duration - 1 + random.randint(0, 2),
                    is_critical=is_critical,
                    resource_names=self.generate_resources(base_task['name']),
                    order=task_counter
                )
                
                current_start += duration
                tasks_created += 1
                task_counter += 1
        
        return tasks_created

    def generate_resources(self, task_name):
        """Генерация ресурсов для задачи"""
        name_lower = task_name.lower()
        
        if 'подготов' in name_lower:
            return 'Прораб, Геодезист'
        elif 'земляные' in name_lower:
            return 'Экскаватор, Водитель'
        elif 'фундамент' in name_lower:
            return 'Бетонщики, Арматурщики'
        elif 'стен' in name_lower:
            return 'Каменщики, Монтажники'
        elif 'кровл' in name_lower:
            return 'Кровельщики, Такелажники'
        elif 'инженер' in name_lower:
            return 'Электрики, Сантехники'
        elif 'отделк' in name_lower:
            return 'Маляры, Штукатуры'
        elif 'благоустрой' in name_lower:
            return 'Озеленители, Плиточники'
        else:
            return 'Универсальная бригада'

    def print_enhanced_stats(self):
        """Расширенная статистика импорта"""
        print(f"\n📈 ПОДРОБНАЯ СТАТИСТИКА ИМПОРТА:")
        print(f"   🏢 Проектов в системе: {Project.objects.count()}")
        print(f"   📋 Импортировано спецификаций: {self.stats['specifications']}")
        print(f"   📝 Элементов спецификаций: {self.stats['spec_items']}")
        print(f"   📊 Создано/обновлено графиков: {self.stats['schedules']}")
        print(f"   🗓️ Задач в графиках: {self.stats['schedule_tasks']}")
        
        if self.stats['matched_files']:
            print(f"\n✅ СОПОСТАВЛЕННЫЕ ФАЙЛЫ ({len(self.stats['matched_files'])}):")
            for match in self.stats['matched_files']:
                print(f"   • {match}")
        
        if self.stats['errors']:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:5]:  # Показываем первые 5
                print(f"   • {error}")
            if len(self.stats['errors']) > 5:
                print(f"   • ... и ещё {len(self.stats['errors']) - 5} предупреждений")

    def run_enhanced_import(self):
        """Запуск расширенного импорта"""
        print("🚀 ЗАПУСК РАСШИРЕННОГО ИМПОРТА ДАННЫХ")
        print("=" * 60)
        
        # Импортируем спецификации
        self.import_specifications_enhanced()
        
        # Создаем графики для всех проектов
        self.create_schedules_for_all_projects()
        
        print("\n" + "=" * 60)
        self.print_enhanced_stats()
        print("✅ РАСШИРЕННЫЙ ИМПОРТ ЗАВЕРШЕН")


if __name__ == "__main__":
    importer = EnhancedExcelDataImporter()
    importer.run_enhanced_import()