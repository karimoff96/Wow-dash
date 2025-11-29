from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Order, OrderMedia


@login_required(login_url='admin_login')
def ordersList(request):
    """List all orders with search and filter"""
    orders = Order.objects.all().select_related('bot_user', 'product', 'language').order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(bot_user__name__icontains=search_query) |
            Q(bot_user__username__icontains=search_query) |
            Q(bot_user__phone__icontains=search_query) |
            Q(product__name__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Payment type filter
    payment_filter = request.GET.get('payment', '')
    if payment_filter:
        orders = orders.filter(payment_type=payment_filter)
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(orders, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get status choices for filter dropdown
    status_choices = Order.STATUS_CHOICES
    payment_choices = Order.PAYMENT_TYPE
    
    context = {
        "title": "Orders List",
        "subTitle": "Orders List",
        "orders": page_obj,
        "paginator": paginator,
        "search_query": search_query,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
        "per_page": per_page,
        "total_orders": paginator.count,
        "status_choices": status_choices,
        "payment_choices": payment_choices,
    }
    return render(request, "orders/ordersList.html", context)


@login_required(login_url='admin_login')
def orderDetail(request, order_id):
    """View order details"""
    order = get_object_or_404(Order.objects.select_related('bot_user', 'product', 'language'), id=order_id)
    
    context = {
        "title": f"Order #{order.id}",
        "subTitle": "Order Details",
        "order": order,
    }
    return render(request, "orders/orderDetail.html", context)


@login_required(login_url='admin_login')
def updateOrderStatus(request, order_id):
    """Update order status"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            order.save()
            messages.success(request, f'Order status updated from {old_status} to {new_status}')
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('orderDetail', order_id=order_id)


@login_required(login_url='admin_login')
def deleteOrder(request, order_id):
    """Delete an order"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        order.delete()
        messages.success(request, f'Order #{order_id} has been deleted')
        return redirect('ordersList')
    
    return redirect('orderDetail', order_id=order_id)
