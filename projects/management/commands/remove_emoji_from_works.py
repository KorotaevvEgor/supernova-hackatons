from django.core.management.base import BaseCommand
from projects.models import Work
import re

class Command(BaseCommand):
    help = 'Удалить эмодзи из названий и описаний работ (Work)'

    def handle(self, *args, **options):
        # Шаблон для поиска эмодзи
        emoji_pattern = re.compile(r'[\U0001F000-\U0001FFFF]|[\U00002600-\U000027BF]|[\U0001F900-\U0001F9FF]|[\U0001F1E0-\U0001F1FF]')
        
        updated_count = 0
        
        self.stdout.write("=== Удаление эмодзи из работ (Work) ===")
        
        for work in Work.objects.all():
            updated = False
            old_name = work.name
            old_description = work.description
            
            # Обрабатываем название
            if work.name and emoji_pattern.search(work.name):
                # Убираем эмодзи и очищаем лишние пробелы
                work.name = emoji_pattern.sub('', work.name).strip()
                # Убираем двойные пробелы
                work.name = ' '.join(work.name.split())
                updated = True
                
            # Обрабатываем описание
            if work.description and emoji_pattern.search(work.description):
                # Убираем эмодзи и очищаем лишние пробелы
                work.description = emoji_pattern.sub('', work.description).strip()
                # Убираем двойные пробелы
                work.description = ' '.join(work.description.split())
                updated = True
            
            if updated:
                work.save()
                updated_count += 1
                
                self.stdout.write(f"ID {work.id}:")
                if old_name != work.name:
                    self.stdout.write(f"  NAME: '{old_name}' -> '{work.name}'")
                if old_description != work.description:
                    desc_preview = (work.description[:80] + '...') if len(work.description) > 80 else work.description
                    self.stdout.write(f"  DESC: обновлено -> '{desc_preview}'")
                self.stdout.write("")
        
        if updated_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Успешно обновлено {updated_count} работ')
            )
        else:
            self.stdout.write(
                self.style.WARNING('Не найдено работ с эмодзи')
            )
