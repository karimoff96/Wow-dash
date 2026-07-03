import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Prefetch, F, FloatField, Case, When, Value, ExpressionWrapper
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from bot.admin_bot_service import send_renewal_request_notification
from organizations.models import TranslationCenter
from .models import Tariff, TariffPricing, Subscription, Feature, UsageTracking, SubscriptionHistory, SubscriptionAnalytics

logger = logging.getLogger(__name__)


def _invalidate_monitoring_cache():
    """
    Delete the centers-monitoring analytics cache key.
    Called whenever a subscription is created, renewed, or status-changed
    so the monitoring page reflects the change on next load instead of
    waiting up to 5 minutes for TTL expiry.
    Completely safe: silently swallows any Redis/cache errors.
    """
    try:
        from django.core.cache import cache
        cache.delete('billing:centers_monitoring_data')
    except Exception:
        pass


@login_required
def subscription_list(request):
    """List all subscriptions - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    # Filters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    sub_status = request.GET.get('sub_status', 'all')
    sort_by = request.GET.get('sort', 'name')
    tariff_filter = request.GET.get('tariff')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    sort_by = request.GET.get('sort', '-end_date')
    
    # Base queryset
    subscriptions = Subscription.objects.select_related(
        'organization', 'tariff', 'pricing', 'created_by'
    ).all()
    
    # Apply filters
    if status_filter != 'all':
        subscriptions = subscriptions.filter(status=status_filter)
    
    if search_query:
        subscriptions = subscriptions.filter(
            Q(organization__name__icontains=search_query) |
            Q(organization__subdomain__icontains=search_query) |
            Q(transaction_id__icontains=search_query)
        )

    if tariff_filter:
        subscriptions = subscriptions.filter(tariff_id=tariff_filter)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            subscriptions = subscriptions.filter(start_date__gte=start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            subscriptions = subscriptions.filter(end_date__lte=end_dt)
        except ValueError:
            pass

    valid_sorts = [
        'organization__name', '-organization__name',
        'tariff__title', '-tariff__title',
        'start_date', '-start_date',
        'end_date', '-end_date',
        'status', '-status',
        'id', '-id'
    ]
    if sort_by in valid_sorts:
        subscriptions = subscriptions.order_by(sort_by)
    else:
        subscriptions = subscriptions.order_by('-end_date')
    
    # Statistics
    total_subscriptions = Subscription.objects.count()
    active_count = Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count()
    expired_count = Subscription.objects.filter(status=Subscription.STATUS_EXPIRED).count()
    pending_count = Subscription.objects.filter(status=Subscription.STATUS_PENDING).count()
    
    # Expiring soon (within 7 days)
    expiring_soon = Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE,
        end_date__lte=date.today() + timedelta(days=7),
        end_date__gte=date.today()
    ).count()
    
    # Pagination
    paginator = Paginator(subscriptions, 20)
    page_number = request.GET.get('page')
    subscriptions_page = paginator.get_page(page_number)
    
    tariffs = Tariff.objects.filter(is_active=True).order_by('title')

    context = {
        'title': _('Subscription Management'),
        'subTitle': _('Subscriptions'),
        'subscriptions': subscriptions_page,
        'status_filter': status_filter,
        'search_query': search_query,
        'tariff_filter': tariff_filter,
        'start_date': start_date,
        'end_date': end_date,
        'sort_by': sort_by,
        'tariffs': tariffs,
        'total_subscriptions': total_subscriptions,
        'active_count': active_count,
        'expired_count': expired_count,
        'pending_count': pending_count,
        'expiring_soon': expiring_soon,
    }
    
    return render(request, 'billing/subscription_list.html', context)


@login_required
def subscription_create(request, center_id):
    """Create subscription for a center - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    center = get_object_or_404(TranslationCenter, pk=center_id)
    
    if request.method == 'POST':
        tariff_id = request.POST.get('tariff')
        pricing_id = request.POST.get('pricing')
        start_date_str = request.POST.get('start_date')
        status = request.POST.get('status', Subscription.STATUS_PENDING)
        amount_paid = request.POST.get('amount_paid')
        payment_method = request.POST.get('payment_method')
        transaction_id = request.POST.get('transaction_id')
        notes = request.POST.get('notes', '')
        
        try:
            if not tariff_id:
                messages.error(request, _("Please select a tariff."))
                tariffs = Tariff.objects.filter(is_active=True).prefetch_related('pricing')
                return render(request, 'billing/subscription_create.html', {'center': center, 'tariffs': tariffs})
            
            tariff = Tariff.objects.get(pk=tariff_id)
            
            # For trial subscriptions, get first available pricing or create one
            if tariff.is_trial:
                # Get or create a trial pricing
                pricing, created = TariffPricing.objects.get_or_create(
                    tariff=tariff,
                    duration_months=1,
                    defaults={
                        'price': 0,
                        'currency': 'UZS',
                        'discount_percentage': 0,
                        'is_active': True
                    }
                )
            else:
                if not pricing_id or pricing_id == 'trial':
                    messages.error(request, _("Please select a pricing option for non-trial tariffs."))
                    tariffs = Tariff.objects.filter(is_active=True).prefetch_related('pricing')
                    return render(request, 'billing/subscription_create.html', {'center': center, 'tariffs': tariffs})
                pricing = TariffPricing.objects.get(pk=pricing_id)
            
            # Convert string date to date object
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else date.today()
            
            # Check if center already has subscription
            if hasattr(center, 'subscription'):
                # Center already has a subscription (OneToOneField — only one allowed).
                # Update it in-place so the PK and full history are preserved.
                subscription = center.subscription
                old_info = f'{subscription.tariff.title} ({subscription.start_date} – {subscription.end_date})'

                # Log the replacement under the EXISTING subscription record
                SubscriptionHistory.objects.create(
                    subscription=subscription,
                    action='cancelled',
                    description=_('Replaced: ') + old_info,
                    performed_by=request.user
                )

                # Overwrite all mutable fields
                subscription.tariff = tariff
                subscription.pricing = pricing
                subscription.start_date = start_date
                subscription.end_date = None        # let save() auto-calculate
                subscription.trial_end_date = None  # let save() handle trial
                subscription.is_trial = tariff.is_trial
                subscription.status = status if not tariff.is_trial else Subscription.STATUS_ACTIVE
                subscription.amount_paid = amount_paid if amount_paid else None
                subscription.payment_method = payment_method or ''
                subscription.transaction_id = transaction_id or ''
                subscription.notes = notes
                subscription.auto_renew = False
                subscription.created_by = request.user
                subscription.payment_date = date.today() if status == Subscription.STATUS_ACTIVE else None
                subscription.save()
            else:
                # No existing subscription — create fresh
                subscription = Subscription.objects.create(
                    organization=center,
                    tariff=tariff,
                    pricing=pricing,
                    start_date=start_date,
                    status=status if not tariff.is_trial else Subscription.STATUS_ACTIVE,
                    amount_paid=amount_paid if amount_paid else None,
                    payment_method=payment_method or '',
                    transaction_id=transaction_id or '',
                    notes=notes,
                    auto_renew=False,
                    created_by=request.user
                )

                if status == Subscription.STATUS_ACTIVE:
                    subscription.payment_date = date.today()
                    subscription.save()

            SubscriptionHistory.objects.create(
                subscription=subscription,
                action='created',
                description=_('Subscription assigned by superuser'),
                performed_by=request.user
            )

            _invalidate_monitoring_cache()
            messages.success(request, _("Subscription created successfully!"))
            return redirect('billing:subscription_detail', pk=subscription.pk)
            
        except Exception as e:
            messages.error(request, f"Error creating subscription: {str(e)}")
    
    tariffs = Tariff.objects.filter(is_active=True).prefetch_related('pricing')
    
    context = {
        'center': center,
        'tariffs': tariffs,
    }
    
    return render(request, 'billing/subscription_create.html', context)


@login_required
def subscription_detail(request, pk):
    """View subscription details - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    subscription = get_object_or_404(
        Subscription.objects.select_related(
            'organization', 'tariff', 'pricing'
        ),
        pk=pk
    )
    
    # Get comprehensive analytics for this center
    org = subscription.organization
    analytics = SubscriptionAnalytics.get_center_analytics(org)
    
    # Get usage statistics
    current_usage = {}
    if subscription.organization:
        current_usage = {
            'branches': org.branches.count(),
            'branches_limit': subscription.tariff.max_branches,
            'branches_percent': subscription.get_usage_percentage('branches'),
            'staff': org.get_staff_count(),
            'staff_limit': subscription.tariff.max_staff,
            'staff_percent': subscription.get_usage_percentage('staff'),
            'orders': org.get_current_month_orders_count(),
            'orders_limit': subscription.tariff.max_monthly_orders,
            'orders_percent': subscription.get_usage_percentage('orders'),
            'broadcasts': org.get_current_month_broadcasts_count(),
            'broadcasts_limit': subscription.tariff.max_monthly_broadcasts,
            'broadcasts_percent': subscription.get_usage_percentage('broadcasts'),
        }
    
    # Get subscription history
    history_entries = subscription.history.all()[:20]  # Last 20 entries
    
    context = {
        'title': _('Billing'),
        'subTitle': _('Subscription Detail'),
        'subscription': subscription,
        'current_usage': current_usage,
        'analytics': analytics,
        'history_entries': history_entries,
    }
    
    return render(request, 'billing/subscription_detail.html', context)


@login_required
def subscription_update_status(request, pk):
    """Update subscription status - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied."))
        return redirect('dashboard')
    
    if request.method == 'POST':
        subscription = get_object_or_404(Subscription, pk=pk)
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        old_status = subscription.status
        subscription.status = new_status
        
        if new_status == Subscription.STATUS_ACTIVE and not subscription.payment_date:
            subscription.payment_date = date.today()
        
        subscription.save()
        
        SubscriptionHistory.objects.create(
            subscription=subscription,
            action='status_changed',
            description=f'Status changed from {old_status} to {new_status}. {notes}',
            performed_by=request.user
        )
        
        _invalidate_monitoring_cache()  # reflect change immediately on monitoring page
        messages.success(request, _("Subscription status updated successfully!"))
    
    return redirect('billing:subscription_detail', pk=pk)


@login_required
def tariff_list(request):
    """List all tariffs - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    tariffs = Tariff.objects.prefetch_related(
        Prefetch('pricing', queryset=TariffPricing.objects.filter(is_active=True)),
        'features'
    ).all()
    
    context = {
        'title': _('Tariff Plans'),
        'subTitle': _('Tariffs'),
        'tariffs': tariffs,
    }
    
    return render(request, 'billing/tariff_list.html', context)


@login_required
def tariff_create(request):
    """Create new tariff - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            title_uz = request.POST.get('title_uz', '')
            title_ru = request.POST.get('title_ru', '')
            title_en = request.POST.get('title_en', '')
            slug = request.POST.get('slug')
            description_uz = request.POST.get('description_uz', '')
            description_ru = request.POST.get('description_ru', '')
            description_en = request.POST.get('description_en', '')
            is_active = request.POST.get('is_active') == 'on'
            is_featured = request.POST.get('is_featured') == 'on'
            show_prices = request.POST.get('show_prices') == 'on'
            is_special = request.POST.get('is_special') == 'on'
            is_trial = request.POST.get('is_trial') == 'on'
            trial_days = request.POST.get('trial_days') or None
            display_order = request.POST.get('display_order', 0)

            # Limits
            max_branches_raw = request.POST.get('max_branches')
            max_staff_raw = request.POST.get('max_staff')
            max_monthly_orders_raw = request.POST.get('max_monthly_orders')
            max_monthly_broadcasts_raw = request.POST.get('max_monthly_broadcasts')

            tariff = Tariff.objects.create(
                title_uz=title_uz,
                title_ru=title_ru,
                title_en=title_en,
                # Fall back to first non-empty for the base field
                title=title_uz or title_ru or title_en,
                slug=slug,
                description_uz=description_uz,
                description_ru=description_ru,
                description_en=description_en,
                description=description_uz or description_ru or description_en,
                is_active=is_active,
                is_featured=is_featured,
                show_prices=show_prices,
                is_special=is_special,
                is_trial=is_trial,
                trial_days=int(trial_days) if trial_days else None,
                display_order=display_order,
                max_branches=int(max_branches_raw) if max_branches_raw else None,
                max_staff=int(max_staff_raw) if max_staff_raw else None,
                max_monthly_orders=int(max_monthly_orders_raw) if max_monthly_orders_raw else None,
                max_monthly_broadcasts=int(max_monthly_broadcasts_raw) if max_monthly_broadcasts_raw else None,
            )

            # Set all 32 feature flags
            feature_fields = [
                'feature_products_basic', 'feature_products_advanced', 'feature_language_pricing', 'feature_dynamic_pricing',
                'feature_orders_basic', 'feature_orders_advanced', 'feature_order_assignment', 'feature_bulk_payments', 'feature_extra_fees',
                'feature_payment_management', 'feature_invoicing', 'feature_expense_tracking', 'feature_general_expenses', 'feature_archive_access',
                'feature_agency_management',
                'feature_marketing_basic', 'feature_broadcast_messages',
                'feature_analytics_basic', 'feature_analytics_advanced', 'feature_financial_reports',
                'feature_staff_performance', 'feature_custom_reports', 'feature_export_reports', 'feature_debt_tracking',
                'feature_multi_branch', 'feature_custom_roles', 'feature_branch_settings', 'feature_audit_logs',
                'feature_telegram_bot', 'feature_webhooks', 'feature_api_access', 'feature_integrations',
            ]
            for field in feature_fields:
                setattr(tariff, field, request.POST.get(field) == 'on')
            tariff.save()

            # Create pricing options
            pricing_durations = request.POST.getlist('pricing_duration[]')
            pricing_discounts = request.POST.getlist('pricing_discount[]')
            pricing_total = request.POST.getlist('pricing_total[]')
            pricing_currency = request.POST.getlist('pricing_currency[]')

            for i in range(len(pricing_durations)):
                duration = int(pricing_durations[i]) if pricing_durations[i] else 0
                total = float(pricing_total[i]) if i < len(pricing_total) and pricing_total[i] else 0
                if duration <= 0 or total <= 0:
                    continue
                discount = float(pricing_discounts[i]) if i < len(pricing_discounts) and pricing_discounts[i] else 0
                currency = pricing_currency[i] if i < len(pricing_currency) else 'UZS'
                TariffPricing.objects.create(
                    tariff=tariff,
                    duration_months=duration,
                    discount_percentage=discount,
                    price=total,
                    currency=currency,
                )

            messages.success(request, _("Tariff created successfully!"))
            return redirect('billing:tariff_list')

        except Exception as e:
            messages.error(request, f"Error creating tariff: {str(e)}")

    return render(request, 'billing/tariff_create.html')


@login_required
def tariff_edit(request, pk):
    """Edit tariff - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    tariff = get_object_or_404(Tariff, pk=pk)
    
    if request.method == 'POST':
        try:
            # Set all language variants
            tariff.title_uz = request.POST.get('title_uz', '')
            tariff.title_ru = request.POST.get('title_ru', '')
            tariff.title_en = request.POST.get('title_en', '')
            
            tariff.slug = request.POST.get('slug')
            
            tariff.description_uz = request.POST.get('description_uz', '')
            tariff.description_ru = request.POST.get('description_ru', '')
            tariff.description_en = request.POST.get('description_en', '')
            
            tariff.is_active = request.POST.get('is_active') == 'on'
            tariff.is_featured = request.POST.get('is_featured') == 'on'
            tariff.show_prices = request.POST.get('show_prices') == 'on'
            tariff.is_special = request.POST.get('is_special') == 'on'
            tariff.is_trial = request.POST.get('is_trial') == 'on'
            tariff.trial_days = request.POST.get('trial_days') or None
            tariff.display_order = request.POST.get('display_order', 0)
            
            # Limits
            max_branches = request.POST.get('max_branches')
            max_staff = request.POST.get('max_staff')
            max_monthly_orders = request.POST.get('max_monthly_orders')
            max_monthly_broadcasts = request.POST.get('max_monthly_broadcasts')
            
            tariff.max_branches = int(max_branches) if max_branches else None
            tariff.max_staff = int(max_staff) if max_staff else None
            tariff.max_monthly_orders = int(max_monthly_orders) if max_monthly_orders else None
            tariff.max_monthly_broadcasts = int(max_monthly_broadcasts) if max_monthly_broadcasts else None
            
            tariff.save()
            
            # Update boolean feature flags (32 features)
            feature_fields = [
                # Orders (5)
                'feature_orders_basic', 'feature_orders_advanced', 'feature_order_assignment',
                'feature_bulk_payments', 'feature_extra_fees',
                # Analytics (7)
                'feature_analytics_basic', 'feature_analytics_advanced', 'feature_financial_reports',
                'feature_staff_performance', 'feature_custom_reports', 'feature_export_reports',
                'feature_debt_tracking',
                # Integration (4)
                'feature_telegram_bot', 'feature_webhooks', 'feature_api_access', 'feature_integrations',
                # Marketing (2)
                'feature_marketing_basic', 'feature_broadcast_messages',
                # Organization (4)
                'feature_multi_branch', 'feature_custom_roles', 'feature_branch_settings',
                'feature_agency_management',
                # Storage (1)
                'feature_archive_access',
                # Financial (4)
                'feature_payment_management', 'feature_invoicing', 'feature_expense_tracking',
                'feature_general_expenses',
                # Advanced (1)
                'feature_audit_logs',
                # Services (4)
                'feature_products_basic', 'feature_products_advanced', 'feature_language_pricing', 'feature_dynamic_pricing',
            ]
            
            for field in feature_fields:
                setattr(tariff, field, request.POST.get(field) == 'on')
            
            tariff.save()
            
            # Update pricing
            pricing_ids = request.POST.getlist('pricing_id[]')
            pricing_durations = request.POST.getlist('pricing_duration[]')
            pricing_discounts = request.POST.getlist('pricing_discount[]')
            pricing_monthly = request.POST.getlist('pricing_monthly[]')
            pricing_total = request.POST.getlist('pricing_total[]')
            pricing_currency = request.POST.getlist('pricing_currency[]')
            
            # Track existing pricing IDs to know which to delete
            existing_ids = set()
            
            for i in range(len(pricing_durations)):
                pricing_id = pricing_ids[i] if i < len(pricing_ids) else ''
                duration = int(pricing_durations[i]) if pricing_durations[i] else 1
                discount = float(pricing_discounts[i]) if i < len(pricing_discounts) and pricing_discounts[i] else 0
                monthly = float(pricing_monthly[i]) if pricing_monthly[i] else 0
                total = float(pricing_total[i]) if pricing_total[i] else 0
                currency = pricing_currency[i] if i < len(pricing_currency) else 'UZS'
                
                # Skip if no valid pricing data
                if duration <= 0 or total <= 0:
                    continue
                
                if pricing_id:
                    # Update existing pricing
                    pricing_obj = TariffPricing.objects.get(id=pricing_id, tariff=tariff)
                    pricing_obj.duration_months = duration
                    pricing_obj.discount_percentage = discount
                    pricing_obj.price = total
                    pricing_obj.currency = currency
                    pricing_obj.save()
                    existing_ids.add(int(pricing_id))
                else:
                    # Create new pricing
                    new_pricing = TariffPricing.objects.create(
                        tariff=tariff,
                        duration_months=duration,
                        discount_percentage=discount,
                        price=total,
                        currency=currency
                    )
                    existing_ids.add(new_pricing.id)
            
            # Delete or deactivate pricing options that were removed
            def _soft_delete(pricing_qs):
                for pricing in pricing_qs:
                    # If a pricing plan has subscriptions, keep it but mark inactive
                    if pricing.subscriptions.exists():
                        pricing.is_active = False
                        pricing.save()
                    else:
                        pricing.delete()

            if pricing_durations:
                # User submitted pricing rows; delete everything not in the submitted set
                obsolete = tariff.pricing.exclude(id__in=existing_ids)
                _soft_delete(obsolete)
            else:
                # User removed all rows on the page; wipe all pricing for this tariff
                _soft_delete(tariff.pricing.all())
            
            messages.success(request, _("Tariff updated successfully!"))
            return redirect('billing:tariff_list')
            
        except Exception as e:
            messages.error(request, f"Error updating tariff: {str(e)}")
    
    # Pre-calculate base monthly price for the template (from 1-month plan)
    base_price = ''
    one_month_pricing = tariff.pricing.filter(duration_months=1).first()
    if one_month_pricing:
        base_price = one_month_pricing.price
    elif tariff.pricing.exists():
        first_pricing = tariff.pricing.order_by('duration_months').first()
        # Reverse-calculate: price / months / (1 - discount/100)
        discount = first_pricing.discount_percentage / 100
        if discount < 1:
            base_price = round(float(first_pricing.price) / first_pricing.duration_months / float(1 - discount) / 100) * 100

    context = {
        'tariff': tariff,
        'base_price': base_price,
    }
    
    return render(request, 'billing/tariff_edit.html', context)


@login_required
def tariff_delete(request, pk):
    """Delete tariff - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    tariff = get_object_or_404(Tariff, pk=pk)
    
    # Check if tariff has any subscriptions
    subscription_count = tariff.subscriptions.count()
    if subscription_count > 0:
        messages.error(request, _(f"Cannot delete tariff '{tariff.title}'. It has {subscription_count} subscription(s) associated with it."))
        return redirect('billing:tariff_list')
    
    if request.method == 'POST':
        tariff_name = tariff.title
        tariff.delete()
        messages.success(request, _(f"Tariff '{tariff_name}' deleted successfully!"))
        return redirect('billing:tariff_list')
    
    return redirect('billing:tariff_list')


@login_required
def usage_tracking_list(request):
    """View usage tracking statistics - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    # Filters
    center_id = request.GET.get('center')
    year = request.GET.get('year', date.today().year)
    month = request.GET.get('month', date.today().month)
    min_orders = request.GET.get('min_orders')
    min_revenue = request.GET.get('min_revenue')
    min_bot_orders = request.GET.get('min_bot_orders')
    min_manual_orders = request.GET.get('min_manual_orders')
    min_branches = request.GET.get('min_branches')
    min_staff = request.GET.get('min_staff')
    sort_by = request.GET.get('sort', '-total_revenue')  # Default: highest revenue first
    
    usage_data = UsageTracking.objects.select_related('organization').all()
    
    if center_id:
        usage_data = usage_data.filter(organization_id=center_id)
    
    if year:
        usage_data = usage_data.filter(year=year)
    
    if month:
        usage_data = usage_data.filter(month=month)
    
    if min_orders:
        try:
            usage_data = usage_data.filter(orders_created__gte=int(min_orders))
        except ValueError:
            pass
    
    if min_revenue:
        try:
            usage_data = usage_data.filter(total_revenue__gte=float(min_revenue))
        except ValueError:
            pass

    if min_bot_orders:
        try:
            usage_data = usage_data.filter(bot_orders__gte=int(min_bot_orders))
        except ValueError:
            pass

    if min_manual_orders:
        try:
            usage_data = usage_data.filter(manual_orders__gte=int(min_manual_orders))
        except ValueError:
            pass

    if min_branches:
        try:
            usage_data = usage_data.filter(branches_count__gte=int(min_branches))
        except ValueError:
            pass

    if min_staff:
        try:
            usage_data = usage_data.filter(staff_count__gte=int(min_staff))
        except ValueError:
            pass
    
    # Add derived averages
    usage_data = usage_data.annotate(
        avg_revenue_per_order=Case(
            When(
                orders_created__gt=0,
                then=ExpressionWrapper(F('total_revenue') / F('orders_created'), output_field=FloatField()),
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )
    )

    # Apply sorting
    valid_sorts = [
        'organization__name', '-organization__name',
        'orders_created', '-orders_created',
        'bot_orders', '-bot_orders',
        'manual_orders', '-manual_orders',
        'branches_count', '-branches_count',
        'staff_count', '-staff_count',
        'total_revenue', '-total_revenue',
        'year', '-year', 'month', '-month'
    ]
    if sort_by in valid_sorts:
        usage_data = usage_data.order_by(sort_by, '-year', '-month')
    else:
        usage_data = usage_data.order_by('-total_revenue', '-year', '-month')
    
    # Pagination
    paginator = Paginator(usage_data, 20)
    page_number = request.GET.get('page')
    usage_page = paginator.get_page(page_number)
    
    # Get all centers for filter
    centers = TranslationCenter.objects.all().order_by('name')
    
    # Generate year and month ranges for filters
    current_year = date.today().year
    years = list(range(2024, current_year + 2))  # 2024 to current year + 1
    months = list(range(1, 13))  # 1 to 12
    
    # Calculate summary statistics
    total_orders = usage_data.aggregate(total=Sum('orders_created'))['total'] or 0
    total_revenue = usage_data.aggregate(total=Sum('total_revenue'))['total'] or 0
    total_bot_orders = usage_data.aggregate(total=Sum('bot_orders'))['total'] or 0
    total_manual_orders = usage_data.aggregate(total=Sum('manual_orders'))['total'] or 0
    avg_revenue_per_order = (total_revenue / total_orders) if total_orders else 0
    total_centers = usage_data.values('organization').distinct().count()
    
    context = {
        'title': _('Usage Tracking'),
        'subTitle': _('Usage Tracking'),
        'usage_data': usage_page,
        'centers': centers,
        'selected_center': center_id,
        'selected_year': year,
        'selected_month': month,
        'min_orders': min_orders,
        'min_revenue': min_revenue,
        'min_bot_orders': min_bot_orders,
        'min_manual_orders': min_manual_orders,
        'min_branches': min_branches,
        'min_staff': min_staff,
        'sort_by': sort_by,
        'years': years,
        'months': months,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_bot_orders': total_bot_orders,
        'total_manual_orders': total_manual_orders,
        'avg_revenue_per_order': avg_revenue_per_order,
        'total_centers': total_centers,
    }
    
    return render(request, 'billing/usage_tracking.html', context)


@login_required
def centers_list(request):
    """List all translation centers with subscription status - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    search_query = request.GET.get('search', '')
    sub_status = request.GET.get('sub_status', 'all')
    sort_by = request.GET.get('sort', 'name')

    centers = TranslationCenter.objects.select_related('owner').prefetch_related('subscription', 'subscription__tariff').all()
    
    if search_query:
        centers = centers.filter(
            Q(name__icontains=search_query) |
            Q(subdomain__icontains=search_query) |
            Q(owner__username__icontains=search_query)
        )

    if sub_status and sub_status != 'all':
        if sub_status == 'none':
            centers = centers.filter(subscription__isnull=True)
        else:
            centers = centers.filter(subscription__status=sub_status)

    if sort_by == 'end_date':
        centers = centers.order_by('subscription__end_date', 'name')
    elif sort_by == '-end_date':
        centers = centers.order_by('-subscription__end_date', 'name')
    elif sort_by == '-name':
        centers = centers.order_by('-name')
    else:
        centers = centers.order_by('name')
    
    # Add subscription status to each center
    for center in centers:
        if hasattr(center, 'subscription'):
            center.sub_status = center.subscription.status
            center.sub_tariff = center.subscription.tariff.title
            center.sub_end_date = center.subscription.end_date
        else:
            center.sub_status = None
            center.sub_tariff = None
            center.sub_end_date = None
    
    # Pagination
    paginator = Paginator(centers, 20)
    page_number = request.GET.get('page')
    centers_page = paginator.get_page(page_number)
    
    # Statistics
    total_centers = TranslationCenter.objects.count()
    with_subscription = TranslationCenter.objects.filter(subscription__isnull=False).count()
    without_subscription = total_centers - with_subscription
    
    context = {
        'title': _('All Translation Centers'),
        'subTitle': _('Centers'),
        'centers': centers_page,
        'search_query': search_query,
        'sub_status': sub_status,
        'sort_by': sort_by,
        'total_centers': total_centers,
        'with_subscription': with_subscription,
        'without_subscription': without_subscription,
    }
    
    return render(request, 'billing/centers_list.html', context)


@login_required
def extend_trial(request, pk):
    """Extend the trial end date for a specific subscription - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')

    subscription = get_object_or_404(Subscription, pk=pk)

    if not subscription.is_trial:
        messages.error(request, _("This subscription is not a trial subscription."))
        return redirect('billing:subscription_detail', pk=pk)

    if request.method == 'POST':
        new_end_date_str = request.POST.get('new_trial_end_date')
        try:
            new_end_date = datetime.strptime(new_end_date_str, '%Y-%m-%d').date()
            if new_end_date <= date.today():
                messages.error(request, _("New trial end date must be in the future."))
            else:
                # Update only this subscription's trial dates directly to avoid save() recalculation
                Subscription.objects.filter(pk=pk).update(
                    trial_end_date=new_end_date,
                    end_date=new_end_date,
                    status=Subscription.STATUS_ACTIVE,
                )
                _invalidate_monitoring_cache()
                messages.success(request, _("Trial period extended successfully."))
        except (ValueError, TypeError):
            messages.error(request, _("Invalid date format."))

    return redirect('billing:subscription_detail', pk=pk)


@login_required
def convert_trial_to_paid(request, pk):
    """Convert trial subscription to paid subscription - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    subscription = get_object_or_404(Subscription, pk=pk)
    
    if not subscription.is_trial:
        messages.error(request, _("This subscription is not a trial subscription."))
        return redirect('billing:subscription_detail', pk=pk)
    
    if request.method == 'POST':
        tariff_id = request.POST.get('tariff')
        pricing_id = request.POST.get('pricing')
        
        try:
            if not tariff_id or not pricing_id:
                messages.error(request, _("Please select both tariff and pricing option."))
                tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
                return render(request, 'billing/convert_trial.html', {'subscription': subscription, 'tariffs': tariffs})
            
            tariff = Tariff.objects.get(pk=tariff_id, is_trial=False)
            pricing = TariffPricing.objects.get(pk=pricing_id)
            
            if subscription.convert_trial_to_paid(tariff, pricing):
                _invalidate_monitoring_cache()  # reflect change immediately
                messages.success(request, _("Trial subscription converted to paid subscription successfully!"))
                return redirect('billing:subscription_detail', pk=pk)
            else:
                messages.error(request, _("Failed to convert trial subscription."))
        except Exception as e:
            messages.error(request, f"Error converting subscription: {str(e)}")
    
    # Get non-trial tariffs for conversion
    tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
    
    context = {
        'subscription': subscription,
        'tariffs': tariffs,
    }
    
    return render(request, 'billing/convert_trial.html', context)


@login_required
def subscription_renew(request, pk):
    """Renew subscription - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    subscription = get_object_or_404(Subscription, pk=pk)
    
    if request.method == 'POST':
        tariff_id = request.POST.get('tariff')
        pricing_id = request.GET.get('pricing_id') or request.POST.get('pricing')
        payment_method = request.POST.get('payment_method', '')
        transaction_id = request.POST.get('transaction_id', '')
        amount_paid = request.POST.get('amount_paid')
        notes = request.POST.get('notes', '')
        
        try:
            # Figure out the target tariff first (explicit selection overrides current one)
            tariff = Tariff.objects.get(pk=tariff_id) if tariff_id else subscription.tariff

            pricing = None

            if pricing_id:
                pricing = TariffPricing.objects.get(pk=pricing_id)
                tariff = pricing.tariff
            else:
                # If the chosen tariff has active pricing, a choice is required
                has_active_pricing = tariff.pricing.filter(is_active=True).exists()
                if has_active_pricing:
                    # Try to keep the current pricing if it belongs to the selected tariff
                    if subscription.pricing and subscription.pricing.tariff_id == tariff.id:
                        pricing = subscription.pricing
                    else:
                        messages.error(request, _("Please select a pricing option for this tariff."))
                        raise ValueError("pricing_required")
                # If no active pricing, allow renewing without a pricing option (treat as unlimited/manual)
            
            # Extend subscription
            old_end_date = subscription.end_date
            subscription.tariff = tariff
            subscription.pricing = pricing
            # start_date must move to old_end_date so that save()'s recalculation
            # (end_date = start_date + duration) produces the correct new end_date.
            # Without this, the trial/pre-payment period would be swallowed into
            # the paid period.
            subscription.start_date = old_end_date
            subscription.end_date = (
                old_end_date + relativedelta(months=pricing.duration_months)
                if pricing
                else old_end_date  # No pricing configured: keep current end date (treated as unlimited/manual)
            )
            subscription.status = Subscription.STATUS_PENDING
            subscription.payment_method = payment_method
            subscription.transaction_id = transaction_id
            subscription.notes = notes
            # A renewed subscription is always a paid one — clear any trial flags
            subscription.is_trial = False
            subscription.trial_end_date = None

            if amount_paid:
                subscription.amount_paid = amount_paid
                subscription.payment_date = datetime.now()
                subscription.status = Subscription.STATUS_ACTIVE
            
            subscription.save()
            
            # Log renewal
            period_text = (
                f"{pricing.duration_months} month(s)" if pricing else _("unlimited / no pricing")
            )
            description = _(
                "Subscription renewed for %(period)s. Extended from %(old)s to %(new)s"
            ) % {
                'period': period_text,
                'old': old_end_date,
                'new': subscription.end_date,
            }
            SubscriptionHistory.objects.create(
                subscription=subscription,
                action='renewed',
                description=description,
                performed_by=request.user
            )
            
            messages.success(request, _("Subscription renewed successfully!"))
            _invalidate_monitoring_cache()  # reflect change immediately
            return redirect('billing:subscription_detail', pk=pk)
            
        except Exception as e:
            if str(e) != "pricing_required":
                messages.error(request, f"Error renewing subscription: {str(e)}")
        
    # Get available pricing options for current or other tariffs
    # Get all active tariffs
    tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
    
    # Filter pricing in template or here
    # Since we're passing to template, let's create a list with filtered pricing
    tariffs_with_pricing = []
    for tariff in tariffs:
        # Convert to list so template can iterate properly
        tariff.active_pricing = list(tariff.pricing.filter(is_active=True))
        tariffs_with_pricing.append(tariff)
    
    context = {
        'subscription': subscription,
        'tariffs': tariffs_with_pricing,
    }
    
    return render(request, 'billing/subscription_renew.html', context)


@login_required
def subscription_analytics(request, center_id):
    """Detailed subscription analytics for a specific center - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    center = get_object_or_404(TranslationCenter, pk=center_id)
    
    # Get comprehensive analytics
    analytics = SubscriptionAnalytics.get_center_analytics(center)
    
    # Get payment history with details
    payment_history = Subscription.objects.filter(
        organization=center
    ).exclude(
        amount_paid__isnull=True
    ).exclude(
        amount_paid=0
    ).order_by('-payment_date')
    
    # Calculate monthly breakdown
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth
    
    monthly_payments = Subscription.objects.filter(
        organization=center,
        payment_date__isnull=False
    ).annotate(
        month=TruncMonth('payment_date')
    ).values('month').annotate(
        total=Sum('amount_paid'),
        count=Count('id')
    ).order_by('-month')[:12]
    
    context = {
        'center': center,
        'analytics': analytics,
        'payment_history': payment_history,
        'monthly_payments': monthly_payments,
    }
    
    return render(request, 'billing/subscription_analytics.html', context)


@login_required
def centers_monitoring(request):
    """Monitor all centers' subscription status - Superuser only"""
    if not request.user.is_superuser:
        messages.error(request, _("Access denied. This feature is only available to superusers."))
        return redirect('dashboard')
    
    # Get sorting parameters
    sort_by = request.GET.get('sort', 'payments')  # payments, age, subscriptions
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')  # all, active, expired, pending, none
    
    # ------------------------------------------------------------------
    # Redis cache strategy (5-minute TTL, single shared key):
    # get_all_centers_analytics() is the most expensive query in the project.
    # Only superusers reach this view, so one shared key is safe.
    # On Redis failure the code falls through to the original DB call.
    # ------------------------------------------------------------------
    CACHE_KEY = 'billing:centers_monitoring_data'
    CACHE_TTL = 300  # 5 minutes

    centers_data = None
    try:
        from django.core.cache import cache
        centers_data = cache.get(CACHE_KEY)
    except Exception:
        pass  # Redis unavailable — fall through

    if centers_data is None:
        centers_data = SubscriptionAnalytics.get_all_centers_analytics()
        try:
            from django.core.cache import cache
            cache.set(CACHE_KEY, centers_data, timeout=CACHE_TTL)
        except Exception:
            pass  # Redis write failure is harmless
    
    # Apply search filter (in-memory, on cached or freshly fetched data)
    if search_query:
        centers_data = [
            item for item in centers_data 
            if search_query.lower() in item['center'].name.lower() or 
               search_query.lower() in item['center'].subdomain.lower()
        ]

    if status_filter != 'all':
        if status_filter == 'none':
            centers_data = [item for item in centers_data if not item['current_subscription']]
        else:
            centers_data = [
                item for item in centers_data
                if item['current_subscription'] and item['current_subscription'].status == status_filter
            ]
    
    # Apply sorting
    if sort_by == 'age':
        centers_data.sort(key=lambda x: x['account_age_days'], reverse=True)
    elif sort_by == 'subscriptions':
        centers_data.sort(key=lambda x: x['total_subscriptions'], reverse=True)
    elif sort_by == 'name':
        centers_data.sort(key=lambda x: x['center'].name)
    # Default is already sorted by total_payments
    
    # Calculate totals
    total_revenue = sum(item['total_payments'] for item in centers_data)
    total_centers = len(centers_data)
    active_centers = sum(1 for item in centers_data if item['current_subscription'] and item['current_subscription'].is_active())
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(centers_data, 25)
    page_number = request.GET.get('page')
    centers_page = paginator.get_page(page_number)
    
    context = {
        'title': _('Centers Subscription Monitoring'),
        'subTitle': _('Monitoring'),
        'centers_data': centers_page,
        'sort_by': sort_by,
        'search_query': search_query,
        'total_revenue': total_revenue,
        'total_centers': total_centers,
        'active_centers': active_centers,
        'status_filter': status_filter,
    }
    
    return render(request, 'billing/centers_monitoring.html', context)


@login_required
def request_renewal(request):
    """Request subscription renewal - Regular user view"""
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
        messages.error(request, _("You don't have an admin profile associated with your account."))
        return redirect('dashboard')
    
    center = request.user.admin_profile.center
    
    # Check if center has subscription
    if not center or not hasattr(center, 'subscription'):
        messages.error(request, _("Your center doesn't have an active subscription."))
        return redirect('dashboard')
    
    subscription = center.subscription
    
    if request.method == 'POST':
        # Handle renewal request submission
        tariff_id = request.POST.get('tariff')
        pricing_id = request.POST.get('pricing')
        message = request.POST.get('message', '')
        
        try:
            # More specific error messages
            if not tariff_id:
                messages.error(request, _("Please select a tariff plan."))
                tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
                context = {
                    'title': _('Renew Subscription'),
                    'subTitle': _('Billing'),
                    'subscription': subscription,
                    'tariffs': tariffs,
                    'current_usage': {
                        'branches': center.branches.count(),
                        'staff': center.get_staff_count(),
                        'orders': center.get_current_month_orders_count(),
                        'broadcasts': center.get_current_month_broadcasts_count(),
                    }
                }
                return render(request, 'billing/request_renewal.html', context)
            
            if not pricing_id:
                messages.error(request, _("Please select a subscription duration."))
                tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
                context = {
                    'title': _('Renew Subscription'),
                    'subTitle': _('Billing'),
                    'subscription': subscription,
                    'tariffs': tariffs,
                    'current_usage': {
                        'branches': center.branches.count(),
                        'staff': center.get_staff_count(),
                        'orders': center.get_current_month_orders_count(),
                        'broadcasts': center.get_current_month_broadcasts_count(),
                    }
                }
                return render(request, 'billing/request_renewal.html', context)
            
            tariff = Tariff.objects.get(pk=tariff_id, is_active=True)
            pricing = TariffPricing.objects.get(pk=pricing_id, tariff=tariff)
            
            # Create note for admins
            renewal_request_note = f"""
Renewal Request from {center.name}
User: {request.user.get_full_name()} ({request.user.email})
Current Subscription: {subscription.tariff.title} (ends {subscription.end_date})
Requested Tariff: {tariff.title}
Requested Duration: {pricing.duration_months} months
Requested Price: {pricing.price:,} {pricing.currency}
User Message: {message}
Request Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
            """.strip()
            
            # Log the request in subscription history
            history_entry = SubscriptionHistory.objects.create(
                subscription=subscription,
                action='renewal_requested',
                description=renewal_request_note,
                performed_by=request.user
            )
            
            # Send telegram notification to admin
            try:
                send_renewal_request_notification(history_entry)
            except Exception as e:
                logger.error(f"Failed to send admin notification for renewal request: {e}")
            
            # Send success message
            messages.success(
                request, 
                _("Your renewal request has been submitted successfully! Our team will contact you shortly to process the payment.")
            )
            
            return redirect('billing:request_renewal')
            
        except Exception as e:
            messages.error(request, f"Error submitting renewal request: {str(e)}")
    
    # Get available tariffs for selection
    tariffs = Tariff.objects.filter(is_active=True, is_trial=False).prefetch_related('pricing')
    
    # Get current usage stats
    current_usage = {
        'branches': center.branches.count(),
        'staff': center.get_staff_count(),
        'orders': center.get_current_month_orders_count(),
        'broadcasts': center.get_current_month_broadcasts_count(),
    }
    
    context = {
        'title': _('Renew Subscription'),
        'subTitle': _('Billing'),
        'subscription': subscription,
        'tariffs': tariffs,
        'current_usage': current_usage,
    }
    
    return render(request, 'billing/request_renewal.html', context)


@login_required
def subscription_expired(request):
    """Blocked state page for users with expired or missing subscriptions."""
    if request.user.is_superuser:
        return redirect('dashboard')

    profile = getattr(request.user, 'admin_profile', None)
    if not profile or not profile.center:
        return redirect('dashboard')

    contact_email = os.getenv('SUPPORT_EMAIL', 'support@wowdash.com')
    contact_phone = os.getenv('SUPPORT_PHONE', '+998 (00) 000-00-00')

    context = {
        'title': _('Subscription expired'),
        'subTitle': _('Billing'),
        'contact_email': contact_email,
        'contact_phone': contact_phone,
    }

    return render(request, 'billing/subscription_expired.html', context)

