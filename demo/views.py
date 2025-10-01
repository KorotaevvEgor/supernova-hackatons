from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import pytesseract
from PIL import Image
import pdf2image
import io
import base64

@require_http_methods(["GET"])
def ocr_demo(request):
    """Отображение демо-страницы OCR API"""
    return render(request, 'demo/ocr_api_demo.html')

@csrf_exempt
@require_http_methods(["POST"])
def process_ocr(request):
    """API endpoint для обработки файлов через OCR"""
    try:
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'success': False, 'error': 'Файл не был загружен'})

        # Определяем тип файла
        content_type = file.content_type
        
        # Обработка изображений
        if content_type.startswith('image/'):
            image = Image.open(file)
            text = pytesseract.image_to_string(image, lang='rus')
        
        # Обработка PDF
        elif content_type == 'application/pdf':
            # Конвертируем первую страницу PDF в изображение
            pdf_bytes = file.read()
            pages = pdf2image.convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
            if pages:
                text = pytesseract.image_to_string(pages[0], lang='rus')
            else:
                return JsonResponse({'success': False, 'error': 'Не удалось обработать PDF файл'})
        else:
            return JsonResponse({'success': False, 'error': 'Неподдерживаемый тип файла'})

        # Очищаем и форматируем распознанный текст
        text = text.strip()
        if not text:
            return JsonResponse({'success': False, 'error': 'Не удалось распознать текст в файле'})

        return JsonResponse({
            'success': True,
            'text': text,
            'confidence': 0.95  # Можно добавить реальную оценку уверенности из Tesseract
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка при обработке файла: {str(e)}'
        })
