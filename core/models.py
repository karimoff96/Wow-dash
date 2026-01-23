from django.db import models
from django.utils.translation import gettext_lazy as _


class Region(models.Model):
    """Region/Oblast of Uzbekistan"""
    name = models.CharField(_("Name"), max_length=100)
    code = models.CharField(_("Code"), max_length=10, unique=True)
    is_active = models.BooleanField(_("Active"), default=True)
    
    class Meta:
        verbose_name = _("Region")
        verbose_name_plural = _("Regions")
        ordering = ['name']
    
    def __str__(self):
        return self.name


class District(models.Model):
    """District/Tuman within a Region"""
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='districts',
        verbose_name=_("Region")
    )
    name = models.CharField(_("Name"), max_length=100)
    code = models.CharField(_("Code"), max_length=20, unique=True)
    is_active = models.BooleanField(_("Active"), default=True)
    
    class Meta:
        verbose_name = _("District")
        verbose_name_plural = _("Districts")
        ordering = ['region', 'name']
    
    def __str__(self):
        return f"{self.name}, {self.region.name}"


class AdditionalInfo(models.Model):
    """Additional user info for flexible data storage"""
    bot_user = models.ForeignKey(
        'accounts.BotUser',
        on_delete=models.CASCADE,
        related_name='additional_info'
    )
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.CASCADE,
        related_name='customer_additional_info',
        verbose_name=_("Branch"),
        null=True,
        blank=True
    )
    title = models.CharField(_("Title"), max_length=100)
    body = models.TextField(_("Body"), blank=True, null=True)
    file = models.FileField(_("File"), upload_to='additional_info/', blank=True, null=True)
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Additional Info")
        verbose_name_plural = _("Additional Info")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.bot_user.full_name}"


class AuditLog(models.Model):
    """Model to store audit trail of user actions"""
    
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_VIEW = 'view'
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_ASSIGN = 'assign'
    ACTION_STATUS_CHANGE = 'status_change'
    ACTION_PAYMENT = 'payment'
    ACTION_OTHER = 'other'
    
    ACTION_CHOICES = [
        (ACTION_CREATE, _('Create')),
        (ACTION_UPDATE, _('Update')),
        (ACTION_DELETE, _('Delete')),
        (ACTION_VIEW, _('View')),
        (ACTION_LOGIN, _('Login')),
        (ACTION_LOGOUT, _('Logout')),
        (ACTION_ASSIGN, _('Assign')),
        (ACTION_STATUS_CHANGE, _('Status Change')),
        (ACTION_PAYMENT, _('Payment')),
        (ACTION_OTHER, _('Other')),
    ]
    
    # Who performed the action
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_("User")
    )
    
    # What action was performed
    action = models.CharField(
        _("Action"),
        max_length=20,
        choices=ACTION_CHOICES
    )
    
    # Target object (generic relation)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Content Type")
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Object ID"))
    
    # Human-readable target description
    target_repr = models.CharField(_("Target"), max_length=255, blank=True)
    
    # Additional details
    details = models.TextField(_("Details"), blank=True, null=True)
    changes = models.JSONField(_("Changes"), default=dict, blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField(_("IP Address"), null=True, blank=True)
    user_agent = models.TextField(_("User Agent"), blank=True, null=True)
    
    # Branch/Center context for filtering
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_("Branch")
    )
    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name=_("Translation Center")
    )
    
    # Timestamp
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['branch', 'created_at']),
            models.Index(fields=['center', 'created_at']),
        ]
    
    def __str__(self):
        user_name = self.user.get_full_name() or self.user.username if self.user else 'System'
        return f"{user_name} - {self.get_action_display()} - {self.target_repr}"


class AdminNotification(models.Model):
    """Notification model for admin panel bell notifications"""
    
    TYPE_RECEIPT_PENDING = 'receipt_pending'
    TYPE_ORDER_NEW = 'order_new'
    TYPE_ORDER_CANCELLED = 'order_cancelled'
    TYPE_ORDER_COMPLETED = 'order_completed'
    TYPE_PAYMENT_CONFIRMED = 'payment_confirmed'
    TYPE_USER_NEW = 'user_new'
    TYPE_AGENCY_NEW = 'agency_new'
    TYPE_OTHER = 'other'
    
    TYPE_CHOICES = [
        (TYPE_RECEIPT_PENDING, _('Receipt Pending Verification')),
        (TYPE_ORDER_NEW, _('New Order')),
        (TYPE_ORDER_CANCELLED, _('Order Cancelled')),
        (TYPE_ORDER_COMPLETED, _('Order Completed')),
        (TYPE_PAYMENT_CONFIRMED, _('Payment Confirmed')),
        (TYPE_USER_NEW, _('New User Registered')),
        (TYPE_AGENCY_NEW, _('New Agency Registered')),
        (TYPE_OTHER, _('Other')),
    ]
    
    # Notification type
    notification_type = models.CharField(
        _("Type"),
        max_length=30,
        choices=TYPE_CHOICES,
        default=TYPE_OTHER
    )
    
    # Related object (generic relation)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        verbose_name=_("Content Type")
    )
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))
    
    # Notification content
    title = models.CharField(_("Title"), max_length=255)
    message = models.TextField(_("Message"), blank=True)
    
    # Branch/Center context for filtering
    branch = models.ForeignKey(
        'organizations.Branch',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_notifications',
        verbose_name=_("Branch")
    )
    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_notifications',
        verbose_name=_("Translation Center")
    )
    
    # Read status
    is_read = models.BooleanField(_("Is Read"), default=False)
    read_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='read_notifications',
        verbose_name=_("Read By")
    )
    read_at = models.DateTimeField(_("Read At"), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = _("Admin Notification")
        verbose_name_plural = _("Admin Notifications")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read', 'created_at']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['branch', 'is_read']),
            models.Index(fields=['center', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title}"
    
    def mark_as_read(self, user):
        """Mark notification as read"""
        from django.utils import timezone
        self.is_read = True
        self.read_by = user
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_by', 'read_at'])
    
    def get_link_id(self):
        """Get the ID to use for linking - for receipts, return order ID"""
        if self.notification_type == self.TYPE_RECEIPT_PENDING:
            # For receipts, we need to get the order ID
            try:
                from orders.models import Receipt
                receipt = Receipt.objects.get(pk=self.object_id)
                return receipt.order_id
            except:
                return self.object_id
        return self.object_id
    
    @classmethod
    def create_receipt_notification(cls, receipt):
        """Create a notification for a new receipt upload"""
        from django.contrib.contenttypes.models import ContentType
        
        order = receipt.order
        customer_name = order.bot_user.full_name if order.bot_user else "Unknown"
        
        return cls.objects.create(
            notification_type=cls.TYPE_RECEIPT_PENDING,
            content_type=ContentType.objects.get_for_model(receipt),
            object_id=receipt.id,
            title=f"💳 Receipt - Order #{order.id}",
            message=f"{customer_name} uploaded a receipt for {receipt.amount:,.0f} UZS",
            branch=order.branch,
            center=order.branch.center if order.branch else None,
        )
    
    @classmethod
    def create_order_notification(cls, order):
        """Create a notification for a new order"""
        from django.contrib.contenttypes.models import ContentType
        
        customer_name = order.bot_user.full_name if order.bot_user else "Unknown"
        
        return cls.objects.create(
            notification_type=cls.TYPE_ORDER_NEW,
            content_type=ContentType.objects.get_for_model(order),
            object_id=order.id,
            title=f"📋 New Order #{order.id}",
            message=f"{customer_name} - {order.product.name} ({order.total_pages} pages) - {order.total_price:,.0f} UZS",
            branch=order.branch,
            center=order.branch.center if order.branch else None,
        )
    
    @classmethod
    def create_cancelled_notification(cls, order):
        """Create a notification when an order is cancelled"""
        from django.contrib.contenttypes.models import ContentType
        
        customer_name = order.bot_user.full_name if order.bot_user else "Unknown"
        
        return cls.objects.create(
            notification_type=cls.TYPE_ORDER_CANCELLED,
            content_type=ContentType.objects.get_for_model(order),
            object_id=order.id,
            title=f"❌ Order #{order.id} Cancelled",
            message=f"{customer_name}'s order has been cancelled",
            branch=order.branch,
            center=order.branch.center if order.branch else None,
        )
    
    @classmethod
    def create_completed_notification(cls, order):
        """Create a notification when an order is completed"""
        from django.contrib.contenttypes.models import ContentType
        
        customer_name = order.bot_user.full_name if order.bot_user else "Unknown"
        
        return cls.objects.create(
            notification_type=cls.TYPE_ORDER_COMPLETED,
            content_type=ContentType.objects.get_for_model(order),
            object_id=order.id,
            title=f"✅ Order #{order.id} Completed",
            message=f"{customer_name}'s order completed - {order.total_price:,.0f} UZS",
            branch=order.branch,
            center=order.branch.center if order.branch else None,
        )
    
    @classmethod
    def create_payment_notification(cls, order, amount):
        """Create a notification when payment is confirmed"""
        from django.contrib.contenttypes.models import ContentType
        
        customer_name = order.bot_user.full_name if order.bot_user else "Unknown"
        
        return cls.objects.create(
            notification_type=cls.TYPE_PAYMENT_CONFIRMED,
            content_type=ContentType.objects.get_for_model(order),
            object_id=order.id,
            title=f"💰 Payment - Order #{order.id}",
            message=f"{customer_name} - {amount:,.0f} UZS received",
            branch=order.branch,
            center=order.branch.center if order.branch else None,
        )
    
    @classmethod
    def create_user_notification(cls, user):
        """Create a notification for a new user registration"""
        from django.contrib.contenttypes.models import ContentType
        
        return cls.objects.create(
            notification_type=cls.TYPE_USER_NEW,
            content_type=ContentType.objects.get_for_model(user),
            object_id=user.id,
            title=f"👤 New User",
            message=f"{user.name} registered ({user.phone})",
            branch=user.branch,
            center=user.center,
        )
    
    @classmethod
    def create_agency_notification(cls, agency):
        """Create a notification for a new agency registration"""
        from django.contrib.contenttypes.models import ContentType
        
        return cls.objects.create(
            notification_type=cls.TYPE_AGENCY_NEW,
            content_type=ContentType.objects.get_for_model(agency),
            object_id=agency.id,
            title=f"🏢 New Agency",
            message=f"{agency.name} registered as agency ({agency.phone})",
            branch=agency.branch,
            center=agency.center,
        )
    
    @classmethod
    def get_unread_for_user(cls, user, limit=10):
        """Get unread notifications for a user based on their permissions"""
        from organizations.models import AdminUser
        
        # Superuser sees all notifications
        if user.is_superuser:
            return cls.objects.filter(is_read=False)[:limit]
        
        try:
            profile = user.admin_profile
            if profile.role and profile.role.name == 'owner':
                # Owner sees all for their center
                return cls.objects.filter(is_read=False, center=profile.center)[:limit]
            elif profile.branch:
                # Branch staff see branch notifications
                return cls.objects.filter(
                    is_read=False,
                    branch=profile.branch
                )[:limit]
            elif profile.center:
                # Center-level staff see center notifications
                return cls.objects.filter(
                    is_read=False,
                    center=profile.center
                )[:limit]
            else:
                return cls.objects.filter(is_read=False)[:limit]
        except (AttributeError, AdminUser.DoesNotExist):
            return cls.objects.none()
    
    @classmethod
    def count_unread_for_user(cls, user):
        """Count unread notifications for a user"""
        from organizations.models import AdminUser
        
        # Superuser sees all notifications
        if user.is_superuser:
            return cls.objects.filter(is_read=False).count()
        
        try:
            profile = user.admin_profile
            if profile.role and profile.role.name == 'owner':
                # Owner sees all for their center
                return cls.objects.filter(is_read=False, center=profile.center).count()
            elif profile.branch:
                # Branch staff see branch notifications
                return cls.objects.filter(
                    is_read=False,
                    branch=profile.branch
                ).count()
            elif profile.center:
                # Center-level staff see center notifications
                return cls.objects.filter(
                    is_read=False,
                    center=profile.center
                ).count()
            else:
                return cls.objects.filter(is_read=False).count()
        except (AttributeError, AdminUser.DoesNotExist):
            return 0


class FileArchive(models.Model):
    """Model to track archived files uploaded to Telegram"""
    
    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='file_archives',
        verbose_name=_("Center")
    )
    
    archive_name = models.CharField(
        max_length=255,
        verbose_name=_("Archive Name"),
        help_text=_("Name of the archive file")
    )
    
    archive_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("Local Archive Path"),
        help_text=_("Path to archive file if still stored locally")
    )
    
    telegram_message_id = models.BigIntegerField(
        verbose_name=_("Telegram Message ID"),
        help_text=_("Message ID in Telegram channel where archive is stored")
    )
    
    telegram_channel_id = models.CharField(
        max_length=100,
        verbose_name=_("Telegram Channel ID"),
        help_text=_("Channel ID where archive is uploaded")
    )
    
    total_orders = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Total Orders"),
        help_text=_("Number of orders included in archive")
    )
    
    total_size_bytes = models.BigIntegerField(
        default=0,
        verbose_name=_("Total Size (bytes)"),
        help_text=_("Total size of archived files in bytes")
    )
    
    archive_date = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Archive Date"),
        help_text=_("When the archive was created")
    )
    
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_archives',
        verbose_name=_("Created By")
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Additional notes about this archive")
    )
    
    class Meta:
        verbose_name = _("File Archive")
        verbose_name_plural = _("File Archives")
        ordering = ['-archive_date']
        indexes = [
            models.Index(fields=['center', '-archive_date']),
            models.Index(fields=['telegram_message_id']),
        ]
    
    def __str__(self):
        return f"{self.archive_name} - {self.center.name}"
    
    @property
    def size_mb(self):
        """Get archive size in MB"""
        return self.total_size_bytes / (1024 * 1024)
    
    @property
    def telegram_file_url(self):
        """Get Telegram file URL (for reference)"""
        # Note: Actual file download requires bot API call
        return f"https://t.me/c/{self.telegram_channel_id}/{self.telegram_message_id}"
