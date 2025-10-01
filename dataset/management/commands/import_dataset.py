import os
import pandas as pd
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from dataset.models import (
    ViolationClassifier, ProjectCoordinates, WorkSpecification, 
    NetworkSchedule, TransportDocument, CheckListTemplate, CheckListItem
)

class Command(BaseCommand):
    help = 'Импорт данных из датасета ЛЦТ 2025'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset-path', 
            type=str, 
            default='/Users/korotaevegor/Desktop/Хакатон/Датасет ЛЦТ 2025',
            help='Путь к папке с датасетом ЛЦТ 2025'
        )
        parser.add_argument(
            '--clear', 
            action='store_true', 
            help='Очистить существующие данные перед импортом'
        )
    
    def handle(self, *args, **options):
        dataset_path = options['dataset_path']
        
        if options['clear']:
            self.stdout.write('Очистка существующих данных...')
            ViolationClassifier.objects.all().delete()
            ProjectCoordinates.objects.all().delete()
            WorkSpecification.objects.all().delete()
            NetworkSchedule.objects.all().delete()
            TransportDocument.objects.all().delete()
            CheckListTemplate.objects.all().delete()
            CheckListItem.objects.all().delete()
        
        # Импорт классификатора нарушений
        self.import_violations(dataset_path)
        
        # Импорт координат объектов
        self.import_coordinates(dataset_path)
        
        # Импорт спецификаций работ
        self.import_work_specifications(dataset_path)
        
        # Импорт сетевого графика
        self.import_network_schedule(dataset_path)
        
        # Импорт чек-листов
        self.import_checklists(dataset_path)
        
        self.stdout.write(
            self.style.SUCCESS('Импорт данных успешно завершен!')
        )
    
    def import_violations(self, dataset_path):
        """Импорт классификатора нарушений"""
        file_path = os.path.join(
            dataset_path, 
            'Классификатор нарушений', 
            'Классификатор производство работ.xlsx'
        )
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.WARNING(f'Файл классификатора не найден: {file_path}')
            )
            return
        
        try:
            df = pd.read_excel(file_path)
            count = 0
            
            for _, row in df.iterrows():
                if pd.isna(row.get('Наименование')):
                    continue
                    
                # Определяем категорию на основе текста
                category = 'culture'
                if 'Культура производства' in str(row.get('Категория', '')):
                    category = 'culture'
                elif 'технич' in str(row.get('Категория', '')).lower():
                    category = 'technical'
                elif 'безопас' in str(row.get('Категория', '')).lower():
                    category = 'safety'
                
                # Определяем тип нарушения
                violation_type = 'fixable'
                if 'Грубое' in str(row.get('Тип', '')):
                    violation_type = 'serious'
                elif 'Критическое' in str(row.get('Тип', '')):
                    violation_type = 'critical'
                
                ViolationClassifier.objects.create(
                    category=category,
                    violation_type=violation_type,
                    severity=str(row.get('Тип', 'Грубое')),
                    name=str(row.get('Наименование', '')),
                    fix_period=int(row.get('Регламентный срок устранения', 1))
                )
                count += 1
            
            self.stdout.write(f'Импортировано нарушений: {count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка импорта нарушений: {e}')
            )
    
    def import_coordinates(self, dataset_path):
        """Импорт координат объектов"""
        file_path = os.path.join(
            dataset_path, 
            'Примеры координат объектов ремонта', 
            'Полигоны.xlsx'
        )
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.WARNING(f'Файл координат не найден: {file_path}')
            )
            return
        
        try:
            df = pd.read_excel(file_path)
            count = 0
            
            # Обработка файла с координатами
            if len(df.columns) >= 8:
                # Берем названия объектов из заголовков
                object_names = [
                    'Флотская 54,58к1', 'Некрасовка', 'Бестужевых 27А',
                    'Каргопольская 18', 'Проспект Мира 194', 'Путевой 38',
                    'Челобитьевское 14к3'
                ]
                
                for i, name in enumerate(object_names):
                    if i < len(df.columns) - 1:  # -1 для колонки WKT
                        wkt_column = df.iloc[0, 0] if i == 0 else df.iloc[0, i+1]
                        if pd.notna(wkt_column) and 'POLYGON' in str(wkt_column):
                            ProjectCoordinates.objects.create(
                                name=name,
                                address=name,
                                wkt_polygon=str(wkt_column)
                            )
                            count += 1
            
            self.stdout.write(f'Импортировано координат: {count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка импорта координат: {e}')
            )
    
    def import_work_specifications(self, dataset_path):
        """Импорт спецификаций работ"""
        specs_dir = os.path.join(dataset_path, 'Эл. спец-ии и перечень работ')
        
        if not os.path.exists(specs_dir):
            self.stdout.write(
                self.style.WARNING(f'Папка спецификаций не найдена: {specs_dir}')
            )
            return
        
        count = 0
        for filename in os.listdir(specs_dir):
            if filename.endswith('.xlsx'):
                file_path = os.path.join(specs_dir, filename)
                
                try:
                    df = pd.read_excel(file_path)
                    
                    # Извлекаем название объекта из имени файла
                    object_name = filename.replace('Перечень работ СОК- ', '')\
                                         .replace('Перечень_работ_СОК_', '')\
                                         .replace('.xlsx', '')\
                                         .replace('_', ' ')
                    
                    for _, row in df.iterrows():
                        if pd.isna(row.iloc[0]) or row.iloc[0] == 'Unnamed: 0':
                            continue
                            
                        work_name = str(row.iloc[0])
                        quantity = float(row.iloc[1]) if pd.notna(row.iloc[1]) else 0
                        unit = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ''
                        
                        # Парсим даты
                        start_date = None
                        end_date = None
                        if len(row) > 4 and pd.notna(row.iloc[4]):
                            try:
                                start_date = pd.to_datetime(row.iloc[4]).date()
                            except:
                                pass
                        if len(row) > 5 and pd.notna(row.iloc[5]):
                            try:
                                end_date = pd.to_datetime(row.iloc[5]).date()
                            except:
                                pass
                        
                        address = str(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else ''
                        
                        WorkSpecification.objects.create(
                            object_name=object_name,
                            work_name=work_name,
                            quantity=quantity,
                            unit=unit,
                            start_date=start_date,
                            end_date=end_date,
                            address=address
                        )
                        count += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Ошибка обработки файла {filename}: {e}')
                    )
        
        self.stdout.write(f'Импортировано спецификаций работ: {count}')
    
    def import_network_schedule(self, dataset_path):
        """Импорт сетевого графика"""
        file_path = os.path.join(
            dataset_path, 
            'Пример сетевого графика', 
            'Графики.xlsx'
        )
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.WARNING(f'Файл сетевого графика не найден: {file_path}')
            )
            return
        
        try:
            df = pd.read_excel(file_path)
            count = 0
            current_object = ""
            
            for _, row in df.iterrows():
                # Проверяем, не является ли это заголовком объекта
                if pd.isna(row.iloc[1]) and pd.notna(row.iloc[0]):
                    if 'Проспект Мира' in str(row.iloc[0]) or \
                       'Каргопольская' in str(row.iloc[0]) or \
                       'Флотская' in str(row.iloc[0]):
                        current_object = str(row.iloc[0])
                        continue
                
                # Пропускаем строки заголовков
                if str(row.iloc[0]) in ['Наименование работы', 'Unnamed: 0']:
                    continue
                
                if pd.isna(row.iloc[0]):
                    continue
                
                work_name = str(row.iloc[0])
                kpgz_code = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
                
                start_date = None
                end_date = None
                if pd.notna(row.iloc[2]):
                    try:
                        start_date = pd.to_datetime(row.iloc[2]).date()
                    except:
                        pass
                if len(row) > 3 and pd.notna(row.iloc[3]):
                    try:
                        end_date = pd.to_datetime(row.iloc[3]).date()
                    except:
                        pass
                
                work_essence = str(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else ''
                
                NetworkSchedule.objects.create(
                    object_name=current_object or 'Неизвестный объект',
                    work_name=work_name,
                    kpgz_code=kpgz_code,
                    start_date=start_date,
                    end_date=end_date,
                    work_essence=work_essence
                )
                count += 1
            
            self.stdout.write(f'Импортировано записей сетевого графика: {count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка импорта сетевого графика: {e}')
            )
    
    def import_checklists(self, dataset_path):
        """Импорт чек-листов"""
        # Создаем шаблоны чек-листов на основе загруженных данных
        
        # Чек-лист открытия объекта
        opening_template, created = CheckListTemplate.objects.get_or_create(
            name='Проверка качества выполнения комплекса строительно-монтажных работ',
            form_type='opening',
            defaults={'description': 'Форма №1 «Организация строительства»'}
        )
        
        if created:
            # Добавляем пункты из загруженного чек-листа
            checklist_items = [
                {
                    'section': 'Наличие разрешительной, организационно-технологической, рабочей документации',
                    'item_number': '1.1',
                    'description': 'Наличие приказа на ответственное лицо, осуществляющего строительство (производство работ).',
                    'regulatory_document': 'п. 5.3. СП 48.13330.2019. Изм. №1. Организация строительства'
                },
                {
                    'section': 'Наличие разрешительной, организационно-технологической, рабочей документации',
                    'item_number': '1.2', 
                    'description': 'Наличие приказа на ответственное лицо, осуществляющее строительный контроль (с указанием идентификационного номера в НРС в области строительства).',
                    'regulatory_document': 'п. 5.3. СП 48.13330.2019. Изм. №1. Организация строительства'
                },
                {
                    'section': 'Инженерная подготовка строительной площадки',
                    'item_number': '2.1',
                    'description': 'Наличие акта геодезической разбивочной основы, принятых знаков (реперов).',
                    'regulatory_document': 'п. 7.2. СП 48.13330.2019. Изм. №1. Организация строительства'
                },
                {
                    'section': 'Инженерная подготовка строительной площадки', 
                    'item_number': '2.2',
                    'description': 'Наличие генерального плана (ситуационного плана).',
                    'regulatory_document': 'п. 7.6. СП 48.13330.2019. Изм. №1. Организация строительства'
                }
            ]
            
            for i, item in enumerate(checklist_items):
                CheckListItem.objects.create(
                    template=opening_template,
                    section=item['section'],
                    item_number=item['item_number'],
                    description=item['description'],
                    regulatory_document=item['regulatory_document'],
                    order=i + 1
                )
        
        # Ежедневный чек-лист
        daily_template, created = CheckListTemplate.objects.get_or_create(
            name='Ежедневный контроль строительства',
            form_type='daily',
            defaults={'description': 'Форма №2 - Ежедневный контроль'}
        )
        
        # Контроль качества
        quality_template, created = CheckListTemplate.objects.get_or_create(
            name='Контроль качества работ',
            form_type='quality', 
            defaults={'description': 'Форма №3 - Контроль качества'}
        )
        
        self.stdout.write('Импортированы шаблоны чек-листов')