"""
Reports & Analytics Views
Financial/order reports per branch/center with date filtering
"""

from django.shortcuts import render
from django.db import models
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import json

from orders.models import Order
from services.models import Product
from accounts.models import BotUser
from organizations.models import Branch, TranslationCenter, AdminUser
from organizations.rbac import (
    get_user_orders,
    get_user_customers,
    get_user_branches,
    any_permission_required,
    permission_required,
)


# Period choices for the unified filter
PERIOD_CHOICES = [
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("week", "This Week"),
    ("month", "This Month"),
    ("quarter", "This Quarter"),
    ("year", "This Year"),
    ("custom", "Custom Range"),
]


def get_period_dates(period, custom_from=None, custom_to=None):
    """
    Calculate date range based on selected period.
    Returns (date_from, date_to, period_label, trunc_function)
    """
    today = timezone.now()

    if period == "today":
        date_from = today.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = today
        label = "Today"
        trunc_func = TruncDate
        date_format = "%H:%M"
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = "Yesterday"
        trunc_func = TruncDate
        date_format = "%H:%M"
    elif period == "week":
        # Start of current week (Monday)
        start_of_week = today - timedelta(days=today.weekday())
        date_from = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = today
        label = "This Week"
        trunc_func = TruncDate
        date_format = "%a"
    elif period == "month":
        # Start of current month
        date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        date_to = today
        label = "This Month"
        trunc_func = TruncDate
        date_format = "%b %d"
    elif period == "quarter":
        # Start of current quarter
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        date_from = today.replace(
            month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        date_to = today
        label = "This Quarter"
        trunc_func = TruncWeek
        date_format = "Week %W"
    elif period == "year":
        # Start of current year
        date_from = today.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        date_to = today
        label = "This Year"
        trunc_func = TruncMonth
        date_format = "%b"
    elif period == "custom" and custom_from and custom_to:
        from datetime import datetime

        date_from = datetime.strptime(custom_from, "%Y-%m-%d")
        date_to = datetime.strptime(custom_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
        # Make timezone aware
        date_from = (
            timezone.make_aware(date_from)
            if timezone.is_naive(date_from)
            else date_from
        )
        date_to = (
            timezone.make_aware(date_to) if timezone.is_naive(date_to) else date_to
        )
        days_diff = (date_to - date_from).days
        label = f"{custom_from} to {custom_to}"
        # Choose appropriate truncation based on range
        if days_diff <= 1:
            trunc_func = TruncDate
            date_format = "%H:%M"
        elif days_diff <= 31:
            trunc_func = TruncDate
            date_format = "%b %d"
        elif days_diff <= 90:
            trunc_func = TruncWeek
            date_format = "Week %W"
        else:
            trunc_func = TruncMonth
            date_format = "%b %Y"
    else:
        # Default to last 30 days
        date_from = today - timedelta(days=30)
        date_to = today
        label = "Last 30 Days"
        trunc_func = TruncDate
        date_format = "%b %d"
        period = "month"

    return {
        "date_from": date_from,
        "date_to": date_to,
        "date_from_str": (
            date_from.strftime("%Y-%m-%d")
            if hasattr(date_from, "strftime")
            else str(date_from)[:10]
        ),
        "date_to_str": (
            date_to.strftime("%Y-%m-%d")
            if hasattr(date_to, "strftime")
            else str(date_to)[:10]
        ),
        "label": label,
        "trunc_func": trunc_func,
        "date_format": date_format,
        "period": period,
    }


@login_required(login_url="admin_login")
@permission_required('can_view_financial_reports')
def financial_reports(request):
    """Financial reports view with revenue analytics - requires can_view_financial_reports permission"""
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    branch_id = request.GET.get("branch")
    center_id = request.GET.get("center")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    trunc_func = period_data["trunc_func"]
    date_format = period_data["date_format"]

    # Get orders based on user role
    all_orders = get_user_orders(request.user)

    # Apply date filters
    orders = all_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    # Get available branches for filter
    branches = get_user_branches(request.user)

    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            orders = orders.filter(branch__center_id=center_id)
            branches = branches.filter(center_id=center_id)

    if branch_id:
        orders = orders.filter(branch_id=branch_id)

    # Calculate financial metrics
    total_revenue = float(orders.aggregate(total=Sum("total_price"))["total"] or 0)
    total_orders = orders.count()
    avg_order_value = float(orders.aggregate(avg=Avg("total_price"))["avg"] or 0)

    # Completed orders revenue
    completed_orders = orders.filter(status="completed")
    completed_revenue = float(
        completed_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    # Revenue breakdown by period
    revenue_by_period = (
        orders.annotate(period=trunc_func("created_at"))
        .values("period")
        .annotate(revenue=Sum("total_price"), count=Count("id"))
        .order_by("period")
    )

    daily_labels = []
    daily_values = []
    daily_counts = []
    for item in revenue_by_period:
        if item["period"]:
            daily_labels.append(item["period"].strftime(date_format))
            daily_values.append(float(item["revenue"] or 0))
            daily_counts.append(item["count"])

    # Revenue by status
    status_breakdown = (
        orders.values("status")
        .annotate(revenue=Sum("total_price"), count=Count("id"))
        .order_by("-revenue")
    )

    status_data = []
    for item in status_breakdown:
        status_data.append(
            {
                "status": item["status"],
                "status_display": dict(Order.STATUS_CHOICES).get(
                    item["status"], item["status"]
                ),
                "revenue": float(item["revenue"] or 0),
                "count": item["count"],
            }
        )

    # Revenue by branch (if owner/superuser)
    branch_revenue = []
    is_owner = False
    if hasattr(request.user, "admin_profile") and request.user.admin_profile:
        is_owner = request.user.admin_profile.is_owner

    if is_owner or request.user.is_superuser:
        branch_data = (
            orders.values("branch__id", "branch__name")
            .annotate(revenue=Sum("total_price"), count=Count("id"))
            .order_by("-revenue")[:10]
        )

        for item in branch_data:
            if item["branch__id"]:  # Only include if branch exists
                branch_revenue.append(
                    {
                        "id": item["branch__id"],
                        "branch": item["branch__name"] or "Unassigned",
                        "revenue": float(item["revenue"] or 0),
                        "count": item["count"],
                    }
                )

    # Top products by revenue
    top_products = (
        orders.values("product__name")
        .annotate(revenue=Sum("total_price"), count=Count("id"))
        .order_by("-revenue")[:5]
    )

    product_data = []
    for item in top_products:
        product_data.append(
            {
                "product": item["product__name"] or "Unknown",
                "revenue": float(item["revenue"] or 0),
                "count": item["count"],
            }
        )

    # Chart data for branches
    branch_labels = [b["branch"] for b in branch_revenue]
    branch_revenue_values = [b["revenue"] for b in branch_revenue]
    branch_order_counts = [b["count"] for b in branch_revenue]

    context = {
        "title": "Financial Reports",
        "subTitle": "Reports / Financial",
        # Filters
        "date_from": date_from,
        "date_to": date_to,
        "branches": branches,
        "selected_branch": branch_id,
        "centers": centers,
        "selected_center": center_id,
        # User role
        "is_owner": is_owner,
        # Metrics
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "completed_revenue": completed_revenue,
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Chart data
        "daily_labels": json.dumps(daily_labels),
        "daily_values": json.dumps(daily_values),
        "daily_counts": json.dumps(daily_counts),
        "branch_labels": json.dumps(branch_labels),
        "branch_revenue_values": json.dumps(branch_revenue_values),
        "branch_order_counts": json.dumps(branch_order_counts),
        # Breakdowns
        "status_data": status_data,
        "branch_revenue": branch_revenue,
        "product_data": product_data,
    }
    return render(request, "reports/financial.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_reports', 'can_view_analytics')
def order_reports(request):
    """Order analytics and reports - requires can_view_reports or can_view_analytics permission"""
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    branch_id = request.GET.get("branch")
    status_filter = request.GET.get("status")
    center_id = request.GET.get("center")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    trunc_func = period_data["trunc_func"]
    date_format = period_data["date_format"]

    # Get orders based on user role
    all_orders = get_user_orders(request.user)

    # Apply filters
    orders = all_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    branches = get_user_branches(request.user)

    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            orders = orders.filter(branch__center_id=center_id)
            branches = branches.filter(center_id=center_id)

    if branch_id:
        orders = orders.filter(branch_id=branch_id)
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Order metrics
    total_orders = orders.count()
    completed = orders.filter(status="completed").count()
    cancelled = orders.filter(status="cancelled").count()
    in_progress = orders.filter(status="in_progress").count()
    pending = orders.filter(status__in=["pending", "ready"]).count()

    completion_rate = round(
        (completed / total_orders * 100) if total_orders > 0 else 0, 1
    )
    cancellation_rate = round(
        (cancelled / total_orders * 100) if total_orders > 0 else 0, 1
    )

    # Order counts by period
    orders_by_period = (
        orders.annotate(period=trunc_func("created_at"))
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    )

    daily_labels = []
    daily_values = []
    for item in orders_by_period:
        if item["period"]:
            daily_labels.append(item["period"].strftime(date_format))
            daily_values.append(item["count"])

    # Orders by status breakdown for pie chart
    status_breakdown = (
        orders.values("status").annotate(count=Count("id")).order_by("-count")
    )

    status_labels = []
    status_values = []
    for item in status_breakdown:
        # Convert __proxy__ to string for JSON serialization
        label = dict(Order.STATUS_CHOICES).get(item["status"], item["status"])
        status_labels.append(str(label))
        status_values.append(item["count"])

    # Orders by language pair
    language_breakdown = (
        orders.values("language__name")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    language_data = []
    for item in language_breakdown:
        language_data.append(
            {"pair": item["language__name"] or "N/A", "count": item["count"]}
        )

    # Recent orders list with pagination
    recent_orders_qs = orders.select_related(
        "bot_user", "product", "assigned_to__user"
    ).order_by("-created_at")

    page = request.GET.get("page", 1)
    paginator = Paginator(recent_orders_qs, 10)  # 10 orders per page
    recent_orders = paginator.get_page(page)

    context = {
        "title": "Order Reports",
        "subTitle": "Reports / Orders",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Filters
        "branches": branches,
        "selected_branch": branch_id,
        "selected_status": status_filter,
        "status_choices": Order.STATUS_CHOICES,
        "centers": centers,
        "selected_center": center_id,
        # Metrics
        "total_orders": total_orders,
        "completed": completed,
        "cancelled": cancelled,
        "in_progress": in_progress,
        "pending": pending,
        "completion_rate": completion_rate,
        "cancellation_rate": cancellation_rate,
        # Chart data
        "daily_labels": json.dumps(daily_labels),
        "daily_values": json.dumps(daily_values),
        "status_labels": json.dumps(status_labels),
        "status_values": json.dumps(status_values),
        # Breakdowns
        "language_data": language_data,
        "recent_orders": recent_orders,
        "orders_page": recent_orders,
    }
    return render(request, "reports/orders.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_reports', 'can_view_analytics')
def staff_performance(request):
    """Staff performance reports - requires can_view_reports or can_view_analytics permission"""
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    branch_id = request.GET.get("branch")
    center_id = request.GET.get("center")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]

    # Get orders and branches based on user role
    all_orders = get_user_orders(request.user)
    branches = get_user_branches(request.user)

    # Determine user's access level
    centers = None
    user_center = None
    user_branch = None
    is_center_level = False
    is_branch_level = False
    
    if request.user.is_superuser:
        # Superuser sees all centers
        centers = TranslationCenter.objects.filter(is_active=True)
        is_center_level = True
        if center_id:
            all_orders = all_orders.filter(branch__center_id=center_id)
            branches = branches.filter(center_id=center_id)
    elif hasattr(request, "admin_profile") and request.admin_profile:
        admin_profile = request.admin_profile
        
        # Check if user has center-level access (owner or has center in profile)
        if admin_profile.center:
            user_center = admin_profile.center
            # Owner or user with center assigned - center level access
            is_center_level = True
            # Show their center in dropdown for consistency
            centers = TranslationCenter.objects.filter(id=user_center.id)
            # If they selected a center filter (should be their own), apply it
            if center_id and str(center_id) == str(user_center.id):
                all_orders = all_orders.filter(branch__center=user_center)
                branches = branches.filter(center=user_center)
        
        # Check if user has only branch-level access
        if admin_profile.branch and not is_center_level:
            user_branch = admin_profile.branch
            is_branch_level = True
            # Branch-level users don't get center dropdown, only their branch's data
            branches = branches.filter(id=user_branch.id)
            all_orders = all_orders.filter(branch=user_branch)

    # Filter orders by date
    orders = all_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    # Apply branch filter
    selected_branch = None
    if branch_id:
        orders = orders.filter(branch_id=branch_id)
        selected_branch = branches.filter(id=branch_id).first()

    # Get staff members based on user's access level
    if request.user.is_superuser:
        staff_members = AdminUser.objects.filter(is_active=True).select_related('user', 'role', 'branch', 'branch__center', 'center')
        if center_id:
            # Filter by center - staff can be in center OR have branches in that center
            staff_members = staff_members.filter(
                models.Q(center_id=center_id) | models.Q(branch__center_id=center_id)
            )
    elif hasattr(request, "admin_profile") and request.admin_profile:
        admin_profile = request.admin_profile
        
        if is_center_level and user_center:
            # Center-level user: show all staff in their center (across all branches)
            staff_members = AdminUser.objects.filter(
                models.Q(center=user_center) | models.Q(branch__center=user_center),
                is_active=True
            ).select_related('user', 'role', 'branch', 'branch__center', 'center').distinct()
        elif is_branch_level and user_branch:
            # Branch-level user: show only staff in their branch
            staff_members = AdminUser.objects.filter(
                branch=user_branch,
                is_active=True
            ).select_related('user', 'role', 'branch', 'branch__center')
        else:
            # Fallback: show only themselves
            staff_members = AdminUser.objects.filter(pk=admin_profile.pk).select_related('user', 'role', 'branch', 'branch__center')
    else:
        staff_members = AdminUser.objects.none()

    # Apply branch filter to staff if specified
    if branch_id and is_center_level:
        staff_members = staff_members.filter(branch_id=branch_id)

    # Calculate performance for each staff member
    staff_data = []
    for staff in staff_members:
        staff_orders = orders.filter(assigned_to=staff)
        total_assigned = staff_orders.count()
        completed_orders = staff_orders.filter(status="completed").count()
        revenue = float(
            staff_orders.filter(status="completed").aggregate(total=Sum("total_price"))[
                "total"
            ]
            or 0
        )

        # Calculate average completion time (simplified - based on updated_at - created_at)
        completion_rate = round(
            (completed_orders / total_assigned * 100) if total_assigned > 0 else 0, 1
        )

        staff_data.append(
            {
                "id": staff.id,
                "name": staff.user.get_full_name() or staff.user.username,
                "center": (
                    staff.branch.center.name
                    if staff.branch and staff.branch.center
                    else "N/A"
                ),
                "branch": staff.branch.name if staff.branch else "N/A",
                "role": staff.role.name if staff.role else "Staff",
                "total_assigned": total_assigned,
                "completed": completed_orders,
                "revenue": revenue,
                "completion_rate": completion_rate,
            }
        )

    # Sort by completed orders
    staff_data.sort(key=lambda x: x["completed"], reverse=True)

    # Top performers
    top_performers = staff_data[:5] if staff_data else []

    # Staff performance chart data
    staff_labels = [s["name"] for s in top_performers]
    staff_completed = [s["completed"] for s in top_performers]
    staff_revenue = [s["revenue"] for s in top_performers]

    # Pagination for staff data
    page = request.GET.get("page", 1)
    paginator = Paginator(staff_data, 10)  # 10 staff per page
    staff_page = paginator.get_page(page)

    context = {
        "title": "Staff Performance",
        "subTitle": "Reports / Staff Performance",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Filters
        "branches": branches,
        "selected_branch": branch_id,
        "centers": centers,
        "selected_center": center_id,
        # Access level info
        "is_center_level": is_center_level,
        "is_branch_level": is_branch_level,
        "user_center": user_center,
        "user_branch": user_branch,
        # Staff data with pagination
        "staff_data": staff_page,
        "staff_page": staff_page,
        "top_performers": top_performers,
        # Chart data
        "staff_labels": json.dumps(staff_labels),
        "staff_completed": json.dumps(staff_completed),
        "staff_revenue": json.dumps(staff_revenue),
    }
    return render(request, "reports/staff_performance.html", context)


@login_required(login_url="admin_login")
@permission_required('can_view_analytics')
def branch_comparison(request):
    """Compare branch performance - requires can_view_analytics permission"""
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    center_id = request.GET.get("center")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]

    # Get branches based on user role
    branches = get_user_branches(request.user)
    all_orders = get_user_orders(request.user)

    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            branches = branches.filter(center_id=center_id)
            all_orders = all_orders.filter(branch__center_id=center_id)

    orders = all_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    # Calculate metrics for each branch
    branch_data = []
    for branch in branches:
        branch_orders = orders.filter(branch=branch)
        total_orders = branch_orders.count()
        completed = branch_orders.filter(status="completed").count()
        revenue = float(branch_orders.aggregate(total=Sum("total_price"))["total"] or 0)
        avg_value = float(branch_orders.aggregate(avg=Avg("total_price"))["avg"] or 0)

        # Staff count
        staff_count = AdminUser.objects.filter(branch=branch, is_active=True).count()

        # Customer count
        customer_count = BotUser.objects.filter(branch=branch, is_active=True).count()

        branch_data.append(
            {
                "id": branch.id,
                "name": branch.name,
                "center": branch.center.name if branch.center else "N/A",
                "total_orders": total_orders,
                "completed": completed,
                "revenue": revenue,
                "avg_value": avg_value,
                "staff_count": staff_count,
                "customer_count": customer_count,
                "completion_rate": round(
                    (completed / total_orders * 100) if total_orders > 0 else 0, 1
                ),
            }
        )

    # Sort by revenue
    branch_data.sort(key=lambda x: x["revenue"], reverse=True)

    # Chart data
    branch_labels = [b["name"] for b in branch_data[:10]]
    branch_revenue = [b["revenue"] for b in branch_data[:10]]
    branch_orders_count = [b["total_orders"] for b in branch_data[:10]]

    # Summary
    total_revenue = sum(b["revenue"] for b in branch_data)
    total_orders_count = sum(b["total_orders"] for b in branch_data)
    total_staff = sum(b["staff_count"] for b in branch_data)
    total_customers = sum(b["customer_count"] for b in branch_data)

    context = {
        "title": "Branch Comparison",
        "subTitle": "Reports / Branch Comparison",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Filters
        "centers": centers,
        "selected_center": center_id,
        # Data
        "branch_data": branch_data,
        # Chart data
        "branch_labels": json.dumps(branch_labels),
        "branch_revenue": json.dumps(branch_revenue),
        "branch_orders_count": json.dumps(branch_orders_count),
        # Summary
        "total_revenue": total_revenue,
        "total_orders_count": total_orders_count,
        "total_staff": total_staff,
        "total_customers": total_customers,
    }
    return render(request, "reports/branch_comparison.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_analytics', 'can_view_customer_details')
def customer_analytics(request):
    """Customer analytics - requires can_view_analytics or can_view_customer_details permission"""
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    branch_id = request.GET.get("branch")
    center_id = request.GET.get("center")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    trunc_func = period_data["trunc_func"]
    date_format = period_data["date_format"]

    # Get customers and orders based on user role
    customers = get_user_customers(request.user)
    orders = get_user_orders(request.user)
    branches = get_user_branches(request.user)

    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            # Filter customers who have orders in branches of this center
            customer_ids = (
                orders.filter(branch__center_id=center_id)
                .values_list("customer_id", flat=True)
                .distinct()
            )
            customers = customers.filter(id__in=customer_ids)
            orders = orders.filter(branch__center_id=center_id)
            branches = branches.filter(center_id=center_id)

    if branch_id:
        customers = customers.filter(branch_id=branch_id)
        orders = orders.filter(branch_id=branch_id)

    # Date range filter
    orders = orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    # Customer metrics
    total_customers = customers.count()
    active_customers = customers.filter(is_active=True).count()
    new_customers = customers.filter(
        created_at__gte=date_from, created_at__lte=date_to
    ).count()

    agencies = customers.filter(is_agency=True).count()

    # Customer acquisition trend
    acquisition_data = (
        customers.filter(created_at__gte=date_from, created_at__lte=date_to)
        .annotate(period=trunc_func("created_at"))
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    )

    acquisition_labels = []
    acquisition_values = []
    for item in acquisition_data:
        if item["period"]:
            acquisition_labels.append(item["period"].strftime(date_format))
            acquisition_values.append(item["count"])

    # Top customers by orders
    top_customers = (
        orders.filter(bot_user__isnull=False)
        .values("bot_user__id", "bot_user__name", "bot_user__is_agency")
        .annotate(order_count=Count("id"), total_spent=Sum("total_price"))
        .order_by("-total_spent")[:10]
    )

    top_customer_data = []
    for item in top_customers:
        top_customer_data.append(
            {
                "name": item["bot_user__name"] or "Unknown",
                "is_agency": item["bot_user__is_agency"],
                "order_count": item["order_count"],
                "total_spent": float(item["total_spent"] or 0),
            }
        )

    # Customer type breakdown
    type_breakdown = [
        {"type": "Agencies", "count": agencies},
        {"type": "Regular Customers", "count": total_customers - agencies},
    ]

    context = {
        "title": "Customer Analytics",
        "subTitle": "Reports / Customers",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Filters
        "branches": branches,
        "selected_branch": branch_id,
        "centers": centers,
        "selected_center": center_id,
        # Metrics
        "total_customers": total_customers,
        "active_customers": active_customers,
        "new_customers": new_customers,
        "agencies": agencies,
        # Chart data
        "acquisition_labels": json.dumps(acquisition_labels),
        "acquisition_values": json.dumps(acquisition_values),
        # Breakdowns
        "top_customers": top_customer_data,
        "type_breakdown": type_breakdown,
    }
    return render(request, "reports/customers.html", context)


@login_required(login_url="admin_login")
@permission_required('can_export_data')
def export_report(request, report_type):
    """
    Comprehensive Excel export for all report types.
    Uses the ReportExporter service for multi-sheet Excel generation.
    
    Supports:
    - orders: Order analytics with details
    - financial: Financial/revenue reports
    - staff_performance: Staff performance metrics
    - branch_comparison: Branch comparison analytics
    - customers: Customer analytics
    - unit_economy: Remaining balances/debts
    - my_statistics: Personal staff statistics
    - expense_analytics: Expense analytics by branch and type
    """
    from core.export_service import ReportExporter
    from django.http import HttpResponse
    from django.contrib import messages
    
    # Collect all filter parameters
    filters = {
        'period': request.GET.get('period', 'month'),
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'branch_id': request.GET.get('branch'),
        'center_id': request.GET.get('center'),
        'status': request.GET.get('status'),
        'product_id': request.GET.get('product'),
        'staff_id': request.GET.get('staff'),
        'language': request.GET.get('language'),
        'expense_type': request.GET.get('expense_type'),
    }
    
    # Validate report type
    valid_types = [
        'orders', 'financial', 'staff_performance', 
        'branch_comparison', 'customers', 'unit_economy', 'my_statistics', 'expense_analytics'
    ]
    if report_type not in valid_types:
        return JsonResponse({'error': f'Invalid report type. Valid types: {", ".join(valid_types)}'}, status=400)
    
    try:
        # Create exporter and generate Excel
        exporter = ReportExporter(request.user)
        result = exporter.export(report_type, filters)
        
        if not result['success']:
            # Return JSON error for AJAX or redirect with message
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': result['message']}, status=400)
            messages.warning(request, result['message'])
            return JsonResponse({'error': result['message']}, status=400)
        
        # Create HTTP response with Excel file
        response = HttpResponse(
            result['file_content'],
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{result["filename"]}"'
        return response
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error exporting {report_type} report")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'An error occurred while generating the report'}, status=500)
        return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url="admin_login")
def my_statistics(request):
    """
    Personal statistics view for staff members.
    Shows only orders assigned to the current user.
    """
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")

    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    trunc_func = period_data["trunc_func"]
    date_format = period_data["date_format"]

    today = timezone.now()
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    # Get admin profile
    admin_profile = None
    if hasattr(request.user, "admin_profile"):
        admin_profile = request.user.admin_profile

    # Get only orders assigned to this user
    if admin_profile:
        my_orders = Order.objects.filter(assigned_to=admin_profile)
    else:
        my_orders = Order.objects.none()

    # Orders for selected period
    period_orders = my_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    # Today's stats
    today_orders = my_orders.filter(created_at__gte=today_start)
    today_count = today_orders.count()
    today_completed = today_orders.filter(status="completed").count()
    today_pages = today_orders.aggregate(total=Sum("total_pages"))["total"] or 0

    # This week's stats
    week_orders = my_orders.filter(created_at__gte=week_start)
    week_count = week_orders.count()
    week_completed = week_orders.filter(status="completed").count()
    week_pages = week_orders.aggregate(total=Sum("total_pages"))["total"] or 0

    # This month's stats
    month_orders = my_orders.filter(created_at__gte=month_start)
    month_count = month_orders.count()
    month_completed = month_orders.filter(status="completed").count()
    month_pages = month_orders.aggregate(total=Sum("total_pages"))["total"] or 0

    # This year's stats
    year_orders = my_orders.filter(created_at__gte=year_start)
    year_count = year_orders.count()
    year_completed = year_orders.filter(status="completed").count()
    year_pages = year_orders.aggregate(total=Sum("total_pages"))["total"] or 0

    # All time stats
    total_count = my_orders.count()
    total_completed = my_orders.filter(status="completed").count()
    total_pages = my_orders.aggregate(total=Sum("total_pages"))["total"] or 0

    # Completion rate
    completion_rate = (
        round((total_completed / total_count * 100), 1) if total_count > 0 else 0
    )

    # Status breakdown for selected period
    status_breakdown = (
        period_orders.values("status").annotate(count=Count("id")).order_by("-count")
    )

    STATUS_LABELS = {
        "pending": "Pending",
        "payment_pending": "Awaiting",
        "payment_received": "Received",
        "payment_confirmed": "Confirmed",
        "in_progress": "In Process",
        "ready": "Ready",
        "completed": "Done",
        "cancelled": "Cancelled",
    }

    STATUS_COLORS = {
        "pending": "#FF9F29",
        "payment_pending": "#6C757D",
        "payment_received": "#17A2B8",
        "payment_confirmed": "#28A745",
        "in_progress": "#487FFF",
        "ready": "#6F42C1",
        "completed": "#45B369",
        "cancelled": "#DC3545",
    }

    status_data = []
    for item in status_breakdown:
        status_data.append(
            {
                "status": item["status"],
                "label": STATUS_LABELS.get(item["status"], item["status"]),
                "count": item["count"],
                "color": STATUS_COLORS.get(item["status"], "#6C757D"),
            }
        )

    # Daily performance for selected period (chart data)
    daily_performance = (
        period_orders.annotate(period=trunc_func("created_at"))
        .values("period")
        .annotate(count=Count("id"), pages=Sum("total_pages"))
        .order_by("period")
    )

    daily_labels = []
    daily_counts = []
    daily_pages = []
    for item in daily_performance:
        if item["period"]:
            daily_labels.append(item["period"].strftime(date_format))
            daily_counts.append(item["count"])
            daily_pages.append(item["pages"] or 0)

    # Recent orders (last 10)
    recent_orders = my_orders.select_related("bot_user", "product").order_by(
        "-created_at"
    )[:10]

    context = {
        "title": "My Statistics",
        "subTitle": "Your Personal Performance",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Today
        "today_count": today_count,
        "today_completed": today_completed,
        "today_pages": today_pages,
        # Week
        "week_count": week_count,
        "week_completed": week_completed,
        "week_pages": week_pages,
        # Month
        "month_count": month_count,
        "month_completed": month_completed,
        "month_pages": month_pages,
        # Year
        "year_count": year_count,
        "year_completed": year_completed,
        "year_pages": year_pages,
        # All time
        "total_count": total_count,
        "total_completed": total_completed,
        "total_pages": total_pages,
        "completion_rate": completion_rate,
        # Chart data
        "status_data": json.dumps(status_data),
        "daily_labels": json.dumps(daily_labels),
        "daily_counts": json.dumps(daily_counts),
        "daily_pages": json.dumps(daily_pages),
        # Recent orders
        "recent_orders": recent_orders,
    }

    return render(request, "reports/my_statistics.html", context)


# ============ UNIT ECONOMY ANALYTICS ============

@login_required(login_url="admin_login")
@permission_required('can_view_financial_reports')
def unit_economy(request):
    """
    Unit Economy Analytics View
    Shows remaining debts/receivables broken down by branch, client type, and center.
    """
    from services.analytics import (
        get_remaining_balance_summary,
        get_remaining_by_branch,
        get_remaining_by_client_type,
        get_remaining_by_center,
        get_top_debtors,
    )
    
    # Period filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    
    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    
    # Get branch and center filters
    branch_id = request.GET.get("branch")
    center_id = request.GET.get("center")
    
    # Get available branches for filter
    branches = get_user_branches(request.user)
    
    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            branches = branches.filter(center_id=center_id)
    
    # Check if user is owner
    is_owner = False
    if hasattr(request.user, "admin_profile") and request.user.admin_profile:
        is_owner = request.user.admin_profile.is_owner
    
    # Get analytics data with date filtering
    summary = get_remaining_balance_summary(request.user, date_from=date_from, date_to=date_to)
    by_branch = get_remaining_by_branch(request.user, date_from=date_from, date_to=date_to)
    by_client_type = get_remaining_by_client_type(request.user, date_from=date_from, date_to=date_to)
    by_center = get_remaining_by_center(request.user, date_from=date_from, date_to=date_to)
    top_debtors = get_top_debtors(request.user, date_from=date_from, date_to=date_to)
    
    # Prepare chart data for branch remaining
    branch_labels = [b['branch_name'] for b in by_branch]
    branch_remaining_values = [b['remaining'] for b in by_branch]
    
    # Prepare chart data for client type
    client_type_labels = [by_client_type['agency']['label'], by_client_type['regular']['label']]
    client_type_values = [by_client_type['agency']['remaining'], by_client_type['regular']['remaining']]
    
    # Prepare chart data for center
    center_labels = [c['center_name'] for c in by_center]
    center_remaining_values = [c['remaining'] for c in by_center]
    
    context = {
        "title": "Unit Economy",
        "subTitle": "Reports / Unit Economy",
        # Period filter
        "period": period_data["period"],
        "period_label": period_data["label"],
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data["date_from_str"],
        "date_to": period_data["date_to_str"],
        # Filters
        "branches": branches,
        "selected_branch": branch_id,
        "centers": centers,
        "selected_center": center_id,
        # User role
        "is_owner": is_owner,
        # Summary
        "total_remaining": summary['total_remaining'],
        "total_orders_with_debt": summary['total_orders_with_debt'],
        "fully_paid_count": summary['fully_paid_count'],
        "total_received": summary['total_received'],
        "total_expected": summary['total_expected'],
        "collection_rate": summary['collection_rate'],
        # Breakdowns
        "by_branch": by_branch,
        "by_client_type": by_client_type,
        "by_center": by_center,
        "top_debtors": top_debtors,
        # Chart data
        "branch_labels": json.dumps(branch_labels),
        "branch_remaining_values": json.dumps(branch_remaining_values),
        "client_type_labels": json.dumps(client_type_labels),
        "client_type_values": json.dumps(client_type_values),
        "center_labels": json.dumps(center_labels),
        "center_remaining_values": json.dumps(center_remaining_values),
    }
    
    return render(request, "reports/unit_economy.html", context)


@login_required(login_url="admin_login")
@permission_required('can_view_financial_reports')
def unit_economy_api(request):
    """
    API endpoint for Unit Economy data.
    Returns JSON for AJAX requests / dashboard widgets.
    """
    from services.analytics import get_top_debtors
    
    # Get filters
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    client_type = request.GET.get("client_type", "")  # 'b2b', 'b2c', or ''
    center_id = request.GET.get("center")
    branch_id = request.GET.get("branch")
    
    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    
    # Get all debtors (no limit)
    all_debtors = get_top_debtors(request.user, limit=None, date_from=date_from, date_to=date_to)
    
    # Filter by client type if specified
    if client_type == 'b2b':
        all_debtors = [d for d in all_debtors if d['is_agency']]
    elif client_type == 'b2c':
        all_debtors = [d for d in all_debtors if not d['is_agency']]
    
    # Filter by center if specified
    if center_id:
        all_debtors = [d for d in all_debtors if d.get('center_id') == int(center_id)]
    
    # Filter by branch if specified
    if branch_id:
        all_debtors = [d for d in all_debtors if d.get('branch_id') == int(branch_id)]
    
    # Get accessible centers and branches for filtering
    branches = get_user_branches(request.user)
    
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
    
    # Check if user is owner
    is_owner = False
    if hasattr(request.user, "admin_profile") and request.user.admin_profile:
        is_owner = request.user.admin_profile.is_owner
    
    centers_data = [{'id': c.id, 'name': c.name} for c in centers] if centers else []
    branches_data = [{'id': b.id, 'name': b.name, 'center_id': b.center_id} for b in branches]
    
    return JsonResponse({
        'all_debtors': all_debtors,
        'total_count': len(all_debtors),
        'centers': centers_data,
        'branches': branches_data,
        'is_superuser': request.user.is_superuser,
        'show_center': request.user.is_superuser or is_owner,
        'show_branch': True
    })


@login_required(login_url="admin_login")
@any_permission_required('can_view_financial_reports', 'can_manage_orders', 'can_view_reports')
def debtors_report(request):
    """
    Dedicated page for viewing and managing debtors with advanced filtering.
    Respects RBAC - users see only debtors from their accessible branches.
    """
    from services.analytics import get_top_debtors
    
    # Get filters
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    client_type = request.GET.get("client_type", "")
    center_id = request.GET.get("center", "")
    branch_id = request.GET.get("branch", "")
    debt_range = request.GET.get("debt_range", "")
    collection_rate = request.GET.get("collection_rate", "")
    orders_count = request.GET.get("orders_count", "")
    sort_by = request.GET.get("sort_by", "remaining-desc")
    search = request.GET.get("search", "")
    
    # Get period dates
    period_data = get_period_dates(period, custom_from, custom_to)
    date_from = period_data["date_from"]
    date_to = period_data["date_to"]
    
    # Get all debtors
    all_debtors = get_top_debtors(request.user, limit=None, date_from=date_from, date_to=date_to)
    
    # Apply filters
    filtered_debtors = all_debtors
    
    # Search filter
    if search:
        search_lower = search.lower()
        filtered_debtors = [d for d in filtered_debtors if 
            search_lower in d['customer_name'].lower() or 
            (d['customer_phone'] and search_lower in d['customer_phone'].lower())]
    
    # Client type filter
    if client_type == 'b2b':
        filtered_debtors = [d for d in filtered_debtors if d['is_agency']]
    elif client_type == 'b2c':
        filtered_debtors = [d for d in filtered_debtors if not d['is_agency']]
    
    # Center filter
    if center_id:
        filtered_debtors = [d for d in filtered_debtors if d.get('center_id') == int(center_id)]
    
    # Branch filter
    if branch_id:
        filtered_debtors = [d for d in filtered_debtors if d.get('branch_id') == int(branch_id)]
    
    # Debt range filter
    if debt_range:
        min_debt, max_debt = map(int, debt_range.split('-'))
        filtered_debtors = [d for d in filtered_debtors if min_debt <= d['remaining'] <= max_debt]
    
    # Collection rate filter
    if collection_rate:
        min_rate, max_rate = map(int, collection_rate.split('-'))
        filtered_debtors = [d for d in filtered_debtors if min_rate <= d['collection_rate'] <= max_rate]
    
    # Orders count filter
    if orders_count:
        min_orders, max_orders = map(int, orders_count.split('-'))
        filtered_debtors = [d for d in filtered_debtors if min_orders <= d['orders_with_debt'] <= max_orders]
    
    # Apply sorting
    reverse = 'desc' in sort_by
    if 'remaining' in sort_by:
        filtered_debtors.sort(key=lambda x: x['remaining'], reverse=reverse)
    elif 'orders' in sort_by:
        filtered_debtors.sort(key=lambda x: x['orders_with_debt'], reverse=reverse)
    elif 'rate' in sort_by:
        filtered_debtors.sort(key=lambda x: x['collection_rate'], reverse=reverse)
    elif 'name' in sort_by:
        filtered_debtors.sort(key=lambda x: x['customer_name'], reverse=reverse)
    
    # Calculate summary stats
    total_debt = sum(d['remaining'] for d in filtered_debtors)
    total_orders_with_debt = sum(d['orders_with_debt'] for d in filtered_debtors)
    total_expected = sum(d['total_expected'] for d in filtered_debtors)
    total_received = sum(d['total_received'] for d in filtered_debtors)
    avg_collection_rate = sum(d['collection_rate'] for d in filtered_debtors) / len(filtered_debtors) if filtered_debtors else 0
    
    # Get available branches and centers for filter
    branches = get_user_branches(request.user)
    
    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
    
    # Check user permissions for showing center/branch columns
    is_owner = False
    if hasattr(request.user, "admin_profile") and request.user.admin_profile:
        is_owner = request.user.admin_profile.is_owner
    
    show_center = request.user.is_superuser or is_owner
    show_branch = True
    
    context = {
        'title': 'Debtors Management',
        'debtors': filtered_debtors,
        'total_count': len(filtered_debtors),
        'total_debt': total_debt,
        'total_orders_with_debt': total_orders_with_debt,
        'total_expected': total_expected,
        'total_received': total_received,
        'avg_collection_rate': round(avg_collection_rate, 1),
        'centers': centers,
        'branches': branches,
        'show_center': show_center,
        'show_branch': show_branch,
        # Filters
        'period': period,
        'period_choices': PERIOD_CHOICES,
        'period_label': period_data.get('label', ''),
        'date_from': custom_from or '',
        'date_to': custom_to or '',
        'client_type': client_type,
        'selected_center': center_id,
        'selected_branch': branch_id,
        'debt_range': debt_range,
        'collection_rate_filter': collection_rate,
        'orders_count_filter': orders_count,
        'sort_by': sort_by,
        'search': search,
    }
    
    return render(request, "reports/debtors_report.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_expenses', 'can_manage_expenses', 'can_view_financial_reports')
def expense_analytics_report(request):
    """
    Detailed expense analytics report with hierarchical breakdown:
    - Superuser: See all centers with their branches
    - Center-level: See own center's branches
    - Branch-level: See own branch details
    
    Shows total expense cost = expense_price * order_count for each expense
    """
    from services.models import Expense
    from organizations.rbac import get_user_expenses
    from orders.models import Order
    from decimal import Decimal
    
    # Get date filter
    period = request.GET.get("period", "month")
    custom_from = request.GET.get("date_from")
    custom_to = request.GET.get("date_to")
    period_data = get_period_dates(period, custom_from, custom_to)
    
    # Get filter parameters
    expense_type_filter = request.GET.get('expense_type', '')  # 'b2b', 'b2c', or ''
    center_id = request.GET.get('center')
    branch_id = request.GET.get('branch')
    
    # Determine user's access level first
    user_profile = getattr(request.user, 'admin_profile', None)
    is_superuser = request.user.is_superuser
    
    # Get accessible centers and branches based on RBAC
    accessible_centers = []
    accessible_branches = get_user_branches(request.user)
    
    # Determine if user is center owner or just has permissions
    is_center_owner = False
    if user_profile:
        is_center_owner = (user_profile.is_owner or 
                          (user_profile.center and user_profile.center.owner_id == request.user.id))
    
    # Filter orders by user access level and date range
    orders_base = Order.objects.filter(
        created_at__gte=period_data['date_from'],
        created_at__lte=period_data['date_to']
    ).select_related('product', 'branch', 'branch__center', 'bot_user')
    
    if is_superuser:
        accessible_centers = TranslationCenter.objects.filter(is_active=True)
        # Apply center filter if provided
        if center_id:
            accessible_centers = accessible_centers.filter(id=center_id)
            orders_base = orders_base.filter(branch__center_id=center_id)
    elif is_center_owner and user_profile.center:
        # Center owner sees their own center
        accessible_centers = [user_profile.center]
        orders_base = orders_base.filter(branch__center=user_profile.center)
        # Lock to their center only - ignore center filter
        center_id = None
        branch_id = None
    else:
        # Staff member with permissions - only their branch(es)
        orders_base = orders_base.filter(branch__in=accessible_branches)
        # Lock to their branches only - ignore filters
        center_id = None
        branch_id = None
    
    # Apply branch filter if provided (only for superuser)
    if is_superuser and branch_id:
        orders_base = orders_base.filter(branch_id=branch_id)
        accessible_branches = accessible_branches.filter(id=branch_id)
    
    # Get all expenses with access filtering
    expenses = get_user_expenses(request.user).select_related('branch', 'branch__center')
    
    # Apply same filters to expenses
    if is_superuser and center_id:
        expenses = expenses.filter(branch__center_id=center_id)
    elif is_center_owner and user_profile.center:
        expenses = expenses.filter(branch__center=user_profile.center)
    else:
        # Staff - only their branches
        expenses = expenses.filter(branch__in=accessible_branches)
    
    if is_superuser and branch_id:
        expenses = expenses.filter(branch_id=branch_id)
    
    # Apply expense type filter
    if expense_type_filter in ['b2b', 'b2c']:
        expenses = expenses.filter(expense_type__in=[expense_type_filter, 'both'])
    
    # Calculate expense totals based on actual order usage
    # For each expense, find how many orders use it (through products) and multiply by expense price
    expense_usage = {}
    total_expense_cost = Decimal('0')
    b2b_expense_cost = Decimal('0')
    b2c_expense_cost = Decimal('0')
    both_expense_cost = Decimal('0')
    
    for expense in expenses:
        # Get products that use this expense
        products_with_expense = expense.products.all()
        
        # Count orders that use these products
        order_count = orders_base.filter(product__in=products_with_expense).count()
        
        # Calculate total cost for this expense
        expense_total = expense.price * order_count
        
        expense_usage[expense.id] = {
            'expense': expense,
            'order_count': order_count,
            'total_cost': expense_total
        }
        
        total_expense_cost += expense_total
        
        # Track by type
        if expense.expense_type == 'b2b':
            b2b_expense_cost += expense_total
        elif expense.expense_type == 'b2c':
            b2c_expense_cost += expense_total
        else:  # 'both'
            both_expense_cost += expense_total
    
    # Calculate totals
    total_expenses = {
        'total': total_expense_cost,
        'count': sum(e['order_count'] for e in expense_usage.values())
    }
    
    # B2B/B2C breakdown
    b2b_expenses = {
        'total': b2b_expense_cost,
        'count': sum(e['order_count'] for e in expense_usage.values() if e['expense'].expense_type == 'b2b')
    }
    b2c_expenses = {
        'total': b2c_expense_cost,
        'count': sum(e['order_count'] for e in expense_usage.values() if e['expense'].expense_type == 'b2c')
    }
    both_expenses = {
        'total': both_expense_cost,
        'count': sum(e['order_count'] for e in expense_usage.values() if e['expense'].expense_type == 'both')
    }
    
    # Analytics by center (for superuser)
    by_center = []
    if is_superuser:
        for center in accessible_centers:
            center_orders = orders_base.filter(branch__center=center)
            center_expenses = expenses.filter(branch__center=center)
            
            center_total = Decimal('0')
            center_count = 0
            
            # Calculate center expense totals
            for expense in center_expenses:
                products_with_expense = expense.products.all()
                order_count = center_orders.filter(product__in=products_with_expense).count()
                center_total += expense.price * order_count
                center_count += order_count
            
            # Get branch breakdown for this center
            center_branches_data = []
            for branch in center.branches.filter(is_active=True):
                branch_orders = center_orders.filter(branch=branch)
                branch_expenses = center_expenses.filter(branch=branch)
                
                branch_total = Decimal('0')
                branch_count = 0
                branch_b2b = Decimal('0')
                branch_b2c = Decimal('0')
                branch_both = Decimal('0')
                
                for expense in branch_expenses:
                    products_with_expense = expense.products.all()
                    order_count = branch_orders.filter(product__in=products_with_expense).count()
                    expense_total = expense.price * order_count
                    
                    branch_total += expense_total
                    branch_count += order_count
                    
                    if expense.expense_type == 'b2b':
                        branch_b2b += expense_total
                    elif expense.expense_type == 'b2c':
                        branch_b2c += expense_total
                    else:
                        branch_both += expense_total
                
                if branch_total > 0:  # Only include branches with expenses
                    center_branches_data.append({
                        'branch__id': branch.id,
                        'branch__name': branch.name,
                        'total': branch_total,
                        'count': branch_count,
                        'b2b_total': branch_b2b,
                        'b2c_total': branch_b2c,
                        'both_total': branch_both
                    })
            
            center_branches_data.sort(key=lambda x: x['total'], reverse=True)
            
            by_center.append({
                'center': center,
                'total': center_total,
                'count': center_count,
                'branches': center_branches_data
            })
    
    # Analytics by branch (for center-level and branch-level users)
    by_branch_data = []
    for branch in accessible_branches:
        branch_orders = orders_base.filter(branch=branch)
        branch_expenses = expenses.filter(branch=branch)
        
        branch_total = Decimal('0')
        branch_count = 0
        branch_b2b = Decimal('0')
        branch_b2c = Decimal('0')
        branch_both = Decimal('0')
        
        for expense in branch_expenses:
            products_with_expense = expense.products.all()
            order_count = branch_orders.filter(product__in=products_with_expense).count()
            expense_total = expense.price * order_count
            
            branch_total += expense_total
            branch_count += order_count
            
            if expense.expense_type == 'b2b':
                branch_b2b += expense_total
            elif expense.expense_type == 'b2c':
                branch_b2c += expense_total
            else:
                branch_both += expense_total
        
        if branch_total > 0:  # Only include branches with expenses
            by_branch_data.append({
                'branch__id': branch.id,
                'branch__name': branch.name,
                'branch__center__name': branch.center.name,
                'total': branch_total,
                'count': branch_count,
                'b2b_total': branch_b2b,
                'b2c_total': branch_b2c,
                'both_total': branch_both,
                'avg_expense': branch_total / branch_count if branch_count > 0 else Decimal('0')
            })
    
    by_branch_data.sort(key=lambda x: x['total'], reverse=True)
    
    # Top expenses by total cost (price * usage)
    top_expenses_list = []
    for expense_id, data in expense_usage.items():
        top_expenses_list.append({
            'expense': data['expense'],
            'order_count': data['order_count'],
            'total_cost': data['total_cost']
        })
    top_expenses_list.sort(key=lambda x: x['total_cost'], reverse=True)
    top_expenses = top_expenses_list[:10]
    
    # Expense type distribution
    type_distribution = [
        {'expense_type': 'b2b', 'total': b2b_expense_cost, 'count': b2b_expenses['count']},
        {'expense_type': 'b2c', 'total': b2c_expense_cost, 'count': b2c_expenses['count']},
        {'expense_type': 'both', 'total': both_expense_cost, 'count': both_expenses['count']},
    ]
    type_distribution = [t for t in type_distribution if t['total'] > 0]  # Remove empty types
    
    # Additional statistics
    if expense_usage:
        all_costs = [e['total_cost'] for e in expense_usage.values() if e['total_cost'] > 0]
        expense_stats = {
            'max_price': max(all_costs) if all_costs else Decimal('0'),
            'min_price': min(all_costs) if all_costs else Decimal('0'),
            'avg_price': sum(all_costs) / len(all_costs) if all_costs else Decimal('0')
        }
    else:
        expense_stats = {
            'max_price': Decimal('0'),
            'min_price': Decimal('0'),
            'avg_price': Decimal('0')
        }
    
    # Calculate median
    median_expense = Decimal('0')
    if expense_usage:
        sorted_costs = sorted([e['total_cost'] for e in expense_usage.values() if e['total_cost'] > 0])
        if sorted_costs:
            middle_index = len(sorted_costs) // 2
            if len(sorted_costs) % 2 == 0:
                median_expense = (sorted_costs[middle_index - 1] + sorted_costs[middle_index]) / 2
            else:
                median_expense = sorted_costs[middle_index]
    
    # Monthly trend (if period is long enough)
    monthly_trend = []
    monthly_trend_labels = []
    monthly_trend_values = []
    if (period_data['date_to'] - period_data['date_from']).days > 31:
        # Group orders by month and calculate expense costs
        from django.db.models.functions import TruncMonth
        monthly_orders = orders_base.annotate(
            month=TruncMonth('created_at')
        ).values('month', 'product').annotate(
            order_count=Count('id')
        )
        
        # Build monthly trend data
        monthly_data = {}
        for item in monthly_orders:
            month = item['month']
            product_id = item['product']
            order_count = item['order_count']
            
            # Find expenses for this product
            from services.models import Product
            try:
                product = Product.objects.get(id=product_id)
                for expense in product.expenses.all():
                    if expense.id in expense_usage:
                        if month not in monthly_data:
                            monthly_data[month] = Decimal('0')
                        monthly_data[month] += expense.price * order_count
            except Product.DoesNotExist:
                pass
        
        # Sort by month
        sorted_months = sorted(monthly_data.items())
        for month_date, total in sorted_months:
            monthly_trend.append({'month': month_date, 'total': total, 'count': 0})
            monthly_trend_labels.append(month_date.strftime('%b %Y') if month_date else 'N/A')
            monthly_trend_values.append(float(total or 0))
    
    # Prepare chart data
    branch_labels = [item['branch__name'] for item in by_branch_data[:10]]
    branch_totals = [float(item['total'] or 0) for item in by_branch_data[:10]]
    branch_b2b = [float(item['b2b_total'] or 0) for item in by_branch_data[:10]]
    branch_b2c = [float(item['b2c_total'] or 0) for item in by_branch_data[:10]]
    branch_both = [float(item['both_total'] or 0) for item in by_branch_data[:10]]
    
    type_labels = []
    type_values = []
    for item in type_distribution:
        if item['expense_type'] == 'b2b':
            type_labels.append('B2B (Agency/Business)')
        elif item['expense_type'] == 'b2c':
            type_labels.append('B2C (Individual Customer)')
        else:
            type_labels.append('Both B2B & B2C')
        type_values.append(float(item['total'] or 0))
    
    context = {
        "title": "Expense Analytics Report",
        "subTitle": "Detailed expense analysis by center, branch, and type",
        # Date filter
        "period": period,
        "period_choices": PERIOD_CHOICES,
        "date_from": period_data['date_from_str'],
        "date_to": period_data['date_to_str'],
        "period_label": period_data['label'],
        # Filters
        "expense_type_filter": expense_type_filter,
        "centers": accessible_centers if is_superuser else [],
        "branches": accessible_branches,
        "selected_center": center_id,
        "selected_branch": branch_id,
        # User role
        "is_superuser": is_superuser,
        "is_center_level": is_center_owner and not is_superuser,
        "is_branch_level": not is_center_owner and not is_superuser,
        # Summary
        "total_expenses": total_expenses['total'] or Decimal('0'),
        "total_count": total_expenses['count'],
        "b2b_total": b2b_expenses['total'] or Decimal('0'),
        "b2b_count": b2b_expenses['count'],
        "b2c_total": b2c_expenses['total'] or Decimal('0'),
        "b2c_count": b2c_expenses['count'],
        "both_total": both_expenses['total'] or Decimal('0'),
        "both_count": both_expenses['count'],
        # Statistics
        "highest_expense": expense_stats['max_price'] or Decimal('0'),
        "lowest_expense": expense_stats['min_price'] or Decimal('0'),
        "avg_expense": expense_stats['avg_price'] or Decimal('0'),
        "median_expense": median_expense,
        # Breakdowns
        "by_center": by_center,
        "by_branch": by_branch_data,
        "top_expenses": top_expenses,
        "type_distribution": type_distribution,
        "monthly_trend": monthly_trend,
        # Chart data
        "branch_labels": json.dumps(branch_labels),
        "branch_totals": json.dumps(branch_totals),
        "branch_b2b": json.dumps(branch_b2b),
        "branch_b2c": json.dumps(branch_b2c),
        "branch_both": json.dumps(branch_both),
        "type_labels": json.dumps(type_labels),
        "type_values": json.dumps(type_values),
        "monthly_trend_labels": json.dumps(monthly_trend_labels),
        "monthly_trend_values": json.dumps(monthly_trend_values),
    }
    
    return render(request, "reports/expense_analytics.html", context)
