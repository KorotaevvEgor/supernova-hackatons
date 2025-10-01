from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import DocumentType, Document, ProjectOpeningChecklist, ChecklistItemCompletion
from projects.models import Project
from accounts.models import Visit

OPENING_ACT_CODE = 'OPENING_ACT'

class OpeningChecklistDetailAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        checklist = getattr(project, 'opening_checklist', None)
        if not checklist:
            return Response({'detail': 'Чек-лист еще не создан'}, status=status.HTTP_404_NOT_FOUND)
        items = []
        for ic in checklist.item_completions.select_related('checklist_item').all():
            items.append({
                'item_id': ic.checklist_item.id,
                'name': ic.checklist_item.name,
                'description': ic.checklist_item.description,
                'is_required': ic.checklist_item.is_required,
                'order': ic.checklist_item.order,
                'completed': ic.is_completed,
            })
        return Response({'project_id': project.id, 'is_completed': checklist.is_completed, 'items': items})

class OpeningChecklistCompleteAPI(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, project_id):
        if request.user.user_type != 'construction_control':
            return Response({'detail':'Недостаточно прав'}, status=status.HTTP_403_FORBIDDEN)
        project = get_object_or_404(Project, pk=project_id)
        # Требуем актуальный визит
        visit = Visit.objects.filter(user=request.user, project=project).order_by('-created_at').first()
        if not visit:
            return Response({'detail':'Нет отметки посещения'}, status=status.HTTP_400_BAD_REQUEST)
        checklist = getattr(project, 'opening_checklist', None)
        if not checklist:
            return Response({'detail':'Чек-лист еще не создан (активируйте проект)'}, status=status.HTTP_400_BAD_REQUEST)
        ids_completed = request.data.get('completed_ids', [])
        updated = 0
        for ic in checklist.item_completions.select_related('checklist_item').all():
            if ic.checklist_item.id in ids_completed:
                if not ic.is_completed:
                    ic.is_completed = True
                    ic.completed_by = request.user
                    ic.completed_at = timezone.now()
                    ic.save()
                    updated += 1
        return Response({'status':'ok','updated': updated})

class OpeningChecklistApproveAPI(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, project_id):
        if request.user.user_type != 'inspector':
            return Response({'detail':'Недостаточно прав'}, status=status.HTTP_403_FORBIDDEN)
        project = get_object_or_404(Project, pk=project_id)
        visit = Visit.objects.filter(user=request.user, project=project).order_by('-created_at').first()
        if not visit:
            return Response({'detail':'Нет отметки посещения'}, status=status.HTTP_400_BAD_REQUEST)
        checklist = getattr(project, 'opening_checklist', None)
        if not checklist:
            return Response({'detail':'Чек-лист не найден'}, status=status.HTTP_404_NOT_FOUND)
        checklist.is_completed = True
        checklist.approved_by_inspector = request.user
        checklist.completion_date = timezone.now()
        checklist.save()
        project.opening_checklist_completed = True
        project.save()
        # Обработка файла акта (опционально)
        if 'opening_act' in request.FILES:
            project.opening_act = request.FILES['opening_act']
            project.save()
            # Создаем запись документа
            dt, _ = DocumentType.objects.get_or_create(code=OPENING_ACT_CODE, defaults={'name':'Акт открытия объекта'})
            Document.objects.create(
                document_type=dt,
                project=project,
                title='Акт открытия объекта',
                description='Загружен инспектором',
                file=project.opening_act,
                status='approved',
                created_by=request.user,
                approved_by=request.user,
                approved_at=timezone.now(),
            )
        return Response({'status':'ok','project_id': project.id})
