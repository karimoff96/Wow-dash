from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class TranslationCenter(models.Model):
    """Translation center owned by an owner"""

    name = models.CharField(_("Name"), max_length=200)
    subdomain = models.SlugField(
        _("Subdomain"),
        max_length=63,
        unique=True,
        blank=True,
        null=True,
        help_text=_("Unique subdomain for this center (e.g., 'center1' for center1.alltranslation.uz)"),
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_centers",
        verbose_name=_("Owner"),
    )
    logo = models.ImageField(
        _("Logo"), upload_to="centers/logos/", blank=True, null=True
    )
    address = models.TextField(_("Address"), blank=True, null=True)
    phone = models.CharField(_("Phone"), max_length=20, blank=True, null=True)
    email = models.EmailField(_("Email"), blank=True, null=True)
    location_url = models.URLField(
        _("Location URL"),
        blank=True,
        null=True,
        help_text=_("Google Maps or Yandex Maps URL"),
    )
    # Bot integration fields
    bot_token = models.CharField(
        _("Bot Token"),
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=_("Telegram Bot Token for this center (unique, superuser only)"),
    )
    bot_username = models.CharField(
        _("Bot Username"),
        max_length=100,
        blank=True,
        null=True,
        help_text=_("Telegram Bot username without @ (e.g., 'my_translation_bot')"),
    )
    company_orders_channel_id = models.CharField(
        _("Company Orders Channel ID"),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Telegram channel ID for all company orders"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Translation Center")
        verbose_name_plural = _("Translation Centers")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        """Validate model data"""
        super().clean()
        # Warn if trying to delete center with bot_token
        if self.bot_token:
            # This will be checked in delete() method
            pass

    def delete(self, *args, **kwargs):
        """Override delete to warn about bot_token"""
        if self.bot_token:
            raise ValidationError(
                _("Cannot delete center with active bot token. Remove the bot token first.")
            )
        super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Auto-create default branch for new centers
        if is_new:
            Branch.objects.create(
                center=self, name=f"{self.name} - Main Branch", is_main=True
            )


class Branch(models.Model):
    """Physical branch location of a translation center"""

    center = models.ForeignKey(
        TranslationCenter,
        on_delete=models.CASCADE,
        related_name="branches",
        verbose_name=_("Translation Center"),
    )
    region = models.ForeignKey(
        "core.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("Region"),
    )
    district = models.ForeignKey(
        "core.District",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("District"),
    )
    name = models.CharField(_("Name"), max_length=200)
    address = models.TextField(_("Address"), blank=True, null=True)
    phone = models.CharField(_("Phone"), max_length=20, blank=True, null=True)
    location_url = models.URLField(
        _("Location URL"),
        blank=True,
        null=True,
        help_text=_("Google Maps or Yandex Maps URL"),
    )
    is_main = models.BooleanField(_("Main Branch"), default=False)
    # Bot channel fields for order routing
    b2c_orders_channel_id = models.CharField(
        _("B2C Orders Channel ID"),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Telegram channel ID for B2C (individual customer) orders"),
    )
    b2b_orders_channel_id = models.CharField(
        _("B2B Orders Channel ID"),
        max_length=50,
        blank=True,
        null=True,
        help_text=_("Telegram channel ID for B2B (agency/business) orders"),
    )
    show_pricelist = models.BooleanField(
        _("Show Price List"),
        default=False,
        help_text=_("Show price list button in Telegram bot for this branch"),
    )
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        ordering = ["center", "-is_main", "name"]

    def __str__(self):
        return f"{self.name} ({self.center.name})"


class Role(models.Model):
    """Roles with customizable permissions - can be created by superusers"""

    # System role identifiers (used for special logic)
    OWNER = "owner"
    MANAGER = "manager"
    STAFF = "staff"

    # These are just defaults/system roles - custom roles can be created
    SYSTEM_ROLES = [OWNER, MANAGER, STAFF]

    name = models.CharField(_("Name"), max_length=50, unique=True)
    display_name = models.CharField(_("Display Name"), max_length=100, blank=True)
    description = models.TextField(_("Description"), blank=True, null=True)
    is_active = models.BooleanField(_("Active"), default=True)
    is_system_role = models.BooleanField(
        _("System Role"), default=False, help_text=_("System roles cannot be deleted")
    )

    # Permissions - Organization Management (Centers)
    can_manage_centers = models.BooleanField(_("Can manage centers (full access)"), default=False,
        help_text=_("Full center management - overrides other center permissions"))
    can_view_centers = models.BooleanField(_("Can view centers"), default=False,
        help_text=_("Can view translation center details"))
    can_create_centers = models.BooleanField(_("Can create centers"), default=False,
        help_text=_("Can create new translation centers"))
    can_edit_centers = models.BooleanField(_("Can edit centers"), default=False,
        help_text=_("Can edit translation center settings"))
    can_delete_centers = models.BooleanField(_("Can delete centers"), default=False,
        help_text=_("Can delete translation centers"))
    
    # Permissions - Organization Management (Branches)
    can_manage_branches = models.BooleanField(_("Can manage branches (full access)"), default=False,
        help_text=_("Full branch management - overrides other branch permissions"))
    can_view_branches = models.BooleanField(_("Can view branches"), default=False,
        help_text=_("Can view branch details"))
    can_create_branches = models.BooleanField(_("Can create branches"), default=False,
        help_text=_("Can create new branches"))
    can_edit_branches = models.BooleanField(_("Can edit branches"), default=False,
        help_text=_("Can edit branch settings"))
    can_delete_branches = models.BooleanField(_("Can delete branches"), default=False,
        help_text=_("Can delete branches"))
    
    # Permissions - Staff Management
    can_manage_staff = models.BooleanField(_("Can manage staff (full access)"), default=False,
        help_text=_("Full staff management - overrides other staff permissions"))
    can_view_staff = models.BooleanField(_("Can view staff"), default=False,
        help_text=_("Can view staff details"))
    can_create_staff = models.BooleanField(_("Can create staff"), default=False,
        help_text=_("Can create new staff members"))
    can_edit_staff = models.BooleanField(_("Can edit staff"), default=False,
        help_text=_("Can edit staff details and roles"))
    can_delete_staff = models.BooleanField(_("Can delete staff"), default=False,
        help_text=_("Can delete staff members"))
    
    # Permissions - Order Management (Granular)
    can_manage_orders = models.BooleanField(_("Can manage orders (full access)"), default=False, 
        help_text=_("Full order management - overrides other order permissions"))
    can_view_all_orders = models.BooleanField(_("Can view all orders"), default=False)
    can_view_own_orders = models.BooleanField(_("Can view own orders"), default=True)
    can_create_orders = models.BooleanField(_("Can create orders"), default=False)
    can_edit_orders = models.BooleanField(_("Can edit orders"), default=False)
    can_delete_orders = models.BooleanField(_("Can delete orders"), default=False)
    can_assign_orders = models.BooleanField(_("Can assign orders"), default=False)
    can_update_order_status = models.BooleanField(_("Can update order status"), default=False)
    can_complete_orders = models.BooleanField(_("Can complete orders"), default=False)
    can_cancel_orders = models.BooleanField(_("Can cancel orders"), default=False)
    
    # Permissions - Financial
    can_manage_financial = models.BooleanField(_("Can manage financial (full access)"), default=False,
        help_text=_("Full financial management - overrides other financial permissions"))
    can_receive_payments = models.BooleanField(_("Can receive payments"), default=False)
    can_view_financial_reports = models.BooleanField(_("Can view financial reports"), default=False)
    can_apply_discounts = models.BooleanField(_("Can apply discounts"), default=False)
    can_refund_orders = models.BooleanField(_("Can refund orders"), default=False)
    
    # Permissions - Reports & Analytics
    can_manage_reports = models.BooleanField(_("Can manage reports (full access)"), default=False,
        help_text=_("Full reports management - overrides other report permissions"))
    can_view_reports = models.BooleanField(_("Can view reports"), default=False)
    can_view_analytics = models.BooleanField(_("Can view analytics"), default=False)
    can_export_data = models.BooleanField(_("Can export data"), default=False)
    
    # Permissions - Products & Customers
    can_manage_products = models.BooleanField(_("Can manage products (full access)"), default=False,
        help_text=_("Full product management - overrides other product permissions"))
    can_view_products = models.BooleanField(_("Can view products"), default=False)
    can_create_products = models.BooleanField(_("Can create products"), default=False)
    can_edit_products = models.BooleanField(_("Can edit products"), default=False)
    can_delete_products = models.BooleanField(_("Can delete products"), default=False)
    
    # Permissions - Expenses
    can_manage_expenses = models.BooleanField(_("Can manage expenses (full access)"), default=False,
        help_text=_("Full expense management - overrides other expense permissions"))
    can_view_expenses = models.BooleanField(_("Can view expenses"), default=False)
    can_create_expenses = models.BooleanField(_("Can create expenses"), default=False)
    can_edit_expenses = models.BooleanField(_("Can edit expenses"), default=False)
    can_delete_expenses = models.BooleanField(_("Can delete expenses"), default=False)
    
    can_manage_customers = models.BooleanField(_("Can manage customers (full access)"), default=False,
        help_text=_("Full customer management - overrides other customer permissions"))
    can_view_customers = models.BooleanField(_("Can view customers"), default=False)
    can_create_customers = models.BooleanField(_("Can create customers"), default=False,
        help_text=_("Can create new customer profiles"))
    can_edit_customers = models.BooleanField(_("Can edit customers"), default=False)
    can_delete_customers = models.BooleanField(_("Can delete customers"), default=False)
    
    # Permissions - Marketing & Broadcasts
    can_manage_marketing = models.BooleanField(_("Can manage marketing (full access)"), default=False,
        help_text=_("Full marketing management - overrides other marketing permissions"))
    can_create_marketing_posts = models.BooleanField(_("Can create marketing posts"), default=False)
    can_send_branch_broadcasts = models.BooleanField(_("Can send branch broadcasts"), default=False)
    can_send_center_broadcasts = models.BooleanField(_("Can send center-wide broadcasts"), default=False)
    can_view_broadcast_stats = models.BooleanField(_("Can view broadcast statistics"), default=False)
    
    # Permissions - Branch Settings (Additional Info)
    can_manage_branch_settings = models.BooleanField(_("Can manage branch settings"), default=False,
        help_text=_("Can edit branch payment info, help texts, about us, working hours"))
    can_view_branch_settings = models.BooleanField(_("Can view branch settings"), default=False,
        help_text=_("Can view branch settings without editing"))
    
    # Permissions - Agency Management
    can_manage_agencies = models.BooleanField(_("Can manage agencies (full access)"), default=False,
        help_text=_("Full agency management - overrides other agency permissions"))
    can_view_agencies = models.BooleanField(_("Can view agencies"), default=False,
        help_text=_("Can view list of agency partners"))
    can_create_agencies = models.BooleanField(_("Can create agencies"), default=False,
        help_text=_("Can create new agency profiles and generate invite links"))
    can_edit_agencies = models.BooleanField(_("Can edit agencies"), default=False,
        help_text=_("Can edit agency details and reset invite links"))
    can_delete_agencies = models.BooleanField(_("Can delete agencies"), default=False,
        help_text=_("Can delete agency profiles"))
    
    # Permissions - Audit Logs
    can_manage_audit_logs = models.BooleanField(_("Can manage audit logs (full access)"), default=False,
        help_text=_("Full audit log access - overrides other audit log permissions"))
    can_view_audit_logs = models.BooleanField(_("Can view audit logs"), default=False,
        help_text=_("Can view system audit logs and activity history"))
    can_export_audit_logs = models.BooleanField(_("Can export audit logs"), default=False,
        help_text=_("Can export audit log data to CSV/Excel"))
    can_grant_audit_permissions = models.BooleanField(_("Can grant audit permissions"), default=False,
        help_text=_("Can assign audit log permissions to lower-level users"))

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True, null=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True, null=True)

    class Meta:
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")
        ordering = ["name"]

    def __str__(self):
        return self.display_name or self.name.title()

    def get_name_display(self):
        """Return the display name of the role (for backwards compatibility)"""
        return self.display_name or self.name.replace("_", " ").title()

    def save(self, *args, **kwargs):
        # Auto-set display name if not provided
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").title()
        # Mark system roles
        if self.name in self.SYSTEM_ROLES:
            self.is_system_role = True
        super().save(*args, **kwargs)

    # Master permissions that grant full access to a category
    MASTER_PERMISSIONS = [
        "can_manage_centers",
        "can_manage_branches", 
        "can_manage_staff",
        "can_manage_orders",
        "can_manage_financial",
        "can_manage_reports",
        "can_manage_products",
        "can_manage_expenses",
        "can_manage_customers",
        "can_manage_marketing",
        "can_manage_branch_settings",
        "can_manage_agencies",
        "can_manage_audit_logs",
    ]

    # Superuser-only permissions (should not be displayed for regular staff)
    SUPERUSER_ONLY_PERMISSIONS = [
        "can_manage_centers",
        "can_create_centers",
        "can_delete_centers",
    ]

    # Mapping of master permissions to their child permissions
    MASTER_TO_CHILDREN = {
        "can_manage_centers": ["can_view_centers", "can_create_centers", "can_edit_centers", "can_delete_centers"],
        "can_manage_branches": ["can_view_branches", "can_create_branches", "can_edit_branches", "can_delete_branches"],
        "can_manage_staff": ["can_view_staff", "can_create_staff", "can_edit_staff", "can_delete_staff"],
        "can_manage_orders": ["can_view_all_orders", "can_view_own_orders", "can_create_orders", "can_edit_orders", 
                              "can_delete_orders", "can_assign_orders", "can_update_order_status", 
                              "can_complete_orders", "can_cancel_orders"],
        "can_manage_financial": ["can_receive_payments", "can_view_financial_reports", "can_apply_discounts", "can_refund_orders"],
        "can_manage_reports": ["can_view_reports", "can_view_analytics", "can_export_data"],
        "can_manage_products": ["can_view_products", "can_create_products", "can_edit_products", "can_delete_products"],
        "can_manage_expenses": ["can_view_expenses", "can_create_expenses", "can_edit_expenses", "can_delete_expenses"],
        "can_manage_customers": ["can_view_customers", "can_edit_customers", "can_delete_customers"],
        "can_manage_marketing": ["can_create_marketing_posts", "can_send_branch_broadcasts", 
                                  "can_send_center_broadcasts", "can_view_broadcast_stats"],
        "can_manage_branch_settings": ["can_view_branch_settings"],
        "can_manage_agencies": ["can_view_agencies", "can_create_agencies", "can_edit_agencies", "can_delete_agencies"],
        "can_manage_audit_logs": ["can_view_audit_logs", "can_export_audit_logs", "can_grant_audit_permissions"],
    }

    def has_effective_permission(self, permission):
        """Check if role has a permission, considering master permissions.
        If master permission is enabled, all its child permissions are effectively enabled."""
        # Direct check first
        if getattr(self, permission, False):
            return True
        
        # Check if any master permission grants this
        for master, children in self.MASTER_TO_CHILDREN.items():
            if permission in children and getattr(self, master, False):
                return True
        
        return False

    @classmethod
    def get_all_permissions(cls):
        """Return list of all permission field names grouped by category"""
        return [
            # Organization Management - Centers (master first)
            "can_manage_centers",
            "can_view_centers",
            "can_create_centers",
            "can_edit_centers",
            "can_delete_centers",
            # Organization Management - Branches (master first)
            "can_manage_branches",
            "can_view_branches",
            "can_create_branches",
            "can_edit_branches",
            "can_delete_branches",
            # Staff Management (master first)
            "can_manage_staff",
            "can_view_staff",
            "can_create_staff",
            "can_edit_staff",
            "can_delete_staff",
            # Order Management (master first)
            "can_manage_orders",
            "can_view_all_orders",
            "can_view_own_orders",
            "can_create_orders",
            "can_edit_orders",
            "can_delete_orders",
            "can_assign_orders",
            "can_update_order_status",
            "can_complete_orders",
            "can_cancel_orders",
            # Financial (master first)
            "can_manage_financial",
            "can_receive_payments",
            "can_view_financial_reports",
            "can_apply_discounts",
            "can_refund_orders",
            # Reports & Analytics (master first)
            "can_manage_reports",
            "can_view_reports",
            "can_view_analytics",
            "can_export_data",
            # Products (master first)
            "can_manage_products",
            "can_view_products",
            "can_create_products",
            "can_edit_products",
            "can_delete_products",
            # Expenses (master first)
            "can_manage_expenses",
            "can_view_expenses",
            "can_create_expenses",
            "can_edit_expenses",
            "can_delete_expenses",
            # Customers (master first)
            "can_manage_customers",
            "can_view_customers",
            "can_edit_customers",
            "can_delete_customers",
            # Marketing & Broadcasts (master first)
            "can_manage_marketing",
            "can_create_marketing_posts",
            "can_send_branch_broadcasts",
            "can_send_center_broadcasts",
            "can_view_broadcast_stats",
            # Branch Settings
            "can_manage_branch_settings",
            "can_view_branch_settings",
            # Agency Management (master first)
            "can_manage_agencies",
            "can_view_agencies",
            "can_create_agencies",
            "can_edit_agencies",
            "can_delete_agencies",
            # Audit Logs (master first)
            "can_manage_audit_logs",
            "can_view_audit_logs",
            "can_export_audit_logs",
            "can_grant_audit_permissions",
        ]

    @classmethod
    def get_display_permissions(cls):
        """Return permissions for display (excludes master and superuser-only permissions).
        Used on staff edit page to show individual permissions only."""
        excluded = set(cls.MASTER_PERMISSIONS) | set(cls.SUPERUSER_ONLY_PERMISSIONS)
        return [p for p in cls.get_all_permissions() if p not in excluded]

    @classmethod
    def get_display_permission_categories(cls):
        """Return permissions grouped by category for UI display, 
        excluding master and superuser-only permissions.
        Used on staff edit page for organized display."""
        excluded = set(cls.MASTER_PERMISSIONS) | set(cls.SUPERUSER_ONLY_PERMISSIONS)
        categories = cls.get_permission_categories()
        
        display_categories = {}
        for key, category in categories.items():
            # Filter out excluded permissions
            filtered_perms = [p for p in category["permissions"] if p not in excluded]
            if filtered_perms:  # Only include categories that have permissions left
                display_categories[key] = {
                    "title": category["title"],
                    "icon": category["icon"],
                    "color": category["color"],
                    "permissions": filtered_perms,
                }
        return display_categories

    @classmethod
    def get_permission_categories(cls):
        """Return permissions grouped by category for UI"""
        return {
            "centers": {
                "title": _("Center Management"),
                "icon": "fa-building",
                "color": "primary",
                "permissions": [
                    "can_manage_centers",
                    "can_view_centers",
                    "can_create_centers",
                    "can_edit_centers",
                    "can_delete_centers",
                ],
            },
            "branches": {
                "title": _("Branch Management"),
                "icon": "fa-code-branch",
                "color": "primary",
                "permissions": [
                    "can_manage_branches",
                    "can_view_branches",
                    "can_create_branches",
                    "can_edit_branches",
                    "can_delete_branches",
                ],
            },
            "staff": {
                "title": _("Staff Management"),
                "icon": "fa-users",
                "color": "info",
                "permissions": [
                    "can_manage_staff",
                    "can_view_staff",
                    "can_create_staff",
                    "can_edit_staff",
                    "can_delete_staff",
                ],
            },
            "orders": {
                "title": _("Order Management"),
                "icon": "fa-file-lines",
                "color": "success",
                "permissions": [
                    "can_manage_orders",
                    "can_view_all_orders",
                    "can_view_own_orders",
                    "can_create_orders",
                    "can_edit_orders",
                    "can_delete_orders",
                    "can_assign_orders",
                    "can_update_order_status",
                    "can_complete_orders",
                    "can_cancel_orders",
                ],
            },
            "financial": {
                "title": _("Financial"),
                "icon": "fa-money-bill-wave",
                "color": "warning",
                "permissions": [
                    "can_manage_financial",
                    "can_receive_payments",
                    "can_view_financial_reports",
                    "can_apply_discounts",
                    "can_refund_orders",
                ],
            },
            "reports": {
                "title": _("Reports & Analytics"),
                "icon": "fa-chart-line",
                "color": "purple",
                "permissions": [
                    "can_manage_reports",
                    "can_view_reports",
                    "can_view_analytics",
                    "can_export_data",
                ],
            },
            "products": {
                "title": _("Products"),
                "icon": "fa-box",
                "color": "danger",
                "permissions": [
                    "can_manage_products",
                    "can_view_products",
                    "can_create_products",
                    "can_edit_products",
                    "can_delete_products",
                ],
            },
            "expenses": {
                "title": _("Expenses"),
                "icon": "fa-receipt",
                "color": "warning",
                "permissions": [
                    "can_manage_expenses",
                    "can_view_expenses",
                    "can_create_expenses",
                    "can_edit_expenses",
                    "can_delete_expenses",
                ],
            },
            "customers": {
                "title": _("Customers"),
                "icon": "fa-user-group",
                "color": "cyan",
                "permissions": [
                    "can_manage_customers",
                    "can_view_customers",
                    "can_edit_customers",
                    "can_delete_customers",
                ],
            },
            "marketing": {
                "title": _("Marketing & Broadcasts"),
                "icon": "fa-bullhorn",
                "color": "secondary",
                "permissions": [
                    "can_manage_marketing",
                    "can_create_marketing_posts",
                    "can_send_branch_broadcasts",
                    "can_send_center_broadcasts",
                    "can_view_broadcast_stats",
                ],
            },
            "branch_settings": {
                "title": _("Branch Settings"),
                "icon": "fa-cog",
                "color": "teal",
                "permissions": [
                    "can_manage_branch_settings",
                    "can_view_branch_settings",
                ],
            },
            "agencies": {
                "title": _("Agency Management"),
                "icon": "fa-handshake",
                "color": "indigo",
                "permissions": [
                    "can_manage_agencies",
                    "can_view_agencies",
                    "can_create_agencies",
                    "can_edit_agencies",
                    "can_delete_agencies",
                ],
            },
        }

    @classmethod
    def get_permission_labels(cls):
        """Return human-readable labels for all permissions"""
        return {
            # Center Management
            "can_manage_centers": _("Full Center Management"),
            "can_view_centers": _("View Centers"),
            "can_create_centers": _("Create Centers"),
            "can_edit_centers": _("Edit Centers"),
            "can_delete_centers": _("Delete Centers"),
            # Branch Management
            "can_manage_branches": _("Full Branch Management"),
            "can_view_branches": _("View Branches"),
            "can_create_branches": _("Create Branches"),
            "can_edit_branches": _("Edit Branches"),
            "can_delete_branches": _("Delete Branches"),
            # Staff Management
            "can_manage_staff": _("Full Staff Management"),
            "can_view_staff": _("View Staff"),
            "can_create_staff": _("Create Staff"),
            "can_edit_staff": _("Edit Staff"),
            "can_delete_staff": _("Delete Staff"),
            # Order Management
            "can_manage_orders": _("Full Order Management"),
            "can_view_all_orders": _("View All Orders"),
            "can_view_own_orders": _("View Own Orders"),
            "can_create_orders": _("Create Orders"),
            "can_edit_orders": _("Edit Orders"),
            "can_delete_orders": _("Delete Orders"),
            "can_assign_orders": _("Assign Orders"),
            "can_update_order_status": _("Update Order Status"),
            "can_complete_orders": _("Complete Orders"),
            "can_cancel_orders": _("Cancel Orders"),
            # Financial
            "can_manage_financial": _("Full Financial Management"),
            "can_receive_payments": _("Receive Payments"),
            "can_view_financial_reports": _("View Financial Reports"),
            "can_apply_discounts": _("Apply Discounts"),
            "can_refund_orders": _("Refund Orders"),
            # Reports & Analytics
            "can_manage_reports": _("Full Reports Management"),
            "can_view_reports": _("View Reports"),
            "can_view_analytics": _("View Analytics"),
            "can_export_data": _("Export Data"),
            # Products
            "can_manage_products": _("Full Product Management"),
            "can_view_products": _("View Products"),
            "can_create_products": _("Create Products"),
            "can_edit_products": _("Edit Products"),
            "can_delete_products": _("Delete Products"),
            # Expenses
            "can_manage_expenses": _("Full Expense Management"),
            "can_view_expenses": _("View Expenses"),
            "can_create_expenses": _("Create Expenses"),
            "can_edit_expenses": _("Edit Expenses"),
            "can_delete_expenses": _("Delete Expenses"),
            # Customers
            "can_manage_customers": _("Full Customer Management"),
            "can_view_customers": _("View Customers"),
            "can_edit_customers": _("Edit Customers"),
            "can_delete_customers": _("Delete Customers"),
            # Marketing & Broadcasts
            "can_manage_marketing": _("Full Marketing Management"),
            "can_create_marketing_posts": _("Create Marketing Posts"),
            "can_send_branch_broadcasts": _("Send Branch Broadcasts"),
            "can_send_center_broadcasts": _("Send Center Broadcasts"),
            "can_view_broadcast_stats": _("View Broadcast Stats"),
            # Branch Settings
            "can_manage_branch_settings": _("Manage Branch Settings"),
            "can_view_branch_settings": _("View Branch Settings"),
            # Agency Management
            "can_manage_agencies": _("Full Agency Management"),
            "can_view_agencies": _("View Agencies"),
            "can_create_agencies": _("Create Agencies"),
            "can_edit_agencies": _("Edit Agencies"),
            "can_delete_agencies": _("Delete Agencies"),
        }
    
    @classmethod
    def get_permission_descriptions(cls):
        """Return detailed descriptions for all permissions"""
        return {
            # Center Management
            "can_manage_centers": _("Full control over all center operations - overrides individual permissions"),
            "can_view_centers": _("View translation center details and settings"),
            "can_create_centers": _("Create new translation centers"),
            "can_edit_centers": _("Edit translation center settings and configuration"),
            "can_delete_centers": _("Delete translation centers (requires removing bot token first)"),
            # Branch Management
            "can_manage_branches": _("Full control over all branch operations - overrides individual permissions"),
            "can_view_branches": _("View branch details and settings"),
            "can_create_branches": _("Create new branches within centers"),
            "can_edit_branches": _("Edit branch settings and configuration"),
            "can_delete_branches": _("Delete branches from the system"),
            # Staff Management
            "can_manage_staff": _("Full control over all staff operations - overrides individual permissions"),
            "can_view_staff": _("View staff profiles and details"),
            "can_create_staff": _("Create new staff members and assign roles"),
            "can_edit_staff": _("Edit staff details and change their roles"),
            "can_delete_staff": _("Remove staff members from the system"),
            # Order Management
            "can_manage_orders": _("Full control over all order operations - overrides individual permissions"),
            "can_view_all_orders": _("View all orders in the center/branch, not just assigned ones"),
            "can_view_own_orders": _("View orders assigned to this user"),
            "can_create_orders": _("Create new translation orders"),
            "can_edit_orders": _("Modify existing order details, files, and settings"),
            "can_delete_orders": _("Permanently remove orders from the system"),
            "can_assign_orders": _("Assign orders to other staff members"),
            "can_update_order_status": _("Change order status (pending, in progress, etc.)"),
            "can_complete_orders": _("Mark orders as completed/delivered"),
            "can_cancel_orders": _("Cancel active orders"),
            # Financial
            "can_manage_financial": _("Full control over all financial operations - overrides individual permissions"),
            "can_receive_payments": _("Accept and record customer payments"),
            "can_view_financial_reports": _("Access financial reports and revenue data"),
            "can_apply_discounts": _("Apply discounts to orders"),
            "can_refund_orders": _("Process refunds for completed or cancelled orders"),
            # Reports & Analytics
            "can_manage_reports": _("Full control over all report operations - overrides individual permissions"),
            "can_view_reports": _("Access performance and activity reports"),
            "can_view_analytics": _("View analytics dashboard with charts and metrics"),
            "can_export_data": _("Export data to Excel, PDF, or other formats"),
            # Products
            "can_manage_products": _("Full control over all product operations - overrides individual permissions"),
            "can_view_products": _("View product and service listings"),
            "can_create_products": _("Add new services and products"),
            "can_edit_products": _("Edit existing services and products"),
            "can_delete_products": _("Remove services and products from the system"),
            # Expenses
            "can_manage_expenses": _("Full control over all expense operations - overrides individual permissions"),
            "can_view_expenses": _("View expense records and reports"),
            "can_create_expenses": _("Add new expense entries"),
            "can_edit_expenses": _("Edit existing expense records"),
            "can_delete_expenses": _("Remove expense records from the system"),
            # Customers
            "can_manage_customers": _("Full control over all customer operations - overrides individual permissions"),
            "can_view_customers": _("View customer information and history"),
            "can_edit_customers": _("Edit customer records and contact information"),
            "can_delete_customers": _("Remove customer records from the system"),
            # Marketing & Broadcasts
            "can_manage_marketing": _("Full control over all marketing operations - overrides individual permissions"),
            "can_create_marketing_posts": _("Create and edit marketing posts and announcements"),
            "can_send_branch_broadcasts": _("Send broadcast messages to all customers in their branch"),
            "can_send_center_broadcasts": _("Send broadcast messages to all customers across the entire center"),
            "can_view_broadcast_stats": _("View broadcast delivery statistics and analytics"),
            # Branch Settings
            "can_manage_branch_settings": _("Edit branch payment info, help texts, about us, and working hours"),
            "can_view_branch_settings": _("View branch settings without the ability to edit"),
            # Agency Management
            "can_manage_agencies": _("Full control over all agency operations - overrides individual permissions"),
            "can_view_agencies": _("View list of agency partners and their details"),
            "can_create_agencies": _("Create new agency profiles and generate invitation links"),
            "can_edit_agencies": _("Edit agency information and reset invitation links"),
            "can_delete_agencies": _("Remove agency profiles from the system"),
        }

    @classmethod
    def get_default_permissions_for_role(cls, role_name):
        """Return default permissions for system roles"""
        defaults = {
            cls.OWNER: {
                # Centers
                "can_manage_centers": True,
                "can_view_centers": True,
                "can_create_centers": True,
                "can_edit_centers": True,
                "can_delete_centers": True,
                # Branches
                "can_manage_branches": True,
                "can_view_branches": True,
                "can_create_branches": True,
                "can_edit_branches": True,
                "can_delete_branches": True,
                # Staff
                "can_manage_staff": True,
                "can_view_staff": True,
                "can_create_staff": True,
                "can_edit_staff": True,
                "can_delete_staff": True,
                # Orders (all)
                "can_manage_orders": True,
                "can_view_all_orders": True,
                "can_view_own_orders": True,
                "can_create_orders": True,
                "can_edit_orders": True,
                "can_delete_orders": True,
                "can_assign_orders": True,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": True,
                # Financial
                "can_manage_financial": True,
                "can_receive_payments": True,
                "can_view_financial_reports": True,
                "can_apply_discounts": True,
                "can_refund_orders": True,
                # Reports
                "can_manage_reports": True,
                "can_view_reports": True,
                "can_view_analytics": True,
                "can_export_data": True,
                # Products
                "can_manage_products": True,
                "can_view_products": True,
                "can_create_products": True,
                "can_edit_products": True,
                "can_delete_products": True,
                # Customers
                "can_manage_customers": True,
                "can_view_customers": True,
                "can_edit_customers": True,
                "can_delete_customers": True,
                # Marketing & Broadcasts
                "can_manage_marketing": True,
                "can_create_marketing_posts": True,
                "can_send_branch_broadcasts": True,
                "can_send_center_broadcasts": True,
                "can_view_broadcast_stats": True,
                # Branch Settings
                "can_manage_branch_settings": True,
                "can_view_branch_settings": True,
                # Agencies
                "can_manage_agencies": True,
                "can_view_agencies": True,
                "can_create_agencies": True,
                "can_edit_agencies": True,
                "can_delete_agencies": True,
            },
            cls.MANAGER: {
                # Centers (view only)
                "can_manage_centers": False,
                "can_view_centers": True,
                # Branches (view only)
                "can_manage_branches": False,
                "can_view_branches": True,
                # Staff (view only)
                "can_manage_staff": False,
                "can_view_staff": True,
                # Orders
                "can_manage_orders": True,
                "can_view_all_orders": True,
                "can_view_own_orders": True,
                "can_create_orders": True,
                "can_edit_orders": True,
                "can_delete_orders": False,
                "can_assign_orders": True,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": True,
                # Financial
                "can_manage_financial": False,
                "can_receive_payments": True,
                "can_view_financial_reports": True,
                "can_apply_discounts": True,
                "can_refund_orders": False,
                # Reports
                "can_manage_reports": False,
                "can_view_reports": True,
                "can_view_analytics": True,
                "can_export_data": False,
                # Products (view only)
                "can_manage_products": False,
                "can_view_products": True,
                # Customers
                "can_manage_customers": False,
                "can_view_customers": True,
                "can_edit_customers": True,
                # Marketing & Broadcasts
                "can_manage_marketing": False,
                "can_create_marketing_posts": True,
                "can_send_branch_broadcasts": True,
                "can_send_center_broadcasts": False,
                "can_view_broadcast_stats": True,
                # Branch Settings
                "can_manage_branch_settings": True,
                "can_view_branch_settings": True,
                # Agencies
                "can_manage_agencies": False,
                "can_view_agencies": True,
                "can_create_agencies": True,
                "can_edit_agencies": True,
                "can_delete_agencies": False,
            },
            cls.STAFF: {
                # Centers (no access)
                "can_manage_centers": False,
                # Branches (no access)
                "can_manage_branches": False,
                # Staff (no access)
                "can_manage_staff": False,
                # Orders (limited)
                "can_manage_orders": False,
                "can_view_all_orders": False,
                "can_view_own_orders": True,
                "can_create_orders": False,
                "can_edit_orders": False,
                "can_delete_orders": False,
                "can_assign_orders": False,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": False,
                # Financial
                "can_manage_financial": False,
                "can_receive_payments": True,
                "can_view_financial_reports": False,
                "can_apply_discounts": False,
                "can_refund_orders": False,
                # Reports
                "can_manage_reports": False,
                "can_view_reports": False,
                "can_view_analytics": False,
                "can_export_data": False,
                # Products (view only)
                "can_manage_products": False,
                "can_view_products": True,
                # Customers (view only)
                "can_manage_customers": False,
                "can_view_customers": True,
                # Marketing & Broadcasts
                "can_manage_marketing": False,
                "can_create_marketing_posts": False,
                "can_send_branch_broadcasts": False,
                "can_send_center_broadcasts": False,
                "can_view_broadcast_stats": False,
                # Branch Settings
                "can_manage_branch_settings": False,
                "can_view_branch_settings": True,
                # Agencies
                "can_manage_agencies": False,
                "can_view_agencies": False,
                "can_create_agencies": False,
                "can_edit_agencies": False,
                "can_delete_agencies": False,
            },
        }
        return defaults.get(role_name, {})


class AdminUser(models.Model):
    """Extended user profile for staff/managers with role-based access"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="admin_profile",
        verbose_name=_("User"),
    )
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="users", verbose_name=_("Role"),
        null=True, blank=True,
        help_text=_("Role is optional for superusers"),
    )
    center = models.ForeignKey(
        TranslationCenter,
        on_delete=models.CASCADE,
        related_name="staff",
        verbose_name=_("Translation Center"),
        null=True,
        blank=True,
        help_text=_("For owners, this is their primary center"),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
        verbose_name=_("Branch"),
        help_text=_("Specific branch assignment for managers/staff"),
    )
    phone = models.CharField(_("Phone"), max_length=20, blank=True, null=True)
    avatar = models.ImageField(_("Avatar"), upload_to="avatars/", blank=True, null=True)
    is_active = models.BooleanField(_("Active"), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_staff",
        verbose_name=_("Created by"),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Admin User")
        verbose_name_plural = _("Admin Users")
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self):
        role_name = self.role.name if self.role else "Superuser"
        return f"{self.user.get_full_name() or self.user.username} ({role_name})"

    def clean(self):
        """Validate model data"""
        super().clean()
        
        # Owner replacement is handled in save(), not blocked here
        # This allows superusers to assign a new owner, which will unlink the previous one

    def save(self, *args, **kwargs):
        """Override save to run validation and handle owner replacement"""
        self.full_clean()
        
        # Handle owner replacement if assigning owner role to a center
        if self.role and self.role.name == Role.OWNER and self.center:
            # Unlink any existing owner before saving
            AdminUser.handle_owner_replacement(self.center, new_owner_pk=self.pk)
        
        super().save(*args, **kwargs)

    @classmethod
    def can_assign_owner_role(cls, requesting_user, center=None):
        """
        Check if the requesting user can assign the owner role.
        Only superusers can assign the owner role.
        When a new owner is assigned, the previous owner will be unlinked.
        """
        if not requesting_user.is_superuser:
            return False
        
        # Superusers can always assign owner role
        # Previous owner will be automatically unlinked
        return True

    @classmethod
    def validate_role_assignment(cls, requesting_user, target_role, center=None, exclude_pk=None):
        """
        Validate if the requesting user can assign the specified role.
        Returns (is_valid, error_message).
        """
        if target_role.name == Role.OWNER:
            # Only superusers can assign owner role
            if not requesting_user.is_superuser:
                return False, _("Only superusers can create or assign the Owner role.")
            
            # Owner role can be assigned - previous owner will be unlinked
            # No blocking error, just validation that superuser can do it
        
        return True, None

    @classmethod
    def handle_owner_replacement(cls, center, new_owner_pk=None):
        """
        Handle owner replacement for a center.
        Unlinks (removes branch/center association and deactivates) the previous owner.
        Returns the previous owner if one existed.
        """
        query = cls.objects.filter(
            role__name=Role.OWNER,
            center=center,
            is_active=True
        )
        if new_owner_pk:
            query = query.exclude(pk=new_owner_pk)
        
        previous_owner = query.first()
        if previous_owner:
            # Unlink the previous owner from the center/branch
            previous_owner.branch = None
            previous_owner.center = None
            previous_owner.is_active = False
            # Use update to bypass clean validation
            cls.objects.filter(pk=previous_owner.pk).update(
                branch=None,
                center=None,
                is_active=False
            )
        
        return previous_owner

    @property
    def is_owner(self):
        return self.role and self.role.name == Role.OWNER

    @property
    def is_manager(self):
        return self.role and self.role.name == Role.MANAGER

    @property
    def is_staff_role(self):
        return self.role and self.role.name == Role.STAFF

    def has_permission(self, permission):
        """Check if user has a specific permission with alias support"""
        if not self.role:
            return False
        
        # Permission aliases for backward compatibility
        PERMISSION_ALIASES = {
            'can_view_orders': 'can_view_all_orders',  # Alias to actual field
        }
        
        # Check if permission is an alias
        actual_permission = PERMISSION_ALIASES.get(permission, permission)
        
        # Check direct permission
        if getattr(self.role, actual_permission, False):
            return True
        
        # Check master permissions that grant this permission
        # Example: can_manage_orders grants all order permissions
        MASTER_PERMISSION_MAP = {
            'can_view_all_orders': ['can_manage_orders'],
            'can_view_own_orders': ['can_manage_orders'],
            'can_create_orders': ['can_manage_orders'],
            'can_edit_orders': ['can_manage_orders'],
            'can_delete_orders': ['can_manage_orders'],
            'can_assign_orders': ['can_manage_orders'],
            'can_view_customers': ['can_manage_customers'],
            'can_create_customers': ['can_manage_customers'],
            'can_edit_customers': ['can_manage_customers'],
            'can_delete_customers': ['can_manage_customers'],
            'can_view_products': ['can_manage_products'],
            'can_create_products': ['can_manage_products'],
            'can_edit_products': ['can_manage_products'],
            'can_delete_products': ['can_manage_products'],
            'can_view_expenses': ['can_manage_expenses'],
            'can_create_expenses': ['can_manage_expenses'],
            'can_edit_expenses': ['can_manage_expenses'],
            'can_delete_expenses': ['can_manage_expenses'],
            'can_view_staff': ['can_manage_staff'],
            'can_create_staff': ['can_manage_staff'],
            'can_edit_staff': ['can_manage_staff'],
            'can_delete_staff': ['can_manage_staff'],
            'can_view_branches': ['can_manage_branches'],
            'can_create_branches': ['can_manage_branches'],
            'can_edit_branches': ['can_manage_branches'],
            'can_view_financial_reports': ['can_manage_financial'],
            'can_view_branch_settings': ['can_manage_branch_settings'],
            'can_create_marketing_posts': ['can_manage_marketing'],
            'can_send_branch_broadcasts': ['can_manage_marketing'],
            'can_send_center_broadcasts': ['can_manage_marketing'],
            'can_view_broadcast_stats': ['can_manage_marketing'],
        }
        
        # Check if any master permission grants this permission
        master_permissions = MASTER_PERMISSION_MAP.get(actual_permission, [])
        for master_perm in master_permissions:
            if getattr(self.role, master_perm, False):
                return True
        
        return False

    def get_accessible_branches(self):
        """Get branches this user can access based on their role permissions"""
        # Users with order-viewing or management permissions should see branches
        # This is necessary for order lists and other data access
        if self.center and (self.has_permission('can_view_all_orders') or 
                           self.has_permission('can_view_centers') or
                           self.has_permission('can_manage_orders')):
            return Branch.objects.filter(center=self.center, is_active=True)
        # If user has can_view_branches permission, they can see branches in their center
        elif self.center and self.has_permission('can_view_branches'):
            return Branch.objects.filter(center=self.center, is_active=True)
        elif self.branch:
            # Default: user can only access their assigned branch
            return Branch.objects.filter(pk=self.branch.pk, is_active=True)
        return Branch.objects.none()

    def can_access_branch(self, branch):
        """Check if user can access a specific branch"""
        return self.get_accessible_branches().filter(pk=branch.pk).exists()
