from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from decimal import Decimal
from organizations.models import Branch


class Expense(models.Model):
    """
    Expense model for tracking costs associated with products.
    Expenses can be B2B (agency/business) or B2C (individual customer) for analytics.
    Multi-tenant: each expense belongs to a branch.
    """
    
    EXPENSE_TYPE_CHOICES = (
        ('b2b', _('B2B (Agency/Business)')),
        ('b2c', _('B2C (Individual Customer)')),
        ('both', _('Both B2B & B2C')),
    )
    
    name = models.CharField(max_length=200, verbose_name=_("Expense Name"))
    price_for_original = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Price for Original"),
        help_text=_("Cost of this expense for the original document"),
        default=0
    )
    price_for_copy = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Price for Copy"),
        help_text=_("Cost of this expense per copy document"),
        default=0
    )
    expense_type = models.CharField(
        max_length=10,
        choices=EXPENSE_TYPE_CHOICES,
        default='both',
        verbose_name=_("Expense Type"),
        help_text=_("Whether this expense applies to B2B, B2C, or both")
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='expenses',
        verbose_name=_("Branch"),
        help_text=_("Branch this expense belongs to")
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        verbose_name = str(_("Expense"))
        verbose_name_plural = str(_("Expenses"))
        ordering = ['-created_at']
        unique_together = ('branch', 'name')
    
    def __str__(self):
        return f"{self.name} (Original: {self.price_for_original:.2f}, Copy: {self.price_for_copy:.2f})"
    
    @property
    def total_price_per_order(self):
        """Calculate total expense for a single order (always includes original)"""
        return self.price_for_original
    
    def calculate_total_for_order(self, copy_number=0):
        """
        Calculate total expense cost for an order with given copy number.
        
        Args:
            copy_number: Number of copies for the order
            
        Returns:
            Decimal: Total expense (original + copies)
        """
        return self.price_for_original + (self.price_for_copy * copy_number)
    
    @property
    def center(self):
        """Get center from branch"""
        return self.branch.center
    
    @classmethod
    def get_expenses_by_type(cls, branch=None, center=None, expense_type=None, active_only=True):
        """
        Get expenses filtered by branch/center and expense type.
        
        Args:
            branch: Branch instance or ID to filter by
            center: TranslationCenter instance or ID to filter by (will get all branch expenses)
            expense_type: 'b2b', 'b2c', or None for all
            active_only: If True, only return active expenses
        
        Returns:
            QuerySet of Expense objects
        """
        queryset = cls.objects.select_related('branch', 'branch__center')
        
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        if branch:
            queryset = queryset.filter(branch=branch)
        elif center:
            queryset = queryset.filter(branch__center=center)
        
        if expense_type:
            if expense_type == 'b2b':
                queryset = queryset.filter(expense_type__in=['b2b', 'both'])
            elif expense_type == 'b2c':
                queryset = queryset.filter(expense_type__in=['b2c', 'both'])
        
        return queryset
    
    @classmethod
    def aggregate_expenses_by_type(cls, branch=None, center=None, active_only=True):
        """
        Aggregate expenses by B2B/B2C for analytics.
        
        Args:
            branch: Branch instance or ID to filter by
            center: TranslationCenter instance or ID to filter by
            active_only: If True, only include active expenses
        
        Returns:
            dict with 'b2b_total', 'b2c_total', 'total' keys
        """
        base_queryset = cls.objects.all()
        
        if active_only:
            base_queryset = base_queryset.filter(is_active=True)
        
        if branch:
            base_queryset = base_queryset.filter(branch=branch)
        elif center:
            base_queryset = base_queryset.filter(branch__center=center)
        
        # B2B expenses (b2b + both)
        b2b_total = base_queryset.filter(
            expense_type__in=['b2b', 'both']
        ).aggregate(total=Sum('price_for_original'))['total'] or Decimal('0.00')
        
        # B2C expenses (b2c + both)
        b2c_total = base_queryset.filter(
            expense_type__in=['b2c', 'both']
        ).aggregate(total=Sum('price_for_original'))['total'] or Decimal('0.00')
        
        # Total expenses (all types)
        total = base_queryset.aggregate(total=Sum('price_for_original'))['total'] or Decimal('0.00')
        
        return {
            'b2b_total': b2b_total,
            'b2c_total': b2c_total,
            'total': total,
        }


# Create your models here.
class Language(models.Model):
    """Languages for translation with pricing"""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='languages',
        verbose_name=_("Branch"),
        null=True,
        blank=True,
        help_text=_("Branch this language belongs to")
    )
    name = models.CharField(
        max_length=100, verbose_name=_("Language Name")
    )
    short_name = models.CharField(
        max_length=10, verbose_name=_("Short Name")
    )
    
    # Pricing fields for agencies
    agency_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Agency First Page Price"),
        help_text=_("Additional price for first page translation for agencies")
    )
    agency_other_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Agency Other Pages Price"),
        help_text=_("Additional price per other page for agencies")
    )
    agency_copy_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Agency Copy Price"),
        help_text=_("Additional price per copy for agencies")
    )
    
    # Pricing fields for ordinary users
    ordinary_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Ordinary User First Page Price"),
        help_text=_("Additional price for first page translation for ordinary users")
    )
    ordinary_other_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Ordinary User Other Pages Price"),
        help_text=_("Additional price per other page for ordinary users")
    )
    ordinary_copy_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Ordinary User Copy Price"),
        help_text=_("Additional price per copy for ordinary users")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = str(_("Language"))
        verbose_name_plural = str(_("Languages"))
        unique_together = [('branch', 'name'), ('branch', 'short_name')]


class Category(models.Model):
    """Main service categories: Translation, Apostille - per Branch"""

    CHARGE_TYPE = (
        ("static", _("Bir xil narx")),
        ("dynamic", _("Page soniga qarab narx")),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='categories',
        verbose_name=_("Branch"),
        help_text=_("Branch this category belongs to")
    )
    name = models.CharField(max_length=100, verbose_name=_("Service Name"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    written_verification_required = models.BooleanField(
        default=False,
        verbose_name=_("Written Verification Required"),
        help_text=_("If enabled, the bot will ask users to type full names from their documents to avoid misspelling handwritten names."),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    languages = models.ManyToManyField(Language, verbose_name=_("Languages"))
    charging = models.CharField(
        max_length=20, choices=CHARGE_TYPE, verbose_name=_("Charging Type")
    )

    def __str__(self):
        return self.name

    def get_available_documents(self):
        """Get all active document types for this main service"""
        return self.product_set.filter(is_active=True)

    class Meta:
        verbose_name = str(_("Main Service"))
        verbose_name_plural = str(_("Main Services"))
        unique_together = ("branch", "name")


class Product(models.Model):
    """Document types with pricing and complexity information"""

    name = models.CharField(max_length=100, verbose_name=_("Document Type"))
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, verbose_name=_("Main Service")
    )

    ordinary_first_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("First Page Price for Regular Users"),
    )

    ordinary_other_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Other Pages Price for Regular Users"),
    )

    agency_first_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("First Page Price for Agencies"),
    )

    agency_other_page_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Other Pages Price for Agencies"),
    )
    agency_copy_price_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of total price for a copy of the document for agency",
        default=100,
    )
    user_copy_price_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Percentage of total price for a copy of the document for user",
        default=100,
    )
    
    # New decimal-based copy price fields (replaces percentage calculation)
    agency_copy_price_decimal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="Fixed price per copy for agencies (e.g., 25000 = 25,000 UZS per copy). If set, this overrides agency_copy_price_percentage.",
        verbose_name=_("Agency Copy Price (Fixed)"),
    )
    user_copy_price_decimal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        help_text="Fixed price per copy for users (e.g., 30000 = 30,000 UZS per copy). If set, this overrides user_copy_price_percentage.",
        verbose_name=_("User Copy Price (Fixed)"),
    )
    
    min_pages = models.PositiveIntegerField(default=1, verbose_name=_("Minimum Pages"))
    estimated_days = models.PositiveIntegerField(
        default=1, verbose_name=_("Estimated Days")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    
    # Expenses linked to this product (M2M)
    expenses = models.ManyToManyField(
        Expense,
        blank=True,
        related_name='products',
        verbose_name=_("Expenses"),
        help_text=_("Expenses associated with this product")
    )

    def __str__(self):
        return f"{self.name}"

    @property
    def branch(self):
        """Get branch from category"""
        return self.category.branch

    @property
    def center(self):
        """Get center from category's branch"""
        return self.category.branch.center

    @property
    def full_name(self):
        """Get full name with complexity"""
        return f"{self.category.name} - {self.name}"

    @property
    def service_category(self):
        """Get service category from main service"""
        return self.category.name.lower()

    def get_price_for_user_type(self, is_agency=False, pages=1):
        """Get total price based on user type and number of pages"""
        if self.category.charging == "static":
            # Static pricing - return the first page price regardless of page count
            return (
                self.agency_first_page_price
                if is_agency
                else self.ordinary_first_page_price
            )
        else:
            # Dynamic pricing - first page price + (remaining pages * other page price)
            if pages <= 0:
                pages = 1

            first_page_price = (
                self.agency_first_page_price
                if is_agency
                else self.ordinary_first_page_price
            )
            other_page_price = (
                self.agency_other_page_price
                if is_agency
                else self.ordinary_other_page_price
            )

            if pages == 1:
                return first_page_price
            else:
                return first_page_price + (other_page_price * (pages - 1))

    def get_min_price_for_user_type(self, is_agency=False):
        """Get minimum price based on user type"""
        # Minimum price is always the first page price
        return (
            self.agency_first_page_price
            if is_agency
            else self.ordinary_first_page_price
        )

    def get_price_per_page_for_user_type(self, is_agency=False):
        """Get price per page based on user type (returns first page price)"""
        return (
            self.agency_first_page_price
            if is_agency
            else self.ordinary_first_page_price
        )

    def get_first_page_price(self, is_agency=False):
        """Get first page price based on user type"""
        return (
            self.agency_first_page_price
            if is_agency
            else self.ordinary_first_page_price
        )

    def get_other_page_price(self, is_agency=False):
        """Get other pages price based on user type"""
        return (
            self.agency_other_page_price
            if is_agency
            else self.ordinary_other_page_price
        )

    def get_combined_first_page_price(self, language=None, is_agency=False):
        """
        Get combined first page price (Product + Language)
        
        Args:
            language: Language instance or None
            is_agency: Whether to use agency pricing
        
        Returns:
            Decimal combined first page price
        """
        product_price = self.get_first_page_price(is_agency=is_agency)
        
        if language:
            language_price = (
                language.agency_page_price
                if is_agency
                else language.ordinary_page_price
            )
            return product_price + language_price
        
        return product_price

    def get_combined_other_page_price(self, language=None, is_agency=False):
        """
        Get combined other pages price (Product + Language)
        
        Args:
            language: Language instance or None
            is_agency: Whether to use agency pricing
        
        Returns:
            Decimal combined other page price
        """
        product_price = self.get_other_page_price(is_agency=is_agency)
        
        if language:
            language_price = (
                language.agency_other_page_price
                if is_agency
                else language.ordinary_other_page_price
            )
            return product_price + language_price
        
        return product_price

    def get_combined_copy_price(self, language=None, is_agency=False):
        """
        Get combined copy price (Product + Language)
        
        Args:
            language: Language instance or None
            is_agency: Whether to use agency pricing
        
        Returns:
            Decimal combined copy price
        """
        # Get product copy price (fixed decimal or percentage-based)
        if is_agency:
            product_price = (
                self.agency_copy_price_decimal
                if self.agency_copy_price_decimal is not None
                else Decimal('0.00')
            )
        else:
            product_price = (
                self.user_copy_price_decimal
                if self.user_copy_price_decimal is not None
                else Decimal('0.00')
            )
        
        if language:
            language_price = (
                language.agency_copy_price
                if is_agency
                else language.ordinary_copy_price
            )
            return product_price + language_price
        
        return product_price

    def get_combined_total_price(self, language=None, is_agency=False, pages=1, copies=0):
        """
        Get combined total price including language pricing and copies
        
        Args:
            language: Language instance or None
            is_agency: Whether to use agency pricing
            pages: Number of pages
            copies: Number of copies (0 means only original)
        
        Returns:
            Decimal total price
        """
        if self.category.charging == "static":
            # Static pricing - just first page price
            total = self.get_combined_first_page_price(language=language, is_agency=is_agency)
        else:
            # Dynamic pricing
            if pages <= 0:
                pages = 1
            
            first_page = self.get_combined_first_page_price(language=language, is_agency=is_agency)
            
            if pages == 1:
                total = first_page
            else:
                other_page = self.get_combined_other_page_price(language=language, is_agency=is_agency)
                total = first_page + (other_page * (pages - 1))
        
        # Add copy costs
        if copies > 0:
            copy_price = self.get_combined_copy_price(language=language, is_agency=is_agency)
            total += (copy_price * copies)
        
        return total

    def get_expenses_total(self, expense_type=None):
        """
        Get total expenses for this product (original price only).
        Note: This doesn't include per-copy costs as those depend on copy_number.
        
        Args:
            expense_type: 'b2b', 'b2c', or None for all
        
        Returns:
            Decimal total of expenses for original documents
        """
        queryset = self.expenses.filter(is_active=True)
        
        if expense_type:
            if expense_type == 'b2b':
                queryset = queryset.filter(expense_type__in=['b2b', 'both'])
            elif expense_type == 'b2c':
                queryset = queryset.filter(expense_type__in=['b2c', 'both'])
        
        return queryset.aggregate(total=Sum('price_for_original'))['total'] or Decimal('0.00')
    
    def get_profit_margin(self, is_agency=False, pages=1):
        """
        Calculate profit margin (price - expenses).
        
        Args:
            is_agency: Whether to use agency pricing
            pages: Number of pages
        
        Returns:
            Decimal profit margin
        """
        price = self.get_price_for_user_type(is_agency=is_agency, pages=pages)
        expense_type = 'b2b' if is_agency else 'b2c'
        expenses = self.get_expenses_total(expense_type=expense_type)
        return price - expenses

    class Meta:
        verbose_name = str(_("Document Type"))
        verbose_name_plural = str(_("Document Types"))
        unique_together = ("category", "name")


# ─────────────────────────────────────────────────────────────
# General (Operating) Expenses  – not tied to any specific order
# ─────────────────────────────────────────────────────────────

class GeneralExpenseCategory(models.Model):
    """User-managed categories for operating expenses (per branch)."""

    name = models.CharField(max_length=100, verbose_name=_("Category Name"))
    icon = models.CharField(
        max_length=60,
        blank=True,
        default='',
        verbose_name=_("Iconify Icon"),
        help_text=_("e.g. mdi:office-building — leave blank for default"),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='general_expense_categories',
        verbose_name=_("Branch"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name = _("General Expense Category")
        verbose_name_plural = _("General Expense Categories")
        unique_together = ("branch", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class GeneralExpense(models.Model):
    """
    Operational costs for a center not tied to any specific order.
    Examples: buying stationery, repairing a printer, paying rent, etc.
    """

    PAYMENT_CASH = 'cash'
    PAYMENT_CARD = 'card'
    PAYMENT_NASIYA = 'nasiya'
    PAYMENT_TYPE_CHOICES = [
        (PAYMENT_CASH,   _('Cash')),
        (PAYMENT_CARD,   _('Card')),
        (PAYMENT_NASIYA, _('Nasiya (Credit)')),
    ]

    title = models.CharField(max_length=200, verbose_name=_("Title"))
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Amount (UZS)"),
    )
    category = models.ForeignKey(
        GeneralExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='general_expenses',
        verbose_name=_("Category"),
    )
    date = models.DateField(verbose_name=_("Date"))
    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_TYPE_CHOICES,
        default=PAYMENT_CASH,
        verbose_name=_("Payment Type"),
    )
    nasiya_deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Nasiya Deadline"),
        help_text=_("Repayment deadline for credit expenses."),
    )
    is_paid = models.BooleanField(
        default=True,
        verbose_name=_("Paid"),
        help_text=_("Mark as paid once a nasiya (credit) expense is settled."),
    )
    vendor = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_("Vendor / Supplier"),
        help_text=_("Who was paid — shop, person, company, etc."),
    )
    note = models.TextField(blank=True, default='', verbose_name=_("Note"))
    receipt_image = models.ImageField(
        upload_to='general_expense_receipts/',
        null=True,
        blank=True,
        verbose_name=_("Receipt / Photo"),
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='general_expenses',
        verbose_name=_("Branch"),
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='general_expenses_created',
        verbose_name=_("Recorded By"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    @property
    def is_overdue(self):
        """True when nasiya is unpaid and deadline has passed."""
        from django.utils import timezone
        if self.payment_type == self.PAYMENT_NASIYA and not self.is_paid:
            if self.nasiya_deadline and self.nasiya_deadline < timezone.now().date():
                return True
        return False

    class Meta:
        verbose_name = _("General Expense")
        verbose_name_plural = _("General Expenses")
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["branch", "date"]),
            models.Index(fields=["category", "date"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.amount:,.0f} UZS ({self.date})"
