from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import BotUser
from orders.models import Order
from organizations.models import AdminUser, Branch, TranslationCenter
from organizations.tenant_scope import center_queryset, customer_queryset, get_profile_center
from services.models import Category, Product


class TenantScopeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner_one = user_model.objects.create_user("tenant-scope-owner-one")
        self.owner_two = user_model.objects.create_user("tenant-scope-owner-two")
        self.center_one = TranslationCenter.objects.create(name="Scope One", owner=self.owner_one)
        self.center_two = TranslationCenter.objects.create(name="Scope Two", owner=self.owner_two)
        self.branch_one = self.center_one.branches.first()
        self.branch_two = self.center_two.branches.first()
        category_one = Category.objects.create(branch=self.branch_one, name="One")
        category_two = Category.objects.create(branch=self.branch_two, name="Two")
        self.product_one = self._product(category_one, "One")
        self.product_two = self._product(category_two, "Two")
        self.customer_one = BotUser.objects.create(
            center=self.center_one,
            branch=self.branch_one,
            user_id=101,
            name="Customer One",
            phone="+998900000101",
        )
        self.customer_two = BotUser.objects.create(
            center=self.center_two,
            branch=self.branch_two,
            user_id=202,
            name="Customer Two",
            phone="+998900000202",
        )
        self.order_one = self._order(self.branch_one, self.product_one, self.customer_one)
        self.order_two = self._order(self.branch_two, self.product_two, self.customer_two)

    def _product(self, category, name):
        return Product.objects.create(
            category=category,
            name=name,
            ordinary_first_page_price=Decimal("100"),
            ordinary_other_page_price=Decimal("50"),
            agency_first_page_price=Decimal("80"),
            agency_other_page_price=Decimal("40"),
        )

    def _order(self, branch, product, customer):
        return Order.objects.create(
            branch=branch,
            product=product,
            bot_user=customer,
            total_pages=1,
            total_price=Decimal("100"),
        )

    def test_center_scope_is_fail_closed_and_never_returns_foreign_rows(self):
        scoped = center_queryset(Order.objects.all(), self.center_one)
        self.assertEqual(list(scoped), [self.order_one])
        self.assertFalse(center_queryset(Order.objects.all(), None).exists())
        self.assertEqual(center_queryset(Order.objects.all(), None, allow_global=True).count(), 2)

    def test_center_scope_supports_explicit_relation_paths(self):
        scoped = center_queryset(Branch.objects.all(), self.center_two, lookup="center")
        self.assertEqual(list(scoped), [self.branch_two])

    def test_customer_scope_requires_matching_center_and_customer(self):
        own = customer_queryset(Order.objects.all(), self.center_one, self.customer_one)
        foreign_customer = customer_queryset(Order.objects.all(), self.center_one, self.customer_two)
        missing_customer = customer_queryset(Order.objects.all(), self.center_one, None)

        self.assertEqual(list(own), [self.order_one])
        self.assertFalse(foreign_customer.exists())
        self.assertFalse(missing_customer.exists())

    def test_profile_center_handles_profiles_and_unscoped_users(self):
        profile = AdminUser.objects.create(user=self.owner_one, center=self.center_one)
        self.assertEqual(get_profile_center(self.owner_one), profile.center)
        anonymous_user = get_user_model().objects.create_user("tenant-scope-no-profile")
        self.assertIsNone(get_profile_center(anonymous_user))
