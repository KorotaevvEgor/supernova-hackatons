from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.modern_dashboard, name='dashboard'),
    path('control/', views.construction_control_dashboard, name='construction_control_dashboard'),
    path('profile/', views.profile_dashboard, name='profile_dashboard'),
    path('remarks/', views.manage_remarks, name='manage_remarks'),
    path('schedule-changes/', views.manage_schedule_changes, name='manage_schedule_changes'),
    path('remark/<int:remark_id>/approve/', views.approve_remark, name='approve_remark'),
    path('remark/<int:remark_id>/reject/', views.reject_remark, name='reject_remark'),
    path('schedule-change/<int:change_id>/approve/', views.approve_schedule_change, name='approve_schedule_change'),
    path('schedule-change/<int:change_id>/reject/', views.reject_schedule_change, name='reject_schedule_change'),
    
    # Новые замечания
    path('comments/', views.manage_comments, name='manage_comments'),
    path('comment/<int:comment_id>/approve/', views.approve_comment, name='approve_comment'),
    path('comment/<int:comment_id>/reject/', views.reject_comment, name='reject_comment'),
]
