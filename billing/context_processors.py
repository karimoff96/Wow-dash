"""
Context processor to make billing/subscription info available in all templates.
"""
from datetime import date

def billing_context(request):
    """
    Add billing and subscription information to template context.
    
    Available in all templates:
    - has_active_subscription: Boolean
    - user_tariff: Tariff object or None
    - subscription_status: Dict with subscription details
    - subscription_alert: Dict with alert information for display
    """
    context = {}
    
    if request.user.is_authenticated:
        # Superusers always have access
        if request.user.is_superuser:
            context['has_active_subscription'] = True
            context['user_tariff'] = None
            context['subscription_status'] = {
                'is_superuser': True,
                'has_subscription': True,
                'is_active': True
            }
            context['subscription_alert'] = None
            return context
        
        # Check center subscription
        if hasattr(request.user, 'admin_profile') and request.user.admin_profile:
            center = request.user.admin_profile.center
            
            if center and hasattr(center, 'subscription'):
                subscription = center.subscription
                days_remaining = subscription.days_remaining()
                
                context['has_active_subscription'] = subscription.is_active()
                context['user_tariff'] = subscription.tariff
                context['subscription_status'] = {
                    'has_subscription': True,
                    'is_active': subscription.is_active(),
                    'tariff_name': subscription.tariff.title,
                    'days_remaining': days_remaining,
                    'is_trial': subscription.is_trial,
                    'end_date': subscription.end_date,
                }
                
                # Determine alert level based on days remaining
                alert = None
                if days_remaining is not None:
                    if days_remaining < 0:
                        # Expired
                        alert = {
                            'level': 'critical',
                            'icon': 'ri-error-warning-line',
                            'bg_class': 'bg-danger-600',
                            'text_class': 'text-white',
                            'dismissible': False,
                            'days': days_remaining,
                            'end_date': subscription.end_date,
                        }
                    elif days_remaining <= 1:
                        # Less than 1 day - critical
                        alert = {
                            'level': 'urgent',
                            'icon': 'ri-alarm-warning-line',
                            'bg_class': 'bg-danger-600',
                            'text_class': 'text-white',
                            'dismissible': False,
                            'days': days_remaining,
                            'end_date': subscription.end_date,
                        }
                    elif days_remaining <= 3:
                        # 1-3 days - danger
                        alert = {
                            'level': 'danger',
                            'icon': 'ri-alert-line',
                            'bg_class': 'bg-warning-600',
                            'text_class': 'text-white',
                            'dismissible': True,
                            'dismiss_hours': 6,
                            'days': days_remaining,
                            'end_date': subscription.end_date,
                        }
                    elif days_remaining <= 7:
                        # 3-7 days - warning
                        alert = {
                            'level': 'warning',
                            'icon': 'ri-information-line',
                            'bg_class': 'bg-warning-100',
                            'text_class': 'text-warning-600',
                            'dismissible': True,
                            'dismiss_hours': 12,
                            'days': days_remaining,
                            'end_date': subscription.end_date,
                        }
                    elif days_remaining <= 14:
                        # 7-14 days - info
                        alert = {
                            'level': 'info',
                            'icon': 'ri-notification-3-line',
                            'bg_class': 'bg-info-100',
                            'text_class': 'text-info-600',
                            'dismissible': True,
                            'dismiss_hours': 24,
                            'days': days_remaining,
                            'end_date': subscription.end_date,
                        }
                
                context['subscription_alert'] = alert
            else:
                context['has_active_subscription'] = False
                context['user_tariff'] = None
                context['subscription_status'] = {
                    'has_subscription': False,
                    'is_active': False
                }
        else:
            context['has_active_subscription'] = False
            context['user_tariff'] = None
            context['subscription_status'] = {
                'has_subscription': False,
                'is_active': False
            }
    else:
        context['has_active_subscription'] = False
        context['user_tariff'] = None
        context['subscription_status'] = {
            'has_subscription': False,
            'is_active': False
        }
    
    return context
