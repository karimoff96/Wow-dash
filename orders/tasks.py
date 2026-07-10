"""Periodic assignment and SLA escalation automation."""

from datetime import timedelta

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils import timezone


@shared_task(name="workflow.automation", queue="maintenance")
def workflow_automation_task():
    from core.models import AdminNotification
    from orders.models import Order
    from orders.workflow_service import assign_order

    now = timezone.now()
    active = Order.objects.filter(
        branch__center__workflow_automation_enabled=True,
    ).exclude(status__in=["completed", "cancelled"]).select_related(
        "branch__center", "product__category", "language"
    )
    assigned = 0
    for order in active.filter(assigned_to__isnull=True).order_by("workflow_priority", "created_at")[:200]:
        if assign_order(order):
            assigned += 1

    due_soon = active.filter(sla_due_at__gt=now, sla_due_at__lte=now + timedelta(hours=24))
    overdue = active.filter(sla_due_at__lte=now)
    content_type = ContentType.objects.get_for_model(Order)
    notifications = 0

    for label, queryset, notification_type in (
        ("Due soon", due_soon, AdminNotification.TYPE_OTHER),
        ("SLA overdue", overdue, AdminNotification.TYPE_ORDER_OVERDUE),
    ):
        for order in queryset[:500]:
            cache_key = f"workflow:sla-alert:{label}:{order.pk}"
            if not cache.add(cache_key, True, timeout=12 * 3600):
                continue
            AdminNotification.objects.create(
                notification_type=notification_type,
                content_type=content_type,
                object_id=order.pk,
                title=f"{label}: Order #{order.get_order_number()}",
                message=f"{order.get_customer_display_name()} — {order.product.name}",
                branch=order.branch,
                center=order.branch.center if order.branch else None,
            )
            notifications += 1
    return {"assigned": assigned, "notifications": notifications}
