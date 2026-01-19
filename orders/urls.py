"""
URL configuration for orders app.
"""

from django.urls import path
from .views import (
    ordersList, orderDetail, orderEdit, updateOrderStatus, deleteOrder,
    assignOrder, unassignOrder, receivePayment, completeOrder,
    api_order_stats, api_branch_staff, myOrders, orderCreate,
    record_order_payment, add_order_extra_fee, get_order_payment_info,
    bulk_delete_orders, search_customers, search_categories, search_products
)
from .bulk_payment_views import (
    bulk_payment_page, search_customers_with_debt, get_customer_debt_details,
    preview_payment_distribution, process_bulk_payment, payment_history, get_top_debtors_api
)

app_name = 'orders'

urlpatterns = [
    # Order list and detail
    path("", ordersList, name="ordersList"),
    path("my-orders/", myOrders, name="myOrders"),
    path("create/", orderCreate, name="orderCreate"),
    path("<int:order_id>/", orderDetail, name="orderDetail"),
    path("<int:order_id>/edit/", orderEdit, name="orderEdit"),
    
    # Order actions
    path("<int:order_id>/update-status/", updateOrderStatus, name="updateOrderStatus"),
    path("<int:order_id>/delete/", deleteOrder, name="deleteOrder"),
    path("bulk-delete/", bulk_delete_orders, name="bulk_delete_orders"),
    path("<int:order_id>/assign/", assignOrder, name="assignOrder"),
    path("<int:order_id>/unassign/", unassignOrder, name="unassignOrder"),
    path("<int:order_id>/receive-payment/", receivePayment, name="receivePayment"),
    path("<int:order_id>/complete/", completeOrder, name="completeOrder"),
    
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
    
    # API endpoints
    path("api/stats/", api_order_stats, name="api_order_stats"),
    path("api/branch/<int:branch_id>/staff/", api_branch_staff, name="api_branch_staff"),
    path("api/search-customers/", search_customers, name="search_customers"),
    path("api/search-categories/", search_categories, name="search_categories"),
    path("api/search-products/", search_products, name="search_products"),
]
