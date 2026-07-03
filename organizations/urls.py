from django.urls import path
from . import views

urlpatterns = [
    # Translation Centers
    path('centers/', views.center_list, name='center_list'),
    path('centers/create/', views.center_create, name='center_create'),
    path('centers/<int:center_id>/', views.center_detail, name='center_detail'),
    path('centers/<int:center_id>/edit/', views.center_edit, name='center_edit'),
    
    # Branches
    path('branches/', views.branch_list, name='branch_list'),
    path('branches/create/', views.branch_create, name='branch_create'),
    path('branches/create/<int:center_id>/', views.branch_create, name='branch_create_for_center'),
    path('branches/<int:branch_id>/', views.branch_detail, name='branch_detail'),
    path('branches/<int:branch_id>/edit/', views.branch_edit, name='branch_edit'),
    
    # Branch Settings (Additional Info)
    path('branches/<int:branch_id>/settings/', views.branch_settings, name='branch_settings'),
    path('branches/<int:branch_id>/settings/edit/', views.branch_settings_edit, name='branch_settings_edit'),
    
    # Staff
    path('staff/', views.staff_list, name='staff_list'),
    path('staff/create/', views.staff_create, name='staff_create'),
    path('staff/<int:staff_id>/', views.staff_detail, name='staff_detail'),
    path('staff/<int:staff_id>/edit/', views.staff_edit, name='staff_edit'),
    path('staff/<int:staff_id>/toggle/', views.staff_toggle_active, name='staff_toggle_active'),
    
    # Roles (Superuser only)
    path('roles/', views.role_list, name='role_list'),
    path('roles/create/', views.role_create, name='role_create'),
    path('roles/<int:role_id>/edit/', views.role_edit, name='role_edit'),
    path('roles/<int:role_id>/delete/', views.role_delete, name='role_delete'),
    
    # API endpoints
    path('api/districts/<int:region_id>/', views.get_districts, name='get_districts'),
    path('api/branch/<int:branch_id>/staff/', views.get_branch_staff, name='get_branch_staff'),
    path('api/region/create/', views.create_region, name='create_region'),
    path('api/district/create/', views.create_district, name='create_district'),
    path('api/user/create/', views.api_create_user, name='api_create_user'),
    
    # Webhook management (Superuser only)
    path('api/centers/<int:center_id>/webhook/setup/', views.setup_center_webhook, name='setup_center_webhook'),
    path('api/centers/<int:center_id>/webhook/remove/', views.remove_center_webhook, name='remove_center_webhook'),
    path('api/centers/<int:center_id>/webhook/info/', views.get_center_webhook_info, name='get_center_webhook_info'),
]
