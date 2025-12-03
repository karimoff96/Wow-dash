from django.contrib import admin
from django.contrib.auth.models import Group
from django.utils.html import format_html
from accounts.models import BotUser, AdditionalInfo


admin.site.unregister(Group)


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "username",
        "phone",
        "branch",
        "is_agency",
        "is_used",
        "agency_display",
        "invitation_link_display",
        "created_at",
        "is_active",
    )
    list_filter = (
        "branch",
        "language",
        "is_active",
        "is_agency",
        "is_used",
        "created_at",
        "agency",
    )
    search_fields = ("name", "username", "phone", "user_id", "agency_token")
    ordering = ("-created_at",)
    list_select_related = ("agency", "branch")
    actions = ["mark_as_unused"]
    autocomplete_fields = ['branch', 'agency']

    fieldsets = (
        (
            "Branch Assignment",
            {
                "fields": (
                    "branch",
                )
            },
        ),
        (
            "Telegram User Information",
            {
                "fields": (
                    "user_id",
                    "username",
                    "name",
                    "phone",
                    "language",
                    "is_active",
                )
            },
        ),
        (
            "Agency Information",
            {
                "fields": (
                    "is_agency",
                    "is_used",
                    "agency_token",
                    "agency_link_display_field",
                    "agency",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "step",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "agency_token",
        "agency_link_display_field",
    )

    def agency_display(self, obj):
        if obj.agency:
            return obj.agency.display_name
        return "-"

    agency_display.short_description = "Agency"
    agency_display.admin_order_field = "agency__name"

    def invitation_link_display(self, obj):
        """Display invitation link status in list view"""
        if obj.is_agency:
            if obj.is_used:
                return format_html('<span style="color: orange;">🔒 Used</span>')
            else:
                return format_html('<span style="color: green;">✅ Available</span>')
        return "-"

    invitation_link_display.short_description = "Invite Status"

    def agency_link_display_field(self, obj):
        """Display clickable agency link in detail view"""
        if obj.is_agency and obj.agency_link:
            status = "🔒 USED" if obj.is_used else "✅ ACTIVE"
            return format_html(
                '<div style="margin: 10px 0;">'
                "<p><strong>Status: {}</strong></p>"
                "<p><strong>Invitation Link:</strong></p>"
                '<input type="text" value="{}" readonly style="width: 100%; padding: 8px; font-family: monospace; background: #f5f5f5;" onclick="this.select(); document.execCommand(\'copy\'); alert(\'Link copied to clipboard!\');" />'
                '<p style="color: #666; margin-top: 8px;"><small>Click the link above to copy it to clipboard</small></p>'
                "</div>",
                status,
                obj.agency_link,
            )
        return "-"

    agency_link_display_field.short_description = "Agency Invitation Link"

    def mark_as_unused(self, request, queryset):
        """Admin action to reset agency invitation links"""
        updated = 0
        for obj in queryset:
            if obj.is_agency and obj.is_used:
                obj.is_used = False
                obj.save()
                updated += 1

        if updated > 0:
            self.message_user(
                request,
                f"Successfully reset {updated} agency invitation link(s) to unused status.",
            )
        else:
            self.message_user(
                request,
                "No agency invitations were reset. Only used agency profiles can be reset.",
                level="WARNING",
            )

    mark_as_unused.short_description = "Reset invitation link (mark as unused)"

    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(AdditionalInfo)
class AdditionalInfoAdmin(admin.ModelAdmin):
    """Admin for AdditionalInfo - branch-specific settings"""
    
    list_display = (
        '__str__',
        'branch',
        'bank_card',
        'support_phone',
        'updated_at',
    )
    list_filter = ('branch__center', 'branch')
    search_fields = ('branch__name', 'bank_card', 'holder_name', 'support_phone')
    autocomplete_fields = ['branch']
    
    fieldsets = (
        (
            "Branch",
            {
                "fields": ("branch",),
                "description": "Leave empty for global/default settings that apply when branch doesn't have its own."
            }
        ),
        (
            "Payment Information",
            {
                "fields": ("bank_card", "holder_name"),
            }
        ),
        (
            "Help Text",
            {
                "fields": ("help_text",),  # modeltranslation will add _uz, _ru, _en
                "classes": ("collapse",),
            }
        ),
        (
            "Description",
            {
                "fields": ("description",),
                "classes": ("collapse",),
            }
        ),
        (
            "About Us",
            {
                "fields": ("about_us",),
                "classes": ("collapse",),
            }
        ),
        (
            "Working Hours",
            {
                "fields": ("working_hours",),
            }
        ),
        (
            "Contact Information",
            {
                "fields": ("support_phone", "support_telegram"),
            }
        ),
    )
