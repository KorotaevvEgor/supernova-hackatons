from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from .models import (
    ViolationClassifier, ProjectCoordinates, WorkSpecification, 
    NetworkSchedule, TransportDocument, CheckListTemplate, 
    CheckListItem, ViolationPrescription
)
from .serializers import (
    ViolationClassifierSerializer, ProjectCoordinatesSerializer,
    WorkSpecificationSerializer, NetworkScheduleSerializer,
    TransportDocumentSerializer, CheckListTemplateSerializer,
    CheckListItemSerializer, ViolationPrescriptionSerializer
)


class ViolationClassifierViewSet(viewsets.ReadOnlyModelViewSet):
    """API для классификатора нарушений"""
    queryset = ViolationClassifier.objects.all()
    serializer_class = ViolationClassifierSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'violation_type', 'severity']
    search_fields = ['name']
    ordering_fields = ['category', 'fix_period', 'created_at']
    ordering = ['category', 'severity', 'name']
    
    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Получить список категорий нарушений"""
        categories = ViolationClassifier.CATEGORY_CHOICES
        return Response([{'value': choice[0], 'label': choice[1]} for choice in categories])
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """Получить список типов нарушений"""
        types = ViolationClassifier.TYPE_CHOICES
        return Response([{'value': choice[0], 'label': choice[1]} for choice in types])


class WorkSpecificationViewSet(viewsets.ReadOnlyModelViewSet):
    """АPI для спецификаций работ"""
    queryset = WorkSpecification.objects.all()
    serializer_class = WorkSpecificationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['object_name', 'unit']
    search_fields = ['work_name', 'object_name', 'address']
    ordering_fields = ['start_date', 'end_date', 'quantity']
    ordering = ['object_name', 'start_date']
    
    @action(detail=False, methods=['get'])
    def by_object(self, request):
        """Группировка работ по объектам"""
        objects = {}
        specifications = self.get_queryset()
        
        for spec in specifications:
            if spec.object_name not in objects:
                objects[spec.object_name] = []
            objects[spec.object_name].append(WorkSpecificationSerializer(spec).data)
        
        return Response(objects)
