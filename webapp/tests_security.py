import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import BotUser
from billing.models import Subscription, Tariff
from orders.models import Order, OrderMedia
from organizations.models import Branch, TranslationCenter
from services.models import Category, Language, Product


class MiniAppTenantSecurityTests(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.tempdir.name, DEBUG=False)
        self.media_settings.enable()
        self.tariff = Tariff.objects.create(title="Mini App", slug="mini-app-security")
        self.owner = get_user_model().objects.create_user("mini-app-owner")
        self.center1, self.branch1 = self._center("Center One", "111:test-one")
        self.center2, self.branch2 = self._center("Center Two", "222:test-two")
        self.category1, self.product1 = self._catalog(self.branch1, "One")
        self.category2, self.product2 = self._catalog(self.branch2, "Two")
        self.user1 = BotUser.objects.create(
            center=self.center1, branch=self.branch1, user_id=777,
            name="Customer One", phone="+998900000001", is_active=True,
        )
        self.user2 = BotUser.objects.create(
            center=self.center2, branch=self.branch2, user_id=777,
            name="Customer Two", phone="+998900000002", is_active=True,
        )
        self.media = OrderMedia.objects.create(
            file=SimpleUploadedFile("private.pdf", b"private tenant document"),
            pages=1,
        )
        self.order = Order.objects.create(
            branch=self.branch1, bot_user=self.user1, product=self.product1,
            total_pages=1, total_price=Decimal("10000"), status="completed",
        )
        self.order.files.add(self.media)

    def tearDown(self):
        self.media_settings.disable()
        self.tempdir.cleanup()

    def _center(self, name, token):
        center = TranslationCenter.objects.create(name=name, owner=self.owner, bot_token=token)
        center.workflow_automation_enabled = True
        center.save(update_fields=["workflow_automation_enabled"])
        branch = center.branches.first()
        Subscription.objects.create(
            organization=center,
            tariff=self.tariff,
            start_date=timezone.localdate() - timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=30),
            status=Subscription.STATUS_ACTIVE,
        )
        return center, branch

    def _catalog(self, branch, suffix):
        category = Category.objects.create(branch=branch, name=f"Translation {suffix}")
        product = Product.objects.create(
            category=category, name=f"Passport {suffix}",
            ordinary_first_page_price=Decimal("10000"),
            ordinary_other_page_price=Decimal("5000"),
            agency_first_page_price=Decimal("9000"),
            agency_other_page_price=Decimal("4000"),
        )
        return category, product

    def _payload(self, center):
        return {"init_data": "signed", "center_id": center.pk}

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_customer_cannot_download_another_centers_media(self, _auth):
        response = self.client.post(
            reverse("webapp:api_secure_media", args=[self.media.pk]),
            data=json.dumps(self._payload(self.center2)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 410)

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_owner_receives_internal_nginx_redirect_for_media(self, _auth):
        response = self.client.post(
            reverse("webapp:api_secure_media", args=[self.media.pk]),
            data=json.dumps(self._payload(self.center1)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["X-Accel-Redirect"].startswith("/protected-media/"))

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_quote_rejects_language_from_another_tenant(self, _auth):
        language = Language.objects.create(branch=self.branch2, name="Remote", short_name="RMT")
        self.category2.languages.add(language)
        payload = {
            **self._payload(self.center1),
            "product_id": self.product1.pk,
            "language_id": language.pk,
            "pages": 1,
        }
        response = self.client.post(
            reverse("webapp:api_quote_create"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_expired_center_cannot_use_mini_app_api(self, _auth):
        subscription = self.center1.subscription
        subscription.status = Subscription.STATUS_EXPIRED
        subscription.end_date = timezone.localdate() - timedelta(days=1)
        subscription.save(update_fields=["status", "end_date"])
        response = self.client.post(
            reverse("webapp:api_my_orders"),
            data=json.dumps(self._payload(self.center1)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_customer_comment_is_tenant_scoped(self, _auth):
        foreign = self.client.post(
            reverse("webapp:api_add_order_comment", args=[self.order.pk]),
            data=json.dumps({**self._payload(self.center2), "comment": "foreign"}),
            content_type="application/json",
        )
        own = self.client.post(
            reverse("webapp:api_add_order_comment", args=[self.order.pk]),
            data=json.dumps({**self._payload(self.center1), "comment": "Please call me"}),
            content_type="application/json",
        )
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(own.status_code, 200)
        self.assertTrue(self.order.timeline.filter(data__body="Please call me").exists())

    @patch("webapp.views.get_validated_telegram_user", return_value=(777, {}))
    def test_customer_can_update_notification_preferences(self, _auth):
        response = self.client.post(
            reverse("webapp:api_notification_preferences"),
            data=json.dumps({
                **self._payload(self.center1),
                "receive_marketing": False,
                "receive_promotions": False,
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["preferences"]["receive_marketing"])
        self.assertFalse(response.json()["preferences"]["receive_promotions"])
