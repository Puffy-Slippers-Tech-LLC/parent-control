"""Guarded controller for public UI operations, with sanitized evidence."""

import json

import accessible_ui
from private_artifacts import require
import system_runner as system


class UiObservations:
    def __init__(self, transport):
        self.transport = transport
        self.initial_settings = None

    def observe(self, operation):
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        raw = self.transport.call(['/usr/bin/python3', '-I', '-c', program, operation, version],
                                  timeout=90)
        require(isinstance(raw, bytes) and 0 < len(raw) <= 2048, 'ui:response-size')
        result = json.loads(raw)
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation == 'child-picker-opened':
            require(type(result) is dict and set(result) == {*expected, 'navigation'}, 'ui:response')
            keys = result['navigation']
            require(type(keys) is list and 1 <= len(keys) <= 32 and keys[0] == 'home'
                    and all(key == 'down' for key in keys[1:]), 'ui:navigation')
            expected['navigation'] = keys
        if operation in ('parent-selected', 'parent-returned'):
            require(type(result) is dict and set(result) == {*expected, 'settings'}, 'ui:response')
            settings = result['settings']
            require(type(settings) is dict and set(settings) == {'child', 'limit_enabled', 'allowance'}
                    and settings['child'] == 'fixture-child' and type(settings['limit_enabled']) is bool
                    and type(settings['allowance']) is list and 1 <= len(settings['allowance']) <= 2,
                    'ui:settings')
            import re
            require(all(type(value) is str and re.fullmatch(
                r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', value)
                        for value in settings['allowance']), 'ui:settings')
            expected['settings'] = settings
            if operation == 'parent-selected':
                require(self.initial_settings is None, 'ui:selection-replay')
                self.initial_settings = settings
            else:
                require(self.initial_settings is not None and settings == self.initial_settings,
                        'ui:settings-changed')
        require(result == expected, 'ui:response')
        return result
