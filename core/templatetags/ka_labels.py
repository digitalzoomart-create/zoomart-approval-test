from django import template

register = template.Library()

ROLE_LABELS_KA = {
    "Employee": "თანამშრომელი",
    "Manager": "დეპარტამენტის დირექტორი",
    "Finance": "ფინანსები",
    "Administrator": "ადმინისტრატორი",
    "Senior Management": "კომპანიის დირექტორი",
    "Procurement Manager": "შესყიდვების მენეჯერი",
}


@register.filter
def role_ka(value):
    """Translate an internal role/group name (stored in English so code
    logic never breaks) into the Georgian label shown to users."""
    return ROLE_LABELS_KA.get(value, value)
