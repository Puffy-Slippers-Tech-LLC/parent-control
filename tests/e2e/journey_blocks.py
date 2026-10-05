"""Registered checkpoint fragments for composing installed journey recipes.

These declare the existing worker protocols, not customer expectations or
phase transitions. Each call returns a fresh mapping owned by its caller.
"""

from private_artifacts import require


def prefixed_stages(prefix, screens):
    """Name an independent invocation without changing its public operations."""
    import re
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'journey:stage-prefix')
    return {prefix + '-' + stage: tag for stage, tag in screens.items()}


def custom_allowance(prefix, minutes):
    """Ordinary editor input and saved readback; selection belongs to the caller."""
    from accessible_ui import CUSTOM_ALLOWANCE_OPERATIONS, TEXT_VALUES
    require(type(minutes) is int and 'daily-' + str(minutes) in TEXT_VALUES
            and 'custom-' + str(minutes) + '-saved' in CUSTOM_ALLOWANCE_OPERATIONS,
            'journey:custom-allowance')
    return prefixed_stages(prefix, {
        'open': f'ui:custom-{minutes}-open',
        **{f'text-{action}': f'ui:text-daily-{minutes}-{action}'
           for action in ('focus', 'selected', 'read')},
        'saved': f'ui:custom-{minutes}-saved',
    })


def allowance_selection(prefix, values):
    """PARENT06: one native click, typed choice, Enter and saved-value readback."""
    from accessible_ui import PRESETS
    require(type(values) is tuple and len(values) == 1
            and all(value == 'custom' or type(value) is int and value in PRESETS for value in values),
            'journey:allowance-keyboard')
    value = values[0]
    return prefixed_stages(prefix, {
        'ready': f'ui:allowance-keyboard-{value}-click',
        'confirm': f'ui:allowance-keyboard-{value}-selected',
    })


def language_selection(prefix, language, *, surface, child='existing'):
    """LANG01 chooser fragment; caller owns candidate and response expectations."""
    import re
    require(language in ('en', 'de', 'zh-Hans', 'he') and surface in ('parent', 'kiosk', 'overlay')
            and type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'language:choice-binding')
    require(child in ('existing', 'child') and (surface == 'kiosk' or child == 'existing'),
            'language:child-binding')
    owner = 'kiosk-riley' if surface == 'kiosk' and child == 'child' else surface
    return {prefix + '-open': 'ui:' + owner + '-language-open',
            prefix + '-choose': 'ui:' + owner + '-language-choose-' + language.lower()}


def overlay_license_read(prefix='', *, links='license'):
    """Owned About read/close fragment; callers declare preserved form endpoints."""
    import re
    require(type(prefix) is str and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', prefix),
            'journey:overlay-about-binding')
    require(links in ('license', 'browser-links', 'information'), 'journey:overlay-about-links')
    selected = {'license': ('license',), 'browser-links': ('website', 'privacy'),
        'information': ('website', 'privacy', 'support', 'license', 'legal-notices')}[links]
    reads = tuple((link + '-read', 'overlay-' + link + '-read') for link in selected)
    return {prefix + stage: 'ui:' + operation for stage, operation in (
        *((('help-read', 'overlay-help-read'),) if links == 'information' else ()),
        ('about-open', 'overlay-information-about' if links == 'information' else 'overlay-about-open'),
        *reads,
        ('about-close-ready', 'overlay-about-close-ready'),
        ('about-closed', 'overlay-about-closed'),
        ('form-returned', 'overlay-valid-fraction-soft-read'))}


def native_usable_app(route, *, child='other-child'):
    """FLOW08 finite native usable scope; caller owns stages and later activity."""
    require(route in ('command', 'grid'), 'journey:native-route')
    require(child in ('child', 'other-child') and (child != 'child' or route == 'command'),
            'journey:native-child-binding')
    stages = {
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
    return {stage: tag.replace('ui:native-', 'ui:overlay-native-') if child == 'child' else tag
            for stage, tag in stages.items()}


def native_activity_entry(prefix, *, route='command', child='child'):
    """FLOW08 + APP04 capture; caller owns transition and comparison endpoints."""
    import re
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'journey:native-activity-prefix')
    return {**{f'{prefix}-{stage}': tag for stage, tag in
               native_usable_app(route, child=child).items()},
            f'{prefix}-capture': 'ui:overlay-native-activity' if child == 'child'
            else 'ui:native-activity'}


def filter_screens(kind, mask, prefix):
    """PARENT11 finite input stages; callers check the resulting catalogue."""
    import re
    from accessible_ui import FILTER_OPTIONS
    require(kind in FILTER_OPTIONS and type(mask) is int
            and 0 <= mask < (1 << len(FILTER_OPTIONS[kind]))
            and type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'journey:filter-binding')
    return {f'{prefix}-{action}': f'ui:filter-{kind}-{mask}-{action}'
            for action in ('open', *FILTER_OPTIONS[kind])}


def custom_child_selection(prefix, child, *, route='action'):
    """Public selector checkpoints; choose the input route before execution."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    require(route in ('action', 'keyboard'), 'journey:child-picker-route')
    operations = (('child-picker-opened', 'child-choice-highlighted', 'parent-selected')
                  if child == 'child' else ('existing-child-picker-opened',
                      'existing-child-choice-highlighted', 'existing-returned'))
    if route == 'keyboard':
        operations = (operations[0].replace('-opened', '-presented'), *operations[1:])
    return {**({f'{prefix}-ready': 'ui:parent-child-picker-ready'} if route == 'keyboard' else {}),
            **{f'{prefix}-{suffix}': 'ui:' + operation
               for suffix, operation in zip(('open', 'focus', 'selected'), operations)}}


def custom_save_entry(prefix, child):
    """Enabled rapid-save entry, then independent reselection and editor read."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    other = 'existing' if child == 'child' else 'child'
    return {
        **allowance_selection(prefix + '-choice', ('custom',)),
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
        **allowance_selection(prefix + '-choice', ('custom',)),
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


def fresh_desktop(account, expected='success', *, product_free=False):
    """Direct fixture entry, with fresh recipient proofs before secret input.

    Deliberate wrong-account visits belong to the separate harness qualification.
    """
    require(account in ('parent', 'other-child', 'child'), 'journey:desktop-binding')
    require(expected in ('success', 'time-denied') and
            (expected == 'success' or account == 'child'), 'journey:desktop-result')
    require(type(product_free) is bool and
            (not product_free or account in ('parent', 'other-child')),
            'journey:desktop-product-binding')
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
            'installed-greeter': ('ui:gdm-product-free-standard-list' if product_free
                                  else 'ui:gdm-standard-list'),
            'standard-focused': ('ui:gdm-product-free-standard-focused' if product_free
                                 else 'ui:gdm-standard-focused'),
            'standard-recipient-qualified': 'ui:gdm-standard-recipient',
            'standard-recipient-rechecked': 'ui:gdm-standard-recipient-rechecked',
            'desktop': 'ui:standard-desktop',
        }
    return {
        'installed-greeter': 'ui:gdm-product-free-list' if product_free else 'ui:gdm-list',
        'parent-focused': 'ui:gdm-product-free-focused' if product_free else 'ui:gdm-focused',
        'recipient-qualified': 'ui:gdm-parent-recipient',
        'recipient-rechecked': 'ui:gdm-parent-recipient-rechecked',
        'desktop': 'ui:fresh-parent-desktop' if product_free else 'ui:desktop',
    }


def rejected_gdm_return():
    """DESK11: reobserve the rejected child prompt before Escape and list readback."""
    return {'denied-return-ready': 'ui:gdm-child-denied-return-ready',
            'denied-returned': 'ui:gdm-child-denied-returned'}


def station_entry(prefix=''):
    """Minimal passwordless station entry, without unrelated account visits."""
    require(prefix in ('', 'cancel-', 'escape-', 'initial-', 'renewed-'), 'journey:station-binding')
    return {
        prefix + 'station-list': 'ui:gdm-station-list',
        prefix + 'station-focused': 'ui:gdm-station-focused',
        prefix + 'station-branch': 'ui:' + ('station-initial-entry' if prefix in ('initial-', 'renewed-')
                                          else 'station-default-entry'),
    }


def parent_reopen():
    """LIFE01: normal closure, same-desktop launch and untouched selection read.

    Child reselection and persistence assertions belong to the caller.
    Matches onpc_lifecycle::reopen without adding selection repair.
    """
    return {
        'prior-window': 'ui:parent-window',
        'close-ready': 'ui:parent-restart-ready',
        'closed': 'ui:parent-search-closed',
        'same-desktop': 'ui:desktop',
        'same-parent-command': 'ui:parent-command-launch',
        'same-parent-window': 'ui:parent-window',
        'initial-selection': 'ui:parent-initial-selection',
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


def overlay_entry(prefix, route, *, form_operation='overlay-request-form'):
    """REQUEST02/13 input followed by REQUEST03's independent fixed-child read."""
    import re
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix)
            and route in ('command', 'panel', 'panel-reopen'), 'journey:overlay-binding')
    require(form_operation in ('overlay-request-form', 'overlay-valid-excluded-read',
                               'overlay-valid-fraction-soft-read', 'overlay-language-initial',
                               'overlay-language-form-de', 'language-history-overlay-he-casey'),
            'journey:overlay-form-binding')
    return {
        **({prefix + '-reveal': 'ui:overlay-panel-reveal-ready'} if route == 'panel-reopen' else {}),
        **({prefix + '-panel': 'ui:overlay-panel-ready'} if route != 'command' else {}),
        prefix + '-launch': 'ui:child-command-launch' if route == 'command' else 'ui:overlay-panel-launch',
        **({prefix + '-overview': 'ui:overlay-panel-overview'} if route == 'panel-reopen' else {}),
        prefix + '-form': 'ui:' + form_operation,
    }


def product_free_desktop():
    """Fresh administrator login and command context before installing the app."""
    stages = fresh_desktop('parent', product_free=True)
    stages.update({
        'command-context': 'system:parent-command-context',
    })
    return stages


def package_installation():
    """LIFE04 declaration: fresh admin entry, one input and separate readback.

    The caller owns phase/assertion boundaries, package selection and any
    qualification-only wrong-entry checks. No reboot is implicit.
    """
    return {
        **product_free_desktop(),
        'package-submitted': 'system:parent-command-context',
        'package-result': 'system:parent-command-context',
    }


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
