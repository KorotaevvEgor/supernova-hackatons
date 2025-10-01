from django.urls import path
from . import views

app_name = 'projects_api'

urlpatterns = [
    path('', views.ProjectListAPI.as_view(), name='list'),
    path('<int:pk>/', views.ProjectDetailAPI.as_view(), name='detail'),
    path('<int:pk>/activate/', views.ProjectActivateAPI.as_view(), name='activate'),
    path('<int:pk>/spec/', views.WorkSpecListAPI.as_view(), name='spec-list'),
    path('<int:pk>/kpi/', views.ProjectKPIAPI.as_view(), name='kpi'),
    path('<int:pk>/export/materials/', views.MaterialsExportCSVAPI.as_view(), name='export-materials'),
    path('<int:pk>/export/works/', views.WorksExportCSVAPI.as_view(), name='export-works'),
    path('works/<int:pk>/report-completion/', views.WorkReportCompletionAPI.as_view(), name='work-report-completion'),
    path('works/<int:pk>/verify/', views.WorkVerifyAPI.as_view(), name='work-verify'),
    path('<int:pk>/works/', views.ProjectWorksAPI.as_view(), name='project-works'),
    path('works/<int:pk>/schedule-change/', views.ScheduleChangeCreateAPI.as_view(), name='schedule-change-create'),
    path('schedule-changes/<int:pk>/review/', views.ScheduleChangeReviewAPI.as_view(), name='schedule-change-review'),
]
