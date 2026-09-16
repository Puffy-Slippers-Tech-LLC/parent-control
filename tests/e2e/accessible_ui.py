"""Bounded public AT-SPI interaction in the installed fixture's desktop.

This file also runs as a standalone program in the guarded guest. It reads only
public UI objects; it never imports product code or reads product storage/buses.
Only fixed operation names and sanitized results cross the controller boundary.
"""

import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import time


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
})
STANDARD_OPERATIONS = frozenset({
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
})
PRODUCT = 'Oh No! Parent Control'
LICENSE_LINK = 'GNU General Public License v3.0'
ABOUT_FOOTER = '© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.'
CHILD = 'Riley (Child)'
EXISTING_CHILD = 'Jordan (Child)'
NEW_CHILD = 'Morgan (Child)'
CHILD_IDENTITIES = {CHILD: 'fixture-child', EXISTING_CHILD: 'existing-fixture-child',
                    NEW_CHILD: 'new-fixture-child'}
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
GREETER_IDENTITIES = {PARENT: 'parent', OTHER_PARENT: 'other-parent',
                      CHILD: 'child', EXISTING_CHILD: 'other-child'}
GREETER_OPERATIONS = frozenset({'gdm-list', 'gdm-focused', 'gdm-select-parent', 'gdm-dismissed', 'gdm-returned',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked'})
GREETER_NAVIGATION = frozenset({'gdm-list', 'gdm-other-list', 'gdm-standard-list'})
KEYRING_LABELS = (
    'Unlock Login Keyring',
    'The login keyring did not get unlocked when you logged into your computer.',
    'The password you use to log in to your computer no longer matches that of your login keyring.',
)


class UiError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise UiError(code)


class AccessibleUI:
    """Fresh semantic lookup, bounded waits, unique targets and public actions.

    Appearance/coordinates are deliberately absent from the acceptance model.
    Hidden or disabled controls cannot authorize input. An action's return value
    is not success: callers must independently observe its resulting UI state.
    """

    def __init__(self, api, *, timeout=45, query_errors=(), dispatch=None, system_prompt=None):
        self.api = api
        self.timeout = timeout
        self.query_errors = query_errors
        self.dispatch = dispatch
        self.last_roles = set()
        self.system_prompt = system_prompt
        self.prompt_enabled = False
        self.handling_prompt = False
        self.prompt_count = 0

    def nodes(self, root=None, *, strict=False):
        root = root if root is not None else self.api.get_desktop(0)
        pending = [root]
        visited = 0
        seen = set()
        while pending:
            node = pending.pop()
            if node is None:
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
                yield node
                # Never traverse editable text, including a revealed password.
                if node.get_role_name() not in ('password text', 'text', 'entry'):
                    pending.extend(node.get_child_at_index(i)
                                   for i in reversed(range(node.get_child_count())))
            except self.query_errors:
                if strict:
                    raise
                # A dead unrelated subtree must not hide live controls.
                continue

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
        found = []
        self.last_roles = set()
        for node in self.nodes(root):
            try:
                label = ' '.join(node.get_name().split())
                if name is not None and label != ' '.join(name.split()):
                    continue
                if contains is not None and contains not in label:
                    continue
                role = node.get_role_name()
                if name is not None or contains is not None:
                    safe_roles = {'button', 'push button', 'toggle button', 'label', 'icon',
                                  'text', 'entry', 'panel', 'frame', 'dialog', 'link', 'combo box',
                                  'list box', 'list item', 'menu item', 'check box', 'switch'}
                    self.last_roles.add(role if role in safe_roles else 'other')
                if roles and role not in roles:
                    continue
                if showing and not self.showing(node):
                    continue
                if not showing and not node.get_state_set().contains(self.api.StateType.VISIBLE):
                    continue
                if sensitive and not node.get_state_set().contains(self.api.StateType.SENSITIVE):
                    continue
                if editable and not node.get_state_set().contains(self.api.StateType.EDITABLE):
                    continue
            except self.query_errors:
                continue
            found.append(node)
        require(len(found) <= 1, 'ui:ambiguous-target')
        return found[0] if found else None

    def wait(self, predicate, code):
        deadline = time.monotonic() + self.timeout
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
            if value:
                return value
            if time.monotonic() >= deadline:
                raise UiError('ui:timeout:' + code)
            time.sleep(.2)

    def target(self, name=None, roles=(), **kwargs):
        try:
            return self.wait(lambda: self.find(name, roles, **kwargs), 'target')
        except UiError as error:
            if str(error) == 'ui:timeout:target':
                raise UiError('ui:timeout:target:roles=' + ','.join(sorted(self.last_roles))) from None
            raise

    def activate(self, node):
        self.handle_system_prompt()
        require(self.showing(node) and node.get_state_set().contains(self.api.StateType.SENSITIVE),
                'ui:unusable-target')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-action')
        count = self.api.Action.get_n_actions(action)
        require(count == 1, 'ui:missing-or-ambiguous-action')
        require(self.api.Action.do_action(action, 0), 'ui:action-refused')

    def reveal(self, name, roles, *, root):
        """Scroll existing content into view through the public UI interface."""
        self.scroll_target(name, roles, root=root)
        return self.target(name, roles, root=root)

    def scroll_target(self, name, roles, *, root):
        """UI23: one public scroll request, without asserting its result."""
        node = self.target(name, roles, root=root, showing=False)
        if not self.showing(node):
            component = node.get_component_iface()
            require(component is not None and component.scroll_to(self.api.ScrollType.ANYWHERE),
                    'ui:scroll-refused')

    def find_labelled_button(self, name, *, root=None):
        """One fresh lookup by button name or its showing label's ancestry."""
        button = self.find(name, ('button', 'push button'), sensitive=True, root=root)
        if button is not None:
            return button
        node = self.find(name, ('label',), root=root)
        for _ in range(16):
            if node is None or node == root:
                return None
            if node.get_role_name() in ('button', 'push button'):
                return node if self.showing(node) and self.has_state(
                    node, self.api.StateType.SENSITIVE) else None
            node = node.get_parent()
        return None

    def labelled_button(self, name):
        return self.wait(lambda: self.find_labelled_button(name), 'labelled-button')

    def parent(self):
        return self.target(PRODUCT, ('frame',))

    def about(self):
        return self.target('About', ('frame', 'dialog'))

    def open_about(self, version):
        """ABOUT01: independent Parent entry; menu, About, text and license link."""
        self.activate(self.target('Parent app menu', ('toggle button',),
                                  root=self.parent(), sensitive=True))
        self.activate(self.target('About', ('button', 'push button'),
                                  root=self.parent(), sensitive=True))
        root = self.about()
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        self.reveal(LICENSE_LINK, ('link',), root=root)

    def read_document(self, root, projection, *, maximum):
        """UI03: only the bounded GPL heading projection; never return raw text."""
        require(projection == 'gpl-heading' and type(maximum) is int
                and 64 <= maximum <= 1024, 'ui:document-binding')
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
        """Read the actual named viewer, without opening or repairing it."""
        def document():
            frame = self.find(roles=('frame',), contains='LICENSE')
            if frame is None:
                return False
            return any(self.read_document(node, 'gpl-heading', maximum=1024)
                       for node in self.nodes(frame)
                       if self.showing(node) and node.get_role_name() in ('text', 'document text'))
        return self.wait(document, 'license-content')

    def open_license(self):
        """ABOUT02: one link action followed by actual viewer content."""
        self.activate(self.target(LICENSE_LINK, ('link',), root=self.about(), sensitive=True))
        self.license_content()

    def window_ready_to_close(self, window):
        """UI01/02: fresh active named window before a worker's Alt-F4."""
        require(window in ('license', 'about'), 'ui:window-binding')
        def active():
            root = (self.find(roles=('frame',), contains='LICENSE') if window == 'license'
                    else self.find('About', ('frame', 'dialog')))
            return root is not None and self.has_state(root, self.api.StateType.ACTIVE)
        self.wait(active, 'active-' + window)

    def window_closed(self, window, destination):
        """UI11: complete fresh absence within the positively recognized return UI."""
        require((window, destination) in (('license', 'about'), ('about', 'parent')),
                'ui:window-binding')
        def closed():
            nodes = list(self.nodes(strict=True))
            if not nodes:
                return False
            present = False
            underlying = False
            for node in nodes:
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-window')
                if node.get_role_name() not in ('frame', 'dialog') or not self.showing(node):
                    continue
                name = node.get_name()
                present |= ('LICENSE' in name if window == 'license' else name == 'About')
                underlying |= name == ('About' if destination == 'about' else PRODUCT)
            return underlying and not present
        self.wait(closed, window + '-close')

    def about_footer(self):
        """ABOUT04's public reveal/read, in an independently opened About window."""
        self.reveal(ABOUT_FOOTER, ('label',), root=self.about())
        self.read_label(self.about(), 'about-footer', maximum=80)

    def settings(self, child=CHILD):
        """PARENT03: explicit child, public settings; no scenario expectations."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        root = self.parent()
        picker = self.target(roles=('combo box',), root=root, sensitive=True)
        self.read_label(picker, 'child', expected=child, maximum=80)
        toggle = self.target('Screen time limit', ('switch',), root=root, sensitive=True)
        allowance = self.target('Daily time allowance', ('button', 'push button'),
                                root=root)
        labels = self.read_label(allowance, 'allowance', maximum=80)
        if child in (EXISTING_CHILD, NEW_CHILD):
            self.reveal("Today's Remaining Time", ('label',), root=root)
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
            self.target(label, ('label',), root=root)
            return True
        if projection == 'search-query':
            require(expected in ('', PRODUCT[:1], PRODUCT) and len(expected) <= maximum,
                    'ui:search-binding')
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
            label = 'Search "' + expected + '" on the web'
            require(len(label) <= maximum, 'ui:text-bound')
            return self.find(label, ('label',), root=root) is not None
        if projection == 'empty-explanation':
            text = 'No interactive non-administrator account was found.'
            require(len(text) <= maximum, 'ui:text-bound')
            return self.find(text, ('label',), root=root) is not None
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
            self.target(expected, ('label',), root=root)
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
            root = self.find(PRODUCT, ('frame',))
            if root is None:
                return False
            picker = self.find(roles=('combo box',), root=root)
            return (picker is not None
                    and self.read_label(root, 'empty-explanation', maximum=80)
                    and self.read_label(picker, 'empty-picker', maximum=80))
        self.wait(empty, 'parent-empty')

    def open_child_picker(self, child):
        """UI15 opening: activate once, then independently collect current order."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        picker = self.target(roles=('combo box',), root=self.parent(), sensitive=True)
        self.activate(self.target(roles=('toggle button',), root=picker, sensitive=True))
        return self.wait(lambda: self.child_navigation(child), 'child-choice')

    def child_navigation(self, child):
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        root = self.find(PRODUCT, ('frame',))
        if root is None:
            return None
        listing = self.find(roles=('list box',), root=root)
        if listing is None or self.find(child, ('label',), root=listing) is None:
            return None
        choices = self.choice_order(listing, identities=CHILD_IDENTITIES,
                                    maximum=32, cardinality=(1, 32), projection='child-picker-order')
        identity = CHILD_IDENTITIES[child]
        require(choices.count(identity) == 1, 'ui:choice-identity')
        label = self.target(child, ('label',), root=listing)
        row = label
        for _ in range(16):
            if row is None or row == listing or row.get_role_name() == 'list item':
                break
            row = row.get_parent()
        require(row is not None and row.get_role_name() == 'list item'
                and self.has_state(row, self.api.StateType.SENSITIVE), 'ui:unusable-choice')
        return ['home'] + ['down'] * choices.index(identity)

    def child_highlighted(self, child):
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        def highlighted():
            root = self.find(PRODUCT, ('frame',))
            if root is None:
                return False
            listing = self.find(roles=('list box',), root=root)
            if listing is None:
                return False
            row = self.find(child, ('label',), root=listing)
            for _ in range(16):
                if row is None or row == root:
                    return False
                if row.get_role_name() == 'list item':
                    return (self.showing(row) and self.has_state(row, self.api.StateType.SENSITIVE)
                            and self.has_state(row, self.api.StateType.SELECTED))
                row = row.get_parent()
            return False
        return self.wait(highlighted, 'choice-highlight')

    def selected_child(self, child):
        """UI15 closed-picker result followed by PARENT03, after caller's Enter."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        self.observe_absence('parent', 'child-popup', name=child, mode='snapshot')
        return self.settings(child)

    def parent_page(self, child, page):
        """PARENT04: select the declared page and observe its usable controls."""
        require(child in CHILD_IDENTITIES and page in ('Screen Limits', 'App Limits'),
                'ui:page-binding')
        print('ui:parent-page=started', file=sys.stderr, flush=True)
        root = self.parent()
        picker = self.target(roles=('combo box',), root=root, sensitive=True)
        self.read_label(picker, 'child', expected=child, maximum=80)
        self.activate(self.target(page, ('page tab',), root=root, sensitive=True))
        print('ui:parent-page=activated', file=sys.stderr, flush=True)
        if page == 'Screen Limits':
            return self.selected_child(child)
        # Reacquire once after the page transition. Local target roots can be
        # shared within this invocation; scanning the entire installed catalogue
        # again for every filter needlessly exhausts the observation deadline.
        root = self.parent()
        self.target('Search installed apps', ('text', 'entry'), root=root, sensitive=True)
        print('ui:parent-page=search-ready', file=sys.stderr, flush=True)
        self.reveal('Filter Access Rule', ('button', 'push button'), root=root)
        self.reveal('Filter Match Rule', ('button', 'push button'), root=root)
        print('ui:parent-page=filters-ready', file=sys.stderr, flush=True)

    def launchable_result(self, product):
        """SEARCH04's registered launchable branch, without launching."""
        require(product == PRODUCT, 'ui:search-binding')
        return self.labelled_button(product)

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
        return self.target('Activities', ('toggle button', 'button', 'push button'))

    def greeter_list(self, name=PARENT):
        # GDM01: the positive account surface and absence must be fresh together.
        self.observe_absence('greeter', 'password', name=name, mode='snapshot')
        return self.labelled_button(name)

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
                picker = self.target(roles=('combo box',), root=root, sensitive=True)
                self.read_label(picker, 'child', expected=name, maximum=80)
                nodes = list(self.nodes(root, strict=True))
                return (not any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes)
                        and not any(node.get_role_name() == 'list box' and self.showing(node)
                                    for node in nodes))
            return self.wait(closed, 'picker-close')
        require(surface == 'greeter' and target in ('password', 'account')
                and name in GREETER_IDENTITIES and mode == 'snapshot', 'ui:absence-binding')

        def absent():
            positive = (self.find_labelled_button(name) if target == 'password'
                        else self.find(name, ('label',)))
            if positive is None:
                return False
            root = self.api.get_desktop(0)
            require(root is not None, 'ui:missing-surface')
            # Consume the entire traversal, including unrelated subtrees, before
            # accepting exclusion. A stale read cannot stand in for absence.
            found = []
            for node in self.nodes(root, strict=True):
                role = node.get_role_name()
                if self.has_state(node, self.api.StateType.DEFUNCT):
                    return False
                if self.showing(node) and (role == 'password text' if target == 'password'
                        else role in ('button', 'push button') and node.get_name() == name):
                    found.append(node)
            return not found

        return self.wait(absent, 'gdm-prompt-dismissed' if target == 'password' else 'gdm-list-hidden')

    def choice_order(self, root, *, identities, maximum, cardinality, projection):
        """UI13: fresh complete collection, returning only canonical identities.

        Rows may be outside the viewport in a scrolling account list. Their
        order is readable; the separate focus checkpoint qualifies the input.
        """
        require(root is not None and type(maximum) is int and 1 <= maximum <= 32
                and type(cardinality) is tuple and len(cardinality) == 2
                and 0 <= cardinality[0] <= cardinality[1] <= maximum
                and ((identities == GREETER_IDENTITIES and projection == 'greeter-account-order')
                     or (identities == CHILD_IDENTITIES and projection == 'child-picker-order')),
                'ui:collection-binding')
        choices = []
        for node in self.nodes(root, strict=True):
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-collection')
            roles = ('list item',) if projection == 'child-picker-order' else ('button', 'push button')
            if node.get_role_name() not in roles:
                continue
            # GDM may put its label on the button or a nested public label.
            labels = {node.get_name()} | {child.get_name() for child in self.nodes(node, strict=True)
                                        if child.get_role_name() == 'label'}
            matches = [identity for label, identity in identities.items() if label in labels]
            require(len(matches) <= 1, 'ui:ambiguous-choice-identity')
            # The accepted baseline preserves unrelated accounts. They occupy
            # real Home/Down positions but are never selectable fixture targets.
            # Keep their labels private and represent only their list positions.
            identity = matches[0] if matches else f'unrelated-account-{len(choices) + 1}'
            require(identity not in choices, 'ui:duplicate-choice-identity')
            choices.append(identity)
            require(len(choices) <= maximum, 'ui:collection-bound')
        require(cardinality[0] <= len(choices) <= cardinality[1], 'ui:collection-cardinality')
        return tuple(choices)

    def greeter_navigation(self, name):
        button = self.greeter_list(name)
        choices = self.choice_order(button.get_parent(), identities=GREETER_IDENTITIES,
                                    maximum=32, cardinality=(1, 32), projection='greeter-account-order')
        identity = GREETER_IDENTITIES[name]
        require(choices.count(identity) == 1, 'ui:gdm-account-list')
        return ['home'] + ['down'] * choices.index(identity)

    def greeter_prompt(self):
        # This observation submits no secret and cannot authorize one. Read
        # only the account label and password role/state, never its contents.
        self.target(PARENT, ('label',))
        self.observe_absence('greeter', 'account', name=PARENT, mode='snapshot')
        self.wait(lambda: (field := self.find(roles=('password text',), sensitive=True))
                  is not None and self.has_state(field, self.api.StateType.FOCUSED),
                  'gdm-password-focus')

    def password_recipient(self, name):
        """Read only public identity, masked role, focus and empty length.

        Never read password text or children. A false/stale observation cannot
        authorize typing. The caller also requires a separate fresh recheck.
        """
        if self.find(name, ('label',)) is None:
            return False
        identities = (PARENT, OTHER_PARENT, CHILD, EXISTING_CHILD)
        if any(self.find(label, ('button', 'push button')) is not None
               for label in identities):
            return False
        if any(self.find(other, ('label',)) is not None for other in identities if other != name):
            return False
        field = self.find(roles=('password text',), sensitive=True)
        if field is None or not self.has_state(field, self.api.StateType.FOCUSED):
            return False
        interface = field.get_text_iface()
        return interface is not None and self.api.Text.get_character_count(interface) == 0

    def search_query(self, expected):
        """Read only the overview's public search field; never arbitrary text."""
        require(expected in ('', PRODUCT[:1], PRODUCT), 'ui:search-binding')
        overview = self.find('Overview')
        self.search_status = 'overview-missing'
        if overview is None:
            return False
        field = self.find(roles=('text', 'entry'), root=overview, sensitive=True, editable=True)
        self.search_status = 'field-missing'
        if field is None:
            return False
        return self.read_label(field, 'search-query', expected=expected, maximum=80)

    def search_ready(self, surface, *, focused=False):
        """SEARCH01/UI21: read the empty field, optionally its independent focus."""
        require(surface == 'overview' and type(focused) is bool, 'ui:search-binding')
        def ready():
            if not self.search_query(''):
                return False
            field = self.find(roles=('text', 'entry'), root=self.find('Overview'),
                              sensitive=True, editable=True)
            return field if field is not None and (not focused or self.has_state(
                field, self.api.StateType.FOCUSED)) else False
        return self.wait_search(ready, 'standard-search-focus' if focused else 'standard-search-ready')

    def search_absence(self, product, *, stable_seconds):
        """Positive query/result witnesses plus fresh, complete absence reads.

        A missing tree, unfinished query, stale subtree or failed read cannot
        prove that the launcher is unavailable. Require a stable observation
        interval; repeat reads only, with no replay of customer input.
        """
        stable_since = None
        def observed():
            nonlocal stable_since
            try:
                root = self.api.get_desktop(0)
                ready = root is not None and self.search_query(product)
                if ready:
                    suggestion = self.find_labelled_button('Search online', root=self.find('Overview'))
                    ready = suggestion is not None
                    self.search_status = 'suggestion-matched' if ready else 'suggestion-missing'
                if ready:
                    ready = self.read_label(suggestion, 'web-suggestion', expected=product, maximum=80)
                    self.search_status = 'description-matched' if ready else 'description-missing'
                # This negative assertion must not skip inaccessible subtrees.
                # Product labels include launch results even if their enclosing
                # button has a missing/wrong accessible name.
                for node in self.nodes(root, strict=True) if root is not None else ():
                    if self.has_state(node, self.api.StateType.DEFUNCT):
                        ready = False
                        self.search_status = 'incomplete-read'
                    if (self.showing(node) and node.get_role_name() in
                            ('button', 'push button', 'label', 'frame', 'dialog')
                            and ' '.join(node.get_name().split()) == product):
                        ready = False
                        self.search_status = 'parent-available'
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
        """Fixed public UI vocabulary for a blocked case-5 input; no raw tree."""
        windows = []
        known = {'gnome-shell': 'shell', 'GNOME Shell': 'shell', 'Unlock Login Keyring': 'keyring',
                 'Welcome to Ubuntu': 'welcome', 'Welcome': 'welcome',
                 'Authentication Required': 'authentication', PRODUCT: 'parent',
                 'Software Updater': 'software-updater'}
        buttons, tokens, applications, focused = set(), set(), set(), set()
        search_nodes = []
        for node in self.nodes():
            role = node.get_role_name()
            name = node.get_name()
            if role == 'application':
                applications.add(name if name in ('gnome-shell', 'gcr-prompter', 'update-manager',
                    'gnome-initial-setup', 'polkit-gnome-authentication-agent-1') else 'other')
            if self.showing(node):
                label = ' '.join(name.split())
                search_label = ('search-online' if label == 'Search online' else
                    'web-description' if label == 'Search "' + PRODUCT + '" on the web' else
                    'query-containing' if PRODUCT in label else None)
                if search_label is not None and role not in ('text', 'entry', 'password text'):
                    parent = node.get_parent()
                    search_nodes.append({'label': search_label, 'role': role,
                        'parent_role': parent.get_role_name() if parent is not None else 'none'})
                if role in ('button', 'push button') and name in (
                        'Cancel', 'Unlock', 'Close', 'Remind Me Later', 'Install Now',
                        'Not Now', 'Next', 'Skip', 'Start Tour', 'No Thanks', 'Log Out'):
                    buttons.add(name)
                if role in ('label', 'frame', 'dialog', 'window'):
                    tokens.update(word for word in ('keyring', 'password', 'welcome', 'update',
                        'authentication', 'keyboard', 'unlock', 'log out') if word in name.lower())
                if self.has_state(node, self.api.StateType.FOCUSED):
                    focused.add(role if role in ('text', 'entry', 'password text', 'button',
                        'push button', 'window', 'frame', 'dialog') else 'other')
            if role in ('window', 'frame', 'dialog', 'alert') and self.showing(node):
                windows.append({'role': role, 'surface': known.get(node.get_name(), 'other'),
                                'focused': self.has_state(node, self.api.StateType.FOCUSED),
                                'modal': self.has_state(node, self.api.StateType.MODAL)})
        return {'search_windows': windows[:8], 'buttons': sorted(buttons), 'tokens': sorted(tokens),
                'applications': sorted(applications), 'focused_roles': sorted(focused),
                'search_nodes': search_nodes[:12]}

    def system_prompt_control(self, *, qualify=True):
        """Resolve Cancel only in an identified, focused login-keyring prompt.

        No product window is closed, no password is submitted, and no action
        is replayed. Unknown prompts remain blocked for diagnosis.
        """
        # One fresh public traversal for all registered titles. This check runs
        # before every wait/input: rescanning a large installed-app catalogue
        # twice per title made ordinary Parent navigation exceed its deadline.
        # Nothing is cached across calls, so late/queued prompts remain visible.
        matches = {title: {'windows': [], 'labels': []} for title in KEYRING_LABELS}
        for node in self.nodes(strict=True):
            role = node.get_role_name()
            if role not in ('frame', 'dialog', 'label') or not self.showing(node):
                continue
            title = ' '.join(node.get_name().split())
            if title in matches:
                matches[title]['labels' if role == 'label' else 'windows'].append(node)
        for title in KEYRING_LABELS:
            windows = matches[title]['windows']
            require(len(windows) <= 1, 'ui:ambiguous-target')
            root = windows[0] if windows else None
            if root is None:
                labels = matches[title]['labels']
                require(len(labels) <= 1, 'ui:ambiguous-target')
                node = labels[0] if labels else None
                for _ in range(12):
                    if node is None:
                        break
                    if node.get_role_name() in ('frame', 'dialog'):
                        root = node
                        break
                    node = node.get_parent()
            if root is None or not self.showing(root) or root.get_name() == PRODUCT:
                continue
            if not qualify:
                # After Escape, poll only presence: focus/control transitions
                # during dismissal cannot authorize another key or abort a wait.
                return root
            if title.startswith(('The login keyring', 'The password you use')):
                # GNOME Shell renders the prompt's message and description,
                # not its legacy window title. Match the full public keyring
                # description and confirm its controls within the same dialog.
                require(self.find('Authentication required', ('label',), root=root) is not None
                        and self.find('Unlock', ('button', 'push button'), root=root,
                                      sensitive=True) is not None
                        and self.find(roles=('password text',), root=root,
                                      sensitive=True) is not None,
                        'ui:keyring-prompt-identity')
            controls = [control for name in ('Cancel',) if (control := self.find(
                name, ('button', 'push button'), root=root, sensitive=True)) is not None]
            require(len(controls) == 1, 'ui:system-prompt-control')
            field = self.find(roles=('password text',), root=root, sensitive=True)
            require(field is not None and self.has_state(field, self.api.StateType.FOCUSED),
                    'ui:system-prompt-focus')
            return controls[0]
        return None

    def system_prompt_absent(self, dialog=None):
        # A stale subtree cannot establish dismissal. Do not require focus or
        # enabled controls while the recognized dialog is closing.
        present = False
        for node in self.nodes(strict=True):
            if dialog is not None:
                if node == dialog and self.showing(node):
                    present = True
            elif (node.get_role_name() in ('frame', 'dialog', 'label') and self.showing(node)
                    and ' '.join(node.get_name().split()) in KEYRING_LABELS):
                present = True
        return not present

    def pointer_target(self, node):
        require(self.showing(node) and self.has_state(node, self.api.StateType.SENSITIVE),
                'ui:pointer-target-unusable')
        component = node.get_component_iface()
        require(component is not None, 'ui:pointer-unavailable')
        rect = component.get_extents(self.api.CoordType.SCREEN)
        require(rect.width > 0 and rect.height > 0, 'ui:pointer-unavailable')
        point = {'x': rect.x + rect.width // 2, 'y': rect.y + rect.height // 2}
        require(all(type(value) is int and 0 <= value <= 32767 for value in point.values()),
                'ui:pointer-bounds')
        return point

    def handle_system_prompt(self):
        """Pause a desktop wait for one normal Cancel click, then observe closure.

        The same adapter invocation resumes its pending read after dismissal;
        neither the surrounding operation nor earlier input is replayed. The
        graphical worker owns pointer input. Unknown prompts and GDM are excluded.
        """
        if not self.prompt_enabled or self.system_prompt is None or self.handling_prompt:
            return
        control = self.system_prompt_control()
        if control is None:
            return
        self.handling_prompt = True
        try:
            while control is not None:
                require(self.prompt_count < 3, 'ui:system-prompt-limit')
                self.prompt_count += 1
                dialog = control.get_parent()
                for _ in range(12):
                    if dialog is None or dialog.get_role_name() in ('frame', 'dialog'):
                        break
                    dialog = dialog.get_parent()
                require(dialog is not None and dialog.get_role_name() in ('frame', 'dialog'),
                        'ui:system-prompt-dialog')
                self.system_prompt(self.pointer_target(control))
                # Multiple applications may queue identical keyring requests.
                # A new dialog is a new input target only after a complete read
                # proves this exact dialog disappeared. Never reclick this one.
                self.wait(lambda: self.system_prompt_absent(dialog), 'system-prompt-dismissed')
                control = self.system_prompt_control()
        except self.query_errors:
            raise UiError('ui:system-prompt-observation-failed') from None
        finally:
            self.handling_prompt = False

    def run(self, operation, version):
        require(operation in OPERATIONS, 'ui:operation')
        self.prompt_enabled = operation not in GREETER_OPERATIONS
        self.handle_system_prompt()
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation in GREETER_OPERATIONS:
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
            elif operation in ('gdm-focused', 'gdm-other-focused', 'gdm-standard-focused'):
                name = OTHER_PARENT if operation == 'gdm-other-focused' else PARENT
                if operation == 'gdm-standard-focused':
                    name = EXISTING_CHILD
                self.wait(lambda: self.has_state(self.greeter_list(name), self.api.StateType.FOCUSED),
                          'gdm-account-focus')
            elif operation in GREETER_NAVIGATION:
                name = OTHER_PARENT if operation == 'gdm-other-list' else PARENT
                if operation == 'gdm-standard-list':
                    name = EXISTING_CHILD
                result['navigation'] = self.greeter_navigation(name)
            else:
                self.greeter_list()
        elif operation in ('desktop', 'standard-desktop'):
            self.desktop_result(PARENT if operation == 'desktop' else EXISTING_CHILD, 'success')
        elif operation == 'standard-system-prompt':
            self.wait(self.system_prompt_absent, 'system-prompt-dismissed')
        elif operation == 'standard-app-grid':
            self.wait(self.system_prompt_absent, 'system-prompt-dismissed')
            field = self.search_ready('overview')
            # Public screen coordinates route ordinary pointer input only.
            # They are never compared to a reference layout or used as an
            # outcome: the next checkpoint must independently observe focus.
            result['pointer'] = self.pointer_target(field)
        elif operation == 'standard-search-focused':
            self.search_ready('overview', focused=True)
        elif operation == 'standard-search-started':
            # GNOME's public overview supports type-to-search without manually
            # focusing the entry. Observe the first character before continuing.
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'standard-search-started')
        elif operation == 'standard-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'standard-search-entered')
        elif operation == 'standard-parent-unavailable':
            self.search_result(PRODUCT, 'unavailable', stable_seconds=2)
        elif operation == 'app-grid':
            # The worker entered the product query with real keyboard input.
            # Verify a launchable result, not GNOME's grid geometry or tiles.
            self.launchable_result(PRODUCT)
        elif operation == 'parent-window':
            self.parent()
        elif operation == 'parent-empty':
            self.parent_empty()
        elif operation in PICKER_OPERATIONS:
            result['navigation'] = self.open_child_picker(PICKER_OPERATIONS[operation])
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
        return result


def greeter_account():
    """Resolve the sole active local greeter via public logind session metadata.

    Modern GDM can use a dynamic account instead of the legacy gdm UID. This
    selects only the public UI connection identity; it proves no product result.
    """
    deadline = time.monotonic() + 15
    def call(*args):
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'ui:timeout:greeter-identity')
        return subprocess.run(['/usr/bin/loginctl', *args], capture_output=True,
                              text=True, check=True, timeout=min(5, remaining)).stdout
    rows = call('list-sessions', '--no-legend', '--no-pager').splitlines()
    require(len(rows) <= 32, 'ui:session-bound')
    found = []
    for row in rows:
        session = row.split()[0]
        import re
        require(re.fullmatch(r'[a-zA-Z0-9]+', session), 'ui:session-id')
        props = dict(line.split('=', 1) for line in call('show-session', session,
            '-p', 'Class', '-p', 'Active', '-p', 'Remote', '-p', 'Type', '-p', 'Seat', '-p', 'User').splitlines())
        if (props.get('Class') == 'greeter' and props.get('Active') == 'yes'
                and props.get('Remote') == 'no' and props.get('Seat') == 'seat0'
                and props.get('Type') in ('wayland', 'x11')):
            require(props.get('User', '').isdecimal() and int(props['User']) > 0,
                    'ui:greeter-user')
            found.append(int(props['User']))
    require(len(found) == 1, 'ui:greeter-identity')
    return pwd.getpwuid(found[0])


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


def main():
    require(len(sys.argv) == 3 and sys.argv[1] in OPERATIONS, 'ui:arguments')
    greeter = sys.argv[1] in GREETER_OPERATIONS
    require(os.geteuid() == 0, 'ui:fixture-identity')
    account = greeter_account() if greeter else pwd.getpwnam(
        'onpc-child-jordan' if sys.argv[1] in STANDARD_OPERATIONS else 'onpc-parent-jamie')
    require(account.pw_uid > 0 and (greeter or account.pw_uid >= 1000), 'ui:fixture-identity')
    environment = session_environment(account)
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
    ui = AccessibleUI(Atspi, query_errors=(GLib.Error,),
        dispatch=lambda: GLib.MainContext.default().iteration(False),
        system_prompt=lambda point: print(json.dumps({'event': 'system-prompt',
            'kind': 'login-keyring', 'pointer': point}), flush=True))
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
