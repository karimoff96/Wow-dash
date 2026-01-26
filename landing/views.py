from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import ContactRequest
import logging

logger = logging.getLogger(__name__)


def home(request):
    """Landing page view with multi-language support"""
    
    # Get language from session or default to Russian
    lang = request.session.get('landing_language', 'ru')
    
    context = {
        'current_language': lang,
    }
    
    return render(request, 'landing/home.html', context)


def change_language(request, lang_code):
    """Change landing page language"""
    if lang_code in ['ru', 'uz', 'en']:
        request.session['landing_language'] = lang_code
    
    return redirect('landing_home')


def contact_form(request):
    """Handle contact form submission"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            company = request.POST.get('company', '').strip()
            phone = request.POST.get('phone', '').strip()
            message = request.POST.get('message', '').strip()
            
            # Basic validation
            if not name or not email or not message:
                messages.error(request, _("Please fill in all required fields"))
                return redirect('landing_home')
            
            # Create contact request
            ContactRequest.objects.create(
                name=name,
                email=email,
                company=company,
                phone=phone,
                message=message
            )
            
            messages.success(request, _("Thank you! We will contact you soon."))
            logger.info(f"New contact request from {name} ({email})")
            
        except Exception as e:
            logger.error(f"Contact form error: {e}")
            messages.error(request, _("An error occurred. Please try again."))
    
    return redirect('landing_home')
