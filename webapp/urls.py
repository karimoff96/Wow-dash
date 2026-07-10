from django.urls import path
from . import views

app_name = "webapp"

urlpatterns = [
    # HTML entry-point — subdomain-based (BotFather URL: https://{subdomain}.multilang.uz/webapp/)
    path("", views.webapp_index_subdomain, name="index_subdomain"),

    # HTML entry-point — legacy center_id-based URL (kept for backward compatibility)
    path("<int:center_id>/", views.webapp_index, name="index"),

    # JSON API — all require initData + center_id in the request body
    path("api/init/", views.api_init, name="api_init"),
    path("api/register/", views.api_register, name="api_register"),
    path("api/order/create/", views.api_create_order, name="api_create_order"),
    path("api/orders/", views.api_my_orders, name="api_my_orders"),
    path("api/orders/<int:order_id>/", views.api_order_detail, name="api_order_detail"),
    path("api/orders/<int:order_id>/comments/", views.api_add_order_comment, name="api_add_order_comment"),
    path("api/orders/<int:order_id>/payme-checkout/", views.api_order_payme_checkout, name="api_order_payme_checkout"),
    path("api/orders/<int:order_id>/receipt/", views.api_upload_receipt, name="api_upload_receipt"),

    # Quote-to-order workflow
    path("api/quotes/create/", views.api_quote_create, name="api_quote_create"),
    path("api/quotes/", views.api_my_quotes, name="api_my_quotes"),
    path("api/quotes/<int:quote_id>/accept/", views.api_accept_quote, name="api_accept_quote"),
    path("api/quotes/<int:quote_id>/reject/", views.api_reject_quote, name="api_reject_quote"),
    path("api/media/<int:media_id>/download/", views.api_secure_media, name="api_secure_media"),
    path("api/notification-preferences/", views.api_notification_preferences, name="api_notification_preferences"),

    # Profile view / update
    path("api/profile/", views.api_profile, name="api_profile"),

    # Center / branch info (about us, help, other services)
    path("api/center-info/", views.api_center_info, name="api_center_info"),

    # Price list for user's branch
    path("api/pricelist/", views.api_pricelist, name="api_pricelist"),

    # Payme post-checkout return page
    path("payment-return/", views.payment_return, name="payment_return"),
]
