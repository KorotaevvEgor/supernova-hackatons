import json
import pandas as pd
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from projects.models import Project, WorkType, Work
from materials.models import MaterialType, MaterialDelivery
from violations.models import ViolationCategory, ViolationType, Violation
from documents.models import OpeningChecklistItem

User = get_user_model()


class Command(BaseCommand):
    help = 'Загружает данные из датасета хакатона в систему'

    def add_arguments(self, parser):
        parser.add_argument('--dataset-path', type=str, default='../Датасет ЛЦТ 2025',
                          help='Путь к папке с датасетом')

    def handle(self, *args, **options):
        dataset_path = options['dataset_path']
        
        self.stdout.write(self.style.SUCCESS('Начинаем загрузку данных из датасета...'))
        
        # Создаем тестовых пользователей
        self.create_test_users()
        
        # Загружаем координаты объектов
        self.load_coordinates(dataset_path)
        
        # Загружаем графики работ
        self.load_work_schedules(dataset_path)
        
        # Создаем базовые типы материалов
        self.create_material_types()
        
        # Создаем типы нарушений
        self.create_violation_types()
        
        # Создаем чек-лист открытия объекта
        self.create_opening_checklist()

        # Импорт электронной спецификации/перечня работ и объемов
        self.import_work_specs(dataset_path)

        # Импорт классификатора нарушений из файла (при наличии)
        self.import_violation_classifier(dataset_path)
        
        self.stdout.write(self.style.SUCCESS('Загрузка данных завершена!'))

    def create_test_users(self):
        """Создание тестовых пользователей"""
        users_data = [
            {
                'username': 'stroy_control_1',
                'first_name': 'Анна',
                'last_name': 'Петрова',
                'email': 'a.petrova@stroy.mos.ru',
                'user_type': 'construction_control',
                'organization': 'Служба строительного контроля',
                'position': 'Ведущий инженер'
            },
            {
                'username': 'foreman_1',
                'first_name': 'Сергей',
                'last_name': 'Иванов',
                'email': 's.ivanov@contractor.ru',
                'user_type': 'foreman',
                'organization': 'ООО "СтройМонтаж"',
                'position': 'Прораб'
            },
            {
                'username': 'foreman_2',
                'first_name': 'Дмитрий',
                'last_name': 'Козлов',
                'email': 'd.kozlov@contractor.ru',
                'user_type': 'foreman',
                'organization': 'ООО "УрбанСтрой"',
                'position': 'Прораб'
            },
            {
                'username': 'inspector_1',
                'first_name': 'Елена',
                'last_name': 'Сидорова',
                'email': 'e.sidorova@control.mos.ru',
                'user_type': 'inspector',
                'organization': 'Мосгосстройнадзор',
                'position': 'Инспектор'
            }
        ]
        
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'email': user_data['email'],
                    'user_type': user_data['user_type'],
                    'organization': user_data['organization'],
                    'position': user_data['position'],
                    'is_active': True
                }
            )
            if created:
                user.set_password('demo123')
                user.save()
                self.stdout.write(f'Создан пользователь: {user.username}')

    def load_coordinates(self, dataset_path):
        """Загружает координаты объектов из файла полигонов"""
        try:
            coordinates_file = f'{dataset_path}/Примеры координат объектов ремонта/Полигоны.xlsx'
            df = pd.read_excel(coordinates_file)
            
            # Получаем пользователей для назначения
            control_user = User.objects.filter(user_type='construction_control').first()
            foreman_users = list(User.objects.filter(user_type='foreman'))
            
            projects_data = [
                {'name': 'Флотская улица, дом 54, 58к1', 'column': 'Флотская, 54,58к1'},
                {'name': 'Некрасовка проектируемый проезд', 'column': 'Некрасовка'},
                {'name': 'Бестужевых улица, дом 27А', 'column': 'Бестужевых улица, д.27А'},
                {'name': 'Каргопольская улица, дом 18', 'column': 'Каргопольская улица, д. 18'},
                {'name': 'Проспект Мира, дом 194', 'column': 'Пропект Мира 194'},
                {'name': 'Путевой проезд, дом 38', 'column': 'Путевой проезд, д. 38'},
                {'name': 'Челобитьевское шоссе, дом 14 к3,к4,к5', 'column': 'Челобитьевское шоссе, д14 к3,к4,к5'},
            ]
            
            for i, project_info in enumerate(projects_data):
                if project_info['column'] in df.columns:
                    # Получаем JSON данные полигона
                    polygon_row = df[df['Unnamed: 0'] == 'Полигон json WGS 84']
                    if not polygon_row.empty:
                        polygon_json = polygon_row[project_info['column']].iloc[0]
                        
                        project, created = Project.objects.get_or_create(
                            name=project_info['name'],
                            defaults={
                                'address': project_info['name'],
                                'coordinates': polygon_json,
                                'status': 'active' if i % 3 == 0 else 'planned',
                                'control_service': control_user,
                                'foreman': foreman_users[i % len(foreman_users)] if foreman_users else None,
                                'contract_number': f'КТ-2024-{1000 + i}',
                                'planned_start_date': timezone.now().date() + timedelta(days=i*30),
                                'planned_end_date': timezone.now().date() + timedelta(days=i*30 + 120),
                                'description': f'Работы по благоустройству территории: {project_info["name"]}'
                            }
                        )
                        
                        if created:
                            self.stdout.write(f'Создан проект: {project.name}')
                        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при загрузке координат: {e}'))

    def load_work_schedules(self, dataset_path):
        """Загружает примеры сетевых графиков"""
        try:
            schedule_file = f'{dataset_path}/Пример сетевого графика/Графики.xlsx'
            
            # Загружаем типы работ из листа "Разбивка"
            df_breakdown = pd.read_excel(schedule_file, sheet_name='Разбивка', skiprows=1)
            
            # Создаем типы работ
            work_types_data = [
                {'name': 'Устройство бортового камня', 'code': '02.03.03.11'},
                {'name': 'Ремонт асфальтобетонного покрытия', 'code': '02.03.03.12'},
                {'name': 'Устройство тротуарного покрытия', 'code': '02.03.03.13'},
                {'name': 'Озеленение территории', 'code': '02.03.03.14'},
                {'name': 'Установка малых архитектурных форм', 'code': '02.03.03.15'},
            ]
            
            for work_type_data in work_types_data:
                work_type, created = WorkType.objects.get_or_create(
                    code=work_type_data['code'],
                    defaults={
                        'name': work_type_data['name'],
                        'description': f'Работы по {work_type_data["name"].lower()}'
                    }
                )
                if created:
                    self.stdout.write(f'Создан тип работ: {work_type.name}')
            
            # Создаем работы для проектов
            projects = Project.objects.all()
            work_types = WorkType.objects.all()
            
            for project in projects:
                for i, work_type in enumerate(work_types):
                    start_date = project.planned_start_date + timedelta(days=i*20)
                    end_date = start_date + timedelta(days=15)
                    
                    work, created = Work.objects.get_or_create(
                        project=project,
                        work_type=work_type,
                        defaults={
                            'name': f'{work_type.name} на объекте {project.name}',
                            'planned_start_date': start_date,
                            'planned_end_date': end_date,
                            'volume': 100 + i*50,
                            'unit': 'м²' if 'покрытие' in work_type.name.lower() else 'м',
                            'description': f'Выполнение работ: {work_type.name}'
                        }
                    )
                    if created:
                        self.stdout.write(f'Создана работа: {work.name}')
                        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при загрузке графиков: {e}'))

    def create_material_types(self):
        """Создает базовые типы материалов"""
        materials_data = [
            {'name': 'Тротуарная плитка 300х150', 'code': 'ТП-300-150', 'unit': 'шт'},
            {'name': 'Бортовой камень БР 100.20.8', 'code': 'БК-100-20-8', 'unit': 'м'},
            {'name': 'Асфальтобетонная смесь', 'code': 'АБС-I', 'unit': 'т'},
            {'name': 'Песок строительный', 'code': 'ПС', 'unit': 'м³'},
            {'name': 'Щебень гранитный фр.5-20', 'code': 'ЩГ-5-20', 'unit': 'м³'},
            {'name': 'Цемент М400', 'code': 'ЦМ-400', 'unit': 'т'},
        ]
        
        for material_data in materials_data:
            material_type, created = MaterialType.objects.get_or_create(
                code=material_data['code'],
                defaults={
                    'name': material_data['name'],
                    'unit': material_data['unit'],
                    'description': f'Материал: {material_data["name"]}'
                }
            )
            if created:
                self.stdout.write(f'Создан тип материала: {material_type.name}')

    def create_violation_types(self):
        """Создает типы нарушений на основе классификатора (базовые примеры)"""
        
        # Создаем категории
        categories_data = [
            {'name': 'Нарушения технологии производства работ'},
            {'name': 'Нарушения требований безопасности'},
            {'name': 'Нарушения сроков выполнения работ'},
            {'name': 'Нарушения качества материалов'},
        ]
        
        for cat_data in categories_data:
            category, created = ViolationCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': f'Категория нарушений: {cat_data["name"]}'
                }
            )
            if created:
                self.stdout.write(f'Создана категория нарушений: {category.name}')
        
        # Создаем типы нарушений
        violations_data = [
            {
                'code': 'ТПР-001',
                'name': 'Нарушение последовательности технологических операций',
                'category': 'Нарушения технологии производства работ',
                'source': 'construction_control',
                'type_field': 'Технологическое',
                'kind': 'Критичное',
                'days': 3
            },
            {
                'code': 'БЕЗ-001',
                'name': 'Нарушение требований охраны труда',
                'category': 'Нарушения требований безопасности',
                'source': 'inspector',
                'type_field': 'Безопасность',
                'kind': 'Критичное',
                'days': 1
            },
            {
                'code': 'СРК-001',
                'name': 'Отставание от графика производства работ',
                'category': 'Нарушения сроков выполнения работ',
                'source': 'construction_control',
                'type_field': 'Организационное',
                'kind': 'Среднее',
                'days': 5
            },
            {
                'code': 'КМА-001',
                'name': 'Использование материалов без сертификата качества',
                'category': 'Нарушения качества материалов',
                'source': 'inspector',
                'type_field': 'Качество',
                'kind': 'Критичное',
                'days': 7
            },
        ]
        
        for viol_data in violations_data:
            category = ViolationCategory.objects.get(name=viol_data['category'])
            violation_type, created = ViolationType.objects.get_or_create(
                code=viol_data['code'],
                defaults={
                    'name': viol_data['name'],
                    'category': category,
                    'source': viol_data['source'],
                    'type_field': viol_data['type_field'],
                    'kind': viol_data['kind'],
                    'regulatory_deadline_days': viol_data['days'],
                    'description': f'Тип нарушения: {viol_data["name"]}'
                }
            )
            if created:
                self.stdout.write(f'Создан тип нарушения: {violation_type.name}')

    def create_opening_checklist(self):
        """Создает пункты чек-листа открытия объекта"""
        checklist_items = [
            {
                'name': 'Ограждение строительной площадки установлено',
                'description': 'Проверка наличия и качества ограждения строительной площадки',
                'order': 1
            },
            {
                'name': 'Информационный щит установлен',
                'description': 'Проверка наличия информационного щита с данными о проекте',
                'order': 2
            },
            {
                'name': 'Подготовлены временные дороги и проезды',
                'description': 'Обеспечение подъездных путей к объекту',
                'order': 3
            },
            {
                'name': 'Обеспечено электроснабжение объекта',
                'description': 'Подключение временного электроснабжения',
                'order': 4
            },
            {
                'name': 'Организована система водоснабжения',
                'description': 'Обеспечение водоснабжения для производства работ',
                'order': 5
            },
            {
                'name': 'Проведена разбивка осей и уровней',
                'description': 'Геодезическая разбивка объекта согласно проекту',
                'order': 6
            },
            {
                'name': 'Оформлены разрешительные документы',
                'description': 'Получение всех необходимых разрешений',
                'order': 7
            },
            {
                'name': 'Назначены ответственные лица',
                'description': 'Назначение и документальное оформление ответственных',
                'order': 8
            },
        ]
        
        for item_data in checklist_items:
            item, created = OpeningChecklistItem.objects.get_or_create(
                name=item_data['name'],
                defaults={
                    'description': item_data['description'],
                    'order': item_data['order'],
                    'is_required': True
                }
            )
            if created:
                self.stdout.write(f'Создан пункт чек-листа: {item.name}')

    def import_work_specs(self, dataset_path):
        """Импорт электронных спецификаций и перечней работ для проектов"""
        try:
            import os
            specs_dir = f'{dataset_path}/Эл. спец-ии и перечень работ'
            if not os.path.isdir(specs_dir):
                self.stdout.write('Папка со спецификациями не найдена, пропускаем')
                return
            from projects.models import WorkSpecRow, Project
            # Простейшее сопоставление по вхождению названия проекта в имя файла
            files = [f for f in os.listdir(specs_dir) if f.endswith('.xlsx')]
            for f in files:
                file_path = f'{specs_dir}/{f}'
                df = pd.read_excel(file_path)
                # Эвристика поиска колонок
                cols = {c: c for c in df.columns}
                name_col = next((c for c in df.columns if 'наимен' in str(c).lower()), df.columns[0])
                unit_col = next((c for c in df.columns if 'ед' in str(c).lower()), None)
                vol_col = next((c for c in df.columns if 'объ' in str(c).lower() or 'кол' in str(c).lower()), None)
                code_col = next((c for c in df.columns if 'код' in str(c).lower() or 'кпгз' in str(c).lower()), None)
                # Находим проект по имени
                proj = None
                for p in Project.objects.all():
                    if any(token in f for token in [p.name.split(',')[0], p.name.split(' ')[0]]):
                        proj = p
                        break
                if not proj:
                    continue
                order = 0
                created_rows = 0
                for _, row in df.iterrows():
                    name = str(row.get(name_col, '')).strip()
                    if not name or name.lower().startswith('наименование'):
                        continue
                    unit = str(row.get(unit_col, '')).strip() if unit_col else ''
                    code = str(row.get(code_col, '')).strip() if code_col else ''
                    vol_val = row.get(vol_col) if vol_col else None
                    try:
                        planned_volume = float(str(vol_val).replace(',', '.')) if vol_val not in [None, 'nan', ''] else None
                    except Exception:
                        planned_volume = None
                    WorkSpecRow.objects.get_or_create(
                        project=proj,
                        code=code,
                        name=name,
                        defaults={
                            'unit': unit,
                            'planned_volume': planned_volume,
                            'order': order
                        }
                    )
                    order += 1
                    created_rows += 1
                self.stdout.write(self.style.SUCCESS(f'Импортировано строк спецификации для {proj.name}: {created_rows}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта спецификаций: {e}'))

    def import_violation_classifier(self, dataset_path):
        """Импорт классификатора нарушений из файла"""
        try:
            import os
            file_path = f"{dataset_path}/Классификатор нарушений/Классификатор производство работ.xlsx"
            if not os.path.isfile(file_path):
                self.stdout.write('Файл классификатора не найден, пропускаем')
                return
            df = pd.read_excel(file_path)
            from violations.models import ViolationCategory, ViolationType
            # Пытаемся определить колонки
            name_col = next((c for c in df.columns if 'наимен' in str(c).lower()), df.columns[0])
            code_col = next((c for c in df.columns if 'код' in str(c).lower()), None)
            type_col = next((c for c in df.columns if 'тип' in str(c).lower()), None)
            kind_col = next((c for c in df.columns if 'вид' in str(c).lower()), None)
            days_col = next((c for c in df.columns if 'срок' in str(c).lower()), None)
            cat, _ = ViolationCategory.objects.get_or_create(name='Классификатор контрольного органа')
            created = 0
            for _, row in df.iterrows():
                name = str(row.get(name_col, '')).strip()
                if not name or name.lower().startswith('наименование'):
                    continue
                code = str(row.get(code_col, '')).strip() if code_col else ''
                type_field = str(row.get(type_col, '')).strip() if type_col else ''
                kind = str(row.get(kind_col, '')).strip() if kind_col else ''
                try:
                    days = int(row.get(days_col)) if days_col else 3
                except Exception:
                    days = 3
                ViolationType.objects.get_or_create(
                    code=code or f'INS-{100000+created}',
                    defaults={
                        'name': name,
                        'category': cat,
                        'source': 'inspector',
                        'type_field': type_field or 'Технологическое',
                        'kind': kind or 'Среднее',
                        'regulatory_deadline_days': days,
                        'description': name
                    }
                )
                created += 1
            self.stdout.write(self.style.SUCCESS(f'Импортировано типов нарушений (инспектор): {created}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка импорта классификатора: {e}'))
