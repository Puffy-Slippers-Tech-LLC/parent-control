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
    'desktop', 'app-grid', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'license', 'about-returned', 'parent-returned',
    'discovery-ready', 'new-child-picker-opened', 'new-child-choice-highlighted',
    'new-child-selected', 'existing-child-picker-opened', 'existing-child-choice-highlighted',
    'existing-returned', 'existing-apps', 'new-child-apps', 'new-child-screen',
    'discovery-child-picker-opened', 'discovery-child-choice-highlighted', 'discovery-selected',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
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
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked'})
GREETER_NAVIGATION = frozenset({'gdm-list', 'gdm-other-list'})


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

    def __init__(self, api, *, timeout=45, query_errors=()):
        self.api = api
        self.timeout = timeout
        self.query_errors = query_errors
        self.last_roles = set()

    def nodes(self, root=None):
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
             showing=True):
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
            except self.query_errors:
                continue
            found.append(node)
        require(len(found) <= 1, 'ui:ambiguous-target')
        return found[0] if found else None

    def wait(self, predicate, code):
        deadline = time.monotonic() + self.timeout
        while True:
            try:
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

    def labelled_button(self, name):
        """Resolve either a named button or its showing label's button ancestor."""
        def lookup():
            button = self.find(name, ('button', 'push button'), sensitive=True)
            if button is not None:
                return button
            label = self.find(name, ('label',))
            node = label
            for _ in range(16):
                if node is None:
                    return None
                if node.get_role_name() in ('button', 'push button'):
                    return node if self.showing(node) and self.has_state(
                        node, self.api.StateType.SENSITIVE) else None
                node = node.get_parent()
            return None
        return self.wait(lookup, 'labelled-button')

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
        if any(self.find(label, ('button', 'push button')) is not None
               for label in (PARENT, OTHER_PARENT)):
            return False
        other = OTHER_PARENT if name == PARENT else PARENT
        if self.find(other, ('label',)) is not None:
            return False
        field = self.find(roles=('password text',), sensitive=True)
        if field is None or not self.has_state(field, self.api.StateType.FOCUSED):
            return False
        interface = field.get_text_iface()
        return interface is not None and self.api.Text.get_character_count(interface) == 0

    def run(self, operation, version):
        require(operation in OPERATIONS, 'ui:operation')
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation in GREETER_OPERATIONS:
            if operation == 'gdm-wrong-recipient-refused':
                self.wait(lambda: self.password_recipient(OTHER_PARENT), 'gdm-other-recipient')
                require(not self.password_recipient(PARENT), 'ui:gdm-wrong-recipient-accepted')
            elif operation in ('gdm-parent-recipient', 'gdm-parent-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(PARENT), 'gdm-parent-recipient')
            elif operation == 'gdm-select-parent':
                self.greeter_prompt()
            elif operation in ('gdm-focused', 'gdm-other-focused'):
                name = OTHER_PARENT if operation == 'gdm-other-focused' else PARENT
                self.wait(lambda: self.has_state(self.greeter_list(name), self.api.StateType.FOCUSED),
                          'gdm-account-focus')
            elif operation in GREETER_NAVIGATION:
                button = self.greeter_list(OTHER_PARENT if operation == 'gdm-other-list' else PARENT)
                container = button.get_parent()
                require(container is not None, 'ui:gdm-account-list')
                rows = [node for node in self.nodes(container)
                        if node.get_role_name() in ('button', 'push button')]
                require(0 < len(rows) <= 32 and rows.count(button) == 1, 'ui:gdm-account-list')
                result['navigation'] = ['home'] + ['down'] * rows.index(button)
            else:
                self.greeter_list()
        elif operation == 'desktop':
            self.target('Activities', ('toggle button', 'button', 'push button'))
        elif operation == 'app-grid':
            # The worker entered the product query with real keyboard input.
            # Verify a launchable result, not GNOME's grid geometry or tiles.
            self.labelled_button(PRODUCT)
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
    account = greeter_account() if greeter else pwd.getpwnam('onpc-parent-jamie')
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
    result = AccessibleUI(Atspi, query_errors=(GLib.Error,)).run(sys.argv[1], sys.argv[2])
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No raw UI tree, account names, document contents or D-Bus errors.
        print(str(error) if isinstance(error, UiError) else 'ui:adapter-failed:' + type(error).__name__,
              file=sys.stderr, flush=True)
        raise SystemExit(1)
