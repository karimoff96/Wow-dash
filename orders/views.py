from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, F
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
import os
import logging
from .models import Order, OrderMedia, OrderPriceChange, PaymeTransaction
logger = logging.getLogger(__name__)
from organizations.rbac import (
    get_user_orders, get_user_staff, get_user_branches,
    admin_profile_required, role_required, manager_or_owner_required,
    permission_required, any_permission_required
)
from organizations.models import AdminUser, Branch, TranslationCenter
from core.audit import log_action, log_order_assign, log_status_change
from bot.notification_service import send_order_notification
from billing.decorators import require_feature, require_active_subscription, check_order_limit
from django.views.decorators.http import require_GET
from core.throttling import throttle


def has_order_permission(request, permission_name, order=None):
    """
    Check if user has a specific order permission.
    
    Args:
        request: The HTTP request with user and admin_profile
        permission_name: The permission to check (e.g., 'can_edit_orders')
        order: Optional Order object to check branch access
    
    Returns:
        bool: True if user has permission, False otherwise
    """
    # Superusers have all permissions
    if request.user.is_superuser:
        return True
    
    # Must have admin profile
    if not request.admin_profile:
        return False
    
    # Use has_permission method which handles master permissions properly
    if not request.admin_profile.has_permission(permission_name):
        return False
    
    # If order specified, check branch access
    if order and order.branch:
        accessible_branches = request.admin_profile.get_accessible_branches()
        if order.branch not in accessible_branches:
            return False
    
    # For staff-level users, restrict to their own orders if they lack broader permissions
    if not request.user.is_superuser:
        ap = request.admin_profile
        # If user only has can_view_own_orders, they can only see assigned orders
        if permission_name in ['can_view_own_orders', 'can_view_all_orders']:
            if not (ap.has_permission('can_view_all_orders') or ap.has_permission('can_manage_orders')):
                if order and order.assigned_to != ap:
                    return False
        # For edit/delete/status updates, restrict to assigned orders unless they can manage orders
        elif permission_name in ['can_edit_orders', 'can_delete_orders', 'can_update_order_status',
                                 'can_complete_orders', 'can_cancel_orders', 'can_edit_price']:
            if not (ap.has_permission('can_manage_orders') or ap.has_permission('can_assign_orders')):
                if order and order.assigned_to != ap:
                    return False
    
    return True


def get_user_order_permissions(request, order=None):
    """
    Get all order-related permissions for a user.
    Returns a dict of permission name -> boolean.
    """
    permissions = {
        'can_view_all_orders': has_order_permission(request, 'can_view_all_orders', order),
        'can_view_own_orders': has_order_permission(request, 'can_view_own_orders', order),
        'can_create_orders': has_order_permission(request, 'can_create_orders', order),
        'can_edit_orders': has_order_permission(request, 'can_edit_orders', order),
        'can_delete_orders': has_order_permission(request, 'can_delete_orders', order),
        'can_assign_orders': has_order_permission(request, 'can_assign_orders', order),
        'can_update_order_status': has_order_permission(request, 'can_update_order_status', order),
        'can_complete_orders': has_order_permission(request, 'can_complete_orders', order),
        'can_cancel_orders': has_order_permission(request, 'can_cancel_orders', order),
        'can_manage_orders': has_order_permission(request, 'can_manage_orders', order),
        'can_receive_payments': has_order_permission(request, 'can_receive_payments', order),
        'can_apply_discounts': has_order_permission(request, 'can_apply_discounts', order),
        'can_refund_orders': has_order_permission(request, 'can_refund_orders', order),
    }
    return permissions


@login_required(login_url='admin_login')
@require_GET
@any_permission_required('can_view_all_orders', 'can_manage_orders')
def api_payme_transactions(request):
    """Return Payme transactions for dashboard tables (JSON)."""
    qs = PaymeTransaction.objects.select_related('order').order_by('-created_at')

    state = request.GET.get('state')
    if state:
        try:
            qs = qs.filter(state=int(state))
        except ValueError:
            pass

    order_id = request.GET.get('order_id')
    if order_id:
        qs = qs.filter(order_id=order_id)

    limit = request.GET.get('limit')
    try:
        limit_val = int(limit) if limit else 100
    except ValueError:
        limit_val = 100
    qs = qs[: max(1, min(limit_val, 500))]

    data = []
    for tx in qs:
        data.append(
            {
                "payme_transaction_id": tx.payme_transaction_id,
                "order_id": tx.order_id,
                "state": tx.state,
                "amount_tiyin": tx.amount_tiyin,
                "amount_sum": tx.amount_sum,
                "create_time_ms": tx.create_time_ms,
                "perform_time_ms": tx.perform_time_ms,
                "cancel_time_ms": tx.cancel_time_ms,
                "cancel_reason": tx.cancel_reason,
                "created_at": tx.created_at,
            }
        )

    return JsonResponse({"transactions": data})


@login_required(login_url='admin_login')
@require_GET
@any_permission_required('can_view_all_orders', 'can_manage_orders')
def api_payme_transaction_detail(request, tx_id):
    """Return a single Payme transaction with raw payloads."""
    try:
        tx = PaymeTransaction.objects.select_related('order').get(payme_transaction_id=tx_id)
    except PaymeTransaction.DoesNotExist:
        return JsonResponse({"error": "not_found"}, status=404)

    payload = {
        "payme_transaction_id": tx.payme_transaction_id,
        "order_id": tx.order_id,
        "state": tx.state,
        "amount_tiyin": tx.amount_tiyin,
        "amount_sum": tx.amount_sum,
        "account": tx.account,
        "create_time_ms": tx.create_time_ms,
        "perform_time_ms": tx.perform_time_ms,
        "cancel_time_ms": tx.cancel_time_ms,
        "cancel_reason": tx.cancel_reason,
        "checkout_url": tx.checkout_url,
        "detail": tx.detail,
        "raw_request": tx.raw_request,
        "raw_response": tx.raw_response,
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
    }
    return JsonResponse(payload)


@login_required(login_url='admin_login')
@require_active_subscription
@require_feature('orders_basic')
@any_permission_required('can_view_all_orders', 'can_view_own_orders', 'can_manage_orders')
def ordersList(request):
    """List orders with search and filter - Permission-based access"""
    
    # Determine what orders user can see based on permissions
    can_view_all = request.user.is_superuser
    can_view_own_only = False
    
    if not request.user.is_superuser and request.admin_profile:
        can_view_all = request.admin_profile.has_permission('can_view_all_orders')
        can_view_own_only = request.admin_profile.has_permission('can_view_own_orders') and not can_view_all
    
    # Get base queryset based on permissions
    if request.user.is_superuser:
        orders = Order.objects.all()
    elif can_view_all:
        # User can view all orders in their scope (branch/center)
        orders = get_user_orders(request.user)
    elif can_view_own_only:
        # User can only view orders assigned to them
        orders = Order.objects.filter(assigned_to=request.admin_profile)
    elif request.admin_profile:
        # Fallback: user has admin profile but no specific order permissions
        # Show orders in their scope (same as can_view_all but they'll have limited actions)
        orders = get_user_orders(request.user)
        can_view_all = True  # For UI purposes - they can see all but with limited actions
    else:
        # No admin profile - show nothing
        orders = Order.objects.none()
    
    orders = orders.select_related(
        'bot_user', 'product', 'language', 'branch', 'branch__center',
        'assigned_to', 'assigned_to__user'
    ).prefetch_related('receipts').order_by('-created_at')
    
    # View mode filter (for users who can view all - let them switch to "my orders" view)

    view_mode = request.GET.get('view', 'all' if can_view_all else 'mine')
    if can_view_all and view_mode == 'mine' and request.admin_profile:
        orders = orders.filter(assigned_to=request.admin_profile)
    
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
    if payment_filter == 'payme':
        orders = orders.filter(payment_source='payme')
    elif payment_filter:
        # 'card' filter → manual card transfers only (exclude Payme)
        if payment_filter == 'card':
            orders = orders.filter(payment_type='card', payment_source='manual')
        else:
            orders = orders.filter(payment_type=payment_filter)
    
    # Center filter (for superusers only)
    center_filter = request.GET.get('center', '')
    if center_filter and request.user.is_superuser:
        orders = orders.filter(branch__center_id=center_filter)
    
    # Branch filter (for owners/superusers who can see multiple branches)
    branch_filter = request.GET.get('branch', '')
    if branch_filter:
        orders = orders.filter(branch_id=branch_filter)
    
    # Staff filter - assigned_to
    staff_filter = request.GET.get('staff', '')
    assigned_to_filter = request.GET.get('assigned_to', '') or staff_filter  # Support both parameter names
    exclude_completed = request.GET.get('exclude_completed', '')
    if assigned_to_filter:
        orders = orders.filter(assigned_to_id=assigned_to_filter)
        if exclude_completed == '1':
            orders = orders.exclude(status='completed')
    
    # Staff filter - completed orders (completed_by OR assigned+completed)
    staff_completed_filter = request.GET.get('staff_completed', '')
    if staff_completed_filter:
        orders = orders.filter(
            Q(completed_by_id=staff_completed_filter) | Q(assigned_to_id=staff_completed_filter, status='completed')
        )
    
    # Staff filter - completed_by (legacy, keeping for backward compatibility)
    completed_by_filter = request.GET.get('completed_by', '')
    if completed_by_filter and not staff_completed_filter:
        orders = orders.filter(completed_by_id=completed_by_filter)
    
    # Assignment filter (only show for users who can view all)
    assignment_filter = request.GET.get('assignment', '')
    if can_view_all:
        if assignment_filter == 'unassigned':
            orders = orders.filter(assigned_to__isnull=True)
        elif assignment_filter == 'assigned':
            orders = orders.filter(assigned_to__isnull=False)
    
    # Pending receipts filter - show orders with pending receipts
    has_pending_receipts = request.GET.get('has_pending_receipts', '')
    if has_pending_receipts == 'true':
        orders = orders.filter(receipts__status='pending').distinct()

    # New orders filter - pending and unassigned (no staff action taken)
    new_only = request.GET.get('new_only', '')
    if new_only == '1':
        orders = orders.filter(status='pending', assigned_to__isnull=True)

    # Overdue filter - orders with past deadline that are not completed/cancelled
    overdue_only = request.GET.get('overdue_only', '')
    if overdue_only == '1':
        orders = orders.filter(
            deadline__lt=timezone.now().date()
        ).exclude(status__in=['completed', 'cancelled'])

    # Date range filters
    date_field = request.GET.get('date_field', 'created_at')
    if date_field not in ['created_at', 'updated_at']:
        date_field = 'created_at'

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    date_preset = request.GET.get('date_preset', '')
    tz = timezone.get_current_timezone()

    if date_from:
        parsed_from = parse_date(date_from)
        if parsed_from:
            start_dt = timezone.make_aware(datetime.combine(parsed_from, time.min), tz)
            orders = orders.filter(**{f"{date_field}__gte": start_dt})

    if date_to:
        parsed_to = parse_date(date_to)
        if parsed_to:
            end_dt = timezone.make_aware(datetime.combine(parsed_to, time.max), tz)
            orders = orders.filter(**{f"{date_field}__lte": end_dt})

    # Sort order
    sort_by = request.GET.get('sort_by', '')
    if sort_by == 'deadline':
        # Upcoming deadlines first; orders without deadline appear at end
        orders = orders.order_by(F('deadline').asc(nulls_last=True))
    elif sort_by == 'deadline_desc':
        orders = orders.order_by(F('deadline').desc(nulls_last=True))
    else:
        orders = orders.order_by('-created_at')

    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(orders, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = Order.STATUS_CHOICES
    payment_choices = list(Order.PAYMENT_TYPE) + [("payme", "Payme")]
    
    # Get accessible branches for filter dropdown
    branches = get_user_branches(request.user) if not request.user.is_superuser else None
    centers = None
    staff_members = None
    
    if request.user.is_superuser:
        from organizations.models import Branch, TranslationCenter, AdminUser
        branches = Branch.objects.filter(is_active=True).select_related('center')
        centers = TranslationCenter.objects.filter(is_active=True)
        staff_members = AdminUser.objects.filter(user__is_active=True).select_related('user', 'role', 'branch', 'center').order_by('user__first_name', 'user__last_name')
    else:
        # Non-superusers: get staff from accessible branches
        from organizations.models import AdminUser
        accessible_branches = get_user_branches(request.user)
        staff_members = AdminUser.objects.filter(
            branch__in=accessible_branches,
            user__is_active=True
        ).select_related('user', 'role', 'branch', 'center').order_by('user__first_name', 'user__last_name')
    
    # Get order statistics based on what user can see
    if request.user.is_superuser:
        base_orders = Order.objects.all()
    elif can_view_all:
        base_orders = get_user_orders(request.user)
    else:
        base_orders = Order.objects.filter(assigned_to=request.admin_profile) if request.admin_profile else Order.objects.none()

    # Unfiltered totals — used only for the tab badge counts
    base_stats = {
        'total': base_orders.count(),
    }

    # Filtered stats — computed from the same queryset that was built up with all
    # active filters (date range, status, branch, search, etc.) so the stat cards
    # always reflect what the user is currently looking at.
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status='pending').count(),
        'in_progress': orders.filter(status='in_progress').count(),
        'completed': orders.filter(status='completed').count(),
        'unassigned': orders.filter(assigned_to__isnull=True).count() if can_view_all else 0,
        'new': base_orders.filter(status='pending', assigned_to__isnull=True).count(),
    }
    
    # Stats for "my orders" (for users who can view all)
    my_stats = None
    if can_view_all and request.admin_profile:
        my_orders = Order.objects.filter(assigned_to=request.admin_profile)
        my_stats = {
            'total': my_orders.count(),
            'in_progress': my_orders.filter(status='in_progress').count(),
            'completed': my_orders.filter(status='completed').count(),
        }
    
    # Count orders with pending receipts
    pending_receipts_count = base_orders.filter(receipts__status='pending').distinct().count()
    
    # Check if user can create orders
    can_create_orders = request.user.is_superuser
    if not can_create_orders and request.admin_profile:
        can_create_orders = request.admin_profile.has_permission('can_create_orders')
    
    context = {
        "title": _("Orders with Pending Receipts") if has_pending_receipts == 'true' else (_("My Orders") if (can_view_own_only or view_mode == 'mine') else _("Orders")),
        "subTitle": _("Review uploaded payment receipts") if has_pending_receipts == 'true' else (_("Orders assigned to me") if (can_view_own_only or view_mode == 'mine') else _("All Orders")),
        "title_i18n": "orders.pendingReceipts" if has_pending_receipts == 'true' else ("orders.myOrders" if (can_view_own_only or view_mode == 'mine') else "orders.allOrders"),
        "orders": page_obj,
        "paginator": paginator,
        "search_query": search_query,
        "status_filter": status_filter,
        "payment_filter": payment_filter,
        "center_filter": center_filter,
        "branch_filter": branch_filter,
        "assignment_filter": assignment_filter,
        "staff_filter": staff_filter,
        "has_pending_receipts": has_pending_receipts,
        "pending_receipts_count": pending_receipts_count,
        "new_only": new_only,
        "sort_by": sort_by,
        "overdue_only": overdue_only,
        "today": timezone.now().date(),
        "date_field": date_field,
        "date_from": date_from,
        "date_to": date_to,
        "date_preset": date_preset,
        "per_page": per_page,
        "total_orders": paginator.count,
        "status_choices": status_choices,
        "payment_choices": payment_choices,
        "centers": centers,
        "branches": branches,
        "staff_members": staff_members,
        "stats": stats,
        "base_stats": base_stats,
        "my_stats": my_stats,
        "can_view_all": can_view_all,
        "can_view_own_only": can_view_own_only,
        "view_mode": view_mode,
        "can_create_orders": can_create_orders,
    }
    return render(request, "orders/ordersList.html", context)


@login_required(login_url='admin_login')
@require_active_subscription
@require_feature('orders_basic')
@any_permission_required('can_view_all_orders', 'can_view_own_orders', 'can_manage_orders')
def orderDetail(request, order_id):
    """View order details with permission-based access control"""
    order = get_object_or_404(
        Order.objects.select_related(
            'bot_user', 'product', 'language', 'branch', 'branch__center',
            'assigned_to', 'assigned_to__user', 'assigned_by', 'assigned_by__user',
            'payment_received_by', 'payment_received_by__user',
            'completed_by', 'completed_by__user',
            'created_by', 'created_by__user'
        ), 
        id=order_id
    )
    
    # Check view permission
    can_view = has_order_permission(request, 'can_view_all_orders', order)
    if not can_view:
        # Check if user can view their own orders and this is assigned to them
        if request.admin_profile and order.assigned_to == request.admin_profile:
            if has_order_permission(request, 'can_view_own_orders', order):
                can_view = True
    
    if not can_view:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('orders:ordersList')
    
    # Get all order permissions for current user
    order_permissions = get_user_order_permissions(request, order)
    
    # Get available staff for assignment
    available_staff = []
    if order_permissions['can_assign_orders']:
        # Get staff from the order's branch, or all staff if no branch
        if request.user.is_superuser:
            if order.branch:
                available_staff = AdminUser.objects.filter(
                    branch=order.branch,
                    is_active=True
                ).select_related('user', 'role')
            else:
                available_staff = AdminUser.objects.filter(
                    is_active=True
                ).select_related('user', 'role')
        elif request.admin_profile:
            if order.branch:
                available_staff = AdminUser.objects.filter(
                    branch=order.branch,
                    is_active=True
                ).select_related('user', 'role')
            else:
                accessible_branches = request.admin_profile.get_accessible_branches()
                available_staff = AdminUser.objects.filter(
                    branch__in=accessible_branches,
                    is_active=True
                ).select_related('user', 'role')
    
    # Get allowed status transitions based on current status
    allowed_transitions = get_allowed_status_transitions(order.status)
    
    # Get detailed price breakdown
    price_breakdown = order.get_price_breakdown()

    # Price change history
    price_changes = order.price_changes.select_related('changed_by', 'changed_by__user').order_by('-changed_at')

    # Internal comments
    from .models import OrderComment
    order_comments = order.comments.select_related('author', 'author__user').order_by('created_at')

    # can_edit_price: dedicated permission or financial/order management masters
    can_edit_price = (
        request.user.is_superuser or bool(
            request.admin_profile and (
                request.admin_profile.has_permission('can_edit_price') or
                request.admin_profile.has_permission('can_manage_orders') or
                request.admin_profile.has_permission('can_manage_financial')
            )
        )
    )

    # can_force_accept: ability to override payment totals (requires financial management permission)
    can_force_accept = (
        request.user.is_superuser or
        bool(request.admin_profile and request.admin_profile.has_permission('can_manage_financial'))
    )

    context = {
        "title": f"Order #{order.id}",
        "subTitle": _("Order Details"),
        "title_i18n": "detail.orderDetails",
        "order": order,
        "price_breakdown": price_breakdown,
        "price_changes": price_changes,
        "can_edit_price": can_edit_price,
        "can_force_accept": can_force_accept,
        "available_staff": available_staff,
        # Permission flags from the granular permission system
        "can_assign": order_permissions['can_assign_orders'],
        "can_update_status": order_permissions['can_update_order_status'],
        "can_receive_payment": order_permissions['can_receive_payments'],
        "can_complete": order_permissions['can_complete_orders'],
        "can_edit": order_permissions['can_edit_orders'],
        "can_delete": order_permissions['can_delete_orders'],
        "can_cancel": order_permissions['can_cancel_orders'],
        # All order permissions for template use
        "order_permissions": order_permissions,
        "allowed_transitions": allowed_transitions,
        "status_choices": Order.STATUS_CHOICES,
        "order_comments": order_comments,
        "can_manage_comments": (
            request.user.is_superuser or
            bool(request.admin_profile and request.admin_profile.has_permission('can_manage_orders'))
        ),
    }
    return render(request, "orders/orderDetail.html", context)


@login_required(login_url='admin_login')
@require_active_subscription
@require_feature('orders_advanced')
@any_permission_required('can_edit_orders', 'can_manage_orders')
def orderEdit(request, order_id):
    """Edit an order - permission-based access control"""
    from services.models import Product, Language
    from accounts.models import BotUser
    
    order = get_object_or_404(
        Order.objects.select_related(
            'bot_user', 'product', 'product__category', 
            'product__category__branch', 'product__category__branch__center',
            'language', 'branch', 'branch__center'
        ),
        id=order_id
    )
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_edit_orders', order):
        messages.error(request, "You don't have permission to edit this order.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Get accessible centers and branches
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        branches = Branch.objects.filter(is_active=True).select_related('center')
        # Superuser sees all products
        products = Product.objects.filter(is_active=True)
        # Superuser sees all customers
        bot_users = BotUser.objects.all().order_by('-created_at')
    elif request.admin_profile:
        branches = request.admin_profile.get_accessible_branches()
        # Filter products by accessible branches (Product -> Category -> Branch)
        branch_ids = branches.values_list('id', flat=True)
        products = Product.objects.filter(
            is_active=True,
            category__branch_id__in=branch_ids
        ).select_related('category', 'category__branch')
        
        # Get bot users based on accessible branches
        # Check if user can access center-level customers
        if request.admin_profile.has_permission('can_view_centers') or request.admin_profile.has_permission('can_manage_centers'):
            # Center owner/manager - get all customers from their center
            # Include both: BotUsers with center FK set AND those linked via their branch
            center = request.admin_profile.center
            if center:
                from django.db.models import Q as _Q
                bot_users = BotUser.objects.filter(
                    _Q(center=center) | _Q(branch__center=center)
                ).order_by('-created_at').distinct()
            else:
                bot_users = BotUser.objects.none()
        else:
            # Branch-level staff - get customers from accessible branches
            bot_users = BotUser.objects.filter(branch_id__in=branch_ids).order_by('-created_at')

        # Always ensure the order's existing bot_user is in the list (even if outside normal scope)
        if order.bot_user and not bot_users.filter(pk=order.bot_user_id).exists():
            from django.db.models import Q as _Q2
            bot_users = BotUser.objects.filter(
                _Q2(pk=order.bot_user_id) | _Q2(pk__in=bot_users.values_list('pk', flat=True))
            ).order_by('-created_at')
    else:
        branches = Branch.objects.none()
        products = Product.objects.none()
        bot_users = BotUser.objects.none()
    
    # Languages are global - no filtering needed
    languages = Language.objects.all()  # Language model doesn't have is_active field
    
    if request.method == 'POST':
        # Get form data
        bot_user_id = request.POST.get('bot_user')
        manual_first_name = request.POST.get('manual_first_name', '').strip()
        manual_last_name = request.POST.get('manual_last_name', '').strip()
        manual_phone = request.POST.get('manual_phone', '').strip()
        branch_id = request.POST.get('branch')
        product_id = request.POST.get('product')
        language_id = request.POST.get('language')
        total_pages = request.POST.get('total_pages')
        copy_number = request.POST.get('copy_number', 0)
        payment_type = request.POST.get('payment_type')
        description = request.POST.get('description', '')
        extra_fee = request.POST.get('extra_fee', 0)
        extra_fee_description = request.POST.get('extra_fee_description', '')
        
        # Store old values for audit
        old_values = {
            'bot_user': str(order.bot_user) if order.bot_user else None,
            'manual_first_name': order.manual_first_name,
            'manual_last_name': order.manual_last_name,
            'manual_phone': order.manual_phone,
            'branch': str(order.branch) if order.branch else None,
            'product': str(order.product),
            'language': str(order.language) if order.language else None,
            'total_pages': order.total_pages,
            'copy_number': order.copy_number,
            'payment_type': order.payment_type,
            'total_price': str(order.total_price),
            'extra_fee': str(order.extra_fee),
            'extra_fee_description': order.extra_fee_description,
            'description': order.description,
            'files_count': order.files.count(),
        }
        
        try:
            # Update customer information
            # Determine if this is a manual order or bot user order
            is_manual_order = bool(manual_first_name and manual_phone)
            
            if is_manual_order:
                # Manual order - update manual fields
                order.manual_first_name = manual_first_name
                order.manual_last_name = manual_last_name
                order.manual_phone = manual_phone
                # Try to get or create bot_user with this phone (for consistency)
                if manual_phone:
                    _edit_branch = order.branch
                    _edit_center = _edit_branch.center if _edit_branch else None
                    bot_user, created = BotUser.objects.get_or_create(
                        phone=manual_phone,
                        defaults={
                            'name': f"{manual_first_name} {manual_last_name}".strip(),
                            'user_id': None,
                            'username': None,
                            'is_active': True,
                            'branch': _edit_branch,
                            'center': _edit_center,
                        }
                    )
                    _edit_fields = []
                    if not bot_user.is_active:
                        bot_user.is_active = True
                        _edit_fields.append('is_active')
                    if not bot_user.branch and _edit_branch:
                        bot_user.branch = _edit_branch
                        _edit_fields.append('branch')
                    if not bot_user.center and _edit_center:
                        bot_user.center = _edit_center
                        _edit_fields.append('center')
                    if _edit_fields:
                        _edit_fields.append('updated_at')
                        bot_user.save(update_fields=_edit_fields)
                    order.bot_user = bot_user
            elif bot_user_id:
                # Bot user order - update bot_user reference; validate cross-center access
                _new_bot_user = BotUser.objects.get(pk=bot_user_id)
                if not request.user.is_superuser and request.admin_profile:
                    _accessible_branches = request.admin_profile.get_accessible_branches()
                    _customer_in_scope = (
                        (_new_bot_user.branch_id and _accessible_branches.filter(pk=_new_bot_user.branch_id).exists()) or
                        (request.admin_profile.center_id and _new_bot_user.center_id == request.admin_profile.center_id)
                    )
                    if not _customer_in_scope:
                        raise PermissionError("Customer outside your accessible scope.")
                order.bot_user = _new_bot_user
                # Clear manual fields
                order.manual_first_name = None
                order.manual_last_name = None
                order.manual_phone = None
            
            # Update order
            if branch_id:
                _new_branch = Branch.objects.get(pk=branch_id)
                if not request.user.is_superuser and request.admin_profile:
                    _accessible_branches = request.admin_profile.get_accessible_branches()
                    if not _accessible_branches.filter(pk=_new_branch.pk).exists():
                        raise PermissionError("Branch outside your accessible scope.")
                order.branch = _new_branch
            if product_id:
                order.product = Product.objects.get(pk=product_id)
            if language_id:
                order.language = Language.objects.get(pk=language_id)
            elif language_id == '':
                order.language = None
            
            order.total_pages = int(total_pages) if total_pages else order.total_pages
            order.copy_number = int(copy_number) if copy_number else 0
            order.payment_type = payment_type if payment_type else order.payment_type
            order.description = description

            # Deadline (optional)
            from datetime import date as _date
            deadline_str = (request.POST.get('deadline') or '').strip()
            if deadline_str:
                try:
                    order.deadline = _date.fromisoformat(deadline_str)
                except ValueError:
                    pass
            else:
                order.deadline = None
            
            # Handle receipt upload/replacement
            if 'recipt' in request.FILES:
                # Delete old receipt if exists
                if order.recipt:
                    order.recipt.delete(save=False)
                order.recipt = request.FILES['recipt']
            
            # Handle file deletions
            files_to_delete = request.POST.getlist('delete_files')
            if files_to_delete:
                for file_id in files_to_delete:
                    try:
                        file_obj = OrderMedia.objects.get(pk=file_id)
                        order.files.remove(file_obj)
                        file_obj.delete()
                    except OrderMedia.DoesNotExist:
                        pass
            
            # Handle new file uploads
            new_files = request.FILES.getlist('new_files')
            for uploaded_file in new_files:
                # Create OrderMedia instance
                file_pages = request.POST.get(f'file_pages_{uploaded_file.name}', 1)
                try:
                    file_pages = int(file_pages)
                except (ValueError, TypeError):
                    file_pages = 1
                
                order_media = OrderMedia.objects.create(
                    file=uploaded_file,
                    pages=file_pages
                )
                order.files.add(order_media)

            # Handle additional file deletions
            additional_files_to_delete = request.POST.getlist('delete_additional_files')
            if additional_files_to_delete:
                for file_id in additional_files_to_delete:
                    try:
                        file_obj = OrderMedia.objects.get(pk=file_id)
                        order.additional_files.remove(file_obj)
                        file_obj.delete()
                    except OrderMedia.DoesNotExist:
                        pass

            # Handle new additional file uploads
            new_additional_files = request.FILES.getlist('new_additional_files')
            for uploaded_file in new_additional_files:
                order_media = OrderMedia.objects.create(
                    file=uploaded_file,
                    pages=1
                )
                order.additional_files.add(order_media)
            
            # Recalculate price — skip if a manual price override exists
            if not order.price_changes.exists():
                order.total_price = order.calculated_price
            
            # Update extra fee
            try:
                order.extra_fee = Decimal(extra_fee) if extra_fee else Decimal('0')
            except (ValueError, InvalidOperation):
                order.extra_fee = Decimal('0')
            order.extra_fee_description = extra_fee_description
            
            order.save()
            
            # Audit log the edit
            new_values = {
                'bot_user': str(order.bot_user) if order.bot_user else None,
                'manual_first_name': order.manual_first_name,
                'manual_last_name': order.manual_last_name,
                'manual_phone': order.manual_phone,
                'branch': str(order.branch) if order.branch else None,
                'product': str(order.product),
                'language': str(order.language) if order.language else None,
                'total_pages': order.total_pages,
                'copy_number': order.copy_number,
                'payment_type': order.payment_type,
                'total_price': str(order.total_price),
                'extra_fee': str(order.extra_fee),
                'extra_fee_description': order.extra_fee_description,
                'description': order.description,
                'files_count': order.files.count(),
            }
            
            log_action(
                user=request.user,
                action='update',
                target=order,
                details=f'Order #{order.id} edited',
                changes={'old': old_values, 'new': new_values},
                request=request
            )
            
            messages.success(request, f'Order #{order_id} updated successfully.')
            return_page = request.POST.get('return_page', '')
            if return_page:
                return redirect(reverse('orders:ordersList') + f'?page={return_page}')
            return redirect('orders:orderDetail', order_id=order_id)
            
        except PermissionError as pe:
            messages.error(request, _("You don't have permission to make that change: ") + str(pe))
            return redirect('orders:orderDetail', order_id=order_id)
        except Exception as e:
            messages.error(request, f'Error updating order: {str(e)}')
    
    price_changes = order.price_changes.select_related('changed_by', 'changed_by__user').order_by('-changed_at')

    # can_edit_price: dedicated permission or financial/order management masters
    can_edit_price = (
        request.user.is_superuser or bool(
            request.admin_profile and (
                request.admin_profile.has_permission('can_edit_price') or
                request.admin_profile.has_permission('can_manage_orders') or
                request.admin_profile.has_permission('can_manage_financial')
            )
        )
    )
    context = {
        "title": f"Edit Order #{order.id}",
        "subTitle": _("Edit Order"),
        "title_i18n": "orders.editOrderTitle",
        "order": order,
        "centers": centers,
        "branches": branches,
        "products": products,
        "languages": languages,
        "bot_users": bot_users,
        "payment_choices": Order.PAYMENT_TYPE,
        "is_superuser": request.user.is_superuser,
        "price_changes": price_changes,
        "can_edit_price": can_edit_price,
    }
    return render(request, "orders/orderEdit.html", context)


def get_allowed_status_transitions(current_status):
    """Get allowed status transitions from current status"""
    transitions = {
        'pending': ['payment_pending', 'cancelled'],
        'payment_pending': ['payment_received', 'cancelled'],
        'payment_received': ['payment_confirmed', 'payment_pending'],
        'payment_confirmed': ['in_progress', 'cancelled'],
        'in_progress': ['ready', 'cancelled'],
        'ready': ['completed', 'in_progress'],
        'completed': [],
        'cancelled': ['pending'],  # Allow reactivation
    }
    return transitions.get(current_status, [])


@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_update_order_status', 'can_complete_orders', 'can_cancel_orders', 'can_manage_orders')
def updateOrderStatus(request, order_id):
    """Update order status with permission-based access control"""
    order = get_object_or_404(Order, id=order_id)
    
    new_status = request.POST.get('status')
    
    # Determine which permission is needed based on target status
    if new_status == 'completed':
        required_permission = 'can_complete_orders'
    elif new_status == 'cancelled':
        required_permission = 'can_cancel_orders'
    else:
        required_permission = 'can_update_order_status'
    
    # Check permission
    if not has_order_permission(request, required_permission, order):
        messages.error(request, f"You don't have permission to change order status.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    if new_status not in dict(Order.STATUS_CHOICES):
        messages.error(request, 'Invalid status')
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Validate status transition
    allowed_transitions = get_allowed_status_transitions(order.status)
    if new_status not in allowed_transitions:
        messages.error(request, f'Cannot change status from {order.get_status_display()} to {dict(Order.STATUS_CHOICES).get(new_status)}')
        return redirect('orders:orderDetail', order_id=order_id)
    
    old_status = order.status
    admin_profile = request.admin_profile
    
    # Use helper methods for special status changes
    if new_status == 'payment_confirmed' and admin_profile:
        order.mark_payment_received(admin_profile)
    elif new_status == 'completed' and admin_profile:
        order.mark_completed(admin_profile)
    else:
        order.status = new_status
        order.save()
    
    # Audit log the status change
    log_status_change(
        user=request.user,
        order=order,
        old_status=old_status,
        new_status=new_status,
        request=request
    )
    
    messages.success(request, f'Order status updated from {dict(Order.STATUS_CHOICES).get(old_status)} to {dict(Order.STATUS_CHOICES).get(new_status)}')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'new_status': new_status,
            'new_status_display': order.get_status_display(),
        })
    
    return redirect('orders:orderDetail', order_id=order_id)


@login_required(login_url='admin_login')
@require_POST
@require_active_subscription
@require_feature('orders_advanced')
@any_permission_required('can_delete_orders', 'can_manage_orders')
def deleteOrder(request, order_id):
    """Delete an order - permission-based access control"""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check permission using granular permission system
        if not has_order_permission(request, 'can_delete_orders', order):
            messages.error(request, "You don't have permission to delete orders.")
            return redirect('orders:ordersList')
        
        # Store order info before deletion
        order_number = order.get_order_number()
        
        # Audit log before deletion
        try:
            log_action(
                user=request.user,
                action='delete',
                target=order,
                details=f'Order #{order.id} deleted',
                changes={'order_id': order.id, 'status': order.status},
                request=request
            )
        except Exception as log_error:
            # Log the error but continue with deletion
            import logging
            logging.getLogger(__name__).warning(f"Failed to log deletion: {log_error}")
        
        # Delete the order
        order.delete()
        messages.success(request, f'Order {order_number} has been deleted successfully')
        return redirect('orders:ordersList')
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error deleting order {order_id}: {str(e)}")
        messages.error(request, f"Failed to delete order: {str(e)}")
        return redirect('orders:ordersList')


@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_assign_orders', 'can_manage_orders')
def assignOrder(request, order_id):
    """Assign an order to a staff member - permission-based access control"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_assign_orders', order):
        messages.error(request, "You don't have permission to assign orders.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    staff_id = request.POST.get('staff_id')
    if not staff_id:
        messages.error(request, "Please select a staff member.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    try:
        staff_member = AdminUser.objects.get(pk=staff_id, is_active=True)
    except AdminUser.DoesNotExist:
        messages.error(request, "Invalid staff member selected.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # For superusers, allow any assignment - also set the order's branch if not set
    if request.user.is_superuser:
        if not order.branch and staff_member.branch:
            order.branch = staff_member.branch
            order.save(update_fields=['branch'])
    else:
        # Verify staff is in the same branch as the order (if order has a branch)
        if order.branch and staff_member.branch != order.branch:
            messages.error(request, "Staff member must be in the same branch as the order.")
            return redirect('orders:orderDetail', order_id=order_id)
    
    # Assign the order
    assigner = request.admin_profile if request.admin_profile else None
    order.assign_to_staff(staff_member, assigner)
    
    # Audit log the assignment
    log_order_assign(
        user=request.user,
        order=order,
        staff=staff_member,
        request=request
    )
    
    messages.success(request, f'Order #{order_id} assigned to {staff_member.user.get_full_name() or staff_member.user.username}')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'assigned_to': str(staff_member),
            'assigned_at': order.assigned_at.isoformat() if order.assigned_at else None,
        })
    
    return redirect('orders:orderDetail', order_id=order_id)


@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_assign_orders', 'can_manage_orders')
def unassignOrder(request, order_id):
    """Unassign an order from a staff member - owners/managers only"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_assign_orders', order):
        messages.error(request, "You don't have permission to unassign orders.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Clear assignment
    previous_assignee = order.assigned_to
    previous_assignee_name = str(previous_assignee) if previous_assignee else None
    order.assigned_to = None
    order.assigned_by = None
    order.assigned_at = None
    if order.status == 'in_progress':
        order.status = 'payment_confirmed'
    order.save()
    
    # Audit log the unassignment
    log_action(
        user=request.user,
        action='assign',
        target=order,
        details=f'Order #{order.id} unassigned from {previous_assignee_name}',
        changes={
            'action': 'unassigned',
            'previous_assignee': previous_assignee_name,
        },
        request=request
    )
    
    messages.success(request, f'Order #{order_id} has been unassigned')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('orders:orderDetail', order_id=order_id)


@login_required(login_url='admin_login')
@require_POST
@require_active_subscription
@require_feature('orders_advanced')
def bulk_delete_orders(request):
    """Bulk delete multiple orders - permission-based access control"""
    # Try both formats: order_ids[] and order_ids
    order_ids = request.POST.getlist('order_ids[]') or request.POST.getlist('order_ids')
    
    if not order_ids:
        return JsonResponse({'success': False, 'message': 'No orders selected'}, status=400)
    
    # Check if user has delete permission
    if not request.user.is_superuser:
        if hasattr(request, 'admin_profile') and request.admin_profile:
            if not request.admin_profile.has_permission('can_delete_orders'):
                return JsonResponse({'success': False, 'message': 'You don\'t have permission to delete orders'}, status=403)
        else:
            return JsonResponse({'success': False, 'message': 'Permission denied'}, status=403)
    
    try:
        # Get orders that the user can delete based on permissions
        orders = Order.objects.filter(id__in=order_ids)
        
        # For non-superusers, filter to only orders they can access
        if not request.user.is_superuser:
            accessible_orders = get_user_orders(request.user)
            orders = orders.filter(id__in=accessible_orders.values_list('id', flat=True))
        
        deleted_count = orders.count()
        
        if deleted_count == 0:
            return JsonResponse({'success': False, 'message': 'No orders found or you don\'t have permission to delete them'}, status=404)
        
        # Log each deletion
        for order in orders:
            log_action(
                user=request.user,
                action='delete',
                target=order,
                details=f'Order #{order.id} deleted (bulk delete)',
                changes={'order_id': order.id, 'status': order.status},
                request=request
            )
        
        # Delete all orders
        orders.delete()
        
        logger.info(f"{deleted_count} orders deleted by {request.user.username} (bulk delete)")
        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} order(s) deleted successfully',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Error in bulk delete orders: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Error deleting orders: {str(e)}'}, status=500)


@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_receive_payments', 'can_manage_financial', 'can_manage_orders')
def receivePayment(request, order_id):
    """Mark payment as received - permission-based access control"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_receive_payments', order):
        messages.error(request, "You don't have permission to receive payments.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Mark payment received
    receiver = request.admin_profile if request.admin_profile else None
    order.mark_payment_received(receiver)
    
    messages.success(request, f'Payment received for Order #{order_id}')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'new_status': order.status,
            'new_status_display': order.get_status_display(),
        })
    
    return redirect('orders:orderDetail', order_id=order_id)


@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_complete_orders', 'can_manage_orders')
def completeOrder(request, order_id):
    """Mark order as completed - permission-based access control"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_complete_orders', order):
        messages.error(request, "You don't have permission to complete orders.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Check if order is ready to be completed
    if order.status not in ['ready', 'in_progress']:
        messages.error(request, "Order must be ready or in progress to complete.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Mark completed
    completer = request.admin_profile if request.admin_profile else None
    order.mark_completed(completer)
    
    messages.success(request, f'Order #{order_id} marked as completed')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'new_status': order.status,
            'new_status_display': order.get_status_display(),
        })
    
    return redirect('orders:orderDetail', order_id=order_id)


# ============ API Endpoints ============

@login_required(login_url='admin_login')
def api_order_stats(request):
    """
    API endpoint for order statistics.

    Redis cache strategy (60-second TTL, per-user key):
    - On hit:  return immediately — zero additional DB queries.
    - On miss: run the original 10 COUNT queries, cache result, return data.
    - On Redis failure: run the original 10 COUNT queries (try/except).
    Invalidation is TTL-based (60 s is accurate enough for a stats bar).
    For immediate accuracy after status changes, the TTL is kept short.
    """
    CACHE_KEY = f'orderstats:user:{request.user.pk}'
    CACHE_TTL = 60  # seconds

    # ── Fast path ──────────────────────────────────────────────────
    try:
        from django.core.cache import cache
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return JsonResponse(cached)
    except Exception:
        pass  # Redis unavailable — fall through

    # ── Slow path: original DB logic (unchanged) ───────────────────
    if request.user.is_superuser:
        base_orders = Order.objects.all()
    else:
        base_orders = get_user_orders(request.user)

    stats = {
        'total': base_orders.count(),
        'pending': base_orders.filter(status='pending').count(),
        'payment_pending': base_orders.filter(status='payment_pending').count(),
        'payment_received': base_orders.filter(status='payment_received').count(),
        'payment_confirmed': base_orders.filter(status='payment_confirmed').count(),
        'in_progress': base_orders.filter(status='in_progress').count(),
        'ready': base_orders.filter(status='ready').count(),
        'completed': base_orders.filter(status='completed').count(),
        'cancelled': base_orders.filter(status='cancelled').count(),
        'unassigned': base_orders.filter(assigned_to__isnull=True).exclude(
            status__in=['completed', 'cancelled']
        ).count(),
    }

    # ── Store in cache ─────────────────────────────────────────
    try:
        from django.core.cache import cache
        cache.set(CACHE_KEY, stats, timeout=CACHE_TTL)
    except Exception:
        pass  # Redis write failure is harmless

    return JsonResponse(stats)


@login_required(login_url='admin_login')
@require_feature('orders_basic')
@throttle(max_calls=30, period=60, key_prefix='api_poll')  # max 30 polls/min per user
def api_poll_new_orders(request):
    """
    Lightweight polling endpoint for real-time new-order detection.

    Strategy (zero DB hit on the happy path):
      1. Read a single Redis key (O(1)) that holds the unix timestamp of the
         last created order in scope.
      2. Compare with the client's `since` timestamp.
      3. If the cache key is absent OR its value <= since  →  no new orders,
         return immediately with no DB query.
      4. Only when cache says "something new" do we hit the DB for the exact
         count – and even then it's a cheap COUNT query on an indexed field.

    Query params:
      since  (float, required) – unix timestamp the client last polled from.

    Response JSON:
      {has_new: bool, count: int, latest_ts: float}
    """
    # Validate `since`
    try:
        since_ts = float(request.GET.get('since', 0))
    except (ValueError, TypeError):
        return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': 0})

    if since_ts <= 0:
        return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': 0})

    import time
    from django.core.cache import cache

    # ------------------------------------------------------------------
    # Detect whether a shared Redis cache backend is actually in use.
    # If not (e.g. LocMemCache in dev / DummyCache), skip the fast-path
    # and go directly to the DB – this ensures correctness in all
    # environments, at the cost of one lightweight COUNT query per poll.
    # ------------------------------------------------------------------
    use_redis = (os.getenv('USE_REDIS', 'False').lower() == 'true')

    # ------------------------------------------------------------------
    # Fast-path: check Redis cache without touching the database
    # ------------------------------------------------------------------
    has_new_in_cache = False

    try:
        if not use_redis:
            # No shared cache – skip straight to DB check
            has_new_in_cache = True
        elif request.user.is_superuser:
            latest_ts = cache.get('realtime:orders:latest_ts')
            has_new_in_cache = (latest_ts is not None and latest_ts > since_ts)

        elif hasattr(request, 'admin_profile') and request.admin_profile:
            ap = request.admin_profile
            # Check per-branch cache keys for all branches the user can access
            try:
                branch_ids = list(ap.get_accessible_branches().values_list('id', flat=True))
            except Exception:
                branch_ids = []

            for branch_id in branch_ids:
                branch_ts = cache.get(f'realtime:orders:latest_ts:b:{branch_id}')
                if branch_ts and branch_ts > since_ts:
                    has_new_in_cache = True
                    break
        else:
            return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': since_ts})

    except Exception:
        # If Redis is down, fall through to the DB check below
        has_new_in_cache = True  # be optimistic – better a false positive than missing orders

    # ------------------------------------------------------------------
    # If cache shows no new orders, return immediately (no DB hit)
    # ------------------------------------------------------------------
    if not has_new_in_cache:
        return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': since_ts})

    # ------------------------------------------------------------------
    # Cache signals new orders – confirm count via a single DB query
    # ------------------------------------------------------------------
    try:
        from django.utils import timezone as tz_utils
        import datetime

        since_dt = datetime.datetime.fromtimestamp(since_ts, tz=datetime.timezone.utc)

        if request.user.is_superuser:
            qs = Order.objects.filter(created_at__gt=since_dt)
        elif request.admin_profile:
            qs = get_user_orders(request.user).filter(created_at__gt=since_dt)
        else:
            return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': since_ts})

        count = qs.count()
        if count > 0:
            latest_ts = time.time()
            # Render new order rows as HTML so the client can inject them directly
            rows_html = ''
            try:
                import datetime as _dt
                from django.template.loader import render_to_string
                new_orders = qs.select_related(
                    'bot_user', 'product', 'language', 'branch', 'branch__center',
                    'assigned_to', 'assigned_to__user'
                ).prefetch_related('receipts').order_by('-created_at')
                rows_html = render_to_string(
                    'orders/_order_row.html',
                    {'orders': new_orders, 'today': _dt.date.today()},
                    request=request,
                )
            except Exception as render_err:
                logger.warning(f"api_poll_new_orders render failed: {render_err}")
            return JsonResponse({'has_new': True, 'count': count, 'latest_ts': latest_ts, 'html': rows_html})

        return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': since_ts})

    except Exception as e:
        logger.warning(f"api_poll_new_orders DB check failed: {e}")
        return JsonResponse({'has_new': False, 'count': 0, 'latest_ts': since_ts})


@login_required(login_url='admin_login')
def api_branch_staff(request, branch_id):
    """API endpoint to get staff members for a branch"""
    from organizations.models import Branch
    
    try:
        branch = Branch.objects.get(pk=branch_id, is_active=True)
    except Branch.DoesNotExist:
        return JsonResponse({'error': 'Branch not found'}, status=404)
    
    # Check access
    if not request.user.is_superuser and request.admin_profile:
        accessible_branches = request.admin_profile.get_accessible_branches()
        if branch not in accessible_branches:
            return JsonResponse({'error': 'Access denied'}, status=403)
    
    staff = AdminUser.objects.filter(
        branch=branch,
        is_active=True
    ).select_related('user', 'role')
    
    staff_list = [
        {
            'id': s.pk,
            'name': s.user.get_full_name() or s.user.username,
            'role': s.role.get_display_name() if s.role else 'Unknown',
            'assigned_orders': s.assigned_orders.filter(
                status__in=['in_progress', 'ready']
            ).count(),
        }
        for s in staff
    ]
    
    return JsonResponse({'staff': staff_list})


@login_required(login_url='admin_login')
@any_permission_required('can_view_own_orders', 'can_view_all_orders', 'can_manage_orders')
def myOrders(request):
    """List orders assigned to the current user (for staff)"""
    if not request.admin_profile:
        messages.error(request, "You need an admin profile to view your orders.")
        return redirect('index')
    
    orders = Order.objects.filter(
        assigned_to=request.admin_profile
    ).select_related(
        'bot_user', 'product', 'language', 'branch'
    ).order_by('-created_at')
    
    # Status filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(orders, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Stats for my orders
    my_orders = Order.objects.filter(assigned_to=request.admin_profile)
    stats = {
        'total': my_orders.count(),
        'in_progress': my_orders.filter(status='in_progress').count(),
        'ready': my_orders.filter(status='ready').count(),
        'completed': my_orders.filter(status='completed').count(),
    }
    
    context = {
        "title": _("My Orders"),
        "subTitle": _("Orders Assigned to Me"),
        "title_i18n": "orders.myOrders",
        "orders": page_obj,
        "paginator": paginator,
        "status_filter": status_filter,
        "per_page": per_page,
        "total_orders": paginator.count,
        "status_choices": Order.STATUS_CHOICES,
        "stats": stats,
    }
    return render(request, "orders/myOrders.html", context)


@login_required(login_url='admin_login')
@require_active_subscription
@require_feature('orders_basic')
@check_order_limit
@permission_required('can_create_orders')
def orderCreate(request):
    """Create a new order - requires can_create_orders permission"""
    from services.models import Product, Language
    from accounts.models import BotUser
    
    # Get accessible centers and branches
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        branches = Branch.objects.filter(is_active=True).select_related('center')
        # Superuser sees all bot users
        bot_users = BotUser.objects.all().order_by('-created_at')[:100]
        # Superuser sees all products
        products = Product.objects.filter(is_active=True)
    elif request.admin_profile:
        branches = request.admin_profile.get_accessible_branches()
        # Filter bot users by accessible branches
        branch_ids = branches.values_list('id', flat=True)
        center_ids = branches.values_list('center_id', flat=True).distinct()
        # Also include users with only a center set (manually created without branch)
        bot_users = BotUser.objects.filter(
            Q(branch_id__in=branch_ids) | Q(center_id__in=center_ids)
        ).distinct().order_by('-created_at')[:100]
        # Filter products by accessible branches (Product -> Category -> Branch)
        products = Product.objects.filter(
            is_active=True,
            category__branch_id__in=branch_ids
        ).select_related('category', 'category__branch')
    else:
        branches = Branch.objects.none()
        bot_users = BotUser.objects.none()
        products = Product.objects.none()
    
    # Get languages scoped to the user's accessible branches
    from organizations.rbac import get_user_languages
    languages = get_user_languages(request.user).order_by('branch__name', 'name')
    
    if request.method == 'POST':
        try:
            # Get form data
            bot_user_id = request.POST.get('bot_user')
            product_id = request.POST.get('product')
            language_id = request.POST.get('language')
            branch_id = request.POST.get('branch')
            total_pages = int(request.POST.get('total_pages', 1))
            copy_number = int(request.POST.get('copy_number', 0))
            payment_type = request.POST.get('payment_type', 'cash')
            description = request.POST.get('description', '')

            # Deadline (optional)
            from datetime import date as _date
            deadline = None
            deadline_str = (request.POST.get('deadline') or '').strip()
            if deadline_str:
                try:
                    deadline = _date.fromisoformat(deadline_str)
                except ValueError:
                    pass
            
            # Check for manual order (manual customer info)
            manual_first_name = request.POST.get('manual_first_name', '').strip()
            manual_last_name = request.POST.get('manual_last_name', '').strip()
            manual_phone = request.POST.get('manual_phone', '').strip()
            
            # Determine if this is a manual order or bot user order
            is_manual_order = bool(manual_first_name and manual_phone)
            
            # Validate required fields
            if not is_manual_order and not bot_user_id:
                messages.error(request, _("Please select a customer or enable manual order and fill in customer details"))
                return redirect('orders:orderCreate')
            
            if is_manual_order and (not manual_first_name or not manual_phone):
                messages.error(request, _("Please provide customer's first name and phone number for manual orders"))
                return redirect('orders:orderCreate')
                
            if not product_id or not branch_id:
                messages.error(request, _("Please fill in all required fields (product and branch)"))
                return redirect('orders:orderCreate')
            
            # Get or create bot_user
            if is_manual_order:
                # Resolve branch early so we can associate the customer with it
                _manual_branch = Branch.objects.filter(pk=branch_id).first() if branch_id else None
                _manual_center = _manual_branch.center if _manual_branch else None
                # Create a temporary/manual bot user for this order
                # Check if user with this phone already exists
                bot_user, created = BotUser.objects.get_or_create(
                    phone=manual_phone,
                    defaults={
                        'name': f"{manual_first_name} {manual_last_name}".strip(),
                        'user_id': None,  # No telegram for manual orders
                        'username': None,
                        'is_active': True,
                        'branch': _manual_branch,
                        'center': _manual_center,
                    }
                )
                # Update name, activation status, and branch/center if missing
                new_name = f"{manual_first_name} {manual_last_name}".strip()
                fields_to_update = []
                if not created and bot_user.name != new_name:
                    bot_user.name = new_name
                    fields_to_update.append('name')
                if not bot_user.is_active:
                    bot_user.is_active = True
                    fields_to_update.append('is_active')
                if not bot_user.branch and _manual_branch:
                    bot_user.branch = _manual_branch
                    fields_to_update.append('branch')
                if not bot_user.center and _manual_center:
                    bot_user.center = _manual_center
                    fields_to_update.append('center')
                if fields_to_update:
                    fields_to_update.append('updated_at')
                    bot_user.save(update_fields=fields_to_update)
            else:
                # Get existing bot user — validate scope to prevent cross-center access
                bot_user = BotUser.objects.get(id=bot_user_id)
                if not request.user.is_superuser and request.admin_profile:
                    _accessible_branches = request.admin_profile.get_accessible_branches()
                    _customer_in_scope = (
                        (bot_user.branch_id and _accessible_branches.filter(pk=bot_user.branch_id).exists()) or
                        (request.admin_profile.center_id and bot_user.center_id == request.admin_profile.center_id)
                    )
                    if not _customer_in_scope:
                        messages.error(request, _("You don't have access to the selected customer."))
                        return redirect('orders:orderCreate')

            product = Product.objects.get(id=product_id)
            branch = Branch.objects.get(id=branch_id)
            # Validate branch is within user's accessible scope
            if not request.user.is_superuser and request.admin_profile:
                _accessible_branches = request.admin_profile.get_accessible_branches()
                if not _accessible_branches.filter(pk=branch.pk).exists():
                    messages.error(request, _("You don't have access to the selected branch."))
                    return redirect('orders:orderCreate')
            language = Language.objects.get(id=language_id) if language_id else None
            
            # Calculate total price using the Order model logic so it honors:
            # - dynamic vs fixed pricing
            # - agency vs ordinary pricing
            # - new fixed per-copy price (if set) vs legacy percentage
            total_price = Order(
                bot_user=bot_user,
                product=product,
                total_pages=total_pages,
                copy_number=copy_number,
            ).calculated_price
            
            # Create the order
            order = Order.objects.create(
                bot_user=bot_user,
                product=product,
                branch=branch,
                language=language,
                total_pages=total_pages,
                copy_number=copy_number,
                payment_type=payment_type,
                description=description,
                deadline=deadline,
                total_price=total_price,
                status='pending',
                is_active=True,
                created_by=getattr(request, 'admin_profile', None),
            )
            
            # Handle receipt upload for card payments
            if 'recipt' in request.FILES:
                order.recipt = request.FILES['recipt']
                order.save()
            
            # Handle file uploads
            files = request.FILES.getlist('files')
            for file in files:
                media = OrderMedia.objects.create(
                    file=file,
                    pages=1  # Default to 1 page per file
                )
                order.files.add(media)

            # Handle additional supply document uploads
            additional_files_list = request.FILES.getlist('additional_files')
            for file in additional_files_list:
                media = OrderMedia.objects.create(
                    file=file,
                    pages=1
                )
                order.additional_files.add(media)
            
            # Send Telegram notification to channels
            try:
                send_order_notification(order.id)
            except Exception as e:
                # Log but don't fail - order creation is more important
                import logging
                logging.getLogger(__name__).warning(f"Failed to send order notification: {e}")
            
            # Log the action
            log_action(
                user=request.user,
                action='create',
                target=order,
                details=f"Created order for {bot_user.name} - {product.name}"
            )
            
            messages.success(request, _("Order created successfully"))
            return redirect('orders:orderDetail', order_id=order.id)
            
        except Exception as e:
            messages.error(request, str(e))
            return redirect('orders:orderCreate')
    
    context = {
        "title": _("Create Order"),
        "subTitle": _("Create a new order manually"),
        "title_i18n": "orders.createTitle",
        "subTitle_i18n": "orders.createSubtitle",
        "centers": centers,
        "branches": branches,
        "products": products,
        "languages": languages,
        "bot_users": bot_users,
        "payment_choices": Order.PAYMENT_TYPE,
        "is_superuser": request.user.is_superuser,
        "languages_by_branch_url": "/services/api/languages-by-branch/",
    }
    return render(request, "orders/orderCreate.html", context)


# ============ Payment Management Views ============

from decimal import Decimal
from orders.payment_service import PaymentService, PaymentError


@login_required(login_url="admin_login")
@require_POST
@require_active_subscription
@require_feature('payment_management')
@any_permission_required('can_receive_payments', 'can_manage_financial', 'can_manage_orders')
def record_order_payment(request, order_id):
    """
    Record a payment for an order.
    
    POST params:
        amount: Decimal amount received (optional if accept_fully)
        accept_fully: "true" to mark as fully paid
        extra_fee: Decimal extra fee to add (optional)
        extra_fee_description: String description (optional)
        force_accept: "true" to force full acceptance (owner only)
        payment_type: "cash", "card", or "bank_transfer" (optional)
        recipt: File upload for payment receipt (optional)
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission - need can_receive_payments
    if not has_order_permission(request, 'can_receive_payments', order):
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to receive payments'
        }, status=403)
    
    try:
        # Parse request data
        amount = request.POST.get('amount')
        accept_fully = request.POST.get('accept_fully', '').lower() == 'true'
        extra_fee = request.POST.get('extra_fee')
        extra_fee_description = request.POST.get('extra_fee_description', '').strip()
        force_accept = request.POST.get('force_accept', '').lower() == 'true'
        payment_type = request.POST.get('payment_type', '').strip()
        receipt_file = request.FILES.get('recipt')
        
        # Update payment type if provided
        if payment_type and payment_type in ['cash', 'card', 'bank_transfer']:
            order.payment_type = payment_type
            order.save(update_fields=['payment_type'])
        
        # Handle receipt file upload
        if receipt_file:
            order.recipt = receipt_file
            order.save(update_fields=['recipt'])
        
        # Force accept requires financial management permission
        if force_accept:
            can_force = (
                request.user.is_superuser or
                (request.admin_profile and request.admin_profile.has_permission('can_manage_financial'))
            )
            if not can_force:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have permission to force accept payments'
                }, status=403)
        
        # Convert to Decimal
        amount = Decimal(amount) if amount else None
        extra_fee = Decimal(extra_fee) if extra_fee else None
        
        # Record the payment
        result = PaymentService.record_payment(
            order_id=order_id,
            received_by=request.admin_profile,
            amount=amount,
            accept_fully=accept_fully,
            extra_fee=extra_fee,
            extra_fee_description=extra_fee_description if extra_fee else None,
            force_accept=force_accept,
            request=request
        )
        
        return JsonResponse(result)
        
    except PaymentError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required(login_url="admin_login")
@require_feature('extra_fees')
@require_POST
@any_permission_required('can_edit_orders', 'can_manage_orders')
def add_order_extra_fee(request, order_id):
    """
    Add an extra fee to an order.
    
    POST params:
        amount: Decimal fee amount
        description: String description
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission - need can_edit_orders or can_manage_orders
    can_add_fee = (
        request.user.is_superuser or
        has_order_permission(request, 'can_edit_orders', order) or
        (request.admin_profile and request.admin_profile.has_permission('can_manage_orders'))
    )
    
    if not can_add_fee:
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to add extra fees'
        }, status=403)
    
    try:
        amount = request.POST.get('amount')
        description = request.POST.get('description', '').strip()
        
        if not amount:
            return JsonResponse({
                'success': False,
                'error': 'Amount is required'
            }, status=400)
        
        if not description:
            return JsonResponse({
                'success': False,
                'error': 'Description is required for extra fees'
            }, status=400)
        
        result = PaymentService.add_extra_fee(
            order_id=order_id,
            amount=Decimal(amount),
            description=description,
            added_by=request.admin_profile,
            request=request
        )
        
        return JsonResponse(result)
        
    except PaymentError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)


@login_required(login_url="admin_login")
@any_permission_required('can_view_all_orders', 'can_view_own_orders', 'can_manage_orders')
def get_order_payment_info(request, order_id):
    """Get current payment status for an order"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check view permission
    if not has_order_permission(request, 'can_view_all_orders', order):
        if not (request.admin_profile and order.assigned_to == request.admin_profile):
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)
    
    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'total_price': float(order.total_price),
        'extra_fee': float(order.extra_fee or 0),
        'extra_fee_description': order.extra_fee_description or '',
        'total_due': float(order.total_due),
        'received': float(order.received or 0),
        'remaining': float(order.remaining),
        'payment_accepted_fully': order.payment_accepted_fully,
        'is_fully_paid': order.is_fully_paid,
        'payment_percentage': order.payment_percentage,
        'status': order.status,
        'payment_type': order.payment_type,
    })


@login_required(login_url='admin_login')
def search_customers(request):
    """
    API endpoint to search for customers (BotUsers) by name or phone
    Returns JSON list of customers matching the search query
    """
    from accounts.models import BotUser
    from organizations.rbac import get_user_branches
    
    # Get search query parameter
    search = request.GET.get('q', '').strip()
    
    # Filter customers based on user permissions
    if request.user.is_superuser:
        # Superuser sees all customers
        customers = BotUser.objects.all()
    elif request.admin_profile:
        # Get accessible branches using RBAC
        accessible_branches = get_user_branches(request.user)
        branch_ids = accessible_branches.values_list('id', flat=True)
        center_ids = accessible_branches.values_list('center_id', flat=True).distinct()
        
        # Also include users with only a center set (manually created without a specific branch)
        customers = BotUser.objects.filter(
            Q(branch_id__in=branch_ids) | Q(center_id__in=center_ids)
        ).distinct()
    else:
        # No access if no admin profile
        customers = BotUser.objects.none()
    
    # Apply search filter if search query provided
    if search:
        customers = customers.filter(
            Q(name__icontains=search) | 
            Q(phone__icontains=search) |
            Q(username__icontains=search)
        )
    
    # Limit results to 50 most recent matches
    customers = customers.select_related('branch', 'branch__center').order_by('-created_at')[:50]
    
    # Format response as Select2 expects
    results = []
    for customer in customers:
        display_text = customer.name or customer.username or 'Unknown'
        if customer.phone:
            display_text += f" ({customer.phone})"
        
        results.append({
            'id': customer.id,
            'text': display_text,
            'is_agency': bool(getattr(customer, 'is_agency', False)),
        })
    
    return JsonResponse({
        'results': results
    })


@login_required
def search_categories(request):
    """
    API endpoint to search categories with RBAC compliance
    Returns JSON list of categories accessible to the user
    """
    from services.models import Category, Product
    from organizations.rbac import get_user_branches
    
    # Get search query parameter
    search = request.GET.get('q', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    
    logger.debug(f"search_categories called: q={search}, branch_id={branch_id}, user={request.user.username}")
    
    # Get accessible branches using RBAC
    accessible_branches = get_user_branches(request.user)
    
    logger.debug(f"User {request.user.username} has access to {accessible_branches.count()} branches")
    
    # If no accessible branches, return empty results
    if not accessible_branches.exists():
        logger.warning(f"User {request.user.username} has no accessible branches")
        return JsonResponse({'results': []})
    
    # Get categories for accessible branches
    categories = Category.objects.filter(
        branch__in=accessible_branches,
        is_active=True
    ).select_related('branch', 'branch__center')
    
    # Filter by branch if provided
    if branch_id:
        try:
            branch_id_int = int(branch_id)
            categories = categories.filter(branch_id=branch_id_int)
            logger.debug(f"Filtered by branch_id={branch_id_int}, found {categories.count()} categories")
        except ValueError:
            logger.error(f"Invalid branch_id: {branch_id}")
    
    # Apply search filter if provided
    if search:
        categories = categories.filter(name__icontains=search)
    
    # Order and limit results
    categories = categories.order_by('branch__center__name', 'branch__name', 'name')[:50]
    
    logger.debug(f"search_categories: Returning {len(categories)} categories for user {request.user.username}")
    
    # Format response as Select2 expects
    results = []
    for category in categories:
        # Only show center name for superusers
        if request.user.is_superuser:
            display_text = f"{category.branch.center.name} - {category.branch.name} | {category.name}"
        else:
            display_text = f"{category.branch.name} | {category.name}"
        results.append({
            'id': category.id,
            'text': display_text
        })
    
    return JsonResponse({
        'results': results
    })


@login_required
def search_products(request):
    """
    API endpoint to search products with RBAC compliance
    Supports optional category filter
    Returns JSON list of products accessible to the user
    """
    from services.models import Product
    from organizations.rbac import get_user_branches
    
    # Get search query and category filter
    search = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    
    logger.debug(f"search_products called: q={search}, category_id={category_id}, branch_id={branch_id}, user={request.user.username}")
    
    # Get accessible branches using RBAC
    accessible_branches = get_user_branches(request.user)
    
    logger.debug(f"User {request.user.username} has access to {accessible_branches.count()} branches")
    
    # If no accessible branches, return empty results
    if not accessible_branches.exists():
        logger.warning(f"User {request.user.username} has no accessible branches")
        return JsonResponse({'results': []})
    
    # Get products for accessible branches
    products = Product.objects.filter(
        category__branch__in=accessible_branches,
        is_active=True
    ).select_related('category', 'category__branch', 'category__branch__center')
    
    # Filter by branch if provided
    if branch_id:
        try:
            branch_id_int = int(branch_id)
            products = products.filter(category__branch_id=branch_id_int)
            logger.debug(f"Filtered by branch_id={branch_id_int}, found {products.count()} products")
        except ValueError:
            logger.error(f"Invalid branch_id: {branch_id}")
    
    # Filter by category if provided
    if category_id:
        try:
            category_id_int = int(category_id)
            products = products.filter(category_id=category_id_int)
            logger.debug(f"Filtered by category_id={category_id_int}, found {products.count()} products")
        except ValueError:
            logger.error(f"Invalid category_id: {category_id}")
    
    # Apply search filter if provided
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(category__name__icontains=search)
        )
    
    # Order and limit results
    products = products.order_by('category__branch__center__name', 'category__name', 'name')[:50]
    
    logger.debug(f"search_products: Returning {len(products)} products for user {request.user.username}")
    
    # Format response as Select2 expects
    results = []
    for product in products:
        # Only show center name for superusers
        if request.user.is_superuser:
            display_text = (
                f"{product.category.branch.center.name} - "
                f"{product.category.name} | {product.name} "
                f"({product.ordinary_first_page_price}/{product.ordinary_other_page_price} UZS/page)"
            )
        else:
            display_text = (
                f"{product.category.name} | {product.name} "
                f"({product.ordinary_first_page_price}/{product.ordinary_other_page_price} UZS/page)"
            )
        results.append({
            'id': product.id,
            'text': display_text,
            # Base prices (both types) so the front-end can estimate correctly
            'charging': getattr(product.category, 'charging', None),
            'price_first': float(product.ordinary_first_page_price),
            'price_other': float(product.ordinary_other_page_price),
            'price_first_agency': float(product.agency_first_page_price),
            'price_other_agency': float(product.agency_other_page_price),

            # Copy pricing: new fixed per-copy fields (nullable) + legacy percentages
            'agency_copy_price_fixed': float(product.agency_copy_price_decimal) if product.agency_copy_price_decimal is not None else None,
            'user_copy_price_fixed': float(product.user_copy_price_decimal) if product.user_copy_price_decimal is not None else None,
            'agency_copy_price_percentage': float(product.agency_copy_price_percentage),
            'user_copy_price_percentage': float(product.user_copy_price_percentage),
        })
    
    return JsonResponse({
        'results': results
    })


# ── Price Edit ──────────────────────────────────────────────────────────────

@login_required(login_url='admin_login')
@require_POST
@any_permission_required('can_edit_price', 'can_manage_orders', 'can_manage_financial')
def edit_order_price(request, order_id):
    """
    Manually override an order's total_price.
    Creates an OrderPriceChange audit record and writes to the audit log.
    Requires: can_edit_orders OR can_manage_orders OR can_manage_financial.
    """
    order = get_object_or_404(Order, id=order_id)

    # Scope check — user must be able to access this order's branch
    if not request.user.is_superuser:
        can_access = (
            has_order_permission(request, 'can_edit_price', order) or
            has_order_permission(request, 'can_manage_orders', order) or
            has_order_permission(request, 'can_manage_financial', order)
        )
        if not can_access:
            return JsonResponse({'success': False, 'error': "You don't have permission to edit this order's price."}, status=403)

    new_price_str = request.POST.get('new_price', '').strip()
    reason = request.POST.get('reason', '').strip()

    if not new_price_str:
        return JsonResponse({'success': False, 'error': 'New price is required.'}, status=400)
    if not reason:
        return JsonResponse({'success': False, 'error': 'Reason is required.'}, status=400)

    try:
        new_price = Decimal(new_price_str)
    except InvalidOperation:
        return JsonResponse({'success': False, 'error': 'Invalid price format.'}, status=400)

    if new_price < 0:
        return JsonResponse({'success': False, 'error': 'Price cannot be negative.'}, status=400)

    old_price = order.total_price
    if old_price == new_price:
        return JsonResponse({'success': False, 'error': 'New price is the same as the current price.'}, status=400)

    admin_profile = getattr(request, 'admin_profile', None)

    # Create audit record
    OrderPriceChange.objects.create(
        order=order,
        old_price=old_price,
        new_price=new_price,
        reason=reason,
        changed_by=admin_profile,
    )

    # Update order
    order.total_price = new_price
    order.save(update_fields=['total_price', 'updated_at'])

    # Write to system audit log
    log_action(
        user=request.user,
        action='update',
        target=order,
        details=f'Price manually changed: {old_price} → {new_price}. Reason: {reason}',
        changes={'old_price': str(old_price), 'new_price': str(new_price), 'reason': reason},
        request=request,
    )

    changed_by_name = 'Superuser'
    if admin_profile:
        changed_by_name = admin_profile.user.get_full_name() or admin_profile.user.username

    return JsonResponse({
        'success': True,
        'new_price': str(new_price),
        'old_price': str(old_price),
        'reason': reason,
        'changed_by': changed_by_name,
        'changed_at': timezone.now().strftime('%d %b %Y, %H:%M'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Order Comments
# ─────────────────────────────────────────────────────────────────────────────

@login_required(login_url='admin_login')
@require_active_subscription
@any_permission_required('can_view_all_orders', 'can_view_own_orders', 'can_manage_orders')
def add_order_comment(request, order_id):
    """AJAX: add an internal comment to an order."""
    from django.http import JsonResponse
    from .models import OrderComment

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    order = get_object_or_404(Order, id=order_id)

    # branch-scope check: staff can only comment on orders in their branch
    if not request.user.is_superuser:
        if not has_order_permission(request, 'can_view_all_orders', order):
            own_ok = (
                request.admin_profile and
                order.assigned_to == request.admin_profile and
                has_order_permission(request, 'can_view_own_orders', order)
            )
            if not own_ok:
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    body = request.POST.get('body', '').strip()
    if not body:
        return JsonResponse({'success': False, 'error': 'Comment cannot be empty'}, status=400)
    if len(body) > 2000:
        return JsonResponse({'success': False, 'error': 'Comment is too long (max 2000 chars)'}, status=400)

    comment = OrderComment.objects.create(
        order=order,
        author=request.admin_profile if hasattr(request, 'admin_profile') else None,
        body=body,
    )

    author_name = (
        comment.author.user.get_full_name() or comment.author.user.username
        if comment.author else 'Superuser'
    )
    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'body': comment.body,
            'author': author_name,
            'created_at': comment.created_at.strftime('%d %b %Y, %H:%M'),
            'is_own': True,
        },
    })


@login_required(login_url='admin_login')
@require_active_subscription
def delete_order_comment(request, order_id, comment_id):
    """AJAX: delete an internal comment (own comment, or superuser/manager)."""
    from django.http import JsonResponse
    from .models import OrderComment

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    comment = get_object_or_404(OrderComment, id=comment_id, order_id=order_id)

    # Only own comment, or superuser, or someone with can_manage_orders
    is_own = (
        request.admin_profile and
        comment.author == request.admin_profile
    )
    is_manager = (
        request.user.is_superuser or
        bool(request.admin_profile and request.admin_profile.has_permission('can_manage_orders'))
    )
    if not (is_own or is_manager):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    comment.delete()
    return JsonResponse({'success': True})


# ─────────────────────────────────────────────────────────────────────────────
# PDF Invoice
# ─────────────────────────────────────────────────────────────────────────────

_INVOICE_STRINGS = {
    'uz': {
        'title': 'HISOB-FAKTURA',
        'invoice_num': 'Hisob-faktura №',
        'date': 'Sana',
        'status': 'Holat',
        'bill_to': 'Xaridor',
        'service_details': 'Xizmat tafsilotlari',
        'agency_client': '💼 Agentlik mijozi',
        'individual_client': '👤 Jismoniy mijoz',
        'translation_lang': 'Til',
        'pages': 'Sahifalar',
        'copies': 'Nusxalar',
        'col_description': 'Tavsif',
        'col_qty': 'Miqdor',
        'col_unit_price': 'Birlik narxi',
        'col_amount': 'Summa',
        'first_page': 'Birinchi sahifa',
        'additional_pages': "Qo'shimcha sahifalar",
        'pages_range': 'Sahifalar 2–',
        'extra_copies': "Qo'shimcha nusxalar",
        'copy_count': 'nusxa',
        'extra_fee': "Qo'shimcha to'lov",
        'subtotal': 'Oraliq jami',
        'total_with_fee': "Jami (+ qo'shimcha to'lov)",
        'grand_total': 'Umumiy jami',
        'amount_paid': "To'langan summa",
        'balance_due': 'Qoldiq',
        'payment_info': "To'lov ma'lumotlari",
        'payment_method': "To'lov usuli",
        'payment_source': "To'lov manbai",
        'payment_received': "To'lov qabul qilindi",
        'received_by': 'Qabul qilgan',
        'notes': 'Izohlar',
        'names_on_doc': 'Hujjatdagi ismlar',
        'generated_on': 'Yaratildi',
        'thank_you': "Ishonchingiz uchun rahmat!",
        'status_completed': 'Bajarildi',
        'status_in_progress': 'Jarayonda',
        'status_pending': 'Kutilmoqda',
        'status_cancelled': 'Bekor qilindi',
        'status_ready': 'Tayyor',
        'status_received': 'Qabul qilindi',
        'status_confirmed': 'Tasdiqlandi',
        'lang_label': 'Tilni tanlang',
        'download_pdf': 'PDF yuklab olish',
        'incl_first': "1-sahifa bilan",
    },
    'ru': {
        'title': 'СЧЁТ',
        'invoice_num': 'Счёт №',
        'date': 'Дата',
        'status': 'Статус',
        'bill_to': 'Покупатель',
        'service_details': 'Детали услуги',
        'agency_client': '💼 Клиент-агентство',
        'individual_client': '👤 Физическое лицо',
        'translation_lang': 'Язык',
        'pages': 'Страниц',
        'copies': 'Копий',
        'col_description': 'Описание',
        'col_qty': 'Кол-во',
        'col_unit_price': 'Цена за ед.',
        'col_amount': 'Сумма',
        'first_page': 'Первая страница',
        'additional_pages': 'Доп. страницы',
        'pages_range': 'Страницы 2–',
        'extra_copies': 'Доп. копии',
        'copy_count': 'коп.',
        'extra_fee': 'Доп. плата',
        'subtotal': 'Промежуточный итог',
        'total_with_fee': 'Итого (+ доп. плата)',
        'grand_total': 'Итого',
        'amount_paid': 'Оплачено',
        'balance_due': 'Остаток',
        'payment_info': 'Информация об оплате',
        'payment_method': 'Способ оплаты',
        'payment_source': 'Источник оплаты',
        'payment_received': 'Оплата получена',
        'received_by': 'Принял(а)',
        'notes': 'Примечания',
        'names_on_doc': 'Имена в документе',
        'generated_on': 'Создано',
        'thank_you': 'Спасибо за Ваш заказ!',
        'status_completed': 'Завершено',
        'status_in_progress': 'В обработке',
        'status_pending': 'Ожидание',
        'status_cancelled': 'Отменено',
        'status_ready': 'Готово',
        'status_received': 'Получено',
        'status_confirmed': 'Подтверждено',
        'lang_label': 'Выберите язык',
        'download_pdf': 'Скачать PDF',
        'incl_first': 'вкл. 1-ю стр.',
    },
    'en': {
        'title': 'INVOICE',
        'invoice_num': 'Invoice #',
        'date': 'Date',
        'status': 'Status',
        'bill_to': 'Bill To',
        'service_details': 'Service Details',
        'agency_client': '💼 Agency Client',
        'individual_client': '👤 Individual Client',
        'translation_lang': 'Language',
        'pages': 'Pages',
        'copies': 'Copies',
        'col_description': 'Description',
        'col_qty': 'Qty',
        'col_unit_price': 'Unit Price',
        'col_amount': 'Amount',
        'first_page': 'First page',
        'additional_pages': 'Additional pages',
        'pages_range': 'Pages 2–',
        'extra_copies': 'Extra copies',
        'copy_count': 'copy/copies',
        'extra_fee': 'Extra fee',
        'subtotal': 'Subtotal',
        'total_with_fee': 'Total (+ extra fee)',
        'grand_total': 'Grand Total',
        'amount_paid': 'Amount Paid',
        'balance_due': 'Balance Due',
        'payment_info': 'Payment Information',
        'payment_method': 'Payment Method',
        'payment_source': 'Payment Source',
        'payment_received': 'Payment Received',
        'received_by': 'Received By',
        'notes': 'Notes',
        'names_on_doc': 'Names on Document',
        'generated_on': 'Generated on',
        'thank_you': 'Thank you for your business!',
        'status_completed': 'Completed',
        'status_in_progress': 'In Progress',
        'status_pending': 'Pending',
        'status_cancelled': 'Cancelled',
        'status_ready': 'Ready',
        'status_received': 'Received',
        'status_confirmed': 'Confirmed',
        'lang_label': 'Select Language',
        'download_pdf': 'Download PDF',
        'incl_first': 'incl. 1st',
    },
}


@login_required(login_url='admin_login')
@require_active_subscription
@any_permission_required('can_view_all_orders', 'can_view_own_orders', 'can_manage_orders')
def order_invoice_pdf(request, order_id):
    """
    Invoice preview (HTML) or PDF download for an order.
    ?lang=uz|ru|en  — language (defaults to dashboard cookie, then uz)
    ?format=pdf     — stream as PDF download instead of HTML preview
    """
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    # ── Language selection ────────────────────────────────────────────────────
    lang = request.GET.get('lang', '').strip().lower()
    if lang not in ('uz', 'ru', 'en'):
        lang = request.COOKIES.get('django_language', 'uz')
    if lang not in ('uz', 'ru', 'en'):
        lang = 'uz'

    as_pdf = request.GET.get('format', '') == 'pdf'

    order = get_object_or_404(
        Order.objects.select_related(
            'bot_user', 'product', 'product__category',
            'language', 'branch', 'branch__center',
        ),
        id=order_id,
    )

    # ── Permission check (same logic as orderDetail) ─────────────────────────
    can_view = has_order_permission(request, 'can_view_all_orders', order)
    if not can_view and request.admin_profile and order.assigned_to == request.admin_profile:
        can_view = has_order_permission(request, 'can_view_own_orders', order)
    if not can_view:
        messages.error(request, "You don't have permission to view this order.")
        return redirect('orders:ordersList')

    price_breakdown = order.get_price_breakdown()
    center = order.center  # property on Order
    strings = _INVOICE_STRINGS.get(lang, _INVOICE_STRINGS['en'])

    # Build per-status label using the selected language strings
    status_map = {
        'completed':        strings['status_completed'],
        'in_progress':      strings['status_in_progress'],
        'pending':          strings['status_pending'],
        'payment_pending':  strings['status_pending'],
        'payment_received': strings['status_received'],
        'payment_confirmed':strings['status_confirmed'],
        'cancelled':        strings['status_cancelled'],
        'ready':            strings['status_ready'],
    }
    status_label = status_map.get(order.status, order.get_status_display())

    html_string = render_to_string('orders/invoice_pdf.html', {
        'order': order,
        'price_breakdown': price_breakdown,
        'center': center,
        'strings': strings,
        'lang': lang,
        'status_label': status_label,
        'is_pdf': as_pdf,
        'request': request,
    })

    if as_pdf:
        import weasyprint
        pdf_bytes = weasyprint.HTML(
            string=html_string,
            base_url=request.build_absolute_uri('/'),
        ).write_pdf()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"invoice-{order.get_order_number()}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return HttpResponse(html_string)
