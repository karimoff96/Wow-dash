import time
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext_lazy as _
from django.utils.translation import activate
from django.db.models import Q
from django.core.paginator import Paginator
from django.core import signing
from django.core.cache import cache
from .models import ContactRequest

# Known disposable / spam email domains
SPAM_EMAIL_DOMAINS = {
    'immenseignite.info',
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwam.com',
    'yopmail.com', 'trashmail.com', 'sharklasers.com', 'spam4.me',
    'maildrop.cc', 'dispostable.com', 'getairmail.com', 'fakeinbox.com',
    'guerrillamailblock.com', 'grr.la', 'guerrillamail.info',
    'guerrillamail.biz', 'guerrillamail.de', 'guerrillamail.net',
    'guerrillamail.org', 'spam.la', 'spamdecoy.net', 'spamfree24.org',
    'spamgourmet.com', 'spamgourmet.net', 'spamgourmet.org',
}


def _get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


from billing.models import Tariff, SubscriptionHistory
from bot.admin_bot_service import (
    send_contact_request_notification,
    update_contact_request_notification,
    update_renewal_request_notification,
)
import logging

logger = logging.getLogger(__name__)


def home(request):
    """Landing page view with multi-language support"""
    
    # Get language from session or default to Russian
    lang = request.session.get('landing_language', 'ru')
    
    # Activate the language for this request
    activate(lang)
    
    # Get active tariffs ordered by trial first, then by price
    tariffs = Tariff.objects.filter(is_active=True, is_special=False).prefetch_related('pricing', 'features').order_by(
        '-is_trial',  # Trial tariffs first
        'display_order'  # Then by display order
    )
    
    canonical_map = {'ru': 'https://multilang.uz/', 'en': 'https://multilang.uz/en/', 'uz': 'https://multilang.uz/uz/'}
    form_token = signing.dumps({'t': time.time()}, salt='contact-form-load')
    context = {
        'current_language': lang,
        'tariffs': tariffs,
        'canonical_url': canonical_map.get(lang, 'https://multilang.uz/'),
        'form_token': form_token,
    }
    
    return render(request, 'landing/home.html', context)


def home_lang(request, lang_code):
    """SEO-friendly language-specific landing page URL (/en/, /uz/).
    Each language has its own crawlable URL so Googlebot indexes all 3 versions."""
    if lang_code not in ['ru', 'uz', 'en']:
        lang_code = 'ru'
    request.session['landing_language'] = lang_code
    activate(lang_code)

    tariffs = Tariff.objects.filter(is_active=True, is_special=False).prefetch_related('pricing', 'features').order_by(
        '-is_trial', 'display_order'
    )
    canonical_map = {'ru': 'https://multilang.uz/', 'en': 'https://multilang.uz/en/', 'uz': 'https://multilang.uz/uz/'}
    form_token = signing.dumps({'t': time.time()}, salt='contact-form-load')
    context = {
        'current_language': lang_code,
        'tariffs': tariffs,
        'canonical_url': canonical_map.get(lang_code, 'https://multilang.uz/'),
        'form_token': form_token,
    }
    return render(request, 'landing/home.html', context)


def change_language(request, lang_code):
    """Change landing page language — redirects to the SEO-friendly language URL."""
    lang_redirects = {'en': '/en/', 'uz': '/uz/', 'ru': '/'}
    if lang_code in lang_redirects:
        request.session['landing_language'] = lang_code
        return redirect(lang_redirects[lang_code])
    return redirect('landing_home')


def contact_form(request):
    """Handle contact form submission"""
    if request.method == 'POST':
        try:
            ip = _get_client_ip(request)

            # --- Check 1: Honeypot ---
            # Bots fill hidden fields; real users never see or touch it
            if request.POST.get('website', ''):
                logger.warning(f"[SPAM] Honeypot triggered from IP {ip}")
                messages.success(request, _("Thank you! We will contact you soon."))
                return redirect('landing_home')

            # --- Check 2: Form token / minimum time check ---
            # Reject submissions that arrive in under 3 seconds (bot speed)
            form_token = request.POST.get('form_token', '')
            try:
                token_data = signing.loads(form_token, salt='contact-form-load', max_age=3600)
                elapsed = time.time() - token_data.get('t', 0)
                if elapsed < 3:
                    logger.warning(f"[SPAM] Form submitted too fast ({elapsed:.1f}s) from IP {ip}")
                    messages.error(request, _("Please try again."))
                    return redirect('landing_home')
            except signing.BadSignature:
                logger.warning(f"[SPAM] Invalid or missing form token from IP {ip}")
                messages.error(request, _("Please try again."))
                return redirect('landing_home')

            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            company = request.POST.get('company', '').strip()
            phone = request.POST.get('phone', '').strip()
            message = request.POST.get('message', '').strip()

            # Basic validation
            if not name or not email or not message:
                messages.error(request, _("Please fill in all required fields"))
                return redirect('landing_home')

            email_lower = email.lower()
            email_domain = email_lower.split('@')[-1] if '@' in email_lower else ''

            # --- Check 3: Spam / disposable email domain ---
            if email_domain in SPAM_EMAIL_DOMAINS:
                logger.warning(f"[SPAM] Blocked disposable email domain '{email_domain}' from IP {ip}")
                messages.success(request, _("Thank you! We will contact you soon."))
                return redirect('landing_home')

            # --- Check 4: Duplicate email dedup (10-minute window) ---
            dedup_key = f"contact:dedup:email:{email_lower}"
            if cache.get(dedup_key):
                logger.warning(f"[SPAM] Duplicate contact form submission for {email_lower} from IP {ip}")
                messages.success(request, _("Thank you! We will contact you soon."))
                return redirect('landing_home')

            # Create contact request
            contact_request = ContactRequest.objects.create(
                name=name,
                email=email,
                company=company,
                phone=phone,
                message=message,
                ip_address=ip or None,
            )

            # Mark email as seen to prevent duplicates for 10 minutes
            cache.set(dedup_key, True, 600)

            # Send notification to admin via Telegram
            logger.info(f"About to send admin notification for contact request from {name}")
            try:
                notification_sent = send_contact_request_notification(contact_request)
                if notification_sent:
                    logger.info(f"✅ Admin notification sent successfully for contact request from {name}")
                else:
                    logger.warning(f"⚠️ Admin notification was not sent for contact request from {name}")
            except Exception as e:
                logger.error(f"❌ Exception while sending admin notification for contact request: {e}")
                import traceback
                logger.error(traceback.format_exc())

            messages.success(request, _("Thank you! We will contact you soon."))
            logger.info(f"New contact request from {name} ({email}) IP={ip}")

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

    # Redirect to unified requests management (contact tab)
    return redirect(f"{reverse('requests_management')}?tab=contact")


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
            try:
                update_contact_request_notification(contact_request)
            except Exception as e:
                logger.error(f"Failed to update admin bot message for contact request {contact_request.id}: {e}")
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


@login_required
def requests_management(request):
    """Unified view for managing both contact requests and renewal requests (Superuser only)"""
    
    # Only superusers can access
    if not request.user.is_superuser:
        messages.error(request, _("You don't have permission to access this page."))
        return redirect('dashboard')

    # Handle renewal actions (approve/reject)
    if request.method == 'POST':
        action = request.POST.get('action')
        history_id = request.POST.get('history_id')
        try:
            if action in ['approve', 'reject'] and history_id:
                history_entry = get_object_or_404(
                    SubscriptionHistory,
                    pk=history_id,
                    action='renewal_requested'
                )
                new_action = 'renewal_approved' if action == 'approve' else 'renewal_rejected'
                SubscriptionHistory.objects.create(
                    subscription=history_entry.subscription,
                    action=new_action,
                    description=history_entry.description,
                    performed_by=request.user,
                )
                messages.success(request, _("Renewal request processed."))
            else:
                messages.error(request, _("Invalid action."))
        except Exception as e:
            messages.error(request, _(f"Error processing renewal: {str(e)}"))
        return redirect(f"{reverse('requests_management')}?tab=renewal")
    
    # Get active tab (default: contact requests)
    active_tab = request.GET.get('tab', 'contact')
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Initialize context
    context = {
        'subTitle': _('Contact & Renewal Requests'),
        'active_tab': active_tab,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'sort_by': sort_by,
    }
    
    # Process Contact Requests Tab
    if active_tab == 'contact':
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
        
        # Apply date range filter
        if date_from:
            from datetime import datetime
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                requests_qs = requests_qs.filter(created_at__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            from datetime import datetime, timedelta
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_obj = date_to_obj + timedelta(days=1)
                requests_qs = requests_qs.filter(created_at__lt=date_to_obj)
            except ValueError:
                pass
        
        # Apply sorting
        valid_sorts = ['created_at', '-created_at', 'name', '-name', 'email', '-email', 'status', '-status']
        if sort_by in valid_sorts:
            requests_qs = requests_qs.order_by(sort_by)
        else:
            requests_qs = requests_qs.order_by('-created_at')
        
        # Pagination
        paginator = Paginator(requests_qs, 20)
        page_number = request.GET.get('page')
        contact_requests = paginator.get_page(page_number)
        
        # Statistics
        context.update({
            'contact_requests': contact_requests,
            'total_contact': ContactRequest.objects.count(),
            'new_contact': ContactRequest.objects.filter(status=ContactRequest.STATUS_NEW).count(),
            'contacted': ContactRequest.objects.filter(status=ContactRequest.STATUS_CONTACTED).count(),
            'pending_contact': ContactRequest.objects.filter(status=ContactRequest.STATUS_PENDING).count(),
            'converted_contact': ContactRequest.objects.filter(status=ContactRequest.STATUS_CONVERTED).count(),
            'cancelled_contact': ContactRequest.objects.filter(status=ContactRequest.STATUS_CANCELLED).count(),
            'status_choices': ContactRequest.STATUS_CHOICES,
        })
    
    # Process Renewal Requests Tab
    elif active_tab == 'renewal':
        # Get renewal requests from SubscriptionHistory
        renewal_qs = SubscriptionHistory.objects.filter(
            action='renewal_requested'
        ).select_related('subscription', 'subscription__organization', 'performed_by')
        
        # Apply status filter (check if already processed)
        if status_filter == 'pending':
            # Get IDs of renewals that don't have a subsequent approved/rejected action
            processed_renewal_ids = SubscriptionHistory.objects.filter(
                action__in=['renewal_approved', 'renewal_rejected'],
                subscription__in=renewal_qs.values('subscription')
            ).values_list('subscription_id', flat=True)
            renewal_qs = renewal_qs.exclude(subscription_id__in=processed_renewal_ids)
        elif status_filter == 'approved':
            approved_subscription_ids = SubscriptionHistory.objects.filter(
                action='renewal_approved'
            ).values_list('subscription_id', flat=True)
            renewal_qs = renewal_qs.filter(subscription_id__in=approved_subscription_ids)
        elif status_filter == 'rejected':
            rejected_subscription_ids = SubscriptionHistory.objects.filter(
                action='renewal_rejected'
            ).values_list('subscription_id', flat=True)
            renewal_qs = renewal_qs.filter(subscription_id__in=rejected_subscription_ids)
        
        # Apply search filter
        if search_query:
            renewal_qs = renewal_qs.filter(
                Q(subscription__organization__name__icontains=search_query) |
                Q(performed_by__email__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        # Apply date range filter
        if date_from:
            from datetime import datetime
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                renewal_qs = renewal_qs.filter(timestamp__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            from datetime import datetime, timedelta
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_obj = date_to_obj + timedelta(days=1)
                renewal_qs = renewal_qs.filter(timestamp__lt=date_to_obj)
            except ValueError:
                pass
        
        # Apply sorting
        sort_mapping = {
            'created_at': 'timestamp',
            '-created_at': '-timestamp',
            'name': 'subscription__organization__name',
            '-name': '-subscription__organization__name',
        }
        actual_sort = sort_mapping.get(sort_by, '-timestamp')
        renewal_qs = renewal_qs.order_by(actual_sort)
        
        # Pagination
        paginator = Paginator(renewal_qs, 20)
        page_number = request.GET.get('page')
        renewal_requests = paginator.get_page(page_number)
        
        # Statistics
        all_renewals = SubscriptionHistory.objects.filter(action='renewal_requested')
        approved_ids = set(SubscriptionHistory.objects.filter(action='renewal_approved').values_list('subscription_id', flat=True))
        rejected_ids = set(SubscriptionHistory.objects.filter(action='renewal_rejected').values_list('subscription_id', flat=True))
        processed_ids = approved_ids | rejected_ids
        
        context.update({
            'renewal_requests': renewal_requests,
            'total_renewal': all_renewals.count(),
            'pending_renewal': all_renewals.exclude(subscription_id__in=processed_ids).count(),
            'approved_renewal': len(approved_ids),
            'rejected_renewal': len(rejected_ids),
            'approved_ids': approved_ids,
            'rejected_ids': rejected_ids,
        })
    
    return render(request, 'landing/requests_management.html', context)


def google_site_verification(request):
    """Serve Google Search Console site verification file."""
    from django.http import HttpResponse
    return HttpResponse(
        'google-site-verification: google145d3096a17fea6d.html',
        content_type='text/html'
    )


def robots_txt(request):
    """Serve robots.txt for SEO crawlers."""
    from django.http import HttpResponse
    content = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /accounts/
Disallow: /billing/
Disallow: /orders/
Disallow: /organizations/
Disallow: /reports/
Disallow: /services/
Disallow: /users/
Disallow: /marketing/
Disallow: /bot/
Disallow: /webapp/
Disallow: /api/
Disallow: /backups/
Disallow: /change-language/

Sitemap: https://multilang.uz/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml(request):
    """Serve sitemap.xml for SEO."""
    from django.http import HttpResponse
    from datetime import date
    today = date.today().isoformat()
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://multilang.uz/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
    <xhtml:link rel="alternate" hreflang="ru" href="https://multilang.uz/"/>
    <xhtml:link rel="alternate" hreflang="uz" href="https://multilang.uz/uz/"/>
    <xhtml:link rel="alternate" hreflang="en" href="https://multilang.uz/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://multilang.uz/"/>
  </url>
  <url>
    <loc>https://multilang.uz/en/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
    <xhtml:link rel="alternate" hreflang="ru" href="https://multilang.uz/"/>
    <xhtml:link rel="alternate" hreflang="uz" href="https://multilang.uz/uz/"/>
    <xhtml:link rel="alternate" hreflang="en" href="https://multilang.uz/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://multilang.uz/"/>
  </url>
  <url>
    <loc>https://multilang.uz/uz/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
    <xhtml:link rel="alternate" hreflang="ru" href="https://multilang.uz/"/>
    <xhtml:link rel="alternate" hreflang="uz" href="https://multilang.uz/uz/"/>
    <xhtml:link rel="alternate" hreflang="en" href="https://multilang.uz/en/"/>
    <xhtml:link rel="alternate" hreflang="x-default" href="https://multilang.uz/"/>
  </url>
  <url>
    <loc>https://multilang.uz/contact/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
    return HttpResponse(content, content_type='application/xml')
