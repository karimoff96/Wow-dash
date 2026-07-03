"""
RBAC (Role-Based Access Control) utilities for the translation center management system.

This module provides:
- Middleware for attaching admin profile to request
- Decorators for permission-based view access
- Helper functions for role checking
"""

import logging
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def get_admin_profile(user):
    """
    Get the AdminUser profile for a Django user.
    Returns None if user doesn't have an admin profile.
    """
    if not user.is_authenticated:
        return None
    
    try:
        return user.admin_profile
    except AttributeError:
        return None


class RBACMiddleware:
    """
    Middleware that attaches admin profile and permissions to the request.
    
    After this middleware runs, you can access:
    - request.admin_profile: The AdminUser instance (or None)
    - request.user_role: The role name ('owner', 'manager', 'staff', or None)
    - request.is_owner: Boolean
    - request.is_manager: Boolean
    - request.is_staff_member: Boolean (different from is_staff which is Django's)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Attach admin profile info to request
        admin_profile = get_admin_profile(request.user)
        request.admin_profile = admin_profile
        
        if admin_profile:
            # Handle case where role might be None (for superusers with admin_profile)
            request.user_role = admin_profile.role.name if admin_profile.role else None
            request.is_owner = admin_profile.is_owner
            request.is_manager = admin_profile.is_manager
            request.is_staff_member = admin_profile.is_staff_role
            request.current_center = admin_profile.center
            request.current_branch = admin_profile.branch
        else:
            request.user_role = None
            request.is_owner = False
            request.is_manager = False
            request.is_staff_member = False
            request.current_center = None
            request.current_branch = None
        
        response = self.get_response(request)
        return response


def admin_profile_required(view_func):
    """
    Decorator that requires user to have an AdminUser profile.
    Superusers are always allowed.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not request.admin_profile:
            messages.error(request, "You need an admin profile to access this page.")
            return redirect('index')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    """
    DEPRECATED: Use @permission_required('can_...') instead.
    
    Role names can be arbitrary (e.g., "Director", "Admin", "Viewer").
    Access control should be based on permissions, not role names.
    
    This decorator is kept for backward compatibility only.
    
    Usage (deprecated):
        @role_required('owner')
        @role_required('owner', 'manager')
    
    Preferred approach:
        @permission_required('can_view_centers')
        @permission_required('can_edit_staff', 'can_delete_staff')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.admin_profile:
                messages.error(request, "You need an admin profile to access this page.")
                return redirect('index')
            
            if request.user_role not in allowed_roles:
                messages.error(request, "You don't have permission to access this page.")
                return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(*permissions):
    """
    Decorator that requires user to have all specified permissions.
    Superusers are always allowed.
    
    Usage:
        @permission_required('can_manage_orders')
        @permission_required('can_manage_staff', 'can_view_reports')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Superusers always have access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check for admin profile
            if not request.admin_profile:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but has no AdminUser profile"
                )
                messages.error(request, "You need an admin profile to access this page. Contact your administrator.")
                return redirect('index')
            
            # Check for active admin profile
            if not request.admin_profile.is_active:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but their AdminUser profile is inactive"
                )
                messages.error(request, "Your admin profile is inactive. Contact your administrator.")
                return redirect('index')
            
            # Check for role assignment
            if not request.admin_profile.role:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but has no role assigned"
                )
                messages.error(request, "You have no role assigned. Contact your administrator to assign you a role.")
                return redirect('index')
            
            # Check if role is active
            if not request.admin_profile.role.is_active:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but their role is inactive"
                )
                messages.error(request, "Your role is inactive. Contact your administrator.")
                return redirect('index')
            
            # Check all required permissions
            missing_perms = []
            for perm in permissions:
                if not request.admin_profile.has_permission(perm):
                    missing_perms.append(perm)
            
            if missing_perms:
                perm_names = ', '.join(missing_perms)
                logger.warning(
                    f"User {request.user.username} (role: {request.admin_profile.role.name}) "
                    f"tried to access {view_func.__name__} but lacks permissions: {perm_names}"
                )
                messages.error(
                    request, 
                    f"You don't have permission to perform this action. "
                    f"Missing: {perm_names}. Contact your administrator to grant these permissions."
                )
                return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def subscription_feature_required(*feature_codes):
    """
    Decorator that requires user's organization subscription to include specific features.
    This enables subscription-based feature gating.
    
    Superusers are always allowed.
    
    Usage:
        @subscription_feature_required('advanced_analytics')
        @subscription_feature_required('telegram_bot', 'marketing_tools')
        
    Example:
        @subscription_feature_required('advanced_analytics')
        def analytics_dashboard(request):
            # Only accessible if subscription includes 'advanced_analytics' feature
            return render(request, 'analytics.html')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.admin_profile:
                messages.error(request, "You need an admin profile to access this page.")
                return redirect('index')
            
            # Check all required subscription features
            for feature_code in feature_codes:
                if not request.admin_profile.has_subscription_feature(feature_code):
                    messages.error(
                        request, 
                        f"This feature is not available in your current subscription plan. "
                        f"Please upgrade to access this functionality."
                    )
                    return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_and_feature_required(permissions=None, features=None):
    """
    Combined decorator that checks both role permissions AND subscription features.
    User must have ALL specified permissions AND ALL specified features.
    
    Superusers are always allowed.
    
    Usage:
        @permission_and_feature_required(
            permissions=['can_view_analytics'],
            features=['advanced_analytics']
        )
        def advanced_analytics_view(request):
            # Requires both permission AND subscription feature
            return render(request, 'advanced_analytics.html')
    
    Args:
        permissions: List of permission codes to check (from Role model)
        features: List of feature codes to check (from subscription tariff)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.admin_profile:
                messages.error(request, "You need an admin profile to access this page.")
                return redirect('index')
            
            # Check role permissions
            if permissions:
                for perm in permissions:
                    if not request.admin_profile.has_permission(perm):
                        messages.error(request, "You don't have permission to perform this action.")
                        return redirect('index')
            
            # Check subscription features
            if features:
                for feature_code in features:
                    if not request.admin_profile.has_subscription_feature(feature_code):
                        messages.error(
                            request,
                            f"This feature is not available in your current subscription plan. "
                            f"Please upgrade to access this functionality."
                        )
                        return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission_check_func, error_message=None):
    """
    Decorator that requires custom permission check function to return True.
    
    Args:
        permission_check_func: A function that takes (user) and returns True/False
        error_message: Custom error message to display if permission denied
    
    Usage:
        def can_manage_payments(user):
            return user.is_superuser or (hasattr(user, 'admin_profile') and user.admin_profile.is_owner)
        
        @require_permission(can_manage_payments, 'Only owners can manage payments')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not permission_check_func(request.user):
                msg = error_message or "You don't have permission to access this page."
                messages.error(request, msg)
                return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def any_permission_required(*permissions):
    """
    Decorator that requires user to have ANY ONE of the specified permissions.
    Superusers are always allowed.
    
    Usage:
        @any_permission_required('can_view_reports', 'can_view_analytics')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Superusers always have access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check for admin profile
            if not request.admin_profile:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but has no AdminUser profile"
                )
                messages.error(request, "You need an admin profile to access this page. Contact your administrator.")
                return redirect('index')
            
            # Check for active admin profile
            if not request.admin_profile.is_active:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but their AdminUser profile is inactive"
                )
                messages.error(request, "Your admin profile is inactive. Contact your administrator.")
                return redirect('index')
            
            # Check for role assignment
            if not request.admin_profile.role:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but has no role assigned"
                )
                messages.error(request, "You have no role assigned. Contact your administrator to assign you a role.")
                return redirect('index')
            
            # Check if role is active
            if not request.admin_profile.role.is_active:
                logger.warning(
                    f"User {request.user.username} tried to access {view_func.__name__} "
                    f"but their role is inactive"
                )
                messages.error(request, "Your role is inactive. Contact your administrator.")
                return redirect('index')
            
            # Check if user has ANY of the permissions
            has_any = any(request.admin_profile.has_permission(perm) for perm in permissions)
            if not has_any:
                # More helpful error message
                perm_names = ', '.join(permissions)
                logger.warning(
                    f"User {request.user.username} (role: {request.admin_profile.role.name}) "
                    f"tried to access {view_func.__name__} but lacks permissions: {perm_names}"
                )
                messages.error(
                    request, 
                    f"You don't have permission to perform this action. "
                    f"Required: {perm_names}. Contact your administrator to grant these permissions."
                )
                return redirect('index')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def owner_required(view_func):
    """
    DEPRECATED: Use @permission_required('can_...') instead.
    
    Role names can be anything, permissions are what define functionality.
    This decorator is kept for backward compatibility only.
    """
    return role_required('owner')(view_func)


def manager_or_owner_required(view_func):
    """
    DEPRECATED: Use @permission_required('can_...') instead.
    
    Role names can be anything, permissions are what define functionality.
    This decorator is kept for backward compatibility only.
    """
    return role_required('owner', 'manager')(view_func)


def can_view_staff_required(view_func):
    """Decorator for views that require can_view_staff or can_manage_staff permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not request.admin_profile:
            messages.error(request, "You need an admin profile to access this page.")
            return redirect('index')
        
        # Check if user has either view or manage staff permission
        if not (request.admin_profile.has_permission('can_view_staff') or 
                request.admin_profile.has_permission('can_manage_staff')):
            messages.error(request, "You don't have permission to view staff details.")
            return redirect('index')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def can_edit_staff(user, staff_member=None):
    """
    Check if user can edit staff members.
    - Superusers can edit anyone
    - Owners can edit anyone in their center (except other owners)
    - Managers can only view, not edit (unless can_manage_staff is granted)
    """
    if user.is_superuser:
        return True
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return False
    
    # Must have can_manage_staff permission
    if not admin_profile.has_permission('can_manage_staff'):
        return False
    
    # If checking specific staff member
    if staff_member:
        # Cannot edit owners unless you're superuser
        if staff_member.is_owner:
            return False
        
        # Must be in same center
        if admin_profile.center and staff_member.center:
            return admin_profile.center.id == staff_member.center.id
    
    return True


def get_assignable_roles(user):
    """
    Get active roles that the user can assign to others.

    Rules:
    - Superusers can assign all active roles (including Owner)
    - Non-superusers can never assign Owner
    - Role-name hierarchy is preserved for system Manager (cannot assign Manager)
    - Users with `can_manage_staff` can assign remaining active roles
    - Users with only `can_create_staff` can assign low-privilege roles
    """
    from organizations.models import Role
    
    roles = Role.objects.filter(is_active=True)

    if user.is_superuser:
        return roles
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return Role.objects.none()
    
    if not admin_profile.role:
        return Role.objects.none()

    # Non-superusers can never assign Owner
    roles = roles.exclude(name=Role.OWNER)

    # Preserve legacy manager restriction by system role name
    if admin_profile.role.name == Role.MANAGER:
        roles = roles.exclude(name=Role.MANAGER)

    if admin_profile.has_permission('can_manage_staff'):
        return roles

    if admin_profile.has_permission('can_create_staff'):
        # Allow creation only into low-privilege roles
        return roles.exclude(can_manage_staff=True).exclude(can_create_staff=True).exclude(can_edit_staff=True).exclude(can_delete_staff=True)

    return Role.objects.none()


def validate_owner_creation(requesting_user, center=None):
    """
    Validate that the requesting user can create an owner.
    Returns (is_valid, error_message)
    
    Note: Superusers can always create/assign owners. 
    If a center already has an owner, the previous owner will be unlinked.
    """
    from organizations.models import AdminUser, Role
    
    # Only superusers can create owners
    if not requesting_user.is_superuser:
        return False, "Only superusers can create the Owner role."
    
    # Superusers can always assign - previous owner will be replaced
    return True, None


def branch_access_required(view_func):
    """
    Decorator that checks if user can access the branch specified in URL.
    Expects 'branch_id' in kwargs.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from organizations.models import Branch
        
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        branch_id = kwargs.get('branch_id')
        if not branch_id:
            return view_func(request, *args, **kwargs)
        
        try:
            branch = Branch.objects.get(pk=branch_id)
        except Branch.DoesNotExist:
            messages.error(request, "Branch not found.")
            return redirect('index')
        
        if not request.admin_profile or not request.admin_profile.can_access_branch(branch):
            messages.error(request, "You don't have access to this branch.")
            return redirect('index')
        
        # Attach branch to request for convenience
        request.target_branch = branch
        return view_func(request, *args, **kwargs)
    return wrapper


class RBACMixin:
    """
    Mixin for class-based views that provides RBAC functionality.
    
    Usage:
        class MyView(RBACMixin, View):
            required_roles = ['owner', 'manager']
            required_permissions = ['can_manage_orders']
    """
    required_roles = None  # List of allowed roles, None means all roles
    required_permissions = None  # List of required permissions
    
    def dispatch(self, request, *args, **kwargs):
        # Superusers bypass all checks
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        # Check for admin profile
        if not request.admin_profile:
            messages.error(request, "You need an admin profile to access this page.")
            return redirect('index')
        
        # Check roles
        if self.required_roles and request.user_role not in self.required_roles:
            messages.error(request, "You don't have permission to access this page.")
            return redirect('index')
        
        # Check permissions
        if self.required_permissions:
            for perm in self.required_permissions:
                if not request.admin_profile.has_permission(perm):
                    messages.error(request, "You don't have permission to perform this action.")
                    return redirect('index')
        
        return super().dispatch(request, *args, **kwargs)


# ============ Query Helpers ============

def get_user_branches(user):
    """Get all branches accessible by this user."""
    from organizations.models import Branch
    
    if user.is_superuser:
        return Branch.objects.filter(is_active=True)
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return Branch.objects.none()
    
    return admin_profile.get_accessible_branches()


def get_user_orders(user):
    """Get all orders accessible by this user."""
    from orders.models import Order
    
    if user.is_superuser:
        return Order.objects.all()
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return Order.objects.none()
    
    # Check if user is center owner (either by role or by ownership)
    is_center_owner = (admin_profile.is_owner or 
                       (admin_profile.center and 
                        admin_profile.center.owner_id == user.id))
    
    # If center owner, get all center orders
    if is_center_owner and admin_profile.center:
        return Order.objects.filter(branch__center=admin_profile.center)
    
    # Get accessible branches
    accessible_branches = admin_profile.get_accessible_branches()
    
    # If user has view_all_orders permission, show all orders in their branches
    if admin_profile.has_permission('can_view_all_orders'):
        return Order.objects.filter(branch__in=accessible_branches)
    
    # If user has reporting/financial permissions, show all branch orders (not just assigned)
    if (admin_profile.has_permission('can_view_financial_reports') or
        admin_profile.has_permission('can_view_reports') or
        admin_profile.has_permission('can_view_analytics')):
        return Order.objects.filter(branch__in=accessible_branches)
    
    # If staff role without special permissions, only show orders assigned to them
    if admin_profile.is_staff_role:
        return Order.objects.filter(
            branch__in=accessible_branches,
            assigned_to=admin_profile
        )
    
    # For managers/other roles, show all orders in their branches
    return Order.objects.filter(branch__in=accessible_branches)


def get_user_customers(user):
    """Get all customers (BotUsers) accessible by this user."""
    from accounts.models import BotUser
    from django.db.models import Q
    
    if user.is_superuser:
        return BotUser.objects.all()
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return BotUser.objects.none()
    
    accessible_branches = admin_profile.get_accessible_branches()
    
    # Include customers who:
    # 1. Are assigned to one of the accessible branches
    # 2. Have orders in one of the accessible branches (even if customer.branch is None)
    return BotUser.objects.filter(
        Q(branch__in=accessible_branches) | 
        Q(order__branch__in=accessible_branches)
    ).distinct()


def get_user_staff(user):
    """Get all staff members accessible by this user (for management)."""
    from organizations.models import AdminUser
    
    if user.is_superuser:
        return AdminUser.objects.all()
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return AdminUser.objects.none()
    
    # Check if user is center owner (either by role or by ownership)
    is_center_owner = (admin_profile.is_owner or 
                       (admin_profile.center and 
                        admin_profile.center.owner_id == user.id))
    
    if is_center_owner and admin_profile.center:
        # Owners can see all staff in their center
        return AdminUser.objects.filter(
            center=admin_profile.center
        ).exclude(pk=admin_profile.pk)
    elif admin_profile.has_permission('can_manage_staff') and admin_profile.center:
        # Users with manage_staff permission can see all staff in their center
        return AdminUser.objects.filter(
            center=admin_profile.center
        ).exclude(pk=admin_profile.pk)
    elif admin_profile.is_manager and admin_profile.branch:
        # Managers can see staff in their branch (excluding owners)
        return AdminUser.objects.filter(
            branch=admin_profile.branch
        ).exclude(pk=admin_profile.pk).exclude(role__name='owner')
    
    return AdminUser.objects.none()


def get_user_categories(user):
    """Get all categories accessible by this user."""
    from services.models import Category
    
    if user.is_superuser:
        return Category.objects.all()
    
    accessible_branches = get_user_branches(user)
    return Category.objects.filter(branch__in=accessible_branches)


def get_user_products(user):
    """Get all products accessible by this user."""
    from services.models import Product
    
    if user.is_superuser:
        return Product.objects.all()
    
    accessible_branches = get_user_branches(user)
    return Product.objects.filter(category__branch__in=accessible_branches)


def get_user_expenses(user):
    """Get all expenses accessible by this user."""
    from services.models import Expense
    
    if user.is_superuser:
        return Expense.objects.all()
    
    accessible_branches = get_user_branches(user)
    return Expense.objects.filter(branch__in=accessible_branches)


def get_user_languages(user):
    """Get all languages accessible by this user."""
    from services.models import Language

    if user.is_superuser:
        return Language.objects.all()

    accessible_branches = get_user_branches(user)
    return Language.objects.filter(branch__in=accessible_branches)
