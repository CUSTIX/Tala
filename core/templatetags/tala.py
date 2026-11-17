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


@register.simple_tag
def icon(name: str, extra: str = ""):
    """An icon from the static sprite. Decorative: screen readers skip it."""
    from django.templatetags.static import static
    from django.utils.html import format_html

    return format_html(
        '<svg class="i {}" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        extra,
        static("core/icons.svg"),
        name,
    )


@register.filter
def monogram(name: str) -> str:
    """ "Grade 7 - Sampaguita" -> "7S"; otherwise the first two initials."""
    import re

    number = re.search(r"\d+", name)
    words = re.findall(r"[A-Za-z]+", name)
    if number and words:
        return number.group() + words[-1][0].upper()
    return "".join(w[0] for w in words[:2]).upper() or "?"
