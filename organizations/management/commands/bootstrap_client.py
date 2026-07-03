import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from organizations.models import AdminUser, Branch, Role, TranslationCenter


def _env(name, default=""):
    return os.getenv(name, default)


class Command(BaseCommand):
    help = "Bootstrap a one-center client deployment with separated setup and owner accounts."

    def add_arguments(self, parser):
        parser.add_argument("--setup-username", default=_env("SETUP_SUPERUSER_USERNAME", "setup-admin"))
        parser.add_argument("--setup-email", default=_env("SETUP_SUPERUSER_EMAIL", "setup@example.com"))
        parser.add_argument("--setup-password", default=_env("SETUP_SUPERUSER_PASSWORD", ""))
        parser.add_argument("--owner-username", default=_env("BUSINESS_OWNER_USERNAME", "owner"))
        parser.add_argument("--owner-email", default=_env("BUSINESS_OWNER_EMAIL", "owner@example.com"))
        parser.add_argument("--owner-password", default=_env("BUSINESS_OWNER_PASSWORD", ""))
        parser.add_argument("--owner-first-name", default=_env("BUSINESS_OWNER_FIRST_NAME", "Business"))
        parser.add_argument("--owner-last-name", default=_env("BUSINESS_OWNER_LAST_NAME", "Owner"))
        parser.add_argument("--center-name", default=_env("CLIENT_CENTER_NAME", "Client Center"))
        parser.add_argument("--center-subdomain", default=_env("CLIENT_CENTER_SUBDOMAIN", ""))
        parser.add_argument("--branch-name", default=_env("CLIENT_MAIN_BRANCH_NAME", "Main Branch"))
        parser.add_argument("--bot-token", default=_env("CLIENT_BOT_TOKEN", ""))
        parser.add_argument("--bot-username", default=_env("CLIENT_BOT_USERNAME", ""))
        parser.add_argument("--company-orders-channel-id", default=_env("CLIENT_COMPANY_ORDERS_CHANNEL_ID", ""))
        parser.add_argument("--b2c-orders-channel-id", default=_env("CLIENT_B2C_ORDERS_CHANNEL_ID", ""))
        parser.add_argument("--b2b-orders-channel-id", default=_env("CLIENT_B2B_ORDERS_CHANNEL_ID", ""))
        parser.add_argument("--payme-enabled", action="store_true", default=_env("CLIENT_PAYME_ENABLED", "false").lower() == "true")
        parser.add_argument("--payme-sandbox", action="store_true", default=_env("CLIENT_PAYME_SANDBOX", "false").lower() == "true")
        parser.add_argument("--payme-merchant-id", default=_env("CLIENT_PAYME_MERCHANT_ID", ""))
        parser.add_argument("--payme-secret-key", default=_env("CLIENT_PAYME_SECRET_KEY", ""))
        parser.add_argument("--payme-secret-key-prod", default=_env("CLIENT_PAYME_SECRET_KEY_PROD", ""))

    @transaction.atomic
    def handle(self, *args, **options):
        setup_password = options["setup_password"]
        owner_password = options["owner_password"]
        if not setup_password and not User.objects.filter(username=options["setup_username"]).exists():
            raise CommandError("Set --setup-password or SETUP_SUPERUSER_PASSWORD for the initial setup superuser.")
        if not owner_password and not User.objects.filter(username=options["owner_username"]).exists():
            raise CommandError("Set --owner-password or BUSINESS_OWNER_PASSWORD for the initial business owner.")

        setup_user = self._upsert_setup_user(options, setup_password)
        owner_user = self._upsert_owner_user(options, owner_password)
        owner_role = self._upsert_owner_role()
        center = self._upsert_center(options, owner_user)
        branch = self._upsert_branch(options, center)
        self._upsert_owner_profile(owner_user, owner_role, center, branch, setup_user)

        self.stdout.write(self.style.SUCCESS("Client bootstrap complete."))
        self.stdout.write(f"Setup superuser: {setup_user.username}")
        self.stdout.write(f"Business owner: {owner_user.username}")
        self.stdout.write(f"Center: {center.name}")
        self.stdout.write(f"Main branch: {branch.name}")

    def _upsert_setup_user(self, options, password):
        user, created = User.objects.get_or_create(
            username=options["setup_username"],
            defaults={
                "email": options["setup_email"],
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        user.email = options["setup_email"]
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if password:
            user.set_password(password)
        user.save()
        self.stdout.write(("Created" if created else "Updated") + f" setup superuser {user.username}.")
        return user

    def _upsert_owner_user(self, options, password):
        user, created = User.objects.get_or_create(
            username=options["owner_username"],
            defaults={
                "email": options["owner_email"],
                "first_name": options["owner_first_name"],
                "last_name": options["owner_last_name"],
                "is_staff": True,
                "is_superuser": False,
                "is_active": True,
            },
        )
        user.email = options["owner_email"]
        user.first_name = options["owner_first_name"]
        user.last_name = options["owner_last_name"]
        user.is_staff = True
        user.is_superuser = False
        user.is_active = True
        if password:
            user.set_password(password)
        user.save()
        self.stdout.write(("Created" if created else "Updated") + f" business owner {user.username}.")
        return user

    def _upsert_owner_role(self):
        defaults = Role.get_default_permissions_for_role(Role.OWNER)
        defaults.update({
            "display_name": "Owner",
            "description": "Business owner. Operational access without setup credential editing.",
            "is_active": True,
            "is_system_role": True,
        })
        role, created = Role.objects.update_or_create(name=Role.OWNER, defaults=defaults)
        self.stdout.write(("Created" if created else "Updated") + " owner role.")
        return role

    def _upsert_center(self, options, owner_user):
        center = TranslationCenter.objects.order_by("id").first()
        if not center:
            center = TranslationCenter(owner=owner_user)

        center.name = options["center_name"]
        center.owner = owner_user
        center.subdomain = options["center_subdomain"] or center.subdomain
        center.is_active = True

        center.bot_token = options["bot_token"] or center.bot_token
        center.bot_username = (options["bot_username"].lstrip("@") or center.bot_username)
        center.company_orders_channel_id = options["company_orders_channel_id"] or center.company_orders_channel_id
        center.payme_enabled = bool(options["payme_enabled"] or center.payme_enabled)
        center.payme_sandbox = bool(options["payme_sandbox"] or center.payme_sandbox)
        center.payme_merchant_id = options["payme_merchant_id"] or center.payme_merchant_id
        center.payme_secret_key = options["payme_secret_key"] or center.payme_secret_key
        center.payme_secret_key_prod = options["payme_secret_key_prod"] or center.payme_secret_key_prod
        center.save()
        return center

    def _upsert_branch(self, options, center):
        branch = Branch.objects.filter(center=center, is_main=True).first()
        if not branch:
            branch = Branch.objects.filter(center=center).order_by("id").first()
        if not branch:
            branch = Branch(center=center, is_main=True)

        branch.name = options["branch_name"]
        branch.center = center
        branch.is_main = True
        branch.is_active = True
        branch.b2c_orders_channel_id = options["b2c_orders_channel_id"] or branch.b2c_orders_channel_id
        branch.b2b_orders_channel_id = options["b2b_orders_channel_id"] or branch.b2b_orders_channel_id
        branch.save()
        return branch

    def _upsert_owner_profile(self, owner_user, owner_role, center, branch, setup_user):
        profile, created = AdminUser.objects.update_or_create(
            user=owner_user,
            defaults={
                "role": owner_role,
                "center": center,
                "branch": branch,
                "is_active": True,
                "created_by": setup_user,
            },
        )
        self.stdout.write(("Created" if created else "Updated") + f" owner profile {profile}.")
        return profile
