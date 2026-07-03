from django.core.management.base import BaseCommand

from bot.monitoring_bot import build_alert_summary, send_monitoring_alert


class Command(BaseCommand):
    help = "Run scheduled monitoring checks and optionally notify owner recipients."

    def add_arguments(self, parser):
        parser.add_argument("--send", action="store_true", help="Send alert summary to OWNER_TELEGRAM_IDS.")
        parser.add_argument("--disk-threshold", type=int, default=90, help="Disk usage percent that triggers an alert.")

    def handle(self, *args, **options):
        summary = build_alert_summary(disk_threshold=options["disk_threshold"])
        self.stdout.write(summary)

        if options["send"] and summary != "Monitoring check passed.":
            if send_monitoring_alert(summary):
                self.stdout.write(self.style.SUCCESS("Monitoring alert sent."))
            else:
                self.stdout.write(self.style.ERROR("Monitoring alert was not sent. Check monitoring bot settings."))
