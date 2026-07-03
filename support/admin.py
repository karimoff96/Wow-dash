from django.contrib import admin
from .models import Ticket, TicketCategory, TicketMessage, TicketAttachment, TicketStatusHistory


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name_uz', 'center', 'telegram_group_id', 'sla_hours', 'order', 'is_active']
    list_filter = ['center', 'is_active']
    list_editable = ['is_active', 'sla_hours', 'order']
    search_fields = ['name_uz', 'name_ru', 'name_en']
    fieldsets = (
        (None, {
            'fields': ('center', 'name_uz', 'name_ru', 'name_en', 'icon', 'color', 'is_active', 'order'),
        }),
        ('Telegram Routing', {
            'fields': ('telegram_group_id', 'sla_hours'),
        }),
    )


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ['sender_type', 'sender', 'body', 'is_internal_note', 'created_at']
    can_delete = False
    show_change_link = False


class TicketStatusHistoryInline(admin.TabularInline):
    model = TicketStatusHistory
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'changed_by', 'reason', 'created_at']
    can_delete = False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'subject', 'center', 'created_by',
        'status', 'priority', 'ticket_type', 'has_unread_reply', 'created_at',
    ]
    list_filter = ['status', 'priority', 'ticket_type', 'center', 'has_unread_reply']
    search_fields = ['ticket_number', 'subject', 'created_by__username', 'created_by__first_name']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at', 'resolved_at', 'closed_at']
    ordering = ['-created_at']
    inlines = [TicketMessageInline, TicketStatusHistoryInline]
    fieldsets = (
        ('Ticket Info', {
            'fields': (
                'ticket_number', 'center', 'created_by', 'category',
                'subject', 'description', 'ticket_type',
            ),
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'has_unread_reply', 'auto_resolve_at'),
        }),
        ('Telegram', {
            'fields': ('telegram_message_id', 'telegram_group_id'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at', 'closed_at'),
            'classes': ('collapse',),
        }),
    )
