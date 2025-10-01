import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from projects.models import Project, WorkType, WeatherForecast, WeatherWorkRecommendation


class Command(BaseCommand):
    help = 'Загрузка демонстрационных данных для погодной аналитики'

    def handle(self, *args, **options):
        # Путь к JSON файлу с тестовыми данными
        json_file_path = os.path.join(os.path.dirname(__file__), '../../../weather_demo_data.json')
        
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'Файл {json_file_path} не найден')
            )
            return
        except json.JSONDecodeError:
            self.stdout.write(
                self.style.ERROR('Ошибка при парсинге JSON файла')
            )
            return

        # Создаем проект
        project_data = data['project']
        project, created = Project.objects.get_or_create(
            name=project_data['name'],
            defaults={
                'address': project_data['location'],
                'planned_start_date': parse_date(project_data['start_date']),
                'planned_end_date': parse_date(project_data['end_date']),
                'description': 'Демонстрационный проект для хакатона',
                'status': 'active',
                'contract_number': 'DEMO-2024-001'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Создан проект: {project.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Проект уже существует: {project.name}')
            )

        # Информация о создании проекта
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Создан проект: {project.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Проект уже существует: {project.name}')
            )

        # Создаем типы работ
        work_types_data = data['work_types']
        work_type_objects = {}
        
        for work_type_data in work_types_data:
            # Генерируем код на основе названия
            code = ''.join([word[0].upper() for word in work_type_data['name'].split()][:3])
            if len(code) < 3:
                code = work_type_data['name'][:3].upper()
                
            work_type, created = WorkType.objects.get_or_create(
                name=work_type_data['name'],
                defaults={
                    'description': work_type_data['description'],
                    'code': f'{code}-{work_type_data["id"]:02d}'
                }
            )
            work_type_objects[work_type_data['id']] = work_type
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Создан тип работ: {work_type.name}')
                )

        # Создаем прогноз погоды
        weather_forecast_data = data['weather_forecast']
        
        for forecast_data in weather_forecast_data:
            weather_forecast, created = WeatherForecast.objects.get_or_create(
                project=project,
                forecast_date=parse_date(forecast_data['date']),
                defaults={
                    'temperature': forecast_data['temperature'],
                    'humidity': forecast_data['humidity'],
                    'wind_speed': forecast_data['wind_speed'],
                    'precipitation': forecast_data['precipitation'],
                    'weather_main': forecast_data['condition'].capitalize(),
                    'weather_description': forecast_data['condition_text']
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Создан прогноз на {forecast_data["date"]}')
                )

        # Создаем рекомендации для работ в зависимости от погоды
        weather_conditions_mapping = {
            'sunny': 'clear',
            'partly_cloudy': 'clouds',
            'cloudy': 'clouds',
            'light_rain': 'rain',
            'rain': 'rain',
            'snow': 'snow',
            'blizzard': 'snow',
            'storm': 'thunderstorm'
        }
        
        # Пройдем по всем типам работ и создадим рекомендации
        for work_type in work_type_objects.values():
            for condition, code in weather_conditions_mapping.items():
                # Определяем риск и рекомендации для различных типов работ
                risk_level = 'low'
                recommendation = f'Работы по {work_type.name.lower()} в условиях "{condition}" разрешены'
                is_allowed = True
                
                # Особые правила для покрасочных работ
                if 'Покрасочные' in work_type.name and code in ['rain', 'snow']:
                    risk_level = 'critical'
                    recommendation = 'Покрасочные работы запрещены при осадках'
                    is_allowed = False
                elif code in ['rain', 'snow'] and 'Земляные' in work_type.name:
                    risk_level = 'high'
                    recommendation = 'Земляные работы при осадках требуют особой осторожности'
                    is_allowed = True
                elif code == 'thunderstorm':
                    risk_level = 'critical'
                    recommendation = f'Работы по {work_type.name.lower()} запрещены при грозе'
                    is_allowed = False
                
                weather_rec, created = WeatherWorkRecommendation.objects.get_or_create(
                    work_type=work_type,
                    weather_condition=code,
                    defaults={
                        'risk_level': risk_level,
                        'recommendation': recommendation,
                        'is_work_allowed': is_allowed
                    }
                )
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Создана рекомендация для {work_type.name} - {condition}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                '\n' + '='*50 + '\n'
                'Загрузка демонстрационных данных завершена успешно!\n'
                f'Проект: {project.name}\n'
                f'Типов работ: {len(work_type_objects)}\n'
                f'Дней прогноза: {len(weather_forecast_data)}\n'
                f'Создано рекомендаций: {len(work_type_objects) * len(weather_conditions_mapping)}\n'
                '='*50
            )
        )
