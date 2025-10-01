#!/usr/bin/env python
"""
Скрипт для экспорта данных из базы данных в фикстуры
"""
import os
import sys
import django
from django.core.management import call_command

# Настройка Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'urban_control_system.settings')
django.setup()

def export_data():
    """Экспорт всех данных в фикстуры"""
    
    # Создаем директорию для фикстур
    fixtures_dir = 'fixtures'
    os.makedirs(fixtures_dir, exist_ok=True)
    
    print("🗂️  Экспортирую данные в фикстуры...")
    
    # Экспорт всех данных кроме системных
    try:
        call_command(
            'dumpdata',
            '--natural-foreign',
            '--natural-primary',
            '--exclude=contenttypes',
            '--exclude=auth.Permission',
            '--exclude=sessions',
            '--exclude=admin.LogEntry',
            '--output=fixtures/all_data.json',
            '--indent=2'
        )
        print("✅ Все данные экспортированы в fixtures/all_data.json")
        
        # Экспорт пользователей отдельно
        call_command(
            'dumpdata',
            'accounts.User',
            '--natural-foreign',
            '--natural-primary',
            '--output=fixtures/users.json',
            '--indent=2'
        )
        print("✅ Пользователи экспортированы в fixtures/users.json")
        
        # Экспорт проектов
        call_command(
            'dumpdata',
            'projects',
            '--natural-foreign',
            '--natural-primary',
            '--output=fixtures/projects.json',
            '--indent=2'
        )
        print("✅ Проекты экспортированы в fixtures/projects.json")
        
        # Экспорт материалов
        call_command(
            'dumpdata',
            'materials',
            '--natural-foreign',
            '--natural-primary',
            '--output=fixtures/materials.json',
            '--indent=2'
        )
        print("✅ Материалы экспортированы в fixtures/materials.json")
        
    except Exception as e:
        print(f"❌ Ошибка при экспорте: {e}")
        return False
    
    print("🎉 Экспорт данных завершен успешно!")
    return True

if __name__ == '__main__':
    export_data()