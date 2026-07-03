from django import template
from billing.models import Feature

register = template.Library()


@register.simple_tag(takes_context=True)
def has_feature(context, feature_code):
    """
    Check if the current user's organization has a specific feature in their tariff.
    
    Usage in templates:
        {% has_feature 'ADVANCED_ANALYTICS' as can_analytics %}
        {% if can_analytics %}
            <!-- Show analytics menu -->
        {% endif %}
    
    Or directly in if statement:
        {% if request.user.admin_profile.center.subscription.tariff|has_feature:'ADVANCED_ANALYTICS' %}
            <!-- Show content -->
        {% endif %}
    """
    request = context.get('request')
    
    if not request or not request.user.is_authenticated:
        return False
    
    # Superusers have access to everything
    if request.user.is_superuser:
        return True
    
    # Check if user has an admin_profile and center
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
        return False
    
    center = request.user.admin_profile.center
    
    # Check if center has active subscription
    if not center or not hasattr(center, 'subscription'):
        return False
    
    subscription = center.subscription
    
    # Check if subscription is active
    if not subscription.is_active():
        return False
    
    # Check if tariff has the feature
    return subscription.tariff.has_feature(feature_code)


@register.filter
def has_feature_filter(tariff, feature_code):
    """
    Filter version to check if a tariff has a feature.
    
    Usage:
        {% if subscription.tariff|has_feature_filter:'ADVANCED_ANALYTICS' %}
            <!-- Show content -->
        {% endif %}
    """
    if not tariff:
        return False
    return tariff.has_feature(feature_code)


@register.simple_tag(takes_context=True)
def user_has_active_subscription(context):
    """
    Check if current user's organization has an active subscription.
    
    Usage:
        {% user_has_active_subscription as has_subscription %}
        {% if has_subscription %}
            <!-- Show content -->
        {% endif %}
    """
    request = context.get('request')
    
    if not request or not request.user.is_authenticated:
        return False
    
    if request.user.is_superuser:
        return True
    
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
        return False
    
    center = request.user.admin_profile.center
    
    if not center or not hasattr(center, 'subscription'):
        return False
    
    return center.subscription.is_active()


@register.simple_tag(takes_context=True)
def get_user_tariff(context):
    """
    Get the current user's tariff.
    
    Usage:
        {% get_user_tariff as tariff %}
        <p>Your plan: {{ tariff.title }}</p>
    """
    request = context.get('request')
    
    if not request or not request.user.is_authenticated:
        return None
    
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
        return None
    
    center = request.user.admin_profile.center
    
    if not center or not hasattr(center, 'subscription'):
        return None
    
    return center.subscription.tariff


@register.simple_tag(takes_context=True)
def check_resource_limit(context, resource_type):
    """
    Check if user can add more resources (branches, staff, orders).
    
    Usage:
        {% check_resource_limit 'branches' as can_add_branch %}
        {% if can_add_branch %}
            <a href="{% url 'branch_create' %}">Add Branch</a>
        {% else %}
            <span class="text-muted">Branch limit reached</span>
        {% endif %}
    """
    request = context.get('request')
    
    if not request or not request.user.is_authenticated:
        return False
    
    if request.user.is_superuser:
        return True
    
    if not hasattr(request.user, 'admin_profile') or not request.user.admin_profile:
        return False
    
    center = request.user.admin_profile.center
    
    if not center or not hasattr(center, 'subscription'):
        return False
    
    subscription = center.subscription
    
    if resource_type == 'branches':
        return subscription.can_add_branch()
    elif resource_type == 'staff':
        return subscription.can_add_staff()
    elif resource_type == 'orders':
        return subscription.can_create_order()
    
    return False
