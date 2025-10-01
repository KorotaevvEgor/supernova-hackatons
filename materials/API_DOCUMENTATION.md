# API Документация: Система OCR для ТТН с поддержкой PDF

## Обзор

Система поддерживает автоматическое распознавание товарно-транспортных накладных (ТТН) как из изображений, так и из PDF файлов, с возможностью экспорта данных в табличные форматы.

## Поддерживаемые форматы файлов

- **Изображения**: JPG, JPEG, PNG, BMP, TIFF
- **Документы**: PDF (до 5 страниц)

## Основные API endpoints

### 1. Загрузка документов ТТН

#### POST `/api/materials/ttn/upload/`

Загружает файл ТТН (изображение или PDF) и запускает OCR обработку.

**Параметры:**
- `delivery_id` (int) - ID поставки материала
- `photo_type` (string, опционально) - Тип документа (по умолчанию: 'ttn_main')
- `image` (file) - Файл документа

**Типы документов:**
- `ttn_main` - Основная страница ТТН
- `ttn_additional` - Дополнительная страница ТТН  
- `quality_certificate` - Сертификат качества
- `passport_material` - Паспорт материала
- `invoice` - Счет-фактура
- `other` - Другой документ

**Пример запроса:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "delivery_id=123" \
  -F "photo_type=ttn_main" \
  -F "image=@document.pdf" \
  http://localhost:8000/api/materials/ttn/upload/
```

**Ответ:**
```json
{
  "success": true,
  "message": "Документ успешно загружен и обработан",
  "data": {
    "document_photo_id": 456,
    "transport_document_id": 789,
    "ocr_result": {
      "success": true,
      "extracted_fields": {
        "document_number": "ТТН-2024-001234",
        "document_date": "2024-09-15",
        "sender_name": "ООО \"СтройМатериалы Плюс\"",
        "vehicle_number": "А123БВ777"
      },
      "confidence": 85.5,
      "requires_manual_check": false
    }
  }
}
```

### 2. Получение статуса обработки

#### GET `/api/materials/ttn/photos/{photo_id}/status/`

Получает статус обработки загруженного документа.

**Ответ:**
```json
{
  "success": true,
  "data": {
    "document_photo": {
      "id": 456,
      "photo_type": "ttn_main",
      "processing_status": "processed",
      "file_type": "pdf",
      "pages_count": 2,
      "ocr_confidence": 85.5
    },
    "transport_document": {
      "id": 789,
      "processing_status": "processed",
      "manual_verification_required": false
    },
    "ocr_result": {
      "extracted_fields": {...},
      "validation_status": "valid"
    }
  }
}
```

### 3. Экспорт данных ТТН

#### GET `/api/materials/ttn/export/{format_type}/`

Экспортирует данные ТТН в различные форматы.

**Форматы экспорта:**
- `csv` - CSV файл
- `excel` - Excel файл (.xlsx)
- `summary` - Сводный отчет в Excel

**Параметры фильтрации:**
- `project_id` (int, опционально) - ID проекта
- `include_ocr_details` (bool, опционально) - Включать детали OCR (по умолчанию: false)
- `date_from` (string, опционально) - Дата начала (формат: YYYY-MM-DD)
- `date_to` (string, опционально) - Дата окончания (формат: YYYY-MM-DD)

**Примеры запросов:**

```bash
# Экспорт в CSV
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/materials/ttn/export/csv/?project_id=123"

# Экспорт в Excel с деталями OCR
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/materials/ttn/export/excel/?include_ocr_details=true&date_from=2024-01-01"

# Сводный отчет
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/materials/ttn/export/summary/"
```

### 4. Массовая обработка документов

#### POST `/api/materials/ttn/bulk-process/`

Запускает массовую OCR обработку неотработанных документов.

**Параметры:**
- `project_id` (int, опционально) - ID проекта для фильтрации
- `max_documents` (int, опционально) - Максимальное количество документов (по умолчанию: 50, максимум: 100)

**Пример запроса:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 123, "max_documents": 20}' \
  http://localhost:8000/api/materials/ttn/bulk-process/
```

**Ответ:**
```json
{
  "success": true,
  "message": "Массовая обработка завершена: 18 успешно, 2 ошибок",
  "data": {
    "processed_count": 18,
    "failed_count": 2,
    "total_documents": 20,
    "results": [
      {
        "photo_id": 456,
        "transport_document_id": 789,
        "success": true,
        "confidence": 85.5
      }
    ]
  }
}
```

### 5. Редактирование извлеченных данных

#### PUT `/api/materials/ttn/ocr-results/{ocr_result_id}/update/`

Позволяет вручную исправить данные, извлеченные OCR.

**Параметры:**
- `extracted_fields` (object) - Обновленные поля

**Пример запроса:**
```bash
curl -X PUT \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "extracted_fields": {
      "document_number": "ТТН-2024-001234-ИСПРАВЛЕНО",
      "vehicle_number": "А123БВ777",
      "cargo_weight": "1500.00"
    }
  }' \
  http://localhost:8000/api/materials/ttn/ocr-results/123/update/
```

## Структура извлекаемых данных

OCR система извлекает следующие поля из документов ТТН:

- `document_number` - Номер ТТН
- `document_date` - Дата ТТН
- `sender_name` - Наименование отправителя
- `sender_inn` - ИНН отправителя
- `receiver_name` - Наименование получателя
- `receiver_inn` - ИНН получателя
- `vehicle_number` - Номер транспортного средства
- `driver_name` - ФИО водителя
- `cargo_description` - Описание груза
- `cargo_weight` - Вес груза (кг)
- `cargo_volume` - Объем груза (м³)
- `packages_count` - Количество мест

## Статусы обработки

### Статусы документов (DocumentPhoto):
- `uploaded` - Загружено
- `processing` - Обрабатывается
- `processed` - Обработано
- `error` - Ошибка обработки

### Статусы ТТН (TransportDocument):
- `uploaded` - Загружено
- `processing` - Обрабатывается
- `processed` - Обработано
- `verified` - Проверено
- `error` - Ошибка обработки

### Статусы валидации OCR:
- `pending` - Ожидает проверки
- `valid` - Данные корректны
- `invalid` - Данные некорректны
- `partial` - Частично корректны

## Качество распознавания

Система автоматически оценивает качество распознавания:

- **Высокая уверенность (>80%)** - Автоматическое принятие данных
- **Средняя уверенность (60-80%)** - Данные приняты, но рекомендуется проверка
- **Низкая уверенность (40-60%)** - Требуется ручная проверка
- **Очень низкая уверенность (<40%)** - Обязательна ручная проверка

## Обработка PDF файлов

Для PDF документов:

1. Каждая страница конвертируется в изображение (DPI: 200)
2. Применяется предварительная обработка для улучшения качества
3. Текст извлекается со всех страниц
4. Результаты объединяются с указанием номера страницы
5. Ограничение: максимум 5 страниц на документ

## Коды ошибок

- `400` - Неверные параметры запроса
- `401` - Не авторизован
- `403` - Нет прав доступа
- `404` - Ресурс не найден
- `500` - Внутренняя ошибка сервера

## Требования для установки

Для работы с PDF файлами необходимо установить дополнительные зависимости:

```bash
pip install PyMuPDF==1.23.30 pdf2image==1.17.0
```

Для экспорта в Excel:
```bash
pip install pandas==2.3.2 openpyxl==3.1.5
```

## Примеры использования

### Python (requests)

```python
import requests

# Загрузка PDF файла
with open('document.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/materials/ttn/upload/',
        files={'image': f},
        data={'delivery_id': 123, 'photo_type': 'ttn_main'},
        headers={'Authorization': 'Bearer YOUR_TOKEN'}
    )

result = response.json()
print(f"Результат: {result}")

# Экспорт в Excel
response = requests.get(
    'http://localhost:8000/api/materials/ttn/export/excel/',
    params={'project_id': 123, 'include_ocr_details': True},
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

with open('export.xlsx', 'wb') as f:
    f.write(response.content)
```

### JavaScript (Fetch API)

```javascript
// Загрузка файла
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('delivery_id', 123);
formData.append('photo_type', 'ttn_main');

fetch('/api/materials/ttn/upload/', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
    },
    body: formData
})
.then(response => response.json())
.then(data => console.log(data));

// Экспорт данных
fetch('/api/materials/ttn/export/csv/?project_id=123', {
    headers: {
        'Authorization': 'Bearer YOUR_TOKEN'
    }
})
.then(response => response.blob())
.then(blob => {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ttn_export.csv';
    a.click();
});
```