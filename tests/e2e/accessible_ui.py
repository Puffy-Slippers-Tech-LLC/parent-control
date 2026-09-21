"""Bounded public AT-SPI interaction in the installed fixture's desktop.

This file also runs as a standalone program in the guarded guest. It reads only
public UI objects; it never imports product code or reads product storage/buses.
Only fixed operation names and sanitized results cross the controller boundary.
"""

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
    'gdm-list', 'gdm-focused', 'gdm-select-parent', 'gdm-dismissed', 'gdm-returned',
    'desktop', 'app-grid', 'parent-window', 'parent-empty', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'license', 'license-closed', 'about-returned', 'parent-returned',
    'discovery-ready', 'new-child-picker-opened', 'new-child-choice-highlighted',
    'new-child-selected', 'existing-child-picker-opened', 'existing-child-choice-highlighted',
    'existing-returned', 'existing-apps', 'new-child-apps', 'new-child-screen',
    'discovery-child-picker-opened', 'discovery-child-choice-highlighted', 'discovery-selected',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused',
    'kiosk-request-form', 'station-entry-branch',
})
STANDARD_OPERATIONS = frozenset({
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
})
TERMINAL_OPERATIONS = frozenset({
    'standard-terminal-input',
    'standard-terminal-focused', 'standard-terminal-wrong-surface',
    'standard-terminal-closed', 'standard-management-denied', 'standard-denial-closed',
})
OPERATIONS |= TERMINAL_OPERATIONS
OPERATIONS |= frozenset({'parent-search-ready', 'parent-search-focused', 'parent-search-entered'})
STANDARD_OPERATIONS |= TERMINAL_OPERATIONS
HELP_BINDINGS = {
    'parent-help': ('oh-no-parent-control-parent', 'help',
                    'Administrator-facing GTK 4/libadwaita parent-control application.'),
    'station-help': ('oh-no-parent-control', 'help',
                     'Libadwaita application for the GNOME Kiosk request station.'),
    'parent-manual': ('oh-no-parent-control-parent', 'manual',
                      'configure controls for managed users'),
    'station-manual': ('oh-no-parent-control', 'manual',
                       'run the parent-control request station'),
}
HELP_OPERATIONS = frozenset({
    'help-system-prompt', 'help-terminal-input', 'help-terminal-focused',
    'help-terminal-wrong-surface', 'help-terminal-closed', 'help-shell-ready',
    *('help-content-' + key for key in HELP_BINDINGS),
})
OPERATIONS |= HELP_OPERATIONS
SESSION_OPERATIONS = frozenset({
    'session-menu-toggle', 'session-menu-power', 'session-menu',
    'switch-user', 'logout', 'logout-confirm',
})
# Session actions remain registered for caller regressions, but cannot become
# reachable until the external Shell publishes its complete ID contract.
SESSION_ACTION_OPERATIONS = frozenset({
    'session-menu-toggle', 'session-menu-power', 'switch-user', 'logout', 'logout-confirm',
})
OPERATIONS |= SESSION_OPERATIONS
SESSION_ACTION_NAMES = {
    'switch-user': 'Switch User…',
    'logout': 'Log Out…',
}
PRODUCT = 'Oh No! Parent Control'
LICENSE_LINK = 'GNU General Public License v3.0'
ABOUT_FOOTER = '© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.'
CHILD = 'Riley (Child)'
EXISTING_CHILD = 'Jordan (Child)'
NEW_CHILD = 'Morgan (Child)'
CHILD_IDENTITIES = {CHILD: 'fixture-child', EXISTING_CHILD: 'existing-fixture-child',
                    NEW_CHILD: 'new-fixture-child'}
CHILD_ACCOUNTS = {CHILD: 'onpc-child-riley', EXISTING_CHILD: 'onpc-child-jordan',
                  NEW_CHILD: 'onpc-child-morgan'}
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
    'discovery-selected': EXISTING_CHILD,
    'new-child-selected': NEW_CHILD, 'new-child-screen': NEW_CHILD, 'existing-returned': EXISTING_CHILD,
}
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
GREETER_OPERATIONS = frozenset({'gdm-list', 'gdm-focused', 'gdm-select-parent', 'gdm-dismissed', 'gdm-returned',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused'})
GREETER_NAVIGATION = frozenset({'gdm-list', 'gdm-other-list', 'gdm-standard-list',
                                'gdm-station-list'})
GDM_NONSECRET_OPERATIONS = frozenset({
    'gdm-list', 'gdm-focused', 'gdm-station-wrong-entry-refused',
    'gdm-station-list', 'gdm-station-focused',
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
KIOSK_OPERATIONS = frozenset({'kiosk-request-form'})
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
                'activities': None, 'app-grid': None, 'quick-settings': None,
                'lock': None,
            }),
            'app-grid': (None, {
                'search': None, 'result::parent': None,
                'web-suggestion::parent': None,
            }),
            'session-menu': (None, {
                'power': None, 'switch-user': None, 'log-out': None,
            }),
            'logout-dialog': (None, {'confirm': None}),
            'notifications': (None, {'notification': None, 'dismiss': None}),
            'lock-screen': (None, {'recipient': None, 'password': None, 'unlock': None}),
        },
        'blocked_consumers': ('DESK01-12', 'SEARCH01-06', 'PANEL01-03',
                              'LIFE02', 'LIFE03', 'LIFE06'),
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
        'blocked_consumers': ('GDM login', 'account switching', 'kiosk entry'),
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
    'gnome-settings': {
        'application_id': None,
        'surfaces': {
            'settings': (None, {
                'search': 'search_entry', 'panel-list': 'panel_list',
            }),
            'users': (None, {
                # The page/list/action IDs are real installed GTK 4 Builder
                # IDs. Account rows are created dynamically without a stable
                # provider-owned identity, and neither page is a scoped root.
                'page': 'current_user_page', 'account-list': 'user_list',
                'account-row::<provider-account-id>': None,
                'add-user': 'add_user_button_row', 'name': 'fullname_row',
                'password': 'password_row', 'administrator': 'account_type_switch',
                'automatic-login': 'auto_login_switch',
                'remove-user': 'remove_user_button',
            }),
        },
        'blocked_consumers': ('ACCOUNT01', 'ACCOUNT02', 'TIME05'),
    },
    'gnome-text-editor': {
        'application_id': None,
        'surfaces': {
            'license-document': (None, {'content': None, 'close': None}),
            'ordinary-document': (None, {
                'content': None, 'save': None, 'close': None,
            }),
        },
        'blocked_consumers': ('ABOUT02', 'FILE08', 'FILE09',
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
        'blocked_consumers': ('FILE04', 'FILE05', 'FILE08', 'FEED08'),
    },
    'gnome-file-roller': {
        'application_id': None,
        'surfaces': {
            'archive': (None, {'archive-content': None, 'extract': None, 'close': None}),
        },
        'blocked_consumers': ('FILE08 archive review', 'FEED08 archive review'),
    },
    'terminal': {
        'application_id': None,
        'surfaces': {
            'terminal': (None, {'input-output': None}),
            'authentication': (None, {
                'recipient': None, 'secret': None, 'submit': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('FILE01', 'FILE02', 'FILE06', 'INFO02', 'LIFE04',
                              'AUTH01-04'),
    },
}


class UiError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise UiError(code)


def public_automation_id(node):
    """Normalize the provider's public stable ID, without selector fallbacks.

    GTK/ATK publish application IDs as AccessibleId. WebKitGTK instead uses
    AccessibleId for a transient AX object number and publishes the document's
    explicit control ID in AT-SPI GetAttributes. Select that contract by the
    provider's toolkit attribute, never by a label, role or tree position.
    Keep this here so the standalone guest reader and preview reader share it.
    """
    attributes = node.get_attributes()
    if attributes is None:
        # A provider can disappear between traversal and this query. With no
        # attributes its ID contract cannot be qualified, so treat the stale
        # node as unidentified rather than accepting a transient AccessibleId.
        return ''
    if attributes.get('toolkit') == 'WebKitGTK':
        return attributes.get('id', '')
    return node.get_accessible_id()


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


class AccessibleUI:
    """Fresh semantic lookup, bounded waits, unique targets and public actions.

    Appearance/coordinates are deliberately absent from the acceptance model.
    Hidden or disabled controls cannot authorize input. An action's return value
    is not success: callers must independently observe its resulting UI state.
    """

    def __init__(self, api, *, timeout=45, query_errors=(), dispatch=None,
                 reset_observer=None, provider_contracts=None, fixture_uids=None,
                 application_ids=None, owner_pids=None, application_owners=None):
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
        self.input_uncertain = False
        self.incomplete_observations = []
        self.gdm_row_diagnostic_emitted = False

    def nodes(self, root=None, *, strict=False, protected_ids=()):
        root = root if root is not None else self.api.get_desktop(0)
        pending = [root]
        visited = 0
        seen = set()
        while pending:
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
                if strict:
                    require(node.get_attributes() is not None, 'ui:incomplete-tree')
                yield node
                # Never traverse password contents. Strict owned observations
                # include ordinary text descendants without reading text values.
                role = node.get_role_name()
                protected = public_automation_id(node) in protected_ids
                if not protected and role != 'password text' and (strict or role not in ('text', 'entry')):
                    children = [node.get_child_at_index(i)
                                for i in reversed(range(node.get_child_count()))]
                    if strict and None in children:
                        error = UiError('ui:incomplete-tree')
                        error.add_note('Null child under public automation-id: '
                                       + (public_automation_id(node) or '[unidentified]'))
                        raise error
                    pending.extend(children)
            except self.query_errors:
                if strict:
                    raise
                # A dead unrelated subtree must not hide live controls.
                continue

    def find_id(self, identity, *, root=None, nodes=None, showing=True):
        """Resolve exactly one public automation ID without selector fallbacks."""
        require(type(identity) is str and identity, 'ui:automation-id')
        found = self.find_all_ids(identity, root=root, nodes=nodes)
        require(len(found) <= 1, 'ui:ambiguous-automation-id')
        if not found or (showing and not self.showing(found[0])):
            return None
        return found[0]

    def find_all_ids(self, identity, *, root=None, nodes=None):
        applications = owned_applications(identity)
        shell_owned = identity.startswith('child-')
        if shell_owned:
            public_nodes = list(self.nodes(strict=True))
            anchors = [node for node in public_nodes
                       if public_automation_id(node) == 'child-screen-time-indicator']
            require(len(anchors) <= 1, 'ui:ambiguous-automation-id')
            if not anchors:
                return []
            application = anchors[0].get_application()
            require(application is not None, 'ui:missing-application-owner')
            scope = list(self.nodes(application, strict=True))
            require(anchors[0] in scope, 'ui:wrong-application-owner')
            surface_id = owned_surface_id(identity)
            if surface_id is not None:
                surfaces = [node for node in scope if public_automation_id(node) == surface_id]
                require(len(surfaces) <= 1, 'ui:ambiguous-automation-id')
                if not surfaces:
                    return []
                scope = list(self.nodes(surfaces[0], strict=True))
            if root is not None:
                require(root in public_nodes and bool(public_automation_id(root)), 'ui:wrong-scope')
                scope = [node for node in scope if node in set(self.nodes(root, strict=True))]
            candidates = scope if nodes is None else [node for node in nodes if node in scope]
        elif applications:
            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                applications = tuple(value for value in applications if value in requested)
            desktop = list(self.nodes(strict=True))
            owners = [node for node in desktop if public_automation_id(node) in applications]
            require(len(owners) <= 1, 'ui:ambiguous-application')
            if not owners:
                return []
            application = owners[0]
            if self.owner_pids is not None:
                require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
            if self.application_owners is not None:
                owners = self.application_owners()
                require(application.get_process_id() in owners.get(
                    public_automation_id(application), ()), 'ui:wrong-application-owner')
            scope = list(self.nodes(application, strict=True))
            surface_id = owned_surface_id(identity)
            if surface_id is not None:
                surfaces = [node for node in scope if public_automation_id(node) == surface_id]
                require(len(surfaces) <= 1, 'ui:ambiguous-automation-id')
                if not surfaces:
                    return []
                self.validate_owned_surface(surfaces[0], application)
                scope = list(self.nodes(surfaces[0], strict=True))
            elif identity.endswith(('-dialog', '-window')):
                for surface in scope:
                    if public_automation_id(surface) == identity:
                        self.validate_owned_surface(surface, application)
            if root is not None:
                root_id = public_automation_id(root)
                require(bool(root_id), 'ui:unidentified-scope')
                # A caller may pass a wider application/window or a narrower
                # form/webview. In both directions require actual containment.
                current = [node for node in self.nodes(application, strict=True)
                           if public_automation_id(node) == root_id]
                require(len(current) == 1 and current[0] == root, 'ui:wrong-scope')
                subtree = set(self.nodes(current[0], strict=True))
                scope = [node for node in scope if node in subtree]
            candidates = scope if nodes is None else [node for node in nodes if node in scope]
        else:
            candidates = self.nodes(root) if nodes is None else nodes
        found = []
        for node in candidates:
            try:
                if public_automation_id(node) != identity:
                    continue
                found.append(node)
            except self.query_errors:
                if applications or shell_owned:
                    raise
                continue
        return found

    def validate_owned_surface(self, surface, application, *, visited=()):
        """Bind a dialog to its actual originating surface in the same app."""
        identity = public_automation_id(surface)
        app_id = public_automation_id(application)
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
        app_nodes = list(self.nodes(application, strict=True))
        # Embedded Adw dialogs can retain true containment. Separate GTK
        # toplevels publish CONTROLLED_BY from their native transient parent.
        containers = [node for node in app_nodes if public_automation_id(node) in expected]
        for container in containers:
            if surface in set(self.nodes(container, strict=True)):
                self.validate_owned_surface(container, application, visited=(*visited, identity))
                return
        parents = []
        for relation in surface.get_relation_set():
            if relation.get_relation_type() == self.api.RelationType.CONTROLLED_BY:
                parents.extend(relation.get_target(index)
                               for index in range(relation.get_n_targets()))
        require(len(parents) == 1 and parents[0] in app_nodes, 'ui:missing-surface-owner')
        parent = parents[0]
        parent_id = public_automation_id(parent)
        require(parent_id in expected, 'ui:wrong-surface-owner')
        matches = [node for node in app_nodes if public_automation_id(node) == parent_id]
        require(len(matches) == 1, 'ui:ambiguous-surface-owner')
        self.validate_owned_surface(parent, application, visited=(*visited, identity))

    def absent_id(self, identity, *, within):
        """Fresh complete negative observation with a positive surrounding ID."""
        try:
            nodes = list(self.nodes(strict=True))
            if not nodes or any(self.has_state(node, self.api.StateType.DEFUNCT)
                                for node in nodes):
                return False
            anchor = self.find_id(within, nodes=nodes)
            if anchor is None:
                return False
            matches = [node for node in nodes if public_automation_id(node) == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if matches:
                target = self.find_id(identity, nodes=nodes, showing=False)
                if target != matches[0]:
                    # A native dialog can disappear after the complete desktop
                    # snapshot but before its application/surface ownership is
                    # revalidated.  That mixed observation proves neither
                    # absence nor wrong ownership; let the caller repeat the
                    # whole read.  A node that remains in a second complete
                    # snapshot really is outside the required owner scope and
                    # must still fail closed.
                    refreshed = list(self.nodes(strict=True))
                    if matches[0] not in refreshed:
                        return False
                    raise UiError('ui:wrong-absence-owner')
                if self.showing(target):
                    return False
            return self.find_id(within) == anchor
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
        application_id, surface_id, controls = self.require_provider_contract(
            provider, surface, (control,))
        application = self.find_id(application_id, nodes=list(self.nodes(root, strict=True)), showing=showing)
        if application is None:
            return None
        surface_root = self.find_id(surface_id, nodes=list(self.nodes(application, strict=True)), showing=showing)
        if surface_root is None:
            return None
        return self.find_id(controls[control], nodes=list(self.nodes(surface_root, strict=True)), showing=showing)

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
        desktop = list(self.nodes(strict=True, protected_ids=protected))
        application = self.find_id(application_id, nodes=desktop, showing=showing)
        if application is None:
            return None, registered
        application_nodes = list(self.nodes(application, strict=True, protected_ids=protected))
        return self.find_id(surface_id, nodes=application_nodes, showing=showing), registered

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

    def wait(self, predicate, code):
        deadline = time.monotonic() + self.timeout
        incomplete = None
        while True:
            # Deliver pending public AT-SPI events before fresh reads. Cache
            # invalidation alone cannot deliver focus/text/registry changes.
            if self.dispatch is not None:
                for _ in range(32):
                    if not self.dispatch():
                        break
            try:
                self.handle_system_prompt()
                value = predicate()
            except self.query_errors:
                # UI objects can disappear during search/animation. Retry only
                # the read, never replay an action whose effect is uncertain.
                value = None
            except UiError as error:
                if str(error) != 'ui:incomplete-tree':
                    raise
                # Discard the entire observation. A child can disappear between
                # ChildCount and GetChildAtIndex during a public UI transition.
                # Only a later complete read may satisfy the predicate; no
                # action is replayed and the original deadline is retained.
                incomplete = error
                self.incomplete_observations.append({
                    'checkpoint': code, 'notes': getattr(error, '__notes__', [])})
                self.incomplete_observations = self.incomplete_observations[-16:]
                value = None
            if value:
                return value
            if time.monotonic() >= deadline:
                raise UiError('ui:timeout:' + code) from incomplete
            time.sleep(.2)

    def target(self, name=None, roles=(), **kwargs):
        raise UiError('ui:legacy-selector-refused')

    def id_target(self, identity, *, root=None, sensitive=False, showing=True):
        """Wait for one public ID, optionally requiring an actionable state."""
        node = self.wait(
            lambda: self.find_id(identity, root=root, showing=showing),
            'automation-id',
        )
        if sensitive:
            require(self.has_state(node, self.api.StateType.SENSITIVE),
                    'ui:unusable-target')
        return node

    def activate(self, node):
        require(not self.input_uncertain, 'ui:uncertain-input')
        self.handle_system_prompt()
        node = self.fresh_owned_target(node)
        require(self.showing(node) and node.get_state_set().contains(self.api.StateType.SENSITIVE),
                'ui:unusable-target')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-action')
        count = self.api.Action.get_n_actions(action)
        require(count == 1, 'ui:missing-or-ambiguous-action')
        self.input_uncertain = True
        require(self.api.Action.do_action(action, 0), 'ui:action-refused')
        self.input_uncertain = False

    def activate_named(self, node, action_name):
        """Invoke one named public action on an already ID-resolved control."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        self.handle_system_prompt()
        node = self.fresh_owned_target(node)
        require(self.showing(node) and self.has_state(node, self.api.StateType.SENSITIVE),
                'ui:unusable-target')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-action')
        names = []
        for index in range(self.api.Action.get_n_actions(action)):
            # GI incorrectly deprecates the recommended rename of this AT-SPI
            # method. Suppress only that metadata warning at the exact call.
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

    def fresh_owned_target(self, node):
        identity = public_automation_id(node)
        require(bool(identity), 'ui:unidentified-action-target')
        if owned_applications(identity) or identity.startswith('child-'):
            current = self.find_id(identity)
            require(current is not None and current == node, 'ui:wrong-action-owner')
            return current
        bindings = [(provider, surface, control)
                    for provider, contract in self.provider_contracts.items()
                    for surface, (_surface_id, controls) in contract.get('surfaces', {}).items()
                    for control, registered_id in controls.items() if registered_id == identity]
        require(len(bindings) == 1, 'ui:unregistered-or-ambiguous-action-target')
        current = self.find_provider_control(*bindings[0])
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
        application = self.id_target(PARENT_APPLICATION, showing=False)
        return self.id_target('about-dialog', root=application)

    def open_about(self, version):
        """ABOUT01: independent Parent entry; menu, About, text and license link."""
        self.activate_named(self.id_target('parent-menu-button',
                                          root=self.parent(), sensitive=True), 'menu.popup')
        self.activate(self.id_target('parent-menu-about', root=self.parent(), sensitive=True))
        root = self.about()
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        self.reveal_id('about-license-value', root=root)

    def reveal_id(self, identity, *, root):
        node = self.id_target(identity, root=root, showing=False)
        if not self.showing(node):
            surface = owned_surface_id(identity)
            require(surface is not None, 'ui:missing-reveal-surface')
            self.activate_named(self.id_target(surface), 'focus.' + identity)
        return self.id_target(identity)

    def read_document(self, root, projection, *, maximum):
        """UI03: only the bounded GPL heading projection; never return raw text."""
        require(projection == 'gpl-heading' and type(maximum) is int
                and 64 <= maximum <= 1024, 'ui:document-binding')
        _application_id, _surface_id, registered = self.require_provider_contract(
            'document-viewer', 'license-document', ('content', 'close'))
        require(public_automation_id(root) == registered['content']
                and self.find_provider_control(
                    'document-viewer', 'license-document', 'content') is root,
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
        return 'GNU GENERAL PUBLIC LICENSE' in value and 'Version 3, 29 June 2007' in value

    def license_content(self):
        """Read the ID-scoped registered viewer, without title discovery."""
        def document():
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
        self.require_provider_contract(
            'document-viewer', 'license-document', ('content', 'close'))
        self.activate(self.id_target('about-license-value', root=self.about(), sensitive=True))
        self.license_content()

    def window_ready_to_close(self, window):
        """UI01/02: fresh active named window before a worker's Alt-F4."""
        require(window in ('license', 'about'), 'ui:window-binding')
        def active():
            if window == 'license':
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
        if window == 'license':
            _application_id, surface_id, registered = self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
        def closed():
            if window == 'about':
                return self.absent_id('about-dialog', within='parent-window')
            nodes = list(self.nodes(strict=True))
            if not nodes:
                return False
            for node in nodes:
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-window')
            underlying = self.find_id('about-dialog', nodes=nodes)
            if underlying is None:
                return False
            external_ids = (surface_id, registered['content'], registered['close'])
            return not any(public_automation_id(node) in external_ids and self.showing(node)
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
        node = self.find_id(prefix + str(uid), nodes=nodes, showing=showing)
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
        selector = self.id_target(
            'parent-child-selector', root=self.parent(), sensitive=True,
        )
        self.activate_named(selector, 'child.focus-' + match.group(1))
        self.input_uncertain = True
        def focused():
            current = self.find_id(identity, root=self.parent())
            return (current is not None
                    and self.has_state(current, self.api.StateType.SENSITIVE)
                    and self.has_state(current, self.api.StateType.FOCUSED))
        result = self.wait(focused, 'focus')
        self.input_uncertain = False
        return result

    def open_child_picker(self, child):
        """UI15 opening: activate by ID and focus the UID-scoped choice by ID."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        picker = self.id_target(
            'parent-child-selector', root=self.parent(), sensitive=True,
        )
        self.activate_named(picker, 'menu.popup')
        popover = self.id_target('parent-child-popover', root=self.parent())
        choices = self.id_target('parent-child-choices', root=popover)
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
        self.activate(self.id_target(page_id, root=root, sensitive=True))
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
        """SEARCH04's ID-scoped registered launchable branch, without input."""
        require(product == PRODUCT, 'ui:search-binding')
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

    def terminal_input(self, *, focused=False):
        """FILE01/UI21: a unique terminal in its active application window.

        No previous launch is required. Overview and inactive/background windows
        cannot authorize input. Window titles may contain private shell paths;
        select by the provider's scoped public ID and never export those titles.
        """
        surface, registered = self.provider_surface(
            'terminal', 'terminal', ('input-output',))
        if surface is None:
            return None
        field = self.find_id(registered['input-output'], root=surface)
        if (field is None or field.get_role_name() != 'terminal'
                or not self.has_state(field, self.api.StateType.SENSITIVE)):
            return None
        if not self.has_state(surface, self.api.StateType.ACTIVE):
            return None
        if focused and not self.has_state(field, self.api.StateType.FOCUSED):
            return None
        return field

    def focus_terminal(self):
        # Application SCREEN extents are not reliable global coordinates on
        # Wayland. Focus the qualified public component without translating
        # its window-local geometry into framebuffer pointer input.
        require(not self.input_uncertain, 'ui:uncertain-input')
        field = self.fresh_owned_target(self.wait(self.terminal_input, 'terminal-input'))
        if not self.has_state(field, self.api.StateType.FOCUSED):
            component = field.get_component_iface()
            require(component is not None, 'ui:terminal-focus-unavailable')
            self.input_uncertain = True
            require(component.grab_focus(), 'ui:terminal-focus-refused')
        # Never retry the action, even if the resulting observation times out.
        self.wait(lambda: self.terminal_input(focused=True), 'terminal-focus')
        self.input_uncertain = False

    def help_terminal_text(self):
        """INFO02's bounded local projection; never export terminal contents."""
        field = self.terminal_input(focused=True)
        if field is None:
            return None
        text = field.get_text_iface()
        require(text is not None, 'ui:terminal-text-unavailable')
        count = self.api.Text.get_character_count(text)
        require(0 <= count <= 65536, 'ui:terminal-text-bound')
        # Only the current finite help/manual display and trailing shell prompt.
        return self.api.Text.get_text(text, max(0, count - 8192), count)

    @staticmethod
    def help_shell_prompt(value):
        import re
        # Fixture's normal shell prompt, read publicly and never retained.
        return bool(value and re.search(r'(?:^|\n)onpc-parent-jamie@[^\s:]+:[^\n]*\$\s*', value))

    def help_product_absent(self):
        surrounding = self.terminal_return_surface()
        self.management_absent(within=surrounding)
        for node in self.nodes(strict=True):
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-surface')
            if self.showing(node):
                require(public_automation_id(node) not in (
                    'kiosk-request-window', 'kiosk-request-form', 'feedback-dialog',
                    'parent-access-denied-window', 'startup-error-window'),
                    'ui:help-product-window')

    def terminal_return_surface(self):
        surface, registered = self.provider_surface(
            'terminal', 'terminal', ('input-output',))
        require(surface is not None and self.find_id(
            registered['input-output'], root=surface) is not None,
            'ui:terminal-return-unqualified')
        return public_automation_id(surface)

    def terminal_absent(self):
        """Complete ID-scoped absence of the registered terminal surface."""
        _application_id, surface_id, _registered = self.require_provider_contract(
            'terminal', 'terminal', ('input-output',))
        nodes = list(self.nodes(strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        return not any(public_automation_id(node) == surface_id and self.showing(node)
                       for node in nodes)

    def help_content(self, binding):
        import re
        require(binding in HELP_BINDINGS, 'ui:help-binding')
        command, kind, identity = HELP_BINDINGS[binding]
        value = self.help_terminal_text()
        if value is None:
            return False
        normalized = ' '.join(value.split())
        if kind == 'help':
            found = (re.search(r'(?:^|\n)usage: ' + re.escape(command) + r'\s', value)
                     and identity in normalized and '--help' in value
                     and 'show this help message and exit' in normalized
                     and self.help_shell_prompt(value))
        else:
            found = (command.upper() + '(1)' in value and identity in normalized
                     and all(section in value for section in ('NAME', 'SYNOPSIS', 'DESCRIPTION'))
                     and not self.help_shell_prompt(value))
        self.help_product_absent()
        return bool(found)

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
        surface, registered = self.provider_surface(
            'gnome-shell', 'desktop', ('desktop',))
        target = (self.find_id(registered['desktop'], root=surface)
                  if surface is not None else None)
        require(target is not None, 'ui:desktop')
        return target

    def session_menu_toggle(self):
        """DESK02 entry target, observed only through Shell's panel IDs."""
        self.desktop_result(PARENT, 'success')
        target = self.find_provider_control('gnome-shell', 'panel', 'quick-settings')
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:session-menu-toggle')
        return target

    def session_menu_power(self):
        """DESK02 power target, observed only in the ID-scoped open menu."""
        target = self.find_provider_control('gnome-shell', 'session-menu', 'power')
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:session-menu-power')
        return target

    def session_menu(self):
        """DESK02: observe Switch User and Log Out after Power Off Menu is open."""
        surface, registered = self.provider_surface(
            'gnome-shell', 'session-menu', ('switch-user', 'log-out'))
        require(surface is not None, 'ui:session-menu')
        for logical in ('switch-user', 'log-out'):
            target = self.find_id(registered[logical], root=surface)
            require(target is not None and self.has_state(
                target, self.api.StateType.SENSITIVE),
                    'ui:session-menu')

    def choose_session_action(self, action):
        """Observe one exact ID-scoped action; legacy input routes refuse."""
        require(action in SESSION_ACTION_NAMES, 'ui:session-action-binding')
        logical = {'switch-user': 'switch-user', 'logout': 'log-out'}[action]
        target = self.find_provider_control('gnome-shell', 'session-menu', logical)
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:session-action')
        return target

    def logout_confirm(self):
        """DESK04 confirmation target, distinct by provider surface and ID."""
        target = self.find_provider_control('gnome-shell', 'logout-dialog', 'confirm')
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:logout-confirm')
        return target

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
                    'account-choice::station', 'selected-recipient', 'password')
        return all(type(registered.get(control)) is str and registered[control]
                   for control in required)

    @staticmethod
    def gdm_semantic_name(node):
        return ' '.join(node.get_name().split())

    def gdm_semantic_owner(self):
        """Resolve the one Shell application on the active greeter bus.

        This is the deliberately narrow provider-specific exception for G01.
        It is not a generic name/role selector: the standalone process is bound
        to the sole active local greeter account before this tree is read.
        """
        desktop = self.api.get_desktop(0)
        require(desktop is not None, 'ui:incomplete-tree')
        nodes = list(self.nodes(desktop, strict=True))
        owners = [node for node in nodes
                  if node.get_parent() == desktop
                  and node.get_role_name() == 'application'
                  and self.gdm_semantic_name(node).casefold()
                  in GDM_SEMANTIC_APPLICATION_NAMES]
        require(len(owners) == 1, 'ui:gdm-provider-owner')
        return owners[0]

    def gdm_semantic_nodes(self):
        owner = self.gdm_semantic_owner()
        nodes = list(self.nodes(owner, strict=True))
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
                'station': matches((KIOSK, KIOSK_USERNAME)),
            },
        }

    def gdm_semantic_rows(self):
        """Return the unique ordinary and station rows in a complete list."""
        owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        require(not any(node.get_role_name() == 'password text' for node in showing),
                'ui:gdm-list-prompt-overlap')

        ordinary = self.gdm_semantic_account_rows(owner, showing, (PARENT,))
        station = self.gdm_semantic_account_rows(
            owner, showing, (KIOSK, KIOSK_USERNAME))
        if ((len(ordinary) != 1 or len(station) != 1
                or (ordinary and station and ordinary[0] == station[0]))
                and not self.gdm_row_diagnostic_emitted):
            print(json.dumps(self.gdm_semantic_row_diagnostic(owner), sort_keys=True),
                  file=sys.stderr, flush=True)
            self.gdm_row_diagnostic_emitted = True
        require(len(ordinary) == 1 and len(station) == 1,
                'ui:gdm-account-cardinality')
        require(ordinary[0] != station[0], 'ui:gdm-account-cardinality')
        for row in (*ordinary, *station):
            require(self.has_state(row, self.api.StateType.SENSITIVE),
                    'ui:gdm-account-unavailable')
        return owner, {PARENT: ordinary[0], KIOSK: station[0]}

    def gdm_nonsecret_account(self, name):
        require(name in (PARENT, KIOSK), 'ui:gdm-nonsecret-binding')
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_list(name)
        _owner, rows = self.gdm_semantic_rows()
        return rows[name]

    def gdm_nonsecret_navigation(self, name):
        """Focus one fresh G01 row without deriving input from list position."""
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_navigation(name)
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.gdm_nonsecret_account(name)
        current = self.gdm_nonsecret_account(name)
        require(current == target, 'ui:gdm-stale-focus')
        component = current.get_component_iface()
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

    def gdm_nonsecret_prompt(self):
        """Observe Parent's prompt without reading or authorizing its secret."""
        if self.gdm_nonsecret_has_id_route():
            self.greeter_prompt()
            return
        owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        account_rows = self.gdm_semantic_account_rows(
            owner, showing, (PARENT, KIOSK, KIOSK_USERNAME))
        require(not account_rows, 'ui:gdm-list-prompt-overlap')
        recipients = [node for node in showing
                      if node.get_role_name() == 'label'
                      and self.gdm_semantic_name(node) == PARENT]
        fields = [node for node in showing
                  if node.get_role_name() == 'password text']
        require(len(recipients) == 1, 'ui:gdm-recipient')
        require(len(fields) == 1
                and self.has_state(fields[0], self.api.StateType.SENSITIVE)
                and self.has_state(fields[0], self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')

    def station_entry_branch(self, owner):
        """Read the offered branch without selecting or dismissing any control."""
        require(owner in ('greeter', 'station'), 'ui:station-branch-owner')
        if owner == 'station':
            def destination():
                nodes = list(self.nodes(strict=True))
                require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                for node in nodes), 'ui:station-stale-tree')
                window = self.find_id('kiosk-request-window', nodes=nodes)
                if window is None:
                    return None
                form = self.find_id('kiosk-request-form', root=window)
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

    def greeter_prompt(self):
        # This observation submits no secret and cannot authorize one.
        surface, registered = self.provider_surface(
            'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
        require(surface is not None, 'ui:gdm-surface')
        recipient = self.find_id(registered['selected-recipient'], root=surface)
        require(recipient is not None and ' '.join(recipient.get_name().split()) == PARENT,
                'ui:gdm-recipient')
        self.observe_absence('greeter', 'account', name=PARENT, mode='snapshot')
        field = self.find_id(registered['password'], root=surface)
        require(field is not None and field.get_role_name() == 'password text'
                and self.has_state(field, self.api.StateType.SENSITIVE)
                and self.has_state(field, self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')

    def kiosk_request_form(self):
        """Read REQUEST03's fixed disabled-child station state."""
        last_reset = None
        diagnostic = {'form_count': 0}

        def fresh_reader():
            nonlocal last_reset
            now = time.monotonic()
            if self.reset_observer is not None and (last_reset is None or now - last_reset >= 2):
                # Drop only this reader's stale accessibility objects when the
                # graphical session changes. Never start or inspect services.
                self.reset_observer()
                last_reset = now

        def observe():
            try:
                public_nodes = list(self.nodes(strict=True))
                diagnostic_ids = (
                    'kiosk-request-form', 'kiosk-child-selector',
                    'kiosk-approver-selector', 'kiosk-request-submit',
                    'kiosk-request-cancel', 'kiosk-soft-apps-toggle',
                    'kiosk-screen-limit-notice', 'kiosk-mute-button',
                )
                diagnostic['public_ids'] = {
                    identity: sum(
                        public_automation_id(node) == identity and self.showing(node)
                        for node in public_nodes
                    )
                    for identity in diagnostic_ids
                }
            except self.query_errors:
                fresh_reader()
                return None

            application = self.find_id(KIOSK_APPLICATION, nodes=public_nodes, showing=False)
            form = (self.find_id('kiosk-request-form', root=application, nodes=public_nodes)
                    if application is not None else None)
            diagnostic['form_count'] = int(form is not None)
            if form is None:
                fresh_reader()
                return None

            # A matching ID in another window must never fill a missing field
            # in this form. Keep a complete fresh read for absence checks too.
            form_nodes = list(self.nodes(form, strict=True))
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in form_nodes), 'ui:stale-request-form')
            child = self.find_id('kiosk-child-selector', nodes=form_nodes)
            approver = self.find_id('kiosk-approver-selector', nodes=form_nodes)
            request = self.find_id('kiosk-request-submit', nodes=form_nodes)
            cancel = self.find_id('kiosk-request-cancel', nodes=form_nodes)
            allow_soft = self.find_id('kiosk-soft-apps-toggle', nodes=form_nodes)
            if None in (child, approver, request, cancel, allow_soft):
                return None

            def selected_identity(control, label, identities, code):
                namespace = 'child' if identities == CHILD_IDENTITIES else 'approver'
                accounts = CHILD_ACCOUNTS if namespace == 'child' else APPROVER_ACCOUNTS
                selected_nodes = [node for node in self.nodes(control, strict=True)
                                  if public_automation_id(node).startswith(f'kiosk-{namespace}-selected-')
                                  and self.showing(node)]
                require(len(selected_nodes) == 1, 'ui:' + code)
                selected = []
                for name, canonical in identities.items():
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
                    node = self.find_id(f'kiosk-{namespace}-selected-{uid}', root=control)
                    if node is not None and node == selected_nodes[0]:
                        selected.append((name, canonical))
                require(len(selected) == 1, 'ui:' + code)
                name, canonical = selected[0]
                description = ' '.join(control.get_description().split())
                require(description == f'Selected {label.casefold()}: {name}.', 'ui:' + code)
                return canonical

            duration_ids = (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')
            durations = [
                self.find_id(f'kiosk-duration-{identity}', nodes=form_nodes)
                for identity in duration_ids
            ]
            if any(button is None for button in durations):
                return None
            selected = [index for index, button in enumerate(durations)
                        if self.has_state(button, self.api.StateType.PRESSED)]
            diagnostic['durations'] = {
                str(identity): {
                    'role': button.get_role_name(),
                    'checked': self.has_state(button, self.api.StateType.CHECKED),
                    'pressed': self.has_state(button, self.api.StateType.PRESSED),
                    'sensitive': self.has_state(button, self.api.StateType.SENSITIVE),
                }
                for identity, button in zip(duration_ids, durations)
            }
            require(selected == [2], 'ui:kiosk-duration-selection')
            require(not any(self.has_state(button, self.api.StateType.SENSITIVE)
                            for button in durations), 'ui:kiosk-duration-availability')

            notice = self.find_id('kiosk-screen-limit-notice', nodes=form_nodes)
            if notice is None:
                return None
            message = ' '.join(notice.get_name().split())
            require(message == 'Screen limit is not enabled in Parent App',
                    'ui:kiosk-disabled-message')
            custom = self.find_id('kiosk-custom-duration', nodes=form_nodes)
            require(self.find_id('kiosk-mute-button', nodes=public_nodes) is None,
                    'ui:kiosk-mute-present')
            return {
                'surface': 'kiosk', 'form_count': 1,
                'child': selected_identity(
                    child, 'Child account', CHILD_IDENTITIES, 'kiosk-child'),
                'approver': selected_identity(
                    approver, 'Approving parent', APPROVER_IDENTITIES,
                    'kiosk-approver'),
                'duration_seconds': 1800,
                'custom_text': None if custom is None else 'unexpected-visible-value',
                'allow_soft': self.has_state(allow_soft, self.api.StateType.CHECKED),
                'child_selector_enabled': self.has_state(child, self.api.StateType.SENSITIVE),
                'approver_selector_enabled': self.has_state(approver, self.api.StateType.SENSITIVE),
                'duration_enabled': False,
                'soft_choice_enabled': self.has_state(allow_soft, self.api.StateType.SENSITIVE),
                'request_enabled': self.has_state(request, self.api.StateType.SENSITIVE),
                'cancel_enabled': self.has_state(cancel, self.api.StateType.SENSITIVE),
                'message': 'screen-limit-disabled', 'mute': None,
            }
        try:
            return self.wait(observe, 'kiosk-request-form')
        except UiError:
            print(json.dumps({'event': 'kiosk-form-observation', **diagnostic}, sort_keys=True),
                  file=sys.stderr, flush=True)
            raise

    def password_recipient(self, name):
        """Read only public identity, masked role, focus and empty length.

        Never read password text or children. A false/stale observation cannot
        authorize typing. The caller also requires a separate fresh recheck.
        """
        require(name in GREETER_IDENTITIES, 'ui:gdm-account-binding')
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

    def search_ready(self, surface, *, focused=False):
        """SEARCH01/UI21: read the empty field, optionally its independent focus."""
        require(surface == 'overview' and type(focused) is bool, 'ui:search-binding')
        def ready():
            if not self.search_query(''):
                return False
            surface, registered = self.provider_surface(
                'gnome-shell', 'app-grid', ('search',))
            field = (self.find_id(registered['search'], root=surface)
                     if surface is not None else None)
            return field if field is not None and (not focused or self.has_state(
                field, self.api.StateType.FOCUSED)) else False
        return self.wait_search(ready, 'standard-search-focus' if focused else 'standard-search-ready')

    def focus_search_field(self):
        """Focus the ID-addressed provider search field without pointer geometry."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid', ('search',))
        require(surface is not None, 'ui:search-surface')
        field = self.find_id(registered['search'], root=surface)
        require(field is not None and self.has_state(field, self.api.StateType.SENSITIVE),
                'ui:search-field')
        field = self.fresh_owned_target(field)
        component = field.get_component_iface()
        require(component is not None, 'ui:search-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:search-focus-refused')
        def focused():
            current = self.find_provider_control('gnome-shell', 'app-grid', 'search')
            return current is not None and self.has_state(
                current, self.api.StateType.FOCUSED)
        self.wait(focused, 'standard-search-focus')
        self.input_uncertain = False

    def focus_search_result(self):
        """Qualify the exact launcher recipient before the worker sends Enter."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        self.wait(lambda: self.search_query(PRODUCT), 'parent-search-query')
        target = self.wait(lambda: self.launchable_result(PRODUCT), 'parent-search-result')
        target = self.fresh_owned_target(target)
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
        self.require_provider_contract(
            'gnome-shell', 'app-grid',
            ('search', 'result::parent', 'web-suggestion::parent'))
        def observed():
            nonlocal stable_since
            try:
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
            except self.query_errors:
                stable_since = None
                self.search_status = 'incomplete-read'
                raise
        return self.wait_search(observed, 'standard-parent-unavailable')

    def wait_search(self, predicate, code):
        try:
            return self.wait(predicate, code)
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

    def _provider_kind_from_ids(self, application, surface):
        """Use provider IDs when both available, without requiring control IDs."""
        application_id = public_automation_id(application)
        surface_id = public_automation_id(surface)
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

    def system_prompt_kind(self):
        """Read one complete tree and classify a visible authentication modal.

        This is the provider-specific G02 adapter.  It recognizes only the
        fixed English provider semantics used by the prepared Ubuntu image, or
        a provider's application/surface IDs when both are available.  It does
        not resolve an input control and cannot authorize an action.
        """
        desktop = self.api.get_desktop(0)
        require(desktop is not None, 'ui:incomplete-tree')
        nodes = list(self.nodes(desktop, strict=True))
        require(nodes, 'ui:incomplete-tree')
        provider_application_ids = {
            contract.get('application_id')
            for provider, contract in self.provider_contracts.items()
            if provider in ('mate-polkit-agent', 'gnome-shell-polkit-agent',
                            'gcr-keyring-prompter') and contract.get('application_id')
        }
        applications = [node for node in nodes
                        if node.get_role_name() == 'application'
                        or public_automation_id(node) in provider_application_ids]
        candidates = []
        for application in applications:
            application_nodes = list(self.nodes(application, strict=True))
            application_kind = self._prompt_application_kind(application.get_name())
            owned = bool(public_automation_id(application) in (
                PARENT_APPLICATION, KIOSK_APPLICATION, CHILD_APPLICATION,
                WATCH_APPLICATION, UI_WATCH_APPLICATION))
            for surface in application_nodes:
                if surface is application or not self.showing(surface):
                    continue
                descendants = list(self.nodes(surface, strict=True))
                password = any(node.get_role_name() == 'password text'
                               for node in descendants)
                prompt_title = self._prompt_title(surface.get_name())
                id_kind = self._provider_kind_from_ids(application, surface)
                modal = (surface.get_role_name() in ('alert', 'dialog')
                         or self.has_state(surface, self.api.StateType.MODAL)
                         or id_kind is not None)
                if not modal:
                    continue
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

    def handle_system_prompt(self):
        """Recognize and refuse session prompts without delivering input."""
        if not self.prompt_enabled or self.handling_prompt:
            return
        self.handling_prompt = True
        try:
            kind = self.system_prompt_kind()
            if kind is not None:
                require(self.prompt_session in ('station', 'desktop'),
                        'ui:system-prompt-session')
                raise UiError('ui:system-prompt-refused:' + self.prompt_session + ':' + kind)
        except self.query_errors:
            raise UiError('ui:system-prompt-observation-failed') from None
        finally:
            self.handling_prompt = False

    def run(self, operation, version):
        require(operation in OPERATIONS, 'ui:operation')
        self.prompt_enabled = operation not in GREETER_OPERATIONS and operation != 'station-entry-branch'
        self.prompt_session = ('station' if operation in KIOSK_OPERATIONS else
                               None if operation in GREETER_OPERATIONS else 'desktop')
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'station-entry-branch':
            result['branch'] = self.station_entry_branch(self.branch_owner)
        elif operation in GREETER_OPERATIONS:
            if operation in ('gdm-wrong-recipient-refused', 'gdm-standard-wrong-recipient-refused'):
                self.wait(lambda: self.password_recipient(OTHER_PARENT), 'gdm-other-recipient')
                name = EXISTING_CHILD if operation == 'gdm-standard-wrong-recipient-refused' else PARENT
                require(not self.password_recipient(name), 'ui:gdm-wrong-recipient-accepted')
            elif operation in ('gdm-parent-recipient', 'gdm-parent-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(PARENT), 'gdm-parent-recipient')
            elif operation in ('gdm-standard-recipient', 'gdm-standard-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(EXISTING_CHILD), 'gdm-standard-recipient')
            elif operation == 'gdm-select-parent':
                self.greeter_prompt()
            elif operation == 'gdm-station-wrong-entry-refused':
                self.gdm_nonsecret_prompt()
            elif operation in ('gdm-focused', 'gdm-other-focused', 'gdm-standard-focused',
                              'gdm-station-focused'):
                name = OTHER_PARENT if operation == 'gdm-other-focused' else PARENT
                if operation == 'gdm-standard-focused':
                    name = EXISTING_CHILD
                if operation == 'gdm-station-focused':
                    name = KIOSK
                account = (self.gdm_nonsecret_account if operation in GDM_NONSECRET_OPERATIONS
                           else self.greeter_list)
                self.wait(lambda: self.has_state(account(name), self.api.StateType.FOCUSED),
                          'gdm-account-focus')
            elif operation in GREETER_NAVIGATION:
                name = OTHER_PARENT if operation == 'gdm-other-list' else PARENT
                if operation == 'gdm-standard-list':
                    name = EXISTING_CHILD
                if operation == 'gdm-station-list':
                    name = KIOSK
                navigation = (self.gdm_nonsecret_navigation
                              if operation in GDM_NONSECRET_OPERATIONS
                              else self.greeter_navigation)
                result['focused'] = navigation(name)
            else:
                self.greeter_list()
        elif operation in ('desktop', 'standard-desktop'):
            self.desktop_result(PARENT if operation == 'desktop' else EXISTING_CHILD, 'success')
        elif operation == 'help-system-prompt':
            self.desktop_result(PARENT, 'success')
        elif operation == 'help-terminal-input':
            self.wait(self.terminal_input, 'terminal-input')
        elif operation == 'help-terminal-focused':
            self.focus_terminal()
            self.wait(lambda: self.help_shell_prompt(self.help_terminal_text()), 'help-shell-ready')
        elif operation == 'help-terminal-wrong-surface':
            self.desktop_result(PARENT, 'success')
            require(self.help_terminal_text() is None, 'ui:help-wrong-surface')
        elif operation == 'help-terminal-closed':
            self.desktop_result(PARENT, 'success')
            self.wait(self.terminal_absent, 'terminal-closed')
        elif operation == 'help-shell-ready':
            self.wait(lambda: self.help_shell_prompt(self.help_terminal_text()), 'help-shell-ready')
            self.help_product_absent()
        elif operation.startswith('help-content-'):
            self.wait(lambda: self.help_content(operation.removeprefix('help-content-')), 'help-content')
        elif operation == 'standard-system-prompt':
            self.desktop_result(EXISTING_CHILD, 'success')
        elif operation == 'standard-terminal-input':
            self.wait(self.terminal_input, 'terminal-input')
        elif operation == 'standard-terminal-focused':
            self.focus_terminal()
        elif operation == 'standard-terminal-wrong-surface':
            # Positive desktop evidence makes a missing terminal meaningful.
            self.desktop_result(EXISTING_CHILD, 'success')
            require(self.terminal_input(focused=True) is None, 'ui:terminal-wrong-surface')
        elif operation == 'standard-terminal-closed':
            self.desktop_result(EXISTING_CHILD, 'success')
            self.wait(self.terminal_absent, 'terminal-closed')
        elif operation == 'standard-management-denied':
            self.management_denied()
        elif operation == 'standard-denial-closed':
            surrounding = self.terminal_return_surface()
            self.wait(lambda: self.absent_id('parent-access-denied-window', within=surrounding),
                      'denial-closed')
            self.management_absent(within=surrounding)
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
        elif operation == 'parent-search-ready':
            self.search_ready('overview')
        elif operation == 'parent-search-focused':
            self.focus_search_field()
            self.search_ready('overview', focused=True)
        elif operation == 'parent-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'parent-search-entered')
        elif operation == 'app-grid':
            self.focus_search_result()
        elif operation == 'parent-window':
            self.parent()
        elif operation == 'parent-empty':
            self.parent_empty()
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
        elif operation == 'license':
            self.open_license()
            self.window_ready_to_close('license')
        elif operation == 'license-closed':
            self.window_closed('license', 'about')
        elif operation == 'about-returned':
            self.window_closed('license', 'about')
            self.about_footer()
            self.window_ready_to_close('about')
        elif operation == 'parent-returned':
            self.window_closed('about', 'parent')
            result['settings'] = self.settings()
        elif operation == 'session-menu-toggle':
            self.activate(self.session_menu_toggle())
        elif operation == 'session-menu-power':
            self.activate(self.session_menu_power())
        elif operation == 'session-menu':
            self.session_menu()
        elif operation in SESSION_ACTION_NAMES:
            self.activate(self.choose_session_action(operation))
        elif operation == 'logout-confirm':
            self.activate(self.logout_confirm())
        elif operation == 'kiosk-request-form':
            result['request'] = self.kiosk_request_form()
        return result


def greeter_account(*, station_branch=False):
    """Resolve the sole active local greeter via public logind session metadata.

    Modern GDM can use a dynamic account instead of the legacy gdm UID. This
    selects only the public UI connection identity; it proves no product result.
    """
    # Installed boots gate GDM on enforcement readiness. Snapshot consumers
    # enter here directly after SSH, without the former setup boot-complete
    # wait. Observe the public greeter within its own finite boot budget.
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
        if found:
            if station_branch:
                return pwd.getpwuid(found[0][0]), found[0][1]
            return pwd.getpwuid(found[0])
        # SSH can become ready before GDM after an installed snapshot boots.
        # Retry only absence, never an ambiguous identity or a failed read.
        time.sleep(min(.2, remaining))


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
    if operation in KIOSK_OPERATIONS:
        runtime = '/run/user/' + str(account.pw_uid)
        return {'XDG_RUNTIME_DIR': runtime,
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + runtime + '/bus'}
    return session_environment(account)


def main():
    require(len(sys.argv) == 3 and sys.argv[1] in OPERATIONS, 'ui:arguments')
    greeter = sys.argv[1] in GREETER_OPERATIONS
    kiosk = sys.argv[1] in KIOSK_OPERATIONS
    require(os.geteuid() == 0, 'ui:fixture-identity')
    branch_owner = None
    if sys.argv[1] == 'station-entry-branch':
        account, branch_owner = greeter_account(station_branch=True)
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
