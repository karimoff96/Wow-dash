from django.contrib import admin

from bot.models import TelegramUpdateReceipt


@admin.register(TelegramUpdateReceipt)
class TelegramUpdateReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "update_id", "center", "chat_id", "status", "attempts",
        "received_at", "completed_at",
    )
    list_filter = ("status", "center", "received_at")
    search_fields = ("update_id", "chat_id", "center__name", "last_error")
    readonly_fields = (
        "center", "update_id", "chat_id", "status", "payload", "attempts",
        "last_error", "received_at", "started_at", "completed_at", "updated_at",
    )
    ordering = ("-received_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

