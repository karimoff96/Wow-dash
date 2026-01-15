from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _
from decimal import Decimal, InvalidOperation
import logging
from .models import Order, OrderMedia

logger = logging.getLogger(__name__)
from organizations.rbac import (
    get_user_orders, get_user_staff, get_user_branches,
    admin_profile_required, role_required, manager_or_owner_required,
    permission_required
)
from organizations.models import AdminUser, Branch, TranslationCenter
from core.audit import log_action, log_order_assign, log_status_change
from bot.notification_service import send_order_notification


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
    
    # For staff-level users, check if they can only work on their own orders
    if not request.user.is_superuser:
        role = request.admin_profile.role
        # If user only has can_view_own_orders, they can only see assigned orders
        if permission_name in ['can_view_own_orders', 'can_view_all_orders']:
            # If they don't have can_view_all_orders, check ownership
            if not role.can_view_all_orders and not role.can_manage_orders:
                if order and order.assigned_to != request.admin_profile:
                    return False
        # For edit/delete/status updates, check if order is assigned to them
        elif permission_name in ['can_edit_orders', 'can_delete_orders', 'can_update_order_status', 
                                 'can_complete_orders', 'can_cancel_orders']:
            # Managers and owners can work on any order in their branches
            if not (role.can_manage_orders or role.can_assign_orders or 
                   request.admin_profile.is_owner_role or request.admin_profile.is_manager_role):
                # Regular staff can only work on their assigned orders
                if order and order.assigned_to != request.admin_profile:
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
    if payment_filter:
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
    payment_choices = Order.PAYMENT_TYPE
    
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
    
    stats = {
        'total': base_orders.count(),
        'pending': base_orders.filter(status='pending').count(),
        'in_progress': base_orders.filter(status='in_progress').count(),
        'completed': base_orders.filter(status='completed').count(),
        'unassigned': base_orders.filter(assigned_to__isnull=True).count() if can_view_all else 0,
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
        "title": "Orders with Pending Receipts" if has_pending_receipts == 'true' else ("My Orders" if (can_view_own_only or view_mode == 'mine') else "Orders"),
        "subTitle": "Review uploaded payment receipts" if has_pending_receipts == 'true' else ("Orders assigned to me" if (can_view_own_only or view_mode == 'mine') else "All Orders"),
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
        "per_page": per_page,
        "total_orders": paginator.count,
        "status_choices": status_choices,
        "payment_choices": payment_choices,
        "centers": centers,
        "branches": branches,
        "staff_members": staff_members,
        "stats": stats,
        "my_stats": my_stats,
        "can_view_all": can_view_all,
        "can_view_own_only": can_view_own_only,
        "view_mode": view_mode,
        "can_create_orders": can_create_orders,
    }
    return render(request, "orders/ordersList.html", context)


@login_required(login_url='admin_login')
def orderDetail(request, order_id):
    """View order details with permission-based access control"""
    order = get_object_or_404(
        Order.objects.select_related(
            'bot_user', 'product', 'language', 'branch', 'branch__center',
            'assigned_to', 'assigned_to__user', 'assigned_by', 'assigned_by__user',
            'payment_received_by', 'payment_received_by__user',
            'completed_by', 'completed_by__user'
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
    
    context = {
        "title": f"Order #{order.id}",
        "subTitle": "Order Details",
        "order": order,
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
    }
    return render(request, "orders/orderDetail.html", context)


@login_required(login_url='admin_login')
def orderEdit(request, order_id):
    """Edit an order - permission-based access control"""
    from services.models import Product, Language
    from accounts.models import BotUser
    
    order = get_object_or_404(
        Order.objects.select_related('bot_user', 'product', 'language', 'branch'),
        id=order_id
    )
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_edit_orders', order):
        messages.error(request, "You don't have permission to edit this order.")
        return redirect('orders:orderDetail', order_id=order_id)
    
    # Get available products and languages
    products = Product.objects.filter(is_active=True)
    languages = Language.objects.all()  # Language model doesn't have is_active field
    
    # Get bot users based on user's role and permissions
    if request.user.is_superuser:
        # Superuser sees all customers
        bot_users = BotUser.objects.all().order_by('-created_at')
    elif request.admin_profile:
        # Get accessible branches for this user
        accessible_branches = request.admin_profile.get_accessible_branches()
        
        # Check if user can access center-level customers
        if request.admin_profile.has_permission('can_view_centers') or request.admin_profile.has_permission('can_manage_centers'):
            # Center owner/manager - get all customers from their center
            center = request.admin_profile.center
            if center:
                bot_users = BotUser.objects.filter(center=center).order_by('-created_at')
            else:
                bot_users = BotUser.objects.none()
        else:
            # Branch-level staff - get customers from accessible branches
            bot_users = BotUser.objects.filter(branch__in=accessible_branches).order_by('-created_at')
    else:
        # No admin profile - no access to customers
        bot_users = BotUser.objects.none()
    
    if request.method == 'POST':
        # Get form data
        bot_user_id = request.POST.get('bot_user')
        manual_first_name = request.POST.get('manual_first_name', '').strip()
        manual_last_name = request.POST.get('manual_last_name', '').strip()
        manual_phone = request.POST.get('manual_phone', '').strip()
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
                    bot_user, created = BotUser.objects.get_or_create(
                        phone=manual_phone,
                        defaults={
                            'name': f"{manual_first_name} {manual_last_name}".strip(),
                            'user_id': None,
                            'username': None,
                            'branch': order.branch,
                            'center': order.branch.center if order.branch else None,
                        }
                    )
                    order.bot_user = bot_user
            elif bot_user_id:
                # Bot user order - update bot_user reference
                order.bot_user = BotUser.objects.get(pk=bot_user_id)
                # Clear manual fields
                order.manual_first_name = None
                order.manual_last_name = None
                order.manual_phone = None
            
            # Update order
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
            
            # Recalculate price using the order's calculated_price property
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
            return redirect('orders:orderDetail', order_id=order_id)
            
        except Exception as e:
            messages.error(request, f'Error updating order: {str(e)}')
    
    context = {
        "title": f"Edit Order #{order.id}",
        "subTitle": "Edit Order",
        "order": order,
        "products": products,
        "languages": languages,
        "bot_users": bot_users,
        "payment_choices": Order.PAYMENT_TYPE,
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
def deleteOrder(request, order_id):
    """Delete an order - permission-based access control"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission using granular permission system
    if not has_order_permission(request, 'can_delete_orders', order):
        messages.error(request, "You don't have permission to delete orders.")
        return redirect('orders:ordersList')
    
    # Audit log before deletion
    log_action(
        user=request.user,
        action='delete',
        target=order,
        details=f'Order #{order.id} deleted',
        changes={'order_id': order.id, 'status': order.status},
        request=request
    )
    order.delete()
    messages.success(request, f'Order #{order_id} has been deleted')
    return redirect('orders:ordersList')


@login_required(login_url='admin_login')
@require_POST
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
    """API endpoint for order statistics"""
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
    
    return JsonResponse(stats)


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
        "title": "My Orders",
        "subTitle": "Orders Assigned to Me",
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
    elif request.admin_profile:
        branches = request.admin_profile.get_accessible_branches()
    else:
        branches = Branch.objects.none()
    
    # Get products and languages
    products = Product.objects.filter(is_active=True)
    languages = Language.objects.all()  # Language model doesn't have is_active field
    
    # Get bot users for selection (recent 100)
    bot_users = BotUser.objects.all().order_by('-created_at')[:100]
    
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
                # Create a temporary/manual bot user for this order
                # Check if user with this phone already exists
                bot_user, created = BotUser.objects.get_or_create(
                    phone=manual_phone,
                    defaults={
                        'name': f"{manual_first_name} {manual_last_name}".strip(),
                        'user_id': None,  # No telegram for manual orders
                        'username': None,
                    }
                )
                # Update name if user exists but name changed
                new_name = f"{manual_first_name} {manual_last_name}".strip()
                if not created and bot_user.name != new_name:
                    bot_user.name = new_name
                    bot_user.save()
            else:
                # Get existing bot user
                bot_user = BotUser.objects.get(id=bot_user_id)
            product = Product.objects.get(id=product_id)
            branch = Branch.objects.get(id=branch_id)
            language = Language.objects.get(id=language_id) if language_id else None
            
            # Calculate price (base price * pages * copies)
            base_price = product.price_per_page if hasattr(product, 'price_per_page') else 0
            total_price = base_price * total_pages * max(1, copy_number + 1)
            
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
                total_price=total_price,
                status='pending',
                is_active=True,
            )
            
            # Handle file uploads
            files = request.FILES.getlist('files')
            for file in files:
                media = OrderMedia.objects.create(
                    file=file,
                    pages=1  # Default to 1 page per file
                )
                order.files.add(media)
            
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
        "title": "Create Order",
        "subTitle": "Create a new order manually",
        "centers": centers,
        "branches": branches,
        "products": products,
        "languages": languages,
        "bot_users": bot_users,
        "payment_choices": Order.PAYMENT_TYPE,
        "is_superuser": request.user.is_superuser,
    }
    return render(request, "orders/orderCreate.html", context)


# ============ Payment Management Views ============

from decimal import Decimal
from orders.payment_service import PaymentService, PaymentError


@login_required(login_url="admin_login")
@require_POST
def record_order_payment(request, order_id):
    """
    Record a payment for an order.
    
    POST params:
        amount: Decimal amount received (optional if accept_fully)
        accept_fully: "true" to mark as fully paid
        extra_fee: Decimal extra fee to add (optional)
        extra_fee_description: String description (optional)
        force_accept: "true" to force full acceptance (owner only)
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
        
        # Force accept is only allowed for owners/superusers
        if force_accept:
            is_owner = (
                request.user.is_superuser or 
                (request.admin_profile and request.admin_profile.is_owner)
            )
            if not is_owner:
                return JsonResponse({
                    'success': False,
                    'error': 'Only owners can force accept payments'
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
@require_POST
def add_order_extra_fee(request, order_id):
    """
    Add an extra fee to an order.
    
    POST params:
        amount: Decimal fee amount
        description: String description
    """
    order = get_object_or_404(Order, id=order_id)
    
    # Check permission - need can_edit_orders or owner/manager
    can_add_fee = (
        request.user.is_superuser or
        has_order_permission(request, 'can_edit_orders', order) or
        (request.admin_profile and (request.admin_profile.is_owner or request.admin_profile.is_manager))
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
    
    # Get search query parameter
    search = request.GET.get('q', '').strip()
    
    # Base queryset - all bot users
    customers = BotUser.objects.all()
    
    # Filter by admin's accessible centers/branches if not superuser
    if not request.user.is_superuser and request.admin_profile:
        accessible_branches = request.admin_profile.get_accessible_branches()
        # Filter customers by accessible branches
        customers = customers.filter(
            Q(branch__in=accessible_branches) | Q(branch__isnull=True)
        )
    
    # Apply search filter if search query provided
    if search:
        customers = customers.filter(
            Q(name__icontains=search) | 
            Q(phone__icontains=search) |
            Q(username__icontains=search)
        )
    
    # Limit results to 50 most recent matches
    customers = customers.select_related('branch').order_by('-created_at')[:50]
    
    # Format response as Select2 expects
    results = []
    for customer in customers:
        display_text = customer.name or customer.username or 'Unknown'
        if customer.phone:
            display_text += f" ({customer.phone})"
        
        results.append({
            'id': customer.id,
            'text': display_text
        })
    
    return JsonResponse({
        'results': results
    })
