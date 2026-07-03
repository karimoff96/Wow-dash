from datetime import date

from django.core.management.base import BaseCommand

from billing.models import Subscription


class Command(BaseCommand):
    help = "Mark active subscriptions as expired when their end_date has passed."

    def handle(self, *args, **options):
        today = date.today()
        expired = Subscription.objects.filter(
            status=Subscription.STATUS_ACTIVE,
            end_date__lt=today,
        )
        count = expired.count()
        if count:
            expired.update(status=Subscription.STATUS_EXPIRED)
            self.stdout.write(self.style.SUCCESS(f"Marked {count} subscription(s) as expired."))
        else:
            self.stdout.write("No subscriptions needed expiring.")
