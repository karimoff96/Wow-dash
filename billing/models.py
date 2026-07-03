from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext
from django.core.validators import MinValueValidator
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal


class Feature(models.Model):
    """Individual features that can be included in tariffs (legacy - being replaced by boolean fields)"""
    code = models.CharField(max_length=50, unique=True, verbose_name=_("Feature Code"))
    name = models.CharField(max_length=200, verbose_name=_("Feature Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    category = models.CharField(max_length=50, blank=True, verbose_name=_("Category"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Feature")
        verbose_name_plural = _("Features")
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Tariff(models.Model):
    """Tariff plan template/definition"""
    title = models.CharField(max_length=200, verbose_name=_("Tariff Title"))
    slug = models.SlugField(unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    is_featured = models.BooleanField(default=False, verbose_name=_("Featured"))
    show_prices = models.BooleanField(default=True, verbose_name=_("Show Prices"), help_text=_("Display pricing options publicly"))
    is_special = models.BooleanField(default=False, verbose_name=_("Private Tariff"), help_text=_("Hide from public landing page"))
    is_trial = models.BooleanField(default=False, verbose_name=_("Is Trial"), help_text=_("Free trial tariff"))
    trial_days = models.IntegerField(null=True, blank=True, verbose_name=_("Trial Days"), help_text=_("Duration of trial period in days (only for trial tariffs)"))
    display_order = models.IntegerField(default=0, verbose_name=_("Display Order"))
    
    # Limits
    max_branches = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name=_("Max Branches"),
        help_text=_("Leave empty for unlimited")
    )
    max_staff = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name=_("Max Staff"),
        help_text=_("Leave empty for unlimited")
    )
    max_monthly_orders = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name=_("Max Monthly Orders"),
        help_text=_("Leave empty for unlimited")
    )
    max_monthly_broadcasts = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Max Monthly Broadcasts"),
        help_text=_("Maximum marketing broadcasts per month. Leave empty for unlimited.")
    )
    
    # ============ FEATURE FLAGS (32 Features) ============
    
    # Order Management Features (5)
    feature_orders_basic = models.BooleanField(
        default=False, 
        verbose_name=_("Basic Order Management"),
        help_text=_("Create, view, and track customer orders")
    )
    feature_orders_advanced = models.BooleanField(
        default=False,
        verbose_name=_("Advanced Order Management"),
        help_text=_("Bulk operations, advanced filters, export")
    )
    feature_order_assignment = models.BooleanField(
        default=False,
        verbose_name=_("Order Assignment"),
        help_text=_("Assign orders to specific staff members")
    )
    feature_bulk_payments = models.BooleanField(
        default=False,
        verbose_name=_("Bulk Payment Processing"),
        help_text=_("Process payments across multiple orders")
    )
    feature_extra_fees = models.BooleanField(
        default=False,
        verbose_name=_("Order Extra Fees"),
        help_text=_("Add manual surcharges or price corrections to existing orders")
    )
    
    # Analytics & Reports Features (7)
    feature_analytics_basic = models.BooleanField(
        default=False,
        verbose_name=_("Basic Analytics"),
        help_text=_("View order counts and basic statistics")
    )
    feature_analytics_advanced = models.BooleanField(
        default=False,
        verbose_name=_("Advanced Analytics"),
        help_text=_("Detailed reports, financial analytics, trends")
    )
    feature_financial_reports = models.BooleanField(
        default=False,
        verbose_name=_("Financial Reports"),
        help_text=_("Revenue, profit, expense analysis")
    )
    feature_staff_performance = models.BooleanField(
        default=False,
        verbose_name=_("Staff Performance Reports"),
        help_text=_("Track individual staff productivity")
    )
    feature_custom_reports = models.BooleanField(
        default=False,
        verbose_name=_("Custom Report Builder"),
        help_text=_("Create custom reports with filters")
    )
    feature_export_reports = models.BooleanField(
        default=False,
        verbose_name=_("Export Reports"),
        help_text=_("Export to Excel, PDF, CSV formats")
    )
    feature_debt_tracking = models.BooleanField(
        default=False,
        verbose_name=_("Debt & Receivables Tracking"),
        help_text=_("Unit economy analytics: outstanding balances, top debtors, collection rates")
    )
    
    # Integration Features (4)
    feature_api_access = models.BooleanField(
        default=False,
        verbose_name=_("REST API Access"),
        help_text=_("REST API for custom integrations (on request)")
    )
    feature_webhooks = models.BooleanField(
        default=False,
        verbose_name=_("Telegram Webhook Management"),
        help_text=_("Configure and manage Telegram bot webhooks")
    )
    feature_integrations = models.BooleanField(
        default=False,
        verbose_name=_("Third-Party Integrations"),
        help_text=_("Custom integrations with external services (on request)")
    )
    feature_telegram_bot = models.BooleanField(
        default=False,
        verbose_name=_("Telegram Bot Integration"),
        help_text=_("Customer-facing bot for order placement")
    )
    
    # Marketing & Communications Features (2)
    feature_marketing_basic = models.BooleanField(
        default=False,
        verbose_name=_("Marketing Campaign Tools"),
        help_text=_("Create and manage marketing posts")
    )
    feature_broadcast_messages = models.BooleanField(
        default=False,
        verbose_name=_("Mass Broadcast Messaging"),
        help_text=_("Send targeted broadcasts to customers")
    )
    
    # Organization & Staff Features (3)
    feature_multi_branch = models.BooleanField(
        default=False,
        verbose_name=_("Multiple Branches"),
        help_text=_("Manage multiple branch locations")
    )
    feature_custom_roles = models.BooleanField(
        default=False,
        verbose_name=_("Custom Roles & Permissions"),
        help_text=_("Create custom staff roles with RBAC")
    )
    feature_branch_settings = models.BooleanField(
        default=False,
        verbose_name=_("Branch Settings"),
        help_text=_("Customize settings per branch")
    )
    feature_agency_management = models.BooleanField(
        default=False,
        verbose_name=_("Agency Management"),
        help_text=_("Create and manage B2B agency partners with agency-specific pricing")
    )
    
    # Storage & Archive Features (1)
    feature_archive_access = models.BooleanField(
        default=False,
        verbose_name=_("Historical File Archives"),
        help_text=_("Access compressed archives of completed orders")
    )
    
    # Financial Management Features (4)
    feature_payment_management = models.BooleanField(
        default=False,
        verbose_name=_("Payment Tracking & Recording"),
        help_text=_("Manual payment recording and receipt verification")
    )
    feature_expense_tracking = models.BooleanField(
        default=False,
        verbose_name=_("Expense Tracking"),
        help_text=_("Track business expenses by branch")
    )
    feature_invoicing = models.BooleanField(
        default=False,
        verbose_name=_("Invoicing"),
        help_text=_("Generate and manage invoices for customers")
    )
    feature_general_expenses = models.BooleanField(
        default=False,
        verbose_name=_("General (Operating) Expenses"),
        help_text=_("Track operational costs: rent, salaries, stationery, repairs — not tied to individual orders")
    )
    
    # Advanced Features (1)
    feature_audit_logs = models.BooleanField(
        default=False,
        verbose_name=_("Comprehensive Audit Logs"),
        help_text=_("Track all system actions and changes")
    )
    
    # Services Management Features (4)
    feature_products_basic = models.BooleanField(
        default=False,
        verbose_name=_("Basic Product Management"),
        help_text=_("Manage services and basic pricing")
    )
    feature_products_advanced = models.BooleanField(
        default=False,
        verbose_name=_("Advanced Product Management"),
        help_text=_("Complex pricing, categories, customization")
    )
    feature_language_pricing = models.BooleanField(
        default=False,
        verbose_name=_("Language-Specific Pricing"),
        help_text=_("Different pricing per language combination")
    )
    feature_dynamic_pricing = models.BooleanField(
        default=False,
        verbose_name=_("Dynamic Pricing"),
        help_text=_("Per-page pricing calculations")
    )
    
    # Legacy M2M relationship (will be deprecated)
    features = models.ManyToManyField(Feature, blank=True, verbose_name=_("Features (Legacy)"))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Tariff")
        verbose_name_plural = _("Tariffs")
        ordering = ['display_order', 'title']
    
    def __str__(self):
        return self.title
    
    def has_feature(self, feature_name):
        """
        Check if tariff includes a specific feature by name (without 'feature_' prefix)
        
        Example:
            tariff.has_feature('marketing_basic')  # Checks feature_marketing_basic
            tariff.has_feature('api_access')       # Checks feature_api_access
        """
        feature_field = f"feature_{feature_name}"
        return getattr(self, feature_field, False)
    
    def get_enabled_features(self):
        """
        Get list of all enabled feature names (without 'feature_' prefix)
        
        Returns:
            list: ['orders_basic', 'analytics_basic', 'telegram_bot', ...]
        """
        enabled = []
        for field in self._meta.get_fields():
            if field.name.startswith('feature_') and getattr(self, field.name, False):
                # Remove 'feature_' prefix
                feature_name = field.name[8:]
                enabled.append(feature_name)
        return enabled
    
    def get_features_by_category(self, category=None):
        """
        Get features organized by category with display names
        
        Args:
            category: Optional category name (orders, analytics, integration, etc.)
        
        Returns:
            dict: {display_name: enabled_status} or nested dict if no category specified
        """
        categories = {
            'orders': [
                'orders_basic', 'orders_advanced', 'order_assignment',
                'bulk_payments', 'extra_fees'
            ],
            'analytics': [
                'analytics_basic', 'analytics_advanced', 'financial_reports',
                'staff_performance', 'custom_reports', 'export_reports', 'debt_tracking'
            ],
            'integration': [
                'webhooks', 'api_access', 'integrations', 'telegram_bot'
            ],
            'marketing': ['marketing_basic', 'broadcast_messages'],
            'organization': [
                'multi_branch', 'custom_roles', 'branch_settings', 'agency_management'
            ],
            'storage': ['archive_access'],
            'financial': [
                'payment_management', 'expense_tracking', 'invoicing', 'general_expenses'
            ],
            'advanced': ['audit_logs'],
            'services': [
                'products_basic', 'products_advanced', 'language_pricing', 'dynamic_pricing'
            ],
        }
        
        if category:
            # Return specific category features with display names
            feature_slugs = categories.get(category, [])
            return {self.get_feature_display_name(slug): self.has_feature(slug) for slug in feature_slugs}
        else:
            # Return all categories with display names
            result = {}
            for cat_name, feature_slugs in categories.items():
                result[cat_name] = {self.get_feature_display_name(slug): self.has_feature(slug) for slug in feature_slugs}
            return result
    
    def get_feature_count(self):
        """Get total number of enabled features"""
        return len(self.get_enabled_features())

    def get_total_feature_count(self):
        """Get total number of available feature flags on tariff."""
        return len([field for field in self._meta.get_fields() if field.name.startswith('feature_')])
    
    def get_feature_display_name(self, feature_slug):
        """
        Convert feature slug to display name - matches exactly with feature field names
        
        Args:
            feature_slug: Feature name without 'feature_' prefix (e.g., 'orders_basic')
            
        Returns:
            str: Human-readable translated feature name
        """
        feature_names = {
            # Order Management Features (5)
            'orders_basic': gettext('Basic Order Management'),
            'orders_advanced': gettext('Advanced Order Management'),
            'order_assignment': gettext('Order Assignment'),
            'bulk_payments': gettext('Bulk Payment Processing'),
            'extra_fees': gettext('Order Extra Fees'),
            
            # Analytics & Reports Features (7)
            'analytics_basic': gettext('Basic Analytics'),
            'analytics_advanced': gettext('Advanced Analytics'),
            'financial_reports': gettext('Financial Reports'),
            'staff_performance': gettext('Staff Performance Reports'),
            'custom_reports': gettext('Custom Report Builder'),
            'export_reports': gettext('Export Reports'),
            'debt_tracking': gettext('Debt & Receivables Tracking'),
            
            # Integration Features (4)
            'api_access': gettext('REST API Access'),
            'webhooks': gettext('Telegram Webhook Management'),
            'integrations': gettext('Third-Party Integrations'),
            'telegram_bot': gettext('Telegram Bot Integration'),
            
            # Marketing & Communications Features (2)
            'marketing_basic': gettext('Marketing Campaign Tools'),
            'broadcast_messages': gettext('Mass Broadcast Messaging'),
            
            # Organization & Staff Features
            'multi_branch': gettext('Multiple Branches'),
            'custom_roles': gettext('Custom Roles & Permissions'),
            'branch_settings': gettext('Branch Settings'),
            'agency_management': gettext('Agency Management'),
            
            # Storage & Archive Features
            'archive_access': gettext('Historical File Archives'),
            
            # Financial Management Features
            'payment_management': gettext('Payment Tracking & Recording'),
            'expense_tracking': gettext('Expense Tracking'),
            'invoicing': gettext('Invoicing'),
            'general_expenses': gettext('General (Operating) Expenses'),

            # Advanced Features
            'audit_logs': gettext('Comprehensive Audit Logs'),

            # Services Management Features (4)
            'products_basic': gettext('Basic Product Management'),
            'products_advanced': gettext('Advanced Product Management'),
            'language_pricing': gettext('Language-Specific Pricing'),
            'dynamic_pricing': gettext('Dynamic Pricing'),
        }
        return feature_names.get(feature_slug, feature_slug.replace('_', ' ').title())
    
    def get_enabled_features_with_names(self):
        """
        Get list of enabled features with their display names
        
        Returns:
            list: [('orders_basic', 'Basic Orders'), ('analytics_basic', 'Basic Analytics'), ...]
        """
        features = []
        for feature_slug in self.get_enabled_features():
            display_name = self.get_feature_display_name(feature_slug)
            features.append((feature_slug, display_name))
        return features
    
    def get_pricing_options(self):
        """Get all pricing options for this tariff"""
        return self.pricing.filter(is_active=True).order_by('duration_months')


class TariffPricing(models.Model):
    """Pricing for different subscription periods"""
    DURATION_CHOICES = [
        (1, _("1 Month")),
        (3, _("3 Months")),
        (6, _("6 Months")),
        (12, _("1 Year")),
    ]
    
    CURRENCY_CHOICES = [
        ('UZS', _("Uzbek Sum")),
        ('USD', _("US Dollar")),
        ('RUB', _("Russian Ruble")),
    ]
    
    tariff = models.ForeignKey(
        Tariff, 
        on_delete=models.CASCADE, 
        related_name='pricing',
        verbose_name=_("Tariff")
    )
    duration_months = models.IntegerField(
        choices=DURATION_CHOICES,
        verbose_name=_("Duration (Months)")
    )
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_("Price")
    )
    currency = models.CharField(
        max_length=3, 
        choices=CURRENCY_CHOICES, 
        default='UZS',
        verbose_name=_("Currency")
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Discount %"),
        help_text=_("Discount compared to monthly pricing")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Tariff Pricing")
        verbose_name_plural = _("Tariff Pricings")
        unique_together = ['tariff', 'duration_months', 'currency']
        ordering = ['tariff', 'duration_months']
    
    def __str__(self):
        return f"{self.tariff.title} - {self.duration_months} month(s) - {self.price} {self.currency}"
    
    def get_monthly_price(self):
        """Calculate effective monthly price"""
        return self.price / self.duration_months
    
    def get_savings(self):
        """Calculate savings compared to monthly plan"""
        if self.duration_months == 1:
            return 0
        
        monthly_pricing = TariffPricing.objects.filter(
            tariff=self.tariff,
            duration_months=1,
            currency=self.currency,
            is_active=True
        ).first()
        
        if monthly_pricing:
            total_monthly_cost = monthly_pricing.price * self.duration_months
            return total_monthly_cost - self.price
        return 0


class Subscription(models.Model):
    """Organization's subscription to a tariff"""
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    STATUS_PENDING = 'pending'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, _("Active")),
        (STATUS_EXPIRED, _("Expired")),
        (STATUS_CANCELLED, _("Cancelled")),
        (STATUS_PENDING, _("Pending Payment")),
    ]
    
    organization = models.OneToOneField(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_("Organization")
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_("Tariff")
    )
    pricing = models.ForeignKey(
        TariffPricing,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        null=True,
        blank=True,
        verbose_name=_("Pricing Plan")
    )
    
    # Subscription Period
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))
    
    # Trial Period
    is_trial = models.BooleanField(default=False, verbose_name=_("Is Trial Subscription"))
    trial_end_date = models.DateField(null=True, blank=True, verbose_name=_("Trial End Date"))
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name=_("Status")
    )
    auto_renew = models.BooleanField(default=False, verbose_name=_("Auto Renew"))
    
    # Payment tracking
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Amount Paid")
    )
    payment_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Payment Date"))
    payment_method = models.CharField(max_length=50, blank=True, verbose_name=_("Payment Method"))
    transaction_id = models.CharField(max_length=200, blank=True, verbose_name=_("Transaction ID"))
    
    # Metadata
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_subscriptions',
        verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['end_date', 'status']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.tariff.title} ({self.start_date} - {self.end_date})"
    
    def save(self, *args, **kwargs):
        # Handle trial subscription
        if self.tariff.is_trial and not self.trial_end_date:
            trial_days = self.tariff.trial_days or 10  # Default to 10 days
            self.trial_end_date = self.start_date + timedelta(days=trial_days)
            self.is_trial = True
            self.end_date = self.trial_end_date
            self.status = self.STATUS_ACTIVE  # Trial is automatically active
            self.amount_paid = Decimal('0.00')  # Free trial
        
        # Always recalculate end_date from pricing to prevent manual-entry drift
        elif self.start_date and self.pricing:
            self.end_date = self.start_date + relativedelta(months=self.pricing.duration_months)
        
        # Auto-update status based on dates
        if self.status != self.STATUS_CANCELLED:
            today = date.today()
            if self.end_date < today:
                self.status = self.STATUS_EXPIRED
            elif self.start_date <= today <= self.end_date:
                if self.status == self.STATUS_PENDING and self.payment_date:
                    self.status = self.STATUS_ACTIVE
        
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if subscription is currently active"""
        today = date.today()
        return (
            self.status == self.STATUS_ACTIVE and
            self.start_date <= today <= self.end_date
        )
    
    def days_remaining(self):
        """Calculate days remaining in subscription"""
        if not self.is_active():
            return 0
        return (self.end_date - date.today()).days
    
    def is_trial_active(self):
        """Check if trial period is currently active"""
        if not self.is_trial:
            return False
        today = date.today()
        return self.trial_end_date and self.start_date <= today <= self.trial_end_date
    
    def trial_days_remaining(self):
        """Calculate days remaining in trial period"""
        if not self.is_trial_active():
            return 0
        return (self.trial_end_date - date.today()).days
    
    def days_since_expiration(self):
        """Calculate days passed since subscription expired"""
        if self.status != self.STATUS_EXPIRED:
            return 0
        if not self.end_date:
            return 0
        days_passed = (date.today() - self.end_date).days
        return days_passed if days_passed > 0 else 0
    
    def convert_trial_to_paid(self, tariff, pricing):
        """Convert a trial subscription to a paid subscription"""
        if not self.is_trial:
            return False
        
        self.is_trial = False
        self.tariff = tariff
        self.pricing = pricing
        self.start_date = date.today()
        self.end_date = self.start_date + relativedelta(months=pricing.duration_months)
        self.trial_end_date = None
        self.status = self.STATUS_PENDING
        self.save()
        
        # Create history entry
        SubscriptionHistory.objects.create(
            subscription=self,
            action='trial_converted',
            description=f'Trial converted to {tariff.title} - {pricing.duration_months} month(s)',
            performed_by=None
        )
        return True
    
    def has_feature(self, feature_code):
        """
        Check if subscription includes a specific feature.
        This is used for feature-based access control.
        
        Args:
            feature_code: String code of the feature (e.g., 'advanced_analytics', 'telegram_bot')
        
        Returns:
            Boolean indicating if subscription has access to this feature
        """
        if not self.is_active():
            return False
        
        return self.tariff.has_feature(feature_code)
    
    def get_features(self):
        """
        Get all active feature names for this subscription
        
        Returns:
            list: List of enabled feature names (without 'feature_' prefix)
        """
        if not self.is_active():
            return []
        
        return self.tariff.get_enabled_features()
    
    def get_features_by_category(self, category=None):
        """Get features organized by category"""
        if not self.is_active():
            return {} if category else {cat: {} for cat in ['orders', 'analytics', 'integration', 'marketing', 'organization', 'storage', 'financial', 'advanced', 'services']}
        
        return self.tariff.get_features_by_category(category)
    
    def can_add_branch(self):
        """Check if organization can add more branches"""
        if not self.is_active():
            return False
        
        limit = self.tariff.max_branches
        if limit is None:  # Unlimited
            return True
        
        current_count = self.organization.branches.count()
        return current_count < limit
    
    def can_add_staff(self):
        """Check if organization can add more staff"""
        if not self.is_active():
            return False
        
        limit = self.tariff.max_staff
        if limit is None:
            return True
        
        current_count = self.organization.get_staff_count()
        return current_count < limit
    
    def can_create_order(self):
        """Check if organization can create more orders this month"""
        if not self.is_active():
            return False
        
        limit = self.tariff.max_monthly_orders
        if limit is None:
            return True
        
        current_count = self.organization.get_current_month_orders_count()
        return current_count < limit

    def can_send_broadcast(self):
        """Check if organization can send more marketing broadcasts this month"""
        if not self.is_active():
            return False

        limit = self.tariff.max_monthly_broadcasts
        if limit is None:
            return True

        current_count = self.organization.get_current_month_broadcasts_count()
        return current_count < limit

    def get_broadcasts_limit_info(self):
        """Return (used, limit) tuple for broadcasts this month"""
        limit = self.tariff.max_monthly_broadcasts
        used = self.organization.get_current_month_broadcasts_count()
        return used, limit

    def get_usage_percentage(self, resource_type):
        """Get usage percentage for a specific resource (branches, staff, orders, broadcasts)."""
        if resource_type == 'branches':
            current = self.organization.branches.count()
            limit = self.tariff.max_branches
        elif resource_type == 'staff':
            current = self.organization.get_staff_count()
            limit = self.tariff.max_staff
        elif resource_type == 'orders':
            current = self.organization.get_current_month_orders_count()
            limit = self.tariff.max_monthly_orders
        elif resource_type == 'broadcasts':
            current = self.organization.get_current_month_broadcasts_count()
            limit = self.tariff.max_monthly_broadcasts
        else:
            return 0

        if limit is None or limit == 0:
            return 0

        return int((current / limit) * 100)

    def renew(self, new_pricing=None):
        """Create a new subscription for renewal"""
        if new_pricing is None:
            new_pricing = self.pricing
        
        new_subscription = Subscription.objects.create(
            organization=self.organization,
            tariff=new_pricing.tariff,
            pricing=new_pricing,
            start_date=self.end_date + timedelta(days=1),
            status=self.STATUS_PENDING,
            auto_renew=False,
            payment_method='',
            transaction_id='',
        )
        
        return new_subscription


class UsageTracking(models.Model):
    """Track monthly usage statistics"""
    organization = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='usage_tracking',
        verbose_name=_("Organization")
    )
    year = models.IntegerField(verbose_name=_("Year"))
    month = models.IntegerField(verbose_name=_("Month"))
    
    # Usage counters
    orders_created = models.IntegerField(default=0, verbose_name=_("Orders Created"))
    branches_count = models.IntegerField(default=0, verbose_name=_("Branches Count"))
    staff_count = models.IntegerField(default=0, verbose_name=_("Staff Count"))
    marketing_posts_sent = models.IntegerField(default=0, verbose_name=_("Marketing Posts Sent"))
    
    # Additional metrics
    total_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Total Revenue")
    )
    bot_orders = models.IntegerField(default=0, verbose_name=_("Bot Orders"))
    manual_orders = models.IntegerField(default=0, verbose_name=_("Manual Orders"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Usage Tracking")
        verbose_name_plural = _("Usage Tracking")
        unique_together = ['organization', 'year', 'month']
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['organization', 'year', 'month']),
        ]
    
    def __str__(self):
        return f"{self.organization.name} - {self.year}/{self.month}"
    
    @classmethod
    def get_or_create_current_month(cls, organization):
        """Get or create usage tracking for current month"""
        today = date.today()
        tracking, created = cls.objects.get_or_create(
            organization=organization,
            year=today.year,
            month=today.month,
            defaults={
                'branches_count': organization.branches.count(),
                'staff_count': organization.get_staff_count(),
            }
        )
        return tracking
    
    def increment_orders(self, is_bot_order=False):
        """Increment order counter"""
        self.orders_created += 1
        if is_bot_order:
            self.bot_orders += 1
        else:
            self.manual_orders += 1
        self.save()

    def increment_broadcasts(self):
        """Increment marketing broadcast counter"""
        self.marketing_posts_sent += 1
        self.save(update_fields=['marketing_posts_sent', 'updated_at'])


class SubscriptionHistory(models.Model):
    """Historical record of subscription changes"""
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_("Subscription")
    )
    action = models.CharField(max_length=50, verbose_name=_("Action"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Performed By")
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    admin_telegram_message_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Admin Telegram Message ID"))
    admin_telegram_chat_id = models.BigIntegerField(null=True, blank=True, verbose_name=_("Admin Telegram Chat ID"))
    
    class Meta:
        verbose_name = _("Subscription History")
        verbose_name_plural = _("Subscription History")
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.subscription.organization.name} - {self.action} - {self.timestamp}"


class SubscriptionAnalytics:
    """Helper class for subscription analytics calculations"""
    
    @staticmethod
    def get_center_analytics(organization):
        """Get comprehensive analytics for a translation center"""
        from django.db.models import Sum, Count, Min, Max
        
        # Get all subscriptions for this center (current and past)
        all_subscriptions = Subscription.objects.filter(
            organization=organization
        ).order_by('created_at')
        
        # First subscription date
        first_subscription = all_subscriptions.first()
        first_subscription_date = first_subscription.created_at.date() if first_subscription else None
        
        # Account age in days
        account_age_days = 0
        if first_subscription_date:
            account_age_days = (date.today() - first_subscription_date).days
        
        # Total payments received (sum of all amount_paid)
        total_payments = all_subscriptions.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        # Subscription count
        total_subscriptions_count = all_subscriptions.count()
        active_subscriptions = all_subscriptions.filter(status=Subscription.STATUS_ACTIVE).count()
        
        # Trial information
        trial_subscriptions = all_subscriptions.filter(is_trial=True)
        has_used_trial = trial_subscriptions.exists()
        trial_converted = trial_subscriptions.filter(
            history__action='trial_converted'
        ).exists()
        
        # Payment history
        paid_subscriptions = all_subscriptions.exclude(amount_paid__isnull=True).exclude(amount_paid=0)
        payment_count = paid_subscriptions.count()
        
        # Average subscription duration (for completed subscriptions)
        completed_subs = all_subscriptions.filter(
            status__in=[Subscription.STATUS_EXPIRED, Subscription.STATUS_CANCELLED]
        )
        
        avg_duration_days = 0
        if completed_subs.exists():
            total_days = sum([
                (sub.end_date - sub.start_date).days 
                for sub in completed_subs
            ])
            avg_duration_days = total_days / completed_subs.count() if completed_subs.count() > 0 else 0
        
        # Get current subscription
        current_subscription = getattr(organization, 'subscription', None)
        
        # Lifetime value (total payments)
        lifetime_value = total_payments
        
        # Get all history entries
        all_history = SubscriptionHistory.objects.filter(
            subscription__organization=organization
        ).select_related('subscription', 'performed_by').order_by('-timestamp')
        
        return {
            'first_subscription_date': first_subscription_date,
            'account_age_days': account_age_days,
            'account_age_months': round(account_age_days / 30.44, 1) if account_age_days > 0 else 0,
            'account_age_years': round(account_age_days / 365.25, 1) if account_age_days > 0 else 0,
            'total_payments': total_payments,
            'lifetime_value': lifetime_value,
            'total_subscriptions_count': total_subscriptions_count,
            'active_subscriptions_count': active_subscriptions,
            'payment_count': payment_count,
            'has_used_trial': has_used_trial,
            'trial_converted': trial_converted,
            'average_subscription_days': round(avg_duration_days, 1),
            'current_subscription': current_subscription,
            'all_subscriptions': all_subscriptions,
            'all_history': all_history,
        }
    
    @staticmethod
    def get_all_centers_analytics():
        """Get analytics summary for all centers"""
        from django.db.models import Sum, Count, Avg
        from organizations.models import TranslationCenter
        
        centers_data = []
        
        for center in TranslationCenter.objects.all():
            analytics = SubscriptionAnalytics.get_center_analytics(center)
            centers_data.append({
                'center': center,
                'first_subscription_date': analytics['first_subscription_date'],
                'account_age_days': analytics['account_age_days'],
                'total_payments': analytics['total_payments'],
                'total_subscriptions': analytics['total_subscriptions_count'],
                'current_subscription': analytics['current_subscription'],
                'payment_count': analytics['payment_count'],
            })
        
        # Sort by total payments (highest first)
        centers_data.sort(key=lambda x: x['total_payments'], reverse=True)
        
        return centers_data
