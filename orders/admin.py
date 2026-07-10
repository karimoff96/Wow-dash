from django.contrib import admin
from django.urls import reverse
from .models import (
    AssignmentRule, BulkPayment, Order, OrderEvent, OrderMedia,
    PaymentOrderLink, PaymeTransaction, Quote, QuoteLine, Receipt,
)
from django.utils.html import format_html


# Register your models here.
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bot_user",
        "product",
        "total_pages",
        "copy_number",
        "total_price",
        "payment_type",
        "status_display",
        "language",
        "deadline",
        "is_active",
        "created_at",
    )
    list_filter = (
        "status",
        "payment_type",
        "is_active",
        "deadline",
        "created_at",
        "product__category",
    )
    search_fields = (
        "bot_user__name",
        "bot_user__username",
        "product__name",
        "product__name_uz",
        "product__name_ru",
        "product__name_en",
        "description",
    )
    ordering = ("-created_at",)

    def status_display(self, obj):
        """Display status with color coding"""
        colors = {
            "pending": "orange",
            "payment_pending": "blue",
            "payment_received": "purple",
            "payment_confirmed": "green",
            "in_progress": "teal",
            "ready": "darkgreen",
            "completed": "gray",
            "cancelled": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    fieldsets = (
        (
            "Order Information",
            {
                "fields": (
                    "bot_user",
                    "product",
                    "language",
                    "description",
                    "deadline",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Pricing & Files",
            {
                "fields": (
                    "total_pages",
                    "copy_number",
                    "total_price",
                    "payment_type",
                    "recipt",
                )
            },
        ),
        ("Files", {"fields": ("files",), "classes": ("collapse",)}),
        (
            "Archive Status",
            {
                "fields": ("archived_files", "archive_status_display"),
                "classes": ("collapse",)
            }
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ("created_at", "updated_at", "total_pages", "total_price", "archive_status_display")
    date_hierarchy = "deadline"
    
    def archive_status_display(self, obj):
        """Display archive status with link"""
        if obj.archived_files:
            url = reverse("admin:core_filearchive_change", args=[obj.archived_files.id])
            return format_html(
                '📦 <a href="{}" target="_blank">{}</a><br>'
                '<small>Archived on: {}<br>Size: {:.2f} MB</small>',
                url,
                obj.archived_files.archive_name,
                obj.archived_files.archive_date.strftime("%Y-%m-%d %H:%M"),
                obj.archived_files.size_mb
            )
        return format_html('<span style="color: green;">✓ Files stored locally</span>')
    archive_status_display.short_description = "Archive Status"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("bot_user", "product")
            .prefetch_related("files")
        )


@admin.register(OrderMedia)
class OrderMediaAdmin(admin.ModelAdmin):
    list_display = ("file", "pages", "created_at")
    list_filter = ("created_at",)
    ordering = ("-created_at",)

    readonly_fields = ("pages", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request)


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 0


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('reference', 'version', 'branch', 'bot_user', 'status', 'total', 'valid_until', 'created_at')
    list_filter = ('status', 'source', 'branch__center', 'branch', 'created_at')
    search_fields = ('reference', 'customer_name', 'customer_phone', 'bot_user__name')
    inlines = (QuoteLineInline,)
    ordering = ('-created_at',)


@admin.register(AssignmentRule)
class AssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ('branch', 'priority', 'category', 'product', 'language', 'assignee', 'turnaround_hours', 'is_active')
    list_filter = ('is_active', 'branch__center', 'branch')
    ordering = ('branch', 'priority', 'pk')


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'actor', 'bot_user', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('order__id', 'order__center_order_number', 'actor__user__username')
    readonly_fields = ('order', 'event_type', 'actor', 'bot_user', 'data', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_link",
        "amount",
        "verified_amount",
        "source",
        "status_display",
        "uploaded_by_user",
        "verified_by",
        "created_at",
    )
    list_filter = ("status", "source", "created_at")
    search_fields = (
        "order__id",
        "order__bot_user__name",
        "comment",
    )
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "verified_at")
    autocomplete_fields = ["order", "uploaded_by_user", "verified_by"]
    
    def order_link(self, obj):
        url = reverse("admin:orders_order_change", args=[obj.order_id])
        return format_html('<a href="{}">Order #{}</a>', url, obj.order_id)
    order_link.short_description = "Order"
    
    def status_display(self, obj):
        colors = {
            "pending": "orange",
            "verified": "green",
            "rejected": "red",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_display.short_description = "Status"
    
    fieldsets = (
        (
            "Receipt Information",
            {
                "fields": (
                    "order",
                    "file",
                    "telegram_file_id",
                    "source",
                    "uploaded_by_user",
                )
            },
        ),
        (
            "Amount & Verification",
            {
                "fields": (
                    "amount",
                    "verified_amount",
                    "status",
                    "verified_by",
                    "verified_at",
                    "comment",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(BulkPayment)
class BulkPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bot_user_name",
        "amount",
        "payment_method",
        "orders_count",
        "fully_paid_orders",
        "processed_by_name",
        "created_at",
    )

    @admin.display(description="Bot User", ordering="bot_user__name")
    def bot_user_name(self, obj):
        if obj.bot_user:
            return f"{obj.bot_user.name} ({obj.bot_user.phone or '—'})"
        return "—"

    @admin.display(description="Processed By", ordering="processed_by__user__first_name")
    def processed_by_name(self, obj):
        if obj.processed_by:
            return str(obj.processed_by)
        return "—"
    list_filter = ("payment_method", "created_at", "branch")
    search_fields = ("bot_user__name", "bot_user__phone", "receipt_note")
    readonly_fields = ("created_at", "orders_count", "fully_paid_orders", "remaining_debt_after")
    ordering = ("-created_at",)
    
    fieldsets = (
        (
            "Payment Information",
            {
                "fields": (
                    "bot_user",
                    "amount",
                    "payment_method",
                    "receipt_note",
                )
            },
        ),
        (
            "Processing Details",
            {
                "fields": (
                    "processed_by",
                    "branch",
                    "created_at",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "orders_count",
                    "fully_paid_orders",
                    "remaining_debt_after",
                )
            },
        ),
    )


@admin.register(PaymeTransaction)
class PaymeTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "payme_transaction_id",
        "order_link",
        "amount_sum",
        "state",
        "create_time_ms",
        "perform_time_ms",
        "cancel_time_ms",
        "cancel_reason",
        "created_at",
    )
    list_filter = ("state", "created_at")
    search_fields = ("payme_transaction_id", "order__id")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "payme_transaction_id",
        "amount_tiyin",
        "account",
        "state",
        "create_time_ms",
        "perform_time_ms",
        "cancel_time_ms",
        "cancel_reason",
        "checkout_url",
        "detail",
        "raw_request",
        "raw_response",
        "order",
    )

    def order_link(self, obj):
        if not obj.order_id:
            return "—"
        url = reverse("admin:orders_order_change", args=[obj.order_id])
        return format_html('<a href="{}">Order #{}</a>', url, obj.order_id)

    order_link.short_description = "Order"
    
    def bot_user_name(self, obj):
        return obj.bot_user.name if obj.bot_user else "N/A"
    bot_user_name.short_description = "Customer"
    
    def processed_by_name(self, obj):
        if obj.processed_by:
            return obj.processed_by.user.get_full_name() or obj.processed_by.user.username
        return "N/A"
    processed_by_name.short_description = "Processed By"


@admin.register(PaymentOrderLink)
class PaymentOrderLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bulk_payment_id",
        "order_id",
        "amount_applied",
        "previous_received",
        "new_received",
        "fully_paid",
        "created_at",
    )
    list_filter = ("fully_paid", "created_at")
    search_fields = ("bulk_payment__id", "order__id")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    
    def bulk_payment_id(self, obj):
        return f"Payment #{obj.bulk_payment.id}"
    bulk_payment_id.short_description = "Bulk Payment"
    
    def order_id(self, obj):
        return f"Order #{obj.order.get_order_number()}"
    order_id.short_description = "Order"
