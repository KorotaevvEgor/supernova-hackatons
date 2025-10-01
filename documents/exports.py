from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import HttpResponse
import io
import pandas as pd
from django.shortcuts import get_object_or_404
from .models import ProjectOpeningChecklist, ChecklistItemCompletion

class OpeningChecklistExportXLSXAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, project_id):
        checklist = get_object_or_404(ProjectOpeningChecklist, project_id=project_id)
        rows = []
        for ic in checklist.item_completions.select_related('checklist_item').all():
            rows.append({
                'Пункт': ic.checklist_item.name,
                'Обязательно': 'Да' if ic.checklist_item.is_required else 'Нет',
                'Выполнено': 'Да' if ic.is_completed else 'Нет',
                'Когда': ic.completed_at,
                'Кем': ic.completed_by.get_full_name() if ic.completed_by else '',
                'Примечания': ic.completion_notes or ''
            })
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Чек-лист')
        buf.seek(0)
        resp = HttpResponse(buf.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        resp['Content-Disposition'] = 'attachment; filename="opening_checklist.xlsx"'
        return resp
