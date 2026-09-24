"""Bounded public AT-SPI interaction in the installed fixture's desktop.

This file also runs as a standalone program in the guarded guest. It reads only
public UI objects; it never imports product code or reads product storage/buses.
Only fixed operation names and sanitized results cross the controller boundary.
"""

from contextlib import contextmanager
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time
import warnings


OPERATIONS = frozenset({
    'gdm-no-child-refused',
    'gdm-list', 'gdm-focused', 'gdm-select-parent', 'gdm-navigation-returned',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-dismissed', 'gdm-returned',
    'desktop', 'app-grid', 'parent-window', 'parent-empty', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'about-rechecked', 'license-unrelated-launched', 'license-unrelated-ready',
    'license-unrelated-closed', 'license-empty-launched', 'license-empty-ready',
    'license-empty-closed', 'license', 'license-ambiguous-launched',
    'license-ambiguous-ready', 'license-ambiguous-closed',
    'license-provider-refusals', 'license-closed', 'about-returned', 'parent-returned',
    'discovery-ready', 'new-child-picker-opened', 'new-child-choice-highlighted',
    'new-child-selected', 'existing-child-picker-opened', 'existing-child-choice-highlighted',
    'existing-returned', 'existing-apps', 'new-child-apps', 'new-child-screen',
    'discovery-child-picker-opened', 'discovery-child-choice-highlighted', 'discovery-selected',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'fresh-parent-desktop', 'fresh-standard-desktop',
    'keyring-cancel-standard',
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused',
    'gdm-station-returned', 'kiosk-request-form', 'kiosk-request-cancel',
    'kiosk-request-escape-ready', 'station-entry-branch', 'station-default-entry',
})
STANDARD_OPERATIONS = frozenset({
    'standard-desktop', 'fresh-standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
    'keyring-cancel-standard',
})
OPERATIONS |= frozenset({
    'parent-command-launch', 'standard-parent-command-launch', 'standard-parent-closed',
    'child-command-launch',
})
OPERATIONS |= frozenset({'parent-search-ready', 'parent-search-focused', 'parent-search-entered'})
OPERATIONS |= frozenset({'parent-search-close-ready', 'parent-search-closed'})
OPERATIONS |= frozenset({'shell-search-started', 'shell-search-wrong-result-refused',
                         'shell-search-cleared',
                         'shell-search-dismissed'})
OPERATIONS |= frozenset({'standard-management-denied'})
STANDARD_OPERATIONS |= frozenset({'standard-management-denied'})
STANDARD_OPERATIONS |= frozenset({'standard-parent-command-launch', 'standard-parent-closed'})
STANDARD_OPERATIONS |= frozenset({'child-command-launch'})
OPERATIONS |= frozenset({'standard-search-qualified'})
STANDARD_OPERATIONS |= frozenset({'standard-search-qualified'})
OPERATIONS |= frozenset({'help-desktop-clear'})
PRODUCT = 'Oh No! Parent Control'
LICENSE_LINK = 'GNU General Public License v3.0'
ABOUT_FOOTER = '© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.'
CHILD = 'Riley (Child)'
EXISTING_CHILD = 'Jordan (Child)'
NEW_CHILD = 'Morgan (Child)'
CHILD_IDENTITIES = {CHILD: 'fixture-child', EXISTING_CHILD: 'existing-fixture-child',
                    NEW_CHILD: 'new-fixture-child'}
CHILD_ACCOUNTS = {CHILD: 'onpc-child-riley', EXISTING_CHILD: 'onpc-child-jordan',
                  NEW_CHILD: 'onpc-e2e-new-child'}
PICKER_OPERATIONS = {
    'child-picker-opened': CHILD, 'new-child-picker-opened': NEW_CHILD,
    'existing-child-picker-opened': EXISTING_CHILD, 'discovery-child-picker-opened': EXISTING_CHILD,
}
HIGHLIGHT_OPERATIONS = {
    'child-choice-highlighted': CHILD, 'new-child-choice-highlighted': NEW_CHILD,
    'existing-child-choice-highlighted': EXISTING_CHILD,
    'discovery-child-choice-highlighted': EXISTING_CHILD,
}
SETTINGS_OPERATIONS = {
    'parent-selected': CHILD, 'parent-returned': CHILD, 'discovery-ready': EXISTING_CHILD,
    'parent-toggle-disabled-settings': CHILD,
    'discovery-selected': EXISTING_CHILD,
    'new-child-selected': NEW_CHILD, 'new-child-screen': NEW_CHILD, 'existing-returned': EXISTING_CHILD,
}
OPERATIONS |= frozenset(SETTINGS_OPERATIONS)
TOGGLE_OPERATIONS = {
    'parent-toggle-enabled': {'state': True, 'activated': True},
    'parent-toggle-disabled': {'state': False, 'activated': True},
    'parent-toggle-current': {'state': False, 'activated': False},
    'parent-toggle-wrong-refused': {'refusal': 'wrong-control'},
    'parent-toggle-hidden-refused': {'refusal': 'hidden-control', 'state': False},
}
OPERATIONS |= frozenset(TOGGLE_OPERATIONS)
PARENT_SAVE_OPERATIONS = {
    'parent-save-wrong-child-refused': {'refusal': 'wrong-child'},
    'parent-save-enabled': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': True,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': True,
    },
    'parent-save-reopened': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': True,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': True,
    },
    'parent-save-disabled': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': False,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': False,
    },
}
OPERATIONS |= frozenset(PARENT_SAVE_OPERATIONS)
PARENT = 'Jamie (Parent)'
OTHER_PARENT = 'Casey (Parent)'
KIOSK = 'Oh No! Parent Control'
KIOSK_USERNAME = 'oh-no-parent-control'
GREETER_IDENTITIES = {PARENT: 'parent', OTHER_PARENT: 'other-parent',
                      CHILD: 'child', EXISTING_CHILD: 'other-child',
                      KIOSK: 'station', KIOSK_USERNAME: 'station'}
GDM_PROVIDER_CONTROLS = (
    'account-list',
    *(f'account-choice::{identity}' for identity in dict.fromkeys(GREETER_IDENTITIES.values())),
    'selected-recipient', 'password', 'submit', 'cancel', 'session-chooser',
    'session-choice::<provider-session-id>',
)
GREETER_OPERATIONS = frozenset({'gdm-list', 'gdm-focused', 'gdm-select-parent',
    'gdm-no-child-refused',
    'gdm-navigation-returned', 'gdm-dismissed', 'gdm-returned',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused',
    'gdm-station-returned'})
GREETER_NAVIGATION = frozenset({'gdm-list', 'gdm-other-list', 'gdm-standard-list',
                                'gdm-station-list', 'gdm-product-free-list'})
GDM_NONSECRET_OPERATIONS = frozenset({
    'gdm-list', 'gdm-focused', 'gdm-other-list', 'gdm-other-focused',
    'gdm-standard-list', 'gdm-standard-focused',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-station-wrong-entry-refused',
    'gdm-station-list', 'gdm-station-focused', 'gdm-station-returned',
})
GDM_SEMANTIC_APPLICATION_NAMES = frozenset({'gnome-shell', 'gnome shell'})
GDM_ACCOUNT_ROLES = frozenset({'button', 'push button'})
GDM_DIAGNOSTIC_ROLES = frozenset({
    'application', 'button', 'push button', 'label', 'password text',
    'toggle button', 'radio button', 'menu item', 'radio menu item',
    'check menu item', 'combo box',
})
# G03 observation only: these are provider labels, never invented public IDs.
GDM_SESSION_LABELS = {
    'Session': 'session-chooser', 'Select Session': 'session-chooser',
    'Choose Session': 'session-chooser',
    'Oh No! Parent Control': 'station', 'GNOME': 'gnome',
    'GNOME on Xorg': 'gnome-xorg', 'Ubuntu': 'ubuntu',
    'Ubuntu on Xorg': 'ubuntu-xorg', 'Sign In': 'sign-in',
    'Log In': 'sign-in', 'Cancel': 'cancel',
}
KIOSK_OPERATIONS = frozenset({'kiosk-request-form', 'kiosk-child-choices-closed',
                              'kiosk-no-child-form'})
KIOSK_CHOICE_OPERATIONS = frozenset({'kiosk-child-choices-open'})
OPERATIONS |= KIOSK_OPERATIONS | KIOSK_CHOICE_OPERATIONS
KIOSK_ACCOUNT_REQUESTS = {
    'kiosk-child-select': ('fixture-child', 'other-fixture-parent'),
    'kiosk-approver-select': ('fixture-child', 'fixture-parent'),
    'kiosk-enabled-form': ('fixture-child', 'fixture-parent'),
}
KIOSK_DISABLED_REQUESTS = {
    'kiosk-disabled-child-select': ('fixture-child', 'other-fixture-parent'),
    'kiosk-disabled-form': ('fixture-child', 'other-fixture-parent'),
}
KIOSK_ACCOUNT_REFUSALS = frozenset({'kiosk-choice-refusals', 'parent-kiosk-refused'})
OPERATIONS |= frozenset(KIOSK_ACCOUNT_REQUESTS) | frozenset(KIOSK_DISABLED_REQUESTS) | KIOSK_ACCOUNT_REFUSALS
KIOSK_EXIT_OPERATIONS = frozenset({'kiosk-request-cancel',
                                   'kiosk-request-escape-ready'})
KIOSK_SESSION_OPERATIONS = (KIOSK_OPERATIONS | KIOSK_EXIT_OPERATIONS | KIOSK_CHOICE_OPERATIONS
                            | frozenset(KIOSK_ACCOUNT_REQUESTS) | frozenset(KIOSK_DISABLED_REQUESTS)
                            | {'kiosk-choice-refusals'})
STATION_BRANCH_OPERATIONS = frozenset({'station-entry-branch', 'station-default-entry'})
APPROVER_IDENTITIES = {OTHER_PARENT: 'other-fixture-parent', PARENT: 'fixture-parent'}
APPROVER_ACCOUNTS = {OTHER_PARENT: 'onpc-parent-casey', PARENT: 'onpc-parent-jamie'}
# Public-ID inventory for external applications on the maintained Ubuntu 26.04
# host.  An observed Builder ID is recorded only when the installed provider
# owns it; it is not usable until the application and surface roots are also
# ID-addressable. ``None`` is an exact provider-ID gap. Scoped provider
# adapters such as G01 may still use the separately reviewed semantic contract;
# generic label, object-name, tree-position and geometry fallbacks stay refused.
EXTERNAL_PROVIDER_CONTRACTS = {
    'gnome-shell': {
        'application_id': None,
        'surfaces': {
            'desktop': (None, {
                'desktop': None, 'launcher': None,
            }),
            'panel': (None, {
                'activities': None, 'app-grid': None,
            }),
            'app-grid': (None, {
                'search': None, 'result::parent': None,
                'web-suggestion::parent': None,
            }),
            'notifications': (None, {'notification': None, 'dismiss': None}),
            'lock-screen': (None, {'recipient': None, 'password': None, 'unlock': None}),
        },
        # System session/power/network inputs use session_control and guarded
        # commands. Only their required public results need a GUI provider.
        'blocked_consumers': ('DESK01 desktop observation', 'DESK06-08 lock/unlock',
                              'DESK10 window activation', 'DESK12 panel reveal',
                              'SEARCH01-06', 'PANEL01-03'),
    },
    'ding-desktop': {
        'application_id': None,
        'surfaces': {
            'desktop': (None, {'desktop': None, 'file': None, 'launcher': None}),
        },
        'blocked_consumers': ('DESK desktop-icon routes', 'native desktop launch'),
    },
    'gdm': {
        'application_id': None,
        'surfaces': {
            'greeter': (None, {
                'account-list': None,
                'account-choice::parent': None,
                'account-choice::other-parent': None,
                'account-choice::child': None,
                'account-choice::other-child': None,
                'account-choice::station': None,
                'selected-recipient': None, 'password': None,
                'submit': None, 'cancel': None,
                'session-chooser': None,
                'session-choice::<provider-session-id>': None,
            }),
        },
        'blocked_consumers': ('GDM account selection/login', 'greeter result observation',
                              'kiosk entry'),
    },
    'gnome-shell-polkit-agent': {
        'application_id': None,
        'surfaces': {
            'polkit': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('authentication', 'recipient safety'),
    },
    'mate-polkit-agent': {
        'application_id': None,
        'surfaces': {
            'polkit': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('station authentication', 'recipient safety'),
    },
    'gcr-keyring-prompter': {
        'application_id': None,
        'surfaces': {
            'keyring': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('keyring unlock', 'recipient safety', 'prompt dismissal'),
    },
    'gtk-file-chooser': {
        'application_id': None,
        'surfaces': {
            'file-chooser': (None, {
                'location': None, 'file-choice': None,
                'accept': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('FILE03 native chooser route',
                              'FEED06 native chooser route',
                              'FEED08 native diagnostic-save route'),
    },
    'xdg-desktop-portal-gnome-nautilus': {
        'application_id': None,
        'surfaces': {
            'file-chooser': (None, {
                # These GTK 4 Builder IDs are published by the installed
                # Nautilus provider, but the dialog, cancel action and dynamic
                # file choices have no provider-owned IDs.
                'location': 'filename_entry', 'file-choice': None,
                'accept': 'accept_button', 'cancel': None,
            }),
        },
        'blocked_consumers': ('FILE03 portal route', 'FEED06 portal route',
                              'FEED08 portal diagnostic-save route'),
    },
    'gnome-text-editor': {
        'application_id': None,
        'surfaces': {
            'license-document': (None, {'content': None, 'close': None}),
            'ordinary-document': (None, {
                'content': None, 'save': None, 'close': None,
            }),
        },
        'blocked_consumers': ('ABOUT02', 'FILE08',
                              'FEED08 saved-output review', 'retained-work scenarios'),
    },
    'document-viewer': {
        'application_id': None,
        'surfaces': {
            'license-document': (None, {'content': None, 'close': None}),
        },
        'blocked_consumers': ('ABOUT02', 'ABOUT03'),
    },
    'gnome-papers': {
        'application_id': None,
        'surfaces': {
            'document': (None, {'content': None, 'close': None}),
        },
        'blocked_consumers': ('PDF saved-output review',),
    },
    'gnome-nautilus': {
        'application_id': None,
        'surfaces': {
            'files': (None, {'directory-row': None, 'file-row': None, 'open': None}),
        },
        'blocked_consumers': ('FILE04 tested file-manager launch',),
    },
    'gnome-file-roller': {
        'application_id': None,
        'surfaces': {
            'archive': (None, {'archive-content': None, 'extract': None, 'close': None}),
        },
        'blocked_consumers': ('FILE08 archive review', 'FEED08 archive review'),
    },
}


class UiError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise UiError(code)


def _public_automation_id(node, attributes):
    if attributes is None:
        # A provider can disappear between traversal and this query. With no
        # attributes its ID contract cannot be qualified, so treat the stale
        # node as unidentified rather than accepting a transient AccessibleId.
        return ''
    if attributes.get('toolkit') == 'WebKitGTK':
        return attributes.get('id', '')
    return node.get_accessible_id()


def public_automation_id(node):
    """Normalize the provider's public stable ID, without selector fallbacks.

    GTK/ATK publish application IDs as AccessibleId. WebKitGTK instead uses
    AccessibleId for a transient AX object number and publishes the document's
    explicit control ID in AT-SPI GetAttributes. Select that contract by the
    provider's toolkit attribute, never by a label, role or tree position.
    Keep this here so the standalone guest reader and preview reader share it.
    """
    return _public_automation_id(node, node.get_attributes())


def owned_surface_id(identity):
    """The public containing surface for repository-owned control namespaces.

    Longest/specialized prefixes precede their shared window namespace. These
    are product IDs, not external-provider aliases or label-derived selectors.
    A surface itself is discovered by its unique ID by the caller.
    """
    fixture = re.match(r'^(onpc-fixture-(?:native|flatpak|snap|game)-(?:primary|secondary))(?:-|$)', identity)
    if fixture:
        return None if identity == fixture[1] else fixture[1]
    if identity in ('child-request-tooltip', 'child-countdown-menu'):
        return None  # Shell chrome siblings; application ownership is checked separately.
    for prefix, surface in (
        ('parent-access-denied-', 'parent-access-denied-window'),
        ('parent-revoke-', 'parent-revoke-dialog'),
        ('parent-match-rule-', 'parent-match-rule-dialog'),
        ('feedback-full-privacy-', 'feedback-privacy-dialog'),
        ('feedback-privacy-', 'feedback-privacy-dialog'),
        ('feedback-success-', 'feedback-success-dialog'),
        ('error-report-unavailable-', 'error-report-unavailable-dialog'),
        ('startup-error-', 'startup-error-window'),
        ('preview-screen-', 'preview-screen-dialog'),
        ('preview-viewer-', 'preview-viewer-window'),
        ('e2e-watch-', 'e2e-watch-window'),
        ('ui-watch-', 'ui-watch-window'),
        ('about-', 'about-dialog'),
        ('feedback-', 'feedback-dialog'),
        ('parent-', 'parent-window'),
        ('kiosk-', 'kiosk-request-window'),
        ('child-countdown-', 'child-countdown-menu'),
        ('child-', 'child-screen-time-indicator'),
    ):
        if identity.startswith(prefix):
            # The privacy link opens the modal and the revoke button opens its
            # confirmation; both belong to their original containing window.
            if identity == 'feedback-privacy-link':
                return 'feedback-dialog'
            if identity == 'parent-revoke-button':
                return 'parent-window'
            return None if identity == surface else surface
    return None


PARENT_APPLICATION = 'com.puffyslippers.OhNoParentControl.Parent'
KIOSK_APPLICATION = 'com.puffyslippers.OhNoParentControl'
CHILD_APPLICATION = 'com.puffyslippers.OhNoParentControl.ChildRequest'
WATCH_APPLICATION = 'org.onpc.E2EWatch'
UI_WATCH_APPLICATION = 'org.onpc.UIWatch'
PRODUCT_APPLICATIONS = (PARENT_APPLICATION, KIOSK_APPLICATION, CHILD_APPLICATION)


def owned_applications(identity):
    fixture = re.match(r'^onpc-fixture-(native|flatpak|snap|game)-(primary|secondary)(?:-|$)', identity)
    if fixture:
        return (f'com.puffyslippers.ONPCFixture.{fixture[1]}.{fixture[2]}',)
    if identity.startswith('e2e-watch-'):
        return (WATCH_APPLICATION,)
    if identity.startswith('ui-watch-'):
        return (UI_WATCH_APPLICATION,)
    if identity.startswith('parent-'):
        return (PARENT_APPLICATION,)
    if identity.startswith(('kiosk-', 'preview-screen-')):
        return (KIOSK_APPLICATION, CHILD_APPLICATION)
    if identity.startswith('preview-viewer-'):
        return ('com.puffyslippers.ScreenPreview',)
    if identity.startswith(('about-', 'feedback-', 'startup-error-', 'error-report-')):
        return PRODUCT_APPLICATIONS
    return ()


KIOSK_DIAGNOSTIC_IDS = (
    KIOSK_APPLICATION, 'kiosk-request-window', 'kiosk-request-form',
    'kiosk-child-selector', 'kiosk-approver-selector', 'kiosk-request-submit',
    'kiosk-request-cancel', 'kiosk-soft-apps-toggle', 'kiosk-screen-limit-notice',
    'kiosk-mute-button', 'kiosk-custom-duration',
    *(f'kiosk-duration-{value}' for value in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')),
)
KIOSK_DIAGNOSTIC_PHASES = frozenset({
    'start', 'dispatch', 'prompt-check', 'public-tree', 'public-ids',
    'form-tree', 'form-states', 'duration-states', 'message',
    'selected-child', 'selected-approver', 'projection', 'reset-reader',
    *KIOSK_DIAGNOSTIC_IDS,
})


class KioskDiagnostic:
    """Bounded public-read progress, never an identity or acceptance proof.

    Flush first visits before accessibility calls so even a transport timeout
    retains the last phase. Counts describe only a completed public snapshot;
    failed snapshots explicitly invalidate them. No UI text or exception text.
    """

    def __init__(self):
        self.started = time.monotonic()
        self.phase = 'start'
        self.tree = 'unread'
        self.ids = {}
        self.tree_reads = self.nodes_read = self.incomplete = self.query_errors = 0
        self.emitted = set()

    def check(self):
        # A predicate can perform many individually bounded AT-SPI calls. The
        # wait-loop deadline alone does not bound that work. Native calls retain
        # Atspi.set_timeout's existing 2s/5s limits.
        require(time.monotonic() - self.started < 90, 'ui:timeout:kiosk-request-form')

    def emit(self, phase=None, status='reading'):
        if phase is not None:
            require(phase in KIOSK_DIAGNOSTIC_PHASES, 'ui:diagnostic-phase')
            self.phase = phase
        key = (self.phase, status)
        if key in self.emitted or (len(self.emitted) >= 64 and status == 'reading'):
            return
        self.emitted.add(key)
        print(json.dumps({
            'event': 'kiosk-form-observation', 'phase': self.phase, 'status': status,
            'elapsed_ms': int((time.monotonic() - self.started) * 1000),
            'tree': self.tree, 'public_ids': self.ids,
            'tree_reads': self.tree_reads, 'nodes_read': self.nodes_read,
            'incomplete_reads': self.incomplete, 'query_errors': self.query_errors,
        }, sort_keys=True), flush=True)


class AccessibleUI:
    """Fresh semantic lookup, bounded waits, unique targets and public actions.

    Appearance/coordinates are deliberately absent from the acceptance model.
    Hidden or disabled controls cannot authorize input. An action's return value
    is not success: callers must independently observe its resulting UI state.
    """

    def __init__(self, api, *, timeout=45, query_errors=(), dispatch=None,
                 reset_observer=None, provider_contracts=None, fixture_uids=None,
                 application_ids=None, owner_pids=None, application_owners=None,
                 application_owner_history=None):
        self.api = api
        self.timeout = timeout
        self.query_errors = query_errors
        self.dispatch = dispatch
        self.last_roles = set()
        self.prompt_enabled = False
        self.prompt_session = None
        self.handling_prompt = False
        self.reset_observer = reset_observer
        self.provider_contracts = (EXTERNAL_PROVIDER_CONTRACTS if provider_contracts is None
                                   else provider_contracts)
        # Preview callers provide their declared fixture UIDs. Installed callers
        # resolve the fixed fixture account, never infer identity from UI labels.
        self.fixture_uids = fixture_uids
        self.application_ids = application_ids
        self.owner_pids = owner_pids
        self.application_owners = application_owners
        self.application_owner_history = application_owner_history
        self._observation_cache = None
        self.input_uncertain = False
        self.incomplete_observations = []
        self.gdm_row_diagnostic_emitted = False
        self.kiosk_diagnostic = None

    @property
    def input_uncertain(self):
        return self._input_uncertain

    @input_uncertain.setter
    def input_uncertain(self, value):
        # Every public input sets this latch before dispatch. No read captured
        # before an action may authorize its result, even inside a predicate.
        if value:
            self.invalidate_observation()
        self._input_uncertain = value

    def invalidate_observation(self):
        """End the current read boundary before input, retry or client reset."""
        if self._observation_cache is not None:
            self._observation_cache.clear()

    @contextmanager
    def observation(self):
        """Share complete reads across composed helpers until input or retry.

        The operation entry point and standalone waits open this scope. Nested
        helpers reuse it without knowing the element/provider being observed.
        Input, a pending predicate, or an accessibility-client reset invalidates
        it. Leaving the outermost scope discards all observations.
        """
        previous = self._observation_cache
        if previous is None:
            self._observation_cache = []
        try:
            yield
        except BaseException:
            self.invalidate_observation()
            raise
        finally:
            if previous is None:
                self._observation_cache = None

    def nodes(self, root=None, *, strict=False, protected_ids=(), protect_text=False,
              snapshot=None, facts=None, identities=None):
        """Reuse complete reads only within an explicit observation boundary."""
        if self._observation_cache is None:
            yield from self._read_nodes(
                root, strict=strict, protected_ids=protected_ids, protect_text=protect_text,
                snapshot=snapshot, facts=facts, identities=identities)
            return
        root = root if root is not None else self.api.get_desktop(0)
        protection = (frozenset(protected_ids), protect_text)
        for policy, read_nodes, edges, read_facts, read_ids in reversed(self._observation_cache):
            if policy == protection and root in edges:
                selected = self.snapshot_scope(read_nodes, edges, root)
                if not strict:
                    # Preserve the legacy reader's text-child exclusion when
                    # projecting a complete strict read; never broaden a scope.
                    allowed, pending = set(), [root]
                    while pending:
                        node = pending.pop()
                        if node in allowed:
                            continue
                        allowed.add(node)
                        if read_facts[node]['role'] not in ('text', 'entry'):
                            pending.extend(edges[node])
                    selected = [node for node in selected if node in allowed]
                break
        else:
            if not strict:
                # A tolerant read can silently omit unavailable subtrees and
                # therefore can never seed a later complete observation.
                yield from self._read_nodes(
                    root, strict=False, protected_ids=protected_ids, protect_text=protect_text,
                    snapshot=snapshot, facts=facts, identities=identities)
                return
            edges, read_facts, read_ids = {}, {}, {}
            try:
                selected = list(self._read_nodes(
                    root, strict=True, protected_ids=protected_ids, protect_text=protect_text,
                    snapshot=edges, facts=read_facts, identities=read_ids))
            except BaseException:
                self.invalidate_observation()
                raise
            # Publish only after traversal completes. Partial reads, including
            # query errors and missing children, never enter the reusable set.
            self._observation_cache.append((protection, selected, edges, read_facts, read_ids))
        if snapshot is not None:
            snapshot.update({node: ([] if not strict and read_facts[node]['role'] in
                                   ('text', 'entry') else list(edges[node]))
                             for node in selected})
        if facts is not None:
            facts.update({node: dict(read_facts[node]) for node in selected})
        if identities is not None:
            identities.update({node: read_ids[node] for node in selected})
        yield from selected

    def _read_nodes(self, root=None, *, strict=False, protected_ids=(), protect_text=False,
                    snapshot=None, facts=None, identities=None):
        diagnostic = self.kiosk_diagnostic
        if diagnostic is not None:
            diagnostic.check()
            diagnostic.tree_reads += 1
        root = root if root is not None else self.api.get_desktop(0)
        pending = [root]
        visited = 0
        seen = set()
        while pending:
            if diagnostic is not None:
                diagnostic.check()
                diagnostic.nodes_read += 1
            node = pending.pop()
            if node is None:
                require(not strict, 'ui:incomplete-tree')
                continue
            visited += 1
            require(visited <= 6000, 'ui:tree-bound')
            # GTK can expose the same accessible through two parent paths
            # during a stack transition. Identity deduplication still refuses
            # two distinct matching controls and bounds malformed cycles.
            if node in seen:
                continue
            seen.add(node)
            try:
                node.clear_cache_single()
                attributes = node.get_attributes()
                if strict:
                    require(attributes is not None, 'ui:incomplete-tree')
                role = node.get_role_name()
                identity = _public_automation_id(node, attributes)
                if identities is not None:
                    identities[node] = identity
                if facts is not None:
                    states = node.get_state_set()
                    facts[node] = {
                        'identity': identity,
                        'role': role,
                        'name': node.get_name(),
                        'showing': (states.contains(self.api.StateType.SHOWING)
                                    and states.contains(self.api.StateType.VISIBLE)
                                    and not states.contains(self.api.StateType.DEFUNCT)),
                        'modal': states.contains(self.api.StateType.MODAL),
                    }
                yield node
                if diagnostic is not None:
                    diagnostic.check()
                # Never traverse password contents. Strict owned observations
                # include ordinary text descendants without reading text values.
                protected = identity in protected_ids
                if (not protected and role != 'password text'
                        and not (protect_text and role in ('text', 'entry'))
                        and (strict or role not in ('text', 'entry'))):
                    children = []
                    for i in reversed(range(node.get_child_count())):
                        if diagnostic is not None:
                            diagnostic.check()
                        children.append(node.get_child_at_index(i))
                    if strict and None in children:
                        error = UiError('ui:incomplete-tree')
                        error.add_note('Null child under public automation-id: '
                                       + (public_automation_id(node) or '[unidentified]'))
                        raise error
                    if snapshot is not None:
                        snapshot.setdefault(node, []).extend(
                            child for child in children if child is not None)
                    pending.extend(children)
                elif snapshot is not None:
                    snapshot.setdefault(node, [])
            except self.query_errors:
                if strict:
                    raise
                # A dead unrelated subtree must not hide live controls.
                continue

    @staticmethod
    def snapshot_scope(nodes, snapshot, root):
        """Return root's scope from one complete traversal, without rereading it."""
        require(root in snapshot and root in nodes, 'ui:wrong-scope')
        pending = [root]
        descendants = set()
        while pending:
            node = pending.pop()
            if node in descendants:
                continue
            descendants.add(node)
            pending.extend(snapshot.get(node, ()))
        return [node for node in nodes if node in descendants]

    @staticmethod
    def snapshot_matches(identity, nodes, *, showing=None, show=None, identities=None):
        """Resolve one ID from an already complete snapshot.

        ``show`` is injected by callers so this helper never starts another
        tree read while an input recipient is being qualified.
        """
        matches = [node for node in nodes if (
            public_automation_id(node) if identities is None else identities[node]) == identity]
        require(len(matches) <= 1, 'ui:ambiguous-automation-id')
        if not matches or (showing is True and not show(matches[0])):
            return None
        return matches[0]

    def snapshot_owned_target(self, identity, *, root=None, showing=True,
                              check_prompt=False, observation=None,
                              allow_unmapped_surface=False):
        """Resolve one repository-owned ID from one complete public snapshot."""
        require(type(identity) is str and identity, 'ui:automation-id')
        applications = owned_applications(identity)
        shell_owned = identity.startswith('child-')
        require(applications or shell_owned, 'ui:unowned-automation-id')
        if observation is None:
            snapshot = {}
            facts = {}
            identities = {}
            nodes = list(self.nodes(strict=True, snapshot=snapshot, identities=identities,
                                    **({'facts': facts} if check_prompt else {})))
        else:
            nodes, snapshot, identities, facts = observation
            require(all(node in snapshot and node in identities for node in nodes),
                    'ui:incomplete-tree')
        if check_prompt:
            require(facts is not None and all(node in facts for node in nodes),
                    'ui:incomplete-tree')
            self.handle_system_prompt(observation=(nodes, snapshot, facts))

        if shell_owned:
            anchors = [node for node in nodes
                       if identities[node] == 'child-screen-time-indicator']
            require(len(anchors) <= 1, 'ui:ambiguous-automation-id')
            if not anchors:
                return None
            application = anchors[0].get_application()
            require(application is not None and application in nodes,
                    'ui:missing-application-owner')
            scope = self.snapshot_scope(nodes, snapshot, application)
            require(anchors[0] in scope, 'ui:wrong-application-owner')
        else:
            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                applications = tuple(value for value in applications if value in requested)
            owners = [node for node in nodes if identities[node] in applications]
            require(len(owners) <= 1, 'ui:ambiguous-application')
            if not owners:
                return None
            application = owners[0]
            if self.owner_pids is not None:
                require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
            if self.application_owners is not None:
                owners_by_id = self.application_owners()
                require(application.get_process_id() in owners_by_id.get(
                    identities[application], ()), 'ui:wrong-application-owner')
            scope = self.snapshot_scope(nodes, snapshot, application)

        surface_id = owned_surface_id(identity)
        if surface_id is not None:
            surface = self.snapshot_matches(
                surface_id, scope, showing=False, show=self.showing, identities=identities)
            if surface is None:
                return None
            if not shell_owned:
                self.validate_owned_surface(
                    surface, application, nodes=nodes, snapshot=snapshot, identities=identities)
            scope = self.snapshot_scope(nodes, snapshot, surface)
        elif not shell_owned and identity.endswith(('-dialog', '-window')):
            surface = self.snapshot_matches(
                identity, scope, showing=False, show=self.showing, identities=identities)
            if surface is not None:
                self.validate_owned_surface(
                    surface, application, nodes=nodes, snapshot=snapshot,
                    identities=identities, allow_unmapped=allow_unmapped_surface)

        if root is not None:
            root_id = identities.get(root, '')
            require(bool(root_id), 'ui:unidentified-scope')
            application_scope = self.snapshot_scope(nodes, snapshot, application)
            current = [node for node in application_scope if identities[node] == root_id]
            require(len(current) == 1 and current[0] == root, 'ui:wrong-scope')
            subtree = set(self.snapshot_scope(nodes, snapshot, root))
            scope = [node for node in scope if node in subtree]
        return self.snapshot_matches(
            identity, scope, showing=showing, show=self.showing, identities=identities)

    def snapshot_provider_target(self, provider, surface, control, *, showing=True,
                                 check_prompt=False):
        """Resolve a registered provider surface/control with one tree read."""
        application_id, surface_id, registered = self.require_provider_contract(
            provider, surface, (control,))
        protected = tuple(registered[key] for key in ('password', 'secret')
                          if key in registered and registered[key])
        snapshot = {}
        facts = {}
        identities = {}
        nodes = list(self.nodes(
            strict=True, protected_ids=protected, snapshot=snapshot, identities=identities,
            **({'facts': facts} if check_prompt else {})))
        if check_prompt:
            self.handle_system_prompt(observation=(nodes, snapshot, facts))
        application = self.snapshot_matches(
            application_id, nodes, showing=showing, show=self.showing, identities=identities)
        if application is None:
            return None
        application_nodes = self.snapshot_scope(nodes, snapshot, application)
        surface_root = self.snapshot_matches(
            surface_id, application_nodes, showing=showing, show=self.showing, identities=identities)
        if surface_root is None:
            return surface_root
        surface_nodes = self.snapshot_scope(nodes, snapshot, surface_root)
        return self.snapshot_matches(
            registered[control], surface_nodes, showing=showing, show=self.showing, identities=identities)

    def find_id(self, identity, *, root=None, nodes=None, showing=True):
        """Resolve exactly one public automation ID without selector fallbacks."""
        require(type(identity) is str and identity, 'ui:automation-id')
        if owned_applications(identity) or identity.startswith('child-'):
            found = self.snapshot_owned_target(identity, root=root, showing=showing)
            return found if nodes is None or found is None or found in nodes else None
        identities = {} if nodes is None else None
        candidates = self.nodes(root, identities=identities) if nodes is None else nodes
        found = None
        for node in candidates:
            try:
                if (identities[node] if identities is not None else public_automation_id(node)) != identity:
                    continue
                require(found is None, 'ui:ambiguous-automation-id')
                found = node
            except self.query_errors:
                continue
        if found is None or (showing and not self.showing(found)):
            return None
        return found

    def find_all_ids(self, identity, *, root=None, nodes=None):
        require(not owned_applications(identity) and not identity.startswith('child-'),
                'ui:owned-id-requires-direct-lookup')
        identities = {} if nodes is None else None
        candidates = self.nodes(root, identities=identities) if nodes is None else nodes
        found = []
        for node in candidates:
            try:
                if (identities[node] if identities is not None else public_automation_id(node)) != identity:
                    continue
                found.append(node)
            except self.query_errors:
                continue
        return found

    def validate_owned_surface(self, surface, application, *, visited=(), nodes=None,
                               snapshot=None, identities=None, allow_unmapped=False):
        """Bind a dialog to its actual originating surface in the same app."""
        identify = public_automation_id if identities is None else identities.__getitem__
        identity = identify(surface)
        app_id = identify(application)
        primary = ((f'onpc-fixture-{"-".join(app_id.split(".")[-2:])}',)
                   if app_id.startswith('com.puffyslippers.ONPCFixture.') else
                   ('e2e-watch-window',) if app_id == WATCH_APPLICATION else
                   ('ui-watch-window',) if app_id == UI_WATCH_APPLICATION else
                   ('parent-window', 'parent-access-denied-window', 'startup-error-window')
                   if app_id == PARENT_APPLICATION else
                   ('kiosk-request-window', 'startup-error-window')
                   if app_id in (KIOSK_APPLICATION, CHILD_APPLICATION) else
                   ('preview-viewer-window',))
        require(identity not in visited and len(visited) < 8, 'ui:surface-owner-cycle')
        if identity in primary:
            return
        expected = (('feedback-dialog',) if identity == 'feedback-privacy-dialog' else
                    ('parent-window',) if identity in ('parent-revoke-dialog', 'parent-match-rule-dialog') else
                    ('kiosk-request-window',) if identity == 'preview-screen-dialog' else
                    tuple(value for value in primary if value != 'parent-access-denied-window'))
        if nodes is None or snapshot is None:
            snapshot = {}
            app_nodes = list(self.nodes(application, strict=True, snapshot=snapshot))
            nodes = app_nodes
        else:
            app_nodes = self.snapshot_scope(nodes, snapshot, application)
        # Embedded Adw dialogs can retain true containment. Separate GTK
        # toplevels publish CONTROLLED_BY from their native transient parent.
        containers = [node for node in app_nodes if identify(node) in expected]
        for container in containers:
            if surface in self.snapshot_scope(nodes, snapshot, container):
                self.validate_owned_surface(
                    container, application, visited=(*visited, identity),
                    nodes=nodes, snapshot=snapshot, identities=identities)
                return
        parents = []
        for relation in surface.get_relation_set():
            if relation.get_relation_type() == self.api.RelationType.CONTROLLED_BY:
                parents.extend(relation.get_target(index)
                               for index in range(relation.get_n_targets()))
        # Repository surfaces deliberately remove CONTROLLED_BY when they
        # unmap. A complete negative observation may still see the hidden GTK
        # accessible briefly, so its application scope proves ownership while
        # its missing relation proves that it is no longer mapped. Showing
        # surfaces and any relation that remains retain the full owner checks.
        if allow_unmapped and not parents and not self.showing(surface):
            return
        require(len(parents) == 1 and parents[0] in app_nodes, 'ui:missing-surface-owner')
        parent = parents[0]
        require(identities is None or parent in identities, 'ui:wrong-surface-owner')
        parent_id = identify(parent)
        require(parent_id in expected, 'ui:wrong-surface-owner')
        matches = [node for node in app_nodes if identify(node) == parent_id]
        require(len(matches) == 1, 'ui:ambiguous-surface-owner')
        self.validate_owned_surface(
            parent, application, visited=(*visited, identity),
            nodes=nodes, snapshot=snapshot, identities=identities)

    def absent_id(self, identity, *, within):
        """Fresh complete negative observation with a positive surrounding ID."""
        try:
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            if not nodes or any(self.has_state(node, self.api.StateType.DEFUNCT)
                                for node in nodes):
                return False
            observation = (nodes, snapshot, identities, None)
            anchor = (self.snapshot_owned_target(
                within, observation=observation)
                if owned_applications(within) or within.startswith('child-') else
                self.snapshot_matches(
                    within, nodes, showing=True, show=self.showing,
                    identities=identities))
            if anchor is None:
                return False
            matches = [node for node in nodes if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if matches:
                target = (self.snapshot_owned_target(
                    identity, showing=False, observation=observation,
                    allow_unmapped_surface=True)
                    if owned_applications(identity) or identity.startswith('child-') else
                    self.snapshot_matches(
                        identity, nodes, showing=False, show=self.showing,
                        identities=identities))
                if target != matches[0]:
                    # A launched process can exit before AT-SPI removes its
                    # last cached node. That node cannot prove absence and is
                    # no longer eligible for input, but it is not a foreign
                    # owner. Retry until a fresh complete tree drops it.
                    history = (self.application_owner_history()
                               if self.application_owner_history is not None else {})
                    expected = owned_applications(identity)
                    known_pids = {
                        pid for application in expected
                        for pid in history.get(application, ())
                    }
                    if expected and matches[0].get_process_id() in known_pids:
                        return False
                    raise UiError('ui:wrong-absence-owner')
                if self.showing(target):
                    return False
            return True
        except self.query_errors:
            return False  # An incomplete read never proves absence.
        except UiError as error:
            if str(error) == 'ui:incomplete-tree':
                return False
            raise

    def find_provider_control(self, provider, surface, control, *, root=None, showing=True):
        """Resolve one registered control inside its provider-owned ID scopes.

        All three identities are mandatory.  Partial provider observations stay
        useful audit evidence but cannot become selectors until the owning
        application and surface publish stable IDs too.
        """
        require(root is None, 'ui:provider-root-unsupported')
        return self.snapshot_provider_target(
            provider, surface, control, showing=showing)

    def require_provider_contract(self, provider, surface, controls):
        """Validate a complete mapping before the first public-tree read."""
        require(type(provider) is str and provider and type(surface) is str and surface
                and type(controls) is tuple and controls
                and all(type(control) is str and control for control in controls),
                'ui:provider-binding')
        contract = self.provider_contracts.get(provider)
        require(contract is not None, 'ui:unregistered-provider')
        application_id = contract.get('application_id')
        require(type(application_id) is str and application_id,
                'ui:unqualified-provider-application')
        surface_contract = contract.get('surfaces', {}).get(surface)
        require(surface_contract is not None, 'ui:unregistered-provider-surface')
        surface_id, registered = surface_contract
        require(type(surface_id) is str and surface_id,
                'ui:unqualified-provider-surface')
        for control in controls:
            require(control in registered, 'ui:unregistered-provider-control')
            require(type(registered[control]) is str and registered[control],
                    'ui:unqualified-provider-control')
        return application_id, surface_id, registered

    def provider_surface(self, provider, surface, controls, *, showing=True):
        """Resolve a qualified provider surface without label/role fallbacks."""
        application_id, surface_id, registered = self.require_provider_contract(
            provider, surface, controls)
        protected = tuple(registered[key] for key in ('password', 'secret')
                          if key in registered and registered[key])
        snapshot = {}
        identities = {}
        desktop = list(self.nodes(
            strict=True, protected_ids=protected, snapshot=snapshot, identities=identities))
        application = self.snapshot_matches(
            application_id, desktop, showing=showing, show=self.showing, identities=identities)
        if application is None:
            return None, registered
        application_nodes = self.snapshot_scope(desktop, snapshot, application)
        return self.snapshot_matches(
            surface_id, application_nodes, showing=showing, show=self.showing,
            identities=identities), registered

    def showing(self, node):
        states = node.get_state_set()
        return (states.contains(self.api.StateType.SHOWING)
                and states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT))

    def has_state(self, node, state):
        node.clear_cache_single()
        return node.get_state_set().contains(state)

    def find(self, name=None, roles=(), *, root=None, sensitive=False, contains=None,
             showing=True, editable=False):
        """Retired name/role selector; public automation IDs are mandatory."""
        raise UiError('ui:legacy-selector-refused')

    def wait(self, predicate, code, *, prompt_in_predicate=False):
        deadline = time.monotonic() + self.timeout
        incomplete = None
        while True:
            # Deliver pending public AT-SPI events before fresh reads. Cache
            # invalidation alone cannot deliver focus/text/registry changes.
            if self.kiosk_diagnostic is not None:
                self.kiosk_diagnostic.emit('dispatch')
                self.kiosk_diagnostic.check()
            # Composed read helpers can share an already complete snapshot.
            # Dispatch before a new read boundary, never midway through one.
            if self.dispatch is not None and not self._observation_cache:
                for _ in range(32):
                    if not self.dispatch():
                        break
            try:
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.emit('prompt-check')
                with self.observation():
                    if not prompt_in_predicate:
                        self.handle_system_prompt()
                    value = predicate()
            except self.query_errors:
                # UI objects can disappear during search/animation. Retry only
                # the read, never replay an action whose effect is uncertain.
                value = None
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.query_errors += 1
                    self.kiosk_diagnostic.emit(status='query-error')
            except UiError as error:
                if str(error) not in (
                        'ui:incomplete-tree', 'ui:stale-picker',
                        'ui:system-prompt-observation-failed'):
                    raise
                # Discard the entire observation. A child can disappear between
                # ChildCount and GetChildAtIndex during a public UI transition.
                # GTK can likewise leave a defunct picker node in one AT-SPI
                # snapshot while removing a closed popover. Prompt scans can
                # encounter the same disappearing objects; a failed scan never
                # authorizes the predicate or any input.
                # Only a later complete read may satisfy the predicate; no
                # action is replayed and the original deadline is retained.
                incomplete = error
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.incomplete += 1
                    self.kiosk_diagnostic.emit(status='incomplete')
                self.incomplete_observations.append({
                    'checkpoint': code, 'notes': getattr(error, '__notes__', [])})
                self.incomplete_observations = self.incomplete_observations[-16:]
                value = None
            if value:
                return value
            self.invalidate_observation()
            if time.monotonic() >= deadline:
                if incomplete is not None and str(incomplete) in (
                        'ui:stale-picker', 'ui:system-prompt-observation-failed'):
                    raise incomplete
                raise UiError('ui:timeout:' + code) from incomplete
            time.sleep(.2)

    def target(self, name=None, roles=(), **kwargs):
        raise UiError('ui:legacy-selector-refused')

    def id_target(self, identity, *, root=None, sensitive=False, showing=True):
        """Wait for one public ID, optionally requiring an actionable state."""
        owned = bool(owned_applications(identity) or identity.startswith('child-'))
        node = self.wait(
            (lambda: self.snapshot_owned_target(
                identity, root=root, showing=showing, check_prompt=True))
            if owned else
            (lambda: self.find_id(identity, root=root, showing=showing)),
            'automation-id',
            prompt_in_predicate=owned,
        )
        if sensitive:
            require(self.has_state(node, self.api.StateType.SENSITIVE),
                    'ui:unusable-target')
        return node

    def _invoke_target(self, node, action_name=None):
        """Invoke an ID-qualified target without another public-tree traversal."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        states = node.get_state_set()
        # SHOWING is a viewport/rendering state. A clipped or covered control
        # remains directly actionable while the application keeps it VISIBLE
        # and SENSITIVE; truly hidden or disabled application state still
        # refuses input.
        require(states.contains(self.api.StateType.VISIBLE)
                and states.contains(self.api.StateType.SENSITIVE)
                and not states.contains(self.api.StateType.DEFUNCT),
                'ui:unusable-target')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-action')
        count = self.api.Action.get_n_actions(action)
        if action_name is None:
            require(count == 1, 'ui:missing-or-ambiguous-action')
            matches = [0]
        else:
            names = []
            for index in range(count):
                # GI incorrectly deprecates the recommended rename of this
                # AT-SPI method. Suppress only that metadata warning here.
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        'ignore',
                        message=r'^Atspi\.Action\.get_action_name is deprecated$',
                        category=DeprecationWarning,
                    )
                    names.append(self.api.Action.get_action_name(action, index))
            matches = [index for index, name in enumerate(names) if name == action_name]
            require(len(matches) == 1, 'ui:missing-or-ambiguous-action')
        self.input_uncertain = True
        require(self.api.Action.do_action(action, matches[0]), 'ui:action-refused')
        self.input_uncertain = False
        return node

    def activate_id(self, identity, *, action_name=None):
        """Resolve and invoke one repository-owned automation ID in one snapshot."""
        require(type(identity) is str and identity, 'ui:automation-id')
        require(owned_applications(identity) or identity.startswith('child-'),
                'ui:unowned-automation-id')
        node = self.wait(
            lambda: self.snapshot_owned_target(
                identity, showing=False, check_prompt=True),
            'automation-id', prompt_in_predicate=True,
        )
        return self._invoke_target(node, action_name)

    def activate_provider(self, provider, surface, control, *, action_name=None):
        """Resolve and invoke one qualified external-provider ID in one snapshot."""
        node = self.wait(
            lambda: self.snapshot_provider_target(
                provider, surface, control, showing=False, check_prompt=True),
            'provider-automation-id', prompt_in_predicate=True,
        )
        return self._invoke_target(node, action_name)

    def activate(self, node):
        return self._invoke_target(self.fresh_owned_target(node))

    def activate_named(self, node, action_name):
        """Invoke one named public action on an already ID-resolved control."""
        return self._invoke_target(self.fresh_owned_target(node), action_name)

    def fresh_owned_target(self, node):
        identity = public_automation_id(node)
        require(bool(identity), 'ui:unidentified-action-target')
        if owned_applications(identity) or identity.startswith('child-'):
            current = self.snapshot_owned_target(
                identity, showing=False, check_prompt=True)
            require(current is not None and current == node, 'ui:wrong-action-owner')
            return current
        bindings = [(provider, surface, control)
                    for provider, contract in self.provider_contracts.items()
                    for surface, (_surface_id, controls) in contract.get('surfaces', {}).items()
                    for control, registered_id in controls.items() if registered_id == identity]
        require(len(bindings) == 1, 'ui:unregistered-or-ambiguous-action-target')
        current = self.snapshot_provider_target(
            *bindings[0], showing=False, check_prompt=True)
        require(current is not None and current == node, 'ui:wrong-action-owner')
        return current

    def reveal(self, name, roles, *, root):
        raise UiError('ui:legacy-selector-refused')

    def scroll_target(self, name, roles, *, root):
        raise UiError('ui:legacy-selector-refused')

    def find_labelled_control(self, name, roles, *, root=None):
        raise UiError('ui:legacy-selector-refused')

    def find_labelled_button(self, name, *, root=None):
        raise UiError('ui:legacy-selector-refused')

    def labelled_button(self, name):
        raise UiError('ui:legacy-selector-refused')

    def parent(self):
        return self.id_target('parent-window')

    def about(self):
        return self.id_target('about-dialog')

    def open_about(self, version):
        """ABOUT01: independent Parent entry; menu, About, text and license link."""
        self.activate_id('parent-menu-button', action_name='menu.popup')
        self.activate_id('parent-menu-about')
        root = self.about()
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        self.reveal_id('about-license-value', root=root)

    def reveal_id(self, identity, *, root):
        node = self.id_target(identity, root=root, showing=False)
        if not self.showing(node):
            surface = owned_surface_id(identity)
            require(surface is not None, 'ui:missing-reveal-surface')
            self.activate_id(surface, action_name='focus.' + identity)
        return self.id_target(identity)

    def read_document(self, root, projection, *, maximum):
        """UI03: only the bounded GPL heading projection; never return raw text."""
        require(projection == 'gpl-heading' and type(maximum) is int
                and 64 <= maximum <= 1024, 'ui:document-binding')
        if self.provider_contracts['document-viewer']['application_id']:
            _application_id, _surface_id, registered = self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
            require(public_automation_id(root) == registered['content']
                    and self.find_provider_control(
                        'document-viewer', 'license-document', 'content') is root,
                    'ui:document-owner')
        else:
            window, content, _observation = self.license_viewer_snapshot()
            require(root is content and window is not None
                    and self.has_state(window, self.api.StateType.ACTIVE),
                    'ui:document-owner')
        require(root.get_role_name() in ('text', 'document text') and self.showing(root),
                'ui:document-surface')
        text = root.get_text_iface()
        if text is None:
            return False
        count = self.api.Text.get_character_count(text)
        require(type(count) is int and count >= 0, 'ui:document-bound')
        value = self.api.Text.get_text(text, 0, min(count, maximum))
        require(type(value) is str and len(value) <= maximum, 'ui:document-bound')
        return self.license_headings_match(value)

    @staticmethod
    def license_headings_match(value):
        return ('GNU GENERAL PUBLIC LICENSE' in value
                and 'Version 3, 29 June 2007' in value)

    @staticmethod
    def license_fixture_path(kind):
        require(kind in ('unrelated', 'empty', 'ambiguous'), 'ui:license-fixture-kind')
        return Path('/tmp/onpc-e2e-license-' + kind + '.txt')

    def license_fixture_launch(self, kind):
        """Open an owned synthetic document in the installed handler."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        if kind == 'ambiguous':
            self.window_ready_to_close('license')
        else:
            window, _content, _observation = self.license_viewer_snapshot()
            require(window is None and self.about() is not None,
                    'ui:license-fixture-entry')
        path = self.license_fixture_path(kind)
        with path.open('x') as stream:
            if kind != 'empty':
                # GtkSourceFileLoader omits an implicit trailing newline from
                # the public buffer. Use identical file and displayed text.
                stream.write('ONPC E2E synthetic ' + kind + ' document')
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/gnome-text-editor',
            '--new-window', str(path),
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)

    def license_fixture_windows(self, kind):
        """Resolve only actual Text Editor windows and fixture document text."""
        desktop = self.api.get_desktop(0)
        require(desktop is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(desktop, strict=True, snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        owners = [node for node in snapshot[desktop]
                  if facts[node]['role'] == 'application'
                  and (facts[node]['identity'] == 'org.gnome.TextEditor'
                       or (not facts[node]['identity'] and facts[node]['name'].casefold()
                           in ('gnome-text-editor', 'org.gnome.texteditor', 'text editor')))]
        require(len(owners) <= 1, 'ui:license-provider-ambiguous')
        if not owners:
            return None
        owner = owners[0]
        windows = [node for node in self.snapshot_scope(nodes, snapshot, owner)
                   if facts[node]['role'] in ('frame', 'window') and facts[node]['showing']]
        expected = 2 if kind == 'ambiguous' else 1
        require(len(windows) <= expected, 'ui:license-fixture-window-count')
        if len(windows) < expected:
            return None
        active = [node for node in windows if self.has_state(node, self.api.StateType.ACTIVE)]
        require(len(active) <= 1, 'ui:license-fixture-active-window')
        if not active:
            return None
        window = active[0]
        documents = [node for node in self.snapshot_scope(nodes, snapshot, window)
                     if facts[node]['identity'] == 'view']
        require(len(documents) <= 1, 'ui:license-fixture-document')
        if not documents:
            return None
        require(facts[documents[0]]['showing']
                and facts[documents[0]]['role'] in ('text', 'document text')
                and owner.get_process_id() > 0
                and window.get_process_id() == owner.get_process_id()
                and documents[0].get_process_id() == owner.get_process_id(),
                'ui:license-fixture-document')
        content = documents[0]
        text = content.get_text_iface()
        require(text is not None, 'ui:license-fixture-text')
        count = self.api.Text.get_character_count(text)
        require(type(count) is int and 0 <= count <= 128, 'ui:license-fixture-text')
        value = self.api.Text.get_text(text, 0, count)
        expected_text = '' if kind == 'empty' else 'ONPC E2E synthetic ' + kind + ' document'
        require(value == expected_text, 'ui:license-fixture-content')
        return window, content

    def license_fixture_ready(self, kind):
        window, content = self.wait(lambda: self.license_fixture_windows(kind),
                                    'license-fixture-' + kind)
        if kind == 'ambiguous':
            for action in (self.license_viewer_snapshot,
                           lambda: self.window_ready_to_close('license')):
                try:
                    action()
                except UiError as error:
                    require(str(error) == 'ui:license-window-ambiguous',
                            'ui:license-ambiguity-refusal')
                else:
                    raise UiError('ui:license-ambiguity-accepted')
        else:
            require(not self.read_document(content, 'gpl-heading', maximum=1024),
                    'ui:license-unrelated-content-accepted')
            try:
                self.open_license()
            except UiError as error:
                require(str(error) == 'ui:license-already-open',
                        'ui:license-wrong-entry-refusal')
            else:
                raise UiError('ui:license-wrong-entry-accepted')
        require(self.has_state(window, self.api.StateType.ACTIVE),
                'ui:license-fixture-close-recipient')

    def license_fixture_closed(self, kind):
        if kind == 'ambiguous':
            self.window_ready_to_close('license')
        else:
            self.window_closed('license', 'about')
        self.license_fixture_path(kind).unlink()

    def license_provider_metadata(self):
        """Record the actual viewer locale, installed package and input sources."""
        from gi.repository import Gio
        window, content, _observation = self.license_viewer_snapshot()
        require(window is not None and content is not None,
                'ui:license-provider-owner')
        pid = window.get_process_id()
        require(type(pid) is int and pid > 0, 'ui:license-provider-owner')
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                           if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}',
             'gnome-text-editor'], text=True, timeout=5).strip()
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        return validate_shell_metadata({'version': version, 'locale': locale,
                                        'keyboard': [list(source) for source in sources]})

    def license_viewer_snapshot(self):
        """GNOME Text Editor 50 provider exception for ABOUT02/03 only.

        The application/window have no usable public IDs. Resolve the registry
        application and its sole showing window by scoped public semantics, then
        use the provider's Builder ID ``view`` for the document. Never identify
        a document by its title, contents, position or geometry. Other handlers,
        multiple windows/documents and prompts cannot authorize reading/closing.
        """
        desktop = self.api.get_desktop(0)
        require(desktop is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(desktop, strict=True, snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        owners = [node for node in snapshot[desktop]
                  if facts[node]['role'] == 'application'
                  and (facts[node]['identity'] == 'org.gnome.TextEditor'
                       or (not facts[node]['identity'] and facts[node]['name'].casefold()
                           in ('gnome-text-editor', 'org.gnome.texteditor', 'text editor')))]
        require(len(owners) <= 1, 'ui:license-provider-ambiguous')
        observation = (nodes, snapshot, facts)
        if not owners:
            return None, None, observation
        owner = owners[0]
        owned = self.snapshot_scope(nodes, snapshot, owner)
        windows = [node for node in owned if facts[node]['role'] in ('frame', 'window')
                   and facts[node]['showing']]
        require(len(windows) <= 1, 'ui:license-window-ambiguous')
        if not windows:
            return None, None, observation
        window = windows[0]
        scoped = self.snapshot_scope(nodes, snapshot, window)
        documents = [node for node in scoped if facts[node]['identity'] == 'view']
        require(len(documents) <= 1, 'ui:license-document-ambiguous')
        content = documents[0] if documents else None
        require(owner.get_process_id() > 0
                and window.get_process_id() == owner.get_process_id()
                and (content is None or content.get_process_id() == owner.get_process_id()),
                'ui:document-owner')
        if content is not None and (facts[content]['role'] not in ('text', 'document text')
                                    or not facts[content]['showing']):
            content = None
        return window, content, observation

    def license_content(self):
        """Read the ID-scoped registered viewer, without title discovery."""
        def document():
            if not self.provider_contracts['document-viewer']['application_id']:
                window, node, _observation = self.license_viewer_snapshot()
                return (node is not None and self.has_state(window, self.api.StateType.ACTIVE)
                        and self.read_document(node, 'gpl-heading', maximum=1024))
            surface, registered = self.provider_surface(
                'document-viewer', 'license-document', ('content', 'close'))
            if surface is None:
                return False
            node = self.find_id(registered['content'], root=surface)
            return (node is not None and node.get_role_name() in ('text', 'document text')
                    and self.showing(node)
                    and self.read_document(node, 'gpl-heading', maximum=1024))
        return self.wait(document, 'license-content')

    def open_license(self):
        """ABOUT02: one link action followed by actual viewer content."""
        if self.provider_contracts['document-viewer']['application_id']:
            self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
        else:
            # A pre-existing editor must not supply unrelated content or receive
            # the subsequent Alt-F4. The link is the sole launch input.
            window, _content, _observation = self.license_viewer_snapshot()
            require(window is None, 'ui:license-already-open')
        self.activate_id('about-license-value')
        self.license_content()

    def window_ready_to_close(self, window):
        """UI01/02: fresh active named window before a worker's Alt-F4."""
        require(window in ('license', 'about'), 'ui:window-binding')
        def active():
            if window == 'license':
                if not self.provider_contracts['document-viewer']['application_id']:
                    root, content, _observation = self.license_viewer_snapshot()
                    if content is None:
                        return False
                    # Reacquire and verify the document again at the close input
                    # boundary; successful launch alone never authorizes input.
                    if not self.read_document(content, 'gpl-heading', maximum=1024):
                        return False
                else:
                    root, _registered = self.provider_surface(
                        'document-viewer', 'license-document', ('content', 'close'))
            else:
                root = self.find_id('about-dialog')
            return root is not None and self.has_state(root, self.api.StateType.ACTIVE)
        self.wait(active, 'active-' + window)

    def window_closed(self, window, destination):
        """UI11: complete fresh absence within the positively recognized return UI."""
        require((window, destination) in (('license', 'about'), ('about', 'parent')),
                'ui:window-binding')
        semantic_license = (window == 'license'
                            and not self.provider_contracts['document-viewer']['application_id'])
        if window == 'license' and not semantic_license:
            _application_id, surface_id, registered = self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
        def closed():
            if window == 'about':
                return self.absent_id('about-dialog', within='parent-window')
            if semantic_license:
                viewer, _content, (nodes, snapshot, facts) = self.license_viewer_snapshot()
                identities = {node: facts[node]['identity'] for node in nodes}
                underlying = self.snapshot_owned_target(
                    'about-dialog', observation=(nodes, snapshot, identities, facts))
                return (viewer is None and underlying is not None
                        and self.has_state(underlying, self.api.StateType.ACTIVE))
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            if not nodes:
                return False
            for node in nodes:
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-window')
            underlying = self.snapshot_owned_target(
                'about-dialog', observation=(nodes, snapshot, identities, None))
            if underlying is None:
                return False
            external_ids = (surface_id, registered['content'], registered['close'])
            return not any(identities[node] in external_ids and self.showing(node)
                           for node in nodes)
        self.wait(closed, window + '-close')

    def about_footer(self):
        """ABOUT04's public reveal/read, in an independently opened About window."""
        self.reveal_id('about-copyright', root=self.about())
        self.read_label(self.about(), 'about-footer', maximum=80)

    def settings(self, child=CHILD):
        """PARENT03: explicit child, public settings; no scenario expectations."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        selected = self.child_id_control(
            child, 'parent-child-selected-', root=picker, showing=True,
        )
        require(selected is not None, 'ui:selected-child')
        self.read_label(selected, 'child', expected=child, maximum=80)
        toggle = self.id_target('parent-screen-limit-toggle', root=root, sensitive=True)
        allowance = self.id_target('parent-daily-limit-selector', root=root)
        labels = self.read_label(allowance, 'allowance', maximum=80)
        if child in (EXISTING_CHILD, NEW_CHILD):
            self.reveal_id('parent-time-status', root=root)
        return {'child': CHILD_IDENTITIES[child],
                'limit_enabled': toggle.get_state_set().contains(self.api.StateType.CHECKED),
                'allowance': labels}

    def set_toggle(self, identity, desired, *, root):
        """UI17: set the one qualified Parent switch to an explicit state."""
        require(identity == 'parent-screen-limit-toggle' and type(desired) is bool,
                'ui:toggle-binding')
        # A complete lookup may legitimately omit a hidden GTK stack page.
        # Retry incomplete reads, but never wait for a missing input target to
        # appear or substitute another control.
        target, = self.wait(lambda: (self.snapshot_owned_target(
            identity, root=root, showing=False, check_prompt=True),),
            'toggle-target', prompt_in_predicate=True)
        require(target is not None, 'ui:unusable-target')
        states = target.get_state_set()
        require(states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT),
                'ui:unusable-target')
        initial = self.has_state(target, self.api.StateType.CHECKED)
        activated = initial != desired
        if activated:
            self._invoke_target(target)

        def desired_state():
            current = self.snapshot_owned_target(
                identity, root=root, showing=False, check_prompt=True)
            if current is None:
                return None
            return current if self.has_state(current, self.api.StateType.CHECKED) == desired else None

        current = self.wait(desired_state, 'toggle-state', prompt_in_predicate=True)
        require(self.has_state(current, self.api.StateType.CHECKED) == desired,
                'ui:toggle-state')
        return {'state': desired, 'activated': activated}

    def parent_toggle_operation(self, operation):
        """Installed Parent binding and bounded refusal checks for UI17."""
        require(operation in TOGGLE_OPERATIONS, 'ui:toggle-operation')
        root = self.parent()
        if operation == 'parent-toggle-wrong-refused':
            try:
                self.set_toggle('parent-legend-toggle', True, root=root)
            except UiError as error:
                require(str(error) == 'ui:toggle-binding', 'ui:toggle-wrong-refusal')
                return {'refusal': 'wrong-control'}
            raise UiError('ui:toggle-wrong-accepted')
        if operation == 'parent-toggle-hidden-refused':
            self.activate_id('parent-page-app-limits')

            def hidden():
                snapshot, identities, facts = {}, {}, {}
                nodes = list(self.nodes(strict=True, snapshot=snapshot,
                                        identities=identities, facts=facts))
                observation = (nodes, snapshot, identities, facts)
                current_root = self.snapshot_owned_target(
                    'parent-window', check_prompt=True, observation=observation)
                if current_root is None:
                    return False
                target = self.snapshot_owned_target(
                    'parent-screen-limit-toggle', root=current_root, showing=False,
                    observation=observation)
                return target is None or not self.has_state(target, self.api.StateType.VISIBLE)

            self.wait(hidden, 'toggle-hidden', prompt_in_predicate=True)
            try:
                self.set_toggle('parent-screen-limit-toggle', True, root=root)
            except UiError as error:
                require(str(error) == 'ui:unusable-target', 'ui:toggle-hidden-refusal')
            else:
                raise UiError('ui:toggle-hidden-accepted')
            self.activate_id('parent-page-screen-limits')
            target = self.id_target('parent-screen-limit-toggle')
            require(not self.has_state(target, self.api.StateType.CHECKED),
                    'ui:toggle-hidden-state-changed')
            return {'refusal': 'hidden-control', 'state': False}
        desired = operation == 'parent-toggle-enabled'
        return self.set_toggle('parent-screen-limit-toggle', desired, root=root)

    def parent_save_snapshot(self, child, expected_enabled):
        """PARENT08: wait for one terminal saved/control-state snapshot."""
        require(child in CHILD_IDENTITIES and type(expected_enabled) is bool,
                'ui:parent-save-binding')
        uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
        expected_selected = 'parent-child-selected-' + str(uid)

        def saved():
            snapshot, identities, facts = {}, {}, {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities, facts=facts))
            observation = (nodes, snapshot, identities, facts)
            root = self.snapshot_owned_target(
                'parent-window', check_prompt=True, observation=observation)
            if root is None:
                return False
            require(not any(
                identities[node] in ('feedback-dialog',
                                     'error-report-unavailable-dialog')
                and self.showing(node)
                for node in nodes
            ), 'ui:parent-save-error-report')
            root_nodes = self.snapshot_scope(nodes, snapshot, root)
            picker = self.snapshot_matches(
                'parent-child-selector', root_nodes, showing=True, show=self.showing)
            toggle = self.snapshot_matches(
                'parent-screen-limit-toggle', root_nodes, showing=True, show=self.showing)
            allowance = self.snapshot_matches(
                'parent-daily-limit-selector', root_nodes, showing=True, show=self.showing)
            if picker is None or toggle is None or allowance is None:
                return False
            picker_nodes = self.snapshot_scope(nodes, snapshot, picker)
            selected = [node for node in picker_nodes
                        if re.fullmatch(r'parent-child-selected-[0-9]+', identities[node])
                        and self.showing(node)]
            require(len(selected) == 1, 'ui:selected-child')
            require(identities[selected[0]] == expected_selected, 'ui:wrong-child')
            # The UID belongs to the selected-content box. Verify its label
            # inside this same complete snapshot, as UI03 does for selection.
            selected_nodes = self.snapshot_scope(nodes, snapshot, selected[0])
            labels = [node.get_name() for node in selected_nodes
                      if node.get_role_name() == 'label' and self.showing(node)]
            require(labels == [child], 'ui:wrong-child')
            value = {
                'child': CHILD_IDENTITIES[child], 'result': 'saved',
                'limit_enabled': self.has_state(toggle, self.api.StateType.CHECKED),
                'child_selector_enabled': self.has_state(
                    picker, self.api.StateType.SENSITIVE),
                'toggle_enabled': self.has_state(toggle, self.api.StateType.SENSITIVE),
                'allowance_enabled': self.has_state(
                    allowance, self.api.StateType.SENSITIVE),
            }
            expected = {
                'child': CHILD_IDENTITIES[child], 'result': 'saved',
                'limit_enabled': expected_enabled, 'child_selector_enabled': True,
                'toggle_enabled': True, 'allowance_enabled': expected_enabled,
            }
            return value if value == expected else False

        return self.wait(saved, 'parent-save', prompt_in_predicate=True)

    def parent_save_operation(self, operation):
        """Installed PARENT08 saved snapshot and wrong-child refusal."""
        require(operation in PARENT_SAVE_OPERATIONS, 'ui:parent-save-operation')
        if operation == 'parent-save-wrong-child-refused':
            try:
                self.parent_save_snapshot(EXISTING_CHILD, True)
            except UiError as error:
                require(str(error) == 'ui:wrong-child', 'ui:parent-save-wrong-refusal')
                return {'refusal': 'wrong-child'}
            raise UiError('ui:parent-save-wrong-accepted')
        return self.parent_save_snapshot(
            CHILD, operation != 'parent-save-disabled')

    def read_label(self, root, projection, *, maximum, expected=None):
        """UI03: bounded registered nonsecret projections; no arbitrary text."""
        require(projection in ('child', 'allowance', 'empty-explanation', 'empty-picker',
                               'search-query', 'web-suggestion', 'about-product',
                               'about-version', 'about-footer')
                and type(maximum) is int
                and 1 <= maximum <= 80, 'ui:text-binding')
        require(root.get_role_name() != 'password text', 'ui:masked-text')
        if projection.startswith('about-'):
            if projection == 'about-version':
                import re
                require(type(expected) is str and re.fullmatch(r'[0-9][0-9A-Za-z.+:~\-]{0,63}', expected),
                        'ui:version-binding')
                label = 'Version ' + expected
            else:
                label = PRODUCT if projection == 'about-product' else ABOUT_FOOTER
            require(len(label) <= maximum, 'ui:text-bound')
            identity = {'about-product': 'about-product-name',
                        'about-version': 'about-version',
                        'about-footer': 'about-copyright'}[projection]
            node = self.id_target(identity, root=root)
            require(node.get_name() == label, 'ui:about-label')
            return True
        if projection == 'search-query':
            require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal') and len(expected) <= maximum,
                    'ui:search-binding')
            _application_id, _surface_id, registered = self.require_provider_contract(
                'gnome-shell', 'app-grid', ('search',))
            require(public_automation_id(root) == registered['search']
                    and self.find_provider_control(
                        'gnome-shell', 'app-grid', 'search') is root,
                    'ui:search-owner')
            require(root.get_role_name() in ('text', 'entry') and self.showing(root)
                    and self.has_state(root, self.api.StateType.EDITABLE), 'ui:search-field')
            text = root.get_text_iface()
            count = self.api.Text.get_character_count(text) if text is not None else -1
            matches = (count == len(expected)
                       and self.api.Text.get_text(text, 0, count) == expected)
            self.search_status = ('query-matched' if matches else
                                  'query-mismatch-length=' + str(min(count, 256)))
            return matches
        if projection == 'web-suggestion':
            require(expected == PRODUCT, 'ui:search-binding')
            _application_id, _surface_id, registered = self.require_provider_contract(
                'gnome-shell', 'app-grid', ('web-suggestion::parent',))
            require(public_automation_id(root) == registered['web-suggestion::parent']
                    and self.find_provider_control(
                        'gnome-shell', 'app-grid', 'web-suggestion::parent') is root,
                    'ui:search-owner')
            label = 'Search "' + expected + '" on the web'
            require(len(label) <= maximum, 'ui:text-bound')
            matches = []
            for node in self.nodes(root, strict=True):
                if (node.get_role_name() == 'label' and self.showing(node)
                        and ' '.join(node.get_name().split()) == label):
                    matches.append(node)
            require(len(matches) <= 1, 'ui:ambiguous-text-projection')
            return len(matches) == 1
        if projection == 'empty-explanation':
            text = 'No interactive non-administrator account was found.'
            require(len(text) <= maximum, 'ui:text-bound')
            require(public_automation_id(root) == 'parent-no-users-message',
                    'ui:text-surface')
            return (self.showing(root) and root.get_role_name() == 'label'
                    and ' '.join(root.get_name().split()) == text)
        if projection == 'empty-picker':
            labels = []
            for node in self.nodes(root, strict=True):
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-picker')
                if node.get_role_name() == 'label' and self.showing(node):
                    text = node.get_name().strip()
                    require(len(text) <= maximum, 'ui:text-bound')
                    labels.append(text)
            return labels == ['(None)']
        if projection == 'child':
            require(expected in CHILD_IDENTITIES and len(expected) <= maximum, 'ui:child-binding')
            labels = [node.get_name() for node in self.nodes(root, strict=True)
                      if node.get_role_name() == 'label' and self.showing(node)]
            require(labels == [expected], 'ui:child-label')
            return CHILD_IDENTITIES[expected]
        import re
        labels = sorted({node.get_name() for node in self.nodes(root, strict=True)
                         if node.get_role_name() == 'label' and self.showing(node)})
        require(1 <= len(labels) <= 2 and all(len(text) <= maximum and re.fullmatch(
            r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', text) for text in labels),
            'ui:allowance-label')
        return labels

    def parent_empty(self):
        """PARENT19: fresh explanation and sole empty picker label, without input."""
        def empty():
            root = self.find_id('parent-window')
            if root is None:
                return False
            require(root.get_name() == PRODUCT, 'ui:parent-surface')
            picker = self.find_id('parent-child-selector', root=root)
            explanation = self.find_id('parent-no-users-message', root=root)
            placeholder = (self.find_id('parent-child-selected-none', root=picker)
                           if picker is not None else None)
            return (picker is not None and explanation is not None and placeholder is not None
                    and self.read_label(explanation, 'empty-explanation', maximum=80)
                    and self.read_label(picker, 'empty-picker', maximum=80))
        self.wait(empty, 'parent-empty')

    def child_id_control(self, child, prefix, *, root, showing):
        """Resolve a UID-scoped child control, then verify its public label."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
        require(prefix in ('parent-child-choice-', 'parent-child-selected-'),
                'ui:child-control-binding')
        nodes = list(self.nodes(root, strict=True))
        identities = set()
        for node in nodes:
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-picker')
            identity = public_automation_id(node)
            if re.fullmatch(re.escape(prefix) + r'[0-9]+', identity) is None:
                continue
            require(identity not in identities, 'ui:ambiguous-automation-id')
            identities.add(identity)
        node = self.snapshot_matches(
            prefix + str(uid), nodes, showing=showing, show=self.showing,
        )
        if node is not None:
            self.read_label(node, 'child', expected=child, maximum=80)
        return node

    def focus(self, node):
        """Focus one already ID-resolved public control without keyboard routing."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        identity = public_automation_id(node)
        match = re.fullmatch(r'parent-child-choice-([0-9]+)', identity)
        require(match is not None, 'ui:child-choice-id')
        current = self.find_id(identity, root=self.parent(), showing=False)
        require(current is not None and current == node, 'ui:wrong-focus-owner')
        node = current
        labels = []
        for label in CHILD_IDENTITIES:
            if self.fixture_uids is not None:
                uid = self.fixture_uids.get(label)
            else:
                try:
                    uid = pwd.getpwnam(CHILD_ACCOUNTS[label]).pw_uid
                except KeyError:
                    continue
            if uid is not None and str(uid) == match.group(1):
                labels.append(label)
        require(len(labels) == 1, 'ui:fixture-child-uid')
        self.read_label(node, 'child', expected=labels[0], maximum=80)
        require(not self.has_state(node, self.api.StateType.DEFUNCT)
                and self.has_state(node, self.api.StateType.VISIBLE)
                and self.has_state(node, self.api.StateType.SENSITIVE),
                'ui:unusable-target')
        if self.showing(node) and self.has_state(node, self.api.StateType.FOCUSED):
            return True
        self.activate_id(
            'parent-child-selector', action_name='child.focus-' + match.group(1),
        )
        self.input_uncertain = True
        def focused():
            current = self.find_id(identity)
            return (current is not None
                    and self.has_state(current, self.api.StateType.SENSITIVE)
                    and self.has_state(current, self.api.StateType.FOCUSED))
        result = self.wait(focused, 'focus')
        self.input_uncertain = False
        return result

    def open_child_picker(self, child):
        """UI15 opening: activate by ID and focus the UID-scoped choice by ID."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        self.activate_id('parent-child-selector', action_name='menu.popup')
        choices = self.id_target('parent-child-choices')
        choice = self.wait(
            lambda: self.child_id_control(
                child, 'parent-child-choice-', root=choices, showing=False,
            ),
            'child-choice',
        )
        self.focus(choice)
        return True

    def child_highlighted(self, child):
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        def highlighted():
            root = self.find_id('parent-window')
            if root is None:
                return False
            popover = self.find_id('parent-child-popover', root=root)
            if popover is None:
                return False
            choices = self.find_id('parent-child-choices', root=popover)
            if choices is None:
                return False
            choice = self.child_id_control(
                child, 'parent-child-choice-', root=choices, showing=True,
            )
            return (choice is not None
                    and self.has_state(choice, self.api.StateType.SENSITIVE)
                    and self.has_state(choice, self.api.StateType.FOCUSED))
        return self.wait(highlighted, 'choice-highlight')

    def selected_child(self, child):
        """UI15 closed-picker result followed by PARENT03, after caller's Enter."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        def closed():
            root = self.find_id('parent-window')
            if root is None:
                return False
            nodes = list(self.nodes(root, strict=True))
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in nodes), 'ui:stale-picker')
            return self.absent_id('parent-child-popover', within='parent-window')
        self.wait(closed, 'picker-close')
        return self.settings(child)

    def parent_page(self, child, page):
        """PARENT04: select the declared page and observe its usable controls."""
        require(child in CHILD_IDENTITIES and page in ('Screen Limits', 'App Limits'),
                'ui:page-binding')
        print('ui:parent-page=started', file=sys.stderr, flush=True)
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:selected-child')
        page_id = {'Screen Limits': 'parent-page-screen-limits',
                   'App Limits': 'parent-page-app-limits'}[page]
        self.activate_id(page_id)
        print('ui:parent-page=activated', file=sys.stderr, flush=True)
        if page == 'Screen Limits':
            return self.selected_child(child)
        # Reacquire once after the page transition. Local target roots can be
        # shared within this invocation; scanning the entire installed catalogue
        # again for every filter needlessly exhausts the observation deadline.
        root = self.parent()
        self.id_target('parent-app-search', root=root, sensitive=True)
        print('ui:parent-page=search-ready', file=sys.stderr, flush=True)
        self.reveal_id('parent-filter-access-rule', root=root)
        self.reveal_id('parent-filter-match-rule', root=root)
        print('ui:parent-page=filters-ready', file=sys.stderr, flush=True)

    def launchable_result(self, product):
        """SEARCH04's owned Shell launcher branch, without input."""
        require(product == PRODUCT, 'ui:search-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            owner, nodes, snapshot, facts = self.shell_search_snapshot()
            if owner is None:
                return None
            scoped = self.snapshot_scope(nodes, snapshot, owner)
            candidates = []
            for node in scoped:
                if (facts[node]['role'] not in ('button', 'push button')
                        or not facts[node]['showing']
                        or not self.has_state(node, self.api.StateType.SENSITIVE)):
                    continue
                labels = [facts[child]['name'] for child in self.snapshot_scope(
                    nodes, snapshot, node) if facts[child]['role'] == 'label'
                    and facts[child]['showing']]
                if (facts[node]['name'] == product or labels == [product]):
                    candidates.append(node)
            require(len(candidates) <= 1, 'ui:shell-result-ambiguous')
            return candidates[0] if candidates else None
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid', ('result::parent',))
        if surface is None:
            return None
        target = self.find_id(registered['result::parent'], root=surface)
        if target is None:
            return None
        require(target.get_role_name() in ('button', 'push button')
                and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:search-result')
        labels = [' '.join(node.get_name().split()) for node in self.nodes(target, strict=True)
                  if self.showing(node) and node.get_role_name() == 'label']
        require(' '.join(target.get_name().split()) == product or labels == [product],
                'ui:search-result')
        return target

    def help_desktop_clear(self):
        """Check the parent desktop after each stream read, with no product window."""
        self.standard_shell_desktop(no_prompt=True)
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        nodes = list(self.nodes(root, strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:stale-surface')
        forbidden = {'parent-window', 'parent-access-denied-window',
                     'kiosk-request-window', 'kiosk-request-form',
                     'feedback-dialog', 'startup-error-window'}
        require(not any(self.showing(node) and public_automation_id(node) in forbidden
                        for node in nodes), 'ui:help-product-window')

    def launch_parent_command(self, *, standard=False):
        """PARENT01: submit one fixed public executable as the desktop user.

        The user service manager supplies the graphical session environment.
        No shell, terminal, product API, policy write or success inference is
        involved. The journey observes the expected product window separately.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require_active_launch_session()
        self.desktop_result(EXISTING_CHILD if standard else PARENT, 'success')
        self.handle_system_prompt()
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-parent',
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        # Keep the input latch set: even a successful submission cannot be
        # repeated by this adapter instance. The next checkpoint is a new read.

    def parent_search_closed(self):
        """Independent complete window absence on the qualified Parent desktop."""
        self.standard_shell_desktop(no_prompt=True)
        _owner, nodes, _snapshot, facts = self.shell_search_snapshot()
        forbidden = {'parent-window', 'parent-access-denied-window', 'startup-error-window'}
        return not any(facts[node]['showing'] and facts[node]['identity'] in forbidden
                       for node in nodes)

    def shell_provider_metadata(self):
        """Qualification provenance only; no product state or arbitrary text."""
        from gi.repository import Gio
        owner, _nodes, _snapshot, _facts = self.shell_search_snapshot()
        require(owner is not None, 'ui:shell-provider-owner')
        pid = owner.get_process_id()
        require(type(pid) is int and pid > 0, 'ui:shell-provider-owner')
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                           if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'gnome-shell'],
            text=True, timeout=5).strip()
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        return validate_shell_metadata({'version': version, 'locale': locale,
                                        'keyboard': [list(source) for source in sources]})

    def launch_child_command(self):
        """REQUEST02 input: submit the installed child overlay command once.

        A separate form observation must establish the child and usable result.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require_active_launch_session()
        self.desktop_result(EXISTING_CHILD, 'success')
        self.handle_system_prompt()
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-child',
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)

    def parent_denial_closed(self):
        """Read the public desktop and complete absence after denial dismissal."""
        self.desktop_result(EXISTING_CHILD, 'success')
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        nodes = list(self.nodes(root, strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:stale-surface')
        forbidden = {'parent-access-denied-window', 'parent-window',
                     'parent-screen-limits-page', 'parent-app-limits-page',
                     'parent-screen-limit-toggle'}
        return not any(self.showing(node) and public_automation_id(node) in forbidden
                       for node in nodes)

    def management_denied(self):
        """FILE06: the specific visible refusal, never generic error or echo."""
        root = self.id_target('parent-access-denied-window')
        message = self.id_target('parent-access-denied-message', root=root)
        require(message.get_role_name() == 'label' and message.get_name() ==
                'Only an administrator can manage parental controls. '
                'Sign in with an administrator account to open the Parent App.',
                'ui:denial-message')
        self.id_target('parent-access-denied-close', root=root, sensitive=True)
        require(self.has_state(root, self.api.StateType.ACTIVE), 'ui:denial-not-active')
        self.management_absent()

    def management_absent(self, *, within='parent-access-denied-window'):
        """UI11: complete fresh exclusion; stale or missing trees refuse."""
        require(self.find_id(within) is not None, 'ui:missing-surrounding-surface')
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        for node in self.nodes(root, strict=True):
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-surface')
            if self.showing(node):
                require(public_automation_id(node) not in (
                    'parent-window', 'parent-screen-limits-page', 'parent-app-limits-page',
                    'parent-screen-limit-toggle'), 'ui:management-exposed')

    def search_result(self, product, expected, *, stable_seconds=2):
        """SEARCH04: observe the explicit registered result, without launching."""
        require(product == PRODUCT and expected in ('launchable', 'unavailable'),
                'ui:search-binding')
        if expected == 'launchable':
            return self.launchable_result(product)
        return self.observe_absence('overview', 'launcher-and-window', name=product,
                                    mode='stable', stable_seconds=stable_seconds)

    def desktop_result(self, account, expected):
        """GDM06 success on the caller's qualified public desktop connection."""
        require(account in (PARENT, EXISTING_CHILD) and expected == 'success',
                'ui:desktop-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            return self.standard_shell_desktop()
        surface, registered = self.provider_surface(
            'gnome-shell', 'desktop', ('desktop',))
        target = (self.find_id(registered['desktop'], root=surface)
                  if surface is not None else None)
        require(target is not None, 'ui:desktop')
        return target

    def standard_shell_desktop(self, *, no_prompt=False):
        """Shell 50 English desktop observation on the bound fixture user's bus.

        This external-provider adapter recognizes Shell's public Activities toggle;
        it authorizes no Shell input, menu, search, lock or retained-session route.
        """
        def observe():
            root = self.api.get_desktop(0)
            require(root is not None, 'ui:incomplete-tree')
            snapshot = {}
            facts = {}
            nodes = list(self.nodes(root, strict=True, protect_text=True,
                                    snapshot=snapshot, facts=facts))
            require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                            for node in nodes), 'ui:stale-surface')
            if no_prompt:
                require(self.system_prompt_kind(observation=(nodes, snapshot, facts)) is None,
                        'ui:fresh-desktop-prompt')
            owners = [node for node in nodes if node.get_parent() == root
                      and node.get_role_name() == 'application'
                      and node.get_name().casefold() in GDM_SEMANTIC_APPLICATION_NAMES]
            require(len(owners) <= 1, 'ui:shell-provider-owner')
            if not owners:
                return None
            panels = [node for node in self.snapshot_scope(nodes, snapshot, owners[0])
                      if node.get_role_name() == 'toggle button' and node.get_name() == 'Activities'
                      and self.showing(node)
                      and self.has_state(node, self.api.StateType.SENSITIVE)]
            require(len(panels) <= 1, 'ui:shell-desktop-ambiguous')
            return panels[0] if panels else None
        if not no_prompt:
            return self.wait(observe, 'shell-desktop')
        # A complete positive desktop and repeated complete prompt-free reads
        # make the declared fresh-keyring profile observable, including late
        # dialogs. No prompt input is delivered by this qualification.
        stable_since = None
        def stable():
            nonlocal stable_since
            try:
                desktop = observe()
            except Exception:
                stable_since = None
                raise
            if desktop is None:
                stable_since = None
                return None
            stable_since = stable_since or time.monotonic()
            return desktop if time.monotonic() - stable_since >= 2 else None
        return self.wait(stable, 'fresh-shell-desktop', prompt_in_predicate=True)

    def keyring_cancel_target(self):
        """Resolve the real gcr login-keyring Cancel through one complete tree."""
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(root, strict=True, protect_text=True,
                                snapshot=snapshot, facts=facts))
        kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
        require(kind in (None, 'keyring'), 'ui:keyring-prompt-replaced')
        if kind is None:
            return None
        applications = [node for node in nodes if node.get_parent() == root
                        and facts[node]['role'] == 'application'
                        and self._prompt_application_kind(facts[node]['name']) == 'keyring']
        require(len(applications) == 1, 'ui:keyring-owner')
        # GTK's application container has no window visibility state. Require
        # a live owner here and visible dialog/controls below, as for Shell.
        require(not self.has_state(applications[0], self.api.StateType.DEFUNCT),
                'ui:stale-surface')
        scopes = self.snapshot_scope(nodes, snapshot, applications[0])
        dialogs = [node for node in scopes if node is not applications[0]
                   and facts[node]['showing']
                   and (facts[node]['role'] in ('dialog', 'alert') or facts[node]['modal'])]
        require(len(dialogs) == 1
                and facts[dialogs[0]]['name'].casefold() == 'unlock login keyring',
                'ui:keyring-dialog')
        controls = self.snapshot_scope(nodes, snapshot, dialogs[0])
        fields = [node for node in controls if facts[node]['role'] == 'password text'
                  and facts[node]['showing']]
        require(len(fields) == 1 and self.has_state(fields[0], self.api.StateType.SENSITIVE)
                and self.has_state(fields[0], self.api.StateType.FOCUSED),
                'ui:keyring-focus')
        interface = fields[0].get_text_iface()
        require(interface is not None and self.api.Text.get_character_count(interface) == 0,
                'ui:keyring-secret-state')
        buttons = [node for node in controls if facts[node]['role'] in ('push button', 'button')
                   and facts[node]['name'] == 'Cancel' and facts[node]['showing']]
        require(len(buttons) == 1 and self.has_state(buttons[0], self.api.StateType.SENSITIVE),
                'ui:keyring-cancel')
        self._keyring_challenge = (applications[0], dialogs[0], fields[0], buttons[0])
        return buttons[0]

    def cancel_keyring_prompt(self):
        """Cancel once, then independently observe a stable prompt-free desktop."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.wait(self.keyring_cancel_target, 'keyring-prompt',
                           prompt_in_predicate=True)
        challenge = self._keyring_challenge
        self._invoke_target(target)
        def dismissed():
            root = self.api.get_desktop(0)
            require(root is not None, 'ui:incomplete-tree')
            snapshot, facts = {}, {}
            nodes = list(self.nodes(root, strict=True, protect_text=True,
                                    snapshot=snapshot, facts=facts))
            kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
            require(kind in (None, 'keyring'), 'ui:keyring-prompt-replaced')
            if kind == 'keyring':
                require(all(node in nodes for node in challenge),
                        'ui:keyring-prompt-replaced')
            return kind is None
        self.wait(dismissed, 'keyring-dismissed', prompt_in_predicate=True)
        self.standard_shell_desktop(no_prompt=True)

    def greeter_list(self, name=PARENT):
        """GDM01: resolve the greeter/list/account entirely by provider IDs."""
        require(name in GREETER_IDENTITIES, 'ui:gdm-account-binding')
        logical = 'account-choice::' + GREETER_IDENTITIES[name]

        def account():
            surface, registered = self.provider_surface(
                'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
            if surface is None:
                return None
            account_list = self.find_id(registered['account-list'], root=surface)
            if account_list is None:
                return None
            target = self.find_id(registered[logical], root=account_list)
            if target is None:
                return None
            names = (KIOSK, KIOSK_USERNAME) if name == KIOSK else (name,)
            require(' '.join(target.get_name().split()) in names,
                    'ui:gdm-account-label')
            return target

        target = self.wait(account, 'gdm-account-id')
        self.observe_absence('greeter', 'password', name=name, mode='snapshot')
        return target

    def gdm_nonsecret_has_id_route(self):
        """Whether G01 can use a complete public-ID route without tree reads."""
        contract = self.provider_contracts.get('gdm', {})
        surface = contract.get('surfaces', {}).get('greeter')
        if not (type(contract.get('application_id')) is str
                and contract['application_id'] and surface is not None
                and type(surface[0]) is str and surface[0]):
            return False
        registered = surface[1]
        required = ('account-list', 'account-choice::parent',
                    'account-choice::other-parent', 'account-choice::other-child',
                    'account-choice::station', 'selected-recipient', 'password')
        return all(type(registered.get(control)) is str and registered[control]
                   for control in required)

    @staticmethod
    def gdm_semantic_name(node):
        return ' '.join(node.get_name().split())

    def gdm_semantic_owner(self):
        """Resolve the one Shell application on the active greeter bus."""
        return self.gdm_semantic_nodes(protect_text=True)[0]

    def gdm_semantic_nodes(self, *, protect_text=False):
        """Resolve owner and its complete scope from the same public snapshot.

        This is the deliberately narrow provider-specific exception for G01.
        It is not a generic name/role selector: the standalone process is bound
        to the sole active local greeter account before this tree is read.
        """
        def owner():
            desktop = self.api.get_desktop(0)
            require(desktop is not None, 'ui:incomplete-tree')
            snapshot = {}
            nodes = list(self.nodes(desktop, strict=True, protect_text=protect_text,
                                    snapshot=snapshot))
            owners = [node for node in nodes
                      if node.get_parent() == desktop
                      and node.get_role_name() == 'application'
                      and self.gdm_semantic_name(node).casefold()
                      in GDM_SEMANTIC_APPLICATION_NAMES]
            require(len(owners) <= 1, 'ui:gdm-provider-owner')
            if not owners:
                return None
            return owners[0], self.snapshot_scope(nodes, snapshot, owners[0])

        # The greeter session and bus can precede Shell's public application.
        # Absence permits another read, never input or a replacement owner.
        owner, nodes = self.wait(owner, 'gdm-provider-owner')
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:gdm-stale-tree')
        return owner, nodes

    def gdm_semantic_account_rows(self, owner, nodes, names):
        """Resolve exact account labels to their GDM button ancestors."""
        rows = []
        for node in nodes:
            if not self.showing(node) or self.gdm_semantic_name(node) not in names:
                continue
            candidate = node if node.get_role_name() in GDM_ACCOUNT_ROLES else None
            if node.get_role_name() == 'label':
                current = node.get_parent()
                while current is not None and current != owner:
                    if current.get_role_name() in GDM_ACCOUNT_ROLES:
                        candidate = current
                        break
                    current = current.get_parent()
            if (candidate is not None and self.showing(candidate)
                    and candidate not in rows):
                rows.append(candidate)
        return rows

    def gdm_semantic_row_diagnostic(self, owner):
        """Return only fixed categories describing failed account matching."""
        desktop = self.api.get_desktop(0)
        all_nodes = list(self.nodes(desktop, strict=True))

        def ownership(node):
            current = node
            visited = set()
            while current is not None and current not in visited:
                if current == owner:
                    return 'provider-owner'
                visited.add(current)
                current = current.get_parent()
            return 'other-owner'

        def role(node):
            observed = node.get_role_name()
            return observed if observed in GDM_DIAGNOSTIC_ROLES else 'other'

        def matches(names):
            found = [node for node in all_nodes
                     if self.gdm_semantic_name(node) in names]
            provider_nodes = [node for node in all_nodes
                              if ownership(node) == 'provider-owner']
            roles = {}
            visibility = {'showing': 0, 'hidden': 0}
            owners = {'provider-owner': 0, 'other-owner': 0}
            for node in found:
                observed_role = role(node)
                roles[observed_role] = roles.get(observed_role, 0) + 1
                observed_visibility = 'showing' if self.showing(node) else 'hidden'
                visibility[observed_visibility] += 1
                observed_owner = ownership(node)
                owners[observed_owner] += 1
            return {
                'matching_nodes': len(found),
                'matching_rows': len(self.gdm_semantic_account_rows(
                    owner, provider_nodes, names)),
                'roles': {key: roles[key] for key in sorted(roles)},
                'visibility': visibility,
                'ownership': owners,
            }

        return {
            'event': 'gdm-account-observation',
            'owner': {
                'role': role(owner),
                'showing': self.showing(owner),
            },
            'matches': {
                'ordinary': matches((PARENT,)),
                'other-ordinary': matches((OTHER_PARENT,)),
                'standard': matches((EXISTING_CHILD,)),
                'station': matches((KIOSK, KIOSK_USERNAME)),
            },
        }

    def gdm_semantic_rows(self, expected, *, excluded=()):
        """Return declared fixture rows from one complete account-list snapshot."""
        require(type(expected) is tuple and expected
                and len(set(expected)) == len(expected)
                and set(expected) <= {PARENT, OTHER_PARENT, EXISTING_CHILD, KIOSK}
                and type(excluded) is tuple
                and len(set(excluded)) == len(excluded)
                and set(excluded) <= {PARENT, OTHER_PARENT, EXISTING_CHILD, KIOSK}
                and not set(expected) & set(excluded),
                'ui:gdm-account-binding')
        owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        require(not any(node.get_role_name() == 'password text' for node in showing),
                'ui:gdm-list-prompt-overlap')

        bindings = {
            PARENT: (PARENT,),
            OTHER_PARENT: (OTHER_PARENT,),
            EXISTING_CHILD: (EXISTING_CHILD,),
            KIOSK: (KIOSK, KIOSK_USERNAME),
        }
        identities = (*expected, *excluded)
        rows = {name: self.gdm_semantic_account_rows(
            owner, showing, bindings[name]) for name in identities}
        expected_rows = {name: rows[name] for name in expected}
        complete = (all(len(matches) == 1 for matches in expected_rows.values())
                    and len({matches[0] for matches in expected_rows.values()})
                    == len(expected_rows))
        if excluded:
            complete = complete and all(not rows[name] for name in excluded)
        if not complete and not self.gdm_row_diagnostic_emitted:
            print(json.dumps(self.gdm_semantic_row_diagnostic(owner), sort_keys=True),
                  file=sys.stderr, flush=True)
            self.gdm_row_diagnostic_emitted = True
        require(complete, 'ui:gdm-account-cardinality')
        result = {name: matches[0] for name, matches in expected_rows.items()}
        for row in result.values():
            require(self.has_state(row, self.api.StateType.SENSITIVE),
                    'ui:gdm-account-unavailable')
        return owner, result

    def gdm_nonsecret_account(self, name):
        require(name in (PARENT, OTHER_PARENT, EXISTING_CHILD, KIOSK),
                'ui:gdm-nonsecret-binding')
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_list(name)
        expected = tuple(dict.fromkeys((PARENT, KIOSK, name)))
        _owner, rows = self.gdm_semantic_rows(expected)
        return rows[name]

    def gdm_product_free_account(self):
        """Resolve case 1's declared Parent row while proving station absence."""
        require(not self.gdm_nonsecret_has_id_route(),
                'ui:gdm-product-free-binding')
        _owner, rows = self.gdm_semantic_rows((PARENT,), excluded=(KIOSK,))
        return rows[PARENT]

    def gdm_nonsecret_navigation(self, name):
        """Focus one fresh G01 row without deriving input from list position."""
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_navigation(name)
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.gdm_nonsecret_account(name)
        if self.has_state(target, self.api.StateType.FOCUSED):
            return True
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')

        def focused():
            refreshed = self.gdm_nonsecret_account(name)
            require(refreshed == target, 'ui:gdm-stale-focus')
            return self.has_state(refreshed, self.api.StateType.FOCUSED)

        self.wait(focused, 'gdm-account-focus')
        self.input_uncertain = False
        return True

    def gdm_product_free_navigation(self):
        """Focus case 1's fresh Parent row without accepting another binding."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.gdm_product_free_account()
        if self.has_state(target, self.api.StateType.FOCUSED):
            return True
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')

        def focused():
            refreshed = self.gdm_product_free_account()
            require(refreshed == target, 'ui:gdm-stale-focus')
            return self.has_state(refreshed, self.api.StateType.FOCUSED)

        self.wait(focused, 'gdm-account-focus')
        self.input_uncertain = False
        return True

    def kiosk_gdm_returned(self):
        """Observe the exited station's usable greeter and absent owned UI."""
        self.gdm_semantic_rows((PARENT, KIOSK))
        nodes = list(self.nodes(strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:gdm-stale-tree')
        forbidden = {
            KIOSK_APPLICATION, 'kiosk-request-window', 'kiosk-request-form',
            'feedback-dialog', 'startup-error-window',
            'error-report-unavailable-dialog',
        }
        require(not any(public_automation_id(node) in forbidden and self.showing(node)
                        for node in nodes), 'ui:kiosk-exit-incomplete')

    def gdm_semantic_prompt(self):
        """Resolve one prepared prompt without traversing its protected field."""
        owner, nodes = self.gdm_semantic_nodes(protect_text=True)
        showing = [node for node in nodes if self.showing(node)]
        account_rows = self.gdm_semantic_account_rows(
            owner, showing, tuple(GREETER_IDENTITIES))
        require(not account_rows, 'ui:gdm-list-prompt-overlap')
        recipients = [node for node in showing
                      if node.get_role_name() == 'label'
                      and self.gdm_semantic_name(node)
                      in (PARENT, OTHER_PARENT, EXISTING_CHILD)]
        fields = [node for node in showing
                  if node.get_role_name() == 'password text']
        require(len(recipients) == 1, 'ui:gdm-recipient')
        require(len(fields) == 1
                and self.has_state(fields[0], self.api.StateType.SENSITIVE)
                and self.has_state(fields[0], self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')
        return self.gdm_semantic_name(recipients[0]), fields[0]

    def gdm_nonsecret_prompt(self):
        """Observe Parent's prompt without reading or authorizing its secret."""
        self.greeter_prompt()

    def station_entry_branch(self, owner):
        """Read the offered branch without selecting or dismissing any control."""
        require(owner in ('greeter', 'station'), 'ui:station-branch-owner')
        if owner == 'station':
            def destination():
                snapshot = {}
                identities = {}
                nodes = list(self.nodes(
                    strict=True, snapshot=snapshot, identities=identities))
                require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                for node in nodes), 'ui:station-stale-tree')
                observation = (nodes, snapshot, identities, None)
                window = self.snapshot_owned_target(
                    'kiosk-request-window', observation=observation)
                if window is None:
                    return None
                form = self.snapshot_owned_target(
                    'kiosk-request-form', root=window, observation=observation)
                if form is None:
                    return None
                return {'destination': 'default-request-form', 'controls': []}
            return self.wait(destination, 'station-default-destination')
        _owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        recipients = [node for node in showing if node.get_role_name() == 'label'
                      and self.gdm_semantic_name(node) in (KIOSK, KIOSK_USERNAME)]
        require(len(recipients) == 1, 'ui:station-branch-recipient')
        require(not any(node.get_role_name() == 'password text' for node in showing),
                'ui:station-unexpected-password')
        roles = {'button', 'push button', 'toggle button', 'radio button',
                 'menu item', 'radio menu item', 'check menu item', 'combo box'}
        controls = []
        for node in showing:
            role = node.get_role_name()
            if role not in roles:
                continue
            label = GDM_SESSION_LABELS.get(self.gdm_semantic_name(node), 'unresolved')
            controls.append({'label': label, 'role': role,
                             'public_id_present': bool(public_automation_id(node)),
                             'sensitive': self.has_state(node, self.api.StateType.SENSITIVE),
                             'focused': self.has_state(node, self.api.StateType.FOCUSED)})
        require(0 < len(controls) <= 12, 'ui:station-branch-controls')
        known = [control['label'] for control in controls if control['label'] != 'unresolved']
        require(len(known) == len(set(known)), 'ui:station-branch-ambiguous')
        return {'destination': 'greeter-controls', 'controls': controls}

    def station_default_entry(self, owner):
        """Read back the one qualified passwordless default-session result."""
        require(owner == 'station', 'ui:station-default-branch')

        def destination():
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                            for node in nodes), 'ui:station-stale-tree')
            observation = (nodes, snapshot, identities, None)
            window = self.snapshot_owned_target(
                'kiosk-request-window', observation=observation)
            if window is None:
                return None
            require(self.showing(window), 'ui:station-default-window')
            form = self.snapshot_owned_target(
                'kiosk-request-form', root=window, observation=observation)
            if form is None:
                return None
            require(self.showing(form), 'ui:station-default-form')
            return {'destination': 'default-request-form'}

        return self.wait(destination, 'station-default-destination')

    def observe_absence(self, surface, target, *, name, mode, stable_seconds=None):
        """UI11: registered positive surfaces and complete fresh exclusion reads."""
        if surface == 'overview':
            require(target == 'launcher-and-window' and name == PRODUCT and mode == 'stable'
                    and type(stable_seconds) in (int, float) and 0 < stable_seconds <= 10,
                    'ui:absence-binding')
            return self.search_absence(name, stable_seconds=stable_seconds)
        require(stable_seconds is None, 'ui:absence-binding')
        if surface == 'parent':
            require(target == 'child-popup' and name in CHILD_IDENTITIES
                    and mode == 'snapshot', 'ui:absence-binding')
            def closed():
                root = self.parent()
                picker = self.id_target('parent-child-selector', root=root, sensitive=True)
                if self.child_id_control(name, 'parent-child-selected-',
                                         root=picker, showing=True) is None:
                    return False
                nodes = list(self.nodes(root, strict=True))
                return (not any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes)
                        and self.absent_id('parent-child-popover', within='parent-window'))
            return self.wait(closed, 'picker-close')
        require(surface == 'greeter' and target in ('password', 'account')
                and name in GREETER_IDENTITIES and mode == 'snapshot', 'ui:absence-binding')

        def absent():
            account_control = 'account-choice::' + GREETER_IDENTITIES[name]
            positive_control = account_control if target == 'password' else 'selected-recipient'
            absent_control = 'password' if target == 'password' else 'account-list'
            surface_root, registered = self.provider_surface(
                'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
            if surface_root is None:
                return False
            nodes = list(self.nodes(surface_root, strict=True))
            positive = self.find_id(registered[positive_control], nodes=nodes)
            if positive is None:
                return False
            if target == 'account':
                require(' '.join(positive.get_name().split()) == name,
                        'ui:gdm-recipient')
            for node in nodes:
                if self.has_state(node, self.api.StateType.DEFUNCT):
                    return False
            absent = self.find_id(registered[absent_control], nodes=nodes, showing=False)
            return absent is None or not self.showing(absent)

        return self.wait(absent, 'gdm-prompt-dismissed' if target == 'password' else 'gdm-list-hidden')

    def choice_order(self, root, *, identities, maximum, cardinality, projection):
        """UI13: fresh complete collection, returning only canonical identities.

        Rows may be outside the viewport in a scrolling account list. Their
        order is readable; the separate focus checkpoint qualifies the input.
        """
        require(root is not None and type(maximum) is int and 1 <= maximum <= 32
                and type(cardinality) is tuple and len(cardinality) == 2
                and 0 <= cardinality[0] <= cardinality[1] <= maximum
                and identities == CHILD_IDENTITIES and projection == 'child-picker-order',
                'ui:collection-binding')
        choices = []
        if projection == 'child-picker-order':
            require(public_automation_id(root) == 'parent-child-choices',
                    'ui:child-collection-surface')
            require(self.find_id('parent-child-choices', showing=False) == root,
                    'ui:wrong-collection-owner')
            bindings = {}
            for label, canonical in CHILD_IDENTITIES.items():
                if self.fixture_uids is not None:
                    if label not in self.fixture_uids:
                        continue  # The new account may not have been created yet.
                    uid = self.fixture_uids[label]
                else:
                    try:
                        uid = pwd.getpwnam(CHILD_ACCOUNTS[label]).pw_uid
                    except KeyError:
                        continue
                require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
                identity = 'parent-child-choice-' + str(uid)
                require(identity not in bindings, 'ui:duplicate-choice-identity')
                bindings[identity] = (label, canonical)
            for node in self.nodes(root, strict=True):
                require(not self.has_state(node, self.api.StateType.DEFUNCT),
                        'ui:stale-collection')
                identity = public_automation_id(node)
                if re.fullmatch(r'parent-child-choice-[0-9]+', identity) is None:
                    continue
                require(identity in bindings, 'ui:unregistered-child-choice')
                label, canonical = bindings[identity]
                self.read_label(node, 'child', expected=label, maximum=80)
                require(canonical not in choices, 'ui:duplicate-choice-identity')
                choices.append(canonical)
                require(len(choices) <= maximum, 'ui:collection-bound')
            require(cardinality[0] <= len(choices) <= cardinality[1],
                    'ui:collection-cardinality')
            return tuple(choices)
    def greeter_navigation(self, name):
        """Focus one ID-addressed row without calculating input from list order."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.fresh_owned_target(self.greeter_list(name))
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')
        self.wait(lambda: self.has_state(self.greeter_list(name), self.api.StateType.FOCUSED),
                  'gdm-account-focus')
        self.input_uncertain = False
        return True

    def greeter_prompt(self, name=PARENT):
        # This observation submits no secret and cannot authorize one.
        require(name in (PARENT, OTHER_PARENT), 'ui:gdm-account-binding')
        if not self.gdm_nonsecret_has_id_route():
            recipient, _field = self.gdm_semantic_prompt()
            require(recipient == name, 'ui:gdm-recipient')
            return
        surface, registered = self.provider_surface(
            'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
        require(surface is not None, 'ui:gdm-surface')
        recipient = self.find_id(registered['selected-recipient'], root=surface)
        require(recipient is not None and ' '.join(recipient.get_name().split()) == name,
                'ui:gdm-recipient')
        self.observe_absence('greeter', 'account', name=name, mode='snapshot')
        field = self.find_id(registered['password'], root=surface)
        require(field is not None and field.get_role_name() == 'password text'
                and self.has_state(field, self.api.StateType.SENSITIVE)
                and self.has_state(field, self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')

    def kiosk_request_form(self, *, enabled=False, expected_selection=None, no_child=False):
        """Read REQUEST03's default-duration station state after accounts load."""
        require(type(enabled) is bool, 'ui:kiosk-enabled-binding')
        require(type(no_child) is bool and (not no_child or (
                not enabled and expected_selection is None)), 'ui:kiosk-profile-binding')
        require(expected_selection is None or (type(expected_selection) is tuple and len(expected_selection) == 2
                and expected_selection[0] in ('child', 'approver')
                and expected_selection[1] in (CHILD_IDENTITIES if expected_selection[0] == 'child'
                                   else APPROVER_IDENTITIES).values()),
                'ui:kiosk-selected-binding')
        last_reset = None
        diagnostic = KioskDiagnostic()
        self.kiosk_diagnostic = diagnostic
        diagnostic.emit()

        def lookup(identity, nodes, identities, *, showing=True, emit=True):
            if emit:
                diagnostic.emit(identity)
            diagnostic.check()
            matches = [node for node in nodes if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if not matches or (showing and not self.showing(matches[0])):
                return None
            return matches[0]

        def fresh_reader():
            nonlocal last_reset
            now = time.monotonic()
            if self.reset_observer is not None and (last_reset is None or now - last_reset >= 2):
                # Drop only this reader's stale accessibility objects when the
                # graphical session changes. Never start or inspect services.
                diagnostic.emit('reset-reader')
                self.invalidate_observation()
                self.reset_observer()
                last_reset = now

        def observe():
            diagnostic.tree = 'unread'
            diagnostic.ids = {}
            diagnostic.emit('public-tree')
            try:
                snapshot = {}
                public_nodes = list(self.nodes(strict=True, snapshot=snapshot))
                diagnostic.emit('public-ids')
                counts = dict.fromkeys(KIOSK_DIAGNOSTIC_IDS, 0)
                identity_by_node = {}
                for node in public_nodes:
                    diagnostic.check()
                    identity = public_automation_id(node)
                    identity_by_node[node] = identity
                    if identity in counts:
                        counts[identity] += 1
                diagnostic.ids = counts
                diagnostic.tree = 'complete'
            except self.query_errors:
                diagnostic.tree = 'incomplete'
                diagnostic.query_errors += 1
                diagnostic.emit(status='query-error')
                fresh_reader()
                return None
            except UiError:
                diagnostic.tree = 'incomplete'
                raise

            application = lookup(KIOSK_APPLICATION, public_nodes, identity_by_node,
                                 showing=False)
            if application is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None

            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                require(KIOSK_APPLICATION in requested, 'ui:wrong-application-owner')
            if self.owner_pids is not None:
                require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
            if self.application_owners is not None:
                owners = self.application_owners()
                require(application.get_process_id() in owners.get(KIOSK_APPLICATION, ()),
                        'ui:wrong-application-owner')

            application_nodes = self.snapshot_scope(public_nodes, snapshot, application)
            window = lookup('kiosk-request-window', application_nodes, identity_by_node)
            if window is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None
            self.validate_owned_surface(window, application)
            window_nodes = self.snapshot_scope(public_nodes, snapshot, window)
            form = lookup('kiosk-request-form', window_nodes, identity_by_node)
            if form is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None

            # A matching ID in another window must never fill a missing field
            # in this form. Keep a complete fresh read for absence checks too.
            diagnostic.emit('form-tree')
            form_nodes = self.snapshot_scope(public_nodes, snapshot, form)
            diagnostic.emit('form-states')
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in form_nodes), 'ui:stale-request-form')
            child = lookup('kiosk-child-selector', form_nodes, identity_by_node)
            approver = lookup('kiosk-approver-selector', form_nodes, identity_by_node)
            request = lookup('kiosk-request-submit', form_nodes, identity_by_node)
            cancel = lookup('kiosk-request-cancel', form_nodes, identity_by_node)
            allow_soft = lookup('kiosk-soft-apps-toggle', form_nodes, identity_by_node)
            if None in (child, approver, request, cancel, allow_soft):
                return None

            def selected_identity(control, label, canonical_identities, code):
                namespace = 'child' if canonical_identities == CHILD_IDENTITIES else 'approver'
                diagnostic.emit('selected-' + namespace)
                accounts = CHILD_ACCOUNTS if namespace == 'child' else APPROVER_ACCOUNTS
                control_nodes = self.snapshot_scope(public_nodes, snapshot, control)
                selected_nodes = [node for node in control_nodes
                                  if identity_by_node[node].startswith(
                                      f'kiosk-{namespace}-selected-')
                                  and self.showing(node)]
                require(len(selected_nodes) == 1, 'ui:' + code)
                selected = []
                for name, canonical in canonical_identities.items():
                    if self.fixture_uids is not None:
                        uid = self.fixture_uids.get(name)
                        if uid is None:
                            continue
                    else:
                        try:
                            uid = pwd.getpwnam(accounts[name]).pw_uid
                        except KeyError:
                            continue
                    require(type(uid) is int and uid >= 1000, 'ui:fixture-account-uid')
                    node = lookup(f'kiosk-{namespace}-selected-{uid}',
                                  control_nodes, identity_by_node, emit=False)
                    if node is not None and node == selected_nodes[0]:
                        selected.append((name, canonical))
                require(len(selected) == 1, 'ui:' + code)
                name, canonical = selected[0]
                control.clear_cache_single()
                description = ' '.join(control.get_description().split())
                if description != f'Selected {label.casefold()}: {name}.':
                    # The selected label ID and the trigger description are
                    # published separately. Read both again after the update.
                    return None
                return canonical

            duration_ids = (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')
            durations = [
                lookup(f'kiosk-duration-{identity}', form_nodes, identity_by_node)
                for identity in duration_ids
            ]
            if any(button is None for button in durations):
                return None
            diagnostic.emit('duration-states')
            selected = [index for index, button in enumerate(durations)
                        if self.has_state(button, self.api.StateType.PRESSED)]
            require(selected == [2], 'ui:kiosk-duration-selection')
            if enabled:
                if not all(self.has_state(button, self.api.StateType.SENSITIVE)
                           for button in durations):
                    return None
            else:
                require(not any(self.has_state(button, self.api.StateType.SENSITIVE)
                                for button in durations), 'ui:kiosk-duration-availability')

            notice = lookup('kiosk-screen-limit-notice', form_nodes, identity_by_node)
            if enabled and notice is not None:
                return None
            if not enabled and not no_child and notice is None:
                return None
            diagnostic.emit('message')
            if no_child:
                status = lookup('kiosk-request-status', form_nodes, identity_by_node, emit=False)
                if status is None or ' '.join(status.get_name().split()) in (
                        'Loading accounts…', 'Loading request details…'):
                    return None
                require(' '.join(status.get_name().split()) ==
                        'No local standard accounts are available. Create one, then reopen this screen.',
                        'ui:kiosk-no-child-message')
                # Include hidden choices: an empty selection alone does not
                # prove the form's complete offered child set is empty.
                require(not any(identity_by_node[node].startswith('kiosk-child-choice-')
                                for node in form_nodes), 'ui:kiosk-no-child-choices')
                control_nodes = self.snapshot_scope(public_nodes, snapshot, child)
                selected = [node for node in control_nodes if identity_by_node[node].startswith(
                    'kiosk-child-selected-')]
                require(len(selected) == 1 and identity_by_node[selected[0]] ==
                        'kiosk-child-selected-none', 'ui:kiosk-no-child-selection')
            elif not enabled:
                message = ' '.join(notice.get_name().split())
                require(message == 'Screen limit is not enabled in Parent App',
                        'ui:kiosk-disabled-message')
            custom = lookup('kiosk-custom-duration', form_nodes, identity_by_node)
            require(lookup('kiosk-mute-button', window_nodes, identity_by_node) is None,
                    'ui:kiosk-mute-present')
            diagnostic.emit('projection')
            projection = {
                'surface': 'kiosk', 'form_count': 1,
                'child': 'none' if no_child else selected_identity(
                    child, 'Child account', CHILD_IDENTITIES, 'kiosk-child'),
                'approver': selected_identity(
                    approver, 'Approving parent', APPROVER_IDENTITIES,
                    'kiosk-approver'),
                'duration_seconds': 1800,
                'custom_text': None if custom is None else 'unexpected-visible-value',
                'allow_soft': self.has_state(allow_soft, self.api.StateType.CHECKED),
                'child_selector_enabled': self.has_state(child, self.api.StateType.SENSITIVE),
                'approver_selector_enabled': self.has_state(approver, self.api.StateType.SENSITIVE),
                'duration_enabled': enabled,
                'soft_choice_enabled': self.has_state(allow_soft, self.api.StateType.SENSITIVE),
                'request_enabled': self.has_state(request, self.api.StateType.SENSITIVE),
                'cancel_enabled': self.has_state(cancel, self.api.StateType.SENSITIVE),
                'message': 'no-child' if no_child else (
                    '' if enabled else 'screen-limit-disabled'), 'mute': None,
            }
            if projection['child'] is None or projection['approver'] is None:
                return None
            if expected_selection is not None and projection[expected_selection[0]] != expected_selection[1]:
                return None
            return projection
        try:
            result = self.wait(observe, 'kiosk-request-form')
            diagnostic.emit(status='passed')
            return result
        except BaseException:
            diagnostic.emit(status='failed')
            raise
        finally:
            self.kiosk_diagnostic = None

    def kiosk_account_snapshot(self, field):
        """One complete owned snapshot for a station account input boundary."""
        require(field in ('child', 'approver'), 'ui:kiosk-account-field')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(strict=True, snapshot=snapshot, facts=facts))
        identities = {node: facts[node]['identity'] for node in nodes}
        require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in nodes), 'ui:stale-request-form')
        observation = (nodes, snapshot, identities, facts)
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        window = self.snapshot_owned_target('kiosk-request-window', observation=observation)
        require(window is not None, 'ui:kiosk-account-surface')
        form = self.snapshot_owned_target(
            'kiosk-request-form', root=window, observation=observation)
        require(form is not None, 'ui:kiosk-account-surface')
        selector = self.snapshot_owned_target(
            f'kiosk-{field}-selector', root=form, showing=False, observation=observation)
        require(selector is not None and self.has_state(selector, self.api.StateType.VISIBLE)
                and self.has_state(selector, self.api.StateType.SENSITIVE),
                'ui:kiosk-account-unavailable')
        return selector, form, observation

    def select_kiosk_account(self, field, name, *, expected, enabled=True, inspect_only=False):
        """UI15: inspect the exact offered set, optionally select and read back."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(type(enabled) is bool, 'ui:kiosk-enabled-binding')
        require(type(inspect_only) is bool, 'ui:kiosk-inspection-binding')
        require(field in ('child', 'approver'), 'ui:kiosk-account-field')
        accounts = CHILD_ACCOUNTS if field == 'child' else APPROVER_ACCOUNTS
        require(type(expected) is tuple and len(expected) == len(set(expected))
                and set(expected) <= set(accounts) and name in expected,
                'ui:kiosk-account-choice')
        bindings = {}
        for label in expected:
            uid = (self.fixture_uids.get(label) if self.fixture_uids is not None
                   else pwd.getpwnam(accounts[label]).pw_uid)
            require(type(uid) is int and uid >= 1000, 'ui:fixture-account-uid')
            identity = f'kiosk-{field}-choice-{uid}'
            require(identity not in bindings, 'ui:duplicate-choice-identity')
            bindings[identity] = label
        selector, form, observation = self.kiosk_account_snapshot(field)
        if inspect_only:
            require(self.snapshot_owned_target(
                f'kiosk-{field}-choices', root=form, observation=observation) is None,
                'ui:kiosk-choices-already-open')
        self._invoke_target(selector)
        if inspect_only:
            self.input_uncertain = True
        self.invalidate_observation()

        def offered():
            _selector, form, observation = self.kiosk_account_snapshot(field)
            nodes, snapshot, identities, _facts = observation
            choices = self.snapshot_owned_target(
                f'kiosk-{field}-choices', root=form, observation=observation)
            if choices is None:
                return None
            scope = self.snapshot_scope(nodes, snapshot, choices)
            found = {}
            for node in scope:
                identity = identities[node]
                if not identity.startswith(f'kiosk-{field}-choice-'):
                    continue
                require(identity in bindings and identity not in found,
                        'ui:kiosk-eligible-set')
                require(self.has_state(node, self.api.StateType.VISIBLE)
                        and self.has_state(node, self.api.StateType.SENSITIVE),
                        'ui:kiosk-account-unavailable')
                label = 'Child account' if field == 'child' else 'Approving parent'
                require(' '.join(node.get_name().split()) == f'{label}: {bindings[identity]}',
                        'ui:kiosk-choice-label')
                found[identity] = node
            require(set(found) == set(bindings), 'ui:kiosk-eligible-set')
            if inspect_only:
                return True
            return next(found[identity] for identity in found if bindings[identity] == name)

        target = self.wait(offered, 'kiosk-offered-accounts', prompt_in_predicate=True)
        if inspect_only:
            self.input_uncertain = False
            return None
        self._invoke_target(target)
        self.input_uncertain = True
        self.invalidate_observation()
        canonical = CHILD_IDENTITIES if field == 'child' else APPROVER_IDENTITIES
        result = self.kiosk_request_form(enabled=enabled, expected_selection=(field, canonical[name]))
        self.input_uncertain = False
        return result

    def collapse_kiosk_child_choices(self):
        """Collapse the inline list once and independently read the whole form."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        # GatewayDropDown is an inline list, not a popup. Its public trigger
        # collapses it; Escape is the whole form's Cancel action.
        selector, form, observation = self.kiosk_account_snapshot('child')
        require(self.snapshot_owned_target(
            'kiosk-child-choices', root=form, observation=observation) is not None,
            'ui:kiosk-choices-not-open')
        self._invoke_target(selector)
        self.input_uncertain = True
        self.invalidate_observation()

        def closed():
            _selector, form, observation = self.kiosk_account_snapshot('child')
            return self.snapshot_owned_target(
                'kiosk-child-choices', root=form, observation=observation) is None

        self.wait(closed, 'kiosk-choices-closed', prompt_in_predicate=True)
        result = self.kiosk_request_form()
        self.input_uncertain = False
        return result

    def kiosk_exit_target(self, *, with_window=False):
        """Resolve the fresh owned Cancel control inside one showing form."""
        snapshot = {}
        facts = {}
        nodes = list(self.nodes(strict=True, snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:stale-request-form')
        identities = {node: facts[node]['identity'] for node in nodes}
        self.handle_system_prompt(observation=(nodes, snapshot, facts))

        def lookup(identity, scope, *, showing=True):
            matches = [node for node in scope if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if not matches or (showing and not self.showing(matches[0])):
                return None
            return matches[0]

        # Resolve this observation from its complete scoped snapshot. Generic
        # find_id re-traverses ownership trees even when supplied these nodes.
        application = lookup(KIOSK_APPLICATION, nodes, showing=False)
        require(application is not None, 'ui:kiosk-application')
        requested = (self.application_ids() if callable(self.application_ids)
                     else self.application_ids)
        if requested is not None:
            require(KIOSK_APPLICATION in requested, 'ui:wrong-application-owner')
        if self.owner_pids is not None:
            require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
        if self.application_owners is not None:
            owners = self.application_owners()
            require(application.get_process_id() in owners.get(KIOSK_APPLICATION, ()),
                    'ui:wrong-application-owner')
        application_nodes = self.snapshot_scope(nodes, snapshot, application)
        window = lookup('kiosk-request-window', application_nodes)
        require(window is not None, 'ui:kiosk-request-window')
        self.validate_owned_surface(
            window, application, nodes=nodes, snapshot=snapshot, identities=identities,
        )
        window_nodes = self.snapshot_scope(nodes, snapshot, window)
        form = lookup('kiosk-request-form', window_nodes)
        require(form is not None, 'ui:kiosk-request-form')
        form_nodes = self.snapshot_scope(nodes, snapshot, form)
        target = lookup('kiosk-request-cancel', form_nodes)
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:kiosk-request-cancel')
        return (window, target) if with_window else target

    def cancel_kiosk_request(self):
        """UI04: activate Cancel once after refusing any system prompt."""
        # The station's scoped public action is explicitly authorized even
        # when its Cancel control is clipped by the scroll viewport.
        target = self.kiosk_exit_target()
        self._invoke_target(target)

    def focus_kiosk_escape_recipient(self):
        """UI05: focus and freshly recheck the owned recipient before Escape."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        window, target = self.kiosk_exit_target(with_window=True)
        identity = public_automation_id(target)
        require(self.has_state(window, self.api.StateType.SENSITIVE), 'ui:unusable-target')
        action = window.get_action_iface()
        require(action is not None, 'ui:missing-action')
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                message=r'^Atspi\.Action\.get_action_name is deprecated$',
                category=DeprecationWarning)
            matches = [index for index in range(self.api.Action.get_n_actions(action))
                       if self.api.Action.get_action_name(action, index) == 'focus.' + identity]
        require(len(matches) == 1, 'ui:missing-or-ambiguous-action')
        self.input_uncertain = True
        require(self.api.Action.do_action(action, matches[0]), 'ui:action-refused')

        def focused():
            current = self.kiosk_exit_target()
            require(current == target, 'ui:kiosk-exit-stale-focus')
            return self.has_state(current, self.api.StateType.FOCUSED)

        # kiosk_exit_target checks prompts in every fresh predicate snapshot.
        self.wait(focused, 'kiosk-exit-focus', prompt_in_predicate=True)
        self.input_uncertain = False

    def password_recipient(self, name):
        """Read only public identity, masked role, focus and empty length.

        Never read password text or children. A false/stale observation cannot
        authorize typing. The caller also requires a separate fresh recheck.
        """
        require(name in GREETER_IDENTITIES, 'ui:gdm-account-binding')
        if not self.gdm_nonsecret_has_id_route():
            require(name in (PARENT, OTHER_PARENT, EXISTING_CHILD),
                    'ui:gdm-nonsecret-binding')
            recipient, field = self.gdm_semantic_prompt()
            if recipient != name:
                return False
            interface = field.get_text_iface()
            return (interface is not None
                    and self.api.Text.get_character_count(interface) == 0)
        surface, registered = self.provider_surface(
            'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
        if surface is None:
            return False
        recipient = self.find_id(registered['selected-recipient'], root=surface)
        field = self.find_id(registered['password'], root=surface)
        account_list = self.find_id(registered['account-list'], root=surface, showing=False)
        if (recipient is None or ' '.join(recipient.get_name().split()) != name
                or field is None or field.get_role_name() != 'password text'
                or not self.has_state(field, self.api.StateType.SENSITIVE)
                or not self.has_state(field, self.api.StateType.FOCUSED)
                or (account_list is not None and self.showing(account_list))):
            return False
        interface = field.get_text_iface()
        return interface is not None and self.api.Text.get_character_count(interface) == 0

    def search_query(self, expected):
        """Read only the overview's public search field; never arbitrary text."""
        require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal'), 'ui:search-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            field = self.shell_search_field()
            if field is None:
                return False
            return self.shell_query_matches(field, expected)
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid', ('search',))
        self.search_status = 'surface-missing'
        if surface is None:
            return False
        field = self.find_id(registered['search'], root=surface)
        self.search_status = 'field-missing'
        if field is None:
            return False
        if (field.get_role_name() not in ('text', 'entry')
                or not self.has_state(field, self.api.StateType.SENSITIVE)
                or not self.has_state(field, self.api.StateType.EDITABLE)):
            self.search_status = 'field-unusable'
            return False
        return self.read_label(field, 'search-query', expected=expected, maximum=80)

    def shell_query_matches(self, field, expected):
        """Read the field from the caller's fresh scoped Shell observation."""
        require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal'), 'ui:search-binding')
        text = field.get_text_iface()
        require(text is not None, 'ui:search-text-unavailable')
        count = self.api.Text.get_character_count(text)
        require(0 <= count <= 80, 'ui:search-text-bound')
        matches = (count == len(expected)
                   and self.api.Text.get_text(text, 0, count) == expected)
        self.search_status = ('query-matched' if matches else
                              'query-mismatch-length=' + str(count))
        return matches

    def shell_search_snapshot(self):
        """Shell 50 Overview adapter; semantics stay inside this provider scope.

        Shell exposes no usable public IDs on the pinned image. A complete fresh
        tree binds the one direct desktop application owner before inspecting its
        search controls. Names never select an application outside that owner.
        """
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(root, strict=True, protect_text=True,
                                snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        owners = [node for node in snapshot[root]
                  if facts[node]['role'] == 'application'
                  and facts[node]['name'].casefold() in GDM_SEMANTIC_APPLICATION_NAMES]
        require(len(owners) <= 1, 'ui:shell-provider-owner')
        return (owners[0] if owners else None), nodes, snapshot, facts

    def shell_search_field(self):
        owner, nodes, snapshot, facts = self.shell_search_snapshot()
        self.search_status = 'shell-owner-missing'
        if owner is None:
            return None
        fields = [node for node in self.snapshot_scope(nodes, snapshot, owner)
                  if facts[node]['role'] in ('text', 'entry')
                  and facts[node]['showing']
                  and self.has_state(node, self.api.StateType.SENSITIVE)
                  and self.has_state(node, self.api.StateType.EDITABLE)]
        require(len(fields) <= 1, 'ui:shell-search-ambiguous')
        self.search_status = 'shell-field-missing' if not fields else 'shell-field-identified'
        return fields[0] if fields else None

    def search_ready(self, surface, *, focused=False):
        """SEARCH01/UI21: read the empty field, optionally its independent focus."""
        require(surface == 'overview' and type(focused) is bool, 'ui:search-binding')
        def ready():
            if not self.search_query(''):
                return False
            if not self.provider_contracts['gnome-shell']['application_id']:
                field = self.shell_search_field()
            else:
                surface, registered = self.provider_surface(
                    'gnome-shell', 'app-grid', ('search',))
                field = (self.find_id(registered['search'], root=surface)
                         if surface is not None else None)
            return field if field is not None and (not focused or self.has_state(
                field, self.api.StateType.FOCUSED)) else False
        return self.wait_search(ready, 'standard-search-focus' if focused else 'standard-search-ready')

    def focus_search_field(self):
        """Focus the scoped provider search field without pointer geometry."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        if not self.provider_contracts['gnome-shell']['application_id']:
            field = self.wait(self.shell_search_field, 'search-field', prompt_in_predicate=True)
        else:
            field = self.wait(
                lambda: self.snapshot_provider_target(
                    'gnome-shell', 'app-grid', 'search', check_prompt=True),
                'search-field', prompt_in_predicate=True,
            )
        require(field is not None and self.has_state(field, self.api.StateType.SENSITIVE),
                'ui:search-field')
        component = field.get_component_iface()
        require(component is not None, 'ui:search-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:search-focus-refused')
        def focused():
            current = (self.shell_search_field()
                       if not self.provider_contracts['gnome-shell']['application_id'] else
                       self.find_provider_control('gnome-shell', 'app-grid', 'search'))
            return current is not None and self.has_state(
                current, self.api.StateType.FOCUSED)
        self.wait(focused, 'standard-search-focus')
        self.input_uncertain = False

    def focus_search_result(self):
        """Qualify the exact launcher recipient before the worker sends Enter."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        self.wait(lambda: self.search_query(PRODUCT), 'parent-search-query')
        target = self.wait(lambda: self.launchable_result(PRODUCT), 'parent-search-result')
        target = (self.launchable_result(PRODUCT)
                  if not self.provider_contracts['gnome-shell']['application_id'] else
                  self.fresh_owned_target(target))
        require(target is not None, 'ui:search-result-stale')
        component = target.get_component_iface()
        require(component is not None, 'ui:search-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:search-focus-refused')
        def focused():
            current = self.launchable_result(PRODUCT)
            return current is not None and self.has_state(current, self.api.StateType.FOCUSED)
        self.wait(focused, 'parent-result-focus')
        self.input_uncertain = False

    def search_absence(self, product, *, stable_seconds):
        """Positive query/result witnesses plus fresh, complete absence reads.

        A missing tree, unfinished query, stale subtree or failed read cannot
        prove that the launcher is unavailable. Require a stable observation
        interval; repeat reads only, with no replay of customer input.
        """
        stable_since = None
        semantic_shell = not self.provider_contracts['gnome-shell']['application_id']
        if not semantic_shell:
            self.require_provider_contract(
                'gnome-shell', 'app-grid',
                ('search', 'result::parent', 'web-suggestion::parent'))
        def observed():
            nonlocal stable_since
            try:
                # Keep prompt/traversal failures inside the interval guard.
                # wait() retries these reads; none may bridge a stable interval.
                self.handle_system_prompt()
                if semantic_shell:
                    owner, nodes, snapshot, facts = self.shell_search_snapshot()
                    self.search_status = 'shell-owner-missing'
                    if owner is None:
                        stable_since = None
                        return False
                    scoped = self.snapshot_scope(nodes, snapshot, owner)
                    fields = [node for node in scoped
                              if facts[node]['role'] in ('text', 'entry')
                              and facts[node]['showing']
                              and self.has_state(node, self.api.StateType.SENSITIVE)
                              and self.has_state(node, self.api.StateType.EDITABLE)]
                    require(len(fields) <= 1, 'ui:shell-search-ambiguous')
                    self.search_status = 'shell-field-missing'
                    if not fields or not self.shell_query_matches(fields[0], product):
                        stable_since = None
                        return False
                    description = 'Search "' + product + '" on the web'
                    buttons = [node for node in scoped
                               if facts[node]['role'] in ('button', 'push button')
                               and facts[node]['showing']]
                    suggestions = [node for node in buttons
                                   if self.has_state(node, self.api.StateType.SENSITIVE)
                                   and (facts[node]['name'] == description or any(
                                       facts[child]['role'] == 'label'
                                       and facts[child]['showing']
                                       and facts[child]['name'] == description
                                       for child in self.snapshot_scope(nodes, snapshot, node)))]
                    require(len(suggestions) <= 1, 'ui:shell-suggestion-ambiguous')
                    self.search_status = 'suggestion-missing'
                    if not suggestions:
                        stable_since = None
                        return False
                    launchers = [node for node in buttons
                                 if facts[node]['name'] == product or any(
                                     facts[child]['role'] == 'label'
                                     and facts[child]['showing']
                                     and facts[child]['name'] == product
                                     for child in self.snapshot_scope(nodes, snapshot, node))]
                    management = {'parent-window', 'parent-access-denied-window',
                                  'kiosk-request-window', 'startup-error-window'}
                    ready = not launchers and not any(
                        facts[node]['showing'] and facts[node]['identity'] in management
                        for node in nodes)
                    self.search_status = ('description-matched' if ready else
                                          'parent-available')
                    if not ready:
                        stable_since = None
                        return False
                    now = time.monotonic()
                    if stable_since is None:
                        stable_since = now
                    return now - stable_since >= stable_seconds
                self.search_status = 'surface-missing'
                surface, registered = self.provider_surface(
                    'gnome-shell', 'app-grid',
                    ('search', 'result::parent', 'web-suggestion::parent'))
                ready = surface is not None and self.search_query(product)
                if ready:
                    suggestion = self.find_id(
                        registered['web-suggestion::parent'], root=surface)
                    ready = (suggestion is not None and self.has_state(
                        suggestion, self.api.StateType.SENSITIVE))
                    self.search_status = 'suggestion-matched' if ready else 'suggestion-missing'
                if ready:
                    ready = self.read_label(suggestion, 'web-suggestion', expected=product, maximum=80)
                    self.search_status = 'description-matched' if ready else 'description-missing'
                root = self.api.get_desktop(0)
                nodes = list(self.nodes(root, strict=True)) if root is not None else []
                for node in nodes:
                    if self.has_state(node, self.api.StateType.DEFUNCT):
                        ready = False
                        self.search_status = 'incomplete-read'
                    if (self.showing(node) and public_automation_id(node)
                            == registered['result::parent']):
                        ready = False
                        self.search_status = 'parent-available'
                    if (self.showing(node) and public_automation_id(node) in (
                            'parent-window', 'parent-access-denied-window',
                            'kiosk-request-window', 'startup-error-window')):
                        ready = False
                        self.search_status = 'parent-window-available'
                if not ready:
                    stable_since = None
                    return False
                now = time.monotonic()
                if stable_since is None:
                    stable_since = now
                return now - stable_since >= stable_seconds
            except (UiError, *self.query_errors):
                stable_since = None
                self.search_status = 'incomplete-read'
                raise
        return self.wait_search(observed, 'standard-parent-unavailable',
                                prompt_in_predicate=True)

    def wait_search(self, predicate, code, *, prompt_in_predicate=False):
        self.search_status = 'observation-pending'
        try:
            return self.wait(predicate, code, prompt_in_predicate=prompt_in_predicate)
        except UiError as error:
            if str(error) == 'ui:timeout:' + code:
                raise UiError(str(error) + ':' + self.search_status) from None
            raise

    def search_diagnostic(self):
        """Fixed ID-presence diagnostic; it never becomes target identity."""
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid',
            ('search', 'result::parent', 'web-suggestion::parent'), showing=False)
        if surface is None:
            return {'provider_surface': 'absent', 'identified_controls': []}
        identified = [logical for logical, identity in registered.items()
                      if self.find_id(identity, root=surface, showing=False) is not None]
        return {'provider_surface': 'identified', 'identified_controls': sorted(identified)}

    def system_prompt_control(self, *, qualify=True):
        """Resolve Cancel only through the qualified keyring provider contract."""
        prompt_controls = ('recipient', 'secret', 'confirm', 'cancel')
        # Validate every authentication provider before the first tree read, so
        # a qualified keyring mapping cannot conceal an unqualified Polkit path
        # (or vice versa) during unrelated waits.
        self.require_provider_contract('gnome-shell-polkit-agent', 'polkit', prompt_controls)
        self.require_provider_contract('gcr-keyring-prompter', 'keyring', prompt_controls)
        polkit, _polkit_registered = self.provider_surface(
            'gnome-shell-polkit-agent', 'polkit', prompt_controls)
        require(polkit is None, 'ui:unsupported-system-prompt')
        surface, registered = self.provider_surface(
            'gcr-keyring-prompter', 'keyring',
            prompt_controls)
        if surface is None:
            return None
        if not qualify:
            return surface
        recipient = self.find_id(registered['recipient'], root=surface)
        field = self.find_id(registered['secret'], root=surface)
        confirm = self.find_id(registered['confirm'], root=surface)
        cancel = self.find_id(registered['cancel'], root=surface)
        require(recipient is not None, 'ui:system-prompt-recipient')
        require(field is not None and field.get_role_name() == 'password text'
                and self.has_state(field, self.api.StateType.SENSITIVE)
                and self.has_state(field, self.api.StateType.FOCUSED),
                'ui:system-prompt-focus')
        interface = field.get_text_iface()
        require(interface is not None and self.api.Text.get_character_count(interface) == 0,
                'ui:system-prompt-secret-state')
        require(confirm is not None and cancel is not None
                and self.has_state(cancel, self.api.StateType.SENSITIVE),
                'ui:system-prompt-control')
        return cancel

    def system_prompt_absent(self, dialog=None):
        # Absence is a fresh read of the qualified provider surface. A stale or
        # incomplete tree cannot establish dismissal.
        prompt_controls = ('recipient', 'secret', 'confirm', 'cancel')
        self.require_provider_contract('gnome-shell-polkit-agent', 'polkit', prompt_controls)
        self.require_provider_contract('gcr-keyring-prompter', 'keyring', prompt_controls)
        polkit, _polkit_registered = self.provider_surface(
            'gnome-shell-polkit-agent', 'polkit', prompt_controls, showing=False)
        require(polkit is None or not self.showing(polkit), 'ui:unsupported-system-prompt')
        surface, _registered = self.provider_surface(
            'gcr-keyring-prompter', 'keyring',
            prompt_controls, showing=False)
        if surface is None or not self.showing(surface):
            return True
        return dialog is not None and surface is not dialog

    @staticmethod
    def _prompt_application_kind(name):
        """Classify only the fixed provider application names for this image."""
        normalized = ' '.join(name.casefold().replace('_', ' ').replace('-', ' ').split())
        if normalized in (
                'policykit authentication agent',
                'mate polkit',
                'mate polkit authentication agent',
                'polkit mate authentication agent 1'):
            return 'mate-polkit'
        if normalized in ('gnome shell', 'gnome shell polkit agent'):
            return 'shell-polkit'
        if normalized in ('gcr prompter', 'gcr prompter 3', 'gcr prompter 4',
                          'system prompter'):
            return 'keyring'
        return None

    @staticmethod
    def _prompt_title(name):
        normalized = ' '.join(name.casefold().split())
        return normalized in (
            'authenticate', 'authentication required', 'password required',
            'unlock keyring', 'unlock login keyring',
        )

    def _provider_kind_from_ids(self, application, surface, identities=None):
        """Use provider IDs when both available, without requiring control IDs."""
        application_id = (public_automation_id(application) if identities is None
                          else identities[application])
        surface_id = (public_automation_id(surface) if identities is None
                      else identities[surface])
        bindings = []
        for provider, kind in (
                ('mate-polkit-agent', 'mate-polkit'),
                ('gnome-shell-polkit-agent', 'shell-polkit'),
                ('gcr-keyring-prompter', 'keyring')):
            contract = self.provider_contracts.get(provider, {})
            expected_application = contract.get('application_id')
            expected_surface = contract.get('surfaces', {}).get(
                'keyring' if kind == 'keyring' else 'polkit', (None, {}))[0]
            if (expected_application and expected_surface
                    and application_id == expected_application and surface_id == expected_surface):
                bindings.append(kind)
        require(len(bindings) <= 1, 'ui:ambiguous-system-prompt')
        return bindings[0] if bindings else None

    def system_prompt_kind(self, *, observation=None):
        """Read one complete tree and classify a visible authentication modal.

        This is the provider-specific G02 adapter.  It recognizes only the
        fixed English provider semantics used by the prepared Ubuntu image, or
        a provider's application/surface IDs when both are available.  It does
        not resolve an input control and cannot authorize an action.
        """
        if observation is None:
            desktop = self.api.get_desktop(0)
            require(desktop is not None, 'ui:incomplete-tree')
            snapshot = {}
            facts = {}
            nodes = list(self.nodes(
                desktop, strict=True, snapshot=snapshot, facts=facts))
            require(nodes, 'ui:incomplete-tree')
        else:
            nodes, snapshot, facts = observation
        identities = {node: facts[node]['identity'] for node in nodes}
        provider_application_ids = {
            contract.get('application_id')
            for provider, contract in self.provider_contracts.items()
            if provider in ('mate-polkit-agent', 'gnome-shell-polkit-agent',
                            'gcr-keyring-prompter') and contract.get('application_id')
        }
        applications = [node for node in nodes
                        if facts[node]['role'] == 'application'
                        or identities[node] in provider_application_ids]
        candidates = []
        for application in applications:
            application_nodes = self.snapshot_scope(nodes, snapshot, application)
            application_kind = self._prompt_application_kind(facts[application]['name'])
            owned = bool(identities[application] in (
                PARENT_APPLICATION, KIOSK_APPLICATION, CHILD_APPLICATION,
                WATCH_APPLICATION, UI_WATCH_APPLICATION))
            for surface in application_nodes:
                if surface is application or not facts[surface]['showing']:
                    continue
                id_kind = self._provider_kind_from_ids(
                    application, surface, identities)
                modal = (facts[surface]['role'] in ('alert', 'dialog')
                         or facts[surface]['modal']
                         or id_kind is not None)
                if not modal:
                    continue
                # Descendant lookup is needed only for candidate dialogs.
                # Doing it for every label/control makes this shared check
                # quadratic in large Shell and application trees.
                descendants = self.snapshot_scope(nodes, snapshot, surface)
                password = any(facts[node]['role'] == 'password text'
                               for node in descendants)
                prompt_title = self._prompt_title(facts[surface]['name'])
                kind = id_kind or application_kind
                # Shell's logout confirmation is also modal. Known provider
                # applications need authentication meaning; an unregistered
                # external modal is itself an unknown surface and must block.
                if kind is not None and not (password or prompt_title):
                    continue
                if not owned:
                    candidates.append(kind or 'unknown')
        require(len(candidates) <= 1, 'ui:ambiguous-system-prompt')
        return candidates[0] if candidates else None

    def pointer_target(self, node):
        raise UiError('ui:pointer-route-refused')

    def pointer_glyph(self, node):
        raise UiError('ui:pointer-route-refused')

    def stable_pointer(self, locate, *, stable_seconds=0.4):
        raise UiError('ui:pointer-route-refused')

    def handle_system_prompt(self, *, observation=None):
        """Recognize and refuse session prompts without delivering input."""
        if not self.prompt_enabled or self.handling_prompt:
            return
        self.handling_prompt = True
        try:
            kind = (self.system_prompt_kind() if observation is None else
                    self.system_prompt_kind(observation=observation))
            if kind is not None:
                require(self.prompt_session in ('station', 'desktop'),
                        'ui:system-prompt-session')
                raise UiError('ui:system-prompt-refused:' + self.prompt_session + ':' + kind)
        except self.query_errors:
            raise UiError('ui:system-prompt-observation-failed') from None
        finally:
            self.handling_prompt = False

    def run(self, operation, version):
        """One registered operation, with generic read reuse between inputs."""
        with self.observation():
            return self._run(operation, version)

    def _run(self, operation, version):
        require(operation in OPERATIONS, 'ui:operation')
        self.prompt_enabled = operation not in GREETER_OPERATIONS and operation not in STATION_BRANCH_OPERATIONS
        self.prompt_session = ('station' if operation in KIOSK_SESSION_OPERATIONS
                               or operation == 'station-default-entry' else
                               None if operation in GREETER_OPERATIONS else 'desktop')
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'station-entry-branch':
            result['branch'] = self.station_entry_branch(self.branch_owner)
        elif operation == 'station-default-entry':
            result['entry'] = self.station_default_entry(self.branch_owner)
        elif operation in GREETER_OPERATIONS:
            if operation == 'gdm-no-child-refused':
                self.gdm_nonsecret_account(KIOSK)
                try:
                    self.kiosk_account_snapshot('child')
                except UiError as error:
                    require(str(error) == 'ui:kiosk-account-surface', 'ui:kiosk-wrong-refusal')
                else:
                    raise UiError('ui:kiosk-wrong-entry-accepted')
            elif operation in ('gdm-wrong-recipient-refused', 'gdm-standard-wrong-recipient-refused'):
                self.wait(lambda: self.password_recipient(OTHER_PARENT), 'gdm-other-recipient')
                name = EXISTING_CHILD if operation == 'gdm-standard-wrong-recipient-refused' else PARENT
                require(not self.password_recipient(name), 'ui:gdm-wrong-recipient-accepted')
            elif operation in ('gdm-parent-recipient', 'gdm-parent-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(PARENT), 'gdm-parent-recipient')
            elif operation in ('gdm-standard-recipient', 'gdm-standard-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(EXISTING_CHILD), 'gdm-standard-recipient')
            elif operation == 'gdm-select-parent':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-product-free-select-parent':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-product-free-returned':
                self.gdm_product_free_account()
            elif operation in ('gdm-navigation-returned', 'gdm-dismissed', 'gdm-returned'):
                self.gdm_nonsecret_account(PARENT)
            elif operation == 'gdm-station-wrong-entry-refused':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-station-returned':
                self.kiosk_gdm_returned()
            elif operation in ('gdm-focused', 'gdm-other-focused', 'gdm-standard-focused',
                              'gdm-station-focused', 'gdm-product-free-focused'):
                name = OTHER_PARENT if operation == 'gdm-other-focused' else PARENT
                if operation == 'gdm-standard-focused':
                    name = EXISTING_CHILD
                if operation == 'gdm-station-focused':
                    name = KIOSK
                account = (self.gdm_product_free_account
                           if operation == 'gdm-product-free-focused'
                           else (lambda: self.gdm_nonsecret_account(name))
                           if operation in GDM_NONSECRET_OPERATIONS
                           else (lambda: self.greeter_list(name)))
                self.wait(lambda: self.has_state(account(), self.api.StateType.FOCUSED),
                          'gdm-account-focus')
            elif operation in GREETER_NAVIGATION:
                name = OTHER_PARENT if operation == 'gdm-other-list' else PARENT
                if operation == 'gdm-standard-list':
                    name = EXISTING_CHILD
                if operation == 'gdm-station-list':
                    name = KIOSK
                if operation == 'gdm-product-free-list':
                    result['focused'] = self.gdm_product_free_navigation()
                else:
                    navigation = (self.gdm_nonsecret_navigation
                                  if operation in GDM_NONSECRET_OPERATIONS
                                  else self.greeter_navigation)
                    result['focused'] = navigation(name)
            else:
                self.greeter_list()
        elif operation in ('fresh-parent-desktop', 'fresh-standard-desktop'):
            self.standard_shell_desktop(no_prompt=True)
        elif operation == 'keyring-cancel-standard':
            self.cancel_keyring_prompt()
        elif operation in ('desktop', 'standard-desktop'):
            self.desktop_result(PARENT if operation == 'desktop' else EXISTING_CHILD, 'success')
        elif operation == 'help-desktop-clear':
            self.help_desktop_clear()
        elif operation == 'standard-system-prompt':
            self.desktop_result(EXISTING_CHILD, 'success')
        elif operation in ('parent-command-launch', 'standard-parent-command-launch'):
            self.launch_parent_command(standard=operation == 'standard-parent-command-launch')
        elif operation == 'child-command-launch':
            self.launch_child_command()
        elif operation == 'standard-parent-closed':
            self.wait(self.parent_denial_closed, 'denial-closed')
        elif operation == 'standard-management-denied':
            self.management_denied()
        elif operation == 'standard-app-grid':
            self.search_ready('overview')
        elif operation == 'standard-search-focused':
            self.focus_search_field()
        elif operation == 'standard-search-started':
            # GNOME's public overview supports type-to-search without manually
            # focusing the entry. Observe the first character before continuing.
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'standard-search-started')
        elif operation == 'standard-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'standard-search-entered')
        elif operation == 'standard-parent-unavailable':
            self.search_result(PRODUCT, 'unavailable', stable_seconds=2)
        elif operation == 'standard-search-qualified':
            self.search_result(PRODUCT, 'unavailable', stable_seconds=2)
            result['provider'] = self.shell_provider_metadata()
        elif operation == 'parent-search-ready':
            self.search_ready('overview')
        elif operation == 'parent-search-focused':
            self.focus_search_field()
            self.search_ready('overview', focused=True)
        elif operation == 'parent-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'parent-search-entered')
        elif operation == 'shell-search-started':
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'shell-search-started')
        elif operation == 'shell-search-wrong-result-refused':
            require(self.search_query(PRODUCT), 'ui:search-query')
            try:
                self.launchable_result('Terminal')
            except UiError as error:
                require(str(error) == 'ui:search-binding', 'ui:wrong-search-refusal')
            else:
                raise UiError('ui:wrong-search-accepted')
        elif operation == 'shell-search-cleared':
            self.search_ready('overview')
        elif operation == 'shell-search-dismissed':
            self.standard_shell_desktop(no_prompt=True)
            require(self.shell_search_field() is None, 'ui:search-not-dismissed')
        elif operation == 'app-grid':
            self.focus_search_result()
        elif operation == 'parent-search-close-ready':
            result['provider'] = self.shell_provider_metadata()
            self.wait(lambda: self.has_state(self.parent(), self.api.StateType.ACTIVE),
                      'parent-search-close-ready')
        elif operation == 'parent-search-closed':
            self.wait(self.parent_search_closed, 'parent-search-closed')
        elif operation == 'parent-window':
            self.parent()
        elif operation == 'parent-empty':
            self.parent_empty()
        elif operation in TOGGLE_OPERATIONS:
            result['toggle'] = self.parent_toggle_operation(operation)
        elif operation in PARENT_SAVE_OPERATIONS:
            result['save'] = self.parent_save_operation(operation)
        elif operation in PICKER_OPERATIONS:
            result['focused'] = self.open_child_picker(PICKER_OPERATIONS[operation])
        elif operation in HIGHLIGHT_OPERATIONS:
            self.child_highlighted(HIGHLIGHT_OPERATIONS[operation])
        elif operation in ('existing-apps', 'new-child-apps'):
            child = EXISTING_CHILD if operation == 'existing-apps' else NEW_CHILD
            self.parent_page(child, 'App Limits')
        elif operation in SETTINGS_OPERATIONS and operation != 'parent-returned':
            child = SETTINGS_OPERATIONS[operation]
            if operation in ('discovery-ready', 'new-child-screen'):
                result['settings'] = self.parent_page(child, 'Screen Limits')
            else:
                result['settings'] = self.selected_child(child)
        elif operation == 'about':
            self.open_about(version)
        elif operation == 'about-rechecked':
            root = self.about()
            self.read_label(root, 'about-product', maximum=80)
            self.read_label(root, 'about-version', maximum=80, expected=version)
            self.id_target('about-license-value', root=root)
        elif operation.startswith('license-') and operation.endswith('-launched'):
            self.license_fixture_launch(operation.removeprefix('license-').removesuffix('-launched'))
        elif operation.startswith('license-') and operation.endswith('-ready'):
            self.license_fixture_ready(operation.removeprefix('license-').removesuffix('-ready'))
        elif operation.startswith('license-') and operation.endswith('-closed') and operation != 'license-closed':
            self.license_fixture_closed(operation.removeprefix('license-').removesuffix('-closed'))
        elif operation == 'license':
            self.open_license()
            self.window_ready_to_close('license')
        elif operation == 'license-provider-refusals':
            self.window_ready_to_close('license')
            result['provider'] = self.license_provider_metadata()
        elif operation == 'license-closed':
            self.window_closed('license', 'about')
        elif operation == 'about-returned':
            self.window_closed('license', 'about')
            self.about_footer()
            self.window_ready_to_close('about')
        elif operation == 'parent-returned':
            self.window_closed('about', 'parent')
            result['settings'] = self.settings()
        elif operation in KIOSK_DISABLED_REQUESTS:
            if operation == 'kiosk-disabled-child-select':
                result['request'] = self.select_kiosk_account(
                    'child', CHILD, expected=(CHILD, EXISTING_CHILD), enabled=False)
            else:
                result['request'] = self.kiosk_request_form(
                    enabled=False, expected_selection=('child', CHILD_IDENTITIES[CHILD]))
        elif operation in KIOSK_ACCOUNT_REQUESTS:
            if operation == 'kiosk-child-select':
                result['request'] = self.select_kiosk_account(
                    'child', CHILD, expected=(CHILD, EXISTING_CHILD))
            elif operation == 'kiosk-approver-select':
                result['request'] = self.select_kiosk_account(
                    'approver', PARENT, expected=(PARENT, OTHER_PARENT))
            else:
                result['request'] = self.kiosk_request_form(enabled=True)
        elif operation in KIOSK_ACCOUNT_REFUSALS:
            if operation == 'parent-kiosk-refused':
                self.parent()
                try:
                    self.kiosk_account_snapshot('child')
                except UiError as error:
                    require(str(error) == 'ui:kiosk-account-surface', 'ui:kiosk-wrong-refusal')
                else:
                    raise UiError('ui:kiosk-wrong-entry-accepted')
            else:
                for field, name, expected in (
                        ('child', PARENT, (CHILD, EXISTING_CHILD)),
                        ('approver', NEW_CHILD, (PARENT, OTHER_PARENT))):
                    try:
                        self.select_kiosk_account(field, name, expected=expected)
                    except UiError as error:
                        require(str(error) == 'ui:kiosk-account-choice', 'ui:kiosk-wrong-refusal')
                    else:
                        raise UiError('ui:kiosk-wrong-choice-accepted')
        elif operation == 'kiosk-child-choices-open':
            self.select_kiosk_account('child', CHILD, expected=(CHILD, EXISTING_CHILD),
                                      enabled=False, inspect_only=True)
        elif operation == 'kiosk-child-choices-closed':
            result['request'] = self.collapse_kiosk_child_choices()
        elif operation == 'kiosk-request-form':
            result['request'] = self.kiosk_request_form()
        elif operation == 'kiosk-no-child-form':
            result['request'] = self.kiosk_request_form(no_child=True)
        elif operation == 'kiosk-request-cancel':
            self.cancel_kiosk_request()
        elif operation == 'kiosk-request-escape-ready':
            self.focus_kiosk_escape_recipient()
        return result


def validate_shell_metadata(value):
    """Bound the nonsecret tuple on both sides of the observation transport."""
    require(type(value) is dict and set(value) == {'version', 'locale', 'keyboard'},
            'ui:shell-metadata')
    require(type(value['keyboard']) is list and 0 < len(value['keyboard']) <= 8,
            'ui:shell-metadata')
    words = [value['version'], value['locale']]
    for source in value['keyboard']:
        require(type(source) is list and len(source) == 2 and source[0] in ('xkb', 'ibus'),
                'ui:shell-metadata')
        words.extend(source)
    require(all(type(word) is str and re.fullmatch(r'[A-Za-z0-9_.+:@()/-]{1,128}', word)
                for word in words), 'ui:shell-metadata')
    return value


def greeter_account(*, station_branch=False, station_required=False):
    """Resolve the sole active local greeter via public logind session metadata.

    Modern GDM can use a dynamic account instead of the legacy gdm UID. This
    selects only the public UI connection identity; it proves no product result.
    """
    # Installed boots gate GDM on enforcement readiness. Snapshot consumers
    # enter here directly after SSH, without the former setup boot-complete
    # wait. Observe the public greeter within its own finite boot budget.
    require(not station_required or station_branch, 'ui:station-account-binding')
    deadline = time.monotonic() + (90 if station_branch else 300)
    def call(*args):
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'ui:timeout:greeter-identity')
        return subprocess.run(['/usr/bin/loginctl', *args], capture_output=True,
                              text=True, check=True, timeout=min(5, remaining)).stdout
    while True:
        rows = call('list-sessions', '--no-legend', '--no-pager').splitlines()
        require(len(rows) <= 32, 'ui:session-bound')
        found = []
        for row in rows:
            session = row.split()[0]
            import re
            require(re.fullmatch(r'[a-zA-Z0-9]+', session), 'ui:session-id')
            props = dict(line.split('=', 1) for line in call('show-session', session,
                '-p', 'Class', '-p', 'Active', '-p', 'Remote', '-p', 'Type', '-p', 'Seat', '-p', 'User').splitlines())
            if ((station_branch or props.get('Class') == 'greeter') and props.get('Active') == 'yes'
                    and props.get('Remote') == 'no' and props.get('Seat') == 'seat0'
                    and props.get('Type') in ('wayland', 'x11')):
                require(props.get('User', '').isdecimal() and int(props['User']) > 0,
                        'ui:greeter-user')
                uid = int(props['User'])
                if station_branch:
                    owner = 'greeter' if props.get('Class') == 'greeter' else 'station'
                    require(owner == 'greeter' or (props.get('Class') == 'user'
                            and uid == pwd.getpwnam(KIOSK_USERNAME).pw_uid),
                            'ui:station-branch-owner')
                    found.append((uid, owner))
                else:
                    found.append(uid)
        require(len(found) <= 1, 'ui:greeter-identity')
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'ui:timeout:greeter-identity')
        if found and not (station_required and found[0][1] != 'station'):
            if station_branch:
                return pwd.getpwuid(found[0][0]), found[0][1]
            return pwd.getpwuid(found[0])
        # SSH can become ready before GDM after an installed snapshot boots.
        # Retry only absence, never an ambiguous identity or a failed read.
        time.sleep(min(.2, remaining))


def require_active_launch_session():
    """Bind direct execution to one active local graphical session of this UID."""
    uid = os.getuid()
    require(uid >= 1000 and os.geteuid() == uid, 'ui:launch-identity')

    def call(*args):
        return subprocess.run(['/usr/bin/loginctl', *args], capture_output=True,
                              text=True, check=True, timeout=10).stdout

    rows = call('list-sessions', '--no-legend', '--no-pager').splitlines()
    require(len(rows) <= 32, 'ui:session-bound')
    active = []
    for row in rows:
        fields = row.split()
        require(len(fields) >= 2, 'ui:session-row')
        if fields[1] != str(uid):
            continue
        session = fields[0]
        require(re.fullmatch(r'[a-zA-Z0-9]+', session), 'ui:session-id')
        props = dict(line.split('=', 1) for line in call(
            'show-session', session, '--no-pager', '-p', 'User', '-p', 'Active',
            '-p', 'Remote', '-p', 'Class', '-p', 'Type', '-p', 'Seat').splitlines())
        if props.get('User') == str(uid) and props.get('Active') == 'yes':
            if props.get('Class') in ('user', 'user-early') and props.get('Type') in ('wayland', 'x11'):
                require(props.get('Remote') == 'no' and props.get('Seat') == 'seat0',
                        'ui:launch-session')
                active.append(session)
    require(len(active) == 1, 'ui:launch-session')


def session_environment(account, *, runtime_root=Path('/run/user'), timeout=20):
    """Wait for the selected account's owned public session-bus socket."""
    runtime = runtime_root / str(account.pw_uid)
    deadline = time.monotonic() + timeout
    while True:
        pending = 'runtime'
        try:
            info = runtime.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == account.pw_uid,
                    'ui:runtime-owner')
            path = runtime / 'bus'
            pending = 'session-bus'
            info = path.lstat()
            require(stat.S_ISSOCK(info.st_mode) and info.st_uid == account.pw_uid,
                    'ui:session-bus')
            return {'XDG_RUNTIME_DIR': str(runtime),
                    'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(path)}
        except FileNotFoundError:
            require(time.monotonic() < deadline, 'ui:timeout:' + pending)
            time.sleep(.2)


def observation_environment(account, operation):
    if operation in KIOSK_SESSION_OPERATIONS or operation == 'station-default-entry':
        runtime = '/run/user/' + str(account.pw_uid)
        return {'XDG_RUNTIME_DIR': runtime,
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + runtime + '/bus'}
    return session_environment(account)


def main():
    require(len(sys.argv) == 3 and sys.argv[1] in OPERATIONS, 'ui:arguments')
    greeter = sys.argv[1] in GREETER_OPERATIONS
    kiosk = sys.argv[1] in KIOSK_SESSION_OPERATIONS or sys.argv[1] == 'station-default-entry'
    require(os.geteuid() == 0, 'ui:fixture-identity')
    branch_owner = None
    if sys.argv[1] in STATION_BRANCH_OPERATIONS:
        account, branch_owner = greeter_account(
            station_branch=True,
            station_required=sys.argv[1] == 'station-default-entry')
        greeter, kiosk = branch_owner == 'greeter', branch_owner == 'station'
    else:
        account = greeter_account() if greeter else pwd.getpwnam(
            'oh-no-parent-control' if kiosk else
            ('onpc-child-jordan' if sys.argv[1] in STANDARD_OPERATIONS else 'onpc-parent-jamie'))
    require(account.pw_uid > 0 and (greeter or account.pw_uid >= 1000), 'ui:fixture-identity')
    # Station entry is qualified by its public form. Bind the observation
    # client to the account without polling session services or treating their
    # readiness as a customer result.
    environment = observation_environment(account, sys.argv[1])
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.clear()
    os.environ.update(HOME=account.pw_dir, USER=account.pw_name,
                      **environment,
                      LANG='C.UTF-8', NO_AT_BRIDGE='0')
    if sys.argv[1] == 'keyring-cancel-standard':
        require_active_launch_session()
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib
    Atspi.set_timeout(2000, 5000)

    def reset_atspi_client():
        # Reconnect this observer's client after a graphical-session handoff.
        # This only resets the local AT-SPI client; it does not start, wait for,
        # or inspect an accessibility service.
        Atspi.exit()
        Atspi.init()

    ui = AccessibleUI(Atspi, timeout=90 if kiosk else 45, query_errors=(GLib.Error,),
        reset_observer=reset_atspi_client if kiosk else None,
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.branch_owner = branch_owner
    try:
        result = ui.run(sys.argv[1], sys.argv[2])
    except UiError:
        if sys.argv[1] in STANDARD_OPERATIONS:
            try:
                print(json.dumps(ui.search_diagnostic(), sort_keys=True), file=sys.stderr, flush=True)
            except Exception:
                print('ui:search-diagnostic-unavailable', file=sys.stderr, flush=True)
        raise
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No raw UI tree, account names, document contents or D-Bus errors.
        print(str(error) if isinstance(error, UiError) else 'ui:adapter-failed:' + type(error).__name__,
              file=sys.stderr, flush=True)
        raise SystemExit(1)
