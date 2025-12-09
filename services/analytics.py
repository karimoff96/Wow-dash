"""
Unit Economy Analytics Service
Provides remaining balance/debt calculations per branch, client type, and center.
Supports multi-tenant data separation through RBAC.
"""

from decimal import Decimal
from django.db.models import Sum, Count, Case, When, F, Q, DecimalField
from django.db.models.functions import Coalesce
from organizations.rbac import get_user_orders


def get_remaining_balance_summary(user, date_from=None, date_to=None):
    """
    Get overall remaining balance summary for the user's scope.
    Args:
        user: The requesting user
        date_from: Optional start date for filtering orders
        date_to: Optional end date for filtering orders
    Returns:
        dict with total_remaining, total_orders_with_debt, fully_paid_count, etc.
    """
    orders = get_user_orders(user)
    
    # Apply date filters if provided
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    # Exclude cancelled orders from debt calculations
    active_orders = orders.exclude(status='cancelled')
    
    # Calculate remaining for each order
    # remaining = max(0, (total_price + extra_fee) - received) if not payment_accepted_fully else 0
    orders_with_remaining = active_orders.annotate(
        total_due=Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0')),
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=F('total_due') - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    )
    
    # Filter orders with outstanding balance
    unpaid_orders = orders_with_remaining.filter(calc_remaining__gt=0)
    
    # Aggregate totals
    total_remaining = unpaid_orders.aggregate(
        total=Coalesce(Sum('calc_remaining'), Decimal('0'))
    )['total']
    
    total_orders_with_debt = unpaid_orders.count()
    fully_paid_count = orders_with_remaining.filter(calc_remaining__lte=0).count()
    
    # Total received amount
    total_received = active_orders.aggregate(
        total=Coalesce(Sum('received'), Decimal('0'))
    )['total']
    
    # Total expected revenue (total_price + extra_fee)
    total_expected = active_orders.aggregate(
        total=Coalesce(
            Sum(F('total_price') + F('extra_fee')),
            Decimal('0')
        )
    )['total']
    
    # Collection rate
    collection_rate = 0
    if total_expected and total_expected > 0:
        collection_rate = round((float(total_received) / float(total_expected)) * 100, 1)
    
    return {
        'total_remaining': float(total_remaining or 0),
        'total_orders_with_debt': total_orders_with_debt,
        'fully_paid_count': fully_paid_count,
        'total_received': float(total_received or 0),
        'total_expected': float(total_expected or 0),
        'collection_rate': collection_rate,
    }


def get_remaining_by_branch(user, limit=10, date_from=None, date_to=None):
    """
    Get remaining balance grouped by branch.
    Args:
        user: The requesting user
        limit: Maximum number of branches to return
        date_from: Optional start date for filtering orders
        date_to: Optional end date for filtering orders
    Returns:
        list of dicts with branch info and remaining balance
    """
    orders = get_user_orders(user)
    
    # Apply date filters if provided
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    orders = orders.exclude(status='cancelled')
    
    branch_data = orders.annotate(
        total_due=Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0')),
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=F('total_due') - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).values(
        'branch__id', 'branch__name', 'branch__center__name'
    ).annotate(
        remaining=Coalesce(Sum('calc_remaining'), Decimal('0')),
        total_orders=Count('id'),
        orders_with_debt=Count('id', filter=Q(calc_remaining__gt=0)),
        total_received=Coalesce(Sum('received'), Decimal('0')),
        total_expected=Coalesce(Sum(F('total_price') + F('extra_fee')), Decimal('0'))
    ).filter(
        remaining__gt=0
    ).order_by('-remaining')[:limit]
    
    result = []
    for item in branch_data:
        collection_rate = 0
        if item['total_expected'] and item['total_expected'] > 0:
            collection_rate = round((float(item['total_received']) / float(item['total_expected'])) * 100, 1)
        
        result.append({
            'branch_id': item['branch__id'],
            'branch_name': item['branch__name'] or 'Unknown Branch',
            'center_name': item['branch__center__name'] or 'Unknown Center',
            'remaining': float(item['remaining'] or 0),
            'total_orders': item['total_orders'],
            'orders_with_debt': item['orders_with_debt'],
            'total_received': float(item['total_received'] or 0),
            'total_expected': float(item['total_expected'] or 0),
            'collection_rate': collection_rate,
        })
    
    return result


def get_remaining_by_client_type(user, date_from=None, date_to=None):
    """
    Get remaining balance grouped by client type (B2B/Agency vs B2C/Regular).
    Args:
        user: The requesting user
        date_from: Optional start date for filtering orders
        date_to: Optional end date for filtering orders
    Returns:
        dict with 'agency' and 'regular' categories
    """
    orders = get_user_orders(user)
    
    # Apply date filters if provided
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    orders = orders.exclude(status='cancelled')
    
    client_data = orders.annotate(
        total_due=Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0')),
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=F('total_due') - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).values(
        'bot_user__is_agency'
    ).annotate(
        remaining=Coalesce(Sum('calc_remaining'), Decimal('0')),
        total_orders=Count('id'),
        orders_with_debt=Count('id', filter=Q(calc_remaining__gt=0)),
        total_received=Coalesce(Sum('received'), Decimal('0')),
        total_expected=Coalesce(Sum(F('total_price') + F('extra_fee')), Decimal('0'))
    )
    
    result = {
        'agency': {  # B2B
            'label': 'B2B (Agency)',
            'remaining': 0,
            'total_orders': 0,
            'orders_with_debt': 0,
            'total_received': 0,
            'total_expected': 0,
            'collection_rate': 0,
        },
        'regular': {  # B2C
            'label': 'B2C (Regular)',
            'remaining': 0,
            'total_orders': 0,
            'orders_with_debt': 0,
            'total_received': 0,
            'total_expected': 0,
            'collection_rate': 0,
        }
    }
    
    for item in client_data:
        key = 'agency' if item['bot_user__is_agency'] else 'regular'
        result[key]['remaining'] = float(item['remaining'] or 0)
        result[key]['total_orders'] = item['total_orders']
        result[key]['orders_with_debt'] = item['orders_with_debt']
        result[key]['total_received'] = float(item['total_received'] or 0)
        result[key]['total_expected'] = float(item['total_expected'] or 0)
        
        if result[key]['total_expected'] > 0:
            result[key]['collection_rate'] = round(
                (result[key]['total_received'] / result[key]['total_expected']) * 100, 1
            )
    
    return result


def get_remaining_by_center(user, limit=10, date_from=None, date_to=None):
    """
    Get remaining balance grouped by translation center.
    Only relevant for superusers or center owners.
    Args:
        user: The requesting user
        limit: Maximum number of centers to return
        date_from: Optional start date for filtering orders
        date_to: Optional end date for filtering orders
    Returns:
        list of dicts with center info and remaining balance
    """
    orders = get_user_orders(user)
    
    # Apply date filters if provided
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    orders = orders.exclude(status='cancelled')
    
    center_data = orders.annotate(
        total_due=Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0')),
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=F('total_due') - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).values(
        'branch__center__id', 'branch__center__name'
    ).annotate(
        remaining=Coalesce(Sum('calc_remaining'), Decimal('0')),
        total_orders=Count('id'),
        orders_with_debt=Count('id', filter=Q(calc_remaining__gt=0)),
        total_received=Coalesce(Sum('received'), Decimal('0')),
        total_expected=Coalesce(Sum(F('total_price') + F('extra_fee')), Decimal('0'))
    ).filter(
        remaining__gt=0
    ).order_by('-remaining')[:limit]
    
    result = []
    for item in center_data:
        collection_rate = 0
        if item['total_expected'] and item['total_expected'] > 0:
            collection_rate = round((float(item['total_received']) / float(item['total_expected'])) * 100, 1)
        
        result.append({
            'center_id': item['branch__center__id'],
            'center_name': item['branch__center__name'] or 'Unknown Center',
            'remaining': float(item['remaining'] or 0),
            'total_orders': item['total_orders'],
            'orders_with_debt': item['orders_with_debt'],
            'total_received': float(item['total_received'] or 0),
            'total_expected': float(item['total_expected'] or 0),
            'collection_rate': collection_rate,
        })
    
    return result


def get_top_debtors(user, limit=10, date_from=None, date_to=None):
    """
    Get top customers with outstanding balance.
    Args:
        user: The requesting user
        limit: Maximum number of debtors to return
        date_from: Optional start date for filtering orders
        date_to: Optional end date for filtering orders
    Returns:
        list of dicts with customer info and remaining balance
    """
    orders = get_user_orders(user)
    
    # Apply date filters if provided
    if date_from:
        orders = orders.filter(created_at__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__lte=date_to)
    
    orders = orders.exclude(status='cancelled')
    
    customer_data = orders.annotate(
        total_due=Coalesce(F('total_price'), Decimal('0')) + Coalesce(F('extra_fee'), Decimal('0')),
        calc_remaining=Case(
            When(payment_accepted_fully=True, then=Decimal('0')),
            default=F('total_due') - Coalesce(F('received'), Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).values(
        'bot_user__id', 'bot_user__name', 'bot_user__phone', 'bot_user__is_agency'
    ).annotate(
        remaining=Coalesce(Sum('calc_remaining'), Decimal('0')),
        total_orders=Count('id'),
        orders_with_debt=Count('id', filter=Q(calc_remaining__gt=0)),
        total_received=Coalesce(Sum('received'), Decimal('0')),
        total_expected=Coalesce(Sum(F('total_price') + F('extra_fee')), Decimal('0'))
    ).filter(
        remaining__gt=0
    ).order_by('-remaining')[:limit]
    
    result = []
    for item in customer_data:
        collection_rate = 0
        if item['total_expected'] and item['total_expected'] > 0:
            collection_rate = round((float(item['total_received']) / float(item['total_expected'])) * 100, 1)
        
        result.append({
            'customer_id': item['bot_user__id'],
            'customer_name': item['bot_user__name'] or 'Unknown',
            'customer_phone': item['bot_user__phone'] or '',
            'is_agency': item['bot_user__is_agency'],
            'client_type': 'B2B' if item['bot_user__is_agency'] else 'B2C',
            'remaining': float(item['remaining'] or 0),
            'total_orders': item['total_orders'],
            'orders_with_debt': item['orders_with_debt'],
            'total_received': float(item['total_received'] or 0),
            'total_expected': float(item['total_expected'] or 0),
            'collection_rate': collection_rate,
        })
    
    return result


def get_unit_economy_analytics(user):
    """
    Get comprehensive Unit Economy analytics for dashboard.
    Combines all analytics into a single response for efficiency.
    """
    return {
        'summary': get_remaining_balance_summary(user),
        'by_branch': get_remaining_by_branch(user),
        'by_client_type': get_remaining_by_client_type(user),
        'by_center': get_remaining_by_center(user),
        'top_debtors': get_top_debtors(user),
    }
