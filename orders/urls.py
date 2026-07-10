"""
URL configuration for orders app.
"""

from django.urls import path
from .views import (
    ordersList, orderDetail, orderEdit, updateOrderStatus, deleteOrder,
    assignOrder, unassignOrder, receivePayment, completeOrder,
    api_order_stats, api_branch_staff, api_poll_new_orders, myOrders, orderCreate,
    record_order_payment, add_order_extra_fee, get_order_payment_info,
    bulk_delete_orders, search_customers, search_categories, search_products,
    edit_order_price, order_invoice_pdf,
    secure_legacy_receipt, secure_order_media, secure_receipt,
    add_order_comment, delete_order_comment,
        api_payme_transactions,
        api_payme_transaction_detail,
)
from .bulk_payment_views import (
    bulk_payment_page, search_customers_with_debt, get_customer_debt_details,
    preview_payment_distribution, process_bulk_payment, payment_history, 
    payment_history_full, get_payment_details, get_top_debtors_api
)
from . import workflow_views

app_name = 'orders'

urlpatterns = [
    path("api/workflow/quotes/", workflow_views.quote_list_api, name="quote_list_api"),
    path("api/workflow/quotes/<int:quote_id>/approve/", workflow_views.approve_quote_api, name="approve_quote_api"),
    path("api/workflow/quotes/<int:quote_id>/revise/", workflow_views.revise_quote_api, name="revise_quote_api"),
    path("api/workflow/kanban/", workflow_views.kanban_api, name="workflow_kanban_api"),
    path("api/workflow/orders/<int:order_id>/auto-assign/", workflow_views.auto_assign_api, name="auto_assign_api"),
    path("api/workflow/orders/<int:order_id>/timeline/", workflow_views.order_timeline_api, name="order_timeline_api"),
    path("api/workflow/metrics/", workflow_views.workflow_metrics_api, name="workflow_metrics_api"),
    # Order list and detail
    path("", ordersList, name="ordersList"),
    path("my-orders/", myOrders, name="myOrders"),
    path("create/", orderCreate, name="orderCreate"),
    path("<int:order_id>/", orderDetail, name="orderDetail"),
    path("<int:order_id>/invoice/", order_invoice_pdf, name="order_invoice_pdf"),
    path("media/<int:media_id>/download/", secure_order_media, name="secure_order_media"),
    path("receipts/legacy/<int:order_id>/download/", secure_legacy_receipt, name="secure_legacy_receipt"),
    path("receipts/<int:receipt_id>/download/", secure_receipt, name="secure_receipt"),
    path("<int:order_id>/edit/", orderEdit, name="orderEdit"),
    
    # Order actions
    path("<int:order_id>/update-status/", updateOrderStatus, name="updateOrderStatus"),
    path("<int:order_id>/delete/", deleteOrder, name="deleteOrder"),
    path("bulk-delete/", bulk_delete_orders, name="bulk_delete_orders"),
    path("<int:order_id>/assign/", assignOrder, name="assignOrder"),
    path("<int:order_id>/unassign/", unassignOrder, name="unassignOrder"),
    path("<int:order_id>/receive-payment/", receivePayment, name="receivePayment"),
    path("<int:order_id>/complete/", completeOrder, name="completeOrder"),
    path("<int:order_id>/edit-price/", edit_order_price, name="edit_order_price"),

    # Internal comments
    path("<int:order_id>/comments/add/", add_order_comment, name="add_order_comment"),
    path("<int:order_id>/comments/<int:comment_id>/delete/", delete_order_comment, name="delete_order_comment"),
    
    # Payment management API
    path("<int:order_id>/payment/record/", record_order_payment, name="record_order_payment"),
    path("<int:order_id>/payment/extra-fee/", add_order_extra_fee, name="add_order_extra_fee"),
    path("<int:order_id>/payment/info/", get_order_payment_info, name="get_order_payment_info"),
    
    # Bulk Payment Management
    path("bulk-payment/", bulk_payment_page, name="bulk_payment_page"),
    path("bulk-payment/top-debtors/", get_top_debtors_api, name="get_top_debtors_api"),
    path("bulk-payment/search-customers/", search_customers_with_debt, name="search_customers_with_debt"),
    path("bulk-payment/customer-debt/<int:customer_id>/", get_customer_debt_details, name="get_customer_debt_details"),
    path("bulk-payment/preview/", preview_payment_distribution, name="preview_payment_distribution"),
    path("bulk-payment/process/", process_bulk_payment, name="process_bulk_payment"),
    path("bulk-payment/history/", payment_history, name="payment_history"),
    path("bulk-payment/history/full/", payment_history_full, name="payment_history_full"),
    path("bulk-payment/details/<int:payment_id>/", get_payment_details, name="get_payment_details"),
    
    # API endpoints
    path("api/stats/", api_order_stats, name="api_order_stats"),
    path("api/branch/<int:branch_id>/staff/", api_branch_staff, name="api_branch_staff"),
    path("api/poll-new-orders/", api_poll_new_orders, name="api_poll_new_orders"),
    path("api/search-customers/", search_customers, name="search_customers"),
    path("api/search-categories/", search_categories, name="search_categories"),
    path("api/search-products/", search_products, name="search_products"),
        # Payme transaction dashboard APIs
        path("api/payme/transactions/", api_payme_transactions, name="api_payme_transactions"),
        path("api/payme/transactions/<str:tx_id>/", api_payme_transaction_detail, name="api_payme_transaction_detail"),
]
