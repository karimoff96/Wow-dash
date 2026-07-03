import os
import logging
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Ticket, TicketCategory, TicketMessage, TicketAttachment, TicketStatusHistory
from .notification_service import notify_support_new_ticket, notify_support_staff_reply, notify_support_status_change
from organizations.rbac import admin_profile_required
from billing.decorators import require_active_subscription

logger = logging.getLogger(__name__)

ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.zip',
}
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _get_center(request):
    """Return the TranslationCenter for the current user (None for superusers)."""
    if request.user.is_superuser:
        return None
    if request.admin_profile:
        return request.admin_profile.center
    return None


def _can_view_all(request):
    """True if user can see all tickets for their center (not just their own)."""
    if request.user.is_superuser:
        return True
    return (
        getattr(request, 'is_owner', False) or
        getattr(request, 'is_manager', False) or
        (request.admin_profile and request.admin_profile.has_permission('can_view_all_orders'))
    )


def _save_attachments(message, files):
    """Validate and save uploaded files as TicketAttachment records."""
    for f in files:
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            continue
        if f.size > MAX_ATTACHMENT_SIZE:
            continue
        TicketAttachment.objects.create(
            message=message,
            file=f,
            original_filename=f.name[:255],
            file_size=f.size,
        )


def _superuser_required(view_func):
    """Restrict a view to superusers only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_superuser:
            messages.error(request, _('Access restricted to superusers.'))
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────────────
# STAFF SIDE — ticket creation & viewing
# ─────────────────────────────────────────────────────────────────────

@login_required
@require_active_subscription
@admin_profile_required
def ticket_list(request):
    """List tickets for the logged-in staff member (or all center tickets for managers)."""
    center = _get_center(request)
    view_all = _can_view_all(request)

    qs = Ticket.objects.select_related('category', 'created_by', 'center').all()

    if request.user.is_superuser:
        pass  # superuser sees all via the support inbox; here show all too
    elif center:
        qs = qs.filter(center=center)
        if not view_all:
            qs = qs.filter(created_by=request.user)
    else:
        qs = qs.filter(created_by=request.user)

    # ── Filters ──────────────────────────────────────────────────────
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if type_filter:
        qs = qs.filter(ticket_type=type_filter)
    if search:
        qs = qs.filter(
            Q(ticket_number__icontains=search) |
            Q(subject__icontains=search) |
            Q(description__icontains=search)
        )

    # ── Stats (based on same scope as query, before filters) ─────────
    base_qs = Ticket.objects.filter(center=center) if center else Ticket.objects.all()
    if not view_all and not request.user.is_superuser:
        base_qs = base_qs.filter(created_by=request.user)

    stats = {
        'total': base_qs.count(),
        'open': base_qs.filter(status=Ticket.STATUS_OPEN).count(),
        'in_progress': base_qs.filter(status=Ticket.STATUS_IN_PROGRESS).count(),
        'awaiting_staff': base_qs.filter(status=Ticket.STATUS_AWAITING_STAFF).count(),
        'resolved': base_qs.filter(
            status__in=[Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED]
        ).count(),
        'unread': base_qs.filter(has_unread_reply=True).count(),
    }

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'support/ticket_list.html', {
        'subTitle': _('My Tickets') if not view_all else _('All Tickets'),
        'page_obj': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'type_filter': type_filter,
        'search': search,
        'can_view_all': view_all,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'type_choices': Ticket.TYPE_CHOICES,
    })


@login_required
@require_active_subscription
@admin_profile_required
def ticket_create(request):
    """Create a new support ticket."""
    center = _get_center(request)

    # Non-superusers must be linked to a center; show a friendly error otherwise.
    if not request.user.is_superuser and center is None:
        messages.error(
            request,
            _('Your account is not linked to a center. Please ask your administrator to assign you to a center before submitting tickets.')
        )
        return redirect('support:ticket_list')

    categories_qs = TicketCategory.objects.filter(is_active=True)
    if center:
        center_cats = categories_qs.filter(center=center)
        # Fall back to all active categories if this center has none configured
        categories_qs = center_cats if center_cats.exists() else categories_qs
    categories = list(categories_qs)

    ctx = {
        'title': _('New Ticket'),
        'subTitle': _('Support Tickets'),
        'categories': categories,
        'ticket_types': Ticket.TYPE_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
    }

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category', '')
        ticket_type = request.POST.get('ticket_type', Ticket.TYPE_GENERAL)
        priority = request.POST.get('priority', Ticket.PRIORITY_NORMAL)

        errors = []
        if not subject:
            errors.append(_('Subject is required.'))
        if not description:
            errors.append(_('Description is required.'))
        if errors:
            for e in errors:
                messages.error(request, e)
            ctx['form_data'] = request.POST
            return render(request, 'support/ticket_create.html', ctx)

        category = None
        if category_id:
            try:
                category = TicketCategory.objects.get(pk=category_id)
            except TicketCategory.DoesNotExist:
                pass

        ticket = Ticket.objects.create(
            center=center,
            created_by=request.user,
            category=category,
            subject=subject,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            status=Ticket.STATUS_OPEN,
        )

        # First message = the description itself
        first_msg = TicketMessage.objects.create(
            ticket=ticket,
            sender_type=TicketMessage.SENDER_STAFF,
            sender=request.user,
            body=description,
        )
        _save_attachments(first_msg, request.FILES.getlist('attachments'))

        # One-way Telegram push to support
        try:
            notify_support_new_ticket(ticket)
        except Exception as exc:
            logger.error(f"Telegram notification failed for {ticket.ticket_number}: {exc}")

        messages.success(request, _(f'Ticket {ticket.ticket_number} submitted successfully.'))
        return redirect('support:ticket_detail', ticket_id=ticket.pk)

    return render(request, 'support/ticket_create.html', ctx)


@login_required
@require_active_subscription
@admin_profile_required
def ticket_detail(request, ticket_id):
    """View ticket thread and post a reply (staff side)."""
    center = _get_center(request)
    ticket = get_object_or_404(
        Ticket.objects.select_related('center', 'category', 'created_by'),
        pk=ticket_id,
    )

    # ── Access control ───────────────────────────────────────────────
    if not request.user.is_superuser:
        if center and ticket.center != center:
            messages.error(request, _('You do not have permission to view this ticket.'))
            return redirect('support:ticket_list')
        if not _can_view_all(request) and ticket.created_by != request.user:
            messages.error(request, _('You do not have permission to view this ticket.'))
            return redirect('support:ticket_list')

    # ── Mark unread reply as seen ────────────────────────────────────
    if ticket.has_unread_reply and ticket.created_by == request.user:
        ticket.has_unread_reply = False
        ticket.save(update_fields=['has_unread_reply'])

    # Staff see only non-internal messages
    thread_messages = (
        ticket.messages
        .select_related('sender')
        .prefetch_related('attachments')
    )
    if not request.user.is_superuser:
        thread_messages = thread_messages.filter(is_internal_note=False)

    status_history = ticket.status_history.select_related('changed_by').all()

    return render(request, 'support/ticket_detail.html', {
        'title': ticket.ticket_number,
        'subTitle': _('Support Tickets'),
        'ticket': ticket,
        'thread_messages': thread_messages,
        'status_history': status_history,
        'can_reply': ticket.is_open,
        'can_resolve': ticket.status in [
            Ticket.STATUS_AWAITING_STAFF, Ticket.STATUS_IN_PROGRESS,
        ],
    })


@login_required
@require_active_subscription
@admin_profile_required
@require_POST
def ticket_reply(request, ticket_id):
    """Staff posts a reply to their own ticket."""
    center = _get_center(request)
    ticket = get_object_or_404(Ticket, pk=ticket_id)

    if not request.user.is_superuser:
        if center and ticket.center != center:
            messages.error(request, _('Permission denied.'))
            return redirect('support:ticket_list')
        if not _can_view_all(request) and ticket.created_by != request.user:
            messages.error(request, _('Permission denied.'))
            return redirect('support:ticket_list')

    if not ticket.is_open:
        messages.error(request, _('Cannot reply to a closed or resolved ticket.'))
        return redirect('support:ticket_detail', ticket_id=ticket_id)

    body = request.POST.get('body', '').strip()
    if not body:
        messages.error(request, _('Reply cannot be empty.'))
        return redirect('support:ticket_detail', ticket_id=ticket_id)

    msg = TicketMessage.objects.create(
        ticket=ticket,
        sender_type=TicketMessage.SENDER_STAFF,
        sender=request.user,
        body=body,
    )
    _save_attachments(msg, request.FILES.getlist('attachments'))

    # Move ticket to IN_PROGRESS when staff replies
    if ticket.status in [Ticket.STATUS_OPEN, Ticket.STATUS_AWAITING_STAFF]:
        ticket.set_status(Ticket.STATUS_IN_PROGRESS, changed_by=request.user)

    # Notify support on Telegram that staff replied
    try:
        notify_support_staff_reply(ticket, msg)
    except Exception as exc:
        logger.error(f"Reply Telegram notification failed for {ticket.ticket_number}: {exc}")

    messages.success(request, _('Your reply has been sent.'))
    return redirect('support:ticket_detail', ticket_id=ticket_id)


@login_required
@require_active_subscription
@admin_profile_required
@require_POST
def ticket_resolve(request, ticket_id):
    """Staff marks their ticket as resolved."""
    center = _get_center(request)
    ticket = get_object_or_404(Ticket, pk=ticket_id)

    if not request.user.is_superuser:
        if center and ticket.center != center:
            messages.error(request, _('Permission denied.'))
            return redirect('support:ticket_list')
        if not _can_view_all(request) and ticket.created_by != request.user:
            messages.error(request, _('Permission denied.'))
            return redirect('support:ticket_list')

    if ticket.status not in [Ticket.STATUS_AWAITING_STAFF, Ticket.STATUS_IN_PROGRESS]:
        messages.warning(request, _('Ticket is not in a state that can be resolved.'))
        return redirect('support:ticket_detail', ticket_id=ticket_id)

    ticket.set_status(
        Ticket.STATUS_RESOLVED,
        changed_by=request.user,
        reason=_('Resolved by staff'),
    )
    TicketMessage.objects.create(
        ticket=ticket,
        sender_type=TicketMessage.SENDER_SYSTEM,
        body=_('Ticket marked as resolved by %(name)s.') % {
            'name': request.user.get_full_name() or request.user.username,
        },
    )
    try:
        notify_support_status_change(ticket, Ticket.STATUS_RESOLVED, changed_by=request.user)
    except Exception as exc:
        logger.error(f"Telegram notify failed on resolve for {ticket.ticket_number}: {exc}")
    messages.success(request, _('Ticket has been resolved.'))
    return redirect('support:ticket_detail', ticket_id=ticket_id)


# ─────────────────────────────────────────────────────────────────────
# SUPERUSER / SUPPORT SIDE — support inbox
# ─────────────────────────────────────────────────────────────────────

@login_required
@_superuser_required
def support_ticket_list(request):
    """Support inbox: all tickets across all centers (superuser only)."""
    from organizations.models import TranslationCenter

    qs = Ticket.objects.select_related('center', 'category', 'created_by').all()

    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    center_filter = request.GET.get('center', '')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if center_filter:
        qs = qs.filter(center_id=center_filter)
    if type_filter:
        qs = qs.filter(ticket_type=type_filter)
    if search:
        qs = qs.filter(
            Q(ticket_number__icontains=search) |
            Q(subject__icontains=search) |
            Q(created_by__username__icontains=search) |
            Q(created_by__first_name__icontains=search) |
            Q(center__name__icontains=search)
        )

    all_tickets = Ticket.objects.all()
    stats = {
        'total': all_tickets.count(),
        'open': all_tickets.filter(status=Ticket.STATUS_OPEN).count(),
        'in_progress': all_tickets.filter(status=Ticket.STATUS_IN_PROGRESS).count(),
        'awaiting_staff': all_tickets.filter(status=Ticket.STATUS_AWAITING_STAFF).count(),
        'resolved': all_tickets.filter(
            status__in=[Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED]
        ).count(),
        'rejected': all_tickets.filter(status=Ticket.STATUS_REJECTED).count(),
        'critical': all_tickets.filter(
            priority=Ticket.PRIORITY_CRITICAL,
            status__in=[Ticket.STATUS_OPEN, Ticket.STATUS_IN_PROGRESS],
        ).count(),
    }

    centers = TranslationCenter.objects.filter(is_active=True).order_by('name')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'support/support_ticket_list.html', {
        'subTitle': _('All Tickets'),
        'page_obj': page_obj,
        'stats': stats,
        'centers': centers,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'center_filter': center_filter,
        'type_filter': type_filter,
        'search': search,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'type_choices': Ticket.TYPE_CHOICES,
    })


@login_required
@_superuser_required
def support_ticket_detail(request, ticket_id):
    """Support view of a ticket — full thread including internal notes."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('center', 'category', 'created_by'),
        pk=ticket_id,
    )
    thread_messages = (
        ticket.messages
        .select_related('sender')
        .prefetch_related('attachments')
        .all()
    )
    status_history = ticket.status_history.select_related('changed_by').all()

    return render(request, 'support/support_ticket_detail.html', {
        'title': ticket.ticket_number,
        'subTitle': _('Support Inbox'),
        'ticket': ticket,
        'thread_messages': thread_messages,
        'status_history': status_history,
        'status_choices': Ticket.STATUS_CHOICES,
        'priority_choices': Ticket.PRIORITY_CHOICES,
        'type_choices': Ticket.TYPE_CHOICES,
    })


@login_required
@_superuser_required
@require_POST
def support_reply(request, ticket_id):
    """Support posts a reply (or internal note) to a ticket."""
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    body = request.POST.get('body', '').strip()
    is_internal = request.POST.get('is_internal_note') == '1'

    if not body:
        messages.error(request, _('Reply cannot be empty.'))
        return redirect('support:support_detail', ticket_id=ticket_id)

    msg = TicketMessage.objects.create(
        ticket=ticket,
        sender_type=TicketMessage.SENDER_SUPPORT,
        sender=request.user,
        body=body,
        is_internal_note=is_internal,
    )
    _save_attachments(msg, request.FILES.getlist('attachments'))

    if not is_internal:
        # Move ticket to AWAITING_STAFF and mark unread for the creator
        if ticket.status in [Ticket.STATUS_OPEN, Ticket.STATUS_IN_PROGRESS]:
            ticket.set_status(Ticket.STATUS_AWAITING_STAFF, changed_by=request.user)
        ticket.has_unread_reply = True
        ticket.save(update_fields=['has_unread_reply'])
        messages.success(request, _('Reply sent to staff.'))
    else:
        messages.success(request, _('Internal note saved.'))

    return redirect('support:support_detail', ticket_id=ticket_id)


@login_required
@_superuser_required
@require_POST
def support_update_status(request, ticket_id):
    """Change ticket status and/or priority from the support side."""
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    new_status = request.POST.get('status', '').strip()
    new_priority = request.POST.get('priority', '').strip()
    reason = request.POST.get('reason', '').strip()

    valid_statuses = [s[0] for s in Ticket.STATUS_CHOICES]
    valid_priorities = [p[0] for p in Ticket.PRIORITY_CHOICES]

    if new_status and new_status != ticket.status and new_status in valid_statuses:
        # For rejected tickets leave a visible system message for the staff member
        if new_status == Ticket.STATUS_REJECTED:
            rejection_body = (
                (_('Ticket rejected by support. Reason: ') + reason)
                if reason
                else _('Ticket rejected by support.')
            )
            TicketMessage.objects.create(
                ticket=ticket,
                sender_type=TicketMessage.SENDER_SYSTEM,
                body=rejection_body,
            )
            ticket.has_unread_reply = True
            ticket.save(update_fields=['has_unread_reply'])

        ticket.set_status(
            new_status,
            changed_by=request.user,
            reason=reason or _('Status changed by support'),
        )
        try:
            notify_support_status_change(ticket, new_status, changed_by=request.user, reason=reason or None)
        except Exception as exc:
            logger.error(f"Telegram notify failed on status change for {ticket.ticket_number}: {exc}")

    if new_priority and new_priority != ticket.priority and new_priority in valid_priorities:
        ticket.priority = new_priority
        ticket.save(update_fields=['priority', 'updated_at'])

    messages.success(request, _('Ticket updated.'))
    return redirect('support:support_detail', ticket_id=ticket_id)
