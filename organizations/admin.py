from django.contrib import admin
from .models import TranslationCenter, Branch, Role, AdminUser
from .credential_locks import (
    BRANCH_SETUP_FIELDS,
    CENTER_SETUP_FIELDS,
    SETUP_FIELD_LABELS,
    is_configured,
    mask_identifier,
    setup_change_summary,
)
from core.audit import log_update


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ['name', 'region', 'district', 'phone', 'is_main', 'is_active',
              'b2c_orders_channel_id', 'b2b_orders_channel_id']

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return list(BRANCH_SETUP_FIELDS)
        return []


def _initial_setup_summary(obj, fields):
    changes = {}
    for field in fields:
        value = getattr(obj, field, None)
        if isinstance(value, bool) and not value:
            if field == "payme_sandbox" and getattr(obj, "payme_enabled", False):
                pass
            else:
                continue
        if not is_configured(value) and not isinstance(value, bool):
            continue

        if field == "payme_sandbox":
            display = "Sandbox" if value else "Production"
        elif field == "payme_enabled":
            display = "Enabled" if value else "Disabled"
        elif field in {"bot_token", "payme_secret_key", "payme_secret_key_prod"}:
            display = "Configured" if is_configured(value) else "Missing"
        else:
            display = mask_identifier(value) or "Missing"

        changes[field] = {
            "label": str(SETUP_FIELD_LABELS.get(field, field)),
            "old": "Missing",
            "new": display,
        }
    return changes


@admin.register(TranslationCenter)
class TranslationCenterAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'phone', 'is_active', 'payme_enabled', 'created_at']
    list_filter = ['is_active', 'payme_enabled', 'created_at']
    search_fields = ['name', 'owner__username', 'owner__first_name', 'owner__last_name']
    inlines = [BranchInline]
    ordering = ['-created_at']
    fieldsets = (
        (None, {
            'fields': ('name', 'subdomain', 'owner', 'logo', 'phone', 'email',
                       'address', 'location_url', 'is_active'),
        }),
        ('Bot Configuration', {
            'fields': ('bot_token', 'bot_username', 'company_orders_channel_id'),
            'classes': ('collapse',),
        }),
        ('Payme Integration', {
            'fields': ('payme_enabled', 'payme_sandbox', 'payme_merchant_id',
                       'payme_secret_key', 'payme_secret_key_prod'),
            'classes': ('collapse',),
            'description': (
                'Enable Payme card payment for this center. '
                'Leave Merchant ID and Secret Key blank to use the global settings from .env. '
                'Per-center keys override the global values only for this center.'
            ),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return list(CENTER_SETUP_FIELDS)
        return []

    def save_model(self, request, obj, form, change):
        old_obj = None
        if change and obj.pk:
            old_obj = TranslationCenter.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        changes = (
            setup_change_summary(old_obj, obj, CENTER_SETUP_FIELDS)
            if change
            else _initial_setup_summary(obj, CENTER_SETUP_FIELDS)
        )
        if changes:
            log_update(
                user=request.user,
                target=obj,
                changes=changes,
                details="Setup-only center configuration changed.",
                request=request,
            )


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'center', 'region', 'is_main', 'show_pricelist', 'is_active']
    list_filter = ['center', 'region', 'is_main', 'show_pricelist', 'is_active']
    search_fields = ['name', 'center__name', 'region__name']
    ordering = ['center', '-is_main', 'name']
    fieldsets = (
        (None, {
            'fields': ('center', 'region', 'district', 'name', 'address', 'phone',
                       'location_url', 'is_main', 'show_pricelist', 'is_active'),
        }),
        ('Telegram Routing', {
            'fields': ('b2c_orders_channel_id', 'b2b_orders_channel_id'),
            'classes': ('collapse',),
            'description': 'Setup-only Telegram channel IDs for order routing.',
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return list(BRANCH_SETUP_FIELDS)
        return []

    def save_model(self, request, obj, form, change):
        old_obj = None
        if change and obj.pk:
            old_obj = Branch.objects.get(pk=obj.pk)

        super().save_model(request, obj, form, change)

        changes = (
            setup_change_summary(old_obj, obj, BRANCH_SETUP_FIELDS)
            if change
            else _initial_setup_summary(obj, BRANCH_SETUP_FIELDS)
        )
        if changes:
            log_update(
                user=request.user,
                target=obj,
                changes=changes,
                details="Setup-only branch configuration changed.",
                request=request,
            )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'is_system_role', 'is_active',
                    'can_manage_centers', 'can_manage_branches', 'can_manage_staff', 
                    'can_manage_orders', 'can_manage_financial']
    list_filter = ['is_system_role', 'is_active']
    search_fields = ['name', 'display_name']
    fieldsets = (
        (None, {
            'fields': ('name', 'display_name', 'description', 'is_active', 'is_system_role')
        }),
        ('Center Management', {
            'fields': (
                'can_manage_centers',
                'can_view_centers',
                'can_create_centers',
                'can_edit_centers',
                'can_delete_centers',
            ),
            'classes': ('collapse',),
        }),
        ('Branch Management', {
            'fields': (
                'can_manage_branches',
                'can_view_branches',
                'can_create_branches',
                'can_edit_branches',
                'can_delete_branches',
            ),
            'classes': ('collapse',),
        }),
        ('Staff Management', {
            'fields': (
                'can_manage_staff',
                'can_view_staff',
                'can_create_staff',
                'can_edit_staff',
                'can_delete_staff',
            ),
            'classes': ('collapse',),
        }),
        ('Order Management', {
            'fields': (
                'can_manage_orders',
                'can_view_all_orders',
                'can_view_own_orders',
                'can_create_orders',
                'can_edit_orders',
                'can_delete_orders',
                'can_assign_orders',
                'can_update_order_status',
                'can_complete_orders',
                'can_cancel_orders',
            ),
            'classes': ('collapse',),
        }),
        ('Financial Permissions', {
            'fields': (
                'can_manage_financial',
                'can_receive_payments',
                'can_view_financial_reports',
                'can_apply_discounts',
                'can_refund_orders',
            ),
            'classes': ('collapse',),
        }),
        ('Reports & Analytics', {
            'fields': (
                'can_manage_reports',
                'can_view_reports',
                'can_view_analytics',
                'can_export_data',
            ),
            'classes': ('collapse',),
        }),
        ('Products', {
            'fields': (
                'can_manage_products',
                'can_view_products',
                'can_create_products',
                'can_edit_products',
                'can_delete_products',
            ),
            'classes': ('collapse',),
        }),
        ('Customers', {
            'fields': (
                'can_manage_customers',
                'can_view_customers',
                'can_edit_customers',
                'can_delete_customers',
            ),
            'classes': ('collapse',),
        }),
        ('Marketing & Broadcasts', {
            'fields': (
                'can_manage_marketing',
                'can_create_marketing_posts',
                'can_send_branch_broadcasts',
                'can_send_center_broadcasts',
                'can_view_broadcast_stats',
            ),
            'classes': ('collapse',),
        }),
        ('Branch Settings', {
            'fields': (
                'can_manage_branch_settings',
                'can_view_branch_settings',
            ),
            'classes': ('collapse',),
        }),
        ('Agency Management', {
            'fields': (
                'can_manage_agencies',
                'can_view_agencies',
                'can_create_agencies',
                'can_edit_agencies',
                'can_delete_agencies',
            ),
            'classes': ('collapse',),
        }),
        ('Bulk Payments (Debt Management)', {
            'fields': (
                'can_manage_bulk_payments',
                'can_assign_bulk_payment_permission',
            ),
            'classes': ('collapse',),
            'description': 'Permissions for processing bulk payments across multiple orders. '
                          'can_assign_bulk_payment_permission allows granting this permission to other roles.'
        }),
    )


@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'center', 'branch', 'phone', 'is_active', 'created_at']
    list_filter = ['role', 'center', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone']
    raw_id_fields = ['user', 'created_by']
    ordering = ['-created_at']
    
    def get_readonly_fields(self, request, obj=None):
        """Prevent non-superusers from changing role to owner"""
        if obj and obj.is_owner and not request.user.is_superuser:
            return ['role']
        return []
    
    def save_model(self, request, obj, form, change):
        """Validate role assignment before saving"""
        if not request.user.is_superuser and obj.role.name == Role.OWNER:
            from django.contrib import messages
            messages.error(request, "Only superusers can assign the Owner role.")
            return
        super().save_model(request, obj, form, change)
