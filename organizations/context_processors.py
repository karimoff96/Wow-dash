"""
Context processors for the translation center management system.
Provides role and permission info to all templates.
"""

import logging
from organizations.rbac import get_admin_profile

logger = logging.getLogger(__name__)


def rbac_context(request):
    """
    Add RBAC-related variables to template context.
    
    Available in templates:
    - admin_profile: The AdminUser instance
    - user_role: Role name ('owner', 'manager', 'staff')
    - is_owner: Boolean
    - is_manager: Boolean  
    - is_staff_member: Boolean
    - current_center: TranslationCenter instance
    - current_branch: Branch instance
    - permissions: Dict of all permissions (granular)
    """
    # Define all available permissions
    all_permissions = {
        # Organization Management - Centers
        'can_manage_centers': False,
        'can_view_centers': False,
        'can_create_centers': False,
        'can_edit_centers': False,
        'can_delete_centers': False,
        # Organization Management - Branches
        'can_manage_branches': False,
        'can_view_branches': False,
        'can_create_branches': False,
        'can_edit_branches': False,
        'can_delete_branches': False,
        # Staff Management
        'can_manage_staff': False,
        'can_view_staff': False,
        'can_create_staff': False,
        'can_edit_staff': False,
        'can_delete_staff': False,
        # Order Management (Granular)
        'can_view_all_orders': False,
        'can_view_own_orders': False,
        'can_create_orders': False,
        'can_edit_orders': False,
        'can_delete_orders': False,
        'can_assign_orders': False,
        'can_update_order_status': False,
        'can_complete_orders': False,
        'can_cancel_orders': False,
        'can_manage_orders': False,
        # Financial
        'can_manage_financial': False,
        'can_receive_payments': False,
        'can_view_financial_reports': False,
        'can_apply_discounts': False,
        'can_refund_orders': False,
        'can_manage_bulk_payments': False,
        'can_assign_bulk_payment_permission': False,
        # Reports & Analytics
        'can_manage_reports': False,
        'can_view_reports': False,
        'can_view_analytics': False,
        'can_export_data': False,
        # Products
        'can_manage_products': False,
        'can_view_products': False,
        'can_create_products': False,
        'can_edit_products': False,
        'can_delete_products': False,
        # Expenses
        'can_manage_expenses': False,
        'can_view_expenses': False,
        'can_create_expenses': False,
        'can_edit_expenses': False,
        'can_delete_expenses': False,
        # Languages
        'can_manage_languages': False,
        'can_view_languages': False,
        'can_create_languages': False,
        'can_edit_languages': False,
        'can_delete_languages': False,
        # Customers
        'can_manage_customers': False,
        'can_view_customers': False,
        'can_create_customers': False,
        'can_edit_customers': False,
        'can_delete_customers': False,
        # Marketing & Broadcasts
        'can_manage_marketing': False,
        'can_create_marketing_posts': False,
        'can_send_branch_broadcasts': False,
        'can_send_center_broadcasts': False,
        'can_view_broadcast_stats': False,
        # Branch Settings
        'can_manage_branch_settings': False,
        'can_view_branch_settings': False,
        # Agencies
        'can_manage_agencies': False,
        'can_view_agencies': False,
        'can_create_agencies': False,
        'can_edit_agencies': False,
        'can_delete_agencies': False,
        # Audit Logs
        'can_manage_audit_logs': False,
        'can_view_audit_logs': False,
        'can_export_audit_logs': False,
        'can_grant_audit_permissions': False,
    }
    
    context = {
        'admin_profile': None,
        'user_role': None,
        'user_role_display': None,
        'is_owner': False,
        'is_manager': False,
        'is_staff_member': False,
        'current_center': None,
        'current_branch': None,
        'permissions': all_permissions.copy(),
        'admin_notifications': [],
        'unread_notifications_count': 0,
    }
    
    if not request.user.is_authenticated:
        return context
    
    # Get admin notifications for authenticated users
    try:
        from core.models import AdminNotification
        notifications = AdminNotification.get_unread_for_user(request.user, limit=10)
        context['admin_notifications'] = list(notifications)
        context['unread_notifications_count'] = AdminNotification.count_unread_for_user(request.user)
    except Exception as e:
        logger.debug(f" Failed to get notifications: {e}")
    
    # Superuser has all permissions
    if request.user.is_superuser:
        superuser_permissions = {k: True for k in all_permissions}
        context.update({
            'user_role': 'superuser',
            'user_role_display': 'Super Admin',
            'is_owner': True,
            'is_manager': True,
            'is_staff_member': False,  # Superuser is not a staff member - they see aggregated data
            'permissions': superuser_permissions,
        })
        return context
    
    admin_profile = get_admin_profile(request.user)
    
    if admin_profile:
        role = admin_profile.role
        # Build permissions dict from role fields
        # Use has_permission method to support master permission inheritance
        permissions = {}
        if role:
            for perm_name in all_permissions.keys():
                permissions[perm_name] = admin_profile.has_permission(perm_name)
        else:
            # No role assigned - no permissions
            permissions = all_permissions.copy()
        
        # Determine access level purely from permissions — role name is irrelevant.
        # Any role (owner, founder, worker, or any future custom role) gets the
        # same UI capabilities as long as it has the matching permissions.
        # is_owner  → has financial management access (the broadest indicator)
        # is_manager → has order management access but not financial
        # is_staff_member → everything else
        computed_is_owner = (
            permissions.get('can_manage_financial', False)
            or permissions.get('can_view_financial_reports', False)
        )
        computed_is_manager = (
            not computed_is_owner
            and (
                permissions.get('can_manage_orders', False)
                or permissions.get('can_view_all_orders', False)
            )
        )
        computed_is_staff = not computed_is_owner and not computed_is_manager

        context.update({
            'admin_profile': admin_profile,
            'user_role': role.name if role else None,
            'user_role_display': (role.display_name or role.name.title()) if role else 'No Role',
            'is_owner': computed_is_owner,
            'is_manager': computed_is_manager,
            'is_staff_member': computed_is_staff,
            'current_center': admin_profile.center,
            'current_branch': admin_profile.branch,
            'permissions': permissions,
        })
    
    return context


def site_settings(request):
    """
    Add site-wide settings to template context.
    
    Available in templates:
    - main_domain: The main domain (e.g., 'alltranslation.uz')
    """
    from django.conf import settings
    return {
        'main_domain': getattr(settings, 'MAIN_DOMAIN', 'alltranslation.uz'),
    }
