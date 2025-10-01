from django.urls import path
from .views import (
    ProfileView, VisitCreateView,
    foreman_identification, foreman_generate_qr, control_verify_identity, verify_qr_token
)
from . import api_views

app_name = 'accounts'

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('visit/', VisitCreateView.as_view(), name='visit'),
    # Foreman identification
    path('foreman/identification/', foreman_identification, name='foreman_identification'),
    path('foreman/generate-qr/', foreman_generate_qr, name='foreman_generate_qr'),
    
    # Control verification  
    path('verify-identity/', control_verify_identity, name='control_verify_identity'),
    path('verify-qr/', verify_qr_token, name='verify_qr_token'),
    
    # Notifications API
    path('notifications/', api_views.user_notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', api_views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read_all/', api_views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
