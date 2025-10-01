from django.urls import path
from .views import OpeningChecklistDetailAPI, OpeningChecklistCompleteAPI, OpeningChecklistApproveAPI
from .exports import OpeningChecklistExportXLSXAPI

app_name = 'documents_api'

urlpatterns = [
    path('opening-checklist/<int:project_id>/', OpeningChecklistDetailAPI.as_view(), name='opening-checklist-detail'),
    path('opening-checklist/<int:project_id>/complete/', OpeningChecklistCompleteAPI.as_view(), name='opening-checklist-complete'),
    path('opening-checklist/<int:project_id>/approve/', OpeningChecklistApproveAPI.as_view(), name='opening-checklist-approve'),
    path('opening-checklist/<int:project_id>/export.xlsx', OpeningChecklistExportXLSXAPI.as_view(), name='opening-checklist-export-xlsx'),
]
