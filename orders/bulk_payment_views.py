"""
Bulk Payment Management Views

Handles bulk payment processing for agencies and customers with outstanding debts.
Implements FIFO (First In, First Out) payment distribution across orders.
"""

import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q, F, Case, When, DecimalField
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext as _
from django.utils import timezone

from accounts.models import BotUser
from orders.models import Order, BulkPayment, PaymentOrderLink
from organizations.rbac import require_permission, get_user_orders, get_user_customers

logger = logging.getLogger(__name__)


def can_manage_bulk_payments(user):
    """
    Check if user has permission to manage bulk payments.
    
    This is now permission-based rather than role-based.
    Superusers can assign this permission to any role via the admin panel.
    
    Permissions:
    - Superusers: Full access (always)
    - Users with can_manage_bulk_payments permission: Full access
    - All others: No access
    """
    if user.is_superuser:
        return True
    
    if not hasattr(user, 'admin_profile') or not user.admin_profile:
        return False
    
    admin_profile = user.admin_profile
    
    # Check if user's role has the bulk payment permission
    if admin_profile.role and hasattr(admin_profile.role, 'can_manage_bulk_payments'):
        return admin_profile.role.can_manage_bulk_payments
    
    return False


@login_required
@require_permission(can_manage_bulk_payments, 'You do not have permission to manage bulk payments')
def bulk_payment_page(request):
    """
    Main bulk payment management page.
    Shows top debtors table with RBAC filtering and payment processing interface.
    Supports pagination and advanced filtering.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    from organizations.models import Branch
    
    # Get filter parameters
    customer_type = request.GET.get('customer_type', '')
    branch_id = request.GET.get('branch_id', '')
    min_debt = request.GET.get('min_debt', '')
    max_debt = request.GET.get('max_debt', '')
    min_days = request.GET.get('min_days', '')
    max_days = request.GET.get('max_days', '')
    sort_by = request.GET.get('sort_by', 'debt_desc')  # debt_desc, debt_asc, orders_desc, days_desc
    per_page = request.GET.get('per_page', '20')
    page = request.GET.get('page', '1')
    
    # Check if coming from debtors report with specific customer
    preselected_customer_id = request.GET.get('customer_id', '')
    
    # Convert per_page to int with validation
    try:
        per_page = int(per_page)
        if per_page not in [10, 20, 50, 100]:
            per_page = 20
    except (ValueError, TypeError):
        per_page = 20
    
    # Get debtors with filters (no limit initially)
    branch_filter = int(branch_id) if branch_id and branch_id.isdigit() else None
    type_filter = customer_type if customer_type in ['agency', 'individual'] else None
    
    top_debtors = get_top_debtors(
        user=request.user,
        limit=None,  # Get all for filtering
        customer_type=type_filter,
        branch_id=branch_filter
    )
    
    # Apply additional filters
    if min_debt:
        try:
            min_debt_val = float(min_debt)
            top_debtors = [d for d in top_debtors if d['total_debt'] >= min_debt_val]
        except ValueError:
            pass
    
    if max_debt:
        try:
            max_debt_val = float(max_debt)
            top_debtors = [d for d in top_debtors if d['total_debt'] <= max_debt_val]
        except ValueError:
            pass
    
    # Apply sorting
    if sort_by == 'debt_asc':
        top_debtors.sort(key=lambda x: x['total_debt'])
    elif sort_by == 'debt_desc':
        top_debtors.sort(key=lambda x: x['total_debt'], reverse=True)
    elif sort_by == 'orders_desc':
        top_debtors.sort(key=lambda x: x['order_count'], reverse=True)
    elif sort_by == 'orders_asc':
        top_debtors.sort(key=lambda x: x['order_count'])
    elif sort_by == 'name_asc':
        top_debtors.sort(key=lambda x: x['name'].lower())
    elif sort_by == 'name_desc':
        top_debtors.sort(key=lambda x: x['name'].lower(), reverse=True)
    
    # Pagination
    paginator = Paginator(top_debtors, per_page)
    
    try:
        page_obj = paginator.get_page(page)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.get_page(1)
    
    # Get filter options
    admin_profile = request.user.admin_profile if hasattr(request.user, 'admin_profile') else None
    show_center_filter = False
    show_branch_filter = False
    available_branches = []
    
    if request.user.is_superuser:
        # Superuser sees all centers and branches
        show_center_filter = True
        show_branch_filter = True
        available_branches = Branch.objects.select_related('center').all().order_by('center__name', 'name')
    elif admin_profile and admin_profile.is_owner:
        # Owner sees their center's branches
        show_branch_filter = True
        if hasattr(admin_profile, 'center'):
            available_branches = Branch.objects.filter(center=admin_profile.center).order_by('name')
    
    context = {
        'page_title': _('Bulk Payment Management'),
        'active_nav': 'bulk_payments',
        'page_obj': page_obj,
        'paginator': paginator,
        'show_center_filter': show_center_filter,
        'show_branch_filter': show_branch_filter,
        'available_branches': available_branches,
        # Pass back filter values for form
        'filter_customer_type': customer_type,
        'filter_branch_id': branch_id,
        'filter_min_debt': min_debt,
        'filter_max_debt': max_debt,
        'filter_min_days': min_days,
        'filter_max_days': max_days,
        'filter_sort_by': sort_by,
        'filter_per_page': per_page,
        'total_debtors': len(top_debtors),
        'preselected_customer_id': preselected_customer_id,  # For auto-selecting customer
    }
    
    return render(request, 'orders/bulk_payment.html', context)


def get_top_debtors(user, limit=50, customer_type=None, branch_id=None):
    """
    Get top debtors with RBAC filtering.
    
    Args:
        user: The request user
        limit: Maximum number of results (None for all)
        customer_type: Filter by 'agency' or 'individual' or None for all
        branch_id: Filter by specific branch ID
    
    Returns:
        List of customer debt data with RBAC applied
    """
    # Get orders accessible to this user with RBAC filtering
    orders = get_user_orders(user).exclude(status='cancelled')
    
    # Apply branch filter if provided
    if branch_id:
        orders = orders.filter(branch_id=branch_id)
    
    # Calculate remaining balance for each order
    orders = orders.annotate(
        remaining_balance=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=(
                Coalesce(F('total_price'), Decimal('0')) + 
                Coalesce(F('extra_fee'), Decimal('0'))
            ) - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )
    
    # Only orders with outstanding balance
    orders_with_debt = orders.filter(remaining_balance__gt=0)
    
    # Group by customer and calculate total debt
    customer_debts = orders_with_debt.values(
        'bot_user__id',
        'bot_user__name',
        'bot_user__phone',
        'bot_user__is_agency'
    ).annotate(
        total_debt=Sum('remaining_balance'),
        order_count=Sum(1)
    ).filter(
        bot_user__isnull=False
    )
    
    # Filter by customer type if specified
    if customer_type == 'agency':
        customer_debts = customer_debts.filter(bot_user__is_agency=True)
    elif customer_type == 'individual':
        customer_debts = customer_debts.filter(bot_user__is_agency=False)
    
    # Order by debt amount and limit
    customer_debts = customer_debts.order_by('-total_debt')
    if limit:
        customer_debts = customer_debts[:limit]
    
    # Format results
    debtors = []
    for item in customer_debts:
        debtors.append({
            'id': item['bot_user__id'],
            'name': item['bot_user__name'] or 'Unknown',
            'phone': item['bot_user__phone'] or 'N/A',
            'is_agency': item['bot_user__is_agency'],
            'customer_type': 'Agency' if item['bot_user__is_agency'] else 'Individual',
            'total_debt': float(item['total_debt']),
            'order_count': item['order_count'],
        })
    
    return debtors


@login_required
@require_http_methods(["GET"])
def search_customers_with_debt(request):
    """
    API endpoint to search customers who have outstanding debts.
    Returns customers with their total debt amount.
    """
    if not can_manage_bulk_payments(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    search_query = request.GET.get('q', '').strip()
    
    if len(search_query) < 2:
        return JsonResponse({'customers': []})
    
    # Get orders accessible to this user
    orders = get_user_orders(request.user).exclude(status='cancelled')
    
    # Calculate remaining balance for each order
    orders = orders.annotate(
        remaining_balance=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=(
                Coalesce(F('total_price'), Decimal('0')) + 
                Coalesce(F('extra_fee'), Decimal('0'))
            ) - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )
    
    # Only orders with outstanding balance
    orders_with_debt = orders.filter(remaining_balance__gt=0)
    
    # Group by customer and calculate total debt
    customer_debts = orders_with_debt.values(
        'bot_user__id',
        'bot_user__name',
        'bot_user__phone',
        'bot_user__is_agency'
    ).annotate(
        total_debt=Sum('remaining_balance'),
        order_count=Sum(1)
    ).filter(
        bot_user__isnull=False
    )
    
    # Search filter
    if search_query:
        customer_debts = customer_debts.filter(
            Q(bot_user__name__icontains=search_query) |
            Q(bot_user__phone__icontains=search_query)
        )
    
    # Limit results
    customer_debts = customer_debts.order_by('-total_debt')[:20]
    
    # Format results
    customers = []
    for item in customer_debts:
        customers.append({
            'id': item['bot_user__id'],
            'name': item['bot_user__name'] or 'Unknown',
            'phone': item['bot_user__phone'] or 'N/A',
            'is_agency': item['bot_user__is_agency'],
            'customer_type': 'B2B (Agency)' if item['bot_user__is_agency'] else 'B2C (Individual)',
            'total_debt': float(item['total_debt']),
            'order_count': item['order_count'],
        })
    
    return JsonResponse({'customers': customers})


@login_required
@require_http_methods(["GET"])
def get_customer_debt_details(request, customer_id):
    """
    Get detailed debt information for a specific customer.
    Returns all outstanding orders with amounts.
    """
    if not can_manage_bulk_payments(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        customer = BotUser.objects.get(id=customer_id)
    except BotUser.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    
    # Get customer's orders with debt
    orders = get_user_orders(request.user).filter(
        bot_user=customer
    ).exclude(status='cancelled').select_related(
        'product', 'branch', 'language', 'payment_received_by__user'
    )
    
    # Calculate remaining balance using annotation with different name
    orders = orders.annotate(
        remaining_balance=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=(
                Coalesce(F('total_price'), Decimal('0')) + 
                Coalesce(F('extra_fee'), Decimal('0'))
            ) - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )
    
    # Only orders with outstanding balance
    orders_with_debt = orders.filter(remaining_balance__gt=0).order_by('created_at')  # FIFO
    
    # Calculate statistics
    total_debt = orders_with_debt.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
    
    # Get oldest debt date
    oldest_order = orders_with_debt.first()
    oldest_debt_days = None
    if oldest_order:
        delta = timezone.now() - oldest_order.created_at
        oldest_debt_days = delta.days
    
    # Format orders
    orders_list = []
    for order in orders_with_debt:
        days_old = (timezone.now() - order.created_at).days
        
        # Get payment info
        payment_info = None
        if order.payment_received_by and order.payment_received_at:
            # Try different ways to get the name
            received_by_name = 'Unknown'
            try:
                if hasattr(order.payment_received_by, 'user') and order.payment_received_by.user:
                    user = order.payment_received_by.user
                    received_by_name = user.get_full_name() or user.username or user.email or 'Unknown'
            except Exception:
                received_by_name = 'Unknown'
            
            payment_info = {
                'received_by': received_by_name,
                'received_at': order.payment_received_at.strftime('%Y-%m-%d %H:%M')
            }
        
        orders_list.append({
            'id': order.id,
            'order_number': order.get_order_number(),
            'created_at': order.created_at.strftime('%Y-%m-%d'),
            'product': order.product.name if order.product else 'N/A',
            'language': order.language.name if order.language else 'N/A',
            'branch': order.branch.name if order.branch else 'N/A',
            'total_price': float(order.total_price),
            'extra_fee': float(order.extra_fee),
            'received': float(order.received),
            'remaining': float(order.remaining_balance),
            'days_old': days_old,
            'status': order.status,
            'payment_info': payment_info,
        })
    
    return JsonResponse({
        'customer': {
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'is_agency': customer.is_agency,
            'customer_type': 'B2B (Agency)' if customer.is_agency else 'B2C (Individual)',
        },
        'debt_summary': {
            'total_debt': float(total_debt),
            'order_count': orders_with_debt.count(),
            'oldest_debt_days': oldest_debt_days,
        },
        'orders': orders_list,
    })


@login_required
@require_http_methods(["POST"])
def preview_payment_distribution(request):
    """
    Preview how a payment amount would be distributed across orders.
    Uses FIFO strategy (oldest orders first).
    """
    if not can_manage_bulk_payments(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        customer_id = request.POST.get('customer_id')
        payment_amount = Decimal(request.POST.get('payment_amount', '0'))
        
        if payment_amount <= 0:
            return JsonResponse({'error': 'Payment amount must be greater than 0'}, status=400)
        
        customer = BotUser.objects.get(id=customer_id)
        
        # Get customer's orders with debt (FIFO order)
        orders = get_user_orders(request.user).filter(
            bot_user=customer
        ).exclude(status='cancelled').annotate(
            remaining_balance=Case(
                When(payment_accepted_fully=True, then=Decimal('0')),
                default=(
                    Coalesce(F('total_price'), Decimal('0')) + 
                    Coalesce(F('extra_fee'), Decimal('0'))
                ) - Coalesce(F('received'), Decimal('0')),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).filter(remaining_balance__gt=0).order_by('created_at')
        
        # Calculate distribution
        remaining_payment = payment_amount
        distribution = []
        fully_paid_count = 0
        
        for order in orders:
            if remaining_payment <= 0:
                break
            
            order_remaining = order.remaining_balance
            amount_to_apply = min(remaining_payment, order_remaining)
            
            will_be_fully_paid = amount_to_apply >= order_remaining
            if will_be_fully_paid:
                fully_paid_count += 1
            
            distribution.append({
                'order_id': order.id,
                'order_number': order.get_order_number(),
                'current_remaining': float(order_remaining),
                'amount_applied': float(amount_to_apply),
                'new_remaining': float(order_remaining - amount_to_apply),
                'fully_paid': will_be_fully_paid,
            })
            
            remaining_payment -= amount_to_apply
        
        # Calculate remaining debt after payment
        total_debt = orders.aggregate(total=Sum('remaining_balance'))['total'] or Decimal('0')
        remaining_debt_after = max(Decimal('0'), total_debt - payment_amount)
        
        return JsonResponse({
            'success': True,
            'distribution': distribution,
            'summary': {
                'payment_amount': float(payment_amount),
                'orders_affected': len(distribution),
                'fully_paid_orders': fully_paid_count,
                'remaining_debt_after': float(remaining_debt_after),
                'unused_amount': float(remaining_payment),
            }
        })
        
    except BotUser.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    except Exception as e:
        logger.error(f"Error previewing payment: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def process_bulk_payment(request):
    """
    Process a bulk payment from a customer.
    Applies payment to orders using FIFO strategy.
    Creates audit trail records.
    """
    if not can_manage_bulk_payments(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        customer_id = request.POST.get('customer_id')
        payment_amount_str = request.POST.get('payment_amount', '0')
        payment_method = request.POST.get('payment_method', 'cash')
        receipt_note = request.POST.get('receipt_note', '').strip()
        
        # Validate customer_id
        if not customer_id:
            return JsonResponse({'error': 'Customer ID is required'}, status=400)
        
        # Validate payment amount
        try:
            payment_amount = Decimal(payment_amount_str)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid payment amount format'}, status=400)
        
        if payment_amount <= 0:
            return JsonResponse({'error': 'Payment amount must be greater than 0'}, status=400)
        
        # Validate payment method
        valid_methods = ['cash', 'bank_transfer', 'card', 'other']
        if payment_method not in valid_methods:
            return JsonResponse({'error': f'Invalid payment method. Must be one of: {", ".join(valid_methods)}'}, status=400)
        # Validate payment method
        valid_methods = ['cash', 'bank_transfer', 'card', 'other']
        if payment_method not in valid_methods:
            return JsonResponse({'error': f'Invalid payment method. Must be one of: {", ".join(valid_methods)}'}, status=400)
        
        # Get customer
        try:
            customer = BotUser.objects.get(id=customer_id)
        except BotUser.DoesNotExist:
            return JsonResponse({'error': 'Customer not found'}, status=404)
        
        # Get admin profile (superusers can process without admin_profile)
        admin_profile = None
        if not request.user.is_superuser:
            admin_profile = request.user.admin_profile if hasattr(request.user, 'admin_profile') else None
            if not admin_profile:
                return JsonResponse({'error': 'Admin profile not found. Please contact system administrator.'}, status=400)
        else:
            # Superuser - try to get admin_profile, if not exists, create a temporary one
            admin_profile = request.user.admin_profile if hasattr(request.user, 'admin_profile') else None
            if not admin_profile:
                # Create or get admin profile for superuser
                from organizations.models import AdminUser
                admin_profile, created = AdminUser.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'is_active': True,
                    }
                )
        
        # Get customer's orders with debt (FIFO order)
        orders = get_user_orders(request.user).filter(
            bot_user=customer
        ).exclude(status='cancelled').select_related('branch').annotate(
            remaining_balance=Case(
                When(payment_accepted_fully=True, then=Decimal('0')),
                default=(
                    Coalesce(F('total_price'), Decimal('0')) + 
                    Coalesce(F('extra_fee'), Decimal('0'))
                ) - Coalesce(F('received'), Decimal('0')),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).filter(remaining_balance__gt=0).order_by('created_at')
        
        if not orders.exists():
            return JsonResponse({'error': 'No outstanding orders found for this customer'}, status=400)
        
        # Get admin's branch (for audit trail)
        admin_branch = admin_profile.branch if (admin_profile and hasattr(admin_profile, 'branch')) else None
        
        # Create bulk payment record
        bulk_payment = BulkPayment.objects.create(
            bot_user=customer,
            amount=payment_amount,
            payment_method=payment_method,
            receipt_note=receipt_note,
            processed_by=admin_profile,  # Can be None for superuser without admin_profile
            branch=admin_branch,
        )
        
        # Apply payment to orders (FIFO)
        remaining_payment = payment_amount
        orders_paid = 0
        fully_paid_count = 0
        
        for order in orders:
            if remaining_payment <= Decimal('0.01'):  # Stop if remaining is negligible
                break
            
            order_remaining = order.remaining_balance
            
            # Skip if order somehow has no remaining balance
            if order_remaining <= Decimal('0.01'):
                continue
            
            amount_to_apply = min(remaining_payment, order_remaining)
            
            # Store previous state
            previous_received = order.received
            
            # Update order received amount
            new_received = previous_received + amount_to_apply
            order.received = new_received
            order.payment_received_by = admin_profile
            order.payment_received_at = timezone.now()
            order.save(update_fields=['received', 'payment_received_by', 'payment_received_at', 'updated_at'])
            
            # Check if fully paid
            new_remaining = (order.total_price + order.extra_fee) - new_received
            fully_paid = new_remaining <= Decimal('0.01')  # Small threshold for floating point
            
            if fully_paid:
                fully_paid_count += 1
                # Optionally update order status if fully paid
                if order.status in ['pending', 'payment_pending', 'payment_received']:
                    order.status = 'payment_confirmed'
                    order.save(update_fields=['status', 'updated_at'])
            
            # Create link record
            PaymentOrderLink.objects.create(
                bulk_payment=bulk_payment,
                order=order,
                amount_applied=amount_to_apply,
                previous_received=previous_received,
                new_received=new_received,
                fully_paid=fully_paid,
            )
            
            remaining_payment -= amount_to_apply
            orders_paid += 1
        
        # Calculate remaining debt
        total_debt_after = orders.aggregate(
            total=Sum(
                Case(
                    When(payment_accepted_fully=True, then=Decimal('0')),
                    default=(
                        Coalesce(F('total_price'), Decimal('0')) + 
                        Coalesce(F('extra_fee'), Decimal('0'))
                    ) - Coalesce(F('received'), Decimal('0')),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
        )['total'] or Decimal('0')
        
        # Update bulk payment statistics
        bulk_payment.orders_count = orders_paid
        bulk_payment.fully_paid_orders = fully_paid_count
        bulk_payment.remaining_debt_after = max(Decimal('0'), total_debt_after)
        bulk_payment.save(update_fields=['orders_count', 'fully_paid_orders', 'remaining_debt_after'])
        
        # Log successful payment
        logger.info(f"Bulk payment processed: Payment #{bulk_payment.id}, Customer: {customer.name}, Amount: {payment_amount}, Orders: {orders_paid}, Fully Paid: {fully_paid_count}, Processed by: {request.user.username}")
        
        # Send notification to customer via bot (if possible)
        try:
            from bot.notification_service import send_payment_confirmation
            send_payment_confirmation(customer, payment_amount, orders_paid, fully_paid_count)
        except ImportError:
            logger.warning("Bot notification service not available")
        except Exception as e:
            logger.warning(f"Could not send payment notification to customer: {e}")
        
        return JsonResponse({
            'success': True,
            'message': _('Payment processed successfully'),
            'payment_id': bulk_payment.id,
            'summary': {
                'payment_amount': float(payment_amount),
                'orders_paid': orders_paid,
                'fully_paid_orders': fully_paid_count,
                'remaining_debt': float(total_debt_after),
                'customer_name': customer.name,
            }
        })
        
    except ValueError as e:
        logger.error(f"ValueError in bulk payment processing: {e}")
        return JsonResponse({'error': f'Invalid input: {str(e)}'}, status=400)
    except Exception as e:
        logger.error(f"Error processing bulk payment: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Payment processing failed: {str(e)}'}, status=500)


@login_required
@require_permission(can_manage_bulk_payments, 'You do not have permission to view payment history')
def payment_history(request):
    """
    View payment history with filters.
    """
    # Get bulk payments accessible to user
    payments = BulkPayment.objects.select_related(
        'bot_user', 'processed_by__user', 'branch'
    ).prefetch_related('order_links')
    
    # Filter based on user role
    if not request.user.is_superuser:
        admin_profile = request.user.admin_profile if hasattr(request.user, 'admin_profile') else None
        if admin_profile:
            if admin_profile.is_owner:
                # Owner sees center payments
                payments = payments.filter(branch__center=admin_profile.center)
            elif admin_profile.is_manager:
                # Manager sees branch payments
                payments = payments.filter(branch=admin_profile.branch)
    
    # Apply filters from query params
    customer_id = request.GET.get('customer_id')
    if customer_id:
        payments = payments.filter(bot_user_id=customer_id)
    
    payment_method = request.GET.get('payment_method')
    if payment_method:
        payments = payments.filter(payment_method=payment_method)
    
    # Order by newest first
    payments = payments.order_by('-created_at')[:100]
    
    context = {
        'page_title': _('Payment History'),
        'payments': payments,
        'active_nav': 'payment_history',
    }
    
    return render(request, 'orders/payment_history.html', context)


@login_required
@require_http_methods(["GET"])
def get_top_debtors_api(request):
    """
    API endpoint to get top debtors with filters.
    Supports RBAC and filtering by customer type and branch.
    """
    if not can_manage_bulk_payments(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Get filter parameters
    customer_type = request.GET.get('customer_type', '')  # 'agency', 'individual', or ''
    branch_id = request.GET.get('branch_id', '')
    limit = int(request.GET.get('limit', 50))
    
    # Apply filters
    branch_filter = int(branch_id) if branch_id and branch_id.isdigit() else None
    type_filter = customer_type if customer_type in ['agency', 'individual'] else None
    
    # Get filtered debtors
    debtors = get_top_debtors(
        user=request.user,
        limit=min(limit, 100),  # Cap at 100
        customer_type=type_filter,
        branch_id=branch_filter
    )
    
    return JsonResponse({'debtors': debtors})
