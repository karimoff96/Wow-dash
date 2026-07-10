from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import BotUser
from orders.models import Order
from organizations.models import AdminUser, Role, TranslationCenter
from services.models import Category, Product


class WorkflowEndpointTenantTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner1 = user_model.objects.create_user("workflow-owner-one")
        self.owner2 = user_model.objects.create_user("workflow-owner-two")
        self.center1 = TranslationCenter.objects.create(name="Tenant One", owner=self.owner1)
        self.center2 = TranslationCenter.objects.create(name="Tenant Two", owner=self.owner2)
        self.branch1 = self.center1.branches.first()
        self.branch2 = self.center2.branches.first()
        category = Category.objects.create(branch=self.branch1, name="Translation")
        product = Product.objects.create(
            category=category, name="Passport",
            ordinary_first_page_price=Decimal("100"), ordinary_other_page_price=Decimal("50"),
            agency_first_page_price=Decimal("80"), agency_other_page_price=Decimal("40"),
        )
        customer = BotUser.objects.create(
            center=self.center1, branch=self.branch1, user_id=123,
            name="Tenant One Customer", phone="+998900000000", is_active=True,
        )
        self.order = Order.objects.create(
            branch=self.branch1, product=product, bot_user=customer,
            total_pages=1, total_price=Decimal("100"), status="pending",
        )
        role = Role.objects.create(
            name="tenant_workflow_viewer",
            can_view_all_orders=True,
            can_manage_orders=False,
        )
        AdminUser.objects.create(
            user=self.owner2, role=role, center=self.center2, branch=self.branch2,
        )

    def test_timeline_endpoint_hides_another_centers_order(self):
        self.client.force_login(self.owner2)
        response = self.client.get(reverse("orders:order_timeline_api", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)
