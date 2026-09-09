"""Ordered controller acknowledgements for the fixed terminal install action.

The caller must drain serial input before each exchange and persist the returned
safe observation before publishing its reply. This boundary neither installs
nor changes the guest; it is not a complete E2E-002 callback.
"""

import re
import sys

from private_artifacts import EvidenceError, require


class InstallationBoundary:
    STAGES = ('install-ready', 'install-password', 'install-complete')
    REFUSAL_STAGES = ('install-ready', 'install-password', 'install-refused')

    def __init__(self, observer, verified, transfer, *, refusal=False):
        require(type(refusal) is bool, 'install:mode')
        self.observer, self.verified, self.transfer = observer, verified, transfer
        self.refusal = refusal
        self.stages = self.REFUSAL_STAGES if refusal else self.STAGES
        self._phase = 0
        self._failed = False
        self._boot = None
        self._package = verified.inputs['package_sha256']
        require(isinstance(self._package, str) and re.fullmatch(r'[0-9a-f]{64}', self._package),
                'install:package-required')
        require(transfer.verified is verified, 'install:transfer-inputs')

    def observe(self, stage):
        require(not self._failed, 'install:previous-failure')
        try:
            require(self._phase < len(self.stages) and stage == self.stages[self._phase],
                    'install:phase')
            self.verified.recheck()
            require(self.verified.inputs['package_sha256'] == self._package, 'install:inputs-changed')
            boot = self.observer.read('boot')['boot_sha256']
            require(self._boot is None or self._boot == boot, 'install:boot-changed')
            if stage == 'install-ready':
                self.transfer.observe(self.observer)
                session = self.observer.read('serial-session')
                absent = self.observer.read('package-absent')
                implementation = self.observer.read('sudo-implementation')
                # These distribution revisions have the audited prompt/hidden
                # input contract. Preserve observed identity before refusing a
                # new version, so an unknown guest never receives a password.
                require(implementation['implementation'] == 'sudo-rs'
                        and implementation['package_version'] in (
                            '0.2.13-0ubuntu1', '0.2.13-0ubuntu1.1', '0.2.13-0ubuntu1.2'),
                        'install:sudo-implementation')
                result = {**absent, **session, 'sudo_implementation': implementation,
                          'verified_assets': True,
                          'installation_authorized': True}
            elif stage == 'install-password':
                result = self.observer.read('install-password')
                if self.refusal:
                    result = {**result, 'installation_refused': True}
            elif stage == 'install-refused':
                result = self.observer.read('install-refused')
            else:
                result = self.observer.read('package-installed')
                require(result['package_sha256'] == self._package, 'install:package-mismatch')
                result = {**result, 'verified_package_digest': True}
            require(self.observer.read('boot')['boot_sha256'] == boot, 'install:boot-changed')
            self.verified.recheck()
            self._boot = boot
            self._phase += 1
            print('e2e:' + stage + '-verified', file=sys.stderr, flush=True)
            return {**result, 'boot_sha256': boot}
        except BaseException as error:
            self._failed = True
            print('e2e:install-boundary-rejected', file=sys.stderr, flush=True)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise KeyboardInterrupt('install:interrupted') from None
            if isinstance(error, EvidenceError) and str(error) in {
                'install:phase', 'install:inputs-changed', 'install:boot-changed',
                'install:package-mismatch', 'install:sudo-implementation',
            }:
                raise
            raise EvidenceError('install:observation-failed') from None
