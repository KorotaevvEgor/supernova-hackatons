#!/bin/bash

# Скрипт для настройки локальной разработки
# Urban Construction Control System

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔧 Настройка локальной среды разработки${NC}"

# Проверка наличия необходимых инструментов
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 не установлен!${NC}"
        echo -e "${YELLOW}Пожалуйста, установите $1 и повторите попытку${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ $1 найден${NC}"
    fi
}

echo -e "\n${YELLOW}🔍 Проверка необходимых инструментов...${NC}"
check_tool "python3"
check_tool "pip"
check_tool "docker"
check_tool "docker-compose"

# Создание .env файла для разработки
if [ ! -f ".env" ]; then
    echo -e "\n${YELLOW}📝 Создание .env файла...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✅ Создан .env файл из примера${NC}"
    echo -e "${BLUE}📋 Отредактируйте .env файл при необходимости${NC}"
else
    echo -e "${GREEN}✅ .env файл уже существует${NC}"
fi

# Создание директорий
echo -e "\n${YELLOW}📁 Создание необходимых директорий...${NC}"
mkdir -p backups logs media staticfiles

# Установка Python зависимостей (опционально)
echo -e "\n${YELLOW}🤔 Установить Python зависимости локально? (y/N)${NC}"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${YELLOW}📦 Установка Python зависимостей...${NC}"
    
    # Проверка виртуального окружения
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}🏗️  Создание виртуального окружения...${NC}"
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo -e "${GREEN}✅ Зависимости установлены${NC}"
else
    echo -e "${BLUE}⏭️  Пропуск установки Python зависимостей${NC}"
fi

# Docker setup
echo -e "\n${YELLOW}🐳 Настройка Docker окружения...${NC}"

# Остановка существующих контейнеров
docker-compose -f docker-compose.dev.yml down 2>/dev/null || true

# Сборка образов
echo -e "${YELLOW}🏗️  Сборка Docker образов...${NC}"
docker-compose -f docker-compose.dev.yml build

# Запуск сервисов
echo -e "${YELLOW}🚀 Запуск сервисов разработки...${NC}"
docker-compose -f docker-compose.dev.yml up -d db

# Ожидание запуска базы данных
echo -e "${YELLOW}⏳ Ожидание запуска базы данных...${NC}"
sleep 10

# Проверка состояния базы данных
if docker-compose -f docker-compose.dev.yml exec db pg_isready -U urban_user; then
    echo -e "${GREEN}✅ База данных готова${NC}"
else
    echo -e "${RED}❌ База данных не запустилась${NC}"
    exit 1
fi

# Запуск веб приложения
echo -e "${YELLOW}🌐 Запуск веб приложения...${NC}"
docker-compose -f docker-compose.dev.yml up -d

# Выполнение миграций
echo -e "${YELLOW}🗃️  Выполнение миграций...${NC}"
sleep 5
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate

# Создание суперпользователя
echo -e "${YELLOW}👤 Создание суперпользователя...${NC}"
docker-compose -f docker-compose.dev.yml exec web python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Суперпользователь создан: admin/admin123')
else:
    print('Суперпользователь уже существует')
" 2>/dev/null || true

# Загрузка тестовых данных
if [ -f "fixtures/all_data.json" ]; then
    echo -e "${YELLOW}📦 Загрузка тестовых данных...${NC}"
    docker-compose -f docker-compose.dev.yml exec web python manage.py loaddata fixtures/all_data.json || echo -e "${YELLOW}⚠️  Некоторые фикстуры не загружены${NC}"
fi

# Проверка состояния
echo -e "\n${YELLOW}🔍 Проверка состояния сервисов...${NC}"
docker-compose -f docker-compose.dev.yml ps

# Проверка доступности
echo -e "\n${YELLOW}🌐 Проверка доступности приложения...${NC}"
sleep 3
if curl -f -s http://localhost:8000/ > /dev/null; then
    echo -e "${GREEN}✅ Приложение доступно на http://localhost:8000/${NC}"
else
    echo -e "${YELLOW}⚠️  Приложение еще запускается...${NC}"
fi

echo -e "\n${GREEN}🎉 Локальная среда разработки настроена!${NC}"
echo -e "\n${BLUE}📌 Полезная информация:${NC}"
echo -e "  🌐 Приложение: http://localhost:8000/"
echo -e "  🔧 Админка: http://localhost:8000/admin/ (admin/admin123)"
echo -e "  🗄️  База данных: localhost:5432 (urban_user/urban_password)"
echo -e "\n${BLUE}📌 Полезные команды:${NC}"
echo -e "  📋 Логи: docker-compose -f docker-compose.dev.yml logs -f web"
echo -e "  🛑 Остановка: docker-compose -f docker-compose.dev.yml down"
echo -e "  🔄 Перезапуск: docker-compose -f docker-compose.dev.yml restart web"
echo -e "  📦 Оболочка: docker-compose -f docker-compose.dev.yml exec web bash"
echo -e "  🗃️  Миграции: docker-compose -f docker-compose.dev.yml exec web python manage.py migrate"
echo -e "  👤 Консоль Django: docker-compose -f docker-compose.dev.yml exec web python manage.py shell"