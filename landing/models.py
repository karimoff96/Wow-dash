from django.db import models
from django.utils.translation import gettext_lazy as _


class ContactRequest(models.Model):
    """Store contact form submissions from landing page"""
    
    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_PENDING = 'pending'
    STATUS_CONVERTED = 'converted'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_NEW, _('New')),
        (STATUS_CONTACTED, _('Contacted')),
        (STATUS_PENDING, _('Pending')),
        (STATUS_CONVERTED, _('Converted')),
        (STATUS_CANCELLED, _('Cancelled')),
    ]
    
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    email = models.EmailField(verbose_name=_("Email"))
    company = models.CharField(max_length=200, blank=True, verbose_name=_("Company"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    message = models.TextField(verbose_name=_("Message"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW,
        verbose_name=_("Status")
    )
    is_contacted = models.BooleanField(default=False, verbose_name=_("Contacted"))  # Keep for backwards compatibility
    notes = models.TextField(blank=True, verbose_name=_("Internal Notes"))
    
    class Meta:
        verbose_name = _("Contact Request")
        verbose_name_plural = _("Contact Requests")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.email}"
