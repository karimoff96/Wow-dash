"""
Reports & Analytics Views
Financial/order reports per branch/center with date filtering
"""

from django.shortcuts import render
from django.db.models import Sum, Count, Avg
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

    # Center filter for superuser
    centers = None
    if request.user.is_superuser:
        centers = TranslationCenter.objects.filter(is_active=True)
        if center_id:
            all_orders = all_orders.filter(branch__center_id=center_id)
            branches = branches.filter(center_id=center_id)

    # Filter orders by date and branch
    orders = all_orders.filter(created_at__gte=date_from, created_at__lte=date_to)

    if branch_id:
        orders = orders.filter(branch_id=branch_id)
        selected_branch = branches.filter(id=branch_id).first()
    else:
        selected_branch = None

    # Get staff members based on permissions
    if request.user.is_superuser:
        staff_members = AdminUser.objects.filter(is_active=True)
        if center_id:
            staff_members = staff_members.filter(branch__center_id=center_id)
    elif hasattr(request, "admin_profile") and request.admin_profile:
        if request.admin_profile.is_owner:
            staff_members = AdminUser.objects.filter(
                center=request.admin_profile.center, is_active=True
            )
        elif request.admin_profile.is_manager:
            staff_members = AdminUser.objects.filter(
                branch=request.admin_profile.branch, is_active=True
            )
        else:
            staff_members = AdminUser.objects.filter(pk=request.admin_profile.pk)
    else:
        staff_members = AdminUser.objects.none()

    if branch_id:
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
        orders.values("bot_user__id", "bot_user__name", "bot_user__is_agency")
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
    }
    
    # Validate report type
    valid_types = [
        'orders', 'financial', 'staff_performance', 
        'branch_comparison', 'customers', 'unit_economy', 'my_statistics'
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
        "payment_pending": "Payment Pending",
        "payment_received": "Payment Received",
        "payment_confirmed": "Payment Confirmed",
        "in_progress": "In Progress",
        "ready": "Ready",
        "completed": "Completed",
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
    from services.analytics import get_unit_economy_analytics
    
    data = get_unit_economy_analytics(request.user)
    return JsonResponse(data)
