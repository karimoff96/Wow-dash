import logging
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

from core.models import AdminNotification, AuditLog
from organizations.rbac import permission_required

logger = logging.getLogger(__name__)


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notification = AdminNotification.objects.get(id=notification_id)
        notification.mark_as_read(request.user)
        return JsonResponse({'success': True})
    except AdminNotification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    from organizations.models import AdminProfile
    
    try:
        profile = request.user.admin_profile
        if profile.role == 'super_admin' or request.user.is_superuser:
            notifications = AdminNotification.objects.filter(is_read=False)
        elif profile.role == 'center_admin':
            notifications = AdminNotification.objects.filter(
                is_read=False,
                center=profile.translation_center
            )
        else:
            notifications = AdminNotification.objects.filter(
                is_read=False,
                branch=profile.branch
            )
        
        from django.utils import timezone
        count = notifications.update(
            is_read=True,
            read_by=request.user,
            read_at=timezone.now()
        )
        
        return JsonResponse({'success': True, 'count': count})
    except (AttributeError, AdminProfile.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)


@login_required
def get_notifications(request):
    """Get unread notifications for the current user (for AJAX refresh)"""
    notifications = AdminNotification.get_unread_for_user(request.user, limit=10)
    count = AdminNotification.count_unread_for_user(request.user)
    
    data = {
        'count': count,
        'notifications': [
            {
                'id': n.id,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'created_at': n.created_at.isoformat(),
            }
            for n in notifications
        ]
    }
    
    return JsonResponse(data)


# Period choices for audit log filtering
PERIOD_CHOICES = [
    ("today", _("Today")),
    ("yesterday", _("Yesterday")),
    ("week", _("This Week")),
    ("month", _("This Month")),
    ("custom", _("Custom Range")),
]


def get_period_dates(period, custom_from=None, custom_to=None):
    """Calculate date range based on selected period."""
    today = timezone.now()

    if period == "today":
        date_from = today.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = today
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "week":
        # Changed to last 7 days instead of current week (Monday-based)
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month":
        date_from = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        date_to = today
    elif period == "custom" and custom_from and custom_to:
        from datetime import datetime
        date_from = datetime.strptime(custom_from, "%Y-%m-%d")
        date_to = datetime.strptime(custom_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
        date_from = timezone.make_aware(date_from)
        date_to = timezone.make_aware(date_to)
    else:
        # Default to last 7 days
        date_from = today - timedelta(days=7)
        date_to = today

    return date_from, date_to


@login_required
@permission_required('can_view_audit_logs')
def audit_logs(request):
    """View audit logs with filtering and pagination."""
    from organizations.models import Branch, TranslationCenter
    from django.contrib.auth.models import User
    
    # Get filter parameters
    period = request.GET.get('period', 'month')  # Changed default to 'month' to show more data
    custom_from = request.GET.get('date_from')
    custom_to = request.GET.get('date_to')
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    branch_filter = request.GET.get('branch', '')
    center_filter = request.GET.get('center', '')
    search_query = request.GET.get('q', '')
    
    # Calculate date range
    date_from, date_to = get_period_dates(period, custom_from, custom_to)
    
    # Base queryset
    logs = AuditLog.objects.select_related('user', 'branch', 'center', 'content_type')
    
    # Filter by date range
    logs = logs.filter(created_at__gte=date_from, created_at__lte=date_to)
    
    # Role-based access control
    if request.user.is_superuser:
        # Superusers can see all logs
        centers = TranslationCenter.objects.filter(is_active=True)
        branches = Branch.objects.filter(is_active=True)
    elif request.admin_profile:
        if request.is_owner:
            # Owners see their center's logs
            centers = TranslationCenter.objects.filter(id=request.current_center.id)
            branches = Branch.objects.filter(center=request.current_center, is_active=True)
            logs = logs.filter(center=request.current_center)
        else:
            # Managers/Staff see their branch's logs
            centers = []
            branches = Branch.objects.filter(id=request.current_branch.id) if request.current_branch else []
            if request.current_branch:
                logs = logs.filter(branch=request.current_branch)
            else:
                logs = logs.none()
    else:
        logs = logs.none()
        centers = []
        branches = []
    
    # Apply filters
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if user_filter:
        logs = logs.filter(user_id=user_filter)
    
    if branch_filter and request.user.is_superuser:
        logs = logs.filter(branch_id=branch_filter)
    
    if center_filter and request.user.is_superuser:
        logs = logs.filter(center_id=center_filter)
    
    if search_query:
        logs = logs.filter(
            models.Q(target_repr__icontains=search_query) |
            models.Q(details__icontains=search_query) |
            models.Q(user__username__icontains=search_query)
        )
    
    # Get users for filter dropdown (based on accessible logs)
    if request.user.is_superuser:
        users = User.objects.filter(audit_logs__isnull=False).distinct()
    elif request.admin_profile and request.current_center:
        users = User.objects.filter(
            audit_logs__center=request.current_center
        ).distinct()
    else:
        users = User.objects.none()
    
    # Order by most recent first
    logs = logs.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'title': _('Audit Logs'),
        'subTitle': _('System activity and audit trail'),
        'logs': page_obj,
        'page_obj': page_obj,
        'period_choices': PERIOD_CHOICES,
        'period': period,
        'date_from': custom_from or date_from.strftime('%Y-%m-%d'),
        'date_to': custom_to or date_to.strftime('%Y-%m-%d'),
        'action_choices': AuditLog.ACTION_CHOICES,
        'action_filter': action_filter,
        'users': users,
        'user_filter': user_filter,
        'centers': centers,
        'branches': branches,
        'center_filter': center_filter,
        'branch_filter': branch_filter,
        'search_query': search_query,
    }
    
    return render(request, 'reports/audit_logs.html', context)
