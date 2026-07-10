"""Subscription-aware access rules for translation-center Telegram bots."""

from datetime import date


def center_can_run_bot(center):
    """Return whether a center's customer-facing Telegram bot may operate."""
    return bool(
        center
        and center.is_active
        and center.customer_bot_enabled
        and center.bot_token
        and center.has_active_subscription()
    )


def center_can_archive(center):
    """Maintenance archival is intentionally independent of subscription access."""
    return bool(
        center
        and center.maintenance_archive_enabled
        and center.bot_token
        and center.company_orders_channel_id
    )


def active_bot_centers(queryset=None):
    """Return centers whose bots are configured and covered by a subscription."""
    from billing.models import Subscription
    from organizations.models import TranslationCenter

    today = date.today()
    queryset = queryset if queryset is not None else TranslationCenter.objects.all()

    return (
        queryset.filter(
            is_active=True,
            customer_bot_enabled=True,
            bot_token__isnull=False,
            subscription__status=Subscription.STATUS_ACTIVE,
            subscription__start_date__lte=today,
            subscription__end_date__gte=today,
        )
        .exclude(bot_token="")
        .select_related("subscription")
    )
