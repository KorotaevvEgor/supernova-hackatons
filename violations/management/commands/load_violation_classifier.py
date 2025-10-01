#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db import models
from violations.models import ViolationClassifier


class Command(BaseCommand):
    help = 'Загрузка классификатора нарушений производства работ из Excel файла'

    def add_arguments(self, parser):
        parser.add_argument(
            'excel_file',
            type=str,
            help='Путь к Excel файлу с классификатором нарушений'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед загрузкой'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка данных без сохранения в базу'
        )

    def handle(self, *args, **options):
        excel_file = options['excel_file']
        clear_existing = options['clear']
        dry_run = options['dry_run']

        self.stdout.write(
            self.style.SUCCESS(f'Начинаем загрузку классификатора из файла: {excel_file}')
        )

        try:
            # Читаем Excel файл
            df = pd.read_excel(excel_file, sheet_name=0)
            
            self.stdout.write(f'Прочитано строк: {len(df)}')
            self.stdout.write(f'Колонки: {list(df.columns)}')

            # Проверяем обязательные колонки
            required_columns = ['Категория', 'Вид', 'Тип', 'Наименование']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise CommandError(
                    f'Отсутствуют обязательные колонки: {missing_columns}'
                )

            # Очищаем данные
            df = df.dropna(subset=['Категория', 'Наименование'])
            
            # Обрабатываем сроки устранения
            def parse_deadline(value):
                if pd.isna(value) or value == '-':
                    return None
                try:
                    return int(value)
                except (ValueError, TypeError):
                    return None

            df['deadline_days'] = df['Регламентный срок устранения'].apply(parse_deadline)

            self.stdout.write(f'После очистки строк: {len(df)}')

            if dry_run:
                self.stdout.write(self.style.WARNING('Режим проверки (dry-run) - данные не будут сохранены'))
                
                # Выводим статистику
                self.stdout.write('\nСтатистика по категориям:')
                for category, count in df['Категория'].value_counts().items():
                    self.stdout.write(f'  {category}: {count} записей')
                
                self.stdout.write('\nПримеры записей:')
                for idx, row in df.head(3).iterrows():
                    self.stdout.write(
                        f'  {row["Категория"]} | {row["Вид"]} | {row["Тип"]} | '
                        f'{row["Наименование"][:50]}... | {row["deadline_days"]} дней'
                    )
                return

            # Транзакция для загрузки данных
            with transaction.atomic():
                if clear_existing:
                    self.stdout.write('Очищаем существующие данные...')
                    ViolationClassifier.objects.all().delete()

                created_count = 0
                updated_count = 0
                error_count = 0

                for idx, row in df.iterrows():
                    try:
                        # Очищаем строковые значения
                        category = str(row['Категория']).strip()
                        kind = str(row['Вид']).strip() if pd.notna(row['Вид']) else ''
                        type_name = str(row['Тип']).strip() if pd.notna(row['Тип']) else ''
                        name = str(row['Наименование']).strip()
                        deadline_days = row['deadline_days']

                        # Проверяем дубликаты по основным полям
                        # Преобразуем NaN в None для корректного сохранения
                        if pd.isna(deadline_days):
                            deadline_days = None

                        classifier, created = ViolationClassifier.objects.get_or_create(
                            category=category,
                            kind=kind,
                            type_name=type_name,
                            name=name,
                            defaults={
                                'regulatory_deadline_days': deadline_days,
                                'is_active': True
                            }
                        )

                        if created:
                            created_count += 1
                        else:
                            # Обновляем существующую запись
                            classifier.regulatory_deadline_days = deadline_days
                            classifier.is_active = True
                            classifier.save()
                            updated_count += 1

                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'Ошибка в строке {idx + 1}: {e}')
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nЗагрузка завершена!\n'
                        f'Создано новых записей: {created_count}\n'
                        f'Обновлено записей: {updated_count}\n'
                        f'Ошибок: {error_count}'
                    )
                )

                # Выводим статистику по категориям
                self.stdout.write('\nСтатистика по категориям в базе данных:')
                categories = ViolationClassifier.objects.values('category').annotate(
                    count=models.Count('id')
                ).order_by('category')
                
                for category_data in categories:
                    self.stdout.write(
                        f'  {category_data["category"]}: {category_data["count"]} записей'
                    )

        except FileNotFoundError:
            raise CommandError(f'Файл не найден: {excel_file}')
        except Exception as e:
            raise CommandError(f'Ошибка при загрузке данных: {e}')