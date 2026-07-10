from django.urls import path
from core import views, archive_views, diagnostics, health

app_name = 'core'

urlpatterns = [
    path('health/live/', health.live, name='health_live'),
    path('health/ready/', health.ready, name='health_ready'),
    path('diagnostics/onboarding/', diagnostics.onboarding_diagnostics, name='onboarding_diagnostics'),
    path('notifications/', views.get_notifications, name='get_notifications'),
    path('notifications/all/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('audit-logs/', views.audit_logs, name='audit_logs'),
    
    # Archive management
    path('archives/', archive_views.archive_list, name='archive_list'),
    path('archives/<int:archive_id>/', archive_views.archive_detail, name='archive_detail'),
    path('archives/trigger/', archive_views.trigger_archive, name='trigger_archive'),
    path('archives/stats/', archive_views.archive_stats, name='archive_stats'),
]
