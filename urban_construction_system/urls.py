from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication URLs
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('control/', include('accounts.urls')),
    
    # Dashboard URLs
    path('', include('dashboard.urls')),
    
    # Main app URLs
    path('projects/', include('projects.urls')),
    path('materials/', include('materials.urls')),
    path('violations/', include('violations.urls')),
    path('verification/', include('verification.urls')),
    path('foreman/', include('foreman.urls')),
    path('inspector/', include('inspector.urls')),
    
    # API URLs
    path('api/projects/', include('projects.api.urls')),
    path('api/materials/', include('materials.api.urls')),
    path('api/violations/', include('violations.api.urls')),
    path('api/accounts/', include('accounts.api.urls')),
    path('api/documents/', include('documents.api.urls')),
    
    # OCR Demo and API URLs
    path('', include('demo.urls')),  # Добавляем URLs для OCR demo
] 

# Добавляем обработку медиа и статических файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
