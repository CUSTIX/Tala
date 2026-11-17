from decimal import Decimal

from django import template

from core.numbers import plain

register = template.Library()


@register.filter
def get(mapping, key):
    """{{ dict|get:key }}: look up a key that is a variable."""
    return mapping.get(key) if mapping else None


@register.filter
def num(value):
    """A Decimal without trailing zeros: 20.00 -> 20, 12.50 -> 12.5."""
    if value is None or value == "":
        return ""
    if not isinstance(value, Decimal):
        return value  # e.g. text typed into a form that is shown again
    return plain(value)


@register.filter
def split_words(value):
    return str(value).split()
