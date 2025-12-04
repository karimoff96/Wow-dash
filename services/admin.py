from django.contrib import admin
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin
from .models import Category, Product, Language, Expense


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "created_at")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_display",
        "expense_type",
        "branch",
        "center_display",
        "is_active",
        "product_count",
        "created_at",
    )
    list_filter = ("is_active", "expense_type", "branch", "branch__center", "created_at")
    search_fields = ("name", "description", "branch__name", "branch__center__name")
    ordering = ("-created_at",)
    autocomplete_fields = ("branch",)
    
    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "price", "expense_type", "description", "is_active")},
        ),
        (
            "Multi-tenant",
            {"fields": ("branch",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
    readonly_fields = ("created_at", "updated_at")
    
    def price_display(self, obj):
        return format_html('<span style="color: #28a745; font-weight: bold;">{}</span>', f"{obj.price:,.2f}")
    price_display.short_description = "Price"
    price_display.admin_order_field = "price"
    
    def center_display(self, obj):
        return obj.branch.center.name if obj.branch else "-"
    center_display.short_description = "Center"
    
    def product_count(self, obj):
        count = obj.products.count()
        if count > 0:
            return format_html('<span style="color: #007bff;">{}</span>', count)
        return "0"
    product_count.short_description = "Products"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("branch", "branch__center").prefetch_related("products")


@admin.register(Category)
class CategoryAdmin(TranslationAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = (
        "name",
        "name_uz",
        "name_ru",
        "name_en",
        "description",
        "description_uz",
        "description_ru",
        "description_en",
    )
    ordering = ("-created_at",)


@admin.register(Product)
class ProductAdmin(TranslationAdmin):
    list_display = (
        "__str__",
        "category",
        "ordinary_first_page_price",
        "ordinary_other_page_price",
        "agency_first_page_price",
        "agency_other_page_price",
        "user_copy_price_percentage",
        "agency_copy_price_percentage",
        "min_pages",
        "estimated_days",
        "expense_count",
        "total_expenses_display",
        "is_active",
    )
    list_filter = ("category", "is_active", "created_at")
    search_fields = (
        "name",
        "name_uz",
        "name_ru",
        "name_en",
        "description",
        "description_uz",
        "description_ru",
        "description_en",
        "category__name_uz",
        "category__name_ru",
        "category__name_en",
    )
    ordering = ("category", "name")
    filter_horizontal = ("expenses",)  # M2M widget for expenses

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("name", "category", "description", "is_active")},
        ),
        (
            "Base Pricing",
            {
                "fields": (
                    "ordinary_first_page_price",
                    "ordinary_other_page_price",
                    "agency_first_page_price",
                    "agency_other_page_price",
                )
            },
        ),
        (
            "Copy Pricing (Additional Copies)",
            {
                "fields": (
                    "user_copy_price_percentage",
                    "agency_copy_price_percentage",
                ),
                "description": "Percentage of base price charged for each additional copy. 100% means each copy costs the same as the base price.",
            },
        ),
        (
            "Expenses",
            {
                "fields": ("expenses",),
                "description": "Link expenses to this product for cost tracking and profit margin analysis.",
            },
        ),
        (
            "Other Settings",
            {
                "fields": (
                    "min_pages",
                    "estimated_days",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "service_category",
    )

    def service_category(self, obj):
        return obj.service_category.title()

    service_category.short_description = "Service Category"
    
    def expense_count(self, obj):
        count = obj.expenses.count()
        if count > 0:
            return format_html('<span style="color: #007bff;">{}</span>', count)
        return "0"
    expense_count.short_description = "Expenses"
    
    def total_expenses_display(self, obj):
        total = obj.get_expenses_total()
        if total > 0:
            return format_html('<span style="color: #dc3545;">{}</span>', f"{total:,.2f}")
        return "-"
    total_expenses_display.short_description = "Total Expenses"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("category").prefetch_related("expenses")
