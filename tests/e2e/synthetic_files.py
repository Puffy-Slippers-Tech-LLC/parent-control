"""FILE05/FIX04 shared finite commands and task-local qualification."""
import json
from pathlib import Path

from private_artifacts import require
from watch_activity import operation


class SyntheticFiles:
    def __init__(self, transport, profile='standard'):
        require(profile in ('standard', 'single', 'count', 'sixth', 'maximum', 'oversized', 'total', 'overflow'),
                'files:profile')
        self.transport = transport
        self.profile = profile
        self.previous = None
        self.failed = False
        self.attempted = set()

    def call(self, name):
        require(not self.failed and name not in self.attempted, 'files:replay')
        require(name in ('stage', 'read', 'copy', 'rename', 'cleanup'), 'files:operation')
        self.attempted.add(name)
        self.failed = True  # Includes interrupted or uncertain transport results.
        with operation('Synthetic fixtures: ' + name):
            value = self._command(name, self.previous)
            require(value != {'refused': True}, 'files:guest-refusal')
            if name == 'cleanup':
                require(value == {'absent': True}, 'files:cleanup-result')
                require(self._command('absent', value) == value, 'files:cleanup-readback')
            else:
                # A separate process independently lists, opens and reads bytes.
                readback = self._command('read', value)
                require(readback == value, 'files:independent-readback')
            self.previous = value
        self.failed = False
        return value

    def _command(self, name, previous):
        program = Path(__file__).with_name('synthetic_files_guest.py').read_bytes()
        raw = self.transport.call([
            '/usr/sbin/runuser', '--user', 'onpc-parent-jamie', '--',
            '/usr/bin/python3', '-I', '-', name,
            json.dumps(previous, sort_keys=True),
            *([] if self.profile == 'standard' else [self.profile])], input=program, timeout=30)
        require(type(raw) is bytes and 0 < len(raw) <= 4096, 'files:output-bound')
        value = json.loads(raw)
        require(type(value) is dict and raw == (json.dumps(value, sort_keys=True) + '\n').encode(),
                'files:output-schema')
        return value


def fixture_actions(profiles, *, stage='chooser-fixtures', cleanup='chooser-cleanup'):
    """Bind declared file sets to one journey, retaining controllers on failure.

    Allocate no paths here: SyntheticFiles owns the finite guest commands and
    identity receipts. Each action guards every set and never retries uncertain
    input; the attempt envelope owns recovery after a failed action.
    """
    require(type(profiles) is tuple and profiles and len(set(profiles)) == len(profiles)
            and all(profile in ('standard', 'single', 'count', 'sixth', 'maximum', 'oversized',
                                'total', 'overflow') for profile in profiles), 'files:profiles')
    require(stage != cleanup, 'files:action-names')

    def prepare(journey, guard):
        require(not hasattr(journey, 'attachment_files'), 'files:fixture-replay')
        journey.attachment_files = []
        receipts = {}
        for profile in profiles:
            guard()
            files = SyntheticFiles(journey.transport, profile)
            journey.attachment_files.append(files)
            receipts[profile] = files.call('stage')
        return receipts

    def release(journey, guard):
        require(hasattr(journey, 'attachment_files')
                and tuple(files.profile for files in journey.attachment_files) == profiles,
                'files:fixture-entry')
        for files in journey.attachment_files:
            guard()
            require(files.call('cleanup') == {'absent': True}, 'files:cleanup-result')
        return {'owned_cleanup': True}

    return {stage: prepare, cleanup: release}


def _qualify_entry(journey, guard):
    guard()
    files = SyntheticFiles(journey.transport)
    staged = files.call('stage')
    require(set(staged['files']) == {'Synthetic note.txt', 'Second note.txt'}, 'files:stage-result')
    files.call('read')
    with operation('Checking synthetic fixture refusal before mutation'):
        for invalid in ('../copy', 'unregistered', 'stage', 'rename'):
            require(files._command(invalid, staged) == {'refused': True}, 'files:refusal')
            require(files._command('read', staged) == staged, 'files:refusal-mutated')
    copied = files.call('copy')
    require(set(copied['files']) == {*staged['files'], 'Synthetic copy.txt'}, 'files:copy-result')
    with operation('Checking duplicate synthetic destination refusal'):
        require(files._command('copy', copied) == {'refused': True}, 'files:duplicate')
        require(files._command('read', copied) == copied, 'files:duplicate-mutated')
    renamed = files.call('rename')
    require(set(renamed['files']) == {*staged['files'], 'Renamed synthetic note.txt'},
            'files:rename-result')
    files.call('cleanup')
    guard()
    return {'profile': 'synthetic-text', 'exact_content_readback': True,
            'invalid_operations_unchanged': True, 'owned_cleanup': True}


def qualify(journey, guard):
    first = _qualify_entry(journey, guard)
    second = _qualify_entry(journey, guard)
    require(first == second, 'files:independent-entry')
    return {**second, 'independent_entries': 2}
