from django import template
from django.utils.translation import activate, get_language

register = template.Library()

@register.filter
def replace(value, arg):
    """
    Replace occurrences in a string.
    Usage: {{ value|replace:"old:new" }}
    """
    if not arg:
        return value
    
    try:
        old, new = arg.split(':', 1)
        return str(value).replace(old, new)
    except ValueError:
        return value

@register.filter
def intspace(value):
    """
    Format integer with space as thousand separator.
    Usage: {{ 1000000|intspace }} -> "1 000 000"
    """
    try:
        value = int(float(value))
        return "{:,}".format(value).replace(',', ' ')
    except (ValueError, TypeError):
        return value

@register.filter
def compact_number(value):
    """
    Shorten a number: 1 500 000 -> 1.5M, 12 500 -> 12.5K, else plain integer.
    Usage: {{ 1500000|compact_number }} -> "1.5M"
    """
    try:
        n = float(value)
    except (ValueError, TypeError):
        return value
    abs_n = abs(n)
    if abs_n >= 1_000_000:
        short = n / 1_000_000
        return f"{short:.2f}".rstrip('0').rstrip('.') + 'M'
    if abs_n >= 1_000:
        short = n / 1_000
        return f"{short:.1f}".rstrip('0').rstrip('.') + 'K'
    return str(int(n))

@register.filter
def get_category_features_in_language(subscription, language_code):
    """
    Get features organized by category with display names in a specific language.
    
    Usage: 
        {% with features=subscription|get_category_features_in_language:request.LANGUAGE_CODE %}
    
    Args:
        subscription: Subscription object
        language_code: Language code (e.g., 'en', 'ru', 'uz')
    
    Returns:
        dict: Features organized by category with translated names
    """
    if not subscription:
        return {}
    
    # Save current language
    current_language = get_language()
    
    try:
        # Activate the requested language
        activate(language_code)
        
        # Get features by category (this will use gettext with the activated language)
        features = subscription.get_features_by_category()
        
        return features
    finally:
        # Restore original language
        activate(current_language)
