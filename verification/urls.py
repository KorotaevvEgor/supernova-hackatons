from django.urls import path
from . import views

app_name = 'verification'

urlpatterns = [
    path('', views.verification_list, name='verification_list'),
    path('verify/<int:work_id>/', views.verify_work, name='verify_work'),
    path('project/<int:project_id>/', views.project_verification, name='project_verification'),
]