import uuid
import os
from django.db import models
from django.utils.translation import gettext_lazy as _


class AdditionalInfo(models.Model):
    """
    Additional information for a Branch - payment details, help texts, about us, etc.
    Each branch can have its own settings. Falls back to center's main branch if not set.
    
    Note: help_text, description, about_us, working_hours fields are translated 
    via modeltranslation (see accounts/translations.py)
    """
    
    branch = models.OneToOneField(
        'organizations.Branch',
        on_delete=models.CASCADE,
        related_name='additional_info',
        verbose_name=_("Branch"),
        null=True,
        blank=True,
        help_text=_("Leave empty for global/default settings")
    )
    
    # Payment Information
    bank_card = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Bank Card Number"),
        help_text=_("Card number for receiving payments (e.g., 8600 1234 5678 9012)")
    )
    holder_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Card Holder Name"),
        help_text=_("Name of the card holder")
    )
    
    # Translatable text fields (translations handled by modeltranslation)
    help_text = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Help Text"),
        help_text=_("Help text shown in bot")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_("Description of the branch/center")
    )
    
    about_us = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("About Us"),
        help_text=_("About us information")
    )
    
    working_hours = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Working Hours"),
        help_text=_("e.g., Mon-Fri: 9:00-18:00, Sat: 10:00-15:00")
    )
    
    # Additional Contact Info
    support_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Support Phone"),
        help_text=_("Phone number for customer support")
    )
    support_telegram = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Support Telegram"),
        help_text=_("Telegram username for support (e.g., @support_bot)")
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    
    class Meta:
        verbose_name = _("Additional Info")
        verbose_name_plural = _("Additional Info")
    
    def __str__(self):
        if self.branch:
            return f"Info for {self.branch.name}"
        return "Global Additional Info"
    
    def get_translated_field(self, field_name, language='uz'):
        """Get translated field value with fallback to default"""
        # Try language-specific field first (created by modeltranslation)
        lang_field = f'{field_name}_{language}'
        value = getattr(self, lang_field, None)
        if value:
            return value
        # Fallback to default field
        return getattr(self, field_name, None) or ""
    
    @classmethod
    def get_for_branch(cls, branch):
        """
        Get AdditionalInfo for a branch.
        Falls back to: branch's info → main branch's info → global info → None
        """
        if branch:
            # Try to get branch-specific info
            try:
                return cls.objects.get(branch=branch)
            except cls.DoesNotExist:
                pass
            
            # Try to get main branch's info
            try:
                main_branch = branch.center.branches.filter(is_main=True).first()
                if main_branch and main_branch != branch:
                    return cls.objects.get(branch=main_branch)
            except cls.DoesNotExist:
                pass
        
        # Fall back to global info (no branch)
        try:
            return cls.objects.get(branch=None)
        except cls.DoesNotExist:
            return None
    
    @classmethod
    def get_for_user(cls, user):
        """Get AdditionalInfo based on user's selected branch"""
        if user and user.branch:
            return cls.get_for_branch(user.branch)
        return cls.get_for_branch(None)
    
    @classmethod
    def get_for_user(cls, user):
        """Get AdditionalInfo based on user's selected branch"""
        if user and user.branch:
            return cls.get_for_branch(user.branch)
        return cls.get_for_branch(None)


class BotUser(models.Model):
    """Model for Telegram bot users (customers)"""

    LANGUAGES = (
        ("uz", "Uzbek"),
        ("ru", "Russian"),
        ("en", "English"),
    )

    # Center relationship - users are scoped per center (multi-tenant)
    # Same Telegram user can register separately for each translation center
    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bot_users',
        verbose_name=_("Translation Center"),
        help_text=_("The center this user belongs to. Same Telegram user can have separate accounts per center.")
    )

    # Branch relationship - customers are tied to specific branches
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers',
        verbose_name=_("Branch")
    )

    # Telegram user data
    user_id = models.BigIntegerField(
        verbose_name=_("Telegram User ID"), blank=True, null=True
    )
    username = models.CharField(
        max_length=100, blank=True, null=True, verbose_name=_("Username")
    )
    name = models.CharField(max_length=100, verbose_name=_("Full Name"))
    phone = models.CharField(max_length=100, verbose_name=_("Phone Number"))

    # Bot interaction data
    language = models.CharField(
        max_length=100, choices=LANGUAGES, default="uz", verbose_name=_("Language")
    )
    step = models.IntegerField(default=0, verbose_name=_("Registration Step"))
    agency_token = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
        verbose_name=_("Agency Token"),
    )
    agency_link = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("Agency Link")
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name=_("Is Used"),
        help_text=_("Whether this invitation link has been used"),
    )
    is_active = models.BooleanField(default=False, verbose_name=_("Is Active"))
    is_agency = models.BooleanField(default=False, verbose_name=_("Is Agency"))
    agency = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agency_users",
        verbose_name=_("Agency"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        center_name = self.center.name if self.center else "Global"
        return f"@{self.username or self.user_id} - {self.name} ({center_name})"

    @property
    def display_name(self):
        """Get display name for user"""
        return self.name or f"User {self.user_id}"
    
    @property
    def full_name(self):
        """Alias for name field for compatibility"""
        return self.name

    @property
    def is_registered(self):
        """Check if user completed registration"""
        return self.is_active and bool(self.name) and bool(self.phone)

    class Meta:
        verbose_name = _("Telegram User")
        verbose_name_plural = _("Telegram Users")
        # Unique constraint: same user_id can exist for different centers
        unique_together = [['user_id', 'center']]
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'center'],
                name='unique_user_per_center'
            )
        ]

    def save(self, *args, **kwargs):
        # Generate agency token and link if this is an agency user
        if self.is_agency:
            if not self.agency_token:
                self.agency_token = uuid.uuid4()
            if not self.agency_link:
                self.agency_link = self.get_agency_invite_link()
        super().save(*args, **kwargs)

    def get_agency_invite_link(self):
        """Generate a unique invite link for the agency"""
        if not self.is_agency:
            return None

        # Get bot username from environment variables
        bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip()
        if not bot_username:
            raise ValueError("TELEGRAM_BOT_USERNAME environment variable is not set")

        # Remove @ if present and ensure it's included in the final URL
        bot_username = bot_username.lstrip("@")
        return f"https://t.me/{bot_username}?start=agency_{self.agency_token}"

    @classmethod
    def get_agency_by_token(cls, token):
        """
        Get agency by invitation token if it exists and hasn't been used yet.
        Marks the token as used if found.
        """
        from django.db import transaction
        import traceback

        try:
            print(f"[DEBUG] Looking for agency with token: {token}")

            # First, let's check if the agency exists at all (regardless of is_used)
            all_agencies = cls.objects.filter(agency_token=token, is_agency=True)
            print(f"[DEBUG] Found {all_agencies.count()} agency(ies) with this token")

            if all_agencies.exists():
                first_agency = all_agencies.first()
                print(
                    f"[DEBUG] Agency found: {first_agency.name}, is_used={first_agency.is_used}"
                )

                if first_agency.is_used:
                    print(f"[WARNING] Agency token already used!")
                    return None

            with transaction.atomic():
                # Use select_for_update to lock the row
                agency = cls.objects.select_for_update().get(
                    agency_token=token,
                    is_agency=True,
                    is_used=False,  # Only get unused tokens
                )
                print(
                    f"[DEBUG] Successfully retrieved unused agency: {agency.name} (ID: {agency.id})"
                )

                # Mark as used
                agency.is_used = True
                agency.save(update_fields=["is_used", "updated_at"])
                print(f"[DEBUG] Marked agency {agency.name} as used")

                return agency
        except cls.DoesNotExist:
            print(f"[WARNING] No unused agency found with token: {token}")
            return None
        except ValueError as e:
            print(f"[ERROR] ValueError in get_agency_by_token: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error in get_agency_by_token: {e}")
            traceback.print_exc()
            return None
