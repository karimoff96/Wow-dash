"""
One-way Telegram notification service for the support ticketing system.

Responsibilities:
  - notify_support_new_ticket()  : alert support group when a ticket is created
  - notify_support_staff_reply() : alert support group when staff posts a follow-up reply

Support NEVER replies via Telegram — all replies happen on the dashboard.
Telegram is used for awareness only (push notifications to the support team).
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

_PRIORITY_ICONS = {
    'low': '🔵',
    'normal': '🟢',
    'high': '🟡',
    'critical': '🔴',
}

_TYPE_ICONS = {
    'bug': '🐛',
    'financial': '💰',
    'technical': '⚙️',
    'cr': '📋',
    'general': '💬',
}

# Map ticket_type → Telegram forum topic thread_id
# Group: https://t.me/c/3166369763 (Multilang Support)
# Confirmed working topic IDs: 2=Finance, 4=Technical, 6=Others
_TYPE_THREAD_ID = {
    'financial': 2,
    'technical': 4,
    'bug':       4,   # bugs → Technical
    'cr':        6,   # change requests → Others
    'general':   6,   # general inquiries → Others (thread 1 does not exist)
}


def _get_thread_id(ticket):
    """Return the forum topic thread_id for this ticket's type."""
    return _TYPE_THREAD_ID.get(ticket.ticket_type, 6)  # default → Others


def _get_bot():
    """
    Return a TeleBot instance using the dedicated support bot token
    (SUPPORT_BOT_TOKEN in settings, sourced from ADMIN_BOT_TOKEN in .env).
    """
    token = getattr(settings, 'SUPPORT_BOT_TOKEN', None)
    if not token:
        logger.error("SUPPORT_BOT_TOKEN is not configured — cannot send support notifications.")
        return None
    try:
        from bot.webhook_manager import _create_bot_instance
        return _create_bot_instance(token)
    except Exception as exc:
        logger.error(f"Could not create support bot instance: {exc}")
    return None


def _get_group_id(ticket):
    """
    Always route to the central support Telegram group.
    Falls back to category-level override if explicitly set.
    """
    if ticket.category and ticket.category.telegram_group_id:
        return ticket.category.telegram_group_id
    return getattr(settings, 'SUPPORT_TELEGRAM_GROUP_ID', None)


def _dashboard_link(path):
    base = getattr(settings, 'BASE_URL', '').rstrip('/')
    if base:
        return f"{base}{path}"
    return None


def notify_support_new_ticket(ticket):
    """
    Send a formatted new-ticket alert to the configured Telegram group.
    Saves the resulting message_id back on the ticket for thread context.
    """
    bot = _get_bot()
    group_id = _get_group_id(ticket)

    if not bot or not group_id:
        logger.warning(
            f"No bot/group configured — skipping Telegram notification for {ticket.ticket_number}"
        )
        return

    priority_icon = _PRIORITY_ICONS.get(ticket.priority, '⚪')
    type_icon = _TYPE_ICONS.get(ticket.ticket_type, '💬')
    category_name = ticket.category.name_uz if ticket.category else '—'
    center_name = ticket.center.name if ticket.center else '—'
    creator = (
        ticket.created_by.get_full_name() or ticket.created_by.username
        if ticket.created_by else 'Unknown'
    )

    desc_preview = ticket.description[:500]
    if len(ticket.description) > 500:
        desc_preview += '…'

    text = (
        f"🎫 <b>New Ticket — {ticket.ticket_number}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{type_icon} <b>Type:</b> {ticket.get_ticket_type_display()}\n"
        f"{priority_icon} <b>Priority:</b> {ticket.get_priority_display()}\n"
        f"📂 <b>Category:</b> {category_name}\n"
        f"🏢 <b>Center:</b> {center_name}\n"
        f"👤 <b>Staff:</b> {creator}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{ticket.subject}</b>\n\n"
        f"{desc_preview}"
    )

    link = _dashboard_link(f"/support/inbox/{ticket.pk}/")
    if link:
        text += f"\n\n🔗 <a href='{link}'>Open in Dashboard →</a>"

    try:
        thread_id = _get_thread_id(ticket)
        try:
            sent = bot.send_message(
                group_id, text,
                parse_mode='HTML',
                message_thread_id=thread_id,
            )
        except Exception as thread_exc:
            err_str = str(thread_exc).lower()
            if 'message thread not found' in err_str or 'thread' in err_str:
                logger.warning(
                    f"Thread {thread_id} not found for ticket {ticket.ticket_number}; "
                    f"sending to main group without thread. Original error: {thread_exc}"
                )
                sent = bot.send_message(group_id, text, parse_mode='HTML')
                thread_id = None  # Don't store a bad thread_id
            else:
                raise
        ticket.telegram_message_id = str(sent.message_id)
        ticket.telegram_group_id = str(group_id)
        ticket.telegram_thread_id = str(thread_id) if thread_id else ''
        ticket.save(update_fields=['telegram_message_id', 'telegram_group_id', 'telegram_thread_id'])
        logger.info(f"Telegram alert sent for ticket {ticket.ticket_number} → thread {thread_id}")
    except Exception as exc:
        logger.error(f"Telegram send failed for {ticket.ticket_number}: {exc}")


def notify_support_staff_reply(ticket, message):
    """
    Notify the support Telegram group when the staff member replies to a ticket.
    Reply is threaded to the original ticket message when possible.
    """
    bot = _get_bot()
    # Always use the central support group — never trust a potentially stale stored value
    group_id = _get_group_id(ticket)

    if not bot or not group_id:
        return

    sender_name = (
        message.sender.get_full_name() or message.sender.username
        if message.sender else 'Staff'
    )
    body_preview = message.body[:400]
    if len(message.body) > 400:
        body_preview += '…'

    text = (
        f"💬 <b>Staff Reply — {ticket.ticket_number}</b>\n"
        f"👤 <b>From:</b> {sender_name}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{body_preview}"
    )

    link = _dashboard_link(f"/support/inbox/{ticket.pk}/")
    if link:
        text += f"\n\n🔗 <a href='{link}'>View Ticket →</a>"

    try:
        reply_to = int(ticket.telegram_message_id) if ticket.telegram_message_id else None
        stored_thread = ticket.telegram_thread_id
        thread_id = int(stored_thread) if stored_thread and stored_thread.strip().lstrip('-').isdigit() else _get_thread_id(ticket)
        try:
            bot.send_message(
                group_id, text,
                parse_mode='HTML',
                message_thread_id=thread_id,
                reply_to_message_id=reply_to,
            )
        except Exception as thread_exc:
            err_str = str(thread_exc).lower()
            if 'message thread not found' in err_str or 'thread' in err_str:
                logger.warning(
                    f"Thread {thread_id} not found for reply on {ticket.ticket_number}; "
                    f"falling back to main group. Error: {thread_exc}"
                )
                bot.send_message(group_id, text, parse_mode='HTML')
            else:
                raise
    except Exception as exc:
        logger.error(
            f"Reply Telegram notification failed for {ticket.ticket_number}: {exc}"
        )


_STATUS_ICONS = {
    'open':            '🟡',
    'in_progress':     '🔄',
    'awaiting_staff':  '⏳',
    'resolved':        '✅',
    'closed':          '🔒',
    'rejected':        '❌',
}


def notify_support_status_change(ticket, new_status, changed_by=None, reason=None):
    """
    Notify the support Telegram group when a ticket's status is updated
    (resolved, closed, rejected, or any other transition).
    """
    bot = _get_bot()
    group_id = _get_group_id(ticket)

    if not bot or not group_id:
        return

    status_icon = _STATUS_ICONS.get(new_status, '🔁')
    status_label = dict([
        ('open', 'Open'), ('in_progress', 'In Progress'),
        ('awaiting_staff', 'Awaiting Staff'), ('resolved', 'Resolved'),
        ('closed', 'Closed'), ('rejected', 'Rejected'),
    ]).get(new_status, new_status.replace('_', ' ').title())

    actor = (
        changed_by.get_full_name() or changed_by.username
        if changed_by else 'System'
    )
    center_name = ticket.center.name if ticket.center else '—'

    text = (
        f"{status_icon} <b>Ticket {new_status.upper()} — {ticket.ticket_number}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Subject:</b> {ticket.subject}\n"
        f"🏢 <b>Center:</b> {center_name}\n"
        f"👤 <b>By:</b> {actor}\n"
        f"🔖 <b>Status:</b> {status_label}"
    )
    if reason:
        text += f"\n💬 <b>Reason:</b> {reason}"

    link = _dashboard_link(f"/support/inbox/{ticket.pk}/")
    if link:
        text += f"\n\n🔗 <a href='{link}'>View Ticket →</a>"

    try:
        reply_to = int(ticket.telegram_message_id) if ticket.telegram_message_id else None
        stored_thread = ticket.telegram_thread_id
        thread_id = int(stored_thread) if stored_thread and stored_thread.strip().lstrip('-').isdigit() else _get_thread_id(ticket)
        try:
            bot.send_message(
                group_id, text,
                parse_mode='HTML',
                message_thread_id=thread_id,
                reply_to_message_id=reply_to,
            )
        except Exception as thread_exc:
            err_str = str(thread_exc).lower()
            if 'message thread not found' in err_str or 'thread' in err_str:
                logger.warning(
                    f"Thread {thread_id} not found for status change on {ticket.ticket_number}; "
                    f"falling back to main group. Error: {thread_exc}"
                )
                bot.send_message(group_id, text, parse_mode='HTML')
            else:
                raise
        logger.info(f"Status-change notification sent for {ticket.ticket_number} → {new_status}")
    except Exception as exc:
        logger.error(f"Status-change Telegram notification failed for {ticket.ticket_number}: {exc}")
