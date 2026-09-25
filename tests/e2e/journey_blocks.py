"""Registered checkpoint fragments for composing installed journey recipes.

These declare the existing worker protocols, not customer expectations or
phase transitions. Each call returns a fresh mapping owned by its caller.
"""

from private_artifacts import require


def fresh_desktop(account):
    """Direct fixture entry, with fresh recipient proofs before secret input.

    Deliberate wrong-account visits belong to the separate harness qualification.
    """
    require(account in ('parent', 'other-child'), 'journey:desktop-binding')
    if account == 'other-child':
        return {
            'installed-greeter': 'ui:gdm-standard-list',
            'standard-focused': 'ui:gdm-standard-focused',
            'standard-recipient-qualified': 'ui:gdm-standard-recipient',
            'standard-recipient-rechecked': 'ui:gdm-standard-recipient-rechecked',
            'desktop': 'ui:standard-desktop',
        }
    return {
        'installed-greeter': 'ui:gdm-list',
        'parent-focused': 'ui:gdm-focused',
        'recipient-qualified': 'ui:gdm-parent-recipient',
        'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
        'desktop': 'ui:desktop',
    }


def station_entry(prefix=''):
    """Minimal passwordless station entry, without unrelated account visits."""
    require(prefix in ('', 'cancel-', 'escape-'), 'journey:station-binding')
    return {
        prefix + 'station-list': 'ui:gdm-station-list',
        prefix + 'station-focused': 'ui:gdm-station-focused',
        prefix + 'station-branch': 'ui:station-default-entry',
    }


def parent_management():
    """PARENT01/02: direct command, owned window and fixture-child selection."""
    return {
        'parent-command': 'ui:parent-command-launch',
        'parent-window': 'ui:parent-window',
        'child-picker-opened': 'ui:child-picker-opened',
        'child-choice-highlighted': 'ui:child-choice-highlighted',
        'parent-selected': 'ui:parent-selected',
    }


def product_free_desktop():
    """Fresh administrator login and command context before installing the app."""
    stages = fresh_desktop('parent')
    stages.update({
        'installed-greeter': 'ui:gdm-product-free-list',
        'parent-focused': 'ui:gdm-product-free-focused',
        'desktop': 'ui:fresh-parent-desktop',
        'command-context': 'system:parent-command-context',
    })
    return stages


def reboot_desktop():
    """Fresh administrator observations for the declared post-reboot challenge."""
    return {'reboot-' + stage: tag for stage, tag in fresh_desktop('parent').items()}


def parent_search():
    """SEARCH06: whole query, ending at the focused result before launch."""
    return {
        'search-ready': 'ui:parent-search-ready',
        'search-focused': 'ui:parent-search-focused',
        'search-entered': 'ui:parent-search-entered',
        'app-grid': 'ui:app-grid',
    }
