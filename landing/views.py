from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.paginator import Paginator
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


@login_required
def contact_requests_list(request):
    """View and manage contact form submissions (Superuser only)"""
    
    # Only superusers can access
    if not request.user.is_superuser:
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('dashboard')
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    requests_qs = ContactRequest.objects.all()
    
    # Apply status filter
    if status_filter != 'all':
        requests_qs = requests_qs.filter(status=status_filter)
    
    # Apply search filter
    if search_query:
        requests_qs = requests_qs.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(requests_qs, 20)  # 20 items per page
    page_number = request.GET.get('page')
    contact_requests = paginator.get_page(page_number)
    
    # Statistics
    total_requests = ContactRequest.objects.count()
    new_requests = ContactRequest.objects.filter(status=ContactRequest.STATUS_NEW).count()
    contacted_requests = ContactRequest.objects.filter(status=ContactRequest.STATUS_CONTACTED).count()
    pending_requests = ContactRequest.objects.filter(status=ContactRequest.STATUS_PENDING).count()
    converted_requests = ContactRequest.objects.filter(status=ContactRequest.STATUS_CONVERTED).count()
    cancelled_requests = ContactRequest.objects.filter(status=ContactRequest.STATUS_CANCELLED).count()
    
    context = {
        'contact_requests': contact_requests,
        'status_filter': status_filter,
        'search_query': search_query,
        'total_requests': total_requests,
        'new_requests': new_requests,
        'contacted_requests': contacted_requests,
        'pending_requests': pending_requests,
        'converted_requests': converted_requests,
        'cancelled_requests': cancelled_requests,
        'status_choices': ContactRequest.STATUS_CHOICES,
    }
    
    return render(request, 'landing/contact_requests.html', context)


@login_required
def contact_request_change_status(request, pk):
    """Change status of a contact request (Superuser only)"""
    
    # Only superusers can access
    if not request.user.is_superuser:
        messages.error(request, _("You don't have permission to perform this action."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        contact_request = get_object_or_404(ContactRequest, pk=pk)
        new_status = request.POST.get('status', '')
        
        # Validate status
        valid_statuses = [choice[0] for choice in ContactRequest.STATUS_CHOICES]
        if new_status in valid_statuses:
            contact_request.status = new_status
            # Update is_contacted for backwards compatibility
            contact_request.is_contacted = (new_status != ContactRequest.STATUS_NEW)
            contact_request.save()
            
            status_display = dict(ContactRequest.STATUS_CHOICES).get(new_status, new_status)
            messages.success(request, _(f"Status updated to {status_display}"))
        else:
            messages.error(request, _("Invalid status"))
    
    return redirect('contact_requests_list')


@login_required
def contact_request_add_note(request, pk):
    """Add internal notes to a contact request (Superuser only)"""
    
    # Only superusers can access
    if not request.user.is_superuser:
        messages.error(request, _("You don't have permission to perform this action."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        contact_request = get_object_or_404(ContactRequest, pk=pk)
        notes = request.POST.get('notes', '').strip()
        contact_request.notes = notes
        contact_request.save()
        
        messages.success(request, _("Notes updated successfully"))
    
    return redirect('contact_requests_list')
