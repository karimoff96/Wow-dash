"""Lightweight liveness/readiness checks for process supervision."""

import shutil
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health_snapshot():
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": type(exc).__name__}

    try:
        cache_key = "health:readiness"
        cache.set(cache_key, "ok", 10)
        cache_ok = cache.get(cache_key) == "ok"
        cache.delete(cache_key)
        checks["cache"] = {"ok": cache_ok}
    except Exception as exc:
        checks["cache"] = {"ok": False, "error": type(exc).__name__}

    disk_path = Path(settings.MEDIA_ROOT)
    if not disk_path.exists():
        disk_path = Path(settings.BASE_DIR)
    usage = shutil.disk_usage(disk_path)
    disk_percent = round((usage.used / usage.total) * 100, 1) if usage.total else 100.0
    checks["disk"] = {
        "ok": disk_percent < getattr(settings, "DISK_CRITICAL_PERCENT", 90),
        "used_percent": disk_percent,
        "free_bytes": usage.free,
    }

    if getattr(settings, "TESTING", False):
        checks["celery"] = {"ok": True, "queues": {}, "testing": True}
    else:
        try:
            import redis

            broker_url = settings.CELERY_BROKER_URL
            parsed = urlparse(broker_url)
            if parsed.scheme not in {"redis", "rediss"}:
                raise RuntimeError("Queue depth monitoring currently requires a Redis broker")
            client = redis.Redis.from_url(broker_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            queue_names = ("default", "broadcasts", "telegram", "maintenance")
            queues = {name: client.llen(name) for name in queue_names}
            max_backlog = getattr(settings, "CELERY_BACKLOG_ALERT_THRESHOLD", 1000)
            checks["celery"] = {
                "ok": sum(queues.values()) < max_backlog,
                "queues": queues,
                "alert_threshold": max_backlog,
            }
        except Exception as exc:
            checks["celery"] = {"ok": False, "error": type(exc).__name__}

    backup_dir = Path(settings.BASE_DIR) / "backups" / "database"
    backups = sorted(
        backup_dir.glob("backup_*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if backup_dir.exists() else []
    backup_age_hours = None
    if backups:
        modified = timezone.datetime.fromtimestamp(
            backups[0].stat().st_mtime,
            tz=timezone.get_current_timezone(),
        )
        backup_age_hours = round((timezone.now() - modified).total_seconds() / 3600, 1)
    checks["backup"] = {
        "ok": backup_age_hours is not None and backup_age_hours <= getattr(settings, "BACKUP_STALE_HOURS", 30),
        "age_hours": backup_age_hours,
        "latest": backups[0].name if backups else None,
    }

    try:
        from core.models import ArchiveRun
        from organizations.models import TranslationCenter

        configured_centers = TranslationCenter.objects.filter(
            maintenance_archive_enabled=True,
        ).exclude(company_orders_channel_id__isnull=True).exclude(company_orders_channel_id="")
        recent_cutoff = timezone.now() - timedelta(
            hours=getattr(settings, "ARCHIVE_STALE_HOURS", 30)
        )
        failed_runs = ArchiveRun.objects.filter(
            status__in=[ArchiveRun.STATUS_FAILED, ArchiveRun.STATUS_PARTIAL],
            started_at__gte=recent_cutoff,
        ).count()
        recent_centers = ArchiveRun.objects.filter(
            center__in=configured_centers,
            status=ArchiveRun.STATUS_COMPLETED,
            completed_at__gte=recent_cutoff,
        ).values("center_id").distinct().count()
        expected_centers = configured_centers.count()
        checks["archive"] = {
            "ok": failed_runs == 0 and (expected_centers == 0 or recent_centers == expected_centers),
            "recent_success_centers": recent_centers,
            "configured_centers": expected_centers,
            "recent_failed_runs": failed_runs,
        }
    except Exception as exc:
        checks["archive"] = {"ok": False, "error": type(exc).__name__}

    telegram = cache.get("health:telegram-connectivity")
    checks["telegram"] = telegram or {
        "ok": None,
        "error": "Not checked yet",
    }

    critical = not checks["database"]["ok"] or not checks["cache"]["ok"] or not checks["disk"]["ok"]
    operational_ok = all(
        check.get("ok") is not False
        for name, check in checks.items()
        if name not in {"database", "cache", "disk"}
    )
    return {
        "ok": not critical,
        "operational_ok": operational_ok,
        "status": "ready" if not critical and operational_ok else ("degraded" if not critical else "unavailable"),
        "checked_at": timezone.now().isoformat(),
        "checks": checks,
    }


def live(request):
    return JsonResponse({"ok": True, "status": "alive"})


def ready(request):
    snapshot = health_snapshot()
    # Operational staleness is reported as degraded but does not remove a
    # healthy web worker from the load balancer.
    if not getattr(request.user, "is_superuser", False):
        snapshot = {
            "ok": snapshot["ok"],
            "operational_ok": snapshot["operational_ok"],
            "status": snapshot["status"],
            "checked_at": snapshot["checked_at"],
            "checks": {
                name: {"ok": details.get("ok")}
                for name, details in snapshot["checks"].items()
            },
        }
    return JsonResponse(snapshot, status=200 if snapshot["ok"] else 503)
