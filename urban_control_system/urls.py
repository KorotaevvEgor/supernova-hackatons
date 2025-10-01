"""
URL configuration for urban_control_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    
    # Role-specific dashboards
    path('dashboard/control/', views.dashboard_control, name='dashboard_control'),
    path('dashboard/foreman/', views.dashboard_foreman, name='dashboard_foreman'),
    path('dashboard/inspector/', views.dashboard_inspector, name='dashboard_inspector'),
    
    # Auth URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='accounts_login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='accounts_logout'),
    
    # Frontend URLs
    path('projects/', include('projects.urls')),
    path('materials/', include('materials.urls')),
    path('violations/', include('violations.urls')),
    path('verification/', include('verification.urls')),
    path('profile/', include('dashboard.urls')),
    path('foreman/', include('foreman.urls')),
    path('inspector/', include('inspector.urls')),
    path('control/', include('accounts.urls')),
    
    # API URLs
    path('api/projects/', include('projects.api_urls')),
    path('api/materials/', include('materials.api_urls')),
    path('api/violations/', include('violations.api_urls')),
    path('api/documents/', include('documents.api_urls')),
    path('dataset/', include('dataset.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
