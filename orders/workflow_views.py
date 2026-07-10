"""Tenant-scoped dashboard JSON endpoints for quotes and workflow boards."""

import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.views.decorators.http import require_GET, require_POST

from orders.models import Order, Quote
from orders.workflow_service import assign_order, revise_quote
from organizations.rbac import any_permission_required
from organizations.tenant_scope import center_queryset, get_profile_center


@login_required
@any_permission_required("can_view_all_orders", "can_manage_orders")
@require_GET
def quote_list_api(request):
    center = get_profile_center(request.user)
    if not center and not request.user.is_superuser:
        return JsonResponse({"error": "No center access"}, status=403)
    quotes = center_queryset(
        Quote.objects.select_related("branch", "bot_user").prefetch_related("lines"),
        center,
        allow_global=request.user.is_superuser,
    )
    if request.GET.get("status"):
        quotes = quotes.filter(status=request.GET["status"])
    return JsonResponse({"quotes": [{
        "id": quote.pk,
        "reference": str(quote.reference),
        "version": quote.version,
        "status": quote.status,
        "customer": quote.bot_user.display_name if quote.bot_user else quote.customer_name,
        "branch": quote.branch.name,
        "total": str(quote.total),
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "created_at": quote.created_at.isoformat(),
    } for quote in quotes[:200]]})


@login_required
@any_permission_required("can_edit_orders", "can_manage_orders")
@require_POST
def approve_quote_api(request, quote_id):
    center = get_profile_center(request.user)
    profile = getattr(request.user, "admin_profile", None)
    quote_scope = center_queryset(
        Quote.objects.all(), center, allow_global=request.user.is_superuser
    )
    quote = get_object_or_404(quote_scope, pk=quote_id)
    if not request.user.is_superuser and (not profile or not (
        profile.has_permission("can_manage_orders") or profile.has_permission("can_edit_orders")
    )):
        return JsonResponse({"error": "Permission denied"}, status=403)
    if quote.status not in {Quote.STATUS_DRAFT, Quote.STATUS_SUBMITTED}:
        return JsonResponse({"error": "Quote cannot be approved in its current state"}, status=409)
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}
    valid_days = max(1, min(int(body.get("valid_days", 7)), 30))
    quote.recalculate(save=False)
    quote.status = Quote.STATUS_APPROVED
    quote.approved_by = profile
    quote.approved_at = timezone.now()
    quote.valid_until = timezone.localdate() + timedelta(days=valid_days)
    quote.save(update_fields=[
        "subtotal", "total", "status", "approved_by", "approved_at", "valid_until", "updated_at"
    ])
    return JsonResponse({"ok": True, "quote_id": quote.pk, "total": str(quote.total)})


@login_required
@any_permission_required("can_edit_orders", "can_manage_orders")
@require_POST
def revise_quote_api(request, quote_id):
    center = get_profile_center(request.user)
    quote_scope = center_queryset(
        Quote.objects.all(), center, allow_global=request.user.is_superuser
    )
    quote = get_object_or_404(quote_scope, pk=quote_id)
    revision = revise_quote(quote, actor=getattr(request.user, "admin_profile", None))
    return JsonResponse({
        "ok": True,
        "quote_id": revision.pk,
        "reference": str(revision.reference),
        "version": revision.version,
        "status": revision.status,
    })


@login_required
@any_permission_required("can_view_all_orders", "can_manage_orders")
@require_GET
def kanban_api(request):
    center = get_profile_center(request.user)
    if not center and not request.user.is_superuser:
        return JsonResponse({"error": "No center access"}, status=403)
    orders = center_queryset(
        Order.objects.select_related("branch", "assigned_to__user", "bot_user", "product"),
        center,
        allow_global=request.user.is_superuser,
    )
    columns = {}
    for status, _ in Order.STATUS_CHOICES:
        columns[status] = [{
            "id": order.pk,
            "number": order.get_order_number(),
            "customer": order.get_customer_display_name(),
            "branch": order.branch.name if order.branch else None,
            "product": order.product.name,
            "assignee": order.assigned_to.user.get_full_name() if order.assigned_to else None,
            "deadline": order.deadline.isoformat() if order.deadline else None,
            "sla_due_at": order.sla_due_at.isoformat() if order.sla_due_at else None,
            "overdue": bool(order.sla_due_at and order.sla_due_at < timezone.now()),
        } for order in orders.filter(status=status).order_by("workflow_priority", "created_at")[:100]]
    return JsonResponse({"columns": columns})


@login_required
@any_permission_required("can_assign_orders", "can_manage_orders")
@require_POST
def auto_assign_api(request, order_id):
    center = get_profile_center(request.user)
    order_scope = center_queryset(
        Order.objects.all(), center, allow_global=request.user.is_superuser
    )
    order = get_object_or_404(order_scope, pk=order_id)
    assignee = assign_order(order, actor=getattr(request.user, "admin_profile", None))
    if assignee is None:
        return JsonResponse({"error": "No eligible staff member"}, status=409)
    return JsonResponse({"ok": True, "assignee_id": assignee.pk, "assignee": str(assignee)})


@login_required
@any_permission_required("can_view_all_orders", "can_manage_orders")
@require_GET
def order_timeline_api(request, order_id):
    center = get_profile_center(request.user)
    order_scope = center_queryset(
        Order.objects.all(), center, allow_global=request.user.is_superuser
    )
    order = get_object_or_404(order_scope, pk=order_id)
    return JsonResponse({"events": [{
        "id": event.pk,
        "type": event.event_type,
        "actor": str(event.actor) if event.actor else None,
        "data": event.data,
        "created_at": event.created_at.isoformat(),
    } for event in order.timeline.select_related("actor__user").all()]})


@login_required
@any_permission_required("can_view_reports", "can_view_analytics", "can_manage_reports")
@require_GET
def workflow_metrics_api(request):
    center = get_profile_center(request.user)
    if not center and not request.user.is_superuser:
        return JsonResponse({"error": "No center access"}, status=403)

    quotes = center_queryset(Quote.objects.all(), center, allow_global=request.user.is_superuser)
    orders = center_queryset(Order.objects.all(), center, allow_global=request.user.is_superuser)

    quote_counts = dict(quotes.values_list("status").annotate(count=Count("id")))
    total_quotes = sum(quote_counts.values())
    converted = quote_counts.get(Quote.STATUS_CONVERTED, 0)
    assigned_metrics = orders.filter(assigned_at__isnull=False).aggregate(
        average_assignment_time=Avg(
            ExpressionWrapper(F("assigned_at") - F("created_at"), output_field=DurationField())
        )
    )
    average_assignment = assigned_metrics["average_assignment_time"]
    overdue = orders.exclude(status__in=["completed", "cancelled"]).filter(sla_due_at__lt=timezone.now()).count()
    active_orders = orders.exclude(status__in=["completed", "cancelled"])
    active_count = active_orders.count()
    completion = orders.filter(completed_at__isnull=False).aggregate(
        average=Avg(
            ExpressionWrapper(F("completed_at") - F("created_at"), output_field=DurationField())
        )
    )["average"]
    customer_order_counts = orders.exclude(bot_user__isnull=True).values("bot_user_id").annotate(
        order_count=Count("id")
    )
    customer_count = customer_order_counts.count()
    repeat_customers = customer_order_counts.filter(order_count__gt=1).count()
    workloads = list(
        active_orders.exclude(assigned_to__isnull=True)
        .values("assigned_to_id", "assigned_to__user__username")
        .annotate(open_orders=Count("id"))
        .order_by("assigned_to_id")
    )
    workload_values = [entry["open_orders"] for entry in workloads]

    return JsonResponse({
        "quotes": quote_counts,
        "quote_conversion_percent": round((converted / total_quotes) * 100, 1) if total_quotes else 0,
        "average_assignment_seconds": average_assignment.total_seconds() if average_assignment else None,
        "active_overdue_orders": overdue,
        "overdue_percent": round((overdue / active_count) * 100, 1) if active_count else 0,
        "average_completion_seconds": completion.total_seconds() if completion else None,
        "repeat_customer_percent": round((repeat_customers / customer_count) * 100, 1) if customer_count else 0,
        "workloads": workloads,
        "workload_spread": (max(workload_values) - min(workload_values)) if workload_values else 0,
    })
