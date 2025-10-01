from rest_framework import serializers
from .models import (
    ViolationClassifier, ProjectCoordinates, WorkSpecification, 
    NetworkSchedule, TransportDocument, CheckListTemplate, 
    CheckListItem, ViolationPrescription
)


class ViolationClassifierSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    violation_type_display = serializers.CharField(source='get_violation_type_display', read_only=True)
    
    class Meta:
        model = ViolationClassifier
        fields = [
            'id', 'category', 'category_display', 'violation_type', 
            'violation_type_display', 'severity', 'name', 'fix_period', 'created_at'
        ]


class ProjectCoordinatesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCoordinates
        fields = ['id', 'name', 'address', 'wkt_polygon', 'created_at']


class WorkSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSpecification
        fields = [
            'id', 'object_name', 'work_name', 'quantity', 'unit', 
            'start_date', 'end_date', 'address', 'created_at'
        ]


class NetworkScheduleSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = NetworkSchedule
        fields = [
            'id', 'object_name', 'work_name', 'kpgz_code', 
            'start_date', 'end_date', 'work_essence', 'duration_days', 'created_at'
        ]
    
    def get_duration_days(self, obj):
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days
        return None


class TransportDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportDocument
        fields = [
            'id', 'document_number', 'date', 'sender', 'receiver', 
            'material_name', 'quantity_net', 'quantity_gross', 'volume', 
            'delivery_address', 'transport_number', 'created_at'
        ]


class CheckListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckListItem
        fields = [
            'id', 'section', 'item_number', 'description', 
            'regulatory_document', 'order'
        ]


class CheckListTemplateSerializer(serializers.ModelSerializer):
    form_type_display = serializers.CharField(source='get_form_type_display', read_only=True)
    items = CheckListItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CheckListTemplate
        fields = [
            'id', 'name', 'form_type', 'form_type_display', 
            'description', 'items_count', 'items', 'created_at'
        ]
    
    def get_items_count(self, obj):
        return obj.items.count()


class ViolationPrescriptionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    violation_display = serializers.StringRelatedField(source='violation', read_only=True)
    inspector_name = serializers.CharField(source='inspector.get_full_name', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = ViolationPrescription
        fields = [
            'id', 'number', 'date_issued', 'violation', 'violation_display',
            'description', 'work_stopped', 'fix_deadline', 'actual_fix_date',
            'status', 'status_display', 'notes', 'inspector', 'inspector_name',
            'is_overdue', 'created_at'
        ]
    
    def get_is_overdue(self, obj):
        from django.utils import timezone
        if obj.status in ['issued', 'in_progress']:
            return obj.fix_deadline < timezone.now().date()
        return False