"""FILE05/FIX04 shared finite commands and task-local qualification."""
import json
import hashlib
from pathlib import Path

from private_artifacts import EvidenceError, require
from watch_activity import operation


class SyntheticFiles:
    def __init__(self, transport, profile='standard'):
        require(profile in ('standard', 'single', 'count', 'sixth', 'maximum', 'oversized', 'total', 'overflow',
                            'name180', 'name181', 'hidden', 'mixed', 'zip', 'save'),
                'files:profile')
        self.transport = transport
        self.profile = profile
        self.previous = None
        self.failed = False
        self.attempted = set()

    def call(self, name):
        require(not self.failed and name not in self.attempted, 'files:replay')
        require(name in ('stage', 'read', 'copy', 'rename', 'cleanup', 'change-source')
                or (name == 'saved' and self.profile == 'save'), 'files:operation')
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
        source = Path(__file__).with_name('download_destination.py').read_text()
        modules = ('import sys, types\n'
                   'download_destination = types.ModuleType("download_destination")\n'
                   'sys.modules["download_destination"] = download_destination\n'
                   f'exec(compile({source!r}, "download_destination.py", "exec"), '
                   'download_destination.__dict__)\n')
        program = modules.encode() + program
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


def read_declared_text(transport, receipt, *, attempt, user='onpc-parent-jamie',
                       artifact='synthetic-note'):
    """Inspect the fixed synthetic text through a fresh guarded SSH command."""
    require(type(attempt) is str and attempt and type(transport.config) is dict
            and transport.config.get('run') == attempt, 'text:attempt')
    require(user == 'onpc-parent-jamie' and artifact == 'synthetic-note', 'text:declaration')
    require(type(receipt) is dict and set(receipt) == {'directory', 'files'}
            and type(receipt['files']) is dict and 'Synthetic note.txt' in receipt['files'],
            'text:receipt')
    files = SyntheticFiles(transport)
    with operation('Reading declared synthetic text artifact'):
        result = files._command('open-text', {'receipt': receipt, 'artifact': artifact})
    expected = b'ONPC synthetic attachment\n'
    require(result == {'artifact': artifact, 'matched': True, 'size': len(expected),
                       'sha256': hashlib.sha256(expected).hexdigest()}, 'text:comparison')
    return result


def save_destination_actions():
    """Owned writable/unwritable preparation and independent FILE05 readback."""
    def prepare(journey, guard):
        require(not hasattr(journey, 'save_files'), 'files:save-replay')
        guard()
        journey.save_files = SyntheticFiles(journey.transport, 'save')
        return journey.save_files.call('stage')

    def saved(journey, guard):
        guard()
        require(hasattr(journey, 'save_files'), 'files:save-entry')
        result = journey.save_files.call('saved')
        require(set(result['files']) == {'Selected diagnostics.zip'}, 'files:save-result')
        return result

    def preserved(journey, guard):
        guard()
        require(hasattr(journey, 'save_files'), 'files:save-entry')
        previous = journey.save_files.previous
        require(bool(previous['files']), 'files:save-entry')
        require(journey.save_files.call('read') == previous, 'files:cancel-changed')
        return {'saved_unchanged': True, 'cancelled_absent': True}

    def cleanup(journey, guard):
        guard()
        require(hasattr(journey, 'save_files'), 'files:save-entry')
        result = journey.save_files.call('cleanup')
        del journey.save_files
        return result

    return {'save-prepare': prepare, 'save-read': saved,
            'save-preserved': preserved, 'save-cleanup': cleanup}


def fixture_actions(profiles, *, stage='chooser-fixtures', cleanup='chooser-cleanup'):
    """Bind declared file sets to one journey, retaining controllers on failure.

    Allocate no paths here: SyntheticFiles owns the finite guest commands and
    identity receipts. Each action guards every set and never retries uncertain
    input; the attempt envelope owns recovery after a failed action.
    """
    require(type(profiles) is tuple and profiles and len(set(profiles)) == len(profiles)
            and all(profile in ('standard', 'single', 'count', 'sixth', 'maximum', 'oversized',
                                'total', 'overflow', 'name180', 'name181', 'hidden', 'mixed')
                    for profile in profiles), 'files:profiles')
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


def change_attachment_source(journey, guard, *, profile='standard'):
    """Mutate the declared source using its existing chooser lifetime owner."""
    require(profile in ('standard', 'single'), 'files:source-profile')
    fixtures = getattr(journey, 'attachment_files', ())
    matches = [files for files in fixtures if files.profile == profile]
    require(len(matches) == 1, 'files:source-entry')
    guard()
    before = matches[0].previous
    changed = matches[0].call('change-source')
    expected = b'ONPC changed synthetic attachment\n'
    source = changed['files']['Synthetic note.txt']
    require(source['size'] == len(expected)
            and source['sha256'] == hashlib.sha256(expected).hexdigest(), 'files:source-content')
    require(changed['directory'] == before['directory']
            and set(changed['files']) == set(before['files'])
            and all(value == before['files'][name] for name, value in changed['files'].items()
                    if name != 'Synthetic note.txt'), 'files:source-unrelated')
    return changed


def qualify_source_change(journey, guard):
    for profile in ('standard', 'single'):
        actions = fixture_actions((profile,))
        actions['chooser-fixtures'](journey, guard)
        files = journey.attachment_files[0]
        receipt = files.previous
        with operation('Checking synthetic source refusal boundaries'):
            require(files._command('probe-source', receipt) == {
                'refused': ['path', 'owner', 'symlink', 'replaced', 'different', 'hardlink'],
                'owned_cleanup': True}, 'files:source-refusals')
            require(files._command('read', receipt) == receipt, 'files:source-preserved')
        changed = change_attachment_source(journey, guard, profile=profile)
        with operation('Checking source replay refusal'):
            require(files._command('change-source', changed) == {'refused': True},
                    'files:source-replay')
            require(files._command('read', changed) == changed, 'files:source-replay-preserved')
        actions['chooser-cleanup'](journey, guard)
        del journey.attachment_files
        guard()
    return {'independent_entries': 2, 'profiles': ['standard', 'single'],
            'exact_changed_content': True, 'wrong_entry_refused': True, 'owned_cleanup': True}


def read_declared_zip(transport, receipt, *, attempt, user='onpc-parent-jamie',
                      artifact='synthetic-archive'):
    """Read the declared ZIP; return only exact names, sizes and digests."""
    require(type(attempt) is str and attempt and type(transport.config) is dict
            and transport.config.get('run') == attempt, 'zip:attempt')
    require(user == 'onpc-parent-jamie' and artifact == 'synthetic-archive', 'zip:declaration')
    require(type(receipt) is dict and set(receipt) == {'directory', 'files'}
            and type(receipt['files']) is dict
            and set(receipt['files']) == {'Synthetic archive.zip'}, 'zip:receipt')
    with operation('Reading declared synthetic ZIP entries and contents'):
        result = SyntheticFiles(transport, 'zip')._command(
            'open-zip', {'receipt': receipt, 'artifact': artifact})
    # Independent consumer expectations, not the producer's byte constants.
    contents = {'empty/': b'', 'note.txt': b'Independent synthetic archive note\n',
                'metadata.json': b'{"kind":"synthetic","version":1}\n'}
    expected = {'artifact': artifact, 'matched': True, 'members': {
        name: {'size': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
        for name, value in contents.items()}}
    require(result == expected, 'zip:comparison')
    return result


def qualify_zip(journey, guard):
    attempt = journey.transport.config['run']
    for _ in range(2):
        guard()
        fixtures = SyntheticFiles(journey.transport, 'zip')
        receipt = fixtures.call('stage')
        read_declared_zip(journey.transport, receipt, attempt=attempt)
        with operation('Checking declared ZIP refusal boundaries'):
            for options in ({'attempt': attempt + '-wrong'},
                            {'attempt': attempt, 'user': 'onpc-child-alex'},
                            {'attempt': attempt, 'artifact': '../synthetic-archive'}):
                try:
                    read_declared_zip(journey.transport, receipt, **options)
                except EvidenceError:
                    pass
                else:
                    require(False, 'zip:controller-wrong-entry')
            for artifact in ('../synthetic-archive', '/synthetic-archive', 'unrelated'):
                require(fixtures._command('open-zip', {'receipt': receipt, 'artifact': artifact})
                        == {'refused': True}, 'zip:wrong-entry')
            require(fixtures._command('probe-zip', receipt) == {
                'refused': ['missing', 'symlink', 'replaced', 'owner', 'malformed', 'duplicate',
                            'unsafe', 'wrong-entry', 'different', 'archive-limit', 'member-limit',
                            'expanded-limit', 'count-limit'],
                'owned_cleanup': True}, 'zip:fault-refusal')
            require(fixtures._command('read', receipt) == receipt, 'zip:fixture-preserved')
        fixtures.call('cleanup')
        guard()
    return {'artifact': 'synthetic-archive', 'exact_entries_and_contents': True,
            'independent_entries': 2, 'wrong_entry_refused': True,
            'fault_matrix_refused': True, 'owned_cleanup': True}


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


def qualify_text(journey, guard):
    """Two independent prepared entries through the same shared reader."""
    attempt = journey.transport.config['run']
    expected = {'artifact': 'synthetic-note', 'matched': True,
                'size': len(b'ONPC synthetic attachment\n'),
                'sha256': hashlib.sha256(b'ONPC synthetic attachment\n').hexdigest()}
    for _ in range(2):
        guard()
        fixtures = SyntheticFiles(journey.transport)
        receipt = fixtures.call('stage')
        require(read_declared_text(journey.transport, receipt, attempt=attempt) == expected,
                'text:valid-entry')
        with operation('Checking declared text refusal boundaries'):
            for options in ({'attempt': attempt + '-wrong'},
                            {'attempt': attempt, 'user': 'onpc-child-alex'},
                            {'attempt': attempt, 'artifact': '../synthetic-note'}):
                try:
                    read_declared_text(journey.transport, receipt, **options)
                except EvidenceError:
                    pass
                else:
                    require(False, 'text:controller-wrong-entry')
            for bad in (
                    {'receipt': receipt, 'artifact': '../synthetic-note'},
                    {'receipt': receipt, 'artifact': '/synthetic-note'},
                    {'receipt': {'directory': [0], 'files': receipt['files']},
                     'artifact': 'synthetic-note'},
                    {'receipt': receipt, 'artifact': 'unrelated'}):
                require(fixtures._command('open-text', bad) == {'refused': True},
                        'text:wrong-entry')
            require(fixtures._command('probe-text', receipt) ==
                    {'refused': ['missing', 'symlink', 'replaced', 'empty', 'different', 'oversized'],
                     'owned_cleanup': True}, 'text:fault-refusal')
            require(fixtures._command('read', receipt) == receipt, 'text:fixture-preserved')
        fixtures.call('cleanup')
        guard()
    return {'artifact': 'synthetic-note', 'exact_content': True,
            'independent_entries': 2, 'wrong_entry_refused': True,
            'fault_matrix_refused': True, 'owned_cleanup': True}
