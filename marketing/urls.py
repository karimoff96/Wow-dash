from django.urls import path
from . import views

urlpatterns = [
    # Marketing posts list and management
    path('', views.marketing_list, name='marketing_list'),
    path('create/', views.marketing_create, name='marketing_create'),
    path('<int:post_id>/', views.marketing_detail, name='marketing_detail'),
    path('<int:post_id>/edit/', views.marketing_edit, name='marketing_edit'),
    path('<int:post_id>/delete/', views.marketing_delete, name='marketing_delete'),
    
    # Broadcast actions
    path('<int:post_id>/preview/', views.marketing_preview, name='marketing_preview'),
    path('<int:post_id>/send/', views.marketing_send, name='marketing_send'),
    path('<int:post_id>/pause/', views.marketing_pause, name='marketing_pause'),
    path('<int:post_id>/cancel/', views.marketing_cancel, name='marketing_cancel'),
    
    # API endpoints
    path('api/recipient-count/', views.api_recipient_count, name='api_recipient_count'),
    path('api/branches/<int:center_id>/', views.api_center_branches, name='api_center_branches'),
]
