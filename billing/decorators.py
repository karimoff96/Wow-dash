# Helper functions and decorators for tariff enforcement

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext as _
from django.http import JsonResponse


def _is_ajax(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept', '').startswith('application/json') or
        request.content_type == 'application/json'
    )


def require_active_subscription(view_func):
    """Decorator to ensure organization has active subscription"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Superusers always have access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Get center from admin_profile (set by RBACMiddleware on request)
        admin_profile = getattr(request, 'admin_profile', None)
        if not admin_profile:
            msg = _('No admin profile found.')
            if _is_ajax(request):
                return JsonResponse({'success': False, 'error': str(msg)}, status=403)
            messages.error(request, msg)
            return redirect('billing:subscription_list')
        
        center = admin_profile.center
        
        if not center or not hasattr(center, 'subscription') or not center.subscription.is_active():
            msg = _('Your subscription has expired or is not active. Please renew to continue.')
            if _is_ajax(request):
                return JsonResponse({'success': False, 'error': str(msg)}, status=403)
            messages.error(request, msg)
            return redirect('billing:subscription_list')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def require_feature(feature_code):
    """Decorator to restrict access based on tariff features"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers always have access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Get center from admin_profile (set by RBACMiddleware on request)
            admin_profile = getattr(request, 'admin_profile', None)
            if not admin_profile:
                msg = _('No admin profile found.')
                if _is_ajax(request):
                    return JsonResponse({'success': False, 'error': str(msg)}, status=403)
                messages.error(request, msg)
                return redirect('billing:subscription_list')

            center = admin_profile.center

            if not center or not hasattr(center, 'subscription'):
                msg = _('No active subscription found.')
                if _is_ajax(request):
                    return JsonResponse({'success': False, 'error': str(msg)}, status=403)
                messages.error(request, msg)
                return redirect('billing:subscription_list')

            if not center.subscription.tariff.has_feature(feature_code):
                msg = _('This feature is not available in your current plan. Please upgrade.')
                if _is_ajax(request):
                    return JsonResponse({'success': False, 'error': str(msg)}, status=403)
                messages.error(request, msg)
                return redirect('billing:tariff_list')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def check_branch_limit(view_func):
    """Check if organization can add more branches"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Superusers always have access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Get center from admin_profile
        if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
            messages.error(request, _("No admin profile found."))
            return redirect('billing:subscription_list')
        
        center = request.user.admin_profile.center
        
        if not center or not hasattr(center, 'subscription'):
            messages.error(request, _("No active subscription found."))
            return redirect('billing:subscription_list')
        
        if not center.subscription.can_add_branch():
            messages.error(
                request,
                _("You have reached your branch limit. Upgrade your plan to add more branches.")
            )
            return redirect('organizations:branch_list')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def check_staff_limit(view_func):
    """Check if organization can add more staff"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Superusers always have access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Get center from admin_profile
        if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
            messages.error(request, _("No admin profile found."))
            return redirect('billing:subscription_list')
        
        center = request.user.admin_profile.center
        
        if not center or not hasattr(center, 'subscription'):
            messages.error(request, _("No active subscription found."))
            return redirect('billing:subscription_list')
        
        if not center.subscription.can_add_staff():
            messages.error(
                request,
                _("You have reached your staff limit. Upgrade your plan to add more users.")
            )
            return redirect('usersList')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def check_order_limit(view_func):
    """Check if organization can create more orders this month"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Superusers always have access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Get center from admin_profile
        if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
            messages.error(request, _("No admin profile found."))
            return redirect('billing:subscription_list')
        
        center = request.user.admin_profile.center
        
        if not center or not hasattr(center, 'subscription'):
            messages.error(request, _("No active subscription found."))
            return redirect('billing:subscription_list')
        
        if not center.subscription.can_create_order():
            messages.error(
                request,
                _("You have reached your monthly order limit. Upgrade your plan or wait for next month.")
            )
            return redirect('orders:order_list')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def check_marketing_limit(view_func):
    """Check if organization can send more marketing broadcasts this month"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Superusers always have access
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
            messages.error(request, _("No admin profile found."))
            return redirect('billing:subscription_list')

        center = request.user.admin_profile.center

        if not center or not hasattr(center, 'subscription'):
            messages.error(request, _("No active subscription found."))
            return redirect('billing:subscription_list')

        if not center.subscription.can_send_broadcast():
            used, limit = center.subscription.get_broadcasts_limit_info()
            messages.error(
                request,
                _("You have reached your monthly broadcast limit (%(used)s/%(limit)s). "
                  "Upgrade your plan or wait for next month.") % {'used': used, 'limit': limit}
            )
            return redirect('marketing_list')

        return view_func(request, *args, **kwargs)
    return wrapper
