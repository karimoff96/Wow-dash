"""
Marketing Models for Broadcast System

Handles marketing posts, broadcast campaigns, and delivery tracking
with multi-tenant support.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class MarketingPost(models.Model):
    """
    Marketing post for broadcasting to customers via Telegram.
    Supports multi-tenant architecture with proper scope boundaries.
    """
    
    # Target scope choices
    SCOPE_ALL = 'all'  # Platform-wide (superuser only)
    SCOPE_CENTER = 'center'  # All branches of a center (owner only)
    SCOPE_BRANCH = 'branch'  # Specific branch (manager+)
    SCOPE_CUSTOM = 'custom'  # Custom segment (future use)
    
    TARGET_SCOPE_CHOICES = [
        (SCOPE_ALL, _('All Users (Platform-wide)')),
        (SCOPE_CENTER, _('Center Users')),
        (SCOPE_BRANCH, _('Branch Users')),
        (SCOPE_CUSTOM, _('Custom Segment')),
    ]
    
    # Status choices
    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_PAUSED = 'paused'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_DRAFT, _('Draft')),
        (STATUS_SCHEDULED, _('Scheduled')),
        (STATUS_SENDING, _('Sending')),
        (STATUS_SENT, _('Sent')),
        (STATUS_PAUSED, _('Paused')),
        (STATUS_FAILED, _('Failed')),
        (STATUS_CANCELLED, _('Cancelled')),
    ]
    
    # Content type choices
    CONTENT_TEXT = 'text'
    CONTENT_PHOTO = 'photo'
    CONTENT_VIDEO = 'video'
    CONTENT_DOCUMENT = 'document'
    
    CONTENT_TYPE_CHOICES = [
        (CONTENT_TEXT, _('Text Only')),
        (CONTENT_PHOTO, _('Photo with Caption')),
        (CONTENT_VIDEO, _('Video with Caption')),
        (CONTENT_DOCUMENT, _('Document with Caption')),
    ]
    
    # Basic fields
    title = models.CharField(
        _('Title'),
        max_length=200,
        help_text=_('Internal title for identification')
    )
    content = models.TextField(
        _('Message Content'),
        help_text=_('Message text (supports HTML: <b>, <i>, <a>, <code>)')
    )
    content_type = models.CharField(
        _('Content Type'),
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default=CONTENT_TEXT
    )
    media_file = models.FileField(
        _('Media File'),
        upload_to='marketing/media/%Y/%m/',
        blank=True,
        null=True,
        help_text=_('Image, video, or document to send with message')
    )
    
    # Targeting
    target_scope = models.CharField(
        _('Target Scope'),
        max_length=20,
        choices=TARGET_SCOPE_CHOICES,
        default=SCOPE_BRANCH
    )
    target_center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='marketing_posts',
        verbose_name=_('Target Center'),
        help_text=_('Required for center/branch scope')
    )
    target_branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='marketing_posts',
        verbose_name=_('Target Branch'),
        help_text=_('Required for branch scope')
    )
    
    # Customer type filter
    include_b2c = models.BooleanField(
        _('Include B2C Customers'),
        default=True,
        help_text=_('Send to individual customers')
    )
    include_b2b = models.BooleanField(
        _('Include B2B Customers'),
        default=True,
        help_text=_('Send to agency customers')
    )
    
    # Scheduling
    scheduled_at = models.DateTimeField(
        _('Scheduled Time'),
        null=True,
        blank=True,
        help_text=_('Leave empty to send immediately')
    )
    
    # Status tracking
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT
    )
    
    # Delivery statistics
    total_recipients = models.PositiveIntegerField(
        _('Total Recipients'),
        default=0
    )
    sent_count = models.PositiveIntegerField(
        _('Sent Count'),
        default=0
    )
    delivered_count = models.PositiveIntegerField(
        _('Delivered Count'),
        default=0
    )
    failed_count = models.PositiveIntegerField(
        _('Failed Count'),
        default=0
    )
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_posts',
        verbose_name=_('Created By')
    )
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    sent_at = models.DateTimeField(_('Sent At'), null=True, blank=True)
    completed_at = models.DateTimeField(_('Completed At'), null=True, blank=True)
    
    # Error tracking
    last_error = models.TextField(
        _('Last Error'),
        blank=True,
        null=True
    )
    
    class Meta:
        verbose_name = _('Marketing Post')
        verbose_name_plural = _('Marketing Posts')
        ordering = ['-created_at']
        permissions = [
            ('can_send_platform_wide', 'Can send platform-wide broadcasts'),
            ('can_send_center_wide', 'Can send center-wide broadcasts'),
            ('can_send_branch', 'Can send branch broadcasts'),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    @property
    def is_sendable(self):
        """Check if post can be sent"""
        return self.status in [self.STATUS_DRAFT, self.STATUS_SCHEDULED, self.STATUS_PAUSED]
    
    @property
    def delivery_percentage(self):
        """Calculate delivery success rate"""
        if self.sent_count == 0:
            return 0
        return round((self.delivered_count / self.sent_count) * 100, 1)
    
    @property
    def pending_count(self):
        """Calculate pending recipients (sent but not yet delivered or failed)"""
        return max(0, self.sent_count - self.delivered_count - self.failed_count)
    
    @property
    def is_scheduled(self):
        """Check if post is scheduled for future"""
        if not self.scheduled_at:
            return False
        return self.scheduled_at > timezone.now()
    
    def get_scope_display_full(self):
        """Get full scope description"""
        if self.target_scope == self.SCOPE_ALL:
            return _('All Platform Users')
        elif self.target_scope == self.SCOPE_CENTER:
            return f"{_('Center')}: {self.target_center.name if self.target_center else 'N/A'}"
        elif self.target_scope == self.SCOPE_BRANCH:
            return f"{_('Branch')}: {self.target_branch.name if self.target_branch else 'N/A'}"
        return self.get_target_scope_display()


class BroadcastRecipient(models.Model):
    """
    Tracks individual recipient delivery status.
    Used for detailed delivery reporting and retry logic.
    """
    
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_FAILED = 'failed'
    STATUS_BLOCKED = 'blocked'
    STATUS_SKIPPED = 'skipped'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, _('Pending')),
        (STATUS_SENT, _('Sent')),
        (STATUS_DELIVERED, _('Delivered')),
        (STATUS_FAILED, _('Failed')),
        (STATUS_BLOCKED, _('Blocked by User')),
        (STATUS_SKIPPED, _('Skipped (Opted Out)')),
    ]
    
    post = models.ForeignKey(
        MarketingPost,
        on_delete=models.CASCADE,
        related_name='recipients',
        verbose_name=_('Marketing Post')
    )
    bot_user = models.ForeignKey(
        'accounts.BotUser',
        on_delete=models.CASCADE,
        related_name='broadcast_receipts',
        verbose_name=_('Recipient')
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    telegram_message_id = models.BigIntegerField(
        _('Telegram Message ID'),
        null=True,
        blank=True
    )
    error_message = models.TextField(
        _('Error Message'),
        blank=True,
        null=True
    )
    retry_count = models.PositiveSmallIntegerField(
        _('Retry Count'),
        default=0
    )
    sent_at = models.DateTimeField(
        _('Sent At'),
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = _('Broadcast Recipient')
        verbose_name_plural = _('Broadcast Recipients')
        unique_together = ['post', 'bot_user']
        indexes = [
            models.Index(fields=['post', 'status']),
            models.Index(fields=['bot_user', 'sent_at']),
        ]
    
    def __str__(self):
        return f"{self.post.title} -> {self.bot_user.display_name}"


class UserBroadcastPreference(models.Model):
    """
    User preferences for receiving broadcasts.
    Implements opt-out functionality.
    """
    
    bot_user = models.OneToOneField(
        'accounts.BotUser',
        on_delete=models.CASCADE,
        related_name='broadcast_preference',
        verbose_name=_('User')
    )
    receive_marketing = models.BooleanField(
        _('Receive Marketing Messages'),
        default=True,
        help_text=_('User can opt out of marketing messages')
    )
    receive_promotions = models.BooleanField(
        _('Receive Promotions'),
        default=True
    )
    receive_updates = models.BooleanField(
        _('Receive Updates'),
        default=True
    )
    last_broadcast_at = models.DateTimeField(
        _('Last Broadcast Received'),
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User Broadcast Preference')
        verbose_name_plural = _('User Broadcast Preferences')
    
    def __str__(self):
        return f"{self.bot_user.display_name} preferences"


class BroadcastRateLimit(models.Model):
    """
    Rate limiting configuration for broadcasts.
    Prevents spam and respects Telegram limits.
    """
    
    center = models.OneToOneField(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='broadcast_rate_limit',
        verbose_name=_('Center')
    )
    
    # Messages per second (Telegram allows ~30 msg/sec for regular bots)
    messages_per_second = models.PositiveSmallIntegerField(
        _('Messages Per Second'),
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text=_('Max messages per second (Telegram limit: 30)')
    )
    
    # Daily limit per user (anti-spam)
    daily_limit_per_user = models.PositiveSmallIntegerField(
        _('Daily Limit Per User'),
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text=_('Max broadcasts per user per day')
    )
    
    # Batch size for processing
    batch_size = models.PositiveSmallIntegerField(
        _('Batch Size'),
        default=50,
        validators=[MinValueValidator(10), MaxValueValidator(100)]
    )
    
    # Delay between batches (seconds)
    batch_delay = models.PositiveSmallIntegerField(
        _('Batch Delay (seconds)'),
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Broadcast Rate Limit')
        verbose_name_plural = _('Broadcast Rate Limits')
    
    def __str__(self):
        return f"Rate limits for {self.center.name}"
    
    @classmethod
    def get_or_create_for_center(cls, center):
        """Get or create rate limit config for a center"""
        obj, _ = cls.objects.get_or_create(center=center)
        return obj
