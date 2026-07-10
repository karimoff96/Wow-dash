"""Transactional quote, assignment, SLA, and order-transition services."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from organizations.models import AdminUser
from orders.models import AssignmentRule, Order, OrderEvent, Quote


ALLOWED_STATUS_TRANSITIONS = {
    "pending": {"payment_pending", "cancelled"},
    "payment_pending": {"payment_received", "cancelled"},
    "payment_received": {"payment_confirmed", "payment_pending"},
    "payment_confirmed": {"in_progress", "cancelled"},
    "in_progress": {"ready", "cancelled"},
    "ready": {"completed", "in_progress"},
    "completed": set(),
    "cancelled": {"pending"},
}


def get_allowed_status_transitions(status):
    return sorted(ALLOWED_STATUS_TRANSITIONS.get(status, set()))


@transaction.atomic
def revise_quote(quote, actor=None):
    """Clone a quote and its price snapshots into the next immutable version."""
    current = Quote.objects.select_for_update().prefetch_related("lines", "files").get(pk=quote.pk)
    latest_version = (
        Quote.objects.filter(reference=current.reference)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or current.version
    )
    revision = Quote.objects.create(
        reference=current.reference,
        version=latest_version + 1,
        supersedes=current,
        branch=current.branch,
        bot_user=current.bot_user,
        customer_name=current.customer_name,
        customer_phone=current.customer_phone,
        source=current.source,
        status=Quote.STATUS_DRAFT,
        currency=current.currency,
        subtotal=current.subtotal,
        discount=current.discount,
        total=current.total,
        valid_until=current.valid_until,
        notes=current.notes,
        created_by=actor,
    )
    revision.files.set(current.files.all())
    for line in current.lines.all():
        revision.lines.create(
            product=line.product,
            language=line.language,
            pages=line.pages,
            copies=line.copies,
            urgency=line.urgency,
            description=line.description,
            unit_price=line.unit_price,
            total_price=line.total_price,
            price_snapshot=line.price_snapshot,
        )
    return revision


def _matching_rules(order):
    return AssignmentRule.objects.filter(branch=order.branch, is_active=True).filter(
        Q(product__isnull=True) | Q(product=order.product),
        Q(category__isnull=True) | Q(category=order.product.category),
        Q(language__isnull=True) | Q(language=order.language),
    ).select_related("assignee").order_by("priority", "pk")


def _eligible_staff(order):
    candidates = AdminUser.objects.filter(is_active=True).filter(
        Q(branch=order.branch) | Q(branch__isnull=True, center=order.branch.center)
    ).select_related("role", "user")
    return [
        candidate for candidate in candidates
        if candidate.has_permission("can_view_own_orders")
        or candidate.has_permission("can_update_order_status")
        or candidate.has_permission("can_manage_orders")
    ]


@transaction.atomic
def assign_order(order, actor=None, force_assignee=None):
    """Assign using the first matching rule, then the lowest open workload."""
    order = Order.objects.select_for_update().select_related(
        "branch__center", "product__category", "language"
    ).get(pk=order.pk)
    rules = list(_matching_rules(order))
    eligible = _eligible_staff(order)
    eligible_ids = {candidate.pk for candidate in eligible}

    assignee = force_assignee if force_assignee and force_assignee.pk in eligible_ids else None
    matched_rule = None
    if assignee is None:
        for rule in rules:
            if rule.assignee_id and rule.assignee_id in eligible_ids:
                assignee = rule.assignee
                matched_rule = rule
                break

    if assignee is None and eligible_ids:
        assignee = (
            AdminUser.objects.filter(pk__in=eligible_ids)
            .annotate(open_orders=Count(
                "assigned_orders",
                filter=~Q(assigned_orders__status__in=["completed", "cancelled"]),
            ))
            .order_by("open_orders", "pk")
            .first()
        )
        matched_rule = rules[0] if rules else None

    if assignee is None:
        return None

    order.assigned_to = assignee
    order.assigned_by = actor
    order.assigned_at = timezone.now()
    order.sla_due_at = timezone.now() + timedelta(
        hours=matched_rule.turnaround_hours if matched_rule else 48
    )
    order._event_actor = actor
    order.save(update_fields=[
        "assigned_to", "assigned_by", "assigned_at", "sla_due_at", "updated_at"
    ])
    return assignee


@transaction.atomic
def transition_order(order, new_status, actor=None, bot_user=None, extra=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if new_status not in ALLOWED_STATUS_TRANSITIONS.get(order.status, set()):
        raise ValueError(f"Transition from {order.status} to {new_status} is not allowed")
    old_status = order.status
    order.status = new_status
    order._event_actor = actor
    order._event_bot_user = bot_user
    order._event_extra = extra or {}
    order.save(update_fields=["status", "updated_at"])
    return old_status, order


@transaction.atomic
def accept_quote(quote, bot_user):
    """Accept one approved quote version and create price-snapshotted orders."""
    quote = Quote.objects.select_for_update().select_related("branch", "bot_user").get(pk=quote.pk)
    if quote.bot_user_id != bot_user.pk:
        raise PermissionError("Quote does not belong to this customer")
    if quote.status != Quote.STATUS_APPROVED:
        raise ValueError("Only approved quotes can be accepted")
    if quote.valid_until and quote.valid_until < timezone.localdate():
        quote.status = Quote.STATUS_EXPIRED
        quote.save(update_fields=["status", "updated_at"])
        raise ValueError("Quote has expired")

    lines = list(quote.lines.select_related("product", "language").all())
    if not lines:
        raise ValueError("Quote has no line items")

    created_orders = []
    shared_files = list(quote.files.all())
    for line in lines:
        order = Order(
            quote=quote,
            branch=quote.branch,
            bot_user=bot_user,
            product=line.product,
            language=line.language,
            total_pages=line.pages,
            copy_number=line.copies,
            total_price=line.total_price,
            description=line.description or quote.notes,
            status="pending",
            is_active=True,
        )
        order._event_bot_user = bot_user
        order.save()
        Order.objects.filter(pk=order.pk).update(total_price=line.total_price)
        order.total_price = line.total_price
        if shared_files:
            order.files.add(*shared_files)
        OrderEvent.objects.create(
            order=order,
            event_type=OrderEvent.TYPE_QUOTE,
            bot_user=bot_user,
            data={
                "quote_id": quote.pk,
                "quote_reference": str(quote.reference),
                "quote_version": quote.version,
                "quoted_total": str(line.total_price),
                "price_snapshot": line.price_snapshot,
            },
        )
        assign_order(order)
        created_orders.append(order)

    quote.status = Quote.STATUS_CONVERTED
    quote.accepted_at = timezone.now()
    quote.converted_at = timezone.now()
    quote.save(update_fields=["status", "accepted_at", "converted_at", "updated_at"])
    return created_orders
