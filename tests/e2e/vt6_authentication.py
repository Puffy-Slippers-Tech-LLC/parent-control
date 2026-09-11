"""Fixed VT6 authentication observations for the guarded qualification worker.

Only trusted controller code constructs this boundary. Its caller persists each
proof before replying and supplies a current-worker guard from run_distribution.
"""

import hashlib
import os
import re
import stat

from private_artifacts import EvidenceError, require
from provenance import identity as file_identity
from vt6_prompt_pixels import verify_prompt_pixels


STAGES = ('vt6-login-ready', 'vt6-password-ready', 'vt6-password-screen',
          'vt6-shell', 'vt6-authenticated')
REFERENCE = 'tests/integration/graphical_smoke/needles/onpc-vt6-parent-password.png'
BOUNDARIES = ('protocol', 'worker-before', 'diagnostic-before', 'inputs-before',
    'diagnostic-after', 'boot-before', 'getty', 'password', 'pixels', 'password-recheck',
    'session', 'lineage', 'command-prepare', 'command-complete', 'session-after',
    'boot-after', 'inputs-after', 'worker-after')
# Same stable metadata as provenance.identity, plus explicit owner/group checks.
# Access time is read activity, not file identity or content provenance.
CAPTURE_FIELDS = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_uid', 'st_gid',
                  'st_size', 'st_mtime_ns', 'st_ctime_ns')
CAPTURE_PREDICATES = ('capture-name', 'capture-directory', 'capture-freshness',
    'capture-regular', 'capture-owner', 'capture-links', 'capture-size', 'capture-inode',
    'capture-mtime', 'capture-ctime', 'reference-input', 'capture-changed',
    *(f'capture-{view}-{field.removeprefix("st_")}'
      for view in ('descriptor', 'path') for field in CAPTURE_FIELDS))
REFUSALS = frozenset('vt6-auth:' + code + '-refused'
                    for code in (*BOUNDARIES, *CAPTURE_PREDICATES))


class Authentication:
    def __init__(self, directory, observer, verified, *, on_diagnostic=None):
        self.directory, self.observer, self.verified = directory, observer, verified
        self.stage = 0
        self.failed = False
        self.refusal = None
        self.boot = None
        self.capture_after = None
        self.existing_screens = set()
        self.existing_inodes = set()
        self.screen_directory_identity = None
        self.command = None
        self.capture_evidence = None
        self.on_diagnostic = on_diagnostic

    def observe(self, stage, shot, guard):
        require(not self.failed, 'vt6-auth:previous-failure')
        boundary = 'protocol'
        try:
            require(self.stage < len(STAGES) and stage == STAGES[self.stage], 'vt6-auth:order')
            require((shot is not None) == (stage == 'vt6-password-screen'), 'vt6-auth:capture-stage')
            self.stage += 1  # A failed or interrupted observation cannot be repeated.
            boundary = 'worker-before'
            guard()
            if stage == 'vt6-password-ready' and self.on_diagnostic is not None:
                boundary = 'diagnostic-before'
                self.on_diagnostic(stage, {'phase': 'before-inputs',
                    'recipient': self.observer.read('vt6-login-diagnostic'), 'recheck_ms': {}})
            boundary = 'inputs-before'
            try:
                self.verified.recheck()
            finally:
                if self.on_diagnostic is not None:
                    self.on_diagnostic(stage, {'phase': 'inputs-before',
                        'recipient': {}, 'recheck_ms': dict(self.verified.recheck_milliseconds)})
            if stage == 'vt6-password-ready' and self.on_diagnostic is not None:
                boundary = 'diagnostic-after'
                self.on_diagnostic(stage, {'phase': 'after-inputs',
                    'recipient': self.observer.read('vt6-login-diagnostic'), 'recheck_ms': {}})
            boundary = 'boot-before'
            boot = self.observer.read('boot')['boot_sha256']
            require(self.boot is None or boot == self.boot, 'vt6-auth:boot')
            self.boot = boot
            if stage == 'vt6-login-ready':
                boundary = 'getty'
                reply = self.observer.read('vt6-getty-identity')
            elif stage == 'vt6-password-ready':
                boundary = 'password'
                reply = self.observer.read('vt6-password-identity')
                self.screen_directory_identity = self._screen_directory()
                self.existing_screens = set((self.directory / 'testresults').iterdir())
                self.existing_inodes = {(info.st_dev, info.st_ino) for path in self.existing_screens
                                        for info in (path.stat(follow_symlinks=False),)}
                # Filesystem timestamp granularity can lag Python's wall clock.
                # Use a same-filesystem creation barrier plus absent path/inode;
                # the trusted current worker captures only after this receipt.
                fd = os.open(self.directory / 'testresults/vt6-capture-barrier',
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                try:
                    os.fsync(fd)
                    self.capture_after = os.fstat(fd).st_ctime_ns
                finally:
                    os.close(fd)
            elif stage == 'vt6-password-screen':
                boundary = 'pixels'
                reply = self._pixels(shot)
                # Fresh exact comparison is bracketed by the password identity
                # read before capture and this ordered same-recipient recheck.
                boundary = 'password-recheck'
                reply.update(self.observer.read('vt6-password-recheck'))
                reply['vt6_password_input_authorized'] = True
            elif stage == 'vt6-shell':
                boundary = 'session'
                session = self._session()
                boundary = 'lineage'
                self.observer.read('vt6-shell-identity')
                boundary = 'command-prepare'
                self.command = self.observer.vt6_command_boundary()
                reply = {**session, **self.command.prepare()}
            else:
                boundary = 'command-complete'
                require(self.command is not None, 'vt6-auth:command')
                reply = self.command.complete()
                boundary = 'session-after'
                reply.update(self._session())
            boundary = 'boot-after'
            require(self.observer.read('boot')['boot_sha256'] == self.boot, 'vt6-auth:boot')
            boundary = 'inputs-after'
            try:
                self.verified.recheck()
            finally:
                if self.on_diagnostic is not None:
                    self.on_diagnostic(stage, {'phase': 'inputs-after',
                        'recipient': {}, 'recheck_ms': dict(self.verified.recheck_milliseconds)})
            boundary = 'worker-after'
            guard()
            return {**reply, 'stage': stage, 'boot_sha256': self.boot}
        except BaseException as error:
            self.failed = True
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise KeyboardInterrupt('vt6-auth:interrupted') from None
            # Keep only exact controller-owned predicate codes. No exception
            # paths, terminal bytes or decoder diagnostics cross this boundary.
            code = str(error) if isinstance(error, EvidenceError) else ''
            self.refusal = (code + '-refused' if code in {
                'vt6-auth:' + item for item in CAPTURE_PREDICATES}
                else 'vt6-auth:' + boundary + '-refused')
            raise EvidenceError(self.refusal) from None

    def _session(self):
        result = self.observer.read('vt6-session')
        require(result.get('fixture_role') == 'parent'
                and result.get('unexpected_user_session') is False
                and result.get('active_local_vt6_session') is True
                and result.get('active_vt6_verified') is True, 'vt6-auth:session')
        return {'active_local_vt6_session': True, 'active_vt6_verified': True}

    def _pixels(self, shot):
        require(type(shot) is str and re.fullmatch(r'smoke-[0-9]+\.png', shot),
                'vt6-auth:capture-name')
        path = self.directory / 'testresults' / shot
        require(self._screen_directory() == self.screen_directory_identity,
                'vt6-auth:capture-directory')
        require(self.capture_after is not None and path not in self.existing_screens
                and path.resolve().parent == (self.directory / 'testresults').resolve(),
                'vt6-auth:capture-freshness')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode), 'vt6-auth:capture-regular')
            require(before.st_uid == os.geteuid(), 'vt6-auth:capture-owner')
            require(before.st_nlink == 1, 'vt6-auth:capture-links')
            require(24 <= before.st_size <= 8 * 1024 * 1024, 'vt6-auth:capture-size')
            require((before.st_dev, before.st_ino) not in self.existing_inodes,
                    'vt6-auth:capture-inode')
            require(before.st_mtime_ns >= self.capture_after, 'vt6-auth:capture-mtime')
            require(before.st_ctime_ns >= self.capture_after, 'vt6-auth:capture-ctime')
            with os.fdopen(os.dup(fd), 'rb') as stream:
                pixels = stream.read(8 * 1024 * 1024 + 1)
            reference = (self.verified.root / REFERENCE).read_bytes()
            require(hashlib.sha256(reference).hexdigest() == self.verified.source_files[REFERENCE],
                    'vt6-auth:reference-input')
            reply = verify_prompt_pixels(pixels, reference)
            current = {'descriptor': os.fstat(fd), 'path': path.stat(follow_symlinks=False)}
            expected = (file_identity(before), before.st_uid, before.st_gid)
            if any((file_identity(info), info.st_uid, info.st_gid) != expected
                   for info in current.values()):
                for field in CAPTURE_FIELDS:
                    for view, info in current.items():
                        require(getattr(before, field) == getattr(info, field),
                                f'vt6-auth:capture-{view}-{field.removeprefix("st_")}')
                require(False, 'vt6-auth:capture-changed')
            require(self._screen_directory() == self.screen_directory_identity,
                    'vt6-auth:capture-directory')
            self.capture_evidence = {'capture_sha256': hashlib.sha256(pixels).hexdigest(),
                'reference_sha256': hashlib.sha256(reference).hexdigest(),
                'capture_mtime_ns': before.st_mtime_ns, 'capture_ctime_ns': before.st_ctime_ns}
            return reply
        finally:
            os.close(fd)

    def _screen_directory(self):
        path = self.directory / 'testresults'
        info = path.stat(follow_symlinks=False)
        require(stat.S_ISDIR(info.st_mode) and path.resolve() == path
                and info.st_uid == os.geteuid() and not stat.S_IMODE(info.st_mode) & 0o022,
                'vt6-auth:capture-directory')
        return info.st_dev, info.st_ino
