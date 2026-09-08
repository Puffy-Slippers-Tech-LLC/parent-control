"""Named read-only E2E observations over the controller's guarded transport.

This is a capability boundary for trusted scenario code, not a Python sandbox.
Provisioning and fault controls retain separate owners. No command, path,
stdin, timeout override, reboot, or copy operation is exposed to scenarios.
"""

import json
import re
import sys

import guest_observations
import installation_observations
from private_artifacts import EvidenceError, require


class ReadOnlyObservations:
    def __init__(self, transport):
        self._transport = transport
        self._config = dict(transport.config)
        self._failed = False

    def _guard(self):
        require(self._transport.config == self._config, 'observation:transport-replaced')
        self._transport.guard(self._config)

    def read(self, name):
        """Return validated safe fields only; any refusal ends this observer.

        Check ownership before execution and again before accepting output.
        Diagnostics never contain raw guest output or transport exception text.
        A new successful probe cannot erase a failed or interrupted observation.
        """
        require(not self._failed, 'observation:previous-failure')
        try:
            require(isinstance(name, str) and name in ('assets', 'greeter', 'parent-session',
                                                      'serial-password', 'serial-session', 'boot',
                                                      'package-absent', 'package-installed',
                                                      'install-password'),
                    'observation:unknown-probe')
            program, timeout = {
                'assets': (guest_observations.ASSETS, 120),
                'greeter': (guest_observations.GREETER, 110),
                'parent-session': (guest_observations.PARENT_SESSION, 110),
                'serial-password': (guest_observations.SERIAL_PASSWORD, 20),
                'serial-session': (guest_observations.SERIAL_SESSION, 110),
                'boot': (guest_observations.BOOT, 20),
                'package-absent': (installation_observations.ABSENT, 30),
                'package-installed': (installation_observations.INSTALLED, 90),
                'install-password': (installation_observations.SUDO_PASSWORD, 20),
            }[name]
            self._guard()
            raw = self._transport.call(['/usr/bin/python3', '-c', program], timeout=timeout)
            self._guard()
            require(isinstance(raw, bytes) and 0 < len(raw) <= 1024,
                    'observation:invalid-output')
            if name == 'boot':
                require(re.fullmatch(rb'[0-9a-f]{64}\n', raw) is not None,
                        'observation:invalid-output')
                result = {'boot_sha256': raw.decode('ascii').strip()}
            elif name == 'package-absent':
                require(raw == b'package-absent\n', 'observation:invalid-output')
                result = {'product_package_absent': True,
                          'core_payload_absent': True, 'product_reboot_required': False}
            elif name == 'package-installed':
                result = json.loads(raw)
                require(isinstance(result, dict) and set(result) == {
                    'package_sha256', 'installed_identity_verified', 'product_reboot_required'}
                    and result['installed_identity_verified'] is True
                    and result['product_reboot_required'] is True
                    and isinstance(result['package_sha256'], str)
                    and re.fullmatch(r'[0-9a-f]{64}', result['package_sha256'])
                    and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                    'observation:invalid-output')
            elif name == 'install-password':
                require(raw == b'install-password-safe\n', 'observation:invalid-output')
                result = {'sudo_install_process_verified': True,
                          'terminal_echo_disabled': True}
            elif name == 'serial-password':
                require(raw == b'serial-password-safe\n', 'observation:invalid-output')
                result = {'serial_login_process_verified': True,
                          'terminal_echo_disabled': True}
            elif name == 'serial-session':
                require(raw == b'serial-session-ready\n', 'observation:invalid-output')
                result = {'fixture_role': 'parent', 'active_local_serial_session': True,
                          'unexpected_user_session': False}
            elif name == 'parent-session':
                require(raw == b'parent-session-ready\n', 'observation:invalid-output')
                result = {'fixture_role': 'parent', 'active_local_graphical_session': True,
                          'unexpected_user_session': False}
            elif name == 'greeter':
                require(raw == b'greeter-ready\n', 'observation:invalid-output')
                result = {'active_graphical_greeter': True, 'unexpected_user_session': False}
            else:
                # Exact serialization rejects duplicate keys, trailing data,
                # booleans-as-counts, and unexpected private fields.
                result = json.loads(raw)
                require(isinstance(result, dict) and set(result) == {'files', 'sha256'}
                        and type(result['files']) is int and 0 < result['files'] <= 100000
                        and isinstance(result['sha256'], str)
                        and re.fullmatch(r'[0-9a-f]{64}', result['sha256'])
                        and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                        'observation:invalid-output')
            print('e2e:observation-' + name + '-verified', file=sys.stderr, flush=True)
            return result
        except BaseException as error:
            self._failed = True
            print('e2e:observation-rejected', file=sys.stderr, flush=True)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise KeyboardInterrupt('observation:interrupted') from None
            if isinstance(error, EvidenceError) and str(error) in {
                'observation:transport-replaced', 'observation:unknown-probe',
                'observation:invalid-output',
            }:
                raise
            raise EvidenceError('observation:probe-failed') from None
