# Система OCR для ТТН с поддержкой PDF

## Новые возможности ✨

- **Поддержка PDF файлов** - автоматическое распознавание ТТН из PDF документов (до 5 страниц)
- **Табличный экспорт** - экспорт распознанных данных в CSV и Excel форматы
- **Массовая обработка** - пакетная обработка неотработанных документов
- **Улучшенный API** - новые endpoints для экспорта и управления документами

## Быстрый старт 🚀

### 1. Установите зависимости

```bash
# Установка PDF библиотек
pip install PyMuPDF==1.23.30 pdf2image==1.17.0

# Для экспорта в Excel (уже установлены)
pip install pandas==2.3.2 openpyxl==3.1.5
```

### 2. Примените миграции

```bash
cd /path/to/your/project
python manage.py migrate materials
```

### 3. Загрузите PDF документ

```python
import requests

# Загрузка PDF файла
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/materials/ttn/upload/',
        files={'image': f},
        data={'delivery_id': 123},
        headers={'Authorization': 'Bearer YOUR_TOKEN'}
    )

print(response.json())
```

### 4. Экспортируйте данные

```bash
# Экспорт в CSV
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/materials/ttn/export/csv/"

# Экспорт в Excel со сводкой
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/materials/ttn/export/summary/" \
  -o ttn_summary.xlsx
```

## Что было добавлено 📝

### Файлы

- `ocr_service.py` - добавлена поддержка PDF (методы `_extract_text_from_pdf`, `_preprocess_image_from_pil`)
- `export_utils.py` - новый сервис для экспорта данных в табличные форматы
- `ocr_api_views.py` - новые API классы `ExportTTNDataAPIView`, `BulkProcessDocumentsAPIView`
- `models.py` - модель `DocumentPhoto` расширена полями `file_type`, `pages_count`
- `requirements.txt` - добавлены зависимости PyMuPDF и pdf2image
- `api_urls.py` - новые маршруты для экспорта и массовой обработки

### API endpoints

- `POST /api/materials/ttn/upload/` - теперь поддерживает PDF файлы
- `GET /api/materials/ttn/export/{format_type}/` - экспорт данных (csv, excel, summary)
- `POST /api/materials/ttn/bulk-process/` - массовая обработка документов

### Функции экспорта

- **CSV экспорт** - стандартный формат с поддержкой кириллицы
- **Excel экспорт** - форматированные таблицы с автоматической настройкой ширины колонок
- **Сводные отчеты** - статистика по обработке ТТН с детальными данными

## Использование 💡

### Загрузка PDF файла

```javascript
const formData = new FormData();
formData.append('image', pdfFile); // PDF файл
formData.append('delivery_id', deliveryId);

fetch('/api/materials/ttn/upload/', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer ' + token
    },
    body: formData
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        console.log('PDF обработан:', data.data.ocr_result);
        console.log('Уверенность:', data.data.ocr_result.confidence + '%');
    }
});
```

### Массовая обработка

```python
# Обработка всех неотработанных документов проекта
response = requests.post(
    'http://localhost:8000/api/materials/ttn/bulk-process/',
    json={'project_id': 123, 'max_documents': 50},
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

result = response.json()
print(f"Обработано: {result['data']['processed_count']}")
print(f"Ошибок: {result['data']['failed_count']}")
```

### Экспорт с фильтрами

```python
# Экспорт с фильтрацией по дате
params = {
    'project_id': 123,
    'date_from': '2024-01-01',
    'date_to': '2024-12-31',
    'include_ocr_details': True
}

response = requests.get(
    'http://localhost:8000/api/materials/ttn/export/excel/',
    params=params,
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

with open('filtered_export.xlsx', 'wb') as f:
    f.write(response.content)
```

## Особенности PDF обработки 📄

### Что обрабатывается:
- PDF файлы до 5 страниц
- Разрешение конвертации: 200 DPI
- Поддерживается русский и английский текст
- Автоматическая предобработка для улучшения качества

### Ограничения:
- Максимум 5 страниц на документ
- PDF должен содержать текстовую или графическую информацию
- Защищенные паролем PDF не поддерживаются

## Мониторинг качества 📊

Система автоматически оценивает качество распознавания:

- **Высокое качество (>80%)** ✅ - данные автоматически приняты
- **Среднее качество (60-80%)** ⚠️ - рекомендуется проверка
- **Низкое качество (<60%)** ❌ - требуется ручная корректировка

## Структура экспортируемых данных 📋

### Основные поля ТТН:
- Номер и дата документа
- Отправитель и получатель (с ИНН)
- Транспортная информация (номер ТС, водитель)
- Данные о грузе (описание, вес, объем)
- Статусы обработки и уверенность OCR

### Дополнительные поля (при `include_ocr_details=true`):
- Детализированные результаты OCR
- Уверенность по каждому полю
- Ошибки валидации
- Координаты найденного текста

## Устранение проблем 🔧

### PDF не обрабатывается
1. Убедитесь, что установлены зависимости PyMuPDF и pdf2image
2. Проверьте размер файла (не более 10 МБ)
3. Убедитесь, что PDF не защищен паролем

### Низкое качество распознавания
1. Используйте PDF с высоким разрешением
2. Убедитесь, что текст не размыт
3. Проверьте правильность сканирования (прямое изображение)

### Ошибки экспорта
1. Проверьте наличие данных для экспорта
2. Убедитесь в корректности параметров фильтрации
3. Для Excel экспорта нужны pandas и openpyxl

## Поддержка 💬

Для получения помощи обратитесь к:
- [API документации](./API_DOCUMENTATION.md) - полная документация по API
- Логам Django - детальная информация об ошибках
- Панели администратора - мониторинг OCR результатов