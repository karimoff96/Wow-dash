from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


class TranslationCenter(models.Model):
    """Translation center owned by an owner"""

    name = models.CharField(_("Name"), max_length=200)
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

    # Permissions - Organization Management
    can_manage_center = models.BooleanField(_("Can manage center"), default=False)
    can_manage_branches = models.BooleanField(_("Can manage branches"), default=False)
    
    # Permissions - Staff Management
    can_manage_staff = models.BooleanField(_("Can manage staff"), default=False)
    can_view_staff = models.BooleanField(_("Can view staff details"), default=False)
    
    # Permissions - Order Management (Granular)
    can_view_all_orders = models.BooleanField(_("Can view all orders"), default=False)
    can_view_own_orders = models.BooleanField(_("Can view own orders"), default=True)
    can_create_orders = models.BooleanField(_("Can create orders"), default=False)
    can_edit_orders = models.BooleanField(_("Can edit orders"), default=False)
    can_delete_orders = models.BooleanField(_("Can delete orders"), default=False)
    can_assign_orders = models.BooleanField(_("Can assign orders"), default=False)
    can_update_order_status = models.BooleanField(_("Can update order status"), default=False)
    can_complete_orders = models.BooleanField(_("Can complete orders"), default=False)
    can_cancel_orders = models.BooleanField(_("Can cancel orders"), default=False)
    can_manage_orders = models.BooleanField(_("Can manage orders (full access)"), default=False, 
        help_text=_("Full order management - overrides other order permissions"))
    
    # Permissions - Financial
    can_receive_payments = models.BooleanField(_("Can receive payments"), default=False)
    can_view_financial_reports = models.BooleanField(_("Can view financial reports"), default=False)
    can_apply_discounts = models.BooleanField(_("Can apply discounts"), default=False)
    can_refund_orders = models.BooleanField(_("Can refund orders"), default=False)
    
    # Permissions - Reports & Analytics
    can_view_reports = models.BooleanField(_("Can view reports"), default=False)
    can_view_analytics = models.BooleanField(_("Can view analytics"), default=False)
    can_export_data = models.BooleanField(_("Can export data"), default=False)
    
    # Permissions - Products & Customers
    can_manage_products = models.BooleanField(_("Can manage products"), default=False)
    can_manage_customers = models.BooleanField(_("Can manage customers"), default=False)
    can_view_customer_details = models.BooleanField(_("Can view customer details"), default=False)
    
    # Permissions - Marketing & Broadcasts
    can_create_marketing_posts = models.BooleanField(_("Can create marketing posts"), default=False)
    can_send_branch_broadcasts = models.BooleanField(_("Can send branch broadcasts"), default=False)
    can_send_center_broadcasts = models.BooleanField(_("Can send center-wide broadcasts"), default=False)
    can_view_broadcast_stats = models.BooleanField(_("Can view broadcast statistics"), default=False)

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

    @classmethod
    def get_all_permissions(cls):
        """Return list of all permission field names grouped by category"""
        return [
            # Organization Management
            "can_manage_center",
            "can_manage_branches",
            # Staff Management
            "can_manage_staff",
            "can_view_staff",
            # Order Management
            "can_view_all_orders",
            "can_view_own_orders",
            "can_create_orders",
            "can_edit_orders",
            "can_delete_orders",
            "can_assign_orders",
            "can_update_order_status",
            "can_complete_orders",
            "can_cancel_orders",
            "can_manage_orders",
            # Financial
            "can_receive_payments",
            "can_view_financial_reports",
            "can_apply_discounts",
            "can_refund_orders",
            # Reports & Analytics
            "can_view_reports",
            "can_view_analytics",
            "can_export_data",
            # Products & Customers
            "can_manage_products",
            "can_manage_customers",
            "can_view_customer_details",
            # Marketing & Broadcasts
            "can_create_marketing_posts",
            "can_send_branch_broadcasts",
            "can_send_center_broadcasts",
            "can_view_broadcast_stats",
        ]

    @classmethod
    def get_permission_categories(cls):
        """Return permissions grouped by category for UI"""
        return {
            "organization": {
                "title": _("Organization Management"),
                "icon": "fa-building",
                "color": "primary",
                "permissions": ["can_manage_center", "can_manage_branches"],
            },
            "staff": {
                "title": _("Staff Management"),
                "icon": "fa-users",
                "color": "info",
                "permissions": ["can_manage_staff", "can_view_staff"],
            },
            "orders": {
                "title": _("Order Management"),
                "icon": "fa-file-lines",
                "color": "success",
                "permissions": [
                    "can_view_all_orders",
                    "can_view_own_orders",
                    "can_create_orders",
                    "can_edit_orders",
                    "can_delete_orders",
                    "can_assign_orders",
                    "can_update_order_status",
                    "can_complete_orders",
                    "can_cancel_orders",
                    "can_manage_orders",
                ],
            },
            "financial": {
                "title": _("Financial"),
                "icon": "fa-money-bill-wave",
                "color": "warning",
                "permissions": [
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
                "permissions": ["can_view_reports", "can_view_analytics", "can_export_data"],
            },
            "products": {
                "title": _("Products & Customers"),
                "icon": "fa-box",
                "color": "danger",
                "permissions": ["can_manage_products", "can_manage_customers", "can_view_customer_details"],
            },
            "marketing": {
                "title": _("Marketing & Broadcasts"),
                "icon": "fa-bullhorn",
                "color": "secondary",
                "permissions": [
                    "can_create_marketing_posts",
                    "can_send_branch_broadcasts",
                    "can_send_center_broadcasts",
                    "can_view_broadcast_stats",
                ],
            },
        }

    @classmethod
    def get_permission_labels(cls):
        """Return human-readable labels for all permissions"""
        return {
            # Organization Management
            "can_manage_center": _("Manage Translation Centers"),
            "can_manage_branches": _("Manage Branches"),
            # Staff Management
            "can_manage_staff": _("Manage Staff Members"),
            "can_view_staff": _("View Staff Details (Read-Only)"),
            # Order Management
            "can_view_all_orders": _("View All Orders"),
            "can_view_own_orders": _("View Own Orders"),
            "can_create_orders": _("Create New Orders"),
            "can_edit_orders": _("Edit Orders"),
            "can_delete_orders": _("Delete Orders"),
            "can_assign_orders": _("Assign Orders to Staff"),
            "can_update_order_status": _("Update Order Status"),
            "can_complete_orders": _("Complete Orders"),
            "can_cancel_orders": _("Cancel Orders"),
            "can_manage_orders": _("Full Order Management"),
            # Financial
            "can_receive_payments": _("Receive Payments"),
            "can_view_financial_reports": _("View Financial Reports"),
            "can_apply_discounts": _("Apply Discounts"),
            "can_refund_orders": _("Refund Orders"),
            # Reports & Analytics
            "can_view_reports": _("View Reports"),
            "can_view_analytics": _("View Analytics Dashboard"),
            "can_export_data": _("Export Data"),
            # Products & Customers
            "can_manage_products": _("Manage Products & Services"),
            "can_manage_customers": _("Manage Customers"),
            "can_view_customer_details": _("View Customer Details"),
            # Marketing & Broadcasts
            "can_create_marketing_posts": _("Create Marketing Posts"),
            "can_send_branch_broadcasts": _("Send Branch Broadcasts"),
            "can_send_center_broadcasts": _("Send Center-wide Broadcasts"),
            "can_view_broadcast_stats": _("View Broadcast Statistics"),
        }
    
    @classmethod
    def get_permission_descriptions(cls):
        """Return detailed descriptions for all permissions"""
        return {
            # Organization Management
            "can_manage_center": _("Create, edit, and delete translation centers"),
            "can_manage_branches": _("Create, edit, and delete branches within centers"),
            # Staff Management
            "can_manage_staff": _("Add, edit, remove staff members and change their roles"),
            "can_view_staff": _("View staff profiles and details without editing"),
            # Order Management
            "can_view_all_orders": _("View all orders in the center/branch, not just assigned ones"),
            "can_view_own_orders": _("View orders assigned to this user"),
            "can_create_orders": _("Create new translation orders"),
            "can_edit_orders": _("Modify existing order details, files, and settings"),
            "can_delete_orders": _("Permanently remove orders from the system"),
            "can_assign_orders": _("Assign orders to other staff members"),
            "can_update_order_status": _("Change order status (pending, in progress, etc.)"),
            "can_complete_orders": _("Mark orders as completed/delivered"),
            "can_cancel_orders": _("Cancel active orders"),
            "can_manage_orders": _("Full control over all order operations - overrides individual permissions"),
            # Financial
            "can_receive_payments": _("Accept and record customer payments"),
            "can_view_financial_reports": _("Access financial reports and revenue data"),
            "can_apply_discounts": _("Apply discounts to orders"),
            "can_refund_orders": _("Process refunds for completed or cancelled orders"),
            # Reports & Analytics
            "can_view_reports": _("Access performance and activity reports"),
            "can_view_analytics": _("View analytics dashboard with charts and metrics"),
            "can_export_data": _("Export data to Excel, PDF, or other formats"),
            # Products & Customers
            "can_manage_products": _("Add, edit, and remove services and products"),
            "can_manage_customers": _("Add, edit customer records and contact information"),
            "can_view_customer_details": _("View customer information and history"),
            # Marketing & Broadcasts
            "can_create_marketing_posts": _("Create and edit marketing posts and announcements"),
            "can_send_branch_broadcasts": _("Send broadcast messages to all customers in their branch"),
            "can_send_center_broadcasts": _("Send broadcast messages to all customers across the entire center"),
            "can_view_broadcast_stats": _("View broadcast delivery statistics and analytics"),
        }

    @classmethod
    def get_default_permissions_for_role(cls, role_name):
        """Return default permissions for system roles"""
        defaults = {
            cls.OWNER: {
                # Organization
                "can_manage_center": True,
                "can_manage_branches": True,
                # Staff
                "can_manage_staff": True,
                "can_view_staff": True,
                # Orders (all)
                "can_view_all_orders": True,
                "can_view_own_orders": True,
                "can_create_orders": True,
                "can_edit_orders": True,
                "can_delete_orders": True,
                "can_assign_orders": True,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": True,
                "can_manage_orders": True,
                # Financial
                "can_receive_payments": True,
                "can_view_financial_reports": True,
                "can_apply_discounts": True,
                "can_refund_orders": True,
                # Reports
                "can_view_reports": True,
                "can_view_analytics": True,
                "can_export_data": True,
                # Products & Customers
                "can_manage_products": True,
                "can_manage_customers": True,
                "can_view_customer_details": True,
                # Marketing & Broadcasts
                "can_create_marketing_posts": True,
                "can_send_branch_broadcasts": True,
                "can_send_center_broadcasts": True,
                "can_view_broadcast_stats": True,
            },
            cls.MANAGER: {
                # Organization
                "can_manage_center": False,
                "can_manage_branches": False,
                # Staff
                "can_manage_staff": False,
                "can_view_staff": True,
                # Orders
                "can_view_all_orders": True,
                "can_view_own_orders": True,
                "can_create_orders": True,
                "can_edit_orders": True,
                "can_delete_orders": False,
                "can_assign_orders": True,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": True,
                "can_manage_orders": True,
                # Financial
                "can_receive_payments": True,
                "can_view_financial_reports": True,
                "can_apply_discounts": True,
                "can_refund_orders": False,
                # Reports
                "can_view_reports": True,
                "can_view_analytics": True,
                "can_export_data": False,
                # Products & Customers
                "can_manage_products": False,
                "can_manage_customers": True,
                "can_view_customer_details": True,
                # Marketing & Broadcasts
                "can_create_marketing_posts": True,
                "can_send_branch_broadcasts": True,
                "can_send_center_broadcasts": False,
                "can_view_broadcast_stats": True,
            },
            cls.STAFF: {
                # Organization
                "can_manage_center": False,
                "can_manage_branches": False,
                # Staff
                "can_manage_staff": False,
                "can_view_staff": False,
                # Orders (limited)
                "can_view_all_orders": False,
                "can_view_own_orders": True,
                "can_create_orders": False,
                "can_edit_orders": False,
                "can_delete_orders": False,
                "can_assign_orders": False,
                "can_update_order_status": True,
                "can_complete_orders": True,
                "can_cancel_orders": False,
                "can_manage_orders": False,
                # Financial
                "can_receive_payments": True,
                "can_view_financial_reports": False,
                "can_apply_discounts": False,
                "can_refund_orders": False,
                # Reports
                "can_view_reports": False,
                "can_view_analytics": False,
                "can_export_data": False,
                # Products & Customers
                "can_manage_products": False,
                "can_manage_customers": False,
                "can_view_customer_details": True,
                # Marketing & Broadcasts
                "can_create_marketing_posts": False,
                "can_send_branch_broadcasts": False,
                "can_send_center_broadcasts": False,
                "can_view_broadcast_stats": False,
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
        """Validate model data - enforce single owner per center"""
        super().clean()
        
        # Check for single owner per center
        if self.role and self.role.name == Role.OWNER and self.center:
            existing_owner = AdminUser.objects.filter(
                role__name=Role.OWNER,
                center=self.center,
                is_active=True
            ).exclude(pk=self.pk).first()
            
            if existing_owner:
                raise ValidationError({
                    'role': _(
                        f'This center already has an owner: {existing_owner.user.get_full_name()}. '
                        'Each center can only have one owner.'
                    )
                })

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def can_assign_owner_role(cls, requesting_user, center=None):
        """
        Check if the requesting user can assign the owner role.
        Only superusers can assign the owner role.
        """
        if not requesting_user.is_superuser:
            return False
        
        # If center specified, check if it already has an active owner
        if center:
            existing_owner = cls.objects.filter(
                role__name=Role.OWNER,
                center=center,
                is_active=True
            ).exists()
            return not existing_owner
        
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
            
            # Check if center already has an owner
            if center:
                query = cls.objects.filter(
                    role__name=Role.OWNER,
                    center=center,
                    is_active=True
                )
                if exclude_pk:
                    query = query.exclude(pk=exclude_pk)
                
                if query.exists():
                    existing = query.first()
                    return False, _(
                        f"This center already has an owner: {existing.user.get_full_name()}. "
                        "Each center can only have one owner."
                    )
        
        return True, None

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
        """Check if user has a specific permission"""
        if not self.role:
            return False
        return getattr(self.role, permission, False)

    def get_accessible_branches(self):
        """Get branches this user can access"""
        if self.is_owner:
            # Owners can access all branches of their centers
            return Branch.objects.filter(center__owner=self.user)
        elif self.is_manager:
            # Managers can access their assigned branch
            if self.branch:
                return Branch.objects.filter(pk=self.branch.pk)
            return Branch.objects.none()
        else:
            # Staff can only access their branch
            if self.branch:
                return Branch.objects.filter(pk=self.branch.pk)
            return Branch.objects.none()

    def can_access_branch(self, branch):
        """Check if user can access a specific branch"""
        return self.get_accessible_branches().filter(pk=branch.pk).exists()
