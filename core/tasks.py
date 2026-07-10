"""Periodic operational tasks routed away from interactive work."""

import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="maintenance.expire_subscriptions", queue="maintenance")
def expire_subscriptions_task():
    call_command("expire_subscriptions")


@shared_task(name="maintenance.cleanup_bot_states", queue="maintenance")
def cleanup_bot_states_task():
    call_command("cleanup_bot_states", hours=24)


@shared_task(name="maintenance.cancel_expired_payme", queue="maintenance")
def cancel_expired_payme_orders_task():
    call_command("cancel_expired_payme_orders")


@shared_task(name="maintenance.notify_overdue_orders", queue="maintenance")
def notify_overdue_orders_task():
    call_command("notify_overdue_orders")


@shared_task(
    bind=True,
    name="maintenance.archive_completed_orders",
    queue="maintenance",
    max_retries=3,
    default_retry_delay=300,
)
def archive_completed_orders_task(self, center_id=None):
    from organizations.models import TranslationCenter
    from core.storage_service import StorageArchiveService

    # Subscription expiry does not stop maintenance archival. The dedicated
    # per-center permission does.
    centers = TranslationCenter.objects.filter(
        is_active=True,
        maintenance_archive_enabled=True,
    )
    if center_id is not None:
        centers = centers.filter(pk=center_id)

    mode = getattr(settings, "ARCHIVE_OPERATION_MODE", "inventory")
    results = {}
    try:
        for center in centers.order_by("pk"):
            results[center.pk] = StorageArchiveService().archive_orders(
                center=center,
                age_days=getattr(settings, "ARCHIVE_RETENTION_DAYS", 30),
                mode=mode,
            )
        return results
    except Exception as exc:
        logger.exception("Scheduled archive processing failed")
        raise self.retry(exc=exc)


@shared_task(name="maintenance.system_health", queue="maintenance")
def system_health_task():
    from bot.admin_bot_service import get_admin_bot, send_security_alert
    from core.health import health_snapshot

    try:
        bot = get_admin_bot()
        if bot is None:
            raise RuntimeError("Admin bot is not configured")
        bot.get_me()
        cache.set(
            "health:telegram-connectivity",
            {"ok": True, "checked_at": timezone.now().isoformat()},
            timeout=900,
        )
    except Exception as exc:
        cache.set(
            "health:telegram-connectivity",
            {"ok": False, "error": type(exc).__name__},
            timeout=900,
        )

    snapshot = health_snapshot()
    disk_percent = snapshot["checks"]["disk"]["used_percent"]
    thresholds = (
        getattr(settings, "DISK_WARNING_PERCENT", 70),
        getattr(settings, "DISK_HIGH_PERCENT", 80),
        getattr(settings, "DISK_CRITICAL_PERCENT", 90),
    )
    crossed = max((threshold for threshold in thresholds if disk_percent >= threshold), default=None)

    if not snapshot["ok"] or not snapshot["operational_ok"] or crossed:
        alert_key = f"health-alert:{snapshot['status']}:{crossed or 'service'}"
        if cache.add(alert_key, True, timeout=3600):
            send_security_alert(
                "⚠️ <b>WowDash health alert</b>\n"
                f"Status: {snapshot['status']}\n"
                f"Disk used: {disk_percent}%\n"
                f"Database: {snapshot['checks']['database']['ok']}\n"
                f"Cache: {snapshot['checks']['cache']['ok']}\n"
                f"Celery: {snapshot['checks']['celery']['ok']}\n"
                f"Archive: {snapshot['checks']['archive']['ok']}\n"
                f"Backup: {snapshot['checks']['backup']['ok']}\n"
                f"Telegram: {snapshot['checks']['telegram'].get('ok')}"
            )
    return snapshot
