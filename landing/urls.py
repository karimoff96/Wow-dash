from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='landing_home'),
    # SEO-friendly per-language URLs so each language gets its own crawlable URL
    path('en/', views.home_lang, {'lang_code': 'en'}, name='landing_home_en'),
    path('uz/', views.home_lang, {'lang_code': 'uz'}, name='landing_home_uz'),
    path('change-language/<str:lang_code>/', views.change_language, name='change_language'),
    path('contact/', views.contact_form, name='contact_form'),
    path('contact-requests/', views.contact_requests_list, name='contact_requests_list'),
    path('contact-requests/<int:pk>/change-status/', views.contact_request_change_status, name='contact_request_change_status'),
    path('contact-requests/<int:pk>/add-note/', views.contact_request_add_note, name='contact_request_add_note'),
    # Unified requests management (contact + renewal)
    path('requests/', views.requests_management, name='requests_management'),
    # SEO
    path('google145d3096a17fea6d.html', views.google_site_verification, name='google_site_verification'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
]
