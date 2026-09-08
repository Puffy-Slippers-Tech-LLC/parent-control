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

    def __init__(self, observer, verified, transfer):
        self.observer, self.verified, self.transfer = observer, verified, transfer
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
            require(self._phase < len(self.STAGES) and stage == self.STAGES[self._phase],
                    'install:phase')
            self.verified.recheck()
            require(self.verified.inputs['package_sha256'] == self._package, 'install:inputs-changed')
            boot = self.observer.read('boot')['boot_sha256']
            require(self._boot is None or self._boot == boot, 'install:boot-changed')
            if stage == 'install-ready':
                self.transfer.observe(self.observer)
                session = self.observer.read('serial-session')
                absent = self.observer.read('package-absent')
                result = {**absent, **session, 'verified_assets': True,
                          'installation_authorized': True}
            elif stage == 'install-password':
                result = self.observer.read('install-password')
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
                'install:package-mismatch',
            }:
                raise
            raise EvidenceError('install:observation-failed') from None
