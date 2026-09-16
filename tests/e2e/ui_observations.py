"""Guarded controller for public UI operations, with sanitized evidence."""

import json

import accessible_ui
from private_artifacts import require
import system_runner as system


class UiObservations:
    def __init__(self, transport, *, system_prompt=None):
        self.transport = transport
        self.initial_settings = None
        self.new_settings = None
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
        if self.system_prompt is None:
            return self.transport.call(argv, timeout=90), []
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
            self.transport.call(argv, timeout=90, on_output=output)
            require(not pending and len(results) == 1, 'ui:response-incomplete')
            return results[0], prompts
        finally:
            commands.progress = previous

    def observe(self, operation):
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        raw, prompts = self.call(['/usr/bin/python3', '-I', '-c', program, operation, version], operation)
        require(isinstance(raw, bytes) and 0 < len(raw) <= 2048, 'ui:response-size')
        result = json.loads(raw)
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'standard-app-grid':
            require(type(result) is dict and set(result) == {*expected, 'pointer'}, 'ui:response')
            point = result['pointer']
            expected['pointer'] = self.point(point)
        if operation in accessible_ui.PICKER_OPERATIONS or operation in accessible_ui.GREETER_NAVIGATION:
            require(type(result) is dict and set(result) == {*expected, 'navigation'}, 'ui:response')
            keys = result['navigation']
            require(type(keys) is list and 1 <= len(keys) <= 32 and keys[0] == 'home'
                    and all(key == 'down' for key in keys[1:]), 'ui:navigation')
            expected['navigation'] = keys
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
            if operation in ('parent-selected', 'discovery-selected'):
                require(self.initial_settings is None, 'ui:selection-replay')
                if operation == 'discovery-selected':
                    require(settings['limit_enabled'] is False and settings['allowance'] == ['0 minutes'],
                            'ui:initial-settings')
                self.initial_settings = settings
            elif operation == 'new-child-selected':
                require(self.initial_settings is not None and self.new_settings is None,
                        'ui:selection-replay')
                self.new_settings = settings
            elif operation == 'new-child-screen':
                require(self.new_settings is not None and settings == self.new_settings,
                        'ui:settings-changed')
            else:
                require(self.initial_settings is not None and settings == self.initial_settings,
                        'ui:settings-changed')
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
