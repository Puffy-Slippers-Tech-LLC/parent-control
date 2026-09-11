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
from vt6_command import CommandRoundTrip


class ReadOnlyObservations:
    def __init__(self, transport, *, on_diagnostic=None):
        self._transport = transport
        self._config = dict(transport.config)
        self._failed = False
        self._on_diagnostic = on_diagnostic
        self._boot = None
        self._vt6_recipient = None
        self._vt6_recipient_stage = 0
        self._vt6_shell = None

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
                                                      'vt6-getty', 'vt6-password', 'vt6-session', 'vt6-install-password',
                                                      'vt6-reboot-password',
                                                      'vt6-getty-identity', 'vt6-password-identity',
                                                      'vt6-password-recheck', 'vt6-shell-identity',
                                                      'vt6-login-diagnostic',
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
                'vt6-getty-identity': (guest_observations.VT6_GETTY_IDENTITY, 60),
                'vt6-password-identity': (guest_observations.VT6_PASSWORD_IDENTITY, 30),
                'vt6-password-recheck': (guest_observations.VT6_PASSWORD_IDENTITY, 30),
                'vt6-shell-identity': (guest_observations.VT6_SHELL_IDENTITY, 45),
                'vt6-login-diagnostic': (guest_observations.VT6_LOGIN_DIAGNOSTIC, 30),
                'vt6-session': (guest_observations.VT6_SESSION, 110),
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
            recipient_stages = ('vt6-getty-identity', 'vt6-password-identity',
                                'vt6-password-recheck', 'vt6-shell-identity')
            if name in recipient_stages:
                require(self._boot is not None and self._vt6_recipient_stage < len(recipient_stages) and
                        name == recipient_stages[self._vt6_recipient_stage],
                        'observation:vt6-recipient-order')
            self._guard()
            raw = self._transport.call(['/usr/bin/python3', '-c', program], timeout=timeout)
            self._guard()
            require(isinstance(raw, bytes) and 0 < len(raw) <= 1024,
                    'observation:invalid-output')
            if name in recipient_stages:
                result = self._accept_vt6_recipient(name, raw)
            elif name == 'vt6-login-diagnostic':
                result = json.loads(raw)
                require(type(result) is dict and set(result) == {
                    'executable', 'login_timeout_seconds', 'timeout_source',
                    'login_version', 'recipient_sha256'}
                    and result['executable'] in ('login', 'agetty', 'other')
                    and type(result['login_timeout_seconds']) is int
                    and 0 <= result['login_timeout_seconds'] <= 86400
                    and result['timeout_source'] in ('login.defs', 'default')
                    and type(result['login_version']) is str
                    and re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,3}){1,2}', result['login_version'])
                    and type(result['recipient_sha256']) is str
                    and re.fullmatch(r'[0-9a-f]{64}', result['recipient_sha256'])
                    and raw == (json.dumps(result, sort_keys=True) + '\n').encode(),
                    'observation:invalid-output')
                recipient = result.pop('recipient_sha256')
                result['matches_pinned_recipient'] = (self._vt6_recipient is not None
                    and recipient == self._vt6_recipient[1])
            elif name == 'startup-broker':
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
            elif name in ('serial-session', 'vt6-session'):
                require(raw == (name + '-ready\n').encode(), 'observation:invalid-output')
                surface = name.removesuffix('-session')
                result = {'fixture_role': 'parent', 'active_local_' + surface + '_session': True,
                          'unexpected_user_session': False}
                if name == 'vt6-session':
                    result['active_vt6_verified'] = True
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
                'observation:vt6-recipient-order', 'observation:vt6-recipient-changed',
                'observation:startup-enforcement-order',
                *('observation:startup-enforcement-' + stage
                  for stage in startup_observations.REFUSALS),
            }:
                raise
            raise EvidenceError('observation:probe-failed') from None

    def _accept_vt6_recipient(self, name, raw):
        """Keep identity private; a matching digest is continuity, not input authority.

        This fixed four-read sequence cannot be repinned or retried. The caller
        still owns worker/capture provenance, pixel checks and durable one-use
        authorization. The shell read proves lineage, not command readiness;
        no read proves empty input or authorizes password submission.
        """
        identity = json.loads(raw)
        probe = 'vt6-password-identity' if name == 'vt6-password-recheck' else name
        digests = ('boot_sha256', 'recipient_sha256', 'shell_sha256') if name == 'vt6-shell-identity' else (
            'boot_sha256', 'recipient_sha256')
        require(isinstance(identity, dict) and set(identity) == {'probe', *digests} and
                identity['probe'] == probe and all(
                    isinstance(identity[key], str) and re.fullmatch(r'[0-9a-f]{64}', identity[key])
                    for key in digests) and
                raw == (json.dumps(identity, sort_keys=True) + '\n').encode(),
                'observation:invalid-output')
        pinned = (identity['boot_sha256'], identity['recipient_sha256'])
        require(identity['boot_sha256'] == self._boot and
                (self._vt6_recipient is None or self._vt6_recipient == pinned),
                'observation:vt6-recipient-changed')
        self._vt6_recipient = pinned
        self._vt6_recipient_stage += 1
        result = {'boot_sha256': identity['boot_sha256'], 'active_vt6_verified': True}
        if name == 'vt6-getty-identity':
            result['vt6_getty_verified'] = True
        elif name == 'vt6-shell-identity':
            self._vt6_shell = identity['shell_sha256']
            result.update(vt6_login_continuity_verified=True,
                          vt6_foreground_shell_verified=True)
        else:
            result.update(vt6_login_process_verified=True, terminal_echo_disabled=True,
                          vt6_recipient_continuity_verified=True)
        return result

    def vt6_command_boundary(self):
        """Create the sole fixed command round trip after ordered lineage proof.

        This is a nonsecret keyboard operation, not a password authorization.
        Failure and replay share this observer's permanent refusal latch.
        """
        require(not self._failed, 'observation:previous-failure')
        try:
            require(self._vt6_recipient_stage == 4 and self._vt6_shell is not None,
                    'observation:vt6-command-order')
            self._vt6_recipient_stage = 5
            return CommandRoundTrip(self, self._vt6_recipient, self._vt6_shell)
        except BaseException:
            self._failed = True
            raise
