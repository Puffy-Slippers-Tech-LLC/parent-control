"""Registered checkpoint fragments for composing installed journey recipes.

These declare the existing worker protocols, not customer expectations or
phase transitions. Each call returns a fresh mapping owned by its caller.
"""

from private_artifacts import require


def native_usable_app(route):
    """FLOW08 finite native usable scope; caller owns stages and later activity."""
    require(route in ('command', 'grid'), 'journey:native-route')
    return {
        'desktop': 'ui:native-desktop',
        **({'command': 'ui:native-command-launch'} if route == 'command' else {
            'search-ready': 'ui:native-search-ready',
            'search-focused': 'ui:native-search-focused',
            'search-entered': 'ui:native-search-entered',
            'app-grid': 'ui:native-grid'}),
        'opened': 'ui:native-opened',
        'submit': 'ui:native-submit',
        'submitted': 'ui:native-submitted',
    }


def filter_screens(kind, mask, prefix):
    """PARENT11 finite option/closure stages with caller-owned invocation IDs."""
    import re
    from accessible_ui import FILTER_OPTIONS
    require(kind in FILTER_OPTIONS and type(mask) is int
            and 0 <= mask < (1 << len(FILTER_OPTIONS[kind]))
            and type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'journey:filter-binding')
    return {f'{prefix}-{action}': f'ui:filter-{kind}-{mask}-{action}'
            for action in ('open', *FILTER_OPTIONS[kind], 'read', 'closed')}


def custom_child_selection(prefix, child):
    """Three public selector checkpoints, reusable with distinct stage IDs."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    operations = (('child-picker-opened', 'child-choice-highlighted', 'parent-selected')
                  if child == 'child' else ('existing-child-picker-opened',
                      'existing-child-choice-highlighted', 'existing-returned'))
    return {f'{prefix}-{suffix}': 'ui:' + operation
            for suffix, operation in zip(('open', 'focus', 'selected'), operations)}


def custom_save_entry(prefix, child):
    """Enabled rapid-save entry, then independent reselection and editor read."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    other = 'existing' if child == 'child' else 'child'
    return {
        f'{prefix}-open': 'ui:custom-6-open',
        f'{prefix}-focus': 'ui:text-daily-6-focus',
        f'{prefix}-wrong-child': 'ui:named-custom-wrong-child-refused',
        f'{prefix}-wrong-surface': 'ui:parent-trace-wrong-surface-refused',
        f'{prefix}-rapid': 'ui:parent-custom-save-trace',
        f'{prefix}-saved': 'ui:custom-6-saved',
        **custom_child_selection(prefix + '-away', other),
        **custom_child_selection(prefix + '-back', child),
        f'{prefix}-reopened': 'ui:custom-6-reopen',
    }


def ordinary_custom_save(prefix, child, value):
    """Select a child and commit the qualified ordinary custom value."""
    require(value == 7, 'journey:ordinary-custom-value')
    return {
        **custom_child_selection(prefix, child),
        f'{prefix}-setup': 'ui:named-custom-setup',
        f'{prefix}-editor': f'ui:custom-{value}-open',
        f'{prefix}-wrong-child': 'ui:named-custom-wrong-child-refused',
        **{f'{prefix}-text-{suffix}': f'ui:text-daily-{value}-{suffix}'
           for suffix in ('focus', 'selected', 'read')},
        f'{prefix}-saved': f'ui:custom-{value}-saved',
    }


def observed_text(entry, binding):
    """UI22 declaration: UI25, one explicitly bound UI16 input, UI26."""
    import re
    require(type(entry) is str and re.fullmatch(r'[a-z][a-z0-9-]*', entry)
            and binding in ('body-first', 'body-clear'), 'journey:trace-binding')
    return {
        f'trace-{entry}-start': 'ui:feedback-trace-start',
        **{f'{entry}-{suffix}': f'ui:text-{binding}-{suffix}'
           for suffix in ('focus', 'selected', 'read')},
        f'trace-{entry}-finish': 'ui:feedback-trace-finish',
    }


def fresh_desktop(account, expected='success'):
    """Direct fixture entry, with fresh recipient proofs before secret input.

    Deliberate wrong-account visits belong to the separate harness qualification.
    """
    require(account in ('parent', 'other-child', 'child'), 'journey:desktop-binding')
    require(expected in ('success', 'time-denied') and
            (expected == 'success' or account == 'child'), 'journey:desktop-result')
    if account == 'child':
        return {
            'installed-greeter': 'ui:gdm-child-list',
            'child-focused': 'ui:gdm-child-focused',
            'child-recipient-qualified': 'ui:gdm-child-recipient',
            'child-recipient-rechecked': 'ui:gdm-child-recipient-rechecked',
            ('desktop' if expected == 'success' else 'denied'):
                ('ui:fresh-child-desktop' if expected == 'success' else 'ui:gdm-child-time-denied'),
        }
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


def rejected_gdm_return():
    """DESK11: reobserve the rejected child prompt before Escape and list readback."""
    return {'denied-return-ready': 'ui:gdm-child-denied-return-ready',
            'denied-returned': 'ui:gdm-child-denied-returned'}


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


def overlay_entry(prefix, route):
    """REQUEST02/13 input followed by REQUEST03's independent fixed-child read."""
    import re
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix)
            and route in ('command', 'panel'), 'journey:overlay-binding')
    return {
        **({prefix + '-panel': 'ui:overlay-panel-ready'} if route == 'panel' else {}),
        prefix + '-launch': 'ui:child-command-launch' if route == 'command' else 'ui:overlay-panel-launch',
        prefix + '-form': 'ui:overlay-request-form',
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
