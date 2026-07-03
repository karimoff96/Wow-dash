import os
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


def ticket_attachment_upload_path(instance, filename):
    import time
    import random
    ext = os.path.splitext(filename)[1][:10] or '.bin'
    new_filename = f"{int(time.time())}_{random.randint(1000, 9999)}{ext}"
    return f"ticket_attachments/{new_filename}"


class TicketCategory(models.Model):
    """Per-center ticket categories, each routed to a dedicated Telegram group."""

    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='ticket_categories',
        verbose_name=_("Center"),
    )
    name_uz = models.CharField(_("Name (UZ)"), max_length=100)
    name_ru = models.CharField(_("Name (RU)"), max_length=100, blank=True)
    name_en = models.CharField(_("Name (EN)"), max_length=100, blank=True)
    icon = models.CharField(
        _("Icon"), max_length=100, default="solar:ticket-bold",
        help_text=_("Iconify icon name, e.g. solar:bug-bold"),
    )
    color = models.CharField(
        _("Color"), max_length=20, default="primary",
        help_text=_("Bootstrap color: primary, success, warning, danger, info"),
    )
    telegram_group_id = models.CharField(
        _("Telegram Group ID"), max_length=50, blank=True, null=True,
        help_text=_("Telegram group ID where tickets in this category are routed"),
    )
    sla_hours = models.PositiveIntegerField(
        _("SLA Hours"), default=72,
        help_text=_("Ticket auto-resolves after this many hours without a staff reply"),
    )
    order = models.PositiveIntegerField(_("Display Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        verbose_name = _("Ticket Category")
        verbose_name_plural = _("Ticket Categories")
        ordering = ['order', 'name_uz']

    def __str__(self):
        return self.name_uz

    def get_name(self, lang='uz'):
        return getattr(self, f'name_{lang}', None) or self.name_uz

    @property
    def localized_name(self):
        from django.utils.translation import get_language
        lang = (get_language() or 'uz')[:2]
        return getattr(self, f'name_{lang}', None) or self.name_uz


class Ticket(models.Model):
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_AWAITING_STAFF = 'awaiting_staff'
    STATUS_RESOLVED = 'resolved'
    STATUS_CLOSED = 'closed'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_OPEN, _('Open')),
        (STATUS_IN_PROGRESS, _('In Progress')),
        (STATUS_AWAITING_STAFF, _('Awaiting Staff Response')),
        (STATUS_RESOLVED, _('Resolved')),
        (STATUS_CLOSED, _('Closed')),
        (STATUS_REJECTED, _('Rejected')),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_CRITICAL = 'critical'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, _('Low')),
        (PRIORITY_NORMAL, _('Normal')),
        (PRIORITY_HIGH, _('High')),
        (PRIORITY_CRITICAL, _('Critical')),
    ]

    TYPE_BUG = 'bug'
    TYPE_FINANCIAL = 'financial'
    TYPE_TECHNICAL = 'technical'
    TYPE_CR = 'cr'
    TYPE_GENERAL = 'general'

    TYPE_CHOICES = [
        (TYPE_BUG, _('Bug / Error')),
        (TYPE_FINANCIAL, _('Financial')),
        (TYPE_TECHNICAL, _('Technical')),
        (TYPE_CR, _('Change Request')),
        (TYPE_GENERAL, _('General Inquiry')),
    ]

    ticket_number = models.CharField(
        _("Ticket Number"), max_length=30, unique=True, editable=False, db_index=True,
    )
    center = models.ForeignKey(
        'organizations.TranslationCenter',
        on_delete=models.CASCADE,
        related_name='tickets',
        verbose_name=_("Center"),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tickets',
        verbose_name=_("Created By"),
    )
    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        verbose_name=_("Category"),
    )
    subject = models.CharField(_("Subject"), max_length=200)
    description = models.TextField(_("Description"))
    status = models.CharField(
        _("Status"), max_length=20, choices=STATUS_CHOICES,
        default=STATUS_OPEN, db_index=True,
    )
    priority = models.CharField(
        _("Priority"), max_length=20, choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL, db_index=True,
    )
    ticket_type = models.CharField(
        _("Type"), max_length=20, choices=TYPE_CHOICES, default=TYPE_GENERAL,
    )

    # Telegram routing (set after notification is sent)
    telegram_message_id = models.CharField(
        _("Telegram Message ID"), max_length=50, blank=True, null=True,
    )
    telegram_group_id = models.CharField(
        _("Telegram Group ID"), max_length=50, blank=True, null=True,
    )
    telegram_thread_id = models.CharField(
        _("Telegram Thread ID"), max_length=50, blank=True, null=True,
        help_text=_("Forum topic thread ID inside the support group"),
    )

    # SLA auto-resolve timestamp (set when status → AWAITING_STAFF)
    auto_resolve_at = models.DateTimeField(_("Auto Resolve At"), null=True, blank=True)

    # Unread indicator for the ticket creator
    has_unread_reply = models.BooleanField(_("Has Unread Support Reply"), default=False)

    resolved_at = models.DateTimeField(_("Resolved At"), null=True, blank=True)
    closed_at = models.DateTimeField(_("Closed At"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Ticket")
        verbose_name_plural = _("Tickets")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['center', 'status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.ticket_number} – {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self._generate_ticket_number()
        super().save(*args, **kwargs)

    def _generate_ticket_number(self):
        year = timezone.now().year
        last = (
            Ticket.objects
            .filter(ticket_number__startswith=f'TKT-{year}-')
            .order_by('-id')
            .first()
        )
        next_num = (int(last.ticket_number.split('-')[-1]) + 1) if last else 1
        return f"TKT-{year}-{next_num:05d}"

    @property
    def is_open(self):
        return self.status in [
            self.STATUS_OPEN,
            self.STATUS_IN_PROGRESS,
            self.STATUS_AWAITING_STAFF,
        ]

    @property
    def status_color(self):
        return {
            self.STATUS_OPEN: 'primary',
            self.STATUS_IN_PROGRESS: 'warning',
            self.STATUS_AWAITING_STAFF: 'info',
            self.STATUS_RESOLVED: 'success',
            self.STATUS_CLOSED: 'secondary',
            self.STATUS_REJECTED: 'danger',
        }.get(self.status, 'secondary')

    @property
    def priority_color(self):
        return {
            self.PRIORITY_LOW: 'secondary',
            self.PRIORITY_NORMAL: 'info',
            self.PRIORITY_HIGH: 'warning',
            self.PRIORITY_CRITICAL: 'danger',
        }.get(self.priority, 'secondary')

    def set_status(self, new_status, changed_by=None, reason=''):
        """Change ticket status, persist, and log history."""
        if self.status == new_status:
            return
        old_status = self.status
        self.status = new_status
        if new_status == self.STATUS_RESOLVED:
            self.resolved_at = timezone.now()
            self.auto_resolve_at = None
        elif new_status == self.STATUS_CLOSED:
            self.closed_at = timezone.now()
        elif new_status == self.STATUS_AWAITING_STAFF:
            sla_hours = self.category.sla_hours if self.category else 72
            self.auto_resolve_at = timezone.now() + timezone.timedelta(hours=sla_hours)
        self.save()
        TicketStatusHistory.objects.create(
            ticket=self,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            reason=reason,
        )


class TicketMessage(models.Model):
    """A single message in a ticket's conversation thread."""

    SENDER_STAFF = 'staff'
    SENDER_SUPPORT = 'support'
    SENDER_SYSTEM = 'system'

    SENDER_CHOICES = [
        (SENDER_STAFF, _('Staff')),
        (SENDER_SUPPORT, _('Support')),
        (SENDER_SYSTEM, _('System')),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("Ticket"),
    )
    sender_type = models.CharField(
        _("Sender Type"), max_length=10, choices=SENDER_CHOICES,
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_messages',
        verbose_name=_("Sender"),
    )
    body = models.TextField(_("Message"))
    is_internal_note = models.BooleanField(
        _("Internal Note"), default=False,
        help_text=_("Internal notes are visible to support only, not to the ticket creator"),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Ticket Message")
        verbose_name_plural = _("Ticket Messages")
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.get_sender_type_display()}] on {self.ticket.ticket_number}"


class TicketAttachment(models.Model):
    """File attached to a ticket message."""

    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_("Message"),
    )
    file = models.FileField(
        _("File"), upload_to=ticket_attachment_upload_path, max_length=500,
    )
    original_filename = models.CharField(_("Original Filename"), max_length=255, blank=True)
    file_size = models.PositiveIntegerField(_("File Size (bytes)"), default=0)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Ticket Attachment")
        verbose_name_plural = _("Ticket Attachments")

    def __str__(self):
        return self.original_filename or str(self.file)

    @property
    def file_url(self):
        try:
            return self.file.url if self.file else None
        except Exception:
            return None

    @property
    def is_image(self):
        if not self.original_filename:
            return False
        return os.path.splitext(self.original_filename)[1].lower() in {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
        }

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size // 1024} KB"
        return f"{self.file_size // (1024 * 1024)} MB"


class TicketStatusHistory(models.Model):
    """Append-only audit log for ticket status transitions."""

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name=_("Ticket"),
    )
    from_status = models.CharField(_("From Status"), max_length=20)
    to_status = models.CharField(_("To Status"), max_length=20)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Changed By"),
    )
    reason = models.TextField(_("Reason"), blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Status History")
        verbose_name_plural = _("Status Histories")
        ordering = ['created_at']

    def __str__(self):
        return f"{self.ticket.ticket_number}: {self.from_status} → {self.to_status}"

    def get_from_status_display(self):
        choices_dict = dict(Ticket.STATUS_CHOICES)
        return choices_dict.get(self.from_status, self.from_status)

    def get_to_status_display(self):
        choices_dict = dict(Ticket.STATUS_CHOICES)
        return choices_dict.get(self.to_status, self.to_status)
