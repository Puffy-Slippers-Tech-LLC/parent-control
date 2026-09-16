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
    'desktop', 'app-grid', 'parent-empty', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'license', 'about-returned', 'parent-returned',
    'discovery-ready', 'new-child-picker-opened', 'new-child-choice-highlighted',
    'new-child-selected', 'existing-child-picker-opened', 'existing-child-choice-highlighted',
    'existing-returned', 'existing-apps', 'new-child-apps', 'new-child-screen',
    'discovery-child-picker-opened', 'discovery-child-choice-highlighted', 'discovery-selected',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-parent-unavailable',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
})
STANDARD_OPERATIONS = frozenset({
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-parent-unavailable',
})
PRODUCT = 'Oh No! Parent Control'
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
        node = self.target(name, roles, root=root, showing=False)
        if not self.showing(node):
            component = node.get_component_iface()
            require(component is not None and component.scroll_to(self.api.ScrollType.ANYWHERE),
                    'ui:scroll-refused')
        return self.target(name, roles, root=root)

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

    def settings(self, child=CHILD):
        root = self.parent()
        picker = self.target(roles=('combo box',), root=root, sensitive=True)
        self.target(child, ('label',), root=picker)
        toggle = self.target('Screen time limit', ('switch',), root=root, sensitive=True)
        allowance = self.target('Daily time allowance', ('button', 'push button'),
                                root=root)
        labels = sorted({node.get_name() for node in self.nodes(allowance)
                         if node.get_role_name() == 'label' and self.showing(node)})
        # Only ordinary duration labels are returned; never arbitrary UI text.
        import re
        require(labels and all(re.fullmatch(r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', text)
                               for text in labels), 'ui:allowance-label')
        if child in (EXISTING_CHILD, NEW_CHILD):
            self.reveal("Today's Remaining Time", ('label',), root=root)
        return {'child': CHILD_IDENTITIES[child],
                'limit_enabled': toggle.get_state_set().contains(self.api.StateType.CHECKED),
                'allowance': labels}

    def greeter_list(self, name=PARENT):
        button = self.labelled_button(name)
        self.wait(lambda: self.find(roles=('password text',)) is None, 'gdm-prompt-dismissed')
        return button

    def greeter_prompt(self):
        # This observation submits no secret and cannot authorize one. Read
        # only the account label and password role/state, never its contents.
        self.target(PARENT, ('label',))
        self.wait(lambda: self.find(PARENT, ('button', 'push button')) is None,
                  'gdm-list-hidden')
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
        overview = self.find('Overview')
        self.search_status = 'overview-missing'
        if overview is None:
            return False
        field = self.find(roles=('text', 'entry'), root=overview, sensitive=True, editable=True)
        self.search_status = 'field-missing'
        if field is None:
            return False
        text = field.get_text_iface()
        count = self.api.Text.get_character_count(text) if text is not None else -1
        matches = (count == len(expected)
                and self.api.Text.get_text(text, 0, len(expected)) == expected)
        self.search_status = 'query-matched' if matches else 'query-mismatch-length=' + str(min(count, 256))
        return matches

    def standard_parent_unavailable(self):
        """Positive query/result witnesses plus fresh, complete absence reads.

        A missing tree, unfinished query, stale subtree or failed read cannot
        prove that the launcher is unavailable. Require a stable observation
        interval; repeat reads only, with no replay of customer input.
        """
        stable_since = None
        def observed():
            nonlocal stable_since
            try:
                ready = self.search_query(PRODUCT)
                if ready:
                    suggestion = self.find_labelled_button('Search online', root=self.find('Overview'))
                    ready = suggestion is not None
                    self.search_status = 'suggestion-matched' if ready else 'suggestion-missing'
                if ready:
                    ready = self.find('Search "' + PRODUCT + '" on the web', ('label',),
                                      root=suggestion) is not None
                    self.search_status = 'description-matched' if ready else 'description-missing'
                # This negative assertion must not skip inaccessible subtrees.
                # Product labels include launch results even if their enclosing
                # button has a missing/wrong accessible name.
                for node in self.nodes(strict=True):
                    if (self.showing(node) and node.get_role_name() in
                            ('button', 'push button', 'label', 'frame', 'dialog')
                            and ' '.join(node.get_name().split()) == PRODUCT):
                        ready = False
                        self.search_status = 'parent-available'
                if not ready:
                    stable_since = None
                    return False
                now = time.monotonic()
                if stable_since is None:
                    stable_since = now
                return now - stable_since >= 2
            except self.query_errors:
                stable_since = None
                self.search_status = 'incomplete-read'
                raise
        self.wait_search(observed, 'standard-parent-unavailable')

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
        for title in KEYRING_LABELS:
            root = self.find(title, ('frame', 'dialog'))
            if root is None:
                label = self.find(title, ('label',))
                node = label
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
                button = self.greeter_list(name)
                container = button.get_parent()
                require(container is not None, 'ui:gdm-account-list')
                rows = [node for node in self.nodes(container)
                        if node.get_role_name() in ('button', 'push button')]
                require(0 < len(rows) <= 32 and rows.count(button) == 1, 'ui:gdm-account-list')
                result['navigation'] = ['home'] + ['down'] * rows.index(button)
            else:
                self.greeter_list()
        elif operation in ('desktop', 'standard-desktop'):
            self.target('Activities', ('toggle button', 'button', 'push button'))
        elif operation == 'standard-system-prompt':
            self.wait(self.system_prompt_absent, 'system-prompt-dismissed')
        elif operation == 'standard-app-grid':
            self.wait(self.system_prompt_absent, 'system-prompt-dismissed')
            self.wait_search(lambda: self.search_query(''), 'standard-search-ready')
            field = self.target(roles=('text', 'entry'), root=self.target('Overview'),
                                sensitive=True, editable=True)
            # Public screen coordinates route ordinary pointer input only.
            # They are never compared to a reference layout or used as an
            # outcome: the next checkpoint must independently observe focus.
            result['pointer'] = self.pointer_target(field)
        elif operation == 'standard-search-focused':
            def focused():
                root = self.find('Overview')
                if root is None or not self.search_query(''):
                    return False
                field = self.find(roles=('text', 'entry'), root=root, sensitive=True, editable=True)
                return field is not None and self.has_state(field, self.api.StateType.FOCUSED)
            self.wait(focused, 'standard-search-focus')
        elif operation == 'standard-search-started':
            # GNOME's public overview supports type-to-search without manually
            # focusing the entry. Observe the first character before continuing.
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'standard-search-started')
        elif operation == 'standard-parent-unavailable':
            self.standard_parent_unavailable()
        elif operation == 'app-grid':
            # The worker entered the product query with real keyboard input.
            # Verify a launchable result, not GNOME's grid geometry or tiles.
            self.labelled_button(PRODUCT)
        elif operation == 'parent-empty':
            def empty():
                root = self.find(PRODUCT, ('frame',))
                if root is None:
                    return False
                explanation = self.find('No interactive non-administrator account was found.',
                                        ('label',), root=root)
                picker = self.find(roles=('combo box',), root=root)
                if explanation is None or picker is None:
                    return False
                # A visible explanation alone must not hide a selected child.
                # Read the public picker even when disabled; never activate it.
                labels = [node.get_name().strip() for node in self.nodes(picker)
                          if node.get_role_name() == 'label' and self.showing(node)]
                return labels == ['(None)']
            self.wait(empty, 'parent-empty')
        elif operation in PICKER_OPERATIONS:
            child = PICKER_OPERATIONS[operation]
            root = self.parent()
            picker = self.target(roles=('combo box',), root=root, sensitive=True)
            self.activate(self.target(roles=('toggle button',), root=picker, sensitive=True))
            def navigation():
                current = self.find(PRODUCT, ('frame',))
                if current is None:
                    return None
                listing = self.find(roles=('list box',), root=current)
                if listing is None or self.find(child, ('label',), root=listing) is None:
                    return None
                rows = [node for node in self.nodes(listing) if node.get_role_name() == 'list item']
                require(0 < len(rows) <= 32, 'ui:choice-bound')
                choices = [index for index, row in enumerate(rows)
                           if self.find(child, ('label',), root=row) is not None]
                require(len(choices) == 1, 'ui:choice-identity')
                require(self.has_state(rows[choices[0]], self.api.StateType.SENSITIVE),
                        'ui:unusable-choice')
                return ['home'] + ['down'] * choices[0]
            result['navigation'] = self.wait(navigation, 'child-choice')
        elif operation in HIGHLIGHT_OPERATIONS:
            def highlighted():
                root = self.find(PRODUCT, ('frame',))
                if root is None:
                    return False
                listing = self.find(roles=('list box',), root=root)
                if listing is None:
                    return False
                row = self.find(HIGHLIGHT_OPERATIONS[operation], ('label',), root=listing)
                for _ in range(16):
                    if row is None or row == root:
                        return False
                    if row.get_role_name() == 'list item':
                        return (self.showing(row) and self.has_state(row, self.api.StateType.SENSITIVE)
                                and self.has_state(row, self.api.StateType.SELECTED))
                    row = row.get_parent()
                return False
            self.wait(highlighted, 'choice-highlight')
        elif operation in ('existing-apps', 'new-child-apps'):
            child = EXISTING_CHILD if operation == 'existing-apps' else NEW_CHILD
            self.settings(child)
            self.activate(self.target('App Limits', ('page tab',), root=self.parent(), sensitive=True))
            self.target('Search installed apps', ('text', 'entry'), root=self.parent(), sensitive=True)
            self.reveal('Filter Access Rule', ('button', 'push button'), root=self.parent())
            self.reveal('Filter Match Rule', ('button', 'push button'), root=self.parent())
        elif operation in SETTINGS_OPERATIONS and operation != 'parent-returned':
            if operation in ('discovery-ready', 'new-child-screen'):
                self.activate(self.target('Screen Limits', ('page tab',), root=self.parent(), sensitive=True))
            self.wait(lambda: self.find(roles=('list box',), root=self.parent()) is None,
                      'picker-close')
            result['settings'] = self.settings(SETTINGS_OPERATIONS[operation])
        elif operation == 'about':
            self.activate(self.target('Parent app menu', ('toggle button',),
                                      root=self.parent(), sensitive=True))
            self.activate(self.target('About', ('button', 'push button'),
                                      root=self.parent(), sensitive=True))
            root = self.about()
            self.target(PRODUCT, ('label',), root=root)
            self.target('Version ' + version, ('label',), root=root)
            self.reveal('GNU General Public License v3.0', ('link',), root=root)
        elif operation == 'license':
            self.activate(self.target('GNU General Public License v3.0', ('link',),
                                      root=self.about(), sensitive=True))
            def document():
                # Read only the foreground LICENSE viewer's public text surface.
                frame = self.find(roles=('frame',), contains='LICENSE')
                if frame is None:
                    return False
                for node in self.nodes(frame):
                    if not self.showing(node) or node.get_role_name() not in ('text', 'document text'):
                        continue
                    text = node.get_text_iface()
                    if text is not None:
                        # Accessible.get_text is a different (deprecated)
                        # interface accessor on the same GI object.
                        value = self.api.Text.get_text(
                            text, 0, min(self.api.Text.get_character_count(text), 1024))
                        if 'GNU GENERAL PUBLIC LICENSE' in value and 'Version 3, 29 June 2007' in value:
                            return True
                return False
            self.wait(document, 'license-content')
        elif operation == 'about-returned':
            self.wait(lambda: self.find(roles=('frame',), contains='LICENSE') is None,
                      'license-close')
            self.reveal('© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.',
                        ('label',), root=self.about())
        elif operation == 'parent-returned':
            self.wait(lambda: self.find('About', ('frame', 'dialog')) is None, 'about-close')
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
