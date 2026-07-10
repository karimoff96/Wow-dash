"""Queued, idempotent processing for Telegram webhook updates."""

import json
import logging

import telebot
from celery import shared_task
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def _configured_bot(center):
    from bot.webhook_manager import get_bot_for_center
    import bot.main as bot_module

    center_bot = get_bot_for_center(center)
    if center_bot is None:
        return None, bot_module

    template = bot_module.bot
    center_bot.message_handlers = template.message_handlers.copy()
    center_bot.callback_query_handlers = template.callback_query_handlers.copy()
    center_bot.inline_handlers = template.inline_handlers.copy()
    center_bot.chosen_inline_handlers = template.chosen_inline_handlers.copy()
    center_bot.edited_message_handlers = template.edited_message_handlers.copy()
    return center_bot, bot_module


@shared_task(
    bind=True,
    name="telegram.process_update",
    queue="telegram",
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_telegram_update(self, receipt_id):
    from bot.access import center_can_run_bot
    from bot.models import TelegramUpdateReceipt

    receipt = TelegramUpdateReceipt.objects.select_related("center", "center__subscription").get(pk=receipt_id)
    if receipt.status in {receipt.STATUS_COMPLETED, receipt.STATUS_DEAD}:
        return {"status": receipt.status, "duplicate": True}

    if not center_can_run_bot(receipt.center):
        receipt.status = receipt.STATUS_COMPLETED
        receipt.completed_at = timezone.now()
        receipt.last_error = "Center or subscription inactive; update intentionally ignored"
        receipt.save(update_fields=["status", "completed_at", "last_error", "updated_at"])
        return {"status": "ignored"}

    lock_key = f"telegram:update-lock:{receipt.center_id}:{receipt.chat_id or receipt.update_id}"
    if not cache.add(lock_key, receipt.pk, timeout=120):
        raise self.retry(countdown=2)

    receipt.status = receipt.STATUS_PROCESSING
    receipt.started_at = timezone.now()
    receipt.attempts += 1
    receipt.save(update_fields=["status", "started_at", "attempts", "updated_at"])

    try:
        center_bot, bot_module = _configured_bot(receipt.center)
        if center_bot is None:
            raise RuntimeError("Center bot could not be initialized")

        update_json = json.dumps(receipt.payload)
        update = telebot.types.Update.de_json(update_json)
        if getattr(update, "message", None):
            update.message._center = receipt.center
            update.message._center_bot = center_bot
        if getattr(update, "callback_query", None):
            update.callback_query._center = receipt.center
            update.callback_query._center_bot = center_bot

        previous_bot = bot_module.bot
        bot_module.bot = center_bot
        try:
            # All business mutations caused by one Telegram update commit as a
            # unit. A handler failure rolls them back before Celery retries the
            # durable receipt, preventing duplicate orders/payments.
            with transaction.atomic():
                center_bot.process_new_updates([update])
        finally:
            bot_module.bot = previous_bot

        receipt.mark_completed()
        return {"status": "completed"}
    except Exception as exc:
        receipt.last_error = str(exc)
        if receipt.attempts >= 3:
            receipt.status = receipt.STATUS_DEAD
            receipt.completed_at = timezone.now()
            receipt.save(update_fields=["status", "completed_at", "last_error", "updated_at"])
            logger.exception("Telegram update %s moved to dead letter", receipt.pk)
            return {"status": "dead", "error": str(exc)}

        receipt.status = receipt.STATUS_FAILED
        receipt.save(update_fields=["status", "last_error", "updated_at"])
        raise self.retry(exc=exc, countdown=min(5 * (2 ** (receipt.attempts - 1)), 60))
    finally:
        cache.delete(lock_key)
