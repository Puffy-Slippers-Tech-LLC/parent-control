"""Guarded controller for public UI operations, with sanitized evidence."""

import json
from dataclasses import dataclass

import accessible_ui
from private_artifacts import require
import system_runner as system


# Fixed public descriptions only; never forward account labels, query text or
# credentials from the observed desktop. New operations must declare prose here.
OPERATION_LABELS = {
    'gdm-list': 'Reading the greeter account list',
    'gdm-focused': 'Checking the intended greeter account is focused',
    'gdm-select-parent': 'Checking the Parent password prompt',
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
    'app-grid': 'Finding the launchable Parent result in public app search',
    'parent-window': 'Waiting for the Parent window',
    'parent-empty': 'Checking the explanation for no eligible children',
    'child-picker-opened': 'Expanding the child selector for [Child user]',
    'child-choice-highlighted': 'Checking [Child user] is highlighted',
    'parent-selected': 'Checking the selected child and displayed settings',
    'about': 'Opening About and reading product information',
    'license': 'Opening and reading the installed license',
    'license-closed': 'Checking the license window is closed',
    'about-returned': 'Reading the About footer',
    'parent-returned': 'Checking the returned child and unchanged settings',
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
    'kiosk-request-form': 'Reading the request-station form and unavailable controls',
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
        require(type(value) is dict and set(value) == {'x', 'y'}
                and all(type(item) is int and 0 <= item <= 32767 for item in value.values()),
                'ui:pointer')
        return value

    def call(self, argv, operation):
        # Greeter startup: 300s identity + 20s bus + 45s UI, with transport
        # margin; still inside the worker's 420s checkpoint deadline.
        # Kiosk waits only for the public form, with transport margin.
        timeout = 390 if operation in accessible_ui.GREETER_OPERATIONS else (
            120 if operation in accessible_ui.KIOSK_OPERATIONS else 90)
        if self.system_prompt is None:
            return self.transport.call(argv, timeout=timeout), []
        commands = self.transport.commands
        previous = commands.progress
        pending = bytearray()
        prompts, results = [], []
        received = 0

        def output(data):
            nonlocal received
            received += len(data)
            require(received <= 8192, 'ui:response-size')
            pending.extend(data)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                if type(value) is dict and value.get('event') == 'system-prompt':
                    require(operation not in accessible_ui.GREETER_OPERATIONS
                            and not results and len(prompts) < 3
                            and set(value) == {'event', 'kind', 'pointer'}
                            and value['kind'] == 'login-keyring', 'ui:system-prompt-response')
                    point = self.point(value['pointer'])
                    # Ownership guards may issue their own recorded commands.
                    # Their output must never enter this UI message parser.
                    commands.progress = previous
                    try:
                        self.system_prompt(point)
                    finally:
                        commands.progress = output
                    prompts.append({'kind': 'login-keyring', 'action': 'cancel-click'})
                else:
                    require(not results, 'ui:response-replay')
                    results.append(bytes(line))
        try:
            self.transport.call(argv, timeout=timeout, on_output=output)
            require(not pending and len(results) == 1, 'ui:response-incomplete')
            return results[0], prompts
        finally:
            commands.progress = previous

    def observe(self, operation):
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        if self.progress is not None:
            self.progress.operation(OPERATION_LABELS[operation])
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        raw, prompts = self.call(['/usr/bin/python3', '-I', '-c', program, operation, version], operation)
        require(isinstance(raw, bytes) and 0 < len(raw) <= 2048, 'ui:response-size')
        result = json.loads(raw)
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation in ('standard-app-grid', *accessible_ui.SESSION_POINTER_OPERATIONS):
            require(type(result) is dict and set(result) == {*expected, 'pointer'}, 'ui:response')
            point = result['pointer']
            expected['pointer'] = self.point(point)
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
        if prompts:
            result['system_prompts'] = prompts
        return result
