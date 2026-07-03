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

from core.models import AdminNotification, AuditLog, NotificationRead
from organizations.rbac import permission_required
from billing.decorators import require_feature, require_active_subscription
from core.throttling import throttle

logger = logging.getLogger(__name__)


def _invalidate_notification_cache(user):
    """
    Delete the per-user notification cache key.
    Completely safe: wrapped in try/except so Redis failures are silently ignored.
    """
    try:
        from django.core.cache import cache
        cache.delete(f'notif:user:{user.pk}')
    except Exception:
        pass


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notification = AdminNotification.objects.get(id=notification_id)
        notification.mark_as_read(request.user)
        _invalidate_notification_cache(request.user)  # keep badge in sync
        return JsonResponse({'success': True})
    except AdminNotification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    try:
        from django.db.models import Exists, OuterRef

        already_read = NotificationRead.objects.filter(
            notification=OuterRef('pk'), user=request.user
        )

        # Mirror the exact same scoping logic used in
        # AdminNotification.get_unread_for_user() so the mark-all operation
        # covers precisely the notifications the user can see.
        if request.user.is_superuser:
            notifications = AdminNotification.objects.exclude(Exists(already_read))
        else:
            profile = getattr(request.user, 'admin_profile', None)
            if not profile:
                return JsonResponse({'success': False, 'error': 'No profile'}, status=403)

            if profile.role and profile.role.name == 'owner':
                notifications = AdminNotification.objects.filter(
                    center=profile.center
                ).exclude(Exists(already_read))
            elif profile.branch:
                notifications = AdminNotification.objects.filter(
                    branch=profile.branch
                ).exclude(Exists(already_read))
            elif profile.center:
                notifications = AdminNotification.objects.filter(
                    center=profile.center
                ).exclude(Exists(already_read))
            else:
                notifications = AdminNotification.objects.exclude(Exists(already_read))

        ids = list(notifications.values_list('id', flat=True))
        if ids:
            NotificationRead.objects.bulk_create(
                [NotificationRead(notification_id=nid, user=request.user) for nid in ids],
                ignore_conflicts=True,
            )

        _invalidate_notification_cache(request.user)  # bust cache immediately
        return JsonResponse({'success': True, 'count': len(ids)})
    except Exception as e:
        logger.warning(f"mark_all_notifications_read failed: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@throttle(max_calls=60, period=60, key_prefix='api_notif')  # max 60 fetches/min per user
def get_notifications(request):
    """
    Get unread notifications for the current user (for AJAX refresh).

    Redis cache strategy (30-second TTL, per-user key):
    - Cache hit  → return instantly, zero DB queries.
    - Cache miss → run original DB queries, store result, return data.
    - Redis down → run original DB queries (try/except guarantees this).
    Cache is invalidated immediately when the user reads a notification.
    """
    CACHE_KEY = f'notif:user:{request.user.pk}'
    CACHE_TTL = 30  # seconds — acceptable staleness for a notification badge

    # ── Fast path: try cache first ──────────────────────────────────────
    try:
        from django.core.cache import cache
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return JsonResponse(cached)
    except Exception:
        pass  # Redis unavailable — fall through to DB

    # ── Slow path: query DB (original logic, unchanged) ──────────────────
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

    # ── Store in cache for next request ─────────────────────────────────
    try:
        from django.core.cache import cache
        cache.set(CACHE_KEY, data, timeout=CACHE_TTL)
    except Exception:
        pass  # Redis write failure is harmless

    return JsonResponse(data)


@login_required
def notifications_list(request):
    """
    Full paginated notifications page for the current user's scope.
    Supports ?filter=all (default) or ?filter=unread.
    """
    filter_type = request.GET.get('filter', 'all')

    # Build base queryset using same scoping as get_unread_for_user
    if request.user.is_superuser:
        qs = AdminNotification.objects.all()
    else:
        profile = getattr(request.user, 'admin_profile', None)
        if not profile:
            qs = AdminNotification.objects.none()
        elif profile.role and profile.role.name == 'owner':
            qs = AdminNotification.objects.filter(center=profile.center)
        elif profile.branch:
            qs = AdminNotification.objects.filter(branch=profile.branch)
        elif profile.center:
            qs = AdminNotification.objects.filter(center=profile.center)
        else:
            qs = AdminNotification.objects.all()

    qs = qs.select_related('branch', 'center').order_by('-created_at')

    from django.db.models import Exists, OuterRef
    already_read = NotificationRead.objects.filter(
        notification=OuterRef('pk'), user=request.user
    )
    # Annotate each notification with whether the current user has read it
    qs = qs.annotate(user_has_read=Exists(already_read))

    total_count = qs.count()
    unread_count = qs.filter(user_has_read=False).count()

    if filter_type == 'unread':
        qs = qs.filter(user_has_read=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page', 1)
    notifications = paginator.get_page(page_number)

    read_count = total_count - unread_count

    # Smart page range: show first, last, current±2, with ellipsis gaps
    current = notifications.number
    total_pages = paginator.num_pages
    delta = 2
    left = max(1, current - delta)
    right = min(total_pages, current + delta)
    page_range = []
    if left > 1:
        page_range.append(1)
        if left > 2:
            page_range.append('...')
    page_range.extend(range(left, right + 1))
    if right < total_pages:
        if right < total_pages - 1:
            page_range.append('...')
        page_range.append(total_pages)

    return render(request, 'core/notifications.html', {
        'notifications': notifications,
        'total_count': total_count,
        'unread_count': unread_count,
        'read_count': read_count,
        'filter': filter_type,
        'page_range': page_range,
        'title': _('Notifications'),
        'subTitle': _('All Notifications'),
    })


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
@require_active_subscription
@require_feature('audit_logs')
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
