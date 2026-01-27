from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='landing_home'),
    path('change-language/<str:lang_code>/', views.change_language, name='change_language'),
    path('contact/', views.contact_form, name='contact_form'),
    path('contact-requests/', views.contact_requests_list, name='contact_requests_list'),
    path('contact-requests/<int:pk>/change-status/', views.contact_request_change_status, name='contact_request_change_status'),
    path('contact-requests/<int:pk>/add-note/', views.contact_request_add_note, name='contact_request_add_note'),
]
