from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    # ── Staff side ────────────────────────────────────────────────────
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/new/', views.ticket_create, name='ticket_create'),
    path('tickets/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:ticket_id>/reply/', views.ticket_reply, name='ticket_reply'),
    path('tickets/<int:ticket_id>/resolve/', views.ticket_resolve, name='ticket_resolve'),

    # ── Support / Superuser inbox ────────────────────────────────────
    path('inbox/', views.support_ticket_list, name='support_list'),
    path('inbox/<int:ticket_id>/', views.support_ticket_detail, name='support_detail'),
    path('inbox/<int:ticket_id>/reply/', views.support_reply, name='support_reply'),
    path('inbox/<int:ticket_id>/status/', views.support_update_status, name='support_status'),
]
