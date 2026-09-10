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
import startup_observations
from private_artifacts import EvidenceError, require


class ReadOnlyObservations:
    def __init__(self, transport, *, on_diagnostic=None):
        self._transport = transport
        self._config = dict(transport.config)
        self._failed = False
        self._on_diagnostic = on_diagnostic
        self._boot = None

    def _guard(self):
        require(self._transport.config == self._config, 'observation:transport-replaced')
        self._transport.guard(self._config)

    def wait_boot_change(self, previous_boot_sha256, *, on_diagnostic=None):
        """Corroborate a separately recorded customer action with fresh reads.

        The caller owns ordered action/acknowledgement checkpoints. This method
        cannot request a reboot, reset a failed observer, repin a host key or
        accept a replacement domain. A fresh BOOT read must agree with readiness
        so a second reboot during reconnection cannot be silently accepted.
        """
        require(not self._failed, 'observation:previous-failure')
        try:
            require(self._boot is not None and previous_boot_sha256 == self._boot,
                    'observation:unobserved-previous-boot')
            self._guard()
            raw = self._transport.wait_boot_change(previous_boot_sha256,
                                                  on_diagnostic=on_diagnostic)
            self._guard()
            require(isinstance(raw, bytes) and re.fullmatch(rb'[0-9a-f]{64}\n', raw),
                'observation:invalid-boot-output')
            after = raw.decode('ascii').strip()
            require(after != previous_boot_sha256, 'observation:boot-unchanged')
            require(self.read('boot')['boot_sha256'] == after,
                    'observation:boot-changed-again')
            print('e2e:boot-change-verified', file=sys.stderr, flush=True)
            return {'previous_boot_sha256': previous_boot_sha256,
                    'boot_sha256': after, 'boot_changed': True}
        except BaseException as error:
            self._failed = True
            print('e2e:boot-change-rejected', file=sys.stderr, flush=True)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise KeyboardInterrupt('observation:interrupted') from None
            if isinstance(error, EvidenceError) and str(error) in {
                'observation:unobserved-previous-boot', 'observation:invalid-boot-output',
                'observation:boot-unchanged', 'observation:boot-changed-again',
                'observation:transport-replaced',
            }:
                raise
            raise EvidenceError('observation:boot-change-failed') from None

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
                                                      'vt6-getty', 'vt6-password', 'vt6-install-password',
                                                      'vt6-reboot-password',
                                                      'package-absent', 'package-installed',
                                                      'installed-layout',
                                                      'install-password', 'reboot-password', 'install-refused',
                                                      'sudo-implementation', 'startup-enforcement',
                                                      'startup-broker'),
                    'observation:unknown-probe')
            program, timeout = {
                'assets': (guest_observations.ASSETS, 120),
                'greeter': (guest_observations.GREETER, 110),
                'parent-session': (guest_observations.PARENT_SESSION, 110),
                'serial-password': (guest_observations.SERIAL_PASSWORD, 20),
                'vt6-password': (guest_observations.VT6_PASSWORD, 20),
                'vt6-getty': (guest_observations.VT6_GETTY, 50),
                'vt6-install-password': (installation_observations.VT6_SUDO_PASSWORD, 20),
                'vt6-reboot-password': (installation_observations.VT6_REBOOT_PASSWORD, 20),
                'serial-session': (guest_observations.SERIAL_SESSION, 110),
                'boot': (guest_observations.BOOT, 20),
                'package-absent': (installation_observations.ABSENT, 30),
                'package-installed': (installation_observations.INSTALLED, 90),
                'installed-layout': (installation_observations.INSTALLED_LAYOUT, 90),
                'install-password': (installation_observations.SUDO_PASSWORD, 20),
                'reboot-password': (installation_observations.REBOOT_PASSWORD, 20),
                'install-refused': (installation_observations.REFUSED, 30),
                'sudo-implementation': (installation_observations.SUDO_IMPLEMENTATION, 30),
                'startup-enforcement': (startup_observations.ENFORCEMENT, 40),
                'startup-broker': (startup_observations.BROKER, 40),
            }[name]
            self._guard()
            raw = self._transport.call(['/usr/bin/python3', '-c', program], timeout=timeout)
            self._guard()
            require(isinstance(raw, bytes) and 0 < len(raw) <= 1024,
                    'observation:invalid-output')
            if name == 'startup-broker':
                result = startup_observations.parse_broker(raw)
            elif name == 'startup-enforcement':
                result = startup_observations.parse_enforcement(raw)
            elif name == 'boot':
                require(re.fullmatch(rb'[0-9a-f]{64}\n', raw) is not None,
                        'observation:invalid-output')
                result = {'boot_sha256': raw.decode('ascii').strip()}
                self._boot = result['boot_sha256']
            elif name == 'package-absent':
                require(raw == b'package-absent\n', 'observation:invalid-output')
                result = {'product_package_absent': True,
                          'core_payload_absent': True, 'product_reboot_required': False}
            elif name == 'install-refused':
                require(raw == b'install-refused-safe\n', 'observation:invalid-output')
                result = {'product_package_absent': True, 'core_payload_absent': True,
                          'product_reboot_required': False, 'install_process_absent': True}
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
            elif name == 'installed-layout':
                result = json.loads(raw)
                require(isinstance(result, dict) and set(result) == {
                    'installed_files', 'inventory_sha256', 'installed_layout_verified'}
                    and type(result['installed_files']) is int
                    and 0 < result['installed_files'] <= 100000
                    and isinstance(result['inventory_sha256'], str)
                    and re.fullmatch(r'[0-9a-f]{64}', result['inventory_sha256'])
                    and result['installed_layout_verified'] is True
                    and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                    'observation:invalid-output')
            elif name == 'sudo-implementation':
                result = json.loads(raw)
                require(isinstance(result, dict) and set(result) == {
                    'implementation', 'package_version', 'executable'}
                    and result['implementation'] == 'sudo-rs'
                    and result['executable'] == '/usr/lib/cargo/bin/sudo'
                    and isinstance(result['package_version'], str)
                    and re.fullmatch(r'0\.2\.[0-9]{1,3}-[0-9]{1,3}ubuntu[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}', result['package_version'])
                    and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                    'observation:invalid-output')
                print('e2e:sudo-implementation:' + raw.decode('ascii').strip(),
                      file=sys.stderr, flush=True)
            elif name in ('install-password', 'reboot-password',
                          'vt6-install-password', 'vt6-reboot-password'):
                refusals = {
                    (name + '-rejected:' + stage + '\n').encode(): stage
                    for stage in installation_observations.SUDO_PASSWORD_STAGES
                }
                diagnostic = re.fullmatch(
                    (name + '-rejected:(').encode('ascii')
                    + installation_observations.LOGIN_RESOLUTION_PATTERN.encode('ascii')
                    + rb')\n', raw)
                condition = refusals.get(raw)
                if diagnostic is not None:
                    condition = diagnostic[1].decode('ascii')
                if condition is not None:
                    # Persist the allowlisted condition in controller stderr
                    # before refusal stops the worker and its callback.
                    print('e2e:' + name + '-rejected:' + condition,
                          file=sys.stderr, flush=True)
                    if self._on_diagnostic is not None:
                        self._on_diagnostic(condition)
                    raise EvidenceError('observation:probe-failed')
                require(raw == (name + '-safe\n').encode(), 'observation:invalid-output')
                action = name.removeprefix('vt6-').removesuffix('-password')
                result = {'sudo_' + action + '_process_verified': True,
                          'terminal_echo_disabled': True}
                if name.startswith('vt6-'):
                    result['active_vt6_verified'] = True
            elif name == 'vt6-getty':
                require(raw == b'vt6-getty-ready\n', 'observation:invalid-output')
                result = {'active_vt6_verified': True, 'vt6_getty_verified': True}
            elif name in ('serial-password', 'vt6-password'):
                require(raw == (name + '-safe\n').encode(), 'observation:invalid-output')
                result = {name.removesuffix('-password') + '_login_process_verified': True,
                          'terminal_echo_disabled': True}
                if name == 'vt6-password':
                    result['active_vt6_verified'] = True
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
                'observation:startup-enforcement-order',
                *('observation:startup-enforcement-' + stage
                  for stage in startup_observations.REFUSALS),
            }:
                raise
            raise EvidenceError('observation:probe-failed') from None
