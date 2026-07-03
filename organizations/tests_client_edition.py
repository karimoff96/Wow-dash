import json

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from core.models import AuditLog
from organizations.admin import TranslationCenterAdmin
from organizations.models import AdminUser, Branch, Role, TranslationCenter
from organizations.rbac import get_assignable_roles


class DashboardCredentialLockTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username="owner",
            password="pass12345",
            is_staff=True,
        )
        self.role = Role.objects.create(
            name="owner",
            display_name="Owner",
            can_edit_centers=True,
            can_view_centers=True,
            can_edit_branches=True,
            can_manage_branches=True,
        )
        self.center = TranslationCenter.objects.create(
            name="Center",
            owner=self.owner,
            bot_token="old-token",
            bot_username="oldbot",
            company_orders_channel_id="-1001111111111",
            payme_enabled=True,
            payme_sandbox=True,
            payme_merchant_id="merchant-old",
            payme_secret_key="sandbox-old",
            payme_secret_key_prod="prod-old",
        )
        self.branch = Branch.objects.create(
            center=self.center,
            name="Main",
            b2c_orders_channel_id="-1002222222222",
            b2b_orders_channel_id="-1003333333333",
        )
        AdminUser.objects.create(
            user=self.owner,
            role=self.role,
            center=self.center,
            branch=self.branch,
        )

    def test_owner_crafted_center_post_cannot_update_setup_fields(self):
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("center_edit", args=[self.center.pk]),
            {
                "phone": "+998901234567",
                "email": "owner@example.com",
                "address": "New address",
                "location_url": "https://maps.example.test",
                "bot_token": "new-token",
                "bot_username": "newbot",
                "company_orders_channel_id": "-1009999999999",
                "payme_enabled": "",
                "payme_sandbox": "",
                "payme_merchant_id": "merchant-new",
                "payme_secret_key": "sandbox-new",
                "payme_secret_key_prod": "prod-new",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.center.refresh_from_db()
        self.assertEqual(self.center.phone, "+998901234567")
        self.assertEqual(self.center.email, "owner@example.com")
        self.assertEqual(self.center.bot_token, "old-token")
        self.assertEqual(self.center.bot_username, "oldbot")
        self.assertEqual(self.center.company_orders_channel_id, "-1001111111111")
        self.assertTrue(self.center.payme_enabled)
        self.assertTrue(self.center.payme_sandbox)
        self.assertEqual(self.center.payme_merchant_id, "merchant-old")
        self.assertEqual(self.center.payme_secret_key, "sandbox-old")
        self.assertEqual(self.center.payme_secret_key_prod, "prod-old")

    def test_owner_crafted_branch_post_cannot_update_channel_ids(self):
        self.client.login(username="owner", password="pass12345")
        response = self.client.post(
            reverse("branch_edit", args=[self.branch.pk]),
            {
                "name": "Main Updated",
                "phone": "+998901111111",
                "address": "Branch address",
                "location_url": "",
                "is_active": "on",
                "show_pricelist": "on",
                "b2c_orders_channel_id": "-1009999999999",
                "b2b_orders_channel_id": "-1008888888888",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.branch.refresh_from_db()
        self.assertEqual(self.branch.name, "Main Updated")
        self.assertEqual(self.branch.b2c_orders_channel_id, "-1002222222222")
        self.assertEqual(self.branch.b2b_orders_channel_id, "-1003333333333")

    def test_superuser_dashboard_post_cannot_update_center_setup_fields(self):
        setup = User.objects.create_superuser(
            username="setup",
            email="setup@example.com",
            password="pass12345",
        )
        self.client.login(username="setup", password="pass12345")
        response = self.client.post(
            reverse("center_edit", args=[self.center.pk]),
            {
                "name": "Center Updated",
                "subdomain": "center-updated",
                "phone": "+998909999999",
                "email": "setup@example.com",
                "address": "Setup address",
                "location_url": "",
                "is_active": "on",
                "bot_token": "new-token",
                "payme_secret_key": "sandbox-new",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.center.refresh_from_db()
        self.assertEqual(self.center.name, "Center Updated")
        self.assertEqual(self.center.bot_token, "old-token")
        self.assertEqual(self.center.payme_secret_key, "sandbox-old")


class PermissionGrantingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner_user = User.objects.create_user(
            username="owner-grants",
            password="pass12345",
            is_staff=True,
        )
        self.owner_role = Role.objects.create(
            name=Role.OWNER,
            display_name="Owner",
            is_system_role=True,
            can_manage_staff=True,
            can_view_staff=True,
            can_create_staff=True,
            can_edit_staff=True,
        )
        self.manager_role = Role.objects.create(
            name=Role.MANAGER,
            display_name="Manager",
            is_system_role=True,
            can_view_staff=True,
        )
        self.staff_role = Role.objects.create(
            name=Role.STAFF,
            display_name="Staff",
            is_system_role=True,
            can_view_own_orders=True,
        )
        self.center = TranslationCenter.objects.create(
            name="Client Center",
            owner=self.owner_user,
        )
        self.branch = Branch.objects.create(center=self.center, name="Main")
        AdminUser.objects.create(
            user=self.owner_user,
            role=self.owner_role,
            center=self.center,
            branch=self.branch,
        )

    def test_owner_can_grant_operational_roles_but_not_owner_role(self):
        roles = get_assignable_roles(self.owner_user)

        self.assertIn(self.manager_role, roles)
        self.assertIn(self.staff_role, roles)
        self.assertNotIn(self.owner_role, roles)

        valid, error = AdminUser.validate_role_assignment(
            self.owner_user,
            self.manager_role,
            center=self.center,
        )
        self.assertTrue(valid)
        self.assertIsNone(error)

        valid, error = AdminUser.validate_role_assignment(
            self.owner_user,
            self.owner_role,
            center=self.center,
        )
        self.assertFalse(valid)
        self.assertIn("Owner", str(error))

    def test_owner_can_open_role_management_without_superuser(self):
        self.client.login(username="owner-grants", password="pass12345")

        response = self.client.get(reverse("role_list"))

        self.assertEqual(response.status_code, 200)
        role_names = [role.name for role in response.context["roles"]]
        self.assertIn(Role.MANAGER, role_names)
        self.assertNotIn(Role.OWNER, role_names)


class RolePermissionCatalogTests(TestCase):
    def test_display_permissions_match_role_payload_permissions(self):
        display_permissions = set(Role.get_display_permissions())
        category_permissions = {
            permission
            for category in Role.get_display_permission_categories().values()
            for permission in category["permissions"]
        }

        self.assertFalse(category_permissions - display_permissions)

    def test_owner_defaults_effectively_grant_all_display_permissions(self):
        owner = Role(
            name=Role.OWNER,
            **Role.get_default_permissions_for_role(Role.OWNER),
        )
        missing_permissions = [
            permission
            for category in Role.get_display_permission_categories().values()
            for permission in category["permissions"]
            if not owner.has_effective_permission(permission)
        ]

        self.assertEqual(missing_permissions, [])


class AdminCredentialAuditTests(TestCase):
    def test_admin_setup_changes_are_masked_in_audit_log(self):
        setup = User.objects.create_superuser(
            username="setup",
            email="setup@example.com",
            password="pass12345",
        )
        center = TranslationCenter.objects.create(
            name="Center",
            owner=setup,
            bot_token="raw-old-token",
            payme_secret_key="raw-old-sandbox",
        )
        request = RequestFactory().post("/admin/organizations/translationcenter/")
        request.user = setup
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        center.bot_token = "raw-new-token"
        center.payme_secret_key = "raw-new-sandbox"
        model_admin = TranslationCenterAdmin(TranslationCenter, admin.site)
        model_admin.save_model(request, center, form=None, change=True)

        audit = AuditLog.objects.latest("created_at")
        serialized = json.dumps(audit.changes)
        self.assertIn("bot_token", audit.changes)
        self.assertIn("payme_secret_key", audit.changes)
        self.assertNotIn("raw-old-token", serialized)
        self.assertNotIn("raw-new-token", serialized)
        self.assertNotIn("raw-old-sandbox", serialized)
        self.assertNotIn("raw-new-sandbox", serialized)
