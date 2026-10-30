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


def daily_time_profile(*, source, entry, window, initial_enabled, minutes):
    """FLOW13 daily-only: explicit new Parent entry, zero grant, save, GDM.

    The caller compares the initial grant, saved settings and resulting balances
    before the worker receives a reply. No revocation or approval is implicit.
    """
    require(window == 'new' and type(initial_enabled) is bool
            and type(minutes) is int and minutes in (2, 4)
            and (source, entry) in (('gdm', 'fresh'), ('desktop', 'same-user')),
            'journey:daily-profile-binding')
    same = entry == 'same-user'
    return {
        **({'same-window-absent': 'ui:parent-new-window-absent',
            'same-desktop': 'ui:desktop',
            **prefixed_stages('same', parent_management())} if same else {
                **fresh_desktop('parent'), **parent_management()}),
        'profile-before': 'ui:time-explanation-reach-read',
        'profile-configured': f'ui:time-explanation-daily-{minutes}-'
                              + ('on' if initial_enabled else 'off') + '-read',
        'profile-settings': 'ui:parent-selected',
        'repeat-desktop': 'ui:desktop',
        'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
    }


def revocation_entry(*, child, approver, duration_seconds, allow_soft):
    """Real kiosk approval and retained Parent return for the fixed revoke slice.

    The caller owns response history, saved-policy assertions and balance reads.
    This declaration matches onpc_time_explanation::revoke_entry.
    """
    from kiosk_approved_flow import obtain_time
    return {
        **fresh_desktop('parent'), **parent_management(),
        'allowance-configured': 'ui:time-explanation-positive-read',
        'before-window': 'ui:retained-parent-leave',
        'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
        **obtain_time(initial='default', child=child, approver=approver,
                      duration_seconds=duration_seconds, allow_soft=allow_soft, exit='automatic'),
        **prefixed_stages('return', fresh_desktop('parent')),
        **prefixed_stages('supplied', retained_parent_entry(source='same-user')),
    }


def grant_only_time_profile(*, source, entry, window, initial_enabled, revoke_first,
                            duration_seconds, request_initial, balance_readback=True,
                            daily_minutes=0):
    """FLOW13: explicit zero-grant/revoke gate, daily allowance, approval, GDM.

    The caller owns balance comparisons and the retained-window identity.
    Later recipes own their duration and all post-preparation assertions. A caller
    observing the approved grant in the child can omit the extra Parent round trip.
    """
    from kiosk_approved_flow import obtain_time
    require(type(initial_enabled) is bool and type(revoke_first) is bool
            and type(balance_readback) is bool
            and type(daily_minutes) is int and daily_minutes in (0, 4)
            and type(duration_seconds) is int and duration_seconds in (120, 180, 240, 600, 1200)
            and request_initial in ('default', 'selected')
            and (source, entry, window) in (('gdm', 'fresh', 'new'),
                                          ('desktop', 'same-user', 'retained')),
            'time-profile:grant-binding')
    return {
        **({**fresh_desktop('parent'), **parent_management()} if window == 'new' else
           prefixed_stages('profile-entry', retained_parent_entry(source='same-user'))),
        'profile-before': 'ui:revoke-balances',
        **({'profile-revoke-open': 'ui:revoke-open',
            'profile-revoke-confirm': 'ui:revoke-confirm',
            'profile-cleared': 'ui:revoke-balances'} if revoke_first else {}),
        **({'profile-daily': 'ui:time-explanation-daily-4-'
                            + ('on' if initial_enabled else 'off') + '-read'} if daily_minutes else {
            'profile-zero': 'ui:time-explanation-zero-read' if initial_enabled else
                            'ui:time-explanation-setup-zero-read'}),
        'profile-window': 'ui:retained-parent-leave',
        'profile-switch': 'system:parent-switch-user', 'profile-gdm': 'ui:gdm-returned',
        **prefixed_stages('profile-request', obtain_time(initial=request_initial, child='fixture-child',
            approver='fixture-parent', duration_seconds=duration_seconds, allow_soft=True, exit='automatic')),
        **({
            **prefixed_stages('profile-return', fresh_desktop('parent')),
            **prefixed_stages('profile-result', retained_parent_entry(
                source='same-user', desktop_observation=False)),
            'profile-balance': 'ui:revoke-balances',
            'profile-final-switch': 'system:parent-switch-user',
            'profile-final-gdm': 'ui:gdm-returned',
        } if balance_readback else {}),
    }


def lock_challenge(prefix='', *, entry='curtain', account='parent'):
    """DESK06 declared curtain, fresh reveal guard and independent challenge."""
    import re
    require(type(prefix) is str and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', prefix),
            'journey:lock-prefix')
    require(entry in ('curtain', 'challenge'), 'journey:lock-entry')
    require(account in ('parent', 'child'), 'journey:lock-account')
    if entry == 'challenge':
        return {prefix + 'challenge': 'ui:' + account + '-lock-challenge'}
    return {prefix + stage: 'ui:' + account + '-lock-' + operation for stage, operation in (
        ('curtain', 'curtain'), ('reveal-ready', 'reveal-ready'), ('challenge', 'challenge'))}


def lock_recipient(prefix='', *, account='parent'):
    """DESK07: two independent empty masked focused lock-recipient reads."""
    import re
    require(type(prefix) is str and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', prefix),
            'journey:lock-prefix')
    require(account in ('parent', 'child'), 'journey:lock-account')
    return {prefix + 'lock-recipient-' + check: 'ui:' + account + '-lock-recipient-' + check
            for check in ('qualified', 'rechecked')}


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
    """PARENT06: one canonical API selection and independent saved-value readback."""
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
    require(links in ('license', 'browser-links', 'information', 'summary'), 'journey:overlay-about-links')
    selected = {'license': ('license',), 'browser-links': ('website', 'privacy'),
        'information': ('website', 'privacy', 'support', 'license', 'legal-notices'),
        'summary': ()}[links]
    reads = (('summary-read', 'overlay-about-summary'),) if links == 'summary' else tuple(
        (link + '-read', 'overlay-' + link + '-read') for link in selected)
    return {prefix + stage: 'ui:' + operation for stage, operation in (
        *((('help-read', 'overlay-help-read'),) if links == 'information' else ()),
        ('about-open', 'overlay-information-about' if links == 'information' else 'overlay-about-open'),
        *reads,
        ('about-close-ready', 'overlay-about-close-ready'),
        ('about-closed', 'overlay-about-closed'),
        ('form-returned', 'overlay-valid-fraction-soft-read'))}


def native_usable_app(route, *, child='other-child', role=None, desktop_observation=True):
    """FLOW08 finite native usable scope; caller owns stages and later activity."""
    require(route in ('command', 'grid'), 'journey:native-route')
    require(type(desktop_observation) is bool and (desktop_observation or route == 'command'),
            'journey:native-desktop-binding')
    require(child in ('parent', 'child', 'other-child') and
            (child != 'parent' or route == 'command'), 'journey:native-child-binding')
    require(role is None or role in ('A', 'S') and child == 'child' and route == 'command',
            'journey:native-role-binding')
    stages = {
        **({'desktop': 'ui:native-desktop'} if desktop_observation else {}),
        **({'command': 'ui:native-command-launch'} if route == 'command' else {
            'search-ready': 'ui:native-search-ready',
            'search-focused': 'ui:native-search-focused',
            'search-entered': 'ui:native-search-entered',
            'app-grid': 'ui:native-grid'}),
        'opened': 'ui:native-opened',
        'submit': 'ui:native-submit',
        'submitted': 'ui:native-submitted',
    }
    operation = {'child': 'overlay-native-', 'parent': 'parent-native-', 'other-child': 'native-'}[child]
    if role is not None:
        operation += {'A': 'allowed-', 'S': 'soft-'}[role]
    return {stage: tag.replace('ui:native-', 'ui:' + operation)
            for stage, tag in stages.items()}


def native_activity_entry(prefix, *, route='command', child='child', desktop_observation=True):
    """FLOW08 + APP04 capture; caller owns transition and comparison endpoints."""
    import re
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'journey:native-activity-prefix')
    return {**{f'{prefix}-{stage}': tag.replace('native-command-launch', 'native-activity-launch')
               for stage, tag in
               native_usable_app(route, child=child, desktop_observation=desktop_observation).items()},
            f'{prefix}-capture': 'ui:' + {'child': 'overlay-native-',
                'parent': 'parent-native-', 'other-child': 'native-'}[child] + 'activity'}


def native_activity_resume(prefix, *, child):
    """APP04 existing-window input/readback; callers compare their own captures."""
    require(child in ('parent', 'child', 'other-child'), 'journey:native-child-binding')
    operation = {'child': 'overlay-native-', 'parent': 'parent-native-', 'other-child': 'native-'}[child]
    return prefixed_stages(prefix, {stage: 'ui:' + operation + action for stage, action in (
        ('opened', 'activity'), ('submit', 'resubmit'), ('submitted', 'submitted'))})


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


def custom_child_selection(prefix, child):
    """Shared canonical UID selection and independent result checkpoints."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    operations = (('child-picker-opened', 'child-choice-highlighted', 'parent-selected')
                  if child == 'child' else ('existing-child-picker-opened',
                      'existing-child-choice-highlighted', 'existing-returned'))
    # Stable recorder stage names retain their bindings; they mean one API
    # setter, selected UID readback and policy readback, never popup or focus.
    return {f'{prefix}-{suffix}': 'ui:' + operation
            for suffix, operation in zip(('open', 'focus', 'selected'), operations)}


def custom_save_entry(prefix, child, *, qualification=True):
    """Rapid saving; qualifications additionally exercise refusals and reload."""
    require(child in ('child', 'existing'), 'journey:custom-child')
    require(type(qualification) is bool, 'journey:custom-qualification')
    other = 'existing' if child == 'child' else 'child'
    return {
        **allowance_selection(prefix + '-choice', ('custom',)),
        **({
            f'{prefix}-open': 'ui:custom-6-open',
            f'{prefix}-focus': 'ui:text-daily-6-focus',
            f'{prefix}-wrong-child': 'ui:named-custom-wrong-child-refused',
            f'{prefix}-wrong-surface': 'ui:parent-trace-wrong-surface-refused',
        } if qualification else {}),
        f'{prefix}-rapid': 'ui:parent-custom-save-trace',
        **({
            f'{prefix}-saved': 'ui:custom-6-saved',
            **custom_child_selection(prefix + '-away', other),
            **custom_child_selection(prefix + '-back', child),
            f'{prefix}-reopened': 'ui:custom-6-reopen',
        } if qualification else {}),
    }


def ordinary_custom_save(prefix, child, value, *, qualification=True):
    """Select a child and commit the qualified ordinary custom value."""
    require(value == 7, 'journey:ordinary-custom-value')
    require(type(qualification) is bool, 'journey:custom-qualification')
    return {
        **custom_child_selection(prefix, child),
        f'{prefix}-setup': 'ui:named-custom-setup',
        **allowance_selection(prefix + '-choice', ('custom',)),
        **({
            f'{prefix}-editor': f'ui:custom-{value}-open',
            f'{prefix}-wrong-child': 'ui:named-custom-wrong-child-refused',
        } if qualification else {}),
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
    require(type(product_free) is bool and (not product_free or expected == 'success'),
            'journey:desktop-product-binding')
    if account == 'child':
        return {
            'installed-greeter': 'ui:gdm-product-free-child-list' if product_free else 'ui:gdm-child-list',
            'child-focused': 'ui:gdm-product-free-child-focused' if product_free else 'ui:gdm-child-focused',
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


def desktop_entry(account, *, source, entry, expected='success', source_account=None):
    """FLOW15 explicit fresh/retained/same/lock entry and independent result."""
    require(account in ('parent', 'child', 'other-child'), 'journey:entry-account')
    require(expected in ('success', 'time-denied') and
            (expected == 'success' or account == 'child'), 'journey:entry-result')
    require((entry == 'fresh' and source == 'gdm')
            or (entry == 'retained' and source in ('gdm', 'desktop'))
            or (entry == 'same' and source == 'desktop' and expected == 'success')
            or (entry == 'lock' and source == 'locked' and account == 'child'),
            'journey:entry-binding')
    role = 'standard' if account == 'other-child' else account
    screens = {}
    if entry == 'retained' and source == 'desktop':
        require(source_account in ('parent', 'child', 'other-child') and source_account != account,
                'journey:entry-source-account')
        source_role = 'standard' if source_account == 'other-child' else source_account
        screens = {'source-desktop': fresh_desktop(source_account)['desktop'],
                   'source-switch': 'system:' + source_role + '-switch-user',
                   'source-greeter': 'ui:gdm-returned'}
    else:
        require(source_account is None, 'journey:entry-source-account')
    screens['entry-guard'] = 'system:' + role + '-entry-' + entry
    if entry in ('fresh', 'retained'):
        screens.update(fresh_desktop(account, expected))
    elif entry == 'same':
        screens['desktop'] = fresh_desktop(account)['desktop']
    else:
        if expected == 'success':
            screens.update(lock_challenge(account='child'))
            screens.update(lock_recipient(account='child'))
            screens['unlock-desktop'] = 'ui:fresh-child-desktop'
        else:
            screens.update({'curtain': 'ui:child-lock-curtain',
                            'reveal-ready': 'ui:child-lock-reveal-ready',
                            'time-denied': 'ui:child-lock-time-denied'})
    return screens


def retained_app_visit(prefix, *, account, source, source_account=None):
    """FLOW09: retained entry, immutable comparison, then original-window use.

    The caller binds the opened activity to its earlier capture in activity_checks
    and the first stage in activity_entries, before any entry input is released.
    """
    return {**prefixed_stages(prefix, desktop_entry(account, source=source, entry='retained',
                         source_account=source_account)),
            **native_activity_resume(prefix + '-activity', child=account)}


def retained_app_activities(users):
    """FLOW14: finite distinct users, explicit entry, capture, Switch User to GDM."""
    require(type(users) is tuple and bool(users) and all(type(user) is tuple and len(user) == 3
            for user in users), 'journey:activity-users')
    require(len({user[1] for user in users}) == len(users)
            and len({user[0] for user in users}) == len(users), 'journey:activity-distinct-users')
    screens = {}
    for prefix, account, entry in users:
        require(entry in ('fresh', 'retained'), 'journey:activity-entry')
        screens.update(prefixed_stages(prefix, desktop_entry(account, source='gdm', entry=entry)))
        screens.update(native_activity_entry(prefix + '-activity', child=account))
        role = 'standard' if account == 'other-child' else account
        screens.update(prefixed_stages(prefix, {'desktop-identity': 'system:' + role + '-entry-same',
            'switch-ready': fresh_desktop(account)['desktop'],
            'switch': 'system:' + role + '-switch-user', 'greeter': 'ui:gdm-returned'}))
    return screens


def retained_parent_entry(*, source='desktop', desktop_observation=True):
    """FLOW01 retained window read without launch or child reselection."""
    require(source in ('desktop', 'child-desktop', 'same-user'), 'retained-parent:source')
    require(type(desktop_observation) is bool and (desktop_observation or source == 'same-user'),
            'retained-parent:desktop-binding')
    return {
        **({'source-desktop': 'ui:fresh-child-desktop' if source == 'child-desktop' else 'ui:standard-desktop',
            'source-switch': 'system:child-switch-user' if source == 'child-desktop' else 'system:standard-switch-user',
            'source-greeter': 'ui:gdm-returned',
            **fresh_desktop('parent')} if source != 'same-user' else
           {'desktop': 'ui:desktop'} if desktop_observation else {}),
        'parent-retained': 'ui:retained-parent-read',
    }


def rejected_gdm_return():
    """DESK11: reobserve the rejected child prompt before Escape and list readback."""
    return {'denied-return-ready': 'ui:gdm-child-denied-return-ready',
            'denied-return-state': 'ui:gdm-child-denied-return-state',
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
                               'overlay-language-form-de', 'language-history-overlay-he-casey',
                               'overlay-long-approver-select'),
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


def restart_reentry(surface):
    """LIFE07 Close, ordinary exit and reopening on the installation boot."""
    require(surface in ('parent', 'overlay', 'kiosk'), 'journey:restart-surface')
    if surface == 'kiosk':
        return {
            'kiosk-close': 'ui:restart-kiosk-close',
            'kiosk-closed': 'ui:restart-kiosk-closed',
            'kiosk-exit': 'ui:restart-kiosk-exit',
            'kiosk-returned': 'ui:gdm-station-returned',
            **station_entry('renewed-'),
            'kiosk-reentry': 'ui:restart-kiosk-read',
        }
    return {
        surface + '-close': 'ui:restart-' + surface + '-close',
        surface + '-closed': 'ui:restart-' + surface + '-closed',
        **({'overlay-exit': 'ui:restart-overlay-exit',
            'overlay-desktop': 'ui:overlay-desktop'} if surface == 'overlay' else {}),
        surface + '-relaunch': 'ui:' + ('parent' if surface == 'parent' else 'child') + '-command-launch',
        surface + '-reentry': 'ui:restart-' + surface + '-read',
    }


def restart_kiosk_usability(prefix=None):
    """Select the declared approver, then independently require usable requests."""
    screens = {
        'usable-kiosk-approver': 'ui:kiosk-language-jordan-jamie',
        'usable-kiosk': 'ui:restart-kiosk-usable',
    }
    return prefixed_stages(prefix, screens) if prefix is not None else screens


def restart_request_usability(prefix, station_prefix):
    """Fresh Child App and station reads after the caller's Parent logout."""
    return {
        **prefixed_stages(prefix + '-child', fresh_desktop('child')),
        prefix + '-overlay-launch': 'ui:child-command-launch',
        prefix + '-usable-overlay': 'ui:restart-overlay-usable',
        prefix + '-child-logout': 'system:child-logout',
        **station_entry(station_prefix), **restart_kiosk_usability(prefix),
        prefix + '-kiosk-exit': 'ui:kiosk-request-cancel',
        prefix + '-kiosk-returned': 'ui:gdm-station-returned',
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
