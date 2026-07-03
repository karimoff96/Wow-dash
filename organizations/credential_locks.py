"""Setup-only credential helpers for client deployments."""

from django.utils.translation import gettext_lazy as _


CENTER_SETUP_FIELDS = (
    "bot_token",
    "bot_username",
    "company_orders_channel_id",
    "payme_enabled",
    "payme_sandbox",
    "payme_merchant_id",
    "payme_secret_key",
    "payme_secret_key_prod",
)

BRANCH_SETUP_FIELDS = (
    "b2c_orders_channel_id",
    "b2b_orders_channel_id",
)

SETUP_FIELD_LABELS = {
    "bot_token": _("Telegram bot token"),
    "bot_username": _("Telegram bot username"),
    "company_orders_channel_id": _("Company orders channel"),
    "payme_enabled": _("Payme enabled"),
    "payme_sandbox": _("Payme mode"),
    "payme_merchant_id": _("Payme merchant ID"),
    "payme_secret_key": _("Payme sandbox secret"),
    "payme_secret_key_prod": _("Payme production secret"),
    "b2c_orders_channel_id": _("B2C orders channel"),
    "b2b_orders_channel_id": _("B2B orders channel"),
}

SECRET_FIELDS = {
    "bot_token",
    "payme_secret_key",
    "payme_secret_key_prod",
}


def is_configured(value):
    return value is not None and str(value).strip() != ""


def mask_identifier(value, visible_start=4, visible_end=4):
    if not is_configured(value):
        return ""

    value = str(value).strip()
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return f"{value[:visible_start]}...{value[-visible_end:]}"


def configured_label(value):
    return _("Configured") if is_configured(value) else _("Missing")


def configured_badge(value):
    return "bg-success-focus text-success-main" if is_configured(value) else "bg-danger-focus text-danger-main"


def setup_change_summary(old_obj, new_obj, fields):
    changes = {}
    if not old_obj:
        return changes

    for field in fields:
        old_value = getattr(old_obj, field, None)
        new_value = getattr(new_obj, field, None)
        if str(old_value or "") == str(new_value or ""):
            continue

        if field in SECRET_FIELDS:
            old_display = configured_label(old_value)
            new_display = configured_label(new_value)
        elif field == "payme_sandbox":
            old_display = _("Sandbox") if old_value else _("Production")
            new_display = _("Sandbox") if new_value else _("Production")
        elif field == "payme_enabled":
            old_display = _("Enabled") if old_value else _("Disabled")
            new_display = _("Enabled") if new_value else _("Disabled")
        else:
            old_display = mask_identifier(old_value) or _("Missing")
            new_display = mask_identifier(new_value) or _("Missing")

        changes[field] = {
            "label": str(SETUP_FIELD_LABELS.get(field, field)),
            "old": str(old_display),
            "new": str(new_display),
        }

    return changes


def build_center_setup_status(center):
    if not center:
        return {
            "items": [],
            "admin_url": None,
        }

    payme_secret = center.payme_secret_key if center.payme_sandbox else center.payme_secret_key_prod
    return {
        "admin_url": f"/admin/organizations/translationcenter/{center.pk}/change/",
        "items": [
            {
                "label": _("Telegram bot token"),
                "value": configured_label(center.bot_token),
                "badge": configured_badge(center.bot_token),
                "detail": _("Stored securely") if center.bot_token else _("Not configured"),
            },
            {
                "label": _("Bot username"),
                "value": f"@{center.bot_username}" if center.bot_username else configured_label(None),
                "badge": configured_badge(center.bot_username),
                "detail": _("Public identifier"),
            },
            {
                "label": _("Company orders channel"),
                "value": mask_identifier(center.company_orders_channel_id) or configured_label(None),
                "badge": configured_badge(center.company_orders_channel_id),
                "detail": _("Order archive destination"),
            },
            {
                "label": _("Webhook"),
                "value": _("Ready") if center.bot_token and center.subdomain else _("Needs setup"),
                "badge": (
                    "bg-success-focus text-success-main"
                    if center.bot_token and center.subdomain
                    else "bg-warning-focus text-warning-main"
                ),
                "detail": _("Managed by setup superuser"),
            },
            {
                "label": _("Payme"),
                "value": _("Enabled") if center.payme_enabled else _("Disabled"),
                "badge": (
                    "bg-success-focus text-success-main"
                    if center.payme_enabled
                    else "bg-neutral-100 text-secondary-light"
                ),
                "detail": _("Sandbox") if center.payme_sandbox else _("Production"),
            },
            {
                "label": _("Payme merchant ID"),
                "value": mask_identifier(center.payme_merchant_id) or configured_label(None),
                "badge": configured_badge(center.payme_merchant_id),
                "detail": _("Masked identifier"),
            },
            {
                "label": _("Active Payme secret"),
                "value": configured_label(payme_secret),
                "badge": configured_badge(payme_secret),
                "detail": _("Sandbox key") if center.payme_sandbox else _("Production key"),
            },
            {
                "label": _("Last health check"),
                "value": _("Not checked"),
                "badge": "bg-neutral-100 text-secondary-light",
                "detail": _("Monitoring bot reports live failures"),
            },
        ],
    }


def build_branch_setup_status(branch):
    if not branch:
        return {"items": []}

    return {
        "items": [
            {
                "label": _("B2C orders channel"),
                "value": mask_identifier(branch.b2c_orders_channel_id) or configured_label(None),
                "badge": configured_badge(branch.b2c_orders_channel_id),
                "detail": _("Individual customer order routing"),
            },
            {
                "label": _("B2B orders channel"),
                "value": mask_identifier(branch.b2b_orders_channel_id) or configured_label(None),
                "badge": configured_badge(branch.b2b_orders_channel_id),
                "detail": _("Agency order routing"),
            },
        ],
    }
