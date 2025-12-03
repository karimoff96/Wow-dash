from django.db import models
from django.utils.translation import gettext_lazy as _
from organizations.models import Branch


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
    min_pages = models.PositiveIntegerField(default=1, verbose_name=_("Minimum Pages"))
    estimated_days = models.PositiveIntegerField(
        default=1, verbose_name=_("Estimated Days")
    )
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

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

    class Meta:
        verbose_name = str(_("Document Type"))
        verbose_name_plural = str(_("Document Types"))
        unique_together = ("category", "name")


# Backward compatibility aliases for bot/main.py
# The bot was written with old model names - these aliases allow it to work
MainService = Category
Product = Product
