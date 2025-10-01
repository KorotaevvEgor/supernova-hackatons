"""
API views для системы входного контроля с OCR-обработкой ТТН
"""

import json
import logging
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from .models import MaterialDelivery, TransportDocument, DocumentPhoto, OCRResult
from .ocr_service import process_transport_document_photo, validate_extracted_data
from .export_utils import ttn_export_service
from projects.models import Project

logger = logging.getLogger(__name__)


class DocumentUploadAPIView(APIView):
    """
    API для загрузки фотографий ТТН и запуска OCR-обработки
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """
        Загрузить фотографию ТТН и запустить OCR-обработку
        """
        try:
            # Получаем параметры
            delivery_id = request.data.get('delivery_id')
            photo_type = request.data.get('photo_type', 'ttn_main')
            image_file = request.FILES.get('image')

            if not delivery_id:
                return Response({
                    'success': False,
                    'error': 'Не указан ID поставки материала'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not image_file:
                return Response({
                    'success': False,
                    'error': 'Не загружен файл документа'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем тип файла
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.pdf', '.bmp', '.tiff']
            file_extension = os.path.splitext(image_file.name)[1].lower() if image_file.name else ''
            
            if file_extension not in allowed_extensions:
                return Response({
                    'success': False,
                    'error': f'Неподдерживаемый формат файла. Поддерживаются: {", ".join(allowed_extensions)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Проверяем существование поставки
            try:
                delivery = MaterialDelivery.objects.get(id=delivery_id)
            except MaterialDelivery.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Поставка не найдена'
                }, status=status.HTTP_404_NOT_FOUND)

            # Создаем или получаем TransportDocument
            transport_doc, created = TransportDocument.objects.get_or_create(
                delivery=delivery,
                defaults={
                    'document_number': f'AUTO-{delivery.id}',
                    'document_date': delivery.delivery_date.date(),
                    'sender_name': delivery.supplier,
                    'receiver_name': delivery.project.name,
                    'cargo_description': f'{delivery.material_type.name} - {delivery.quantity} {delivery.material_type.unit}',
                    'vehicle_number': '',
                    'driver_name': '',
                    'processing_status': 'uploaded'
                }
            )

            # Создаем запись о фотографии документа
            document_photo = DocumentPhoto.objects.create(
                transport_document=transport_doc,
                photo_type=photo_type,
                image=image_file,
                processing_status='uploaded',
                uploaded_by=request.user
            )

            # Запускаем OCR-обработку
            try:
                ocr_result = process_transport_document_photo(document_photo.id)
                
                return Response({
                    'success': True,
                    'message': 'Документ успешно загружен и обработан',
                    'data': {
                        'document_photo_id': document_photo.id,
                        'transport_document_id': transport_doc.id,
                        'ocr_result': ocr_result
                    }
                }, status=status.HTTP_201_CREATED)

            except Exception as ocr_error:
                logger.error(f"Ошибка OCR для фото {document_photo.id}: {str(ocr_error)}")
                
                # Обновляем статус на ошибку
                document_photo.processing_status = 'error'
                document_photo.processing_error = str(ocr_error)
                document_photo.save()
                
                return Response({
                    'success': True,
                    'message': 'Документ загружен, но произошла ошибка при обработке',
                    'data': {
                        'document_photo_id': document_photo.id,
                        'transport_document_id': transport_doc.id,
                        'error': str(ocr_error)
                    }
                }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Ошибка при загрузке документа: {str(e)}")
            return Response({
                'success': False,
                'error': f'Внутренняя ошибка сервера: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessDocumentAPIView(APIView):
    """
    API для повторной обработки документа через OCR
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, photo_id):
        """
        Повторно обработать фотографию документа через OCR
        """
        try:
            document_photo = get_object_or_404(DocumentPhoto, id=photo_id)
            
            # Проверяем права доступа
            if not request.user.is_staff and document_photo.uploaded_by != request.user:
                return Response({
                    'success': False,
                    'error': 'Нет прав для обработки данного документа'
                }, status=status.HTTP_403_FORBIDDEN)

            # Запускаем обработку
            ocr_result = process_transport_document_photo(photo_id)
            
            return Response({
                'success': True,
                'message': 'Документ успешно обработан',
                'data': ocr_result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при обработке документа {photo_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidateExtractedDataAPIView(APIView):
    """
    API для валидации извлеченных OCR данных
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, ocr_result_id):
        """
        Валидировать извлеченные данные OCR
        """
        try:
            # Запускаем валидацию
            validation_result = validate_extracted_data(ocr_result_id)
            
            return Response({
                'success': True,
                'message': 'Валидация завершена',
                'data': validation_result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при валидации OCR результата {ocr_result_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateExtractedDataAPIView(APIView):
    """
    API для ручного редактирования извлеченных данных
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, ocr_result_id):
        """
        Обновить извлеченные данные вручную
        """
        try:
            ocr_result = get_object_or_404(OCRResult, id=ocr_result_id)
            updated_fields = request.data.get('extracted_fields', {})
            
            if not updated_fields:
                return Response({
                    'success': False,
                    'error': 'Не переданы данные для обновления'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Обновляем извлеченные поля
            ocr_result.extracted_fields.update(updated_fields)
            ocr_result.validation_status = 'pending'  # Требуется повторная валидация
            ocr_result.validated_by = request.user
            ocr_result.save()

            # Обновляем связанный TransportDocument
            transport_doc = ocr_result.document_photo.transport_document
            
            field_mapping = {
                'document_number': 'document_number',
                'document_date': 'document_date',
                'sender_name': 'sender_name',
                'receiver_name': 'receiver_name',
                'vehicle_number': 'vehicle_number',
                'driver_name': 'driver_name',
                'cargo_description': 'cargo_description',
                'cargo_weight': 'cargo_weight',
            }

            for ocr_field, model_field in field_mapping.items():
                if ocr_field in updated_fields:
                    value = updated_fields[ocr_field]
                    
                    # Специальная обработка для типов данных
                    if model_field == 'document_date' and isinstance(value, str):
                        from datetime import datetime
                        try:
                            value = datetime.strptime(value, '%Y-%m-%d').date()
                        except ValueError:
                            continue
                    elif model_field == 'cargo_weight' and value:
                        from decimal import Decimal
                        try:
                            value = Decimal(str(value))
                        except (ValueError, TypeError):
                            continue
                    
                    setattr(transport_doc, model_field, value)

            transport_doc.processing_status = 'verified'
            transport_doc.manual_verification_required = False
            transport_doc.processed_by = request.user
            transport_doc.save()

            return Response({
                'success': True,
                'message': 'Данные успешно обновлены',
                'data': {
                    'extracted_fields': ocr_result.extracted_fields,
                    'transport_document_id': transport_doc.id
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при обновлении данных OCR {ocr_result_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentStatusAPIView(APIView):
    """
    API для получения статуса обработки документа
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, photo_id):
        """
        Получить статус обработки документа
        """
        try:
            document_photo = get_object_or_404(DocumentPhoto, id=photo_id)
            
            # Получаем OCR результат, если есть
            ocr_result = None
            if hasattr(document_photo, 'ocr_result'):
                ocr_result = {
                    'id': document_photo.ocr_result.id,
                    'extracted_fields': document_photo.ocr_result.extracted_fields,
                    'overall_confidence': document_photo.ocr_result.overall_confidence,
                    'validation_status': document_photo.ocr_result.validation_status,
                    'validation_errors': document_photo.ocr_result.validation_errors
                }

            response_data = {
                'document_photo': {
                    'id': document_photo.id,
                    'photo_type': document_photo.photo_type,
                    'processing_status': document_photo.processing_status,
                    'processing_error': document_photo.processing_error,
                    'ocr_confidence': document_photo.ocr_confidence,
                    'uploaded_at': document_photo.uploaded_at,
                    'processed_at': document_photo.processed_at,
                    'image_url': document_photo.image.url if document_photo.image else None
                },
                'transport_document': {
                    'id': document_photo.transport_document.id,
                    'processing_status': document_photo.transport_document.processing_status,
                    'manual_verification_required': document_photo.transport_document.manual_verification_required,
                    'ocr_confidence': document_photo.transport_document.ocr_confidence
                },
                'ocr_result': ocr_result
            }

            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при получении статуса документа {photo_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeliveryDocumentsAPIView(APIView):
    """
    API для получения списка документов поставки
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, delivery_id):
        """
        Получить список документов для конкретной поставки
        """
        try:
            delivery = get_object_or_404(MaterialDelivery, id=delivery_id)
            
            # Проверяем права доступа
            if not request.user.is_staff and delivery.received_by != request.user:
                return Response({
                    'success': False,
                    'error': 'Нет прав для просмотра документов данной поставки'
                }, status=status.HTTP_403_FORBIDDEN)

            documents = []
            
            # Получаем TransportDocument если есть
            if hasattr(delivery, 'transport_document'):
                transport_doc = delivery.transport_document
                
                # Получаем все фотографии документов
                photos = DocumentPhoto.objects.filter(transport_document=transport_doc)
                
                for photo in photos:
                    ocr_result = None
                    if hasattr(photo, 'ocr_result'):
                        ocr_result = {
                            'id': photo.ocr_result.id,
                            'extracted_fields': photo.ocr_result.extracted_fields,
                            'overall_confidence': photo.ocr_result.overall_confidence,
                            'validation_status': photo.ocr_result.validation_status
                        }
                    
                    documents.append({
                        'id': photo.id,
                        'photo_type': photo.photo_type,
                        'photo_type_display': photo.get_photo_type_display(),
                        'processing_status': photo.processing_status,
                        'processing_status_display': photo.get_processing_status_display(),
                        'ocr_confidence': photo.ocr_confidence,
                        'uploaded_at': photo.uploaded_at,
                        'processed_at': photo.processed_at,
                        'image_url': photo.image.url if photo.image else None,
                        'ocr_result': ocr_result
                    })

            response_data = {
                'delivery': {
                    'id': delivery.id,
                    'material_type': delivery.material_type.name,
                    'quantity': float(delivery.quantity),
                    'supplier': delivery.supplier,
                    'delivery_date': delivery.delivery_date,
                    'status': delivery.status
                },
                'transport_document': {
                    'id': delivery.transport_document.id if hasattr(delivery, 'transport_document') else None,
                    'processing_status': delivery.transport_document.processing_status if hasattr(delivery, 'transport_document') else None,
                    'manual_verification_required': delivery.transport_document.manual_verification_required if hasattr(delivery, 'transport_document') else None
                },
                'documents': documents
            }

            return Response({
                'success': True,
                'data': response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при получении документов поставки {delivery_id}: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_deliveries_for_ocr(request, project_id):
    """
    Получить список поставок проекта для системы входного контроля
    """
    try:
        project = get_object_or_404(Project, id=project_id)
        
        # Получаем поставки материалов для проекта
        deliveries = MaterialDelivery.objects.filter(
            project=project
        ).select_related('material_type').prefetch_related('transport_document__photos')
        
        deliveries_data = []
        for delivery in deliveries:
            # Считаем количество загруженных документов
            documents_count = 0
            processing_status = None
            requires_manual_check = False
            
            if hasattr(delivery, 'transport_document'):
                documents_count = delivery.transport_document.photos.count()
                processing_status = delivery.transport_document.processing_status
                requires_manual_check = delivery.transport_document.manual_verification_required
            
            deliveries_data.append({
                'id': delivery.id,
                'material_type': {
                    'name': delivery.material_type.name,
                    'code': delivery.material_type.code,
                    'unit': delivery.material_type.unit
                },
                'quantity': float(delivery.quantity),
                'supplier': delivery.supplier,
                'delivery_date': delivery.delivery_date,
                'status': delivery.status,
                'status_display': delivery.get_status_display(),
                'documents_count': documents_count,
                'processing_status': processing_status,
                'requires_manual_check': requires_manual_check,
                'has_transport_document': hasattr(delivery, 'transport_document')
            })
        
        return Response({
            'success': True,
            'data': {
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'address': project.address
                },
                'deliveries': deliveries_data
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Ошибка при получении поставок проекта {project_id}: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Legacy поддержка для простых HTTP запросов
class ExportTTNDataAPIView(APIView):
    """
    API для экспорта данных ТТН в различные форматы
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format_type='csv'):
        """
        Экспорт данных ТТН в указанном формате
        
        Параметры:
        - format_type: csv, excel, summary
        - project_id: ID проекта (опционально)
        - include_ocr_details: включать детали OCR (по умолчанию false)
        - date_from, date_to: фильтр по датам
        """
        try:
            # Получаем параметры фильтрации
            project_id = request.GET.get('project_id')
            include_ocr_details = request.GET.get('include_ocr_details', 'false').lower() == 'true'
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            
            # Базовый queryset
            queryset = TransportDocument.objects.select_related(
                'delivery__project', 'delivery__material_type'
            ).prefetch_related('photos__ocr_result')
            
            # Применяем фильтры
            if project_id:
                try:
                    project = Project.objects.get(id=project_id)
                    # Проверяем права доступа
                    if not request.user.is_staff and not project.is_user_member(request.user):
                        return Response({
                            'success': False,
                            'error': 'Нет прав доступа к данному проекту'
                        }, status=status.HTTP_403_FORBIDDEN)
                    
                    queryset = queryset.filter(delivery__project=project)
                except Project.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Проект не найден'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            if date_from:
                try:
                    from datetime import datetime
                    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                    queryset = queryset.filter(document_date__gte=date_from_obj)
                except ValueError:
                    return Response({
                        'success': False,
                        'error': 'Неверный формат даты date_from (ожидается YYYY-MM-DD)'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            if date_to:
                try:
                    from datetime import datetime
                    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                    queryset = queryset.filter(document_date__lte=date_to_obj)
                except ValueError:
                    return Response({
                        'success': False,
                        'error': 'Неверный формат даты date_to (ожидается YYYY-MM-DD)'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем, есть ли данные для экспорта
            if not queryset.exists():
                return Response({
                    'success': False,
                    'error': 'Нет данных для экспорта с указанными фильтрами'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Выбираем формат экспорта
            try:
                if format_type == 'csv':
                    return ttn_export_service.export_to_csv(queryset, include_ocr_details)
                elif format_type == 'excel':
                    return ttn_export_service.export_to_excel(queryset, include_ocr_details)
                elif format_type == 'summary':
                    return ttn_export_service.export_summary_to_excel(queryset)
                else:
                    return Response({
                        'success': False,
                        'error': f'Неподдерживаемый формат экспорта: {format_type}. Доступны: csv, excel, summary'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except ValueError as ve:
                logger.error(f"Ошибка экспорта {format_type}: {str(ve)}")
                return Response({
                    'success': False,
                    'error': str(ve)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Ошибка при экспорте данных ТТН: {str(e)}")
            return Response({
                'success': False,
                'error': f'Внутренняя ошибка сервера: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BulkProcessDocumentsAPIView(APIView):
    """
    API для массовой обработки документов
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Массовая обработка неотработанных документов
        """
        try:
            project_id = request.data.get('project_id')
            max_documents = int(request.data.get('max_documents', 50))  # Ограничение
            
            if max_documents > 100:
                return Response({
                    'success': False,
                    'error': 'Максимальное количество документов для массовой обработки: 100'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Фильтруем документы для обработки
            photos_queryset = DocumentPhoto.objects.filter(
                processing_status='uploaded'
            )
            
            if project_id:
                try:
                    project = Project.objects.get(id=project_id)
                    if not request.user.is_staff and not project.is_user_member(request.user):
                        return Response({
                            'success': False,
                            'error': 'Нет прав доступа к данному проекту'
                        }, status=status.HTTP_403_FORBIDDEN)
                    
                    photos_queryset = photos_queryset.filter(
                        transport_document__delivery__project=project
                    )
                except Project.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Проект не найден'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            # Ограничиваем количество
            photos_to_process = photos_queryset[:max_documents]
            
            if not photos_to_process:
                return Response({
                    'success': True,
                    'message': 'Нет документов для обработки',
                    'data': {
                        'processed_count': 0,
                        'failed_count': 0,
                        'results': []
                    }
                }, status=status.HTTP_200_OK)
            
            # Обрабатываем документы
            results = []
            processed_count = 0
            failed_count = 0
            
            for photo in photos_to_process:
                try:
                    result = process_transport_document_photo(photo.id)
                    if result.get('success', False):
                        processed_count += 1
                    else:
                        failed_count += 1
                    
                    results.append({
                        'photo_id': photo.id,
                        'transport_document_id': photo.transport_document.id,
                        'success': result.get('success', False),
                        'error': result.get('error') if not result.get('success') else None,
                        'confidence': result.get('confidence', 0)
                    })
                    
                except Exception as processing_error:
                    failed_count += 1
                    results.append({
                        'photo_id': photo.id,
                        'transport_document_id': photo.transport_document.id,
                        'success': False,
                        'error': str(processing_error),
                        'confidence': 0
                    })
            
            return Response({
                'success': True,
                'message': f'Массовая обработка завершена: {processed_count} успешно, {failed_count} ошибок',
                'data': {
                    'processed_count': processed_count,
                    'failed_count': failed_count,
                    'total_documents': len(results),
                    'results': results
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Ошибка при массовой обработке документов: {str(e)}")
            return Response({
                'success': False,
                'error': f'Внутренняя ошибка сервера: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def upload_document_legacy(request):
    """
    Legacy endpoint для загрузки документов (поддержка старых клиентов)
    """
    try:
        if request.content_type.startswith('multipart/form-data'):
            delivery_id = request.POST.get('delivery_id')
            photo_type = request.POST.get('photo_type', 'ttn_main')
            image_file = request.FILES.get('image')
        else:
            data = json.loads(request.body)
            delivery_id = data.get('delivery_id')
            photo_type = data.get('photo_type', 'ttn_main')
            image_file = None

        if not delivery_id or not image_file:
            return JsonResponse({
                'success': False,
                'error': 'Недостаточно параметров'
            }, status=400)

        # Создаем представление API и передаем ему запрос
        api_view = DocumentUploadAPIView()
        api_view.request = request
        
        # Имитируем данные для API
        request.data = {
            'delivery_id': delivery_id,
            'photo_type': photo_type
        }
        request.FILES = {'image': image_file}
        
        response = api_view.post(request)
        
        return JsonResponse(response.data, status=response.status_code)

    except Exception as e:
        logger.error(f"Ошибка в legacy endpoint: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
