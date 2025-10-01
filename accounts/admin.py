from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Notification, UserSession

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'organization', 'is_staff')
    list_filter = ('user_type', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'organization')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('user_type', 'phone', 'organization', 'position', 'avatar', 'last_location')
        }),
    )

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'recipient__username')
    readonly_fields = ('created_at',)

@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'session_start', 'session_end', 'is_verified')
    list_filter = ('is_verified', 'session_start')
    search_fields = ('user__username',)
    readonly_fields = ('session_start',)
