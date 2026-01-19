"""
RBAC (Role-Based Access Control) utilities for the translation center management system.

This module provides:
- Middleware for attaching admin profile to request
- Decorators for permission-based view access
- Helper functions for role checking
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied


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
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.admin_profile:
                messages.error(request, "You need an admin profile to access this page.")
                return redirect('index')
            
            # Check all required permissions
            for perm in permissions:
                if not request.admin_profile.has_permission(perm):
                    messages.error(request, "You don't have permission to perform this action.")
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
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if not request.admin_profile:
                messages.error(request, "You need an admin profile to access this page.")
                return redirect('index')
            
            # Check if user has ANY of the permissions
            has_any = any(request.admin_profile.has_permission(perm) for perm in permissions)
            if not has_any:
                messages.error(request, "You don't have permission to access this page.")
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
    Get roles that the user can assign to others.
    - Superusers can assign all roles including Owner
    - Owners can assign Manager and Staff roles
    - Managers can only assign Staff role
    """
    from organizations.models import Role
    
    if user.is_superuser:
        return Role.objects.filter(is_active=True)
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return Role.objects.none()
    
    if admin_profile.is_owner:
        # Owners can assign any role EXCEPT owner
        return Role.objects.filter(is_active=True).exclude(name=Role.OWNER)
    elif admin_profile.is_manager:
        # Managers can only assign staff role
        return Role.objects.filter(name=Role.STAFF, is_active=True)
    
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
    
    if user.is_superuser:
        return BotUser.objects.all()
    
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return BotUser.objects.none()
    
    accessible_branches = admin_profile.get_accessible_branches()
    return BotUser.objects.filter(branch__in=accessible_branches)


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
