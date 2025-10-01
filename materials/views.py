from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.paginator import Paginator
import pytesseract
import re
import io
import json
import logging
from PIL import Image
from .models import MaterialDelivery, MaterialType, TransportDocument, DocumentPhoto, OCRResult
from .ocr_service import process_transport_document_photo, ttn_ocr_service
from projects.models import Project, Work

logger = logging.getLogger(__name__)

# API Views
def material_list_api(request):
    return JsonResponse({'message': 'Materials API endpoint'})

@method_decorator(csrf_exempt, name='dispatch')
class MaterialDeliveryListCreateAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """
        Возвращаем права доступа в зависимости от метода.
        GET запросы могут выполняться без аутентификации.
        """
        if self.request.method == 'GET':
            return []  # Не требуем аутентификации для GET
        return [permission() for permission in self.permission_classes]
    
    def get(self, request):
        deliveries = MaterialDelivery.objects.select_related('project','material_type').order_by('-delivery_date')[:100]
        data = []
        for d in deliveries:
            data.append({
                'id': d.id,
                'project': d.project.name,
                'material_type': d.material_type.name,
                'quantity': str(d.quantity),
                'unit': d.material_type.unit,
                'status': d.status,
                'supplier': d.supplier,
                'delivery_date': d.delivery_date,
                'ttn_number': d.ttn_number,
            })
        return Response({'results': data})

    def post(self, request):
        try:
            # Получаем данные из запроса
            project_id = request.data.get('project_id')
            material_type_id = request.data.get('material_type_id')  # Изменено на material_type_id
            quantity = request.data.get('quantity')
            supplier = request.data.get('supplier', '')
            ttn_number = request.data.get('ttn_number', '')
            delivery_date = request.data.get('delivery_date')
            
            # Проверяем обязательные поля
            if not all([project_id, material_type_id, quantity, supplier]):
                return Response({
                    'detail': 'project_id, material_type_id, quantity, supplier обязательны'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем объекты
            project = Project.objects.get(pk=project_id)
            material_type = MaterialType.objects.get(pk=material_type_id)
            
            # Проверяем, что проект принадлежит прорабу (если это прораб)
            if (hasattr(request.user, 'user_type') and 
                request.user.user_type == 'foreman' and 
                project.foreman != request.user):
                return Response({
                    'detail': 'У вас нет доступа к этому проекту'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Парсим дату поставки
            from django.utils.dateparse import parse_datetime
            parsed_delivery_date = timezone.now()
            if delivery_date:
                try:
                    parsed_delivery_date = parse_datetime(delivery_date)
                    if not parsed_delivery_date:
                        # Пробуем ISO формат
                        from datetime import datetime
                        parsed_delivery_date = datetime.fromisoformat(delivery_date.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    parsed_delivery_date = timezone.now()
            
            # Создаем поставку
            delivery = MaterialDelivery.objects.create(
                project=project,
                material_type=material_type,
                supplier=supplier,
                quantity=float(quantity),
                delivery_date=parsed_delivery_date,
                status='delivered',  # По умолчанию ставим 'доставлено'
                ttn_number=ttn_number or f'TTN-{timezone.now().strftime("%Y%m%d-%H%M%S")}',
                received_by=request.user,
                manual_entry=True,
            )
            
            # Привязка к строке спецификации, если передана
            spec_row_id = request.data.get('spec_row_id')
            if spec_row_id:
                from projects.models import WorkSpecRow
                try:
                    spec_row = WorkSpecRow.objects.get(pk=spec_row_id, project=project)
                    delivery.spec_row = spec_row
                    delivery.save()
                except WorkSpecRow.DoesNotExist:
                    pass
            
            return Response({
                'status': 'ok', 
                'delivery_id': delivery.id,
                'message': 'Поставка успешно создана'
            })
            
        except Project.DoesNotExist:
            return Response({
                'detail': 'Проект не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        except MaterialType.DoesNotExist:
            return Response({
                'detail': 'Тип материала не найден'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({
                'detail': f'Некорректные данные: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'Error creating material delivery: {str(e)}')
            return Response({
                'detail': 'Ошибка при создании поставки'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MaterialLinkSpecAPI(APIView):
    permission_classes = [IsAuthenticated]
    def patch(self, request, pk):
        from projects.models import WorkSpecRow
        try:
            delivery = MaterialDelivery.objects.get(pk=pk)
        except MaterialDelivery.DoesNotExist:
            return Response({'detail': 'Поставка не найдена'}, status=status.HTTP_404_NOT_FOUND)
        spec_row_id = request.data.get('spec_row_id')
        if not spec_row_id:
            return Response({'detail': 'spec_row_id обязателен'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            spec_row = WorkSpecRow.objects.get(pk=spec_row_id, project=delivery.project)
        except WorkSpecRow.DoesNotExist:
            return Response({'detail': 'Строка спецификации не найдена для проекта'}, status=status.HTTP_404_NOT_FOUND)
        delivery.spec_row = spec_row
        delivery.save()
        return Response({'status': 'ok'})

# ========== НОВЫЕ API ДЛЯ РАБОТЫ С ТТН И OCR ==========

class TTNUploadAPI(APIView):
    """АPI для загрузки документов ТТН и их OCR обработки"""
    permission_classes = []  # Временно отключено для тестирования
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Загрузить ТТН документ и создать запись для OCR обработки"""
        try:
            # Проверяем наличие проекта
            project_id = request.data.get('project_id')
            if not project_id:
                return Response({
                    'success': False, 
                    'error': 'Необходимо указать project_id'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            project = get_object_or_404(Project, id=project_id)
            
            # Проверяем наличие файла
            uploaded_file = request.FILES.get('document')
            if not uploaded_file:
                return Response({
                    'success': False,
                    'error': 'Необходимо загрузить файл документа'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Получаем или создаем базовый тип материала
            default_material_type, created = MaterialType.objects.get_or_create(
                code='UNKNOWN',
                defaults={
                    'name': 'Неопределенный материал (Обрабатывается OCR)',
                    'unit': 'шт.',
                    'description': 'Временный тип материала для OCR обработки'
                }
            )
            
            # Получаем пользователя или создаем фиктивного для теста
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = getattr(request, 'user', None)
            if not user or user.is_anonymous:
                user, created = User.objects.get_or_create(
                    username='test_ocr_user',
                    defaults={'first_name': 'Test', 'last_name': 'OCR User', 'email': 'test@example.com'}
                )
            
            # Создаем поставку материала
            delivery = MaterialDelivery.objects.create(
                project=project,
                material_type=default_material_type,
                supplier='Обрабатывается...',
                quantity=1,  # Минимальное количество
                delivery_date=timezone.now(),
                status='pending',
                ttn_number=f'OCR-{timezone.now().strftime("%Y%m%d-%H%M%S")}',
                received_by=user,
                manual_entry=False
            )
            
            # Создаем запись транспортного документа
            transport_doc = TransportDocument.objects.create(
                delivery=delivery,
                document_number='Обрабатывается',
                document_date=timezone.now().date(),
                sender_name='Обрабатывается',
                sender_address='Обрабатывается',
                receiver_name='Обрабатывается',
                receiver_address='Обрабатывается',
                vehicle_number='',
                driver_name='',
                cargo_description='Обрабатывается',
                processing_status='uploaded',
                processed_by=user
            )
            
            # Определяем тип документа
            photo_type = request.data.get('photo_type', 'ttn_main')
            
            # Создаем фотографию документа
            document_photo = DocumentPhoto.objects.create(
                transport_document=transport_doc,
                photo_type=photo_type,
                image=uploaded_file,
                processing_status='uploaded',
                uploaded_by=user
            )
            
            # Запускаем улучшенную OCR обработку с простым процессором
            try:
                from .simple_ocr_processor import get_simple_ocr_processor
                
                # Получаем данные файла для обработки
                uploaded_file.seek(0)
                file_data = uploaded_file.read()
                
                # Используем простой OCR процессор
                simple_processor = get_simple_ocr_processor()
                ocr_result = simple_processor.process_document(file_data)
                
                # Преобразуем результат в формат для автозаполнения формы
                form_data = self._convert_ocr_to_form_data(ocr_result)
                ocr_result['form_data'] = form_data
                
                logger.info(f"OCR обработка завершена: {ocr_result.get('success', False)}")
                
            except Exception as ocr_error:
                logger.warning(f"Ошибка OCR обработки: {str(ocr_error)}")
                # Создаем фиктивный результат, чтобы не сломать систему
                ocr_result = {
                    'success': False,
                    'error': 'Ошибка системы OCR. Документ загружен, но автораспознавание недоступно.',
                    'confidence': 0,
                    'extracted_fields': {},
                    'form_data': {},
                    'requires_manual_check': True
                }
            
            return Response({
                'success': True,
                'transport_document_id': transport_doc.id,
                'document_photo_id': document_photo.id,
                'delivery_id': delivery.id,
                'ocr_result': ocr_result,
                'message': 'Документ успешно загружен и обработан'
            })
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке ТТН: {str(e)}")
            return Response({
                'success': False,
                'error': f'Ошибка обработки: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _convert_ocr_to_form_data(self, ocr_result):
        """Конвертирует OCR данные в формат для автозаполнения полей формы"""
        if not ocr_result.get('success') or not ocr_result.get('fields'):
            return {}
        
        fields = ocr_result['fields']
        form_data = {}
        
        # Номер ТТН
        if 'document_number' in fields:
            form_data['ttn_number'] = fields['document_number']
        
        # Дата поставки
        if 'date' in fields:
            try:
                import re
                from datetime import datetime
                
                date_str = fields['date']
                # Поддерживаем различные форматы дат
                date_patterns = [
                    (r'(\d{1,2})[.-](\d{1,2})[.-](\d{4})', '%d.%m.%Y'),  # дд.мм.гггг
                    (r'(\d{1,2})[.-](\d{1,2})[.-](\d{2})', '%d.%m.%y'),   # дд.мм.гг
                    (r'(\d{4})[.-](\d{1,2})[.-](\d{1,2})', '%Y-%m-%d'),  # гггг-мм-дд
                ]
                
                for pattern, fmt in date_patterns:
                    match = re.search(pattern, date_str)
                    if match:
                        if fmt in ['%d.%m.%Y', '%d.%m.%y']:
                            parsed_date = datetime.strptime(match.group(0), fmt)
                        else:
                            parsed_date = datetime.strptime(match.group(0), fmt)
                        
                        form_data['delivery_date'] = parsed_date.strftime('%Y-%m-%d')
                        break
            except Exception as e:
                logger.warning(f"Ошибка парсинга даты {fields['date']}: {str(e)}")
        
        # Поставщик
        if 'supplier' in fields:
            supplier = fields['supplier'].strip()
            # Очищаем от лишних символов
            supplier = re.sub(r'^[\s"\\«]+|[\s"\\»]+$', '', supplier)
            if supplier and len(supplier) > 3:
                form_data['supplier'] = supplier
        
        # Количество
        if 'quantity' in fields:
            try:
                quantity = fields['quantity'].replace(',', '.')
                # Извлекаем число
                quantity_match = re.search(r'(\d+(?:\.\d+)?)', quantity)
                if quantity_match:
                    form_data['quantity'] = float(quantity_match.group(1))
            except (ValueError, AttributeError) as e:
                logger.warning(f"Ошибка парсинга количества {fields['quantity']}: {str(e)}")
        
        # Материал (для поиска соответствующего типа)
        if 'material' in fields:
            form_data['material_hint'] = fields['material'].strip()
        
        # Информация о водителе и автомобиле (для справки)
        if 'driver_name' in fields:
            form_data['driver_info'] = fields['driver_name']
        if 'vehicle_number' in fields:
            form_data['vehicle_info'] = fields['vehicle_number']
        
        # ИНН поставщика (для справки)
        if 'inn' in fields:
            form_data['supplier_inn'] = fields['inn']
        
        # Надежность данных для UI
        form_data['ocr_confidence'] = ocr_result.get('confidence', 0)
        form_data['ocr_service'] = ocr_result.get('ocr_service', 'OCR Service')
        
        return form_data


class TTNProcessingStatusAPI(APIView):
    """API для получения статуса обработки ТТН"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, transport_document_id):
        """Получить статус обработки транспортного документа"""
        try:
            transport_doc = get_object_or_404(TransportDocument, id=transport_document_id)
            
            # Получаем все фотографии документа
            photos = transport_doc.photos.all().order_by('-uploaded_at')
            photos_data = []
            
            for photo in photos:
                photo_data = {
                    'id': photo.id,
                    'type': photo.get_photo_type_display(),
                    'status': photo.get_processing_status_display(),
                    'uploaded_at': photo.uploaded_at.isoformat(),
                    'confidence': photo.ocr_confidence,
                    'has_ocr_result': hasattr(photo, 'ocr_result')
                }
                
                # Добавляем OCR результаты если есть
                if hasattr(photo, 'ocr_result'):
                    ocr_result = photo.ocr_result
                    photo_data['ocr_data'] = {
                        'extracted_fields': ocr_result.extracted_fields,
                        'overall_confidence': ocr_result.overall_confidence,
                        'validation_status': ocr_result.get_validation_status_display()
                    }
                
                photos_data.append(photo_data)
            
            return Response({
                'success': True,
                'transport_document': {
                    'id': transport_doc.id,
                    'document_number': transport_doc.document_number,
                    'processing_status': transport_doc.get_processing_status_display(),
                    'requires_manual_check': transport_doc.manual_verification_required,
                    'created_at': transport_doc.created_at.isoformat()
                },
                'photos': photos_data,
                'delivery': {
                    'id': transport_doc.delivery.id,
                    'status': transport_doc.delivery.get_status_display(),
                    'project': transport_doc.delivery.project.name
                }
            })
            
        except Exception as e:
            logger.error(f"Ошибка при получении статуса ТТН: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TTNDataAPI(APIView):
    """API для работы с данными ТТН"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Получить список обработанных ТТН"""
        try:
            # Фильтры
            project_id = request.GET.get('project_id')
            status_filter = request.GET.get('status')
            
            # Базовый запрос
            queryset = TransportDocument.objects.select_related(
                'delivery__project', 'delivery__material_type'
            ).order_by('-created_at')
            
            if project_id:
                queryset = queryset.filter(delivery__project_id=project_id)
            
            if status_filter:
                queryset = queryset.filter(processing_status=status_filter)
            
            # Пагинация
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            # Формируем ответ
            results = []
            for doc in page_obj:
                results.append({
                    'id': doc.id,
                    'document_number': doc.document_number,
                    'document_date': doc.document_date.isoformat() if doc.document_date else None,
                    'sender_name': doc.sender_name,
                    'receiver_name': doc.receiver_name,
                    'processing_status': doc.get_processing_status_display(),
                    'requires_manual_check': doc.manual_verification_required,
                    'created_at': doc.created_at.isoformat(),
                    'project': {
                        'id': doc.delivery.project.id,
                        'name': doc.delivery.project.name
                    },
                    'delivery_status': doc.delivery.get_status_display(),
                    'photos_count': doc.photos.count()
                })
            
            return Response({
                'success': True,
                'results': results,
                'pagination': {
                    'current_page': page,
                    'total_pages': paginator.num_pages,
                    'total_items': paginator.count,
                    'per_page': per_page
                }
            })
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка ТТН: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, transport_document_id):
        """Обновить данные ТТН (ручная коррекция)"""
        try:
            transport_doc = get_object_or_404(TransportDocument, id=transport_document_id)
            
            # Обновляемые поля
            updatable_fields = [
                'document_number', 'document_date', 'sender_name', 'sender_address', 'sender_inn',
                'receiver_name', 'receiver_address', 'receiver_inn', 'vehicle_number', 'driver_name',
                'driver_license_number', 'cargo_description', 'cargo_weight', 'cargo_volume', 'packages_count'
            ]
            
            updated_fields = []
            for field in updatable_fields:
                if field in request.data:
                    value = request.data[field]
                    
                    # Специальная обработка для даты
                    if field == 'document_date' and value:
                        from datetime import datetime
                        try:
                            value = datetime.strptime(value, '%Y-%m-%d').date()
                        except ValueError:
                            continue
                    
                    setattr(transport_doc, field, value)
                    updated_fields.append(field)
            
            if updated_fields:
                transport_doc.processing_status = 'verified'
                transport_doc.manual_verification_required = False
                transport_doc.save()
                
                return Response({
                    'success': True,
                    'updated_fields': updated_fields,
                    'message': 'Данные ТТН успешно обновлены'
                })
            else:
                return Response({
                    'success': False,
                    'error': 'Не указано полей для обновления'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении ТТН: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MaterialOCRAPIView(APIView):
    """Распознавание ТТН и транспортных накладных по изображению с поддержкой SimpleOCRProcessor"""
    permission_classes = []  # Временно отключено для тестирования
    
    def post(self, request):
        file = request.FILES.get('ttn')
        if not file:
            return Response({
                'detail': 'Необходимо загрузить файл изображения в поле "ttn"'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Используем новый SimpleOCRProcessor
            from .simple_ocr_processor import get_simple_ocr_processor
            
            # Читаем файл в байты
            file_data = file.read()
            
            # Обрабатываем через SimpleOCRProcessor
            processor = get_simple_ocr_processor()
            result = processor.process_document(file_data)
            
            if result['success']:
                # Возвращаем результат в совместимом формате
                response_data = {
                    'success': True,
                    'raw_text': result.get('raw_text', ''),
                    'fields': result.get('fields', {}),
                    'confidence': result.get('confidence', 0),
                    'ocr_service': result.get('ocr_service', 'SimpleOCR'),
                    'message': f"Обработка завершена! Найдено полей: {len(result.get('fields', {}))}",
                    'lines_count': 0,
                    
                    # Поддержка legacy полей для обратной совместимости
                    'ttn_number': result.get('fields', {}).get('document_number'),
                    'date': result.get('fields', {}).get('delivery_date'),
                    'quantity': result.get('fields', {}).get('quantity'),
                    'unit': 'т' if result.get('fields', {}).get('quantity') else None,
                    'material_name': result.get('fields', {}).get('description', '').split()[0] if result.get('fields', {}).get('description') else None,
                }
                
                return Response(response_data)
            else:
                return Response({
                    'success': False,
                    'detail': f"Ошибка OCR: {result.get('error', 'Неизвестная ошибка')}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка в MaterialOCRAPIView: {str(e)}")
            return Response({
                'success': False,
                'detail': f'Ошибка OCR: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Frontend Views
@login_required
def material_list(request):
    """Страница материалов с фильтрацией по ролям"""
    from projects.models import Project
    from django.contrib import messages
    from django.db.models import Q, Count
    
    # Проверяем роль пользователя
    if hasattr(request.user, 'user_type') and request.user.user_type == 'foreman':
        # Прораб видит только материалы своих проектов
        projects = Project.objects.filter(foreman=request.user).order_by('name')
        
        # Получаем выбранный проект из параметров
        selected_project_id = request.GET.get('project')
        selected_project = None
        
        if selected_project_id:
            try:
                selected_project = projects.get(id=selected_project_id)
            except Project.DoesNotExist:
                messages.warning(request, 'Выбранный проект не найден.')
        
        # Фильтруем поставки
        deliveries_query = MaterialDelivery.objects.filter(
            project__foreman=request.user
        ).select_related('project', 'material_type', 'received_by')
        
        if selected_project:
            deliveries_query = deliveries_query.filter(project=selected_project)
        
        deliveries = deliveries_query.order_by('-delivery_date')
        
        # Последние обработанные ТТН
        ttn_query = TransportDocument.objects.filter(
            delivery__project__foreman=request.user
        ).select_related('delivery__project', 'delivery__material_type')
        
        if selected_project:
            ttn_query = ttn_query.filter(delivery__project=selected_project)
        
        recent_ttn = ttn_query.order_by('-created_at')[:5]
        
        # Статистика
        total_deliveries = deliveries_query.count()
        pending_deliveries = deliveries_query.filter(status='pending').count()
        delivered_deliveries = deliveries_query.filter(status='delivered').count()
        accepted_deliveries = deliveries_query.filter(status='accepted').count()
        
        context = {
            'is_foreman': True,
            'projects': projects,
            'selected_project': selected_project,
            'deliveries': deliveries[:50],  # Ограничиваем количество
            'recent_ttn': recent_ttn,
            'stats': {
                'total': total_deliveries,
                'pending': pending_deliveries,
                'delivered': delivered_deliveries,
                'accepted': accepted_deliveries,
            },
            'material_types': MaterialType.objects.all().order_by('name'),
        }
        
        return render(request, 'materials/foreman_materials.html', context)
    
    else:
        # Для остальных ролей - обычная страница
        projects = Project.objects.all().order_by('name')[:50]
        recent_deliveries = MaterialDelivery.objects.select_related(
            'project', 'material_type'
        ).order_by('-delivery_date')[:10]
        recent_ttn = TransportDocument.objects.select_related(
            'delivery__project', 'delivery__material_type'
        ).order_by('-created_at')[:5]
        
        context = {
            'projects': projects,
            'recent_deliveries': recent_deliveries,
            'recent_ttn': recent_ttn,
        }
        
        return render(request, 'materials/foreman_page.html', context)


@login_required
def delivery_detail(request, delivery_id):
    """Детальная страница поставки материала"""
    from django.contrib import messages
    from django.db.models import Q
    
    # Получаем поставку
    delivery = get_object_or_404(
        MaterialDelivery.objects.select_related(
            'project', 'material_type', 'received_by', 'spec_row'
        ).prefetch_related(
            'quality_controls'
        ),
        id=delivery_id
    )
    
    # Проверяем доступ
    if hasattr(request.user, 'user_type') and request.user.user_type == 'foreman':
        if delivery.project.foreman != request.user:
            messages.error(request, 'У вас нет доступа к этой поставке')
            return render(request, '403.html', status=403)
    
    # Получаем связанные данные
    # TransportDocument связан через OneToOneField, поэтому получаем так
    transport_documents = []
    try:
        if hasattr(delivery, 'transport_document'):
            transport_documents.append(delivery.transport_document)
    except TransportDocument.DoesNotExist:
        pass
    
    quality_controls = delivery.quality_controls.all().order_by('-created_at')
    
    # Получаем фотографии документов
    document_photos = []
    for doc in transport_documents:
        if hasattr(doc, 'photos'):
            document_photos.extend(doc.photos.all())
    
    # Статистика по поставке
    delivery_stats = {
        'documents_count': len(transport_documents),
        'photos_count': len(document_photos),
        'quality_checks_count': quality_controls.count(),
        'ocr_processed': sum(1 for photo in document_photos if hasattr(photo, 'ocr_result')),
    }
    
    context = {
        'delivery': delivery,
        'transport_documents': transport_documents,
        'quality_controls': quality_controls,
        'document_photos': document_photos,
        'delivery_stats': delivery_stats,
    }
    
    return render(request, 'materials/delivery_detail.html', context)


@login_required
def incoming_control_page(request):
    """Страница создания поставки с OCR распознаванием документов"""
    from projects.models import Project
    from .models import MaterialType
    
    # Получаем доступные проекты и типы материалов
    projects = Project.objects.all().order_by('name')[:50]
    material_types = MaterialType.objects.all().order_by('name')
    
    # Получаем предварительно выбранный проект из URL
    selected_project_id = request.GET.get('project')
    selected_project = None
    if selected_project_id:
        try:
            selected_project = Project.objects.get(id=selected_project_id)
        except Project.DoesNotExist:
            pass
    
    context = {
        'projects': projects,
        'material_types': material_types,
        'selected_project': selected_project,
        'selected_project_id': selected_project_id,
    }
    
    return render(request, 'materials/incoming_control.html', context)


def ocr_test_page(request):
    """Тестовая страница OCR автозаполнения (без аутентификации)"""
    return render(request, 'materials/ocr_test.html')


class ProcessDocumentOCRAPI(APIView):
    """
    API для реального OCR распознавания документов
    """
    permission_classes = []  # Временно отключено для тестирования
    
    def post(self, request):
        try:
            from .simple_ocr_processor import get_simple_ocr_processor
            ocr_processor = get_simple_ocr_processor()
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Получаем загруженный файл
            uploaded_file = request.FILES.get('document')
            if not uploaded_file:
                return Response({
                    'success': False,
                    'error': 'Не предоставлен файл для обработки'
                }, status=400)
            
            # Проверяем тип файла (только изображения)
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff']
            if uploaded_file.content_type not in allowed_types:
                return Response({
                    'success': False,
                    'error': f'Неподдерживаемый тип файла: {uploaded_file.content_type}. Поддерживаются: JPG, PNG, BMP, TIFF'
                }, status=400)
            
            # Проверяем размер файла (10MB максимум)
            if uploaded_file.size > 10 * 1024 * 1024:
                return Response({
                    'success': False,
                    'error': 'Размер файла превышает 10MB'
                }, status=400)
            
            logger.info(f'Обработка документа: {uploaded_file.name}, размер: {uploaded_file.size} bytes')
            
            # Читаем данные файла
            image_data = uploaded_file.read()
            
            # Обрабатываем документ
            result = ocr_processor.process_document(image_data)
            
            if not result['success']:
                return Response({
                    'success': False,
                    'error': result.get('error', 'Неизвестная ошибка OCR')
                }, status=500)
            
            logger.info(f'OCR обработка завершена. Найдено полей: {len(result["fields"])}')
            
            # Формируем ответ
            response_data = {
                'success': True,
                'fields': result['fields'],
                'confidence': result['confidence'],
                'raw_text': result.get('raw_text', ''),
                'lines_count': result.get('lines_count', 0),
                'message': f'Обработка завершена! Найдено полей: {len(result["fields"])}',
                'ocr_service': result.get('ocr_service', 'Простой OCR процессор')
            }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f'Ошибка OCR API: {str(e)}')
            return Response({
                'success': False,
                'error': f'Ошибка обработки: {str(e)}'
            }, status=500)


class CreateDeliveryWithOCRAPI(APIView):
    """
    API для создания поставки материалов с данными из OCR
    """
    permission_classes = []  # Временно отключено для тестирования
    
    def post(self, request):
        try:
            from django.db import transaction
            from projects.models import Project
            import json
            
            # Получаем данные из запроса
            project_id = request.data.get('project')
            material_type_id = request.data.get('material_type')
            quantity = request.data.get('quantity')
            delivery_date = request.data.get('delivery_date')
            supplier = request.data.get('supplier')
            document_number = request.data.get('document_number', '')
            supplier_inn = request.data.get('supplier_inn', '')
            driver_name = request.data.get('driver_name', '')
            vehicle_number = request.data.get('vehicle_number', '')
            cargo_weight = request.data.get('cargo_weight')
            description = request.data.get('description', '')
            ocr_data_str = request.data.get('ocr_data', '{}')
            
            # Проверяем обязательные поля
            if not all([project_id, material_type_id, quantity, delivery_date, supplier]):
                return Response({
                    'success': False,
                    'error': 'Не заполнены обязательные поля'
                }, status=400)
            
            try:
                ocr_data = json.loads(ocr_data_str) if isinstance(ocr_data_str, str) else ocr_data_str
            except (json.JSONDecodeError, TypeError):
                ocr_data = {}
            
            # Получаем связанные объекты
            try:
                project = Project.objects.get(id=project_id)
                material_type = MaterialType.objects.get(id=material_type_id)
            except (Project.DoesNotExist, MaterialType.DoesNotExist):
                return Response({
                    'success': False,
                    'error': 'Некорректные данные проекта или материала'
                }, status=400)
            
            # Получаем пользователя или создаем тестового
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = getattr(request, 'user', None)
            if not user or user.is_anonymous:
                user, created = User.objects.get_or_create(
                    username='test_ocr_user',
                    defaults={
                        'first_name': 'Test', 
                        'last_name': 'OCR User', 
                        'email': 'test@example.com',
                        'user_type': 'foreman'
                    }
                )
            
            # Создаем поставку в транзакции
            with transaction.atomic():
                delivery = MaterialDelivery.objects.create(
                    project=project,
                    material_type=material_type,
                    quantity=float(quantity),
                    delivery_date=delivery_date,
                    supplier=supplier,
                    status='pending',
                    received_by=user,
                    notes=f'OCR: {description[:200]}' if description else 'Created via OCR',
                )
                
                # Создаем транспортный документ если есть данные
                if document_number or driver_name or vehicle_number:
                    transport_doc = TransportDocument.objects.create(
                        delivery=delivery,
                        document_number=document_number or f'OCR-{delivery.id}',
                        driver_name=driver_name or 'Не указано',
                        vehicle_number=vehicle_number or 'Не указано',
                        cargo_weight=float(cargo_weight) if cargo_weight else None,
                        sender_name=supplier,
                        receiver_name=project.name,
                        cargo_description=description or material_type.name,
                        document_date=delivery_date,
                    )
                    
                    # Сохраняем OCR данные в метаданные документа
                    if ocr_data:
                        transport_doc.notes = f'OCR confidence: {ocr_data.get("confidence", 0)}%\n'
                        transport_doc.notes += f'OCR fields: {json.dumps(ocr_data.get("fields", {}), ensure_ascii=False, indent=2)}'
                        transport_doc.save()
                
                # Логирование
                logger.info(f'Created delivery via OCR: {delivery.id} by user {user.username}')
                
                return Response({
                    'success': True,
                    'message': 'Поставка успешно создана и добавлена в список!',
                    'data': {
                        'delivery_id': delivery.id,
                        'delivery_url': f'/materials/delivery/{delivery.id}/',
                        'project': project.name,
                        'material_type': material_type.name,
                        'quantity': delivery.quantity,
                        'supplier': delivery.supplier,
                        'status': delivery.status,
                    }
                })
                
        except Exception as e:
            logger.error(f'Error creating delivery via OCR: {str(e)}')
            return Response({
                'success': False,
                'error': f'Ошибка создания поставки: {str(e)}'
            }, status=500)
