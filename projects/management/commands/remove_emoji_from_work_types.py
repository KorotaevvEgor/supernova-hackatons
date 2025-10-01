from django.core.management.base import BaseCommand
from projects.models import WorkType
import re

class Command(BaseCommand):
    help = 'Удалить эмодзи из названий типов работ (WorkType)'

    def handle(self, *args, **options):
        # Шаблон для поиска эмодзи
        emoji_pattern = re.compile(r'[\U0001F000-\U0001FFFF]|[\U00002600-\U000027BF]|[\U0001F900-\U0001F9FF]|[\U0001F1E0-\U0001F1FF]')
        
        # Маппинг для замены названий
        name_mappings = {
            1: "Умные земляные работы",
            2: "Эко-бетонирование", 
            3: "Нейро-асфальтирование",
            4: "Нано-покрытия",
            5: "Умная плитка",
            6: "Карбоновые конструкции",
            7: "IoT-электромонтаж",
            8: "Био-ландшафт",
            9: "Дрон-демонтаж",
            10: "Солнечная кровля",
            11: "Гидро-системы",
            12: "Квантовое освещение"
        }
        
        updated_count = 0
        
        self.stdout.write("=== Удаление эмодзи из названий типов работ ===")
        
        for work_type in WorkType.objects.all():
            old_name = work_type.name
            
            if emoji_pattern.search(old_name):
                # Используем маппинг если есть, иначе просто убираем эмодзи
                if work_type.id in name_mappings:
                    new_name = name_mappings[work_type.id]
                else:
                    # Убираем эмодзи и лишние пробелы
                    new_name = emoji_pattern.sub('', old_name).strip()
                
                # Обновляем название
                work_type.name = new_name
                work_type.save()
                
                updated_count += 1
                self.stdout.write(
                    f"ID {work_type.id}: '{old_name}' -> '{new_name}'"
                )
        
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Успешно обновлено {updated_count} типов работ')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Не найдено типов работ с эмодзи')
            )
