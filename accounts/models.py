import logging
import uuid
import os
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


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
    
    # Guide link (Telegram message, YouTube, etc.)
    guide = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Guide Link"),
        help_text=_("URL to a guide (Telegram message, YouTube video, documentation, etc.)")
    )
    
    # Reserved fields for future use
    reserved_field_1 = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Reserved Field 1"),
        help_text=_("Reserved for future use")
    )
    reserved_field_2 = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Reserved Field 2"),
        help_text=_("Reserved for future use")
    )
    reserved_field_3 = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Reserved Field 3"),
        help_text=_("Reserved for future use")
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
            # Always regenerate the link to ensure it uses the correct bot username
            self.agency_link = self.get_agency_invite_link()
        super().save(*args, **kwargs)

    def get_agency_invite_link(self):
        """Generate a unique invite link for the agency scoped to their center"""
        if not self.is_agency:
            return None

        # Get bot username from the center's configuration
        bot_username = None
        if self.center and self.center.bot_username:
            bot_username = self.center.bot_username.strip().lstrip("@")
        
        # Fallback to environment variable for backward compatibility
        if not bot_username:
            bot_username = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        
        if not bot_username:
            raise ValueError(
                "Bot username not configured. Please set the bot username in Center settings "
                "or TELEGRAM_BOT_USERNAME environment variable."
            )

        # Generate link with center scope if available
        # Format: agency_{token}_{center_id} for center-scoped invites
        if self.center:
            return f"https://t.me/{bot_username}?start=agency_{self.agency_token}_{self.center.id}"
        return f"https://t.me/{bot_username}?start=agency_{self.agency_token}"

    @classmethod
    def get_agency_by_token(cls, token, center_id=None):
        """
        Get agency by invitation token if it exists and hasn't been used yet.
        Marks the token as used if found.
        
        Args:
            token: The agency UUID token
            center_id: Optional center ID to scope the search (for multi-tenant)
        """
        from django.db import transaction

        try:
            logger.debug(f"Looking for agency with token: {token}, center_id: {center_id}")

            # Build the filter
            filter_kwargs = {
                'agency_token': token,
                'is_agency': True,
            }
            
            # If center_id is provided, scope the search to that center
            if center_id:
                filter_kwargs['center_id'] = center_id

            # First, let's check if the agency exists at all (regardless of is_used)
            all_agencies = cls.objects.filter(**filter_kwargs)
            logger.debug(f"Found {all_agencies.count()} agency(ies) with this token")

            if all_agencies.exists():
                first_agency = all_agencies.first()
                logger.debug(
                    f"Agency found: {first_agency.name}, is_used={first_agency.is_used}, center={first_agency.center}"
                )

                if first_agency.is_used:
                    logger.warning("Agency token already used!")
                    return None

            with transaction.atomic():
                # Add is_used filter for the actual fetch
                filter_kwargs['is_used'] = False
                
                # Use select_for_update to lock the row
                agency = cls.objects.select_for_update().get(**filter_kwargs)
                logger.debug(
                    f"Successfully retrieved unused agency: {agency.name} (ID: {agency.id})"
                )

                # Mark as used
                agency.is_used = True
                agency.save(update_fields=["is_used", "updated_at"])
                logger.debug(f"Marked agency {agency.name} as used")

                return agency
        except cls.DoesNotExist:
            logger.warning(f"No unused agency found with token: {token}, center_id: {center_id}")
            return None
        except ValueError as e:
            logger.error(f"ValueError in get_agency_by_token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in get_agency_by_token: {e}", exc_info=True)
            return None
            return None


# ===== Signals for Admin Notifications =====

@receiver(pre_save, sender=BotUser)
def track_user_registration(sender, instance, **kwargs):
    """Track if this is a new user registration or agency status change"""
    if instance.pk:
        try:
            old_instance = BotUser.objects.get(pk=instance.pk)
            instance._was_active = old_instance.is_active
            instance._was_agency = old_instance.is_agency
        except BotUser.DoesNotExist:
            instance._was_active = False
            instance._was_agency = False
    else:
        instance._was_active = False
        instance._was_agency = False


@receiver(post_save, sender=BotUser)
def create_user_notification(sender, instance, created, **kwargs):
    """Create admin notification when a new user completes registration"""
    try:
        # Check if user just became active (completed registration)
        was_active = getattr(instance, '_was_active', False)
        was_agency = getattr(instance, '_was_agency', False)
        
        # New user completed registration
        if instance.is_active and not was_active:
            from core.models import AdminNotification
            
            if instance.is_agency:
                AdminNotification.create_agency_notification(instance)
            else:
                AdminNotification.create_user_notification(instance)
        
        # Existing user became agency
        elif instance.is_agency and not was_agency and instance.is_active:
            from core.models import AdminNotification
            AdminNotification.create_agency_notification(instance)
            
    except Exception as e:
        logger.error(f"Failed to create user notification: {e}", exc_info=True)


class BotUserState(models.Model):
    """
    Persistent state storage for bot users during multi-step flows.
    Replaces in-memory user_data and uploaded_files dictionaries for multi-worker support.
    
    This model stores temporary data during order creation, file uploads, and payment flows.
    Data is automatically cleaned up after order completion or timeout.
    """
    
    bot_user = models.OneToOneField(
        BotUser,
        on_delete=models.CASCADE,
        related_name='state',
        verbose_name=_("Bot User"),
        primary_key=True,
    )
    
    # Current order in progress (if any)
    current_order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_states',
        verbose_name=_("Current Order"),
    )
    
    # Selected service/product during order creation
    selected_category_id = models.PositiveIntegerField(null=True, blank=True)
    selected_product_id = models.PositiveIntegerField(null=True, blank=True)
    selected_language_id = models.PositiveIntegerField(null=True, blank=True)
    copy_number = models.PositiveIntegerField(default=0)
    
    # File upload tracking
    uploaded_file_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Uploaded File IDs"),
        help_text=_("List of OrderMedia IDs for files uploaded in current session"),
    )
    total_pages = models.PositiveIntegerField(default=0)
    
    # Message tracking for cleanup (store message IDs to delete later)
    message_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Message IDs"),
        help_text=_("List of message IDs to clean up"),
    )
    totals_message_id = models.BigIntegerField(null=True, blank=True)
    last_instruction_message_id = models.BigIntegerField(null=True, blank=True)
    
    # Payment tracking
    pending_payment_order_id = models.PositiveIntegerField(null=True, blank=True)
    pending_receipt_order_id = models.PositiveIntegerField(null=True, blank=True)
    
    # Generic extra data for edge cases (JSON field for flexibility)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Extra Data"),
        help_text=_("Additional temporary data during flows"),
    )
    
    # Timestamps for cleanup
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Bot User State")
        verbose_name_plural = _("Bot User States")
        indexes = [
            models.Index(fields=['updated_at']),
        ]
    
    def __str__(self):
        return f"State for {self.bot_user}"
    
    def clear_order_state(self):
        """Clear all order-related state after order completion or cancellation"""
        self.current_order = None
        self.selected_category_id = None
        self.selected_product_id = None
        self.selected_language_id = None
        self.copy_number = 0
        self.uploaded_file_ids = []
        self.total_pages = 0
        self.message_ids = []
        self.totals_message_id = None
        self.last_instruction_message_id = None
        self.pending_payment_order_id = None
        self.pending_receipt_order_id = None
        self.extra_data = {}
        self.save()
    
    def add_message_id(self, message_id):
        """Add a message ID to the cleanup list"""
        if message_id and message_id not in self.message_ids:
            self.message_ids = self.message_ids + [message_id]
            self.save(update_fields=['message_ids', 'updated_at'])
    
    def add_uploaded_file(self, file_id):
        """Add an uploaded file ID"""
        if file_id and file_id not in self.uploaded_file_ids:
            self.uploaded_file_ids = self.uploaded_file_ids + [file_id]
            self.save(update_fields=['uploaded_file_ids', 'updated_at'])
    
    def get_extra(self, key, default=None):
        """Get a value from extra_data"""
        return self.extra_data.get(key, default)
    
    def set_extra(self, key, value):
        """Set a value in extra_data"""
        self.extra_data[key] = value
        self.save(update_fields=['extra_data', 'updated_at'])
    
    @classmethod
    def get_or_create_for_user(cls, bot_user):
        """Get or create state for a bot user"""
        state, created = cls.objects.get_or_create(bot_user=bot_user)
        return state
    
    @classmethod
    def cleanup_old_states(cls, hours=24):
        """
        Clean up states that haven't been updated in the specified hours.
        Should be called periodically via management command or celery task.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(hours=hours)
        old_states = cls.objects.filter(updated_at__lt=cutoff)
        
        # Clear state but don't delete (preserve the record)
        for state in old_states:
            state.clear_order_state()
        
        return old_states.count()
