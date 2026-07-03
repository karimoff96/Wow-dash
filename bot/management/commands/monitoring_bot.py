from django.core.management.base import BaseCommand

from bot.monitoring_bot import (
    MONITORING_BOT_TOKEN,
    OWNER_TELEGRAM_IDS,
    build_health_summary,
    build_orders_summary,
    build_sales_summary,
    build_today_summary,
    send_monitoring_alert,
    start_monitoring_bot_polling,
)


class Command(BaseCommand):
    help = "Run or test the owner monitoring bot."

    def add_arguments(self, parser):
        parser.add_argument("--configure", action="store_true", help="Show monitoring bot configuration.")
        parser.add_argument("--test", action="store_true", help="Send a test monitoring summary.")
        parser.add_argument("--summary", action="store_true", help="Print a read-only summary without polling.")

    def handle(self, *args, **options):
        if options["configure"]:
            self._show_configuration()

        if options["summary"]:
            self.stdout.write(build_today_summary())
            self.stdout.write("")
            self.stdout.write(build_health_summary())
            self.stdout.write("")
            self.stdout.write(build_sales_summary())
            self.stdout.write("")
            self.stdout.write(build_orders_summary())

        if options["test"]:
            sent = send_monitoring_alert(build_today_summary() + "\n\n" + build_health_summary())
            if sent:
                self.stdout.write(self.style.SUCCESS("Monitoring test sent."))
            else:
                self.stdout.write(self.style.ERROR("Monitoring test was not sent. Check token and OWNER_TELEGRAM_IDS."))

        if not options["configure"] and not options["summary"] and not options["test"]:
            self._start()

    def _show_configuration(self):
        self.stdout.write("Monitoring bot configuration")
        self.stdout.write(f"MONITORING_BOT_TOKEN configured: {bool(MONITORING_BOT_TOKEN)}")
        self.stdout.write(f"OWNER_TELEGRAM_IDS count: {len(OWNER_TELEGRAM_IDS)}")
        for chat_id in OWNER_TELEGRAM_IDS:
            self.stdout.write(f"  {chat_id}")

    def _start(self):
        if not MONITORING_BOT_TOKEN:
            self.stdout.write(self.style.ERROR("MONITORING_BOT_TOKEN is not configured."))
            return
        if not OWNER_TELEGRAM_IDS:
            self.stdout.write(self.style.ERROR("OWNER_TELEGRAM_IDS is not configured."))
            return

        self.stdout.write(self.style.SUCCESS("Starting owner monitoring bot."))
        start_monitoring_bot_polling()
