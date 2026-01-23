from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin
from .models import Region, District, AdditionalInfo, AuditLog, FileArchive


@admin.register(Region)
class RegionAdmin(TranslationAdmin):
    list_display = ['name', 'code', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(District)
class DistrictAdmin(TranslationAdmin):
    list_display = ['name', 'region', 'is_active']
    list_filter = ['region', 'is_active']
    search_fields = ['name', 'region__name']
    ordering = ['region', 'name']


@admin.register(AdditionalInfo)
class AdditionalInfoAdmin(admin.ModelAdmin):
    list_display = ['bot_user', 'branch', 'title', 'created_at']
    list_filter = ['branch', 'created_at']
    search_fields = ['title', 'bot_user__name']
    ordering = ['-created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'target_repr', 'branch', 'ip_address']
    list_filter = ['action', 'created_at', 'branch', 'center']
    search_fields = ['user__username', 'user__first_name', 'target_repr', 'details']
    readonly_fields = ['user', 'action', 'content_type', 'object_id', 'target_repr', 
                       'details', 'changes', 'ip_address', 'user_agent', 'branch', 
                       'center', 'created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(FileArchive)
class FileArchiveAdmin(admin.ModelAdmin):
    list_display = [
        'archive_name', 'center', 'archive_date', 'total_orders',
        'size_display', 'telegram_link', 'created_by'
    ]
    list_filter = ['center', 'archive_date', 'created_by']
    search_fields = ['archive_name', 'center__name', 'notes']
    readonly_fields = [
        'archive_name', 'archive_path', 'telegram_message_id',
        'telegram_channel_id', 'total_orders', 'total_size_bytes',
        'archive_date', 'size_display', 'telegram_link', 'orders_list'
    ]
    ordering = ['-archive_date']
    date_hierarchy = 'archive_date'
    
    fieldsets = (
        (_('Archive Information'), {
            'fields': ('center', 'archive_name', 'archive_date', 'created_by')
        }),
        (_('Telegram Details'), {
            'fields': ('telegram_message_id', 'telegram_channel_id', 'telegram_link')
        }),
        (_('Statistics'), {
            'fields': ('total_orders', 'total_size_bytes', 'size_display')
        }),
        (_('Orders'), {
            'fields': ('orders_list',),
            'classes': ('collapse',)
        }),
        (_('Notes'), {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )
    
    def size_display(self, obj):
        """Display size in human-readable format"""
        return f"{obj.size_mb:.2f} MB"
    size_display.short_description = _("Size")
    
    def telegram_link(self, obj):
        """Display clickable Telegram link"""
        if obj.telegram_message_id and obj.telegram_channel_id:
            # Remove @ or - prefix from channel ID for URL
            channel_id = str(obj.telegram_channel_id).replace('@', '').replace('-100', '')
            url = f"https://t.me/c/{channel_id}/{obj.telegram_message_id}"
            return format_html(
                '<a href="{}" target="_blank">📱 View in Telegram</a>',
                url
            )
        return "-"
    telegram_link.short_description = _("Telegram Link")
    
    def orders_list(self, obj):
        """Display list of archived orders"""
        orders = obj.orders.all()[:50]  # Limit to 50 orders
        if not orders:
            return _("No orders linked")
        
        html = "<ul style='margin: 0; padding-left: 20px;'>"
        for order in orders:
            order_url = reverse('admin:orders_order_change', args=[order.id])
            html += f"<li><a href='{order_url}' target='_blank'>Order #{order.get_order_number()} - {order.get_customer_display_name()}</a></li>"
        
        total = obj.orders.count()
        if total > 50:
            html += f"<li><em>... and {total - 50} more orders</em></li>"
        
        html += "</ul>"
        return format_html(html)
    orders_list.short_description = _("Archived Orders")
    
    def has_add_permission(self, request):
        """Prevent manual creation - archives are created by system"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete archives"""
        return request.user.is_superuser
    
    # Custom actions
    actions = ['trigger_manual_archive']
    
    def trigger_manual_archive(self, request, queryset):
        """Placeholder for manual archive trigger action"""
        self.message_user(
            request,
            _("Manual archiving should be triggered from the center's admin page or via management command."),
            level='warning'
        )
    trigger_manual_archive.short_description = _("Trigger manual archive")
