"""
URL configuration for orders app.
"""

from django.urls import path
from .views import ordersList, orderDetail, updateOrderStatus, deleteOrder

urlpatterns = [
    path("", ordersList, name="ordersList"),
    path("<int:order_id>/", orderDetail, name="orderDetail"),
    path("<int:order_id>/update-status/", updateOrderStatus, name="updateOrderStatus"),
    path("<int:order_id>/delete/", deleteOrder, name="deleteOrder"),
]
