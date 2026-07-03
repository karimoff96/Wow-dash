"""
Management command: auto_resolve_tickets

Automatically resolves tickets that have been in AWAITING_STAFF status
beyond their SLA deadline (auto_resolve_at timestamp).

Also adds SLA breach warnings to tickets that are stuck IN_PROGRESS for too long.

Schedule with cron:
    */30 * * * * /path/to/venv/bin/python /path/to/manage.py auto_resolve_tickets
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.translation import gettext as _
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Auto-resolve tickets whose SLA has expired and add warnings to long-running tickets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be resolved without making changes',
        )
        parser.add_argument(
            '--warn-days',
            type=int,
            default=7,
            help='Add an SLA warning message to IN_PROGRESS tickets older than this many days (default: 7)',
        )

    def handle(self, *args, **options):
        from support.models import Ticket, TicketMessage

        dry_run = options['dry_run']
        warn_days = options['warn_days']
        now = timezone.now()
        resolved_count = 0
        warned_count = 0

        # ── 1. Auto-resolve: AWAITING_STAFF tickets past their deadline ──
        expired = Ticket.objects.filter(
            status=Ticket.STATUS_AWAITING_STAFF,
            auto_resolve_at__lte=now,
        ).select_related('category')

        for ticket in expired:
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would auto-resolve: {ticket.ticket_number} "
                    f"(deadline: {ticket.auto_resolve_at})"
                )
                resolved_count += 1
                continue

            ticket.set_status(
                Ticket.STATUS_RESOLVED,
                changed_by=None,
                reason=_('Auto-resolved: no staff response within the SLA period'),
            )
            TicketMessage.objects.create(
                ticket=ticket,
                sender_type=TicketMessage.SENDER_SYSTEM,
                body=_(
                    'This ticket was automatically resolved because no response was received '
                    'within the expected timeframe. If your issue is still unresolved, '
                    'please open a new ticket.'
                ),
            )
            # Notify the creator that the ticket was auto-resolved
            ticket.has_unread_reply = True
            ticket.save(update_fields=['has_unread_reply'])

            resolved_count += 1
            logger.info(f"Auto-resolved ticket {ticket.ticket_number}")

        # ── 2. SLA warning: IN_PROGRESS tickets stalled for too long ─────
        warn_threshold = now - timezone.timedelta(days=warn_days)

        stalled = Ticket.objects.filter(
            status=Ticket.STATUS_IN_PROGRESS,
            updated_at__lte=warn_threshold,
        ).exclude(
            # Don't warn the same ticket twice within warn_days
            messages__sender_type=TicketMessage.SENDER_SYSTEM,
            messages__body__icontains='taking longer than expected',
            messages__created_at__gte=warn_threshold,
        )

        for ticket in stalled:
            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would add SLA warning: {ticket.ticket_number} "
                    f"(last updated: {ticket.updated_at})"
                )
                warned_count += 1
                continue

            TicketMessage.objects.create(
                ticket=ticket,
                sender_type=TicketMessage.SENDER_SYSTEM,
                body=_(
                    'This ticket is taking longer than expected to resolve. '
                    'Our support team is aware and working on it.'
                ),
            )
            ticket.has_unread_reply = True
            ticket.save(update_fields=['has_unread_reply'])

            warned_count += 1
            logger.info(f"Added SLA warning to ticket {ticket.ticket_number}")

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Done — {resolved_count} ticket(s) auto-resolved, "
                f"{warned_count} SLA warning(s) added."
            )
        )
