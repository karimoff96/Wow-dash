"""
Management command to populate usage tracking data from existing orders.
This command analyzes historical order data and creates/updates UsageTracking records.

Usage:
    python manage.py populate_usage_tracking
    python manage.py populate_usage_tracking --year 2025
    python manage.py populate_usage_tracking --year 2025 --month 12
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Q
from django.db import models
from datetime import date
from billing.models import UsageTracking
from organizations.models import TranslationCenter
from orders.models import Order, Receipt


class Command(BaseCommand):
    help = 'Populate usage tracking data from existing orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Specific year to process (default: all years)',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Specific month to process (requires --year)',
        )
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate existing records (default: skip existing)',
        )

    def handle(self, *args, **options):
        year = options.get('year')
        month = options.get('month')
        recalculate = options.get('recalculate', False)

        if month and not year:
            self.stdout.write(self.style.ERROR('--month requires --year'))
            return

        self.stdout.write(self.style.SUCCESS('Starting usage tracking population...'))

        # Get all organizations
        organizations = TranslationCenter.objects.all()
        total_orgs = organizations.count()
        
        self.stdout.write(f"Processing {total_orgs} organizations...")

        total_created = 0
        total_updated = 0
        total_skipped = 0

        for org_index, organization in enumerate(organizations, 1):
            self.stdout.write(f"\n[{org_index}/{total_orgs}] Processing: {organization.name}")

            # Get all order months for this organization
            orders_query = Order.objects.filter(branch__center=organization)
            
            if year:
                orders_query = orders_query.filter(created_at__year=year)
            if month:
                orders_query = orders_query.filter(created_at__month=month)

            # Group orders by year/month
            order_months = orders_query.values(
                'created_at__year', 
                'created_at__month'
            ).distinct().order_by('created_at__year', 'created_at__month')

            for period in order_months:
                period_year = period['created_at__year']
                period_month = period['created_at__month']

                # Check if tracking already exists
                tracking, created = UsageTracking.objects.get_or_create(
                    organization=organization,
                    year=period_year,
                    month=period_month,
                    defaults={
                        'branches_count': organization.branches.count(),
                        'staff_count': organization.get_staff_count(),
                    }
                )

                if not created and not recalculate:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⊙ {period_year}-{period_month:02d}: Already exists (use --recalculate to update)"
                        )
                    )
                    total_skipped += 1
                    continue

                # Get orders for this period
                period_orders = Order.objects.filter(
                    branch__center=organization,
                    created_at__year=period_year,
                    created_at__month=period_month
                )

                # Count total orders
                total_orders = period_orders.count()
                
                # Count bot orders (have bot_user with user_id/Telegram ID)
                bot_orders = period_orders.filter(
                    bot_user__isnull=False,
                    bot_user__user_id__isnull=False
                ).count()
                
                # Count manual orders (no bot_user OR bot_user without user_id)
                manual_orders = period_orders.filter(
                    models.Q(bot_user__isnull=True) | 
                    models.Q(bot_user__user_id__isnull=True)
                ).count()

                # Calculate total revenue from paid orders (payment_confirmed, completed, ready)
                # Note: Using order status since receipts are rarely verified in this system
                total_revenue = period_orders.filter(
                    status__in=['payment_confirmed', 'completed', 'ready']
                ).aggregate(
                    total=Sum('total_price')
                )['total'] or 0

                # Update tracking record
                tracking.orders_created = total_orders
                tracking.bot_orders = bot_orders
                tracking.manual_orders = manual_orders
                tracking.total_revenue = total_revenue
                tracking.branches_count = organization.branches.count()
                tracking.staff_count = organization.get_staff_count()
                tracking.save()

                action = "Created" if created else "Updated"
                total_created += 1 if created else 0
                total_updated += 0 if created else 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {period_year}-{period_month:02d}: {action} "
                        f"(Orders: {total_orders}, Bot: {bot_orders}, Manual: {manual_orders}, "
                        f"Revenue: {total_revenue:,.0f})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"Completed!\n"
                f"  Created: {total_created}\n"
                f"  Updated: {total_updated}\n"
                f"  Skipped: {total_skipped}\n"
                f"{'='*60}"
            )
        )
