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
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("Price"),
        help_text=_("Cost of this expense")
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
        return f"{self.name} ({self.price})"
    
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
        ).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
        
        # B2C expenses (b2c + both)
        b2c_total = base_queryset.filter(
            expense_type__in=['b2c', 'both']
        ).aggregate(total=Sum('price'))['total'] or Decimal('0.00')
        
        # Total expenses (all types)
        total = base_queryset.aggregate(total=Sum('price'))['total'] or Decimal('0.00')
        
        return {
            'b2b_total': b2b_total,
            'b2c_total': b2c_total,
            'total': total,
        }


# Create your models here.
class Language(models.Model):
    """Languages for translation"""

    name = models.CharField(
        max_length=100, unique=True, verbose_name=_("Language Name")
    )
    short_name = models.CharField(
        max_length=10, unique=True, verbose_name=_("Short Name")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = str(_("Language"))
        verbose_name_plural = str(_("Languages"))


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

    def get_expenses_total(self, expense_type=None):
        """
        Get total expenses for this product.
        
        Args:
            expense_type: 'b2b', 'b2c', or None for all
        
        Returns:
            Decimal total of expenses
        """
        queryset = self.expenses.filter(is_active=True)
        
        if expense_type:
            if expense_type == 'b2b':
                queryset = queryset.filter(expense_type__in=['b2b', 'both'])
            elif expense_type == 'b2c':
                queryset = queryset.filter(expense_type__in=['b2c', 'both'])
        
        return queryset.aggregate(total=Sum('price'))['total'] or Decimal('0.00')
    
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
