from django.urls import path
from . import views

app_name = 'foreman'

urlpatterns = [
    # Главная страница прораба
    path('', views.foreman_dashboard, name='dashboard'),
    
    # Проекты
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    
    # Входной контроль материалов
    path('materials/', views.materials_control, name='materials_control'),
    path('materials/add/', views.add_material_delivery, name='add_material_delivery'),
    
    # Отметка выполненных работ
    path('works/', views.work_progress, name='work_progress'),
    path('api/works/complete/', views.mark_work_completed, name='mark_work_completed'),
    
    # Управление замечаниями
    path('comments/', views.comments_management, name='comments_management'),
    path('comments/<int:comment_id>/resolve/', views.resolve_comment, name='resolve_comment'),
    
    # Идентификация
    path('identification/', views.foreman_identification, name='identification'),
    path('generate-qr/', views.foreman_generate_qr, name='generate_qr'),
]