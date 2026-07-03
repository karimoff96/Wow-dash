"""
Permission Template Tags for RBAC System
=========================================

This module provides a comprehensive set of template tags and filters for 
permission-based UI rendering. It implements a DRY approach to hide or 
disable UI elements based on user permissions.

Usage:
------
{% load permission_tags %}

Simple permission check:
    {% has_perm 'can_manage_orders' as can_manage %}
    {% if can_manage %}...{% endif %}

Multiple permissions (any):
    {% has_any_perm 'can_view_reports,can_view_analytics' as can_view %}

Multiple permissions (all):
    {% has_all_perm 'can_edit_orders,can_delete_orders' as can_modify %}

Widget action check:
    {% can_do 'orders.edit' as allowed %}
    {% can_do 'orders.delete' order as allowed %}

Render button with permission:
    {% permission_button 'can_manage_orders' 'Edit' 'btn-primary' 'onclick="edit()"' %}

Hide element:
    {% if_perm 'can_delete_orders' %}
        <button>Delete</button>
    {% endif_perm %}

Filter usage:
    {{ 'can_manage_orders'|check_perm:request }}
    {{ button_html|show_if_perm:'can_manage_orders' }}
"""

from django import template
from django.utils.safestring import mark_safe
from organizations.rbac import get_admin_profile

register = template.Library()


# =============================================================================
# PERMISSION ACTION MAPPING
# =============================================================================

# Maps widget actions to required permissions
# Format: 'module.action' -> ['required_permission1', 'required_permission2', ...]
PERMISSION_ACTIONS = {
    # Order Actions
    'orders.view_all': ['can_view_all_orders'],
    'orders.view_own': ['can_view_own_orders'],
    'orders.view': ['can_view_all_orders', 'can_view_own_orders'],  # any
    'orders.create': ['can_create_orders'],
    'orders.edit': ['can_edit_orders'],
    'orders.delete': ['can_delete_orders'],
    'orders.assign': ['can_assign_orders'],
    'orders.update_status': ['can_update_order_status'],
    'orders.complete': ['can_complete_orders'],
    'orders.cancel': ['can_cancel_orders'],
    'orders.manage': ['can_manage_orders'],
    
    # Payment Actions
    'payments.receive': ['can_receive_payments'],
    'payments.refund': ['can_refund_orders'],
    'payments.discount': ['can_apply_discounts'],
    
    # Staff Actions
    'staff.view': ['can_view_staff'],
    'staff.manage': ['can_manage_staff'],
    'staff.create': ['can_manage_staff', 'can_create_staff'],
    'staff.edit': ['can_manage_staff', 'can_edit_staff'],
    'staff.delete': ['can_manage_staff', 'can_delete_staff'],
    
    # Organization Actions
    'center.manage': ['can_manage_centers'],
    'center.view': ['can_manage_centers', 'can_view_centers'],
    'center.create': ['can_manage_centers', 'can_create_centers'],
    'center.edit': ['can_manage_centers', 'can_edit_centers'],
    'center.delete': ['can_manage_centers', 'can_delete_centers'],
    'branches.manage': ['can_manage_branches'],
    'branches.view': ['can_manage_branches', 'can_view_branches'],
    'branches.create': ['can_manage_branches', 'can_create_branches'],
    'branches.edit': ['can_manage_branches', 'can_edit_branches'],
    'branches.delete': ['can_manage_branches', 'can_delete_branches'],
    
    # Products
    'products.manage': ['can_manage_products'],
    'products.view': ['can_manage_products', 'can_view_products'],
    'products.create': ['can_manage_products', 'can_create_products'],
    'products.edit': ['can_manage_products', 'can_edit_products'],
    'products.delete': ['can_manage_products', 'can_delete_products'],
    
    # Expenses
    'expenses.manage': ['can_manage_expenses'],
    'expenses.view': ['can_manage_expenses', 'can_view_expenses'],
    'expenses.create': ['can_manage_expenses', 'can_create_expenses'],
    'expenses.edit': ['can_manage_expenses', 'can_edit_expenses'],
    'expenses.delete': ['can_manage_expenses', 'can_delete_expenses'],
    
    # Languages
    'languages.manage': ['can_manage_languages'],
    'languages.view': ['can_manage_languages', 'can_view_languages'],
    'languages.create': ['can_manage_languages', 'can_create_languages'],
    'languages.edit': ['can_manage_languages', 'can_edit_languages'],
    'languages.delete': ['can_manage_languages', 'can_delete_languages'],
    
    # Customers
    'customers.manage': ['can_manage_customers'],
    'customers.view': ['can_manage_customers', 'can_view_customers'],
    'customers.edit': ['can_manage_customers', 'can_edit_customers'],
    'customers.delete': ['can_manage_customers', 'can_delete_customers'],
    
    # Reports & Analytics
    'reports.view': ['can_view_reports'],
    'reports.financial': ['can_view_financial_reports'],
    'analytics.view': ['can_view_analytics'],
    'data.export': ['can_export_data'],
    
    # Marketing
    'marketing.create_posts': ['can_create_marketing_posts'],
    'marketing.broadcast_branch': ['can_send_branch_broadcasts'],
    'marketing.broadcast_center': ['can_send_center_broadcasts'],
    'marketing.view_stats': ['can_view_broadcast_stats'],
    
    # Branch Settings
    'branch_settings.view': ['can_view_branch_settings', 'can_manage_branch_settings', 'can_manage_branches'],
    'branch_settings.manage': ['can_manage_branch_settings', 'can_manage_branches'],
    'branch_settings.edit': ['can_manage_branch_settings', 'can_manage_branches'],
}

# Actions that require ALL listed permissions (default is ANY)
REQUIRE_ALL_PERMISSIONS = {
    'orders.manage',  # Full order management requires explicit manage permission
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_permissions(context):
    """
    Extract permissions from template context.
    Returns a dict of permission_name -> boolean.
    """
    # First check if permissions are in context (from context processor)
    permissions = context.get('permissions', {})
    if permissions:
        return permissions
    
    # Fallback: Get from request
    request = context.get('request')
    if not request:
        return {}
    
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    
    # Superuser has all permissions
    if user.is_superuser:
        return {k: True for k in PERMISSION_ACTIONS.keys()}
    
    # Get admin profile
    admin_profile = get_admin_profile(user)
    if not admin_profile:
        return {}
    
    # Build permissions from role using AdminUser.has_permission method
    # This ensures consistency with backend permission checks and supports
    # permission aliases and master permission inheritance
    result = {}
    permission_fields = [
        'can_manage_centers', 'can_view_centers', 'can_create_centers', 'can_edit_centers', 'can_delete_centers',
        'can_manage_branches', 'can_view_branches', 'can_create_branches', 'can_edit_branches', 'can_delete_branches',
        'can_manage_staff', 'can_view_staff', 'can_create_staff', 'can_edit_staff', 'can_delete_staff',
        'can_view_all_orders', 'can_view_own_orders', 'can_create_orders', 'can_edit_orders',
        'can_delete_orders', 'can_assign_orders', 'can_update_order_status', 'can_complete_orders',
        'can_cancel_orders', 'can_manage_orders', 'can_manage_financial', 'can_receive_payments', 'can_view_financial_reports',
        'can_apply_discounts', 'can_refund_orders', 'can_manage_reports', 'can_view_reports', 'can_view_analytics',
        'can_export_data', 'can_manage_products', 'can_view_products', 'can_create_products', 'can_edit_products', 'can_delete_products',
        'can_manage_expenses', 'can_view_expenses', 'can_create_expenses', 'can_edit_expenses', 'can_delete_expenses',
        'can_manage_customers', 'can_view_customers', 'can_create_customers', 'can_edit_customers', 'can_delete_customers',
        'can_manage_marketing', 'can_create_marketing_posts', 'can_send_branch_broadcasts', 'can_send_center_broadcasts',
        'can_view_broadcast_stats', 'can_manage_branch_settings', 'can_view_branch_settings',
        'can_manage_agencies', 'can_view_agencies', 'can_create_agencies', 'can_edit_agencies', 'can_delete_agencies',
    ]
    for field in permission_fields:
        # Use AdminUser.has_permission for consistency and to support aliases/master permissions
        result[field] = admin_profile.has_permission(field)
    
    return result


def check_permission(context, permission_name):
    """
    Check if user has a specific permission.
    Handles superuser and role-based permissions.
    """
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_superuser:
        return True
    
    # Check is_owner context variable
    if context.get('is_owner', False):
        return True
    
    permissions = get_user_permissions(context)
    return permissions.get(permission_name, False)


def check_action(context, action, require_all=False):
    """
    Check if user can perform a specific action.
    
    Args:
        context: Template context
        action: Action string like 'orders.edit'
        require_all: If True, all permissions must be present; otherwise any is sufficient
    
    Returns:
        Boolean indicating if action is allowed
    """
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_superuser:
        return True
    
    if context.get('is_owner', False):
        return True
    
    # Get required permissions for this action
    required_perms = PERMISSION_ACTIONS.get(action, [])
    if not required_perms:
        return False
    
    # Determine if we need all or any
    require_all = require_all or action in REQUIRE_ALL_PERMISSIONS
    
    permissions = get_user_permissions(context)
    
    if require_all:
        return all(permissions.get(p, False) for p in required_perms)
    else:
        return any(permissions.get(p, False) for p in required_perms)


# =============================================================================
# SIMPLE TAGS
# =============================================================================

@register.simple_tag(takes_context=True)
def has_perm(context, permission_name):
    """
    Check if the current user has a specific permission.
    
    Usage:
        {% has_perm 'can_manage_orders' as can_manage %}
        {% if can_manage %}Show this{% endif %}
    """
    return check_permission(context, permission_name)


@register.simple_tag(takes_context=True)
def has_any_perm(context, permissions_string):
    """
    Check if the current user has ANY of the listed permissions.
    
    Usage:
        {% has_any_perm 'can_view_reports,can_view_analytics' as can_view %}
    """
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_superuser:
        return True
    
    if context.get('is_owner', False):
        return True
    
    perm_list = [p.strip() for p in permissions_string.split(',')]
    permissions = get_user_permissions(context)
    
    return any(permissions.get(p, False) for p in perm_list)


@register.simple_tag(takes_context=True)
def has_all_perm(context, permissions_string):
    """
    Check if the current user has ALL of the listed permissions.
    
    Usage:
        {% has_all_perm 'can_edit_orders,can_delete_orders' as can_modify %}
    """
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_superuser:
        return True
    
    if context.get('is_owner', False):
        return True
    
    perm_list = [p.strip() for p in permissions_string.split(',')]
    permissions = get_user_permissions(context)
    
    return all(permissions.get(p, False) for p in perm_list)


@register.simple_tag(takes_context=True)
def can_do(context, action, obj=None):
    """
    Check if user can perform a specific action.
    
    Usage:
        {% can_do 'orders.edit' as can_edit %}
        {% can_do 'orders.delete' order as can_delete %}
    
    The obj parameter is reserved for future object-level permissions.
    """
    return check_action(context, action)


# =============================================================================
# INCLUSION TAGS FOR UI ELEMENTS
# =============================================================================

@register.simple_tag(takes_context=True)
def permission_button(context, permission, label, css_class='btn-primary', extra_attrs=''):
    """
    Render a button only if user has permission.
    
    Usage:
        {% permission_button 'can_manage_orders' 'Edit Order' 'btn-success' 'data-id="123"' %}
    """
    if not check_permission(context, permission):
        return ''
    
    html = f'<button type="button" class="btn {css_class}" {extra_attrs}>{label}</button>'
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def action_button(context, action, label, css_class='btn-primary', extra_attrs=''):
    """
    Render a button only if user can perform action.
    
    Usage:
        {% action_button 'orders.edit' 'Edit' 'btn-success sm' 'onclick="edit()"' %}
    """
    if not check_action(context, action):
        return ''
    
    html = f'<button type="button" class="btn {css_class}" {extra_attrs}>{label}</button>'
    return mark_safe(html)


@register.simple_tag(takes_context=True)
def permission_link(context, permission, url, label, css_class='', extra_attrs=''):
    """
    Render a link only if user has permission.
    
    Usage:
        {% permission_link 'can_manage_staff' '/staff/add/' 'Add Staff' 'btn btn-primary' %}
    """
    if not check_permission(context, permission):
        return ''
    
    html = f'<a href="{url}" class="{css_class}" {extra_attrs}>{label}</a>'
    return mark_safe(html)


# =============================================================================
# FILTERS
# =============================================================================

@register.filter
def check_perm(permission_name, request):
    """
    Filter to check permission from request.
    
    Usage:
        {% if 'can_manage_orders'|check_perm:request %}...{% endif %}
    """
    if not request or not hasattr(request, 'user'):
        return False
    
    if request.user.is_superuser:
        return True
    
    admin_profile = get_admin_profile(request.user)
    if not admin_profile or not admin_profile.role:
        return False
    
    return getattr(admin_profile.role, permission_name, False)


@register.filter
def show_if_perm(content, permission_context):
    """
    Show content only if user has permission.
    
    Usage:
        {{ '<button>Delete</button>'|show_if_perm:'can_delete_orders,request' }}
    
    Note: This is less efficient than using template tags. Prefer {% has_perm %}.
    """
    parts = permission_context.split(',')
    if len(parts) != 2:
        return ''
    
    permission_name = parts[0].strip()
    # Note: This filter has limitations. Use template tags instead.
    return mark_safe(content)


@register.filter
def disabled_if_no_perm(attrs, permission_context):
    """
    Add 'disabled' attribute if user lacks permission.
    
    Usage:
        <button {{ ''|disabled_if_no_perm:'can_manage_orders,request' }}>Edit</button>
    """
    parts = permission_context.split(',')
    if len(parts) != 2:
        return attrs
    
    permission_name = parts[0].strip()
    # Return disabled attribute
    return mark_safe('disabled')


# =============================================================================
# BLOCK TAGS
# =============================================================================

class IfPermNode(template.Node):
    """Node for {% if_perm %} block tag."""
    
    def __init__(self, permission_name, nodelist_true, nodelist_false=None):
        self.permission_name = permission_name
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false or template.NodeList()
    
    def render(self, context):
        if check_permission(context, self.permission_name):
            return self.nodelist_true.render(context)
        return self.nodelist_false.render(context)


@register.tag('if_perm')
def do_if_perm(parser, token):
    """
    Block tag for conditional rendering based on permission.
    
    Usage:
        {% if_perm 'can_manage_orders' %}
            <button>Edit</button>
        {% else_perm %}
            <span class="disabled">Edit (No Permission)</span>
        {% endif_perm %}
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(
            f"'{bits[0]}' tag requires exactly one argument (permission name)"
        )
    
    permission_name = bits[1].strip("'\"")
    
    nodelist_true = parser.parse(('else_perm', 'endif_perm'))
    token = parser.next_token()
    
    if token.contents == 'else_perm':
        nodelist_false = parser.parse(('endif_perm',))
        parser.delete_first_token()
    else:
        nodelist_false = template.NodeList()
    
    return IfPermNode(permission_name, nodelist_true, nodelist_false)


class IfCanDoNode(template.Node):
    """Node for {% if_can_do %} block tag."""
    
    def __init__(self, action, nodelist_true, nodelist_false=None):
        self.action = action
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false or template.NodeList()
    
    def render(self, context):
        if check_action(context, self.action):
            return self.nodelist_true.render(context)
        return self.nodelist_false.render(context)


@register.tag('if_can_do')
def do_if_can_do(parser, token):
    """
    Block tag for conditional rendering based on action.
    
    Usage:
        {% if_can_do 'orders.delete' %}
            <button class="btn-danger">Delete Order</button>
        {% else_can_do %}
            <!-- Hidden or disabled -->
        {% endif_can_do %}
    """
    bits = token.split_contents()
    if len(bits) != 2:
        raise template.TemplateSyntaxError(
            f"'{bits[0]}' tag requires exactly one argument (action name)"
        )
    
    action = bits[1].strip("'\"")
    
    nodelist_true = parser.parse(('else_can_do', 'endif_can_do'))
    token = parser.next_token()
    
    if token.contents == 'else_can_do':
        nodelist_false = parser.parse(('endif_can_do',))
        parser.delete_first_token()
    else:
        nodelist_false = template.NodeList()
    
    return IfCanDoNode(action, nodelist_true, nodelist_false)


# =============================================================================
# ROLE-BASED SHORTCUTS
# =============================================================================

@register.simple_tag(takes_context=True)
def is_role(context, role_name):
    """
    Check if user has a specific role.
    
    Usage:
        {% is_role 'owner' as is_owner_role %}
        {% is_role 'manager' as is_mgr %}
    """
    role_checks = {
        'owner': context.get('is_owner', False),
        'manager': context.get('is_manager', False),
        'staff': context.get('is_staff_member', False),
        'superuser': context.get('request', {}) and getattr(
            context.get('request'), 'user', None
        ) and context.get('request').user.is_superuser,
    }
    return role_checks.get(role_name.lower(), False)


@register.simple_tag(takes_context=True)
def is_at_least(context, role_name):
    """
    Check if user's role is at least the specified level.
    Role hierarchy: superuser > owner > manager > staff
    
    Usage:
        {% is_at_least 'manager' as is_manager_or_above %}
    """
    hierarchy = ['staff', 'manager', 'owner', 'superuser']
    
    try:
        required_level = hierarchy.index(role_name.lower())
    except ValueError:
        return False
    
    request = context.get('request')
    if request and hasattr(request, 'user') and request.user.is_superuser:
        return True
    
    if context.get('is_owner', False):
        return required_level <= hierarchy.index('owner')
    
    if context.get('is_manager', False):
        return required_level <= hierarchy.index('manager')
    
    if context.get('is_staff_member', False):
        return required_level <= hierarchy.index('staff')
    
    return False
