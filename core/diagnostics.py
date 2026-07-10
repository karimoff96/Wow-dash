"""Center onboarding and operational diagnostics."""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone


@login_required
def onboarding_diagnostics(request):
    profile = getattr(request.user, "admin_profile", None)
    center = getattr(profile, "center", None)
    if not center:
        return JsonResponse({"error": "No center access"}, status=403)

    subscription = getattr(center, "subscription", None)
    last_run = center.archive_runs.order_by("-started_at").first()
    backup_dir = Path(settings.BASE_DIR) / "backups" / "database"
    backups = sorted(backup_dir.glob("backup_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    staff_count = center.get_staff_count()

    checks = {
        "bot_token": bool(center.bot_token),
        "bot_username": bool(center.bot_username),
        "archive_channel": bool(center.company_orders_channel_id),
        "customer_bot_enabled": center.customer_bot_enabled,
        "maintenance_archive_enabled": center.maintenance_archive_enabled,
        "workflow_automation_enabled": center.workflow_automation_enabled,
        "subscription_active": bool(subscription and subscription.is_active()),
        "staff_configured": staff_count > 0,
        "payme_ready": bool(
            center.payme_enabled
            and (center.payme_merchant_id or getattr(settings, "PAYME_MERCHANT_ID", ""))
            and (center.payme_secret_key or getattr(settings, "PAYME_SECRET_KEY", ""))
        ),
        "archive_has_run": bool(last_run),
        "archive_last_success": bool(last_run and last_run.status == "completed"),
        "database_backup_present": bool(backups),
    }
    return JsonResponse({
        "ok": all(value for key, value in checks.items() if key not in {"payme_ready", "archive_has_run"}),
        "center_id": center.pk,
        "checks": checks,
        "last_archive_at": last_run.started_at.isoformat() if last_run else None,
        "last_backup_at": timezone.datetime.fromtimestamp(
            backups[0].stat().st_mtime, tz=timezone.get_current_timezone()
        ).isoformat() if backups else None,
    })
