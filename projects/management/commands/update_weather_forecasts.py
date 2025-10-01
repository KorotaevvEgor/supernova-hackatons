from django.core.management.base import BaseCommand
from projects.models import Project, WeatherForecast
from projects.views import get_or_create_weather_forecast
from django.utils import timezone


class Command(BaseCommand):
    help = 'Обновляет прогнозы погоды для всех проектов на основе текущей даты'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=int,
            help='ID конкретного проекта для обновления (по умолчанию все проекты)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно пересоздать все прогнозы',
        )

    def handle(self, *args, **options):
        self.stdout.write("=== Обновление прогнозов погоды ===")
        
        today = timezone.now().date()
        self.stdout.write(f"Текущая дата: {today}")
        
        # Определяем проекты для обновления
        if options['project_id']:
            projects = Project.objects.filter(id=options['project_id'])
            if not projects.exists():
                self.stderr.write(f"Проект с ID {options['project_id']} не найден")
                return
        else:
            projects = Project.objects.all()
        
        self.stdout.write(f"Обновляем прогнозы для {projects.count()} проектов...")
        
        updated_count = 0
        
        for project in projects:
            self.stdout.write(f"\n📍 Проект: {project.name} (ID: {project.id})")
            
            if options['force']:
                # Принудительно удаляем все старые прогнозы
                old_count = WeatherForecast.objects.filter(project=project).count()
                WeatherForecast.objects.filter(project=project).delete()
                self.stdout.write(f"  Удалено {old_count} старых прогнозов")
            
            # Создаем/обновляем прогноз
            forecasts = get_or_create_weather_forecast(project)
            
            self.stdout.write(f"  ✅ Создано {len(forecasts)} актуальных прогнозов")
            self.stdout.write(f"  📅 Период: {forecasts[0].forecast_date} - {forecasts[-1].forecast_date}")
            
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎉 Обновлено прогнозов для {updated_count} проектов")
        )
        self.stdout.write("Все прогнозы теперь начинаются с текущей даты!")
