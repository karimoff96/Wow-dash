from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='landing_home'),
    path('change-language/<str:lang_code>/', views.change_language, name='change_language'),
    path('contact/', views.contact_form, name='contact_form'),
]
