"""FILE05/FIX04 shared finite commands and task-local qualification."""
import json
from pathlib import Path

from private_artifacts import require
from watch_activity import operation


class SyntheticFiles:
    def __init__(self, transport):
        self.transport = transport
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
            json.dumps(previous, sort_keys=True)], input=program, timeout=30)
        require(type(raw) is bytes and 0 < len(raw) <= 4096, 'files:output-bound')
        value = json.loads(raw)
        require(type(value) is dict and raw == (json.dumps(value, sort_keys=True) + '\n').encode(),
                'files:output-schema')
        return value


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
