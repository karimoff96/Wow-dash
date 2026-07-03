"""Owner monitoring bot.

This bot is separate from customer bots and the central SaaS/admin bot. It
exposes read-only operational summaries and never prints stored credentials.
"""

from collections import Counter, deque
from decimal import Decimal
import logging
import os

import psutil
import telebot
from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from telebot.apihelper import ApiTelegramException

logger = logging.getLogger(__name__)


MONITORING_BOT_TOKEN = getattr(settings, "MONITORING_BOT_TOKEN", "") or os.getenv("MONITORING_BOT_TOKEN", "")
OWNER_TELEGRAM_IDS_RAW = getattr(settings, "OWNER_TELEGRAM_IDS", "") or os.getenv("OWNER_TELEGRAM_IDS", "")


def parse_owner_ids(raw=None):
    raw = OWNER_TELEGRAM_IDS_RAW if raw is None else raw
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        values = raw
    else:
        values = str(raw).split(",")
    owner_ids = []
    for value in values:
        value = str(value).strip()
        if not value:
            continue
        try:
            owner_ids.append(int(value))
        except ValueError:
            logger.warning("Invalid OWNER_TELEGRAM_IDS entry: %s", value)
    return owner_ids


OWNER_TELEGRAM_IDS = parse_owner_ids()
_monitoring_bot = None


def get_monitoring_bot():
    global _monitoring_bot
    if _monitoring_bot is None:
        if not MONITORING_BOT_TOKEN:
            return None
        _monitoring_bot = telebot.TeleBot(MONITORING_BOT_TOKEN, parse_mode="HTML", threaded=False)
    return _monitoring_bot


def _is_allowed(message):
    owner_ids = parse_owner_ids()
    if not owner_ids:
        return False
    return int(message.chat.id) in owner_ids


def _first_center():
    from organizations.models import TranslationCenter

    return TranslationCenter.objects.filter(is_active=True).order_by("id").first()


def _today_orders():
    from orders.models import Order

    now = timezone.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    qs = Order.objects.select_related("branch", "branch__center").filter(created_at__gte=start)
    center = _first_center()
    if center:
        qs = qs.filter(branch__center=center)
    return qs


def _all_orders():
    from orders.models import Order

    qs = Order.objects.select_related("branch", "branch__center").all()
    center = _first_center()
    if center:
        qs = qs.filter(branch__center=center)
    return qs


def _money(value):
    value = value or Decimal("0")
    return f"{Decimal(value):,.0f} UZS"


def build_today_summary():
    orders = _today_orders()
    total_sales = orders.aggregate(total=Sum("total_price"))["total"] or Decimal("0")
    received = orders.aggregate(total=Sum("received"))["total"] or Decimal("0")
    status_counts = Counter(dict(orders.values_list("status").annotate(count=Count("id"))))

    lines = [
        "<b>Today</b>",
        f"Orders: {orders.count()}",
        f"Sales: {_money(total_sales)}",
        f"Received: {_money(received)}",
        "",
        "<b>By status</b>",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"{status}: {count}")
    return "\n".join(lines)


def build_sales_summary():
    orders = _all_orders()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today_start.replace(day=1)

    today_sales = orders.filter(created_at__gte=today_start).aggregate(total=Sum("total_price"))["total"] or 0
    month_sales = orders.filter(created_at__gte=month_start).aggregate(total=Sum("total_price"))["total"] or 0
    unpaid = orders.exclude(status__in=["completed", "cancelled"]).aggregate(total=Sum("total_price"))["total"] or 0

    return "\n".join([
        "<b>Sales</b>",
        f"Today: {_money(today_sales)}",
        f"This month: {_money(month_sales)}",
        f"Open order value: {_money(unpaid)}",
    ])


def build_orders_summary():
    orders = _all_orders()
    status_counts = dict(orders.values_list("status").annotate(count=Count("id")))
    overdue = orders.filter(deadline__lt=timezone.localdate()).exclude(
        status__in=["completed", "cancelled"]
    ).count()
    branch_rows = (
        orders.values("branch__name")
        .annotate(count=Count("id"), sales=Sum("total_price"))
        .order_by("-count")[:8]
    )

    lines = ["<b>Orders</b>"]
    for status, count in sorted(status_counts.items()):
        lines.append(f"{status}: {count}")
    lines.append(f"Overdue: {overdue}")
    lines.append("")
    lines.append("<b>Branches</b>")
    for row in branch_rows:
        name = row["branch__name"] or "Unassigned"
        lines.append(f"{name}: {row['count']} orders, {_money(row['sales'])}")
    return "\n".join(lines)


def build_health_summary():
    center = _first_center()
    disk = psutil.disk_usage(str(settings.BASE_DIR))

    if center:
        bot_status = "configured" if center.bot_token else "missing"
        webhook_status = "setup-managed" if center.bot_token and center.subdomain else "needs setup"
        payme_status = "enabled" if center.payme_enabled else "disabled"
        center_name = center.name
    else:
        bot_status = "missing"
        webhook_status = "needs setup"
        payme_status = "disabled"
        center_name = "No active center"

    return "\n".join([
        "<b>Health</b>",
        f"Center: {center_name}",
        f"Customer bot: {bot_status}",
        f"Webhook: {webhook_status}",
        f"Payme: {payme_status}",
        f"Disk used: {disk.percent:.1f}%",
    ])


def build_recent_errors(limit=10):
    log_file = getattr(settings, "BASE_DIR", None)
    if not log_file:
        return "No log directory configured."

    path = os.path.join(str(settings.BASE_DIR), "logs", "error.log")
    if not os.path.exists(path):
        return "No error.log file found."

    errors = deque(maxlen=limit)
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if " ERROR " in line or line.startswith("ERROR"):
                errors.append(line.strip()[:300])

    if not errors:
        return "No recent ERROR lines found."

    return "<b>Recent errors</b>\n" + "\n".join(errors)


def send_monitoring_alert(message):
    bot = get_monitoring_bot()
    owner_ids = parse_owner_ids()
    if not bot or not owner_ids:
        logger.warning("Monitoring bot token or OWNER_TELEGRAM_IDS is not configured.")
        return False

    sent_any = False
    for chat_id in owner_ids:
        try:
            bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
            sent_any = True
        except ApiTelegramException as exc:
            logger.error("Failed to send monitoring alert to %s: %s", chat_id, exc)
    return sent_any


def build_alert_summary(disk_threshold=90):
    alerts = []
    disk = psutil.disk_usage(str(settings.BASE_DIR))
    if disk.percent >= disk_threshold:
        alerts.append(f"Disk usage is high: {disk.percent:.1f}%")

    center = _first_center()
    if center:
        if not center.bot_token:
            alerts.append("Customer bot token is missing.")
        if center.payme_enabled:
            active_secret = center.payme_secret_key if center.payme_sandbox else center.payme_secret_key_prod
            if not center.payme_merchant_id or not active_secret:
                alerts.append("Payme is enabled but active credentials are incomplete.")

    recent_errors = build_recent_errors(limit=3)
    if recent_errors.startswith("<b>Recent errors</b>"):
        alerts.append(recent_errors)

    if not alerts:
        return "Monitoring check passed."
    return "<b>Monitoring alerts</b>\n" + "\n".join(alerts)


def start_monitoring_bot_polling():
    bot = get_monitoring_bot()
    if not bot:
        raise RuntimeError("MONITORING_BOT_TOKEN is not configured.")

    def guarded_reply(message, text):
        if not _is_allowed(message):
            bot.reply_to(message, "This monitoring bot is restricted.")
            return
        bot.reply_to(message, text, parse_mode="HTML")

    @bot.message_handler(commands=["start", "dashboard"])
    def dashboard(message):
        guarded_reply(message, build_today_summary() + "\n\n" + build_health_summary())

    @bot.message_handler(commands=["health"])
    def health(message):
        guarded_reply(message, build_health_summary())

    @bot.message_handler(commands=["today"])
    def today(message):
        guarded_reply(message, build_today_summary())

    @bot.message_handler(commands=["sales"])
    def sales(message):
        guarded_reply(message, build_sales_summary())

    @bot.message_handler(commands=["orders"])
    def orders(message):
        guarded_reply(message, build_orders_summary())

    @bot.message_handler(commands=["errors"])
    def errors(message):
        guarded_reply(message, build_recent_errors())

    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
