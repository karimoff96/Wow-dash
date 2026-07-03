import logging
from django.db import models
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from accounts.models import BotUser
from organizations.models import Branch, AdminUser
from services.models import Language, Product

logger = logging.getLogger(__name__)

# Create your models here.


def order_media_upload_path(instance, filename):
    """
    Generate a clean, short upload path for order media files.
    Format: order_media/timestamp_random.ext
    """
    import os
    import time
    import random
    
    # Get file extension, limit to 10 chars
    ext = os.path.splitext(filename)[1][:10] or '.bin'
    
    # Generate short filename: timestamp + random 4-digit number
    new_filename = f"{int(time.time())}_{random.randint(1000, 9999)}{ext}"
    
    return f"order_media/{new_filename}"


class OrderMedia(models.Model):
    file = models.FileField(
        upload_to=order_media_upload_path, 
        max_length=500, 
        verbose_name=_("File")
    )
    telegram_file_id = models.CharField(
        max_length=200, 
        null=True, 
        blank=True,
        verbose_name=_("Telegram File ID"),
        help_text=_("Telegram file ID for quick file access without downloading")
    )
    pages = models.PositiveIntegerField(default=1, verbose_name=_("Pages"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    def __str__(self):
        return f"{self.file.name} ({self.pages} pages)"
    
    def save(self, *args, **kwargs):
        """Override save to validate and clean file path - prevents future corruption without breaking existing data"""
        if self.file:
            file_path = str(self.file)
            # Check if path contains Telegram file_id pattern AND doesn't exist on disk (truly corrupted)
            if ('AgAC' in file_path or 'BAAC' in file_path):
                # Check if file actually exists - if it does, it's a legitimate filename, not corruption
                from django.core.files.storage import default_storage
                if not default_storage.exists(file_path):
                    logger.warning(f"Detected and cleaning corrupted file path: {file_path[:100]}")
                    self.file = ''
        super().save(*args, **kwargs)
    
    @property
    def file_url(self):
        """Get file URL safely, only blocking corrupted Telegram file_id paths"""
        try:
            if not self.file:
                return None
            
            file_path = str(self.file)
            
            # Only block if file contains pattern AND doesn't exist (truly corrupted)
            if ('AgAC' in file_path or 'BAAC' in file_path):
                from django.core.files.storage import default_storage
                if not default_storage.exists(file_path):
                    logger.warning(f"Blocked corrupted file path for OrderMedia {self.id}")
                    return None
            
            # Return URL for all other paths (let Django/server handle missing files)
            if hasattr(self.file, 'url'):
                return self.file.url
        except Exception as e:
            logger.error(f"Error getting file URL for OrderMedia {self.id}: {e}")
        return None
    
    @property
    def file_name(self):
        """Get file name safely"""
        try:
            if not self.file:
                return "No file"
            
            file_path = str(self.file)
            
            # Only block if pattern exists AND file doesn't exist on disk
            if ('AgAC' in file_path or 'BAAC' in file_path):
                from django.core.files.storage import default_storage
                if not default_storage.exists(file_path):
                    return "File unavailable (corrupted path)"
            
            if hasattr(self.file, 'name'):
                import os
                return os.path.basename(self.file.name)
        except Exception:
            pass
        return "Unknown file"

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
    PAYMENT_SOURCE = (
        ("manual", _("Manual")),  # Cash or manual card transfer + receipt upload
        ("payme", _("Payme")),    # Paid via Payme checkout
    )
    payment_source = models.CharField(
        max_length=20,
        choices=PAYMENT_SOURCE,
        default="manual",
        verbose_name=_("Payment Source"),
        db_index=True,
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
    name_clarifications = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Name Clarifications"),
        help_text=_("Full names typed by the user to avoid misreading handwriting"),
    )
    files = models.ManyToManyField(OrderMedia, verbose_name=_("Files"))
    additional_files = models.ManyToManyField(
        OrderMedia,
        related_name='additional_for_orders',
        blank=True,
        verbose_name=_("Additional Supply Documents"),
        help_text=_("Supplementary documents provided alongside the main order files"),
    )

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

    created_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders_created",
        verbose_name=_("Created By"),
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
    
    # Deadline (optional customer-requested completion date)
    deadline = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Deadline"),
        help_text=_("Optional date by which the order should be completed")
    )

    # File archiving
    archived_files = models.ForeignKey(
        'core.FileArchive',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name=_("Archived Files"),
        help_text=_("Reference to archive containing this order's files")
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
    def is_new(self):
        """Order has not been touched: still pending and no staff assigned."""
        return self.status == 'pending' and self.assigned_to_id is None

    @property
    def is_manual_order(self):
        """Check if this is a manually created order (no bot_user)"""
        return self.bot_user is None
    
    @property
    def is_archived(self):
        """Check if order files are archived"""
        return self.archived_files is not None
    
    @property
    def has_local_files(self):
        """Check if order files still exist locally (not deleted after archiving)"""
        import os
        
        # Check order media files
        for media in self.files.all():
            if media.file and hasattr(media.file, 'path'):
                try:
                    if os.path.exists(media.file.path):
                        return True
                except:
                    pass
        
        # Check receipt
        if self.recipt and hasattr(self.recipt, 'path'):
            try:
                if os.path.exists(self.recipt.path):
                    return True
            except:
                pass
        
        return False
    
    @property
    def files_location(self):
        """Get user-friendly description of where files are stored"""
        if self.is_archived and not self.has_local_files:
            return "archived_only"  # Files only in archive (deleted locally)
        elif self.is_archived and self.has_local_files:
            return "both"  # Files in both archive and local storage
        else:
            return "local"  # Files only in local storage
    
    def get_archive_info(self):
        """Get archive information with Telegram access link"""
        if not self.is_archived:
            return None
        
        archive = self.archived_files
        
        return {
            'archive_name': archive.archive_name,
            'archive_date': archive.archive_date,
            'total_orders': archive.total_orders,
            'size_mb': archive.size_mb,
            'telegram_link': self._get_telegram_archive_link(),
            'has_local_files': self.has_local_files,
        }
    
    def _get_telegram_archive_link(self):
        """Generate Telegram link to access archived files"""
        if not self.is_archived:
            return None
        
        archive = self.archived_files
        channel_id = archive.telegram_channel_id
        message_id = archive.telegram_message_id
        
        # Handle channel IDs (remove -100 prefix for link)
        if channel_id.startswith('-100'):
            channel_id_clean = channel_id[4:]  # Remove -100
        else:
            channel_id_clean = channel_id.lstrip('-')
        
        return f"https://t.me/c/{channel_id_clean}/{message_id}"

    @property
    def calculated_price(self):
        """Calculate price based on user type, total pages, language, and copy number"""
        # Determine if user is agency (default to False for manual orders)
        is_agency = self.bot_user.is_agency if self.bot_user and hasattr(self.bot_user, 'is_agency') else False
        
        # Use combined pricing method that includes language costs
        base_price = self.product.get_combined_total_price(
            language=self.language,
            is_agency=is_agency,
            pages=self.total_pages,
            copies=self.copy_number
        )

        return base_price

    def get_price_breakdown(self):
        """
        Get detailed price breakdown showing product and language prices separately
        Returns dict with detailed pricing information for display
        """
        from decimal import Decimal
        
        is_agency = self.bot_user.is_agency if self.bot_user and hasattr(self.bot_user, 'is_agency') else False
        
        # Product prices
        product_first_page = self.product.get_first_page_price(is_agency=is_agency)
        product_other_page = self.product.get_other_page_price(is_agency=is_agency)
        
        # Language prices (if language selected)
        language_first_page = Decimal('0.00')
        language_other_page = Decimal('0.00')
        language_copy = Decimal('0.00')
        
        if self.language:
            if is_agency:
                language_first_page = self.language.agency_page_price
                language_other_page = self.language.agency_other_page_price
                language_copy = self.language.agency_copy_price
            else:
                language_first_page = self.language.ordinary_page_price
                language_other_page = self.language.ordinary_other_page_price
                language_copy = self.language.ordinary_copy_price
        
        # Combined prices
        combined_first_page = product_first_page + language_first_page
        combined_other_page = product_other_page + language_other_page
        
        # Calculate original document price
        if self.product.category.charging == "static":
            original_price = combined_first_page
        else:
            if self.total_pages == 1:
                original_price = combined_first_page
            else:
                original_price = combined_first_page + (combined_other_page * (self.total_pages - 1))
        
        # Calculate copy price
        product_copy_price = Decimal('0.00')
        if is_agency:
            product_copy_price = self.product.agency_copy_price_decimal or Decimal('0.00')
        else:
            product_copy_price = self.product.user_copy_price_decimal or Decimal('0.00')
        
        combined_copy_price = product_copy_price + language_copy
        copy_total = combined_copy_price * self.copy_number if self.copy_number > 0 else Decimal('0.00')
        
        return {
            'is_agency': is_agency,
            'total_pages': self.total_pages,
            'copy_number': self.copy_number,
            'language_name': self.language.name if self.language else None,
            
            # Product prices
            'product_first_page': product_first_page,
            'product_other_page': product_other_page,
            'product_copy_price': product_copy_price,
            
            # Language prices
            'language_first_page': language_first_page,
            'language_other_page': language_other_page,
            'language_copy_price': language_copy,
            
            # Combined prices
            'combined_first_page': combined_first_page,
            'combined_other_page': combined_other_page,
            'combined_copy_price': combined_copy_price,
            
            # Totals
            'original_price': original_price,
            'copy_total': copy_total,
            'total_price': original_price + copy_total,
        }

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
        # Skip if the price has been manually overridden via OrderPriceChange
        if not update_fields and (not self.total_price or self.total_pages):
            price_is_locked = bool(self.pk and self.price_changes.exists())
            if not price_is_locked:
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


@receiver(post_save, sender=Order)
def track_order_creation(sender, instance, created, **kwargs):
    """Track order creation in usage statistics"""
    if created:
        try:
            # Get organization from branch
            if not instance.branch:
                return
            
            organization = instance.branch.center
            if not organization:
                return
            
            # Import here to avoid circular imports
            from billing.models import UsageTracking
            
            # Get or create tracking for current month
            tracking = UsageTracking.get_or_create_current_month(organization)
            
            # Determine if it's a bot order or manual order
            # Bot orders have bot_user with user_id (Telegram ID)
            # Manual orders have bot_user but user_id is None
            is_bot_order = bool(instance.bot_user and instance.bot_user.user_id)
            
            # Increment order counter
            tracking.increment_orders(is_bot_order=is_bot_order)
            
            logger.info(f"✓ Tracked order #{instance.id} for {organization.name} (bot={is_bot_order})")
        except Exception as e:
            logger.error(f"✗ Failed to track order creation: {e}")
            import traceback
            traceback.print_exc()


@receiver(post_save, sender=Order)
def track_order_revenue(sender, instance, **kwargs):
    """Track revenue when order status changes to paid/completed"""
    # Check if status changed to a paid status
    if hasattr(instance, '_old_status'):
        old_status = instance._old_status
        new_status = instance.status
        
        # Track revenue when order becomes paid for the first time
        paid_statuses = ['payment_confirmed', 'completed', 'ready']
        
        # Only track if transitioning TO a paid status FROM a non-paid status
        if new_status in paid_statuses and old_status not in paid_statuses:
            try:
                if not instance.branch:
                    return
                
                organization = instance.branch.center
                if not organization:
                    return
                
                # Import here to avoid circular imports
                from billing.models import UsageTracking
                from datetime import date
                
                # Get or create tracking for current month
                today = date.today()
                tracking, created = UsageTracking.objects.get_or_create(
                    organization=organization,
                    year=today.year,
                    month=today.month,
                    defaults={
                        'branches_count': organization.branches.count(),
                        'staff_count': organization.get_staff_count(),
                    }
                )
                
                # Add revenue
                tracking.total_revenue += instance.total_price
                tracking.save(update_fields=['total_revenue', 'updated_at'])
                
                logger.info(f"✓ Tracked revenue {instance.total_price} for {organization.name} (Order #{instance.id}: {old_status} → {new_status})")
            except Exception as e:
                logger.error(f"✗ Failed to track order revenue: {e}")
                import traceback
                traceback.print_exc()


@receiver(post_delete, sender=Order)
def delete_order_notifications(sender, instance, **kwargs):
    """Delete all admin notifications linked to this order when it is deleted."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from core.models import AdminNotification
        ct = ContentType.objects.get_for_model(Order)
        AdminNotification.objects.filter(content_type=ct, object_id=instance.pk).delete()
    except Exception:
        pass


@receiver(post_delete, sender=Receipt)
def delete_receipt_notifications(sender, instance, **kwargs):
    """Delete all admin notifications linked to this receipt when it is deleted."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from core.models import AdminNotification
        ct = ContentType.objects.get_for_model(Receipt)
        AdminNotification.objects.filter(content_type=ct, object_id=instance.pk).delete()
    except Exception:
        pass


@receiver(post_save, sender=Order)
def update_realtime_order_cache(sender, instance, created, **kwargs):
    """
    Update Redis cache timestamps when a new order is created.
    This powers the lightweight polling-based real-time update feature.
    Writes to:
      - realtime:orders:latest_ts            (global, for superusers)
      - realtime:orders:latest_ts:b:<id>     (per branch)
      - realtime:orders:latest_ts:c:<id>     (per center/org)
    All keys have a 24-hour TTL and are O(1) to read.
    Failures are silently swallowed so they never block order creation.
    """
    if not created:
        return
    try:
        import time
        from django.core.cache import cache

        ts = time.time()
        cache_timeout = 86400  # 24 hours

        keys = ['realtime:orders:latest_ts']
        if instance.branch_id:
            keys.append(f'realtime:orders:latest_ts:b:{instance.branch_id}')
            # Safely access center_id without triggering extra query if already
            # prefetched; fall back to a tiny query otherwise.
            center_id = getattr(instance.branch, 'center_id', None)
            if center_id is None and instance.branch_id:
                try:
                    from organizations.models import Branch
                    center_id = Branch.objects.filter(pk=instance.branch_id).values_list('center_id', flat=True).first()
                except Exception:
                    pass
            if center_id:
                keys.append(f'realtime:orders:latest_ts:c:{center_id}')

        for key in keys:
            cache.set(key, ts, timeout=cache_timeout)

        logger.debug(f"✓ Realtime cache updated for new order #{instance.id} (keys: {keys})")
    except Exception as e:
        # Never let a cache failure break order creation
        logger.warning(f"Realtime cache update skipped for order #{instance.id}: {e}")


class BulkPayment(models.Model):
    """
    Track bulk payments from customers/agencies that cover multiple orders.
    This model provides an audit trail for payment operations.
    
    MIGRATION SAFETY: All fields are nullable/optional to ensure backward compatibility
    with existing production data.
    """
    
    PAYMENT_METHOD_CHOICES = (
        ('cash', _('Cash')),
        ('bank_transfer', _('Bank Transfer')),
        ('card', _('Card Payment')),
        ('other', _('Other')),
    )
    
    # Customer who made the payment
    bot_user = models.ForeignKey(
        BotUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulk_payments',
        verbose_name=_('Customer'),
        help_text=_('The customer/agency who made the payment')
    )
    
    # Payment details
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Payment Amount'),
        help_text=_('Total amount received from customer')
    )
    
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        verbose_name=_('Payment Method')
    )
    
    # Optional receipt/note
    receipt_note = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Receipt/Note'),
        help_text=_('Transaction ID, receipt number, or any additional notes')
    )

    receipt_file = models.FileField(
        upload_to='bulk_payment_receipts/',
        blank=True,
        null=True,
        verbose_name=_('Receipt File'),
        help_text=_('Uploaded receipt image/PDF for card payments')
    )
    
    # Admin who processed the payment
    processed_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_bulk_payments',
        verbose_name=_('Processed By'),
        help_text=_('Admin user who recorded this payment')
    )
    
    # Branch context (for audit and filtering)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulk_payments',
        verbose_name=_('Branch'),
        help_text=_('Branch where payment was processed')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    # Statistics (calculated at time of payment)
    orders_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Orders Paid'),
        help_text=_('Number of orders this payment was applied to')
    )
    
    fully_paid_orders = models.PositiveIntegerField(
        default=0,
        verbose_name=_('Fully Paid Orders'),
        help_text=_('Number of orders that were fully paid by this transaction')
    )
    
    remaining_debt_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_('Remaining Debt After'),
        help_text=_('Customer remaining debt after this payment')
    )
    
    class Meta:
        verbose_name = _('Bulk Payment')
        verbose_name_plural = _('Bulk Payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['bot_user', '-created_at']),
            models.Index(fields=['branch', '-created_at']),
        ]
    
    def __str__(self):
        customer_name = self.bot_user.name if self.bot_user else "Unknown"
        return f"Payment #{self.id} - {customer_name} - {self.amount} ({self.created_at.strftime('%Y-%m-%d')})"


class OrderPriceChange(models.Model):
    """
    Audit trail for manual price changes on an order.
    Records who changed the price, when, and why.
    """
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='price_changes',
        verbose_name=_('Order'),
    )
    old_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name=_('Old Price'),
    )
    new_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name=_('New Price'),
    )
    reason = models.TextField(
        verbose_name=_('Reason'),
        help_text=_('Why was the price changed?'),
    )
    changed_by = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='price_changes_made',
        verbose_name=_('Changed By'),
    )
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Changed At'))

    class Meta:
        verbose_name = _('Order Price Change')
        verbose_name_plural = _('Order Price Changes')
        ordering = ['-changed_at']

    def __str__(self):
        return f"Order #{self.order_id}: {self.old_price} → {self.new_price}"

    @property
    def delta(self):
        return self.new_price - self.old_price


class OrderComment(models.Model):
    """
    Internal staff-only comment thread on an order.
    Comments are never visible to bot users / clients.
    """
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Order'),
    )
    author = models.ForeignKey(
        AdminUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_comments',
        verbose_name=_('Author'),
    )
    body = models.TextField(verbose_name=_('Comment'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))

    class Meta:
        verbose_name = _('Order Comment')
        verbose_name_plural = _('Order Comments')
        ordering = ['created_at']

    def __str__(self):
        return f"Comment #{self.id} on Order #{self.order_id}"


class PaymentOrderLink(models.Model):
    """
    Link table between BulkPayment and Orders to track which orders
    were paid by which bulk payment.
    
    MIGRATION SAFETY: All fields properly nullable for backward compatibility.
    """
    
    bulk_payment = models.ForeignKey(
        BulkPayment,
        on_delete=models.CASCADE,
        related_name='order_links',
        verbose_name=_('Bulk Payment')
    )
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payment_links',
        verbose_name=_('Order')
    )
    
    # Amount from this bulk payment applied to this specific order
    amount_applied = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_('Amount Applied'),
        help_text=_('Portion of bulk payment applied to this order')
    )
    
    # Order state before payment
    previous_received = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_('Previous Amount Received'),
        help_text=_('Order received amount before this payment')
    )
    
    # Order state after payment
    new_received = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name=_('New Amount Received'),
        help_text=_('Order received amount after this payment')
    )
    
    fully_paid = models.BooleanField(
        default=False,
        verbose_name=_('Fully Paid'),
        help_text=_('Whether this order was fully paid by this transaction')
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    
    class Meta:
        verbose_name = _('Payment-Order Link')
        verbose_name_plural = _('Payment-Order Links')
        ordering = ['bulk_payment', 'order']
        indexes = [
            models.Index(fields=['bulk_payment']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        return f"Payment #{self.bulk_payment.id} → Order #{self.order.id} ({self.amount_applied})"


class PaymeTransaction(models.Model):
    """
    Payme transaction ledger for bot/webapp payments.
    Stores Payme transaction lifecycle timestamps and links back to the order.

    SAFETY: All fields nullable/optional where possible for backward compatibility.
    """

    STATE_CREATED = 1
    STATE_PERFORMED = 2
    STATE_CANCELLED = -1  # Created but canceled
    STATE_CANCELLED_AFTER_PERFORM = -2

    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='payme_transactions',
        null=True,
        blank=True,
        verbose_name=_('Order'),
    )

    payme_transaction_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Payme Transaction ID'),
    )

    # Amount in tiyin (Payme requires integer minor units)
    amount_tiyin = models.BigIntegerField(
        default=0,
        verbose_name=_('Amount (tiyin)'),
    )

    # Stored account payload (e.g., order_id, phone)
    account = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Account Payload'),
    )

    state = models.IntegerField(
        default=0,
        db_index=True,
        verbose_name=_('State'),
        help_text=_('Payme transaction state: 1=created, 2=performed, -1/-2 canceled'),
    )

    create_time_ms = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Create Time (ms)'),
    )
    perform_time_ms = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Perform Time (ms)'),
    )
    cancel_time_ms = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Cancel Time (ms)'),
    )
    cancel_reason = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_('Cancel Reason'),
    )

    # Optional checkout and detail payloads for debugging/reconciliation
    checkout_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Checkout URL'),
    )
    detail = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Receipt Detail Payload'),
    )
    raw_request = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Last Request Payload'),
    )
    raw_response = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_('Last Response Payload'),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))

    class Meta:
        verbose_name = _('Payme Transaction')
        verbose_name_plural = _('Payme Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payme_transaction_id']),
            models.Index(fields=['state']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Payme {self.payme_transaction_id} ({self.state})"

    @property
    def amount_sum(self):
        """Amount in sum (UZS) converted from tiyin."""
        try:
            return (self.amount_tiyin or 0) / 100
        except Exception:
            return 0
