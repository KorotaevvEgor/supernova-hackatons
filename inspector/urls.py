from django.urls import path
from . import views

app_name = 'inspector'

urlpatterns = [
    # Главная страница инспектора
    path('', views.inspector_dashboard, name='dashboard'),
    
    # Нарушения
    path('violations/', views.violations_list, name='violations_list'),
    path('violations/add/', views.add_violation, name='add_violation'),
    path('violations/<int:violation_id>/', views.violation_detail, name='violation_detail'),
    path('api/violations/status/', views.update_violation_status, name='update_violation_status'),
    
    # Лабораторные пробы
    path('lab-requests/', views.lab_requests, name='lab_requests'),
    path('lab-requests/create/', views.create_lab_request, name='create_lab_request'),
    path('lab-requests/<int:request_id>/', views.lab_request_detail, name='lab_request_detail'),
    
    # Одобрения активации проектов
    path('approvals/', views.project_approvals, name='project_approvals'),
    path('approvals/create/<int:project_id>/', views.create_project_approval, name='create_project_approval'),
    path('approvals/<int:approval_id>/', views.approval_detail, name='approval_detail'),
    
    # Классификатор нарушений из датасета
    path('classifier/', views.violation_classifier, name='violation_classifier'),
    
    # Спецификации работ
    path('specifications/', views.work_specifications, name='work_specifications'),
]