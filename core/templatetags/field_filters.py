from django import template

register = template.Library()

@register.filter
def replace_underscore(value):
    """Replace underscores with spaces in field names"""
    if value:
        return str(value).replace('_', ' ')
    return value

@register.filter
def format_field_name(value):
    """Format field names for display (replace underscores and title case)"""
    if value:
        return str(value).replace('_', ' ').title()
    return value

@register.filter
def safe_length(value):
    """Safely get length of a value, returns 0 if None or not iterable"""
    try:
        return len(value)
    except (TypeError, AttributeError):
        return 0 

@register.filter
def dict_get(mapping, key):
    """Safely get a dictionary value by key in templates."""
    try:
        if mapping is None:
            return None
        return mapping.get(key)
    except AttributeError:
        return None 