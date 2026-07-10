import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from billing.models import Subscription, Tariff
from accounts.models import BotUser
from bot.access import active_bot_centers, center_can_archive, center_can_run_bot
from bot.models import TelegramUpdateReceipt
from bot.tasks import process_telegram_update
from bot.management.commands.bot_watcher import Command as BotWatcherCommand
from bot.management.commands.run_bots import BotThread
from bot.webhook_manager import (
    get_bot_for_center,
    remove_webhook_for_center,
    setup_all_webhooks,
    webhook_handler,
)
from organizations.models import TranslationCenter
from orders.models import Order
from services.models import Category, Product


class BotSubscriptionAccessTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="bot-subscription-owner",
            password="test-password",
        )
        self.tariff = Tariff.objects.create(
            title="Bot subscription test",
            slug="bot-subscription-test",
            feature_telegram_bot=True,
        )
        self.factory = RequestFactory()

    def create_center(self, name, *, status=Subscription.STATUS_ACTIVE, end_date=None):
        center = TranslationCenter.objects.create(
            name=name,
            owner=self.owner,
            bot_token=f"token-{name}",
        )
        Subscription.objects.create(
            organization=center,
            tariff=self.tariff,
            start_date=date.today() - timedelta(days=1),
            end_date=end_date or date.today() + timedelta(days=1),
            status=status,
        )
        return center

    def test_active_bot_centers_only_returns_current_active_subscriptions(self):
        active = self.create_center("active")
        expired = self.create_center("expired")
        pending = self.create_center("pending", status=Subscription.STATUS_PENDING)

        # Simulate a subscription whose status-expiry job has not run yet. Date
        # validity must still stop the bot even though the stored status is active.
        Subscription.objects.filter(organization=expired).update(
            status=Subscription.STATUS_ACTIVE,
            end_date=date.today() - timedelta(days=1),
        )

        center_ids = set(active_bot_centers().values_list("id", flat=True))

        self.assertEqual(center_ids, {active.id})
        self.assertNotIn(expired.id, center_ids)
        self.assertNotIn(pending.id, center_ids)

    def test_center_can_run_bot_rejects_ended_subscription_with_active_status(self):
        center = self.create_center("ended")
        Subscription.objects.filter(organization=center).update(
            status=Subscription.STATUS_ACTIVE,
            end_date=date.today() - timedelta(days=1),
        )
        center = TranslationCenter.objects.get(pk=center.pk)

        self.assertFalse(center_can_run_bot(center))

    def test_expired_subscription_still_allows_maintenance_archive(self):
        center = self.create_center(
            "archive-after-expiry",
            status=Subscription.STATUS_EXPIRED,
            end_date=date.today() - timedelta(days=1),
        )
        center.company_orders_channel_id = "-100123456789"
        center.save(update_fields=["company_orders_channel_id"])

        self.assertFalse(center_can_run_bot(center))
        self.assertTrue(center_can_archive(center))

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_expired_center_receives_no_customer_status_notification(self, get_bot):
        center = self.create_center(
            "no-expired-notification",
            status=Subscription.STATUS_EXPIRED,
            end_date=date.today() - timedelta(days=1),
        )
        branch = center.branches.first()
        category = Category.objects.create(branch=branch, name="Translation")
        product = Product.objects.create(
            category=category,
            name="Passport",
            ordinary_first_page_price=Decimal("100"),
            ordinary_other_page_price=Decimal("50"),
            agency_first_page_price=Decimal("80"),
            agency_other_page_price=Decimal("40"),
        )
        customer = BotUser.objects.create(
            center=center, branch=branch, user_id=12345,
            name="Expired Customer", phone="+998900000000", is_active=True,
        )
        order = Order.objects.create(
            branch=branch, bot_user=customer, product=product,
            total_pages=1, total_price=Decimal("100"), status="ready",
        )

        from bot.main import send_order_status_notification
        send_order_status_notification(order, "in_progress", "ready")

        get_bot.assert_not_called()

    @patch("bot.tasks.process_telegram_update.delay")
    def test_duplicate_webhook_update_is_acknowledged_once(self, enqueue):
        center = self.create_center("webhook-idempotency")
        payload = json.dumps({"update_id": 987, "message": {"chat": {"id": 123}}})

        first = webhook_handler(self.factory.post(
            f"/bot/webhook/{center.id}/",
            data=payload,
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=center.webhook_secret,
        ), center.id)
        second = webhook_handler(self.factory.post(
            f"/bot/webhook/{center.id}/",
            data=payload,
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=center.webhook_secret,
        ), center.id)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(json.loads(second.content), {"ok": True, "duplicate": True})
        self.assertEqual(TelegramUpdateReceipt.objects.filter(center=center, update_id=987).count(), 1)
        enqueue.assert_called_once()

    def test_webhook_rejects_invalid_secret(self):
        center = self.create_center("webhook-secret")
        request = self.factory.post(
            f"/bot/webhook/{center.id}/",
            data=json.dumps({"update_id": 456}),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong-secret",
        )

        self.assertEqual(webhook_handler(request, center.id).status_code, 403)

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_webhook_removal_switches_center_back_to_polling(self, get_bot):
        center = self.create_center("webhook-rollback")
        center.bot_delivery_mode = center.BOT_DELIVERY_WEBHOOK
        center.save(update_fields=["bot_delivery_mode"])
        get_bot.return_value = MagicMock()

        result = remove_webhook_for_center(center)

        center.refresh_from_db()
        self.assertTrue(result["success"])
        self.assertEqual(center.bot_delivery_mode, center.BOT_DELIVERY_POLLING)

    @patch("bot.webhook_manager._create_bot_instance")
    def test_get_bot_for_center_does_not_create_bot_for_expired_center(self, create_bot):
        center = self.create_center(
            "expired-instance",
            status=Subscription.STATUS_EXPIRED,
            end_date=date.today() - timedelta(days=1),
        )

        self.assertIsNone(get_bot_for_center(center))
        create_bot.assert_not_called()

    @patch("bot.webhook_manager.setup_webhook_for_center")
    def test_setup_all_webhooks_skips_expired_centers(self, setup_webhook):
        active = self.create_center("webhook-active")
        self.create_center(
            "webhook-expired",
            status=Subscription.STATUS_EXPIRED,
            end_date=date.today() - timedelta(days=1),
        )
        setup_webhook.return_value = {"success": True}

        results = setup_all_webhooks("https://example.com")

        self.assertEqual(set(results), {active.id})
        setup_webhook.assert_called_once()
        self.assertEqual(setup_webhook.call_args.args[0].id, active.id)

    def test_webhook_acknowledges_but_does_not_dispatch_expired_center_update(self):
        center = self.create_center(
            "webhook-ended",
            status=Subscription.STATUS_EXPIRED,
            end_date=date.today() - timedelta(days=1),
        )
        request = self.factory.post(
            f"/bot/webhook/{center.id}/",
            data=json.dumps({"update_id": 123}),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=center.webhook_secret,
        )

        response = webhook_handler(request, center.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"ok": True, "inactive": True})

    def test_polling_thread_stops_when_subscription_is_inactive(self):
        center = self.create_center("polling-stop")
        bot = MagicMock()
        stdout = MagicMock()
        thread = BotThread(center, bot, stdout)

        with patch.object(thread, "_center_can_keep_running", return_value=False):
            stopped = thread.stop_if_subscription_inactive()

        self.assertTrue(stopped)
        self.assertFalse(thread.running)
        bot.stop_polling.assert_called_once_with()

    def test_bot_watcher_hash_changes_when_subscription_expires(self):
        center = self.create_center("watcher")
        watcher = BotWatcherCommand()
        active_hash = watcher.get_token_hash()

        Subscription.objects.filter(organization=center).update(
            status=Subscription.STATUS_EXPIRED,
        )

        self.assertNotEqual(watcher.get_token_hash(), active_hash)


class TelegramTaskAtomicityTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("telegram-atomic-owner")
        tariff = Tariff.objects.create(title="Telegram atomic", slug="telegram-atomic")
        self.center = TranslationCenter.objects.create(
            name="Telegram Atomic Center", owner=owner, bot_token="123:atomic-test",
        )
        Subscription.objects.create(
            organization=self.center,
            tariff=tariff,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
            status=Subscription.STATUS_ACTIVE,
        )
        self.branch = self.center.branches.first()
        category = Category.objects.create(branch=self.branch, name="Translation")
        self.product = Product.objects.create(
            category=category, name="Passport",
            ordinary_first_page_price=Decimal("100"), ordinary_other_page_price=Decimal("50"),
            agency_first_page_price=Decimal("80"), agency_other_page_price=Decimal("40"),
        )
        self.customer = BotUser.objects.create(
            center=self.center, branch=self.branch, user_id=999,
            name="Atomic Customer", phone="+998900000009", is_active=True,
        )
        self.receipt = TelegramUpdateReceipt.objects.create(
            center=self.center,
            update_id=999,
            chat_id=999,
            payload={
                "update_id": 999,
                "message": {
                    "message_id": 1,
                    "date": 1,
                    "chat": {"id": 999, "type": "private"},
                    "from": {"id": 999, "is_bot": False, "first_name": "Atomic"},
                    "text": "/start",
                },
            },
        )

    @patch("bot.tasks.cache.delete")
    @patch("bot.tasks.cache.add", return_value=True)
    @patch("bot.tasks._configured_bot")
    def test_handler_failure_rolls_back_order_before_retry(self, configured, _add, _delete):
        class FailingBot:
            def process_new_updates(inner_self, updates):
                Order.objects.create(
                    branch=self.branch, bot_user=self.customer, product=self.product,
                    total_pages=1, total_price=Decimal("100"), status="pending",
                )
                raise RuntimeError("failure after business mutation")

        configured.return_value = (FailingBot(), SimpleNamespace(bot=object()))

        with self.assertRaises(RuntimeError):
            process_telegram_update.run(self.receipt.pk)

        self.assertFalse(Order.objects.filter(branch=self.branch).exists())
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, TelegramUpdateReceipt.STATUS_FAILED)
