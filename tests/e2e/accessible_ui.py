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
import sys
import time


OPERATIONS = frozenset({
    'desktop', 'app-grid', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'license', 'about-returned', 'parent-returned',
})
PRODUCT = 'Oh No! Parent Control'
CHILD = 'Riley (Child)'


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
        while pending:
            node = pending.pop()
            if node is None:
                continue
            visited += 1
            require(visited <= 6000, 'ui:tree-bound')
            try:
                node.clear_cache_single()
                yield node
                # Never inspect the contents of a password widget.
                if node.get_role_name() != 'password text':
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

    def settings(self):
        root = self.parent()
        picker = self.target(roles=('combo box',), root=root, sensitive=True)
        self.target(CHILD, ('label',), root=picker)
        toggle = self.target('Screen time limit', ('switch',), root=root, sensitive=True)
        allowance = self.target('Daily time allowance', ('button', 'push button'),
                                root=root)
        labels = sorted({node.get_name() for node in self.nodes(allowance)
                         if node.get_role_name() == 'label' and self.showing(node)})
        # Only ordinary duration labels are returned; never arbitrary UI text.
        import re
        require(labels and all(re.fullmatch(r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', text)
                               for text in labels), 'ui:allowance-label')
        return {'child': 'fixture-child',
                'limit_enabled': toggle.get_state_set().contains(self.api.StateType.CHECKED),
                'allowance': labels}

    def run(self, operation, version):
        require(operation in OPERATIONS, 'ui:operation')
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'desktop':
            self.target('Activities', ('toggle button', 'button', 'push button'))
        elif operation == 'app-grid':
            # The worker entered the product query with real keyboard input.
            # Verify a launchable result, not GNOME's grid geometry or tiles.
            self.labelled_button(PRODUCT)
        elif operation == 'child-picker-opened':
            root = self.parent()
            picker = self.target(roles=('combo box',), root=root, sensitive=True)
            self.activate(self.target(roles=('toggle button',), root=picker, sensitive=True))
            listing = self.target(roles=('list box',), root=root)
            self.target(CHILD, ('label',), root=listing)
            rows = [node for node in self.nodes(listing) if node.get_role_name() == 'list item']
            require(0 < len(rows) <= 32, 'ui:choice-bound')
            choices = [index for index, row in enumerate(rows)
                       if self.find(CHILD, ('label',), root=row) is not None]
            require(len(choices) == 1, 'ui:choice-identity')
            result['navigation'] = ['home'] + ['down'] * choices[0]
        elif operation == 'child-choice-highlighted':
            root = self.parent()
            listing = self.target(roles=('list box',), root=root)
            label = self.target(CHILD, ('label',), root=listing)
            row = label
            while row.get_role_name() != 'list item':
                row = row.get_parent()
                require(row is not None and row != root, 'ui:choice-row')
            self.wait(lambda: self.has_state(row, self.api.StateType.SELECTED),
                      'choice-highlight')
        elif operation == 'parent-selected':
            self.wait(lambda: self.find(roles=('list box',), root=self.parent()) is None,
                      'picker-close')
            result['settings'] = self.settings()
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


def main():
    require(len(sys.argv) == 3 and sys.argv[1] in OPERATIONS, 'ui:arguments')
    account = pwd.getpwnam('onpc-parent-jamie')
    require(os.geteuid() == 0 and account.pw_uid >= 1000, 'ui:fixture-identity')
    runtime = Path('/run/user') / str(account.pw_uid)
    require(runtime.stat().st_uid == account.pw_uid
            and stat.S_ISSOCK((runtime / 'bus').stat().st_mode), 'ui:session-bus')
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.clear()
    os.environ.update(HOME=account.pw_dir, USER=account.pw_name,
                      XDG_RUNTIME_DIR=str(runtime),
                      DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(runtime / 'bus'),
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
