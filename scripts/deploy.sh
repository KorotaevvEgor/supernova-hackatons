#!/bin/bash

# Скрипт для деплоя Urban Construction Control System
# Использование: ./scripts/deploy.sh [production|staging]

set -e  # Выход при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Определение окружения
ENVIRONMENT=${1:-staging}

echo -e "${BLUE}🚀 Начинаю деплой Urban Construction Control System для окружения: ${ENVIRONMENT}${NC}"

# Проверяем наличие необходимых файлов
if [ ! -f ".env.${ENVIRONMENT}" ]; then
    echo -e "${RED}❌ Файл .env.${ENVIRONMENT} не найден!${NC}"
    echo -e "${YELLOW}Создайте .env.${ENVIRONMENT} файл на основе .env.example${NC}"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ Файл docker-compose.yml не найден!${NC}"
    exit 1
fi

# Функция для выполнения команд с логированием
run_command() {
    echo -e "${BLUE}➤ Выполняю: $1${NC}"
    eval $1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Успешно: $1${NC}"
    else
        echo -e "${RED}❌ Ошибка в команде: $1${NC}"
        exit 1
    fi
}

# Загрузка переменных окружения
export $(grep -v '^#' .env.${ENVIRONMENT} | xargs)

echo -e "${YELLOW}📋 Настройки деплоя:${NC}"
echo -e "Environment: ${ENVIRONMENT}"
echo -e "DEBUG: ${DEBUG:-Not set}"
echo -e "ALLOWED_HOSTS: ${ALLOWED_HOSTS:-Not set}"

# Остановка и удаление старых контейнеров
echo -e "\n${YELLOW}🛑 Остановка старых контейнеров...${NC}"
run_command "docker-compose down --volumes --remove-orphans"

# Создание резервной копии (если это продакшн)
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "\n${YELLOW}💾 Создание резервной копии базы данных...${NC}"
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    run_command "docker-compose exec -T db pg_dump -U \${POSTGRES_USER:-urban_user} \${POSTGRES_DB:-urban_system} > backups/${BACKUP_FILE}" || true
    echo -e "${GREEN}💾 Резервная копия сохранена в backups/${BACKUP_FILE}${NC}"
fi

# Сборка новых образов
echo -e "\n${YELLOW}🏗️  Сборка Docker образов...${NC}"
run_command "docker-compose build --no-cache"

# Запуск сервисов
echo -e "\n${YELLOW}🚀 Запуск сервисов...${NC}"
if [ "$ENVIRONMENT" = "production" ]; then
    run_command "docker-compose --profile production up -d"
else
    run_command "docker-compose up -d"
fi

# Ожидание запуска базы данных
echo -e "\n${YELLOW}⏳ Ожидание запуска базы данных...${NC}"
sleep 10

# Выполнение миграций
echo -e "\n${YELLOW}🗃️  Выполнение миграций базы данных...${NC}"
run_command "docker-compose exec web python manage.py migrate"

# Создание суперпользователя (только для staging)
if [ "$ENVIRONMENT" = "staging" ]; then
    echo -e "\n${YELLOW}👤 Создание суперпользователя...${NC}"
    run_command "docker-compose exec web python manage.py shell -c \"
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Суперпользователь создан: admin/admin123')
else:
    print('Суперпользователь уже существует')
\"" || true
fi

# Загрузка фикстур (только для staging/dev)
if [ "$ENVIRONMENT" != "production" ]; then
    echo -e "\n${YELLOW}📦 Загрузка тестовых данных...${NC}"
    run_command "docker-compose exec web python manage.py loaddata fixtures/all_data.json" || echo -e "${YELLOW}⚠️  Фикстуры не загружены (это нормально для первого запуска)${NC}"
fi

# Сбор статических файлов
echo -e "\n${YELLOW}📁 Сбор статических файлов...${NC}"
run_command "docker-compose exec web python manage.py collectstatic --noinput"

# Проверка состояния сервисов
echo -e "\n${YELLOW}🔍 Проверка состояния сервисов...${NC}"
run_command "docker-compose ps"

# Проверка доступности приложения
echo -e "\n${YELLOW}🌐 Проверка доступности приложения...${NC}"
sleep 5
if curl -f -s http://localhost:8000/ > /dev/null; then
    echo -e "${GREEN}✅ Приложение доступно на http://localhost:8000/${NC}"
else
    echo -e "${YELLOW}⚠️  Приложение может быть еще недоступно, подождите несколько минут${NC}"
fi

# Вывод логов (только последние строки)
echo -e "\n${YELLOW}📋 Последние логи:${NC}"
docker-compose logs --tail=10 web

echo -e "\n${GREEN}🎉 Деплой завершен успешно!${NC}"
echo -e "${BLUE}📌 Полезные команды:${NC}"
echo -e "  Просмотр логов: docker-compose logs -f web"
echo -e "  Остановка: docker-compose down"
echo -e "  Доступ к контейнеру: docker-compose exec web bash"
echo -e "  Резервные копии: ls -la backups/"

if [ "$ENVIRONMENT" = "staging" ]; then
    echo -e "\n${YELLOW}👤 Данные для входа в админку:${NC}"
    echo -e "  URL: http://localhost:8000/admin/"
    echo -e "  Логин: admin"
    echo -e "  Пароль: admin123"
fi