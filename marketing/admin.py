from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import (
    MarketingPost, BroadcastRecipient, 
    UserBroadcastPreference, BroadcastRateLimit
)


@admin.register(MarketingPost)
class MarketingPostAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'target_scope', 'status', 'total_recipients',
        'delivery_stats', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'target_scope', 'content_type', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = [
        'total_recipients', 'sent_count', 'delivered_count', 
        'failed_count', 'sent_at', 'completed_at', 'last_error',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Content'), {
            'fields': ('title', 'content', 'content_type', 'media_file')
        }),
        (_('Targeting'), {
            'fields': (
                'target_scope', 'target_center', 'target_branch',
                'include_b2c', 'include_b2b'
            )
        }),
        (_('Scheduling'), {
            'fields': ('scheduled_at', 'status')
        }),
        (_('Statistics'), {
            'fields': (
                'total_recipients', 'sent_count', 'delivered_count',
                'failed_count', 'sent_at', 'completed_at'
            ),
            'classes': ('collapse',)
        }),
        (_('Errors'), {
            'fields': ('last_error',),
            'classes': ('collapse',)
        }),
    )
    
    def delivery_stats(self, obj):
        if obj.sent_count == 0:
            return "-"
        return format_html(
            '<span style="color: green;">{}</span> / '
            '<span style="color: red;">{}</span> / '
            '<span style="color: gray;">{}</span>',
            obj.delivered_count,
            obj.failed_count,
            obj.total_recipients
        )
    delivery_stats.short_description = _('Delivered/Failed/Total')
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ['post', 'bot_user', 'status', 'retry_count', 'sent_at']
    list_filter = ['status', 'post']
    search_fields = ['bot_user__name', 'bot_user__phone']
    readonly_fields = ['telegram_message_id', 'sent_at']
    raw_id_fields = ['post', 'bot_user']


@admin.register(UserBroadcastPreference)
class UserBroadcastPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'bot_user', 'receive_marketing', 'receive_promotions',
        'receive_updates', 'last_broadcast_at'
    ]
    list_filter = ['receive_marketing', 'receive_promotions', 'receive_updates']
    search_fields = ['bot_user__name', 'bot_user__phone']
    raw_id_fields = ['bot_user']


@admin.register(BroadcastRateLimit)
class BroadcastRateLimitAdmin(admin.ModelAdmin):
    list_display = [
        'center', 'messages_per_second', 'daily_limit_per_user',
        'batch_size', 'batch_delay'
    ]
    list_filter = ['center']
