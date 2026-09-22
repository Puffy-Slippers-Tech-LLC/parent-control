"""Guarded controller for public UI operations, with sanitized evidence."""

import json
import sys
from dataclasses import dataclass

import accessible_ui
import watch_activity
from private_artifacts import require
import system_runner as system


# Fixed public descriptions only; never forward account labels, query text or
# credentials from the observed desktop. New operations must declare prose here.
OPERATION_LABELS = {
    'gdm-list': 'Reading the greeter account list',
    'gdm-focused': 'Checking the intended greeter account is focused',
    'gdm-select-parent': 'Checking the Parent password prompt',
    'gdm-navigation-returned': 'Checking the greeter list after dismissing the password prompt',
    'gdm-product-free-list': 'Reading the product-free greeter account list',
    'gdm-product-free-focused': 'Checking the product-free Parent account is focused',
    'gdm-product-free-select-parent': 'Checking the product-free Parent password prompt',
    'gdm-product-free-returned': 'Checking the product-free greeter list after dismissal',
    'gdm-dismissed': 'Checking the password prompt was dismissed',
    'gdm-returned': 'Checking the greeter after returning to graphics',
    'gdm-other-list': 'Reading the wrong-account qualification list',
    'gdm-other-focused': 'Checking the wrong account is focused',
    'gdm-wrong-recipient-refused': 'Rejecting the wrong-account password prompt',
    'gdm-parent-recipient': 'Qualifying the empty masked Parent password field',
    'gdm-parent-recipient-rechecked': 'Freshly rechecking the Parent password recipient',
    'gdm-standard-list': 'Reading the standard-account greeter list',
    'gdm-standard-focused': 'Checking the standard account is focused',
    'gdm-standard-wrong-recipient-refused': 'Rejecting the wrong-account password prompt',
    'gdm-standard-recipient': 'Qualifying the empty masked standard-account password field',
    'gdm-standard-recipient-rechecked': 'Freshly rechecking the standard-account password recipient',
    'desktop': 'Waiting for the Parent desktop',
    'fresh-parent-desktop': 'Checking the fresh Parent desktop without a prompt',
    'fresh-standard-desktop': 'Checking the fresh standard desktop without a prompt',
    'parent-search-ready': 'Reading the empty Parent app search field',
    'parent-search-focused': 'Checking the Parent app search field is focused',
    'parent-search-entered': 'Checking the complete Parent app search query',
    'app-grid': 'Finding the launchable Parent result in public app search',
    'parent-window': 'Waiting for the Parent window',
    'parent-command-launch': 'Invoking the Parent command as [Parent user]',
    'standard-parent-command-launch': 'Invoking the Parent command as [Standard user]',
    'standard-parent-closed': 'Checking denial dismissal returns to the standard desktop',
    'parent-empty': 'Checking the explanation for no eligible children',
    'child-picker-opened': 'Expanding the child selector for [Child user]',
    'child-choice-highlighted': 'Checking [Child user] is highlighted',
    'parent-selected': 'Checking the selected child and displayed settings',
    'about': 'Opening About and reading product information',
    'license': 'Opening and reading the installed license',
    'license-closed': 'Checking the license window is closed',
    'about-returned': 'Reading the About footer',
    'parent-returned': 'Checking the returned child and unchanged settings',
    'parent-toggle-enabled': 'Enabling the Parent screen time limit',
    'parent-toggle-disabled': 'Disabling the Parent screen time limit',
    'parent-toggle-current': 'Reading the already-disabled Parent screen time limit',
    'parent-toggle-wrong-refused': 'Refusing an unregistered Parent toggle binding',
    'parent-toggle-hidden-refused': 'Refusing the hidden Parent screen time limit',
    'parent-toggle-disabled-settings': 'Reading settings while screen time is disabled',
    'parent-save-wrong-child-refused': 'Refusing a Parent save result for the wrong child',
    'parent-save-enabled': 'Reading the saved enabled Parent controls',
    'parent-save-reopened': 'Reading the saved state from a fresh Parent observation',
    'parent-save-disabled': 'Reading the saved disabled Parent controls',
    'discovery-ready': 'Checking existing-child settings and remaining time',
    'new-child-picker-opened': 'Expanding the child selector for [New child]',
    'new-child-choice-highlighted': 'Checking [New child] is highlighted',
    'new-child-selected': 'Checking the selected new child and displayed settings',
    'existing-child-picker-opened': 'Expanding the child selector for [Existing child]',
    'existing-child-choice-highlighted': 'Checking [Existing child] is highlighted',
    'existing-returned': 'Checking the returned existing child and displayed settings',
    'existing-apps': 'Reading App Limits for [Existing child]',
    'new-child-apps': 'Reading App Limits for [New child]',
    'new-child-screen': 'Reading screen-time settings for [New child]',
    'discovery-child-picker-opened': 'Expanding the child selector for [Existing child]',
    'discovery-child-choice-highlighted': 'Checking [Existing child] is highlighted',
    'discovery-selected': 'Checking existing-child settings and remaining time',
    'standard-desktop': 'Waiting for the standard-account desktop',
    'standard-system-prompt': 'Checking for a login-keyring prompt',
    'standard-app-grid': 'Opening public app search',
    'standard-search-focused': 'Checking the app search field is focused',
    'standard-search-started': 'Checking the first search character',
    'standard-search-entered': 'Checking the complete Parent search query',
    'standard-parent-unavailable': 'Checking Parent is unavailable to the standard account',
    'standard-terminal-input': 'Finding the active terminal input surface',
    'standard-terminal-focused': 'Focusing terminal input and checking its focus',
    'standard-terminal-wrong-surface': 'Refusing terminal input on the desktop',
    'standard-terminal-closed': 'Checking the terminal window is closed',
    'standard-management-denied': 'Reading administrator-access denial and checking management is absent',
    'standard-denial-closed': 'Checking denial dismissal returns to Terminal',
}
OPERATION_LABELS.update({
    'help-system-prompt': 'Checking for a login-keyring prompt',
    'help-terminal-input': 'Finding the active terminal input surface',
    'help-terminal-focused': 'Checking focused shell input before reading command help',
    'help-terminal-wrong-surface': 'Refusing help input on the desktop',
    'help-terminal-closed': 'Checking Terminal and product windows are closed',
    'help-shell-ready': 'Checking normal terminal input after command documentation',
    **{'help-content-' + key: 'Reading installed ' + key.replace('-', ' ')
       for key in accessible_ui.HELP_BINDINGS},
})
OPERATION_LABELS.update({
    'session-menu-toggle': 'Locating the desktop system menu',
    'session-menu-power': 'Locating the Power Off Menu',
    'session-menu': 'Opening the desktop session menu',
    'switch-user': 'Choosing Switch User from the session menu',
    'logout': 'Choosing Log Out from the session menu',
    'logout-confirm': 'Confirming Log Out',
})
OPERATION_LABELS.update({
    'gdm-station-wrong-entry-refused': 'Checking a password account does not enter the request station',
    'gdm-station-list': 'Reading the greeter before request-station entry',
    'gdm-station-focused': 'Checking the request station is focused',
    'gdm-station-returned': 'Checking the usable greeter after leaving the request station',
    'kiosk-request-form': 'Reading the request-station form and unavailable controls',
    'kiosk-request-cancel': 'Cancelling the request station through its public control',
    'kiosk-request-escape-ready': 'Checking the request station recipient before Escape',
    'station-entry-branch': 'Observing the offered station session branch without input',
    'station-default-entry': 'Reading back the passwordless default request-station session',
})


@dataclass(frozen=True)
class SettingsObservation:
    """Immutable, sanitized UI values owned explicitly by a scenario."""

    child: str
    limit_enabled: bool
    allowance: tuple

    @classmethod
    def from_settings(cls, settings):
        require(type(settings) is dict and set(settings) == {'child', 'limit_enabled', 'allowance'}
                and settings['child'] in accessible_ui.CHILD_IDENTITIES.values()
                and type(settings['limit_enabled']) is bool
                and type(settings['allowance']) is list and 1 <= len(settings['allowance']) <= 2,
                'ui:settings')
        import re
        require(all(type(value) is str and re.fullmatch(
            r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', value)
            for value in settings['allowance']), 'ui:settings')
        return cls(settings['child'], settings['limit_enabled'], tuple(settings['allowance']))


@dataclass(frozen=True)
class RequestObservation:
    """Immutable REQUEST03 projection containing no customer account labels."""

    surface: str
    form_count: int
    child: str
    approver: str
    duration_seconds: int
    custom_text: str | None
    allow_soft: bool
    child_selector_enabled: bool
    approver_selector_enabled: bool
    duration_enabled: bool
    soft_choice_enabled: bool
    request_enabled: bool
    cancel_enabled: bool
    message: str
    mute: bool | None

    @classmethod
    def from_request(cls, value):
        fields = tuple(cls.__dataclass_fields__)
        require(type(value) is dict and set(value) == set(fields), 'ui:request')
        observation = cls(**value)
        require(type(observation.surface) is str and type(observation.form_count) is int
                and type(observation.child) is str and type(observation.approver) is str
                and type(observation.duration_seconds) is int
                and observation.custom_text is None
                and all(type(getattr(observation, field)) is bool for field in (
                    'allow_soft', 'child_selector_enabled', 'approver_selector_enabled',
                    'duration_enabled', 'soft_choice_enabled', 'request_enabled',
                    'cancel_enabled'))
                and type(observation.message) is str and observation.mute is None,
                'ui:request')
        require(observation == cls(
            surface='kiosk', form_count=1, child='existing-fixture-child',
            approver='other-fixture-parent', duration_seconds=1800, custom_text=None,
            allow_soft=False, child_selector_enabled=True,
            approver_selector_enabled=False, duration_enabled=False,
            soft_choice_enabled=False, request_enabled=False, cancel_enabled=True,
            message='screen-limit-disabled', mute=None,
        ), 'ui:request')
        return observation


def compare_settings(observed, expected):
    """UI12: pure comparison; diagnostics contain only approved field names."""
    require(type(observed) is SettingsObservation and type(expected) is SettingsObservation,
            'ui:comparison-binding')
    different = [field for field in ('child', 'limit_enabled', 'allowance')
                 if getattr(observed, field) != getattr(expected, field)]
    require(not different, 'ui:settings-changed:' + ','.join(different))
    return {'fields': ['child', 'limit_enabled', 'allowance'], 'outcome': 'passed'}


class UiObservations:
    def __init__(self, transport, *, system_prompt=None, progress=None):
        self.transport = transport
        self.progress = progress
        self.last_operation = None
        self.wrong_recipient_refused = False
        self.standard_wrong_recipient_refused = False
        self.system_prompt = system_prompt

    @staticmethod
    def point(value):
        require(False, 'ui:pointer-route-refused')

    @staticmethod
    def retain_kiosk_diagnostic(value):
        """Validate before forwarding; guest text never becomes a diagnostic."""
        require(set(value) == {'event', 'phase', 'status', 'elapsed_ms', 'tree',
                'public_ids', 'tree_reads', 'nodes_read', 'incomplete_reads', 'query_errors'}
                and value['phase'] in accessible_ui.KIOSK_DIAGNOSTIC_PHASES
                and value['status'] in {'reading', 'missing', 'incomplete', 'query-error',
                                        'passed', 'failed'}
                and value['tree'] in {'unread', 'complete', 'incomplete'}, 'ui:diagnostic')
        require(all(type(value[key]) is int and 0 <= value[key] <= 10**9
                    for key in ('elapsed_ms', 'tree_reads', 'nodes_read',
                                'incomplete_reads', 'query_errors')), 'ui:diagnostic')
        counts = value['public_ids']
        require(type(counts) is dict and (not counts or
                set(counts) == set(accessible_ui.KIOSK_DIAGNOSTIC_IDS))
                and all(type(count) is int and 0 <= count <= 6000
                        for count in counts.values())
                and (value['tree'] == 'complete') == bool(counts), 'ui:diagnostic')
        # Controller stderr is retained by the owned command even when its SSH
        # child times out. Keep this evidence separate from the final UI result.
        line = json.dumps(value, sort_keys=True)
        print(line, file=sys.stderr, flush=True)
        watch_activity.event(line)

    def call(self, argv, operation, *, input=None):
        # Greeter startup: 300s identity + 20s bus + 45s UI, with transport
        # margin; still inside the worker's 420s checkpoint deadline.
        # Kiosk waits only for the public form, with transport margin.
        timeout = 390 if (operation in accessible_ui.GREETER_OPERATIONS
                          or operation in accessible_ui.STATION_BRANCH_OPERATIONS) else (
            120 if operation in accessible_ui.KIOSK_SESSION_OPERATIONS else 90)
        kiosk = operation in accessible_ui.KIOSK_SESSION_OPERATIONS
        if self.system_prompt is None and not kiosk:
            return self.transport.call(argv, input=input, timeout=timeout), []
        commands = self.transport.commands
        previous = commands.progress
        pending = bytearray()
        prompts, results = [], []
        received = 0
        diagnostic_count = 0

        def output(data):
            nonlocal received, diagnostic_count
            received += len(data)
            require(received <= (131072 if kiosk else 8192), 'ui:response-size')
            pending.extend(data)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                if type(value) is dict and value.get('event') == 'kiosk-form-observation':
                    diagnostic_count += 1
                    require(kiosk and not results and diagnostic_count <= 128,
                            'ui:diagnostic-order')
                    require(bytes(line) == json.dumps(value, sort_keys=True).encode(),
                            'ui:diagnostic')
                    self.retain_kiosk_diagnostic(value)
                elif type(value) is dict and value.get('event') == 'system-prompt':
                    require(False, 'ui:prompt-coordinate-route-refused')
                else:
                    require(not results, 'ui:response-replay')
                    results.append(bytes(line))
        try:
            self.transport.call(argv, input=input, timeout=timeout, on_output=output)
            require(not pending and len(results) == 1, 'ui:response-incomplete')
            return results[0], prompts
        finally:
            commands.progress = previous

    def observe(self, operation):
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        with watch_activity.operation(OPERATION_LABELS[operation]):
            return self._observe(operation)

    def _observe(self, operation):
        # Qualifications lack a scenario recorder, but use the same existing
        # spectator command pane as customer cases. Keep private program/stdin
        # and raw UI replies hidden; expose the fixed operation and its result.
        watch_activity.event('SSH UI: ' + OPERATION_LABELS[operation])
        if self.progress is not None:
            self.progress.operation(OPERATION_LABELS[operation])
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        # The standalone observer can exceed Linux's per-argument limit after
        # SSH shell quoting. Carry its bytes on the existing guarded stdin pipe.
        try:
            raw, prompts = self.call(['/usr/bin/python3', '-I', '-', operation, version],
                                     operation, input=program.encode())
        except BaseException:
            watch_activity.event('SSH UI observation failed: ' + operation)
            raise
        require(isinstance(raw, bytes) and 0 < len(raw) <= 2048, 'ui:response-size')
        result = json.loads(raw)
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'station-entry-branch':
            require(type(result) is dict and set(result) == {*expected, 'branch'}, 'ui:response')
            branch = result['branch']
            require(type(branch) is dict and set(branch) == {'destination', 'controls'}
                    and type(branch['controls']) is list, 'ui:station-branch')
            controls = branch['controls']
            require((branch['destination'] == 'default-request-form' and not controls)
                    or (branch['destination'] == 'greeter-controls' and 0 < len(controls) <= 12),
                    'ui:station-branch')
            for control in controls:
                require(type(control) is dict and set(control) == {
                    'label', 'role', 'public_id_present', 'sensitive', 'focused'}
                    and control['label'] in {*accessible_ui.GDM_SESSION_LABELS.values(), 'unresolved'}
                    and control['role'] in {'button', 'push button', 'toggle button', 'radio button',
                                           'menu item', 'radio menu item', 'check menu item', 'combo box'}
                    and all(type(control[key]) is bool for key in
                            ('public_id_present', 'sensitive', 'focused')), 'ui:station-branch')
            expected['branch'] = branch
        if operation == 'station-default-entry':
            require(type(result) is dict and set(result) == {*expected, 'entry'}
                    and result['entry'] == {'destination': 'default-request-form'},
                    'ui:station-default-entry')
            expected['entry'] = {'destination': 'default-request-form'}
        if operation in accessible_ui.PICKER_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'focused'}
                    and result['focused'] is True, 'ui:response')
            expected['focused'] = True
        if operation in accessible_ui.GREETER_NAVIGATION:
            require(type(result) is dict and set(result) == {*expected, 'focused'}
                    and result['focused'] is True, 'ui:response')
            expected['focused'] = True
        if operation in accessible_ui.SETTINGS_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'settings'}, 'ui:response')
            settings = result['settings']
            require(type(settings) is dict and set(settings) == {'child', 'limit_enabled', 'allowance'}
                    and settings['child'] == accessible_ui.CHILD_IDENTITIES[
                        accessible_ui.SETTINGS_OPERATIONS[operation]]
                    and type(settings['limit_enabled']) is bool
                    and type(settings['allowance']) is list and 1 <= len(settings['allowance']) <= 2,
                    'ui:settings')
            import re
            require(all(type(value) is str and re.fullmatch(
                r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', value)
                        for value in settings['allowance']), 'ui:settings')
            expected['settings'] = settings
        if operation in accessible_ui.TOGGLE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'toggle'}
                    and result['toggle'] == accessible_ui.TOGGLE_OPERATIONS[operation],
                    'ui:toggle-response')
            expected['toggle'] = accessible_ui.TOGGLE_OPERATIONS[operation]
        if operation in accessible_ui.PARENT_SAVE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'save'}
                    and result['save'] == accessible_ui.PARENT_SAVE_OPERATIONS[operation],
                    'ui:parent-save-response')
            expected['save'] = accessible_ui.PARENT_SAVE_OPERATIONS[operation]
        if operation in accessible_ui.KIOSK_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'request'}, 'ui:response')
            RequestObservation.from_request(result['request'])
            expected['request'] = result['request']
        require(result == expected, 'ui:response')
        if operation == 'gdm-wrong-recipient-refused':
            require(self.last_operation == 'gdm-other-focused', 'ui:recipient-order')
            self.wrong_recipient_refused = True
        elif operation == 'gdm-parent-recipient':
            require(self.wrong_recipient_refused and self.last_operation == 'gdm-focused',
                    'ui:recipient-order')
        elif operation == 'gdm-parent-recipient-rechecked':
            require(self.last_operation == 'gdm-parent-recipient', 'ui:recipient-order')
        elif operation == 'gdm-standard-wrong-recipient-refused':
            require(self.last_operation == 'gdm-other-focused', 'ui:recipient-order')
            self.standard_wrong_recipient_refused = True
        elif operation == 'gdm-standard-recipient':
            require(self.standard_wrong_recipient_refused and self.last_operation == 'gdm-standard-focused',
                    'ui:recipient-order')
        elif operation == 'gdm-standard-recipient-rechecked':
            require(self.last_operation == 'gdm-standard-recipient', 'ui:recipient-order')
        self.last_operation = operation
        watch_activity.event('SSH UI observation passed: ' + operation)
        if prompts:
            result['system_prompts'] = prompts
        return result
