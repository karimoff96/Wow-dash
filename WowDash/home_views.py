from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta
from orders.models import Order
from organizations.rbac import (
    get_user_orders,
    get_user_branches,
    get_user_customers,
    any_permission_required,
)
from organizations.models import AdminUser
import json


def email(request):
    context = {
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request, "email.html", context)


@login_required(login_url="admin_login")
def audit_logs_redirect(request):
    """Redirect to core audit logs view"""
    from core.views import audit_logs
    return audit_logs(request)


@login_required(login_url="admin_login")
def index(request):
    """Dashboard - Executive Summary with brief overview - Role-specific"""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    # Use RBAC-filtered orders
    all_orders = get_user_orders(request.user)

    # Quick stats
    today_orders = all_orders.filter(created_at__gte=today_start)
    yesterday_orders = all_orders.filter(
        created_at__gte=yesterday_start, created_at__lt=today_start
    )
    monthly_orders = all_orders.filter(created_at__gte=month_start)

    today_count = today_orders.count()
    today_revenue = float(
        today_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    yesterday_count = yesterday_orders.count()
    yesterday_revenue = float(
        yesterday_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    monthly_count = monthly_orders.count()
    monthly_revenue = float(
        monthly_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    # Calculate change from yesterday
    order_change = today_count - yesterday_count
    revenue_change = today_revenue - yesterday_revenue

    # User stats - RBAC filtered
    customers = get_user_customers(request.user)
    total_users = customers.count()
    total_agencies = customers.filter(is_agency=True).count()

    # Status counts for today
    completed_today = today_orders.filter(status="completed").count()
    cancelled_today = today_orders.filter(status="cancelled").count()
    in_progress_today = today_orders.filter(status="in_progress").count()

    # Pending orders (orders requiring attention)
    pending_orders = all_orders.filter(
        status__in=[
            "pending",
            "payment_pending",
            "payment_received",
            "payment_confirmed",
            "in_progress",
            "ready",
        ]
    ).count()

    # Unassigned orders (for managers/owners)
    unassigned_orders = all_orders.filter(
        assigned_to__isnull=True,
        status__in=[
            "pending",
            "payment_pending",
            "payment_received",
            "payment_confirmed",
        ],
    ).count()

    # Cancelled orders this week (alert)
    cancelled_week = all_orders.filter(
        created_at__gte=week_start, status="cancelled"
    ).count()

    # Completion rate today
    if today_count > 0:
        completion_rate = round((completed_today / today_count) * 100)
    else:
        completion_rate = 0

    # Weekly revenue chart data
    weekly_chart_data = []
    weekly_chart_labels = []
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        revenue = (
            all_orders.filter(
                created_at__gte=day_start, created_at__lt=day_end
            ).aggregate(total=Sum("total_price"))["total"]
            or 0
        )
        weekly_chart_data.append(float(revenue))
        weekly_chart_labels.append(day_start.strftime("%a"))

    # Mini chart data for orders by hour today
    hourly_orders = []
    for hour in range(24):
        hour_start = today_start + timedelta(hours=hour)
        hour_end = hour_start + timedelta(hours=1)
        if hour_end <= now:
            count = today_orders.filter(
                created_at__gte=hour_start, created_at__lt=hour_end
            ).count()
            hourly_orders.append(count)

    # Recent orders (last 5)
    recent_orders = all_orders.select_related("bot_user", "product").order_by(
        "-created_at"
    )[:5]
    recent_orders_data = []
    for order in recent_orders:
        recent_orders_data.append(
            {
                "id": order.id,
                "customer": order.bot_user.name if order.bot_user else "Unknown",
                "product": order.product.name if order.product else "Unknown",
                "total_price": float(order.total_price or 0),
                "status": order.status,
                "status_display": order.get_status_display(),
                "created_at": order.created_at.strftime("%H:%M"),
            }
        )

    # Total revenue all time
    total_revenue = float(all_orders.aggregate(total=Sum("total_price"))["total"] or 0)
    total_orders = all_orders.count()

    # Role-specific data
    role_context = {}

    if request.user.is_superuser:
        # Superuser sees everything
        from organizations.models import TranslationCenter, Branch

        role_context = {
            "total_centers": TranslationCenter.objects.filter(is_active=True).count(),
            "total_branches": Branch.objects.filter(is_active=True).count(),
            "total_staff": AdminUser.objects.filter(is_active=True).count(),
            "role_title": "System Overview",
        }
    elif hasattr(request, "admin_profile") and request.admin_profile:
        profile = request.admin_profile

        if profile.is_owner and profile.center:
            # Owner sees their center and all branches in their center
            from organizations.models import TranslationCenter, Branch

            center = profile.center
            branches = Branch.objects.filter(center=center, is_active=True)
            staff = AdminUser.objects.filter(center=center, is_active=True)

            # Branch performance data
            branch_performance = []
            for branch in branches[:5]:
                branch_orders = all_orders.filter(
                    branch=branch, created_at__gte=month_start
                )
                branch_revenue = float(
                    branch_orders.aggregate(total=Sum("total_price"))["total"] or 0
                )
                branch_performance.append(
                    {
                        "id": branch.id,
                        "name": branch.name,
                        "orders": branch_orders.count(),
                        "revenue": branch_revenue,
                    }
                )

            role_context = {
                "total_centers": 1,  # Owner sees their own center
                "total_branches": branches.count(),
                "total_staff": staff.count(),
                "branch_performance": branch_performance,
                "role_title": "Owner Dashboard",
            }

        elif profile.is_manager:
            # Manager sees their branch
            branch = profile.branch
            branch_staff = (
                AdminUser.objects.filter(branch=branch, is_active=True)
                if branch
                else AdminUser.objects.none()
            )

            # Staff performance
            staff_performance = []
            for staff_member in branch_staff.exclude(pk=profile.pk)[:5]:
                staff_orders = all_orders.filter(
                    assigned_to=staff_member, created_at__gte=month_start
                )
                staff_completed = staff_orders.filter(status="completed").count()
                staff_performance.append(
                    {
                        "name": staff_member.user.get_full_name()
                        or staff_member.user.username,
                        "assigned": staff_orders.count(),
                        "completed": staff_completed,
                    }
                )

            role_context = {
                "branch_name": branch.name if branch else "No Branch",
                "total_staff": branch_staff.count(),
                "staff_performance": staff_performance,
                "role_title": "Manager Dashboard",
            }

        else:
            # Staff sees their assigned orders
            my_orders = all_orders.filter(assigned_to=profile)
            my_pending = my_orders.filter(status__in=["in_progress", "ready"]).count()
            my_completed_today = my_orders.filter(
                status="completed", updated_at__gte=today_start
            ).count()
            my_total_completed = my_orders.filter(status="completed").count()

            role_context = {
                "my_pending": my_pending,
                "my_completed_today": my_completed_today,
                "my_total_completed": my_total_completed,
                "my_total_assigned": my_orders.count(),
                "role_title": "My Dashboard",
            }

    context = {
        "title": "Dashboard",
        "subTitle": "Executive Summary",
        # Today stats
        "today_count": today_count,
        "today_revenue": today_revenue,
        "order_change": order_change,
        "revenue_change": revenue_change,
        # Monthly stats
        "monthly_count": monthly_count,
        "monthly_revenue": monthly_revenue,
        # User stats
        "total_users": total_users,
        "total_agencies": total_agencies,
        # Status overview
        "completed_today": completed_today,
        "cancelled_today": cancelled_today,
        "in_progress_today": in_progress_today,
        "completion_rate": completion_rate,
        # Alerts
        "pending_orders": pending_orders,
        "unassigned_orders": unassigned_orders,
        "cancelled_week": cancelled_week,
        # Charts
        "weekly_chart_data": json.dumps(weekly_chart_data),
        "weekly_chart_labels": json.dumps(weekly_chart_labels),
        "hourly_orders": json.dumps(hourly_orders),
        # Recent orders
        "recent_orders": recent_orders_data,
        # Totals
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        # Role-specific
        **role_context,
    }
    return render(request, "index.html", context)


def kanban(request):
    context = {
        "title": "Kanban",
        "subTitle": "Kanban",
    }
    return render(request, "kanban.html", context)


def stared(request):
    context = {
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request, "stared.html", context)


def termsAndConditions(request):
    context = {
        "title": "Terms & Condition",
        "subTitle": "Terms & Condition",
    }
    return render(request, "termsAndConditions.html", context)


def viewDetails(request):
    context = {
        "title": "Email",
        "subTitle": "Components / Email",
    }
    return render(request, "viewDetails.html", context)


def widgets(request):
    context = {
        "title": "Widgets",
        "subTitle": "Widgets",
    }
    return render(request, "widgets.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_reports', 'can_view_analytics')
def sales(request):
    """Sales Dashboard - requires can_view_reports or can_view_analytics permission"""
    # Period filter for UI state (data is already computed for all periods)
    period = request.GET.get("period", "year")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    
    # Period label for display
    period_labels = {
        "today": "Today",
        "week": "This Week",
        "month": "This Month",
        "year": "This Year",
        "custom": f"{date_from} to {date_to}" if date_from and date_to else "Custom Range"
    }
    period_label = period_labels.get(period, "This Year")
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    # Get RBAC-filtered orders
    all_orders = get_user_orders(request.user)

    # ============ ORDER STATUS DATA FOR DONUT CHART ============
    # Status choices from model
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
        "pending": "#FF9F29",  # Orange
        "payment_pending": "#6C757D",  # Gray
        "payment_received": "#17A2B8",  # Info/Cyan
        "payment_confirmed": "#28A745",  # Green
        "in_progress": "#487FFF",  # Blue
        "ready": "#6F42C1",  # Purple
        "completed": "#45B369",  # Success Green
        "cancelled": "#DC3545",  # Red
    }

    def get_status_counts(orders_queryset):
        """Get status counts for a given queryset"""
        status_counts = orders_queryset.values("status").annotate(count=Count("status"))
        result = {status: 0 for status in STATUS_LABELS.keys()}
        for item in status_counts:
            result[item["status"]] = item["count"]
        return result

    # Get status counts for each period
    today_status_counts = get_status_counts(
        all_orders.filter(created_at__gte=today_start)
    )
    weekly_status_counts = get_status_counts(
        all_orders.filter(created_at__gte=week_start)
    )
    monthly_status_counts = get_status_counts(
        all_orders.filter(created_at__gte=month_start)
    )
    yearly_status_counts = get_status_counts(
        all_orders.filter(created_at__gte=year_start)
    )

    # Prepare data for each period (only non-zero statuses)
    def prepare_chart_data(status_counts):
        labels = []
        values = []
        colors = []
        for status, count in status_counts.items():
            if count > 0:
                labels.append(STATUS_LABELS[status])
                values.append(count)
                colors.append(STATUS_COLORS[status])
        # If no data, add a placeholder
        if not values:
            labels = ["No Orders"]
            values = [1]
            colors = ["#E4F1FF"]
        return {"labels": labels, "values": values, "colors": colors}

    status_chart_data = {
        "today": prepare_chart_data(today_status_counts),
        "weekly": prepare_chart_data(weekly_status_counts),
        "monthly": prepare_chart_data(monthly_status_counts),
        "yearly": prepare_chart_data(yearly_status_counts),
    }

    # ============ TOP 5 AGENCIES AND CUSTOMERS ============
    def get_top_users(orders_queryset, is_agency=True, limit=5):
        """Get top users by order count"""
        return (
            orders_queryset.filter(bot_user__is_agency=is_agency)
            .values(
                "bot_user__id",
                "bot_user__name",
                "bot_user__username",
                "bot_user__phone",
                "bot_user__created_at",
            )
            .annotate(
                order_count=Count("id"),
                total_spent=Sum("total_price"),
                total_pages=Sum("total_pages"),
            )
            .order_by("-order_count")[:limit]
        )

    # Get top agencies and customers for each period
    def serialize_top_users(queryset):
        """Convert queryset to list of dicts for JSON serialization"""
        result = []
        for user in queryset:
            result.append(
                {
                    "id": user["bot_user__id"],
                    "name": user["bot_user__name"] or "Unknown",
                    "username": user["bot_user__username"] or "-",
                    "phone": user["bot_user__phone"] or "-",
                    "joined": (
                        user["bot_user__created_at"].strftime("%d %b %Y")
                        if user["bot_user__created_at"]
                        else "-"
                    ),
                    "order_count": user["order_count"],
                    "total_spent": float(user["total_spent"] or 0),
                    "total_pages": user["total_pages"] or 0,
                }
            )
        return result

    top_agencies_data = {
        "today": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=today_start), is_agency=True
            )
        ),
        "weekly": serialize_top_users(
            get_top_users(all_orders.filter(created_at__gte=week_start), is_agency=True)
        ),
        "monthly": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=month_start), is_agency=True
            )
        ),
        "yearly": serialize_top_users(
            get_top_users(all_orders.filter(created_at__gte=year_start), is_agency=True)
        ),
    }

    top_customers_data = {
        "today": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=today_start), is_agency=False
            )
        ),
        "weekly": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=week_start), is_agency=False
            )
        ),
        "monthly": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=month_start), is_agency=False
            )
        ),
        "yearly": serialize_top_users(
            get_top_users(
                all_orders.filter(created_at__gte=year_start), is_agency=False
            )
        ),
    }

    # Today's orders
    today_orders = all_orders.filter(created_at__gte=today_start)
    today_count = today_orders.count()
    today_revenue = today_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # This week's orders
    weekly_orders = all_orders.filter(created_at__gte=week_start)
    weekly_count = weekly_orders.count()
    weekly_revenue = weekly_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # This month's orders
    monthly_orders = all_orders.filter(created_at__gte=month_start)
    monthly_count = monthly_orders.count()
    monthly_revenue = monthly_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # This year's orders
    yearly_orders = all_orders.filter(created_at__gte=year_start)
    yearly_count = yearly_orders.count()
    yearly_revenue = yearly_orders.aggregate(total=Sum("total_price"))["total"] or 0

    # Calculate daily average for each period
    days_in_week = max((now - week_start).days, 1)
    days_in_month = max((now - month_start).days, 1)
    days_in_year = max((now - year_start).days, 1)

    daily_avg_weekly = weekly_revenue / days_in_week if days_in_week > 0 else 0
    daily_avg_monthly = monthly_revenue / days_in_month if days_in_month > 0 else 0
    daily_avg_yearly = yearly_revenue / days_in_year if days_in_year > 0 else 0

    # Calculate percentage change (compare with previous period)
    yesterday_start = today_start - timedelta(days=1)
    yesterday_orders = all_orders.filter(
        created_at__gte=yesterday_start, created_at__lt=today_start
    )
    yesterday_revenue = (
        yesterday_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    prev_week_start = week_start - timedelta(days=7)
    prev_week_orders = all_orders.filter(
        created_at__gte=prev_week_start, created_at__lt=week_start
    )
    prev_week_revenue = (
        prev_week_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_month_orders = all_orders.filter(
        created_at__gte=prev_month_start, created_at__lt=month_start
    )
    prev_month_revenue = (
        prev_month_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    prev_year_start = year_start.replace(year=year_start.year - 1)
    prev_year_orders = all_orders.filter(
        created_at__gte=prev_year_start, created_at__lt=year_start
    )
    prev_year_revenue = (
        prev_year_orders.aggregate(total=Sum("total_price"))["total"] or 0
    )

    # Calculate percentage changes
    def calc_percentage(current, previous):
        if previous > 0:
            return round(((current - previous) / previous) * 100, 1)
        return 100 if current > 0 else 0

    today_change = calc_percentage(float(today_revenue), float(yesterday_revenue))
    weekly_change = calc_percentage(float(weekly_revenue), float(prev_week_revenue))
    monthly_change = calc_percentage(float(monthly_revenue), float(prev_month_revenue))
    yearly_change = calc_percentage(float(yearly_revenue), float(prev_year_revenue))

    # ============ CHART DATA FOR EACH PERIOD ============

    # Yearly chart data (12 months) - ORDER COUNTS
    yearly_chart_data = []
    yearly_chart_labels = []
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i * 30)
        m_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            m_end = (m_start + timedelta(days=32)).replace(day=1)
        else:
            m_end = now

        m_count = all_orders.filter(
            created_at__gte=m_start, created_at__lt=m_end
        ).count()
        yearly_chart_data.append(m_count)
        yearly_chart_labels.append(m_start.strftime("%b"))

    # Monthly chart data (days of current month) - ORDER COUNTS
    import calendar

    days_in_current_month = calendar.monthrange(now.year, now.month)[1]
    monthly_chart_data = []
    monthly_chart_labels = []
    for day in range(1, days_in_current_month + 1):
        day_start = month_start.replace(day=day)
        day_end = day_start + timedelta(days=1)
        if day_start > now:
            break
        d_count = all_orders.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).count()
        monthly_chart_data.append(d_count)
        monthly_chart_labels.append(str(day))

    # Weekly chart data (7 days) - ORDER COUNTS
    weekly_chart_data = []
    weekly_chart_labels = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i in range(7):
        day_start = week_start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        if day_start > now:
            break
        d_count = all_orders.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).count()
        weekly_chart_data.append(d_count)
        weekly_chart_labels.append(day_names[i])

    # Today chart data (24 hours) - ORDER COUNTS
    today_chart_data = []
    today_chart_labels = []
    for hour in range(24):
        hour_start = today_start.replace(hour=hour)
        hour_end = hour_start + timedelta(hours=1)
        if hour_start > now:
            break
        h_count = all_orders.filter(
            created_at__gte=hour_start, created_at__lt=hour_end
        ).count()
        today_chart_data.append(h_count)
        today_chart_labels.append(f"{hour:02d}:00")

    # ============ RECENT ORDERS ============
    recent_orders = all_orders.select_related(
        "bot_user", "product", "branch", "branch__center"
    ).order_by("-created_at")[:10]
    recent_orders_data = []
    for order in recent_orders:
        recent_orders_data.append(
            {
                "id": order.id,
                "customer": order.bot_user.name if order.bot_user else "Unknown",
                "product": order.product.name if order.product else "Unknown",
                "total_price": float(order.total_price or 0),
                "status": order.status,
                "status_display": STATUS_LABELS.get(order.status, order.status),
                "created_at": order.created_at.strftime("%d %b %Y, %H:%M"),
                "branch": order.branch.name if order.branch else None,
                "branch_id": order.branch.id if order.branch else None,
                "center": (
                    order.branch.center.name
                    if order.branch and order.branch.center
                    else None
                ),
                "center_id": (
                    order.branch.center.id
                    if order.branch and order.branch.center
                    else None
                ),
            }
        )

    # ============ COMPLETION RATES ============
    def get_completion_rate(orders_queryset):
        total = orders_queryset.count()
        if total == 0:
            return {"completed": 0, "in_progress": 0, "cancelled": 0, "rate": 0}
        completed = orders_queryset.filter(status="completed").count()
        cancelled = orders_queryset.filter(status="cancelled").count()
        in_progress = orders_queryset.filter(
            status__in=[
                "pending",
                "payment_pending",
                "payment_received",
                "payment_confirmed",
                "in_progress",
                "ready",
            ]
        ).count()
        rate = round((completed / total) * 100, 1) if total > 0 else 0
        return {
            "completed": completed,
            "in_progress": in_progress,
            "cancelled": cancelled,
            "total": total,
            "rate": rate,
        }

    completion_rates = {
        "today": get_completion_rate(all_orders.filter(created_at__gte=today_start)),
        "weekly": get_completion_rate(all_orders.filter(created_at__gte=week_start)),
        "monthly": get_completion_rate(all_orders.filter(created_at__gte=month_start)),
        "yearly": get_completion_rate(all_orders.filter(created_at__gte=year_start)),
    }

    context = {
        "title": "Sales Statistics",
        "subTitle": "Sales",
        # Period filter state
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "period_label": period_label,
        # Today
        "today_count": today_count,
        "today_revenue": today_revenue,
        "today_change": today_change,
        "today_daily_avg": today_revenue,  # For today, daily avg is today's revenue
        # Weekly
        "weekly_count": weekly_count,
        "weekly_revenue": weekly_revenue,
        "weekly_change": weekly_change,
        "weekly_daily_avg": round(daily_avg_weekly, 2),
        # Monthly
        "monthly_count": monthly_count,
        "monthly_revenue": monthly_revenue,
        "monthly_change": monthly_change,
        "monthly_daily_avg": round(daily_avg_monthly, 2),
        # Yearly
        "yearly_count": yearly_count,
        "yearly_revenue": yearly_revenue,
        "yearly_change": yearly_change,
        "yearly_daily_avg": round(daily_avg_yearly, 2),
        # Chart data for each period (JSON for JS)
        "yearly_chart_data": json.dumps(yearly_chart_data),
        "yearly_chart_labels": json.dumps(yearly_chart_labels),
        "monthly_chart_data": json.dumps(monthly_chart_data),
        "monthly_chart_labels": json.dumps(monthly_chart_labels),
        "weekly_chart_data": json.dumps(weekly_chart_data),
        "weekly_chart_labels": json.dumps(weekly_chart_labels),
        "today_chart_data": json.dumps(today_chart_data),
        "today_chart_labels": json.dumps(today_chart_labels),
        # Order status chart data (JSON for JS)
        "status_chart_data": json.dumps(status_chart_data),
        # Top agencies and customers data (JSON for JS)
        "top_agencies_data": json.dumps(top_agencies_data),
        "top_customers_data": json.dumps(top_customers_data),
        # Recent orders
        "recent_orders": recent_orders_data,
        # Completion rates
        "completion_rates": json.dumps(completion_rates),
    }
    return render(request, "sales.html", context)


@login_required(login_url="admin_login")
@any_permission_required('can_view_financial_reports', 'can_view_analytics')
def finance(request):
    """Finance/Analytics page - requires can_view_financial_reports or can_view_analytics permission"""
    # Period filter for UI state
    period = request.GET.get("period", "year")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    
    # Period label for display
    period_labels = {
        "today": "Today",
        "week": "This Week",
        "month": "This Month",
        "year": "This Year",
        "custom": f"{date_from} to {date_to}" if date_from and date_to else "Custom Range"
    }
    period_label = period_labels.get(period, "This Year")
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)

    # Get RBAC-filtered orders
    all_orders = get_user_orders(request.user)

    # ============ REVENUE OVERVIEW ============
    def get_revenue_stats(orders_queryset):
        stats = orders_queryset.aggregate(
            total_revenue=Sum("total_price"),
            order_count=Count("id"),
            total_pages=Sum("total_pages"),
        )
        revenue = float(stats["total_revenue"] or 0)
        count = stats["order_count"] or 0
        pages = stats["total_pages"] or 0
        avg_order_value = revenue / count if count > 0 else 0
        return {
            "revenue": revenue,
            "count": count,
            "pages": pages,
            "avg_order_value": round(avg_order_value, 2),
        }

    today_stats = get_revenue_stats(all_orders.filter(created_at__gte=today_start))
    weekly_stats = get_revenue_stats(all_orders.filter(created_at__gte=week_start))
    monthly_stats = get_revenue_stats(all_orders.filter(created_at__gte=month_start))
    yearly_stats = get_revenue_stats(all_orders.filter(created_at__gte=year_start))

    # ============ PAYMENT TYPE BREAKDOWN ============
    def get_payment_breakdown(orders_queryset):
        breakdown = orders_queryset.values("payment_type").annotate(
            count=Count("id"), revenue=Sum("total_price")
        )
        result = {
            "cash": {"count": 0, "revenue": 0},
            "card": {"count": 0, "revenue": 0},
        }
        for item in breakdown:
            if item["payment_type"] in result:
                result[item["payment_type"]] = {
                    "count": item["count"],
                    "revenue": float(item["revenue"] or 0),
                }
        return result

    payment_breakdown = {
        "today": get_payment_breakdown(all_orders.filter(created_at__gte=today_start)),
        "weekly": get_payment_breakdown(all_orders.filter(created_at__gte=week_start)),
        "monthly": get_payment_breakdown(
            all_orders.filter(created_at__gte=month_start)
        ),
        "yearly": get_payment_breakdown(all_orders.filter(created_at__gte=year_start)),
    }

    # ============ REVENUE BY USER TYPE (Agency vs Regular) ============
    def get_user_type_revenue(orders_queryset):
        agency = orders_queryset.filter(bot_user__is_agency=True).aggregate(
            count=Count("id"), revenue=Sum("total_price")
        )
        regular = orders_queryset.filter(bot_user__is_agency=False).aggregate(
            count=Count("id"), revenue=Sum("total_price")
        )
        return {
            "agency": {
                "count": agency["count"] or 0,
                "revenue": float(agency["revenue"] or 0),
            },
            "regular": {
                "count": regular["count"] or 0,
                "revenue": float(regular["revenue"] or 0),
            },
        }

    user_type_revenue = {
        "today": get_user_type_revenue(all_orders.filter(created_at__gte=today_start)),
        "weekly": get_user_type_revenue(all_orders.filter(created_at__gte=week_start)),
        "monthly": get_user_type_revenue(
            all_orders.filter(created_at__gte=month_start)
        ),
        "yearly": get_user_type_revenue(all_orders.filter(created_at__gte=year_start)),
    }

    # ============ REVENUE BY PRODUCT ============
    def get_product_revenue(orders_queryset, limit=5):
        products = (
            orders_queryset.values("product__id", "product__name")
            .annotate(
                count=Count("id"), revenue=Sum("total_price"), pages=Sum("total_pages")
            )
            .order_by("-revenue")[:limit]
        )

        return [
            {
                "id": p["product__id"],
                "name": p["product__name"] or "Unknown",
                "count": p["count"],
                "revenue": float(p["revenue"] or 0),
                "pages": p["pages"] or 0,
            }
            for p in products
        ]

    product_revenue = {
        "today": get_product_revenue(all_orders.filter(created_at__gte=today_start)),
        "weekly": get_product_revenue(all_orders.filter(created_at__gte=week_start)),
        "monthly": get_product_revenue(all_orders.filter(created_at__gte=month_start)),
        "yearly": get_product_revenue(all_orders.filter(created_at__gte=year_start)),
    }

    # ============ MONTHLY REVENUE CHART (Last 12 months) ============
    monthly_revenue_chart = []
    monthly_revenue_labels = []
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i * 30)
        m_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            m_end = (m_start + timedelta(days=32)).replace(day=1)
        else:
            m_end = now

        m_revenue = (
            all_orders.filter(created_at__gte=m_start, created_at__lt=m_end).aggregate(
                total=Sum("total_price")
            )["total"]
            or 0
        )
        monthly_revenue_chart.append(float(m_revenue))
        monthly_revenue_labels.append(m_start.strftime("%b"))

    # ============ PENDING PAYMENTS (Card payments awaiting confirmation) ============
    pending_payments = all_orders.filter(
        payment_type="card", status__in=["payment_pending", "payment_received"]
    ).aggregate(count=Count("id"), total=Sum("total_price"))

    # ============ AVERAGE ORDER VALUE TREND (Last 7 days) ============
    aov_trend_data = []
    aov_trend_labels = []
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        day_stats = all_orders.filter(
            created_at__gte=day_start, created_at__lt=day_end
        ).aggregate(revenue=Sum("total_price"), count=Count("id"))
        revenue = float(day_stats["revenue"] or 0)
        count = day_stats["count"] or 0
        aov = revenue / count if count > 0 else 0
        aov_trend_data.append(round(aov, 2))
        aov_trend_labels.append(day_start.strftime("%a"))

    # ============ COMPARISON WITH PREVIOUS PERIOD ============
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    prev_month_stats = get_revenue_stats(
        all_orders.filter(created_at__gte=prev_month_start, created_at__lt=month_start)
    )

    monthly_revenue_change = 0
    if prev_month_stats["revenue"] > 0:
        monthly_revenue_change = round(
            (
                (monthly_stats["revenue"] - prev_month_stats["revenue"])
                / prev_month_stats["revenue"]
            )
            * 100,
            1,
        )

    context = {
        "title": "Finance & Analytics",
        "subTitle": "Finance",
        # Period filter state
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "period_label": period_label,
        # Revenue stats for each period
        "today_stats": today_stats,
        "weekly_stats": weekly_stats,
        "monthly_stats": monthly_stats,
        "yearly_stats": yearly_stats,
        # Payment breakdown (JSON for JS)
        "payment_breakdown": json.dumps(payment_breakdown),
        # User type revenue (JSON for JS)
        "user_type_revenue": json.dumps(user_type_revenue),
        # Product revenue (JSON for JS)
        "product_revenue": json.dumps(product_revenue),
        # Charts (JSON for JS)
        "monthly_revenue_chart": json.dumps(monthly_revenue_chart),
        "monthly_revenue_labels": json.dumps(monthly_revenue_labels),
        "aov_trend_data": json.dumps(aov_trend_data),
        "aov_trend_labels": json.dumps(aov_trend_labels),
        # Pending payments
        "pending_payments_count": pending_payments["count"] or 0,
        "pending_payments_total": float(pending_payments["total"] or 0),
        # Comparison
        "monthly_revenue_change": monthly_revenue_change,
    }
    return render(request, "finance.html", context)
