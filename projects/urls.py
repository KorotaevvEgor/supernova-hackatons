from django.urls import path, include
from . import views
from . import activation_views
from . import api_views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('schedule/', views.work_schedule, name='work_schedule'),
    path('<int:project_id>/activate/', views.project_activation, name='project_activation'),
    
    # Construction Control Dashboard
    path('control-dashboard/', views.construction_control_dashboard, name='construction_control_dashboard'),
    
    # Comments (Замечания)
    path('comments/', views.comments_list, name='comments_list'),
    path('comments/<int:comment_id>/', views.comment_detail, name='comment_detail'),
    path('<int:project_id>/comments/create/', views.create_comment, name='create_comment'),
    path('comments/<int:comment_id>/accept/', views.accept_comment, name='accept_comment'),
    path('comments/<int:comment_id>/reject/', views.reject_comment, name='reject_comment'),
    path('comments/<int:comment_id>/resolve/', views.resolve_comment, name='resolve_comment'),
    
    # Нарушения инспектора
    path('violations/<int:violation_id>/correct/', views.mark_violation_corrected, name='mark_violation_corrected'),
    
    # API endpoints for workflow
    path('api/projects/<int:project_id>/activate/', api_views.activate_project, name='api_activate_project'),
    path('api/projects/<int:project_id>/status/', api_views.get_project_status, name='api_project_status'),
    path('api/tasks/<int:task_id>/complete/', api_views.complete_task, name='api_complete_task'),
    path('api/tasks/<int:task_id>/upload_photo/', api_views.upload_task_photo, name='api_upload_task_photo'),
    path('api/works/<int:work_id>/report/', api_views.report_work_progress, name='api_report_work'),
    path('api/inspections/', api_views.create_inspection, name='api_create_inspection'),
    path('api/inspections/<int:inspection_id>/complete/', api_views.complete_inspection, name='api_complete_inspection'),
    
    # Comments API
    path('api/comments/', api_views.comments_list_create, name='api_comments_list_create'),
    path('api/comments/<int:comment_id>/', api_views.comment_detail_api, name='api_comment_detail'),
    path('api/comments/<int:comment_id>/accept/', api_views.accept_comment_api, name='api_accept_comment'),
    path('api/comments/<int:comment_id>/reject/', api_views.reject_comment_api, name='api_reject_comment'),
    path('api/comments/<int:comment_id>/resolve/', api_views.resolve_comment_api, name='api_resolve_comment'),
    path('api/comments/validate_location/', api_views.validate_location_for_comment, name='api_validate_location'),
    
    # Activation workflow URLs
    # path('my-projects/', activation_views.projects_list_with_activation, name='my_projects'),  # Удалено по запросу
    path('activate/<int:project_id>/', activation_views.initiate_project_activation, name='initiate_activation'),
    path('activation/<int:activation_id>/assign-foreman/', activation_views.assign_foreman, name='assign_foreman'),
    path('activation/<int:activation_id>/checklist/', activation_views.checklist_form, name='checklist_form'),
    path('activation/<int:activation_id>/inspect/', activation_views.inspector_review, name='inspector_review'),
    path('activation/<int:activation_id>/', activation_views.activation_detail, name='activation_detail'),
    path('inspector/activations/', activation_views.inspector_dashboard_activations, name='inspector_activations'),
    
    # QR коды
    path('<int:project_id>/qr/generate/', views.generate_qr_code, name='generate_qr_code'),
    path('<int:project_id>/qr/<int:qr_id>/', views.qr_code_detail, name='qr_code_detail'),
    path('qr/verify/<uuid:code>/', views.verify_qr_code, name='verify_qr'),
    
    # Погодная аналитика
    path('<int:project_id>/weather-analysis/', views.weather_analysis_detail, name='weather_analysis_detail'),
    
    # Notifications API
    path('api/notifications/', activation_views.notifications_api, name='notifications_api'),
    path('api/notifications/<int:notification_id>/read/', activation_views.mark_notification_read, name='mark_notification_read'),
]
