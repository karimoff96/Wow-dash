from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Subscription management
    path('subscriptions/', views.subscription_list, name='subscription_list'),
    path('subscriptions/create/<int:center_id>/', views.subscription_create, name='subscription_create'),
    path('subscriptions/<int:pk>/', views.subscription_detail, name='subscription_detail'),
    path('subscriptions/<int:pk>/update-status/', views.subscription_update_status, name='subscription_update_status'),
    path('subscriptions/<int:pk>/convert-trial/', views.convert_trial_to_paid, name='convert_trial_to_paid'),
    path('subscriptions/<int:pk>/extend-trial/', views.extend_trial, name='extend_trial'),
    path('subscriptions/<int:pk>/renew/', views.subscription_renew, name='subscription_renew'),
    
    # Analytics and monitoring
    path('analytics/<int:center_id>/', views.subscription_analytics, name='subscription_analytics'),
    path('monitoring/', views.centers_monitoring, name='centers_monitoring'),
    
    # Tariff management
    path('tariffs/', views.tariff_list, name='tariff_list'),
    path('tariffs/create/', views.tariff_create, name='tariff_create'),
    path('tariffs/<int:pk>/edit/', views.tariff_edit, name='tariff_edit'),
    path('tariffs/<int:pk>/delete/', views.tariff_delete, name='tariff_delete'),
    
    # Usage tracking
    path('usage-tracking/', views.usage_tracking_list, name='usage_tracking'),
    
    # Centers with subscription status
    path('centers/', views.centers_list, name='centers_list'),
    
    # User renewal request
    path('request-renewal/', views.request_renewal, name='request_renewal'),

    # Expired subscription landing
    path('subscription-expired/', views.subscription_expired, name='subscription_expired'),
]
