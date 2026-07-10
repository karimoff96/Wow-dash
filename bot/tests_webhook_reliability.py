import json
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from celery.exceptions import Retry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from billing.models import Subscription, Tariff
from bot.models import TelegramUpdateReceipt
from bot.tasks import _configured_bot, process_telegram_update
from bot import webhook_manager
from organizations.models import TranslationCenter


class WebhookManagerReliabilityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("webhook-reliability-owner")
        self.tariff = Tariff.objects.create(title="Webhook reliability", slug="webhook-reliability")
        self.center = TranslationCenter.objects.create(
            name="Webhook Reliability Center",
            owner=self.owner,
            bot_token="123:webhook-reliability",
        )
        Subscription.objects.create(
            organization=self.center,
            tariff=self.tariff,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            status=Subscription.STATUS_ACTIVE,
        )
        self.factory = RequestFactory()
        cache.clear()
        webhook_manager._bot_instances.clear()

    def tearDown(self):
        cache.clear()
        webhook_manager._bot_instances.clear()

    def request(self, payload, *, secret=None):
        return self.factory.post(
            "/bot/webhook/",
            data=payload if isinstance(payload, str) else json.dumps(payload),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret or self.center.webhook_secret,
        )

    @patch("bot.webhook_manager.telebot.TeleBot")
    def test_http_helpers_keep_tls_verification_and_build_non_threaded_bot(self, telebot_cls):
        session = webhook_manager.get_ssl_session()
        self.assertTrue(session.verify)
        self.assertIn("https://", session.adapters)

        instance = webhook_manager._create_bot_instance("123:test")

        self.assertIs(instance, telebot_cls.return_value)
        telebot_cls.assert_called_once_with("123:test", parse_mode="HTML", threaded=False)

    @patch("bot.webhook_manager._create_bot_instance")
    def test_bot_cache_reuses_instances_and_invalidation_removes_them(self, create_bot):
        bot = create_bot.return_value

        self.assertIs(webhook_manager.get_bot_for_center(self.center), bot)
        self.assertIs(webhook_manager.get_bot_for_center(self.center), bot)
        create_bot.assert_called_once_with(self.center.bot_token)

        webhook_manager.invalidate_bot_cache(self.center.pk)
        self.assertNotIn((self.center.pk, self.center.bot_token), webhook_manager._bot_instances)
        self.assertIsNone(cache.get(f"bot_token_valid:{self.center.pk}"))

    @patch("bot.webhook_manager._create_bot_instance")
    def test_cached_token_recreates_process_local_instance(self, create_bot):
        cache.set(f"bot_token_valid:{self.center.pk}", self.center.bot_token)

        self.assertIs(webhook_manager.get_bot_for_center(self.center), create_bot.return_value)
        create_bot.assert_called_once_with(self.center.bot_token)

    @patch("bot.webhook_manager._create_bot_instance", side_effect=RuntimeError("invalid token"))
    def test_bot_creation_failure_and_missing_token_return_none(self, _create_bot):
        self.assertIsNone(webhook_manager.get_bot_for_center(self.center))
        self.center.bot_token = ""
        self.assertIsNone(webhook_manager.get_bot_for_center(self.center))

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_setup_webhook_success_records_delivery_mode_and_secret(self, get_bot):
        bot = MagicMock()
        bot.set_webhook.return_value = True
        get_bot.return_value = bot

        result = webhook_manager.setup_webhook_for_center(self.center, "https://example.com/root/")

        self.assertTrue(result["success"])
        expected_url = f"https://example.com/root/bot/webhook/v2/{self.center.webhook_identifier}/"
        self.assertEqual(result["webhook_url"], expected_url)
        bot.set_webhook.assert_called_once_with(
            url=expected_url,
            secret_token=self.center.webhook_secret,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        self.center.refresh_from_db()
        self.assertEqual(self.center.bot_delivery_mode, self.center.BOT_DELIVERY_WEBHOOK)

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_setup_webhook_handles_telegram_false_and_exception(self, get_bot):
        bot = MagicMock()
        get_bot.return_value = bot
        bot.set_webhook.return_value = False
        self.assertEqual(
            webhook_manager.setup_webhook_for_center(self.center, "https://example.com")["error"],
            "Telegram returned False",
        )

        bot.remove_webhook.side_effect = RuntimeError("telegram unavailable")
        result = webhook_manager.setup_webhook_for_center(self.center, "https://example.com")
        self.assertFalse(result["success"])
        self.assertIn("telegram unavailable", result["error"])

    @override_settings(SITE_URL=None)
    @patch("bot.webhook_manager.get_bot_for_center")
    def test_setup_webhook_validates_configuration_and_access(self, get_bot):
        self.center.bot_token = ""
        self.assertIn("No bot token", webhook_manager.setup_webhook_for_center(self.center)["error"])

        self.center.bot_token = "123:webhook-reliability"
        self.center.customer_bot_enabled = False
        self.assertIn("not active", webhook_manager.setup_webhook_for_center(self.center)["error"])

        self.center.customer_bot_enabled = True
        get_bot.return_value = None
        self.assertIn("Failed to create", webhook_manager.setup_webhook_for_center(self.center)["error"])

        get_bot.return_value = MagicMock()
        self.assertIn("No base URL", webhook_manager.setup_webhook_for_center(self.center)["error"])

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_remove_webhook_reports_missing_bot_and_telegram_failure(self, get_bot):
        self.center.bot_token = ""
        self.assertIn("No bot token", webhook_manager.remove_webhook_for_center(self.center)["error"])

        self.center.bot_token = "123:webhook-reliability"
        get_bot.return_value = None
        self.assertIn("Failed to create", webhook_manager.remove_webhook_for_center(self.center)["error"])

        get_bot.return_value = MagicMock()
        get_bot.return_value.remove_webhook.side_effect = RuntimeError("remove failed")
        result = webhook_manager.remove_webhook_for_center(self.center)
        self.assertFalse(result["success"])
        self.assertIn("remove failed", result["error"])

    @patch("bot.webhook_manager.get_bot_for_center")
    def test_get_webhook_info_success_and_failures(self, get_bot):
        self.center.bot_token = ""
        self.assertIn("No bot token", webhook_manager.get_webhook_info(self.center)["error"])

        self.center.bot_token = "123:webhook-reliability"
        get_bot.return_value = None
        self.assertIn("Failed to create", webhook_manager.get_webhook_info(self.center)["error"])

        info = SimpleNamespace(
            url="https://example.com/hook",
            has_custom_certificate=False,
            pending_update_count=2,
            last_error_date=None,
            last_error_message="",
            max_connections=40,
        )
        get_bot.return_value = MagicMock(get_webhook_info=MagicMock(return_value=info))
        self.assertEqual(webhook_manager.get_webhook_info(self.center)["pending_update_count"], 2)

        get_bot.return_value.get_webhook_info.side_effect = RuntimeError("info failed")
        self.assertIn("info failed", webhook_manager.get_webhook_info(self.center)["error"])

    def test_extract_chat_id_supports_messages_callbacks_and_inline_callbacks(self):
        self.assertEqual(webhook_manager._extract_chat_id({"message": {"chat": {"id": 1}}}), 1)
        self.assertEqual(
            webhook_manager._extract_chat_id({"callback_query": {"message": {"chat": {"id": 2}}}}),
            2,
        )
        self.assertEqual(webhook_manager._extract_chat_id({"callback_query": {"from": {"id": 3}}}), 3)
        self.assertIsNone(webhook_manager._extract_chat_id({}))

    def test_webhook_rejects_invalid_json_and_missing_update_id(self):
        invalid_json = webhook_manager.webhook_handler(self.request("{"), self.center.pk)
        missing_id = webhook_manager.webhook_handler(self.request({"message": {}}), self.center.pk)

        self.assertEqual(invalid_json.status_code, 400)
        self.assertEqual(missing_id.status_code, 400)

    @patch("bot.tasks.process_telegram_update.delay")
    def test_failed_receipt_can_be_requeued_with_new_payload(self, delay):
        receipt = TelegramUpdateReceipt.objects.create(
            center=self.center,
            update_id=44,
            status=TelegramUpdateReceipt.STATUS_FAILED,
            payload={"update_id": 44, "old": True},
            last_error="previous failure",
        )
        payload = {"update_id": 44, "callback_query": {"from": {"id": 900}}}

        response = webhook_manager.webhook_handler(self.request(payload), self.center.pk)

        self.assertEqual(response.status_code, 200)
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, TelegramUpdateReceipt.STATUS_QUEUED)
        self.assertEqual(receipt.chat_id, 900)
        self.assertEqual(receipt.payload, payload)
        self.assertEqual(receipt.last_error, "")
        delay.assert_called_once_with(receipt.pk)

    @patch("bot.tasks.process_telegram_update.delay", side_effect=RuntimeError("redis down"))
    def test_queue_failure_is_recorded_and_returns_retryable_response(self, _delay):
        response = webhook_manager.webhook_handler(self.request({"update_id": 45}), self.center.pk)

        self.assertEqual(response.status_code, 503)
        receipt = TelegramUpdateReceipt.objects.get(update_id=45)
        self.assertEqual(receipt.status, TelegramUpdateReceipt.STATUS_FAILED)
        self.assertIn("redis down", receipt.last_error)

    def test_webhook_health_and_lookup_endpoints_do_not_leak_centers(self):
        active = webhook_manager.webhook_handler(self.factory.get("/"), self.center.pk)
        missing_get = webhook_manager.webhook_handler(self.factory.get("/"), 999999)
        missing_post = webhook_manager.webhook_handler(self.request({"update_id": 1}), 999999)
        missing_v2 = webhook_manager.webhook_handler_v2(
            self.request({"update_id": 2}),
            "00000000-0000-0000-0000-000000000000",
        )

        self.assertEqual(active.status_code, 200)
        self.assertEqual(missing_get.status_code, 404)
        self.assertEqual(missing_post.status_code, 404)
        self.assertEqual(missing_v2.status_code, 404)

        self.center.customer_bot_enabled = False
        self.center.save(update_fields=["customer_bot_enabled"])
        inactive = webhook_manager.webhook_handler(self.factory.get("/"), self.center.pk)
        self.assertEqual(inactive.status_code, 403)

    @patch("bot.tasks.process_telegram_update.delay")
    def test_v2_identifier_queues_update(self, delay):
        response = webhook_manager.webhook_handler_v2(
            self.request({"update_id": 88, "message": {"chat": {"id": 9}}}),
            self.center.webhook_identifier,
        )

        self.assertEqual(response.status_code, 200)
        receipt = TelegramUpdateReceipt.objects.get(update_id=88)
        self.assertEqual(receipt.chat_id, 9)
        delay.assert_called_once_with(receipt.pk)


class TelegramTaskReliabilityTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("telegram-task-owner")
        tariff = Tariff.objects.create(title="Telegram task", slug="telegram-task")
        self.center = TranslationCenter.objects.create(
            name="Telegram Task Center", owner=owner, bot_token="123:telegram-task"
        )
        Subscription.objects.create(
            organization=self.center,
            tariff=tariff,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=30),
            status=Subscription.STATUS_ACTIVE,
        )
        self.receipt = TelegramUpdateReceipt.objects.create(
            center=self.center,
            update_id=500,
            chat_id=600,
            payload={"update_id": 500},
        )

    def test_configured_bot_copies_handlers_and_handles_unavailable_bot(self):
        with patch("bot.webhook_manager.get_bot_for_center", return_value=None):
            center_bot, bot_module = _configured_bot(self.center)
        self.assertIsNone(center_bot)
        self.assertIsNotNone(bot_module)

        fake_bot = SimpleNamespace()
        with patch("bot.webhook_manager.get_bot_for_center", return_value=fake_bot):
            center_bot, bot_module = _configured_bot(self.center)
        self.assertIs(center_bot, fake_bot)
        self.assertEqual(fake_bot.message_handlers, bot_module.bot.message_handlers)
        self.assertIsNot(fake_bot.message_handlers, bot_module.bot.message_handlers)

    def test_completed_receipt_returns_without_reprocessing(self):
        self.receipt.status = TelegramUpdateReceipt.STATUS_COMPLETED
        self.receipt.save(update_fields=["status"])

        self.assertEqual(
            process_telegram_update.run(self.receipt.pk),
            {"status": TelegramUpdateReceipt.STATUS_COMPLETED, "duplicate": True},
        )

    def test_inactive_center_is_intentionally_completed(self):
        self.center.customer_bot_enabled = False
        self.center.save(update_fields=["customer_bot_enabled"])

        self.assertEqual(process_telegram_update.run(self.receipt.pk), {"status": "ignored"})
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, TelegramUpdateReceipt.STATUS_COMPLETED)
        self.assertIn("inactive", self.receipt.last_error)

    @patch("bot.tasks.cache.add", return_value=False)
    def test_busy_chat_lock_retries_without_marking_processing(self, _add):
        with patch.object(process_telegram_update, "retry", side_effect=Retry("locked")):
            with self.assertRaises(Retry):
                process_telegram_update.run(self.receipt.pk)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, TelegramUpdateReceipt.STATUS_QUEUED)
        self.assertEqual(self.receipt.attempts, 0)

    @patch("bot.tasks.cache.delete")
    @patch("bot.tasks.cache.add", return_value=True)
    @patch("bot.tasks.telebot.types.Update.de_json")
    @patch("bot.tasks._configured_bot")
    def test_successful_message_update_completes_and_restores_template_bot(
        self, configured, decode_update, _add, delete
    ):
        center_bot = MagicMock()
        previous_bot = object()
        bot_module = SimpleNamespace(bot=previous_bot)
        configured.return_value = (center_bot, bot_module)
        message = SimpleNamespace()
        decode_update.return_value = SimpleNamespace(message=message, callback_query=None)

        result = process_telegram_update.run(self.receipt.pk)

        self.assertEqual(result, {"status": "completed"})
        self.assertEqual(message._center.pk, self.center.pk)
        self.assertIs(message._center_bot, center_bot)
        center_bot.process_new_updates.assert_called_once()
        self.assertIs(bot_module.bot, previous_bot)
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, TelegramUpdateReceipt.STATUS_COMPLETED)
        delete.assert_called_once()

    @patch("bot.tasks.cache.delete")
    @patch("bot.tasks.cache.add", return_value=True)
    @patch("bot.tasks.telebot.types.Update.de_json")
    @patch("bot.tasks._configured_bot")
    def test_callback_update_gets_explicit_center_context(self, configured, decode_update, _add, _delete):
        center_bot = MagicMock()
        configured.return_value = (center_bot, SimpleNamespace(bot=object()))
        callback = SimpleNamespace()
        decode_update.return_value = SimpleNamespace(message=None, callback_query=callback)

        self.assertEqual(process_telegram_update.run(self.receipt.pk), {"status": "completed"})
        self.assertEqual(callback._center.pk, self.center.pk)
        self.assertIs(callback._center_bot, center_bot)

    @patch("bot.tasks.cache.delete")
    @patch("bot.tasks.cache.add", return_value=True)
    @patch("bot.tasks._configured_bot", return_value=(None, SimpleNamespace(bot=None)))
    def test_third_processing_failure_moves_receipt_to_dead_letter(self, _configured, _add, _delete):
        self.receipt.attempts = 2
        self.receipt.save(update_fields=["attempts"])

        result = process_telegram_update.run(self.receipt.pk)

        self.assertEqual(result["status"], "dead")
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, TelegramUpdateReceipt.STATUS_DEAD)
        self.assertEqual(self.receipt.attempts, 3)
        self.assertIn("could not be initialized", self.receipt.last_error)
