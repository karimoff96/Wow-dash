from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import BotUser
from orders.models import Order, OrderEvent, Quote, QuoteLine
from orders.workflow_service import accept_quote, assign_order, revise_quote, transition_order
from organizations.models import AdminUser, Branch, Role, TranslationCenter
from services.models import Category, Product


class WorkflowServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user("workflow-owner")
        self.center = TranslationCenter.objects.create(name="Workflow Center", owner=self.owner)
        self.branch = Branch.objects.create(center=self.center, name="Main", is_main=True)
        self.category = Category.objects.create(branch=self.branch, name="Translation", charging="dynamic")
        self.product = Product.objects.create(
            name="Passport",
            category=self.category,
            ordinary_first_page_price=Decimal("10000"),
            ordinary_other_page_price=Decimal("5000"),
            agency_first_page_price=Decimal("9000"),
            agency_other_page_price=Decimal("4000"),
        )
        self.customer = BotUser.objects.create(
            center=self.center, branch=self.branch, user_id=100, name="Customer",
            phone="+998900000001", is_active=True,
        )
        self.role = Role.objects.create(
            name="workflow_staff", display_name="Workflow Staff",
            can_view_own_orders=True, can_update_order_status=True,
        )

    def staff(self, username):
        user = get_user_model().objects.create_user(username)
        return AdminUser.objects.create(user=user, role=self.role, center=self.center, branch=self.branch)

    def order(self, assigned_to=None):
        return Order.objects.create(
            branch=self.branch, bot_user=self.customer, product=self.product,
            total_pages=1, total_price=Decimal("10000"), status="pending",
            assigned_to=assigned_to, is_active=True,
        )

    def test_quote_acceptance_is_atomic_and_preserves_snapshot_price(self):
        quote = Quote.objects.create(
            branch=self.branch, bot_user=self.customer, status=Quote.STATUS_APPROVED,
            valid_until=timezone.localdate() + timedelta(days=7),
        )
        QuoteLine.objects.create(
            quote=quote, product=self.product, pages=2,
            total_price=Decimal("25000"), unit_price=Decimal("12500"),
            price_snapshot={"calculation": "v1"},
        )

        orders = accept_quote(quote, self.customer)

        quote.refresh_from_db()
        self.assertEqual(quote.status, Quote.STATUS_CONVERTED)
        self.assertEqual(len(orders), 1)
        orders[0].refresh_from_db()
        self.assertEqual(orders[0].total_price, Decimal("25000"))
        self.assertTrue(orders[0].timeline.filter(event_type=OrderEvent.TYPE_QUOTE).exists())
        with self.assertRaises(ValueError):
            accept_quote(quote, self.customer)

    def test_assignment_selects_lowest_open_workload(self):
        busy = self.staff("busy")
        available = self.staff("available")
        self.order(assigned_to=busy)
        target = self.order()

        assignee = assign_order(target)

        self.assertEqual(assignee, available)
        target.refresh_from_db()
        self.assertIsNotNone(target.sla_due_at)

    def test_invalid_status_transition_is_rejected(self):
        order = self.order()
        with self.assertRaises(ValueError):
            transition_order(order, "completed")

    def test_quote_revision_preserves_reference_and_snapshots(self):
        quote = Quote.objects.create(
            branch=self.branch, bot_user=self.customer, status=Quote.STATUS_APPROVED,
            version=1,
        )
        line = QuoteLine.objects.create(
            quote=quote, product=self.product, pages=1,
            total_price=Decimal("10000"), unit_price=Decimal("10000"),
            price_snapshot={"calculation": "v1"},
        )

        revision = revise_quote(quote)

        self.assertEqual(revision.reference, quote.reference)
        self.assertEqual(revision.version, 2)
        self.assertEqual(revision.supersedes, quote)
        self.assertEqual(revision.lines.get().price_snapshot, line.price_snapshot)
        self.assertEqual(revision.status, Quote.STATUS_DRAFT)
