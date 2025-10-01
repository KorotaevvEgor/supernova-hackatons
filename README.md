# Система управления благоустройством Москвы

## 🏗️ Описание проекта

Современная информационная система для управления процессами благоустройства города Москвы, обеспечивающая полную прослеживаемость, прозрачность и контроль на всех этапах реализации городских программ.

## ✨ Ключевые возможности

### 🎯 Для службы строительного контроля
- Управление объектами благоустройства
- Контроль выполнения работ
- Верификация отчетов прорабов
- Внесение замечаний и контроль их устранения
- Управление графиками работ
- Аналитические дашборды

### 👷 Для прорабов (подрядчиков)
- ⭐ **Входной контроль с OCR** - автоматическое распознавание ТТН и документов
- Отчетность о выполненных работах
- Управление графиками производства работ
- Устранение замечаний и нарушений
- Фотофиксация процессов

### 🔍 For инспекторов контрольных органов
- Согласование активации объектов
- Внесение нарушений по классификатору
- Инициирование лабораторного контроля качества
- Контроль соблюдения нормативных требований
- Фиксация количества рабочей силы и техники

## 🚀 Технологический стек

### Backend
- **Django 5.2** - основной фреймворк
- **PostgreSQL + PostGIS** - пространственная база данных
- **Django REST Framework** - API
- **Celery + Redis** - асинхронные задачи

### Frontend
- **HTML5/CSS3** с **Tailwind CSS** - современный UI
- **Vanilla JavaScript** - интерактивность
- **Chart.js** - графики и аналитика  
- **Leaflet** - интерактивные карты

### Computer Vision & AI ⭐ НОВИНКА!
- **Tesseract OCR** - автоматическое распознавание текста из документов
- **Pillow (PIL)** - обработка и предобработка изображений
- **Intelligent extraction** - извлечение данных из ТТН и документов
- **Confidence scoring** - система оценки качества распознавания

### Дополнительные возможности
- **Геолокация** - GPS трекинг пользователей
- **Offline-first** - работа без интернета
- **PWA** - мобильная версия
- **Service Workers** - кэширование

## 📋 Установка и настройка

### Требования
- Python 3.11+
- PostgreSQL 14+ с PostGIS
- Redis 6+
- Node.js (опционально)

### Быстрый старт

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd urban_construction_system
```

2. **Создание виртального окружения**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

3. **Установка зависимостей**
```bash
pip install -r requirements.txt
```

4. **Настройка базы данных**
```bash
# Создайте PostgreSQL базу данных с PostGIS
createdb urban_control_db
psql -d urban_control_db -c "CREATE EXTENSION postgis;"

# Настройте .env файл
cp .env.example .env
# Отредактируйте DATABASE_URL и другие настройки
```

5. **Миграции**
```bash
python manage.py migrate
```

6. **Создание суперпользователя**
```bash
python manage.py createsuperuser
```

7. **Загрузка тестовых данных**
```bash
python manage.py loaddata fixtures/initial_data.json
```

8. **Запуск сервера**
```bash
python manage.py runserver
```

Система будет доступна по адресу: http://127.0.0.1:8000/

## 🤖 **OCR модуль входного контроля** ⭐ ГЛАВНАЯ НОВИНКА!

Система включает полнофункциональный модуль автоматизации входного контроля материалов на базе компьютерного зрения:

### 🚀 Быстрый доступ к OCR
- **URL**: http://127.0.0.1:8000/materials/incoming-control/
- **Демо-аккаунты**: 
  - Строительный контроль: `stroy_control_1` / `demo123`
  - Прораб: `foreman_1` / `demo123`
  - Инспектор: `inspector_1` / `demo123`

### 🎯 Основные возможности
- **Автоматическое распознавание** товарно-транспортных накладных (ТТН)
- **Поддержка документов**: ТТН, сертификаты качества, паспорта материалов
- **Drag & Drop интерфейс** для удобной загрузки
- **Визуальные индикаторы** качества распознавания
- **Ручное редактирование** распознанных данных
- **Демо-режим** при отсутствии Tesseract

### 📊 Система качества
- 🟢 **Высокая уверенность** (80%+)
- 🟡 **Средняя уверенность** (60-79%)
- 🔴 **Низкая уверенность** (<60%)

### 🛠️ Скрипты управления
```bash
# Запуск системы в фоновом режиме
./start_server.sh

# Проверка статуса
./check_status.sh

# Остановка системы
./stop_server.sh
```

## 🗂️ Структура проекта

```
# 🏗️ Urban Construction Control System

Система контроля городского строительства - комплексная веб-платформа для управления строительными проектами, контроля присутствия прорабов и анализа погодных условий.

## 📋 Оглавление

- [🔥 Основные возможности](#-основные-возможности)
- [🛠 Технологии](#-технологии)
- [📦 Быстрый старт](#-быстрый-старт)
- [🚀 Деплой в продакшен](#-деплой-в-продакшен)
- [⚙️ Конфигурация](#️-конфигурация)
- [📱 API документация](#-api-документация)
- [🔧 Разработка](#-разработка)
- [🐳 Docker](#-docker)
- [📊 Мониторинг](#-мониторинг)

## 🔥 Основные возможности

### 👥 Управление пользователями
- Многоуровневая система ролей (Администратор, Инспектор, Прораб)
- Регистрация и аутентификация
- Профили пользователей с детальной информацией

### 🏢 Управление проектами
- Создание и редактирование строительных проектов
- Привязка участников к проектам
- Отслеживание статуса и прогресса
- Геолокация объектов

### 📊 Dashboard и аналитика
- Интерактивные дашборды для разных ролей
- Статистика по проектам и участникам
- Графики и диаграммы в реальном времени
- Экспорт отчетов

### 🌤️ Погодная аналитика
- Детальный 14-дневный прогноз погоды
- Анализ рисков по типам строительных работ
- Рекомендации по проведению работ
- Интеграция с метеослужбами

### 📱 QR-код верификация
- Генерация динамических QR-кодов для прорабов
- Сканирование через веб-камеру
- Контроль присутствия на объектах
- История верификаций

### 📄 Документооборот
- Загрузка и хранение документов
- OCR для автоматического извлечения текста
- Система уведомлений
- Версионность документов

### 📈 Материалы и нарушения
- Учет строительных материалов
- Фиксация нарушений
- Система штрафов
- Отчетность по инцидентам

## 🛠 Технологии

### Backend
- **Django 5.2.6** - веб-фреймворк
- **Django REST Framework** - API
- **PostgreSQL** - основная база данных
- **SQLite** - база данных для разработки
- **Celery + Redis** - фоновые задачи (опционально)

### Frontend
- **HTML5/CSS3/JavaScript**
- **Tailwind CSS** - стилизация
- **Chart.js** - графики и диаграммы
- **html5-qrcode** - сканирование QR-кодов

### Инфраструктура
- **Docker** - контейнеризация
- **Docker Compose** - оркестрация
- **Gunicorn** - WSGI сервер
- **Nginx** - прокси-сервер
- **WhiteNoise** - статические файлы

### Дополнительные инструменты
- **Tesseract OCR** - распознавание текста
- **OpenCV** - обработка изображений
- **ReportLab** - генерация PDF
- **Pillow** - обработка изображений

## 📦 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd urban_construction_system
```

### 2. Настройка локальной разработки

```bash
# Автоматическая настройка
./scripts/dev_setup.sh

# Или ручная настройка:
cp .env.example .env
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Настройка базы данных

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Загрузка тестовых данных

```bash
python manage.py loaddata fixtures/all_data.json
```

### 5. Запуск сервера разработки

```bash
python manage.py runserver
```

Приложение будет доступно по адресу: http://127.0.0.1:8000/

## 🚀 Деплой в продакшен

### Подготовка к деплою

1. **Создайте production конфигурацию:**
```bash
cp .env.example .env.production
```

2. **Отредактируйте `.env.production`:**
```env
SECRET_KEY=your-super-secret-production-key
DEBUG=False
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@db:5432/urban_system
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Деплой с помощью Docker

```bash
# Автоматический деплой
./scripts/deploy.sh production

# Или пошагово:
docker-compose build
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
```

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|----------|
| `SECRET_KEY` | Секретный ключ Django | - |
| `DEBUG` | Режим отладки | `True` |
| `ENVIRONMENT` | Окружение | `development` |
| `DATABASE_URL` | URL базы данных | `sqlite:///db.sqlite3` |
| `ALLOWED_HOSTS` | Разрешенные хосты | `localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | Доверенные источники | - |
| `TESSERACT_CMD` | Путь к Tesseract | `/usr/local/bin/tesseract` |

## 🐳 Docker

### Development

```bash
# Запуск для разработки
docker-compose -f docker-compose.dev.yml up -d

# Просмотр логов
docker-compose -f docker-compose.dev.yml logs -f web

# Выполнение команд в контейнере
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate
```

### Production

```bash
# Запуск продакшен
docker-compose up -d

# Масштабирование
docker-compose up -d --scale web=3

# Мониторинг
docker-compose ps
docker-compose logs -f
```

## 🔧 Полезные команды

```bash
# Создание суперпользователя
python manage.py createsuperuser

# Сбор статических файлов
python manage.py collectstatic

# Экспорт данных
python scripts/export_data.py

# Просмотр логов Docker
docker-compose logs -f web

# Остановка всех сервисов
docker-compose down

# Выполнение миграций
python manage.py migrate

# Django shell
python manage.py shell
```
├── accounts/                 # Пользователи и аутентификация
├── projects/                # Объекты благоустройства
├── materials/              # Материалы и поставки
├── violations/             # Нарушения и их устранение
├── documents/              # Документооборот
├── static/                 # Статические файлы
│   ├── css/
│   └── js/
├── templates/              # HTML шаблоны
├── media/                  # Загруженные файлы
├── urban_control_system/   # Настройки проекта
└── requirements.txt        # Зависимости
```

## 🔧 Конфигурация

### Переменные окружения (.env)
```bash
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:password@localhost/urban_control_db

# Геопространственная база
GDAL_LIBRARY_PATH=/usr/lib/libgdal.so
GEOS_LIBRARY_PATH=/usr/lib/libgeos_c.so

# Redis для Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email настройки
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-password
```

### OCR настройки
```bash
# Установка Tesseract
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-rus

# macOS
brew install tesseract tesseract-lang

# Windows - скачать с официального сайта
```

## 🎨 Дизайн-система

Проект использует цветовую схему официальных цветов Москвы:

- **Moscow Blue** (#003366) - основной синий
- **Moscow Red** (#DC143C) - акцентный красный  
- **Moscow Gold** (#FFD700) - золотой для важных элементов
- **Moscow Green** (#228B22) - зеленый для успешных операций

## 📱 Мобильная версия

Система адаптирована для мобильных устройств и поддерживает:
- Responsive дизайн
- Touch-интерфейс
- Geolocation API
- Offline работу
- Push уведомления

## 🔐 Безопасность

- Django Security Middleware
- CSRF Protection
- XSS Protection  
- SQL Injection Protection
- Secure Headers
- Rate Limiting
- Permission-based access control

## 📊 Мониторинг и аналитика

- Дашборды для каждой роли пользователей
- Индикаторы срыва сроков
- Статистика по материалам и нарушениям
- Геоаналитика объектов
- Экспорт отчетов в Excel/PDF

## 🧪 Тестирование

```bash
# Запуск тестов
python manage.py test

# Покрытие кода
coverage run --source='.' manage.py test
coverage report
coverage html
```

## 🚀 Деплой в продакшн

### Docker
```bash
docker-compose up -d
```

### Systemd сервис
```bash
sudo cp deploy/urban_control.service /etc/systemd/system/
sudo systemctl enable urban_control
sudo systemctl start urban_control
```

### Nginx конфигурация
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /static/ {
        alias /path/to/urban_construction_system/staticfiles/;
    }
    
    location /media/ {
        alias /path/to/urban_construction_system/media/;
    }
}
```

## 📖 API Документация

API документация доступна по адресам:
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI Schema: `/api/schema/`

### Основные endpoints:

**Проекты:**
- `GET /api/projects/` - список объектов
- `POST /api/projects/` - создание объекта
- `GET /api/projects/{id}/` - детали объекта
- `PUT /api/projects/{id}/` - обновление объекта

**Материалы:**
- `GET /api/materials/` - список поставок
- `POST /api/materials/` - регистрация поставки
- `POST /api/materials/ocr/` - OCR обработка ТТН

**Нарушения:**
- `GET /api/violations/` - список нарушений
- `POST /api/violations/` - создание нарушения
- `POST /api/violations/{id}/resolve/` - устранение нарушения

## 👥 Команда разработки

Проект создан для хакатона "Лидеры цифровой трансформации 2025"

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей

## 🤝 Вклад в проект

1. Fork проекта
2. Создайте feature ветку (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в ветку (`git push origin feature/AmazingFeature`)
5. Открыть Pull Request

## 📞 Техническая поддержка

- Email: support@urban-control.moscow
- Telegram: @urban_control_support
- GitHub Issues: [ссылка на issues]

---

**Система управления благоустройством Москвы** - современное решение для эффективного контроля городских программ благоустройства 🏙️
