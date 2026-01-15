import logging
from django.db import models
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from accounts.models import BotUser
from organizations.models import Branch, AdminUser
from services.models import Language, Product

logger = logging.getLogger(__name__)

# Create your models here.


class OrderMedia(models.Model):
    file = models.FileField(upload_to="order_media/", max_length=500, verbose_name=_("File"))
    pages = models.PositiveIntegerField(default=1, verbose_name=_("Pages"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        return f"{self.file.name} ({self.pages} pages)"

    class Meta:
        verbose_name = _("Order file")
        verbose_name_plural = _("Order media")


class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", _("Pending")),  # Order created, awaiting payment
        ("payment_pending", _("Awaiting")),  # Card payment, waiting for receipt
        ("payment_received", _("Received")),  # Receipt uploaded
        ("payment_confirmed", _("Confirmed")),  # Payment verified by admin
        ("in_progress", _("In Process")),  # Order being processed
        ("ready", _("Ready")),  # Order completed, ready for pickup
        ("completed", _("Done")),  # Order delivered
        ("cancelled", _("Cancelled")),  # Order cancelled
    )

    PAYMENT_TYPE = (
        ("cash", _("Cash")),
        ("card", _("Card")),
    )

    # Branch relationship - orders belong to specific branches
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name=_("Branch"),
        null=True,
        blank=True,
    )

    bot_user = models.ForeignKey(
        BotUser, 
        on_delete=models.CASCADE, 
        verbose_name=_("Telegram User"),
        null=True,
        blank=True,
        help_text=_("Leave empty for manual orders")
    )
    
    # Manual order fields (when bot_user is null)
    manual_first_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("First Name"),
        help_text=_("Customer first name for manual orders")
    )
    manual_last_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Last Name"),
        help_text=_("Customer last name for manual orders")
    )
    manual_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_("Phone Number"),
        help_text=_("Customer phone number for manual orders")
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, verbose_name=_("Document Type")
    )
    total_pages = models.PositiveIntegerField(default=1, verbose_name=_("Total Pages"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name=_("Status"),
    )
    is_active = models.BooleanField(default=False, verbose_name=_("Is Active"))
    description = models.TextField(verbose_name=_("Description"), blank=True, null=True)
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Translation Language"),
        help_text=_(
            "The target language selected by user from category's available languages"
        ),
    )
    payment_type = models.CharField(
        max_length=100,
        choices=PAYMENT_TYPE,
        default="cash",
        verbose_name=_("Payment Type"),
    )
    recipt = models.FileField(
        upload_to="recipts/", blank=True, null=True, verbose_name=_("Receipt"),
        max_length=255,
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Total Price")
    )
    copy_number = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Number of Copies"),
        help_text=_("Additional copies needed (0 means only original)"),
    )
    files = models.ManyToManyField(OrderMedia, verbose_name=_("Files"))

    # Staff assignment fields
    assigned_to = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
        verbose_name=_("Assigned To"),
        limit_choices_to={"role__name": "staff"},
    )
    assigned_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_assigned",
        verbose_name=_("Assigned By"),
        limit_choices_to={"role__name__in": ["owner", "manager"]},
    )
    assigned_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Assigned At")
    )

    # Payment tracking
    payment_received_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_received",
        verbose_name=_("Payment Received By"),
    )
    payment_received_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Payment Received At")
    )
    
    # Partial payment support
    received = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Amount Received"),
        help_text=_("Total amount received so far"),
    )
    extra_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name=_("Extra Fee"),
        help_text=_("Additional charges (rush fee, special handling, etc.)"),
    )
    extra_fee_description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Extra Fee Description"),
        help_text=_("Reason for the extra fee"),
    )
    payment_accepted_fully = models.BooleanField(
        default=False,
        verbose_name=_("Payment Accepted Fully"),
        help_text=_("Mark as True to consider payment complete regardless of received amount"),
    )

    # Order completion tracking
    completed_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_orders",
        verbose_name=_("Completed By"),
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Completed At")
    )
    
    # Center-specific order numbering
    # SAFETY: This field is nullable so existing code won't break if migration isn't run
    center_order_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Center Order Number"),
        help_text=_("Sequential order number within the center (auto-generated)")
    )

    def __str__(self):
        customer_name = self.get_customer_display_name()
        order_num = self.get_order_number()
        return f"Order #{order_num} - {customer_name} - {self.product} ({self.total_pages} pages)"
    
    def get_order_number(self):
        """Get order number - uses center_order_number if available, falls back to id"""
        # SAFETY: Fallback to id if center_order_number doesn't exist or is None
        if hasattr(self, 'center_order_number') and self.center_order_number is not None:
            return self.center_order_number
        return self.id
    
    def get_customer_display_name(self):
        """Get customer name from bot_user or manual fields"""
        if self.bot_user:
            return self.bot_user.display_name
        elif self.manual_first_name or self.manual_last_name:
            name_parts = [self.manual_first_name, self.manual_last_name]
            return " ".join(filter(None, name_parts))
        else:
            return _("Unknown Customer")
    
    def get_customer_phone(self):
        """Get customer phone from bot_user or manual field"""
        if self.bot_user:
            return self.bot_user.phone
        return self.manual_phone or "N/A"
    
    @property
    def center(self):
        """Get center from branch - safely handles missing branch"""
        if self.branch and hasattr(self.branch, 'center'):
            return self.branch.center
        return None
    
    @property
    def is_manual_order(self):
        """Check if this is a manually created order (no bot_user)"""
        return self.bot_user is None

    @property
    def calculated_price(self):
        """Calculate price based on user type, total pages, and copy number"""
        # Determine if user is agency (default to False for manual orders)
        is_agency = self.bot_user.is_agency if self.bot_user and hasattr(self.bot_user, 'is_agency') else False
        
        base_price = self.product.get_price_for_user_type(
            is_agency=is_agency, pages=self.total_pages
        )

        # Add copy charges if copy_number > 0
        if self.copy_number > 0:
            copy_percentage = (
                self.product.agency_copy_price_percentage
                if is_agency
                else self.product.user_copy_price_percentage
            )
            copy_charge = (base_price * copy_percentage * self.copy_number) / 100
            return base_price + copy_charge

        return base_price

    @property
    def total_due(self):
        """Total amount due including extra fees"""
        from decimal import Decimal
        return Decimal(str(self.total_price or 0)) + Decimal(str(self.extra_fee or 0))

    @property
    def remaining(self):
        """
        Calculate remaining balance.
        Returns 0 if payment_accepted_fully is True.
        Otherwise returns total_due - received.
        """
        from decimal import Decimal
        if self.payment_accepted_fully:
            return Decimal('0.00')
        return max(Decimal('0.00'), self.total_due - Decimal(str(self.received or 0)))

    @property
    def is_fully_paid(self):
        """Check if order is fully paid"""
        return self.payment_accepted_fully or self.remaining <= 0

    @property
    def payment_percentage(self):
        """Calculate payment progress percentage"""
        if self.total_due <= 0:
            return 100
        if self.payment_accepted_fully:
            return 100
        from decimal import Decimal
        received = Decimal(str(self.received or 0))
        return min(100, int((received / self.total_due) * 100))

    @property
    def category(self):
        """Get main service from document type"""
        return self.product.category

    @property
    def available_languages(self):
        """Get available languages from product's category"""
        if self.product and self.product.category:
            return self.product.category.languages.all()
        return Language.objects.none()

    def is_valid_language(self, language):
        """Check if the given language is valid for this order's category"""
        if not language:
            return True  # Allow null
        return self.available_languages.filter(pk=language.pk).exists()

    @property
    def complexity_level(self):
        """Get complexity level from document type"""
        return self.product.complexity_level

    @property
    def service_category(self):
        """Get service category from document type"""
        return self.product.service_category

    @property
    def estimated_days(self):
        """Get estimated days from document type"""
        return self.product.estimated_days

    def update_total_pages(self):
        """Update total pages from all files"""
        self.total_pages = self.files.aggregate(total=models.Sum("pages"))["total"] or 0
        return self.total_pages

    def assign_to_staff(self, staff_member, assigned_by):
        """Assign this order to a staff member"""
        self.assigned_to = staff_member
        self.assigned_by = assigned_by
        self.assigned_at = timezone.now()
        self.status = "in_progress"
        self.save(
            update_fields=[
                "assigned_to",
                "assigned_by",
                "assigned_at",
                "status",
                "updated_at",
            ]
        )

    def mark_payment_received(self, received_by, amount=None, accept_fully=False):
        """
        Mark payment as received.
        
        Args:
            received_by: AdminUser who received the payment
            amount: Decimal amount received (if partial payment)
            accept_fully: If True, marks payment as fully accepted regardless of amount
        """
        from decimal import Decimal
        
        self.payment_received_by = received_by
        self.payment_received_at = timezone.now()
        
        if accept_fully:
            self.payment_accepted_fully = True
            self.received = self.total_due
            self.status = "payment_confirmed"
        elif amount is not None:
            self.received = Decimal(str(self.received or 0)) + Decimal(str(amount))
            # Auto-confirm if fully paid
            if self.remaining <= 0:
                self.status = "payment_confirmed"
            else:
                self.status = "payment_received"  # Partial payment received
        else:
            # Legacy behavior - mark as confirmed
            self.status = "payment_confirmed"
        
        self.save(
            update_fields=[
                "payment_received_by",
                "payment_received_at",
                "received",
                "payment_accepted_fully",
                "status",
                "updated_at",
            ]
        )

    def mark_completed(self, completed_by):
        """Mark order as completed"""
        self.completed_by = completed_by
        self.completed_at = timezone.now()
        self.status = "completed"
        
        # Auto-assign to completer if not already assigned
        update_fields = ["completed_by", "completed_at", "status", "updated_at"]
        if not self.assigned_to and completed_by:
            self.assigned_to = completed_by
            update_fields.append("assigned_to")
        
        self.save(update_fields=update_fields)

    def save(self, *args, **kwargs):
        # Get update_fields to check if this is a partial update
        update_fields = kwargs.get('update_fields')
        
        # Auto-set branch from bot_user if not set (only on full save)
        if not update_fields:
            if not self.branch and self.bot_user and self.bot_user.branch:
                self.branch = self.bot_user.branch

        # Validate language only on full save or when language is being updated
        # Skip validation for payment-only updates
        should_validate_language = (
            not update_fields or 
            'language' in update_fields or 
            'product' in update_fields
        )
        
        if should_validate_language and self.language and self.product and self.product.category:
            available_languages = self.product.category.languages.all()
            if (
                available_languages.exists()
                and not available_languages.filter(pk=self.language.pk).exists()
            ):
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    {
                        "language": _(
                            "Selected language is not available for this product's category."
                        )
                    }
                )

        # Update total pages before calculating price (only on full save)
        if not update_fields and hasattr(self, "_update_pages") and self._update_pages:
            self.update_total_pages()

        # Auto-calculate total price based on pages and user type (only on full save)
        if not update_fields and (not self.total_price or self.total_pages):
            self.total_price = self.calculated_price

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ["-created_at"]


class Receipt(models.Model):
    """
    Payment receipts/proofs for orders.
    Supports multiple receipts per order for partial payments.
    """
    SOURCE_CHOICES = (
        ("bot", _("Bot (User Upload)")),
        ("admin", _("Admin Upload")),
        ("phone", _("Phone Confirmation")),
    )
    
    STATUS_CHOICES = (
        ("pending", _("Pending Verification")),
        ("verified", _("Verified")),
        ("rejected", _("Rejected")),
    )
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name=_("Order"),
    )
    file = models.FileField(
        upload_to="receipts/%Y/%m/",
        blank=True,
        null=True,
        max_length=255,
        verbose_name=_("Receipt File"),
        help_text=_("Receipt image or document"),
    )
    telegram_file_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Telegram File ID"),
        help_text=_("File ID from Telegram for quick access"),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Amount"),
        help_text=_("Amount claimed in this receipt"),
    )
    verified_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_("Verified Amount"),
        help_text=_("Amount verified by admin"),
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="bot",
        verbose_name=_("Source"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name=_("Status"),
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Comment"),
        help_text=_("Admin notes or rejection reason"),
    )
    uploaded_by_user = models.ForeignKey(
        BotUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_receipts",
        verbose_name=_("Uploaded By (User)"),
    )
    verified_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_receipts",
        verbose_name=_("Verified By"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Verified At"),
    )
    
    def __str__(self):
        return f"Receipt #{self.id} for Order #{self.order_id} - {self.get_status_display()}"
    
    def verify(self, admin_user, amount=None, comment=None):
        """Verify this receipt and update order payment"""
        from decimal import Decimal
        
        self.status = "verified"
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        
        if amount is not None:
            self.verified_amount = Decimal(str(amount))
        else:
            self.verified_amount = self.amount
        
        if comment:
            self.comment = comment
        
        self.save()
        
        # Update order's received amount
        self.order.received = Decimal(str(self.order.received or 0)) + self.verified_amount
        self.order.save(update_fields=['received', 'updated_at'])
        
        return self
    
    def reject(self, admin_user, comment=None):
        """Reject this receipt"""
        self.status = "rejected"
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.verified_amount = 0
        
        if comment:
            self.comment = comment
        
        self.save()
        return self
    
    class Meta:
        verbose_name = _("Receipt")
        verbose_name_plural = _("Receipts")
        ordering = ["-created_at"]


@receiver(pre_save, sender=Order)
def set_center_order_number(sender, instance, **kwargs):
    """
    Generate sequential order number per center.
    SAFETY: Only runs for new orders and handles missing field gracefully.
    """
    # Only for new orders that don't have a number yet
    if not instance.pk and hasattr(instance, 'center_order_number'):
        try:
            # Get the center from branch
            if instance.branch and hasattr(instance.branch, 'center'):
                center = instance.branch.center
                if center:
                    # Get the highest center_order_number for this center
                    # SAFETY: Use filter to handle None values
                    from django.db.models import Max
                    max_number = Order.objects.filter(
                        branch__center=center,
                        center_order_number__isnull=False
                    ).aggregate(Max('center_order_number'))['center_order_number__max']
                    
                    # Set the next number (start at 1 if no orders exist)
                    instance.center_order_number = (max_number or 0) + 1
                    logger.info(f"✅ Generated center order number {instance.center_order_number} for center {center.name}")
                else:
                    logger.warning(f"⚠️ Order has branch but no center - will use order.id as fallback")
            else:
                logger.warning(f"⚠️ Order has no branch - will use order.id as fallback")
        except Exception as e:
            # SAFETY: If anything goes wrong, log and continue (will use order.id as fallback)
            logger.error(f"❌ Failed to generate center_order_number: {e}")
            instance.center_order_number = None


@receiver(pre_save, sender=Order)
def track_status_change(sender, instance, **kwargs):
    """Track status and payment changes before save"""
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
            instance._old_received = old_instance.received
            instance._old_payment_type = old_instance.payment_type
        except Order.DoesNotExist:
            instance._old_status = None
            instance._old_received = None
            instance._old_payment_type = None
    else:
        instance._old_status = None
        instance._old_received = None
        instance._old_payment_type = None
        instance._is_new = True


@receiver(post_save, sender=Order)
def send_status_notification(sender, instance, created, **kwargs):
    """Send notification after status or payment change"""
    
    # Handle new order notification (admin panel bell)
    if created:
        try:
            from core.models import AdminNotification
            AdminNotification.create_order_notification(instance)
        except Exception as e:
            logger.error(f" Failed to create new order notification: {e}")
        return
        
    # Check for status change
    if hasattr(instance, "_old_status"):
        old_status = instance._old_status
        new_status = instance.status

        if old_status != new_status:
            # Import here to avoid circular imports
            try:
                from bot.main import send_order_status_notification

                send_order_status_notification(instance, old_status, new_status)
            except Exception as e:
                logger.error(f" Failed to send status notification: {e}")
                import traceback
                traceback.print_exc()
            
            # Create admin notifications for important status changes
            try:
                from core.models import AdminNotification
                
                if new_status == 'cancelled':
                    AdminNotification.create_cancelled_notification(instance)
                elif new_status == 'completed':
                    AdminNotification.create_completed_notification(instance)
            except Exception as e:
                logger.error(f" Failed to create status change notification: {e}")
    
    # Check for payment amount change (partial payment received)
    if hasattr(instance, "_old_received"):
        old_received = instance._old_received or 0
        new_received = instance.received or 0
        
        if new_received > old_received and new_received > 0:
            amount_received = new_received - old_received
            
            # Send bot notification to user
            try:
                from bot.main import send_payment_received_notification
                send_payment_received_notification(instance, amount_received, new_received)
            except Exception as e:
                logger.error(f" Failed to send payment notification: {e}")
                import traceback
                traceback.print_exc()
            
            # Create admin notification for payment
            try:
                from core.models import AdminNotification
                AdminNotification.create_payment_notification(instance, amount_received)
            except Exception as e:
                logger.error(f" Failed to create payment notification: {e}")


@receiver(post_save, sender=Receipt)
def create_receipt_notification(sender, instance, created, **kwargs):
    """Create an admin notification when a new receipt is uploaded"""
    if created and instance.status == 'pending':
        try:
            from core.models import AdminNotification
            AdminNotification.create_receipt_notification(instance)
        except Exception as e:
            logger.error(f" Failed to create receipt notification: {e}")
            import traceback
            traceback.print_exc()
