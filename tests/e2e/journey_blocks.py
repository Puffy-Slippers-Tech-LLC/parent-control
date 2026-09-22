"""Registered checkpoint fragments for composing installed journey recipes.

These declare the existing worker protocols, not customer expectations or
phase transitions. Each call returns a fresh mapping owned by its caller.
"""

from private_artifacts import require


def fresh_desktop(account):
    """GDM07 → DESK01, including wrong-recipient refusal and both proofs."""
    require(account in ('parent', 'other-child'), 'journey:desktop-binding')
    if account == 'other-child':
        return {
            'installed-greeter': 'ui:gdm-other-list',
            'other-parent-focused': 'ui:gdm-other-focused',
            'wrong-recipient-refused': 'ui:gdm-standard-wrong-recipient-refused',
            'standard-list': 'ui:gdm-standard-list',
            'standard-focused': 'ui:gdm-standard-focused',
            'standard-recipient-qualified': 'ui:gdm-standard-recipient',
            'standard-recipient-rechecked': 'ui:gdm-standard-recipient-rechecked',
            'desktop': 'ui:standard-desktop',
        }
    return {
        'installed-greeter': 'ui:gdm-other-list',
        'other-parent-focused': 'ui:gdm-other-focused',
        'wrong-recipient-refused': 'ui:gdm-wrong-recipient-refused',
        'parent-list': 'ui:gdm-list',
        'parent-focused': 'ui:gdm-focused',
        'recipient-qualified': 'ui:gdm-parent-recipient',
        'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
        'desktop': 'ui:desktop',
    }


def parent_search():
    """SEARCH06: whole query, ending at the focused result before launch."""
    return {
        'search-ready': 'ui:parent-search-ready',
        'search-focused': 'ui:parent-search-focused',
        'search-entered': 'ui:parent-search-entered',
        'app-grid': 'ui:app-grid',
    }
