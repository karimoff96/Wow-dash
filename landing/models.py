from django.db import models
from django.utils.translation import gettext_lazy as _


class ContactRequest(models.Model):
    """Store contact form submissions from landing page"""
    
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    email = models.EmailField(verbose_name=_("Email"))
    company = models.CharField(max_length=200, blank=True, verbose_name=_("Company"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    message = models.TextField(verbose_name=_("Message"))
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    is_contacted = models.BooleanField(default=False, verbose_name=_("Contacted"))
    notes = models.TextField(blank=True, verbose_name=_("Internal Notes"))
    
    class Meta:
        verbose_name = _("Contact Request")
        verbose_name_plural = _("Contact Requests")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.email}"
