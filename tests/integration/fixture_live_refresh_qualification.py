"""Engineering proof of the actual Ubuntu idle-maintenance refresh boundary.

The host launcher keeps its input owner and VM checkout across these two fixed
phases, editing/building B only after retain-a has independently used A.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

from execution import open_source
import fixture_maintenance as maintenance
import fixture_provision_qualification as proof
from qualification_storage import allocate, recovery_session
import system_runner as system
import vm_control as control
from vm_probe import connect
from tools import fixture_bundle, fixture_execution, fixture_manifest, fixture_provision
from tools.test_storage import authenticated_input
from watch_activity import operation

NAME = 'fixture-live-refresh-qualification.json'
SCHEMA = 'onpc-fixture-live-refresh-qualification-v1'
SUBSETS = ('trusted-hard',)
EDITED = 'tests/fixtures/onpc_test_application.c'


def require(value, reason):
    system.require(value, 'fixture-live-refresh:' + reason)


def selected_target():
    require(proof.prepare_vm.vm_config.selected().name == 'onpc-Ubuntu26.04',
            'target-not-qualified')


def identity(lease):
    lease.guard()
    snapshots = {item.getName(): hashlib.sha256(item.getXMLDesc(0).encode()).hexdigest()
                 for item in lease.source.domain.listAllSnapshots(0)}
    require(lease.source.domain.UUIDString() == lease.state['domain_uuid']
            and lease.source.domain.ID() == lease.state['domain_id'], 'instance-changed')
    return {key: lease.state[key] for key in
            ('domain_uuid', 'domain_id', 'run', 'baseline_sha256')} | {'snapshots': snapshots}


def read_checkpoint(lease):
    require(lease.capture.private_directory() == lease.capture.directory_identity,
            'checkpoint-directory-changed')
    path = lease.directory / NAME
    pinned = system.baseline.identity(path, private=True, mode=0o600)
    require(path.stat().st_size <= 65536, 'checkpoint-size')
    value = system.baseline.parse_json(path.read_bytes())
    require(type(value) is dict and set(value) == {
        'schema', 'selection', 'source_selection', 'binding', 'identity', 'runtime_used'}
        and value['schema'] == SCHEMA and value['runtime_used'] is True
        and type(value['identity']) is dict and set(value['identity']) == {
            'domain_uuid', 'domain_id', 'run', 'baseline_sha256', 'snapshots'}
        and type(value['binding']) is dict, 'checkpoint-schema')
    selection = fixture_execution.Selection.from_record(value['selection'])
    fixture_execution.validate_source_selection(value['source_selection'], selection)
    require(value['identity']['run'] == lease.state['run']
            and value['identity']['domain_uuid'] == lease.state['domain_uuid']
            and value['identity']['baseline_sha256'] == lease.state['baseline_sha256']
            and value['binding']['run'] == lease.state['run']
            and value['binding']['vm_uuid'] == lease.state['domain_uuid'], 'checkpoint-owner')
    require(system.baseline.identity(path, private=True, mode=0o600) == pinned,
            'checkpoint-replaced')
    return value, pinned


def cleanup_checkpoint(lease):
    """Retire only this run's fixed checkpoint after ordinary owned recovery."""
    path = lease.directory / NAME
    if not os.path.lexists(path):
        return
    _, pinned = read_checkpoint(lease)
    require(lease.state['phase'] == 'complete' and lease.source.domain.ID() == -1,
            'checkpoint-cleanup-before-recovery')
    lease.guard(off=True)
    require(system.baseline.identity(path, private=True, mode=0o600) == pinned,
            'checkpoint-replaced')
    path.unlink()
    system.baseline.sync_directory(lease.directory)


def write_checkpoint(lease, selection, source_selection, receipt):
    value = {'schema': SCHEMA, 'selection': selection.record(),
             'source_selection': source_selection, 'binding': receipt.binding,
             'identity': identity(lease), 'runtime_used': True}
    path = lease.directory / NAME
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(system.baseline.encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    system.baseline.sync_directory(lease.directory)
    read_checkpoint(lease)
    return value


def source_proof(allocation, selection, manifest, replacement=None, replacement_manifest=None):
    """Read the actual private producer origin through its authenticated pin."""
    expected = {'source'} if replacement is None else {'source', 'source-edit.json'}
    require(set(os.listdir(allocation)) == expected, 'source-inventory')
    source = os.open('source', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=allocation)
    try:
        pinned = os.fstat(source)
        root = Path('/proc/self/fd/' + str(source)).resolve(strict=True)
        current, _ = fixture_bundle.source_snapshot(root)
        original = manifest['inputs']['source']
        if replacement is None:
            require(current == original, 'source-not-original-a')
            return {'source_sha256': fixture_bundle.digest(current), 'edited': False}
        data = fixture_manifest._decode(fixture_manifest._read(
            allocation, 'source-edit.json', fixture_manifest.MAX_MANIFEST))
        require(type(data) is dict and set(data) == {'schema', 'selection',
            'replacement_selection', 'before', 'after', 'environment', 'edited'}
            and data['schema'] == 'onpc-fixture-live-refresh-source-v1'
            and data['selection'] == selection.record()
            and data['replacement_selection'] == replacement.record()
            and data['before'] == original and data['after'] == current
            and data['environment'] == manifest['inputs']['toolchain']['environment']
            and data['environment'] == replacement_manifest['inputs']['toolchain']['environment']
            and data['edited'] == EDITED and current == replacement_manifest['inputs']['source']
            and set(current) == set(original)
            and {name for name in current if current[name] != original[name]} == {EDITED},
            'actual-source-edit-required')
        require(any(manifest['members'][key]['sha256'] != replacement_manifest['members'][key]['sha256']
                    for key in fixture_manifest.select(SUBSETS)), 'replacement-runtime-not-changed')
        return {'before_sha256': fixture_bundle.digest(original),
                'after_sha256': fixture_bundle.digest(current), 'edited': EDITED}
    finally:
        current_entry = os.stat('source', dir_fd=allocation, follow_symlinks=False)
        os.close(source)
        require((pinned.st_dev, pinned.st_ino) == (current_entry.st_dev, current_entry.st_ino),
                'producer-source-replaced')


def observed_runtime(lease, transport, manifest, receipt):
    # Independent fixture use shares the existing persistent owner. A lost
    # witness reply or controller death must not leave reusable readiness.
    record = maintenance._load(lease)
    require(record['phase'] == 'ready' and record['binding'] == receipt.binding,
            'runtime-owner-not-ready')
    maintenance._idle(lease, transport, record)
    record['phase'] = 'pending'
    maintenance._save(lease, record)
    try:
        observed = proof.audit(transport, manifest, SUBSETS)
        members = proof.validate_readback(observed, manifest, SUBSETS, receipt.binding, installed=False)
        witnesses = proof.runtime_witnesses(transport, members, observed['accounts'], 'ubuntu')
        require(maintenance._load(lease) == record, 'runtime-owner-changed')
        maintenance._idle(lease, transport, record)
    except BaseException:
        if maintenance._load(lease) == record:
            record['phase'] = 'unavailable'
            maintenance._save(lease, record)
        raise
    record['phase'] = 'ready'
    maintenance._save(lease, record)
    return observed, witnesses


def terminal(lease, transport, receipt):
    controller = fixture_provision.Provisioner(lease, transport, register_staging=lambda _: None)
    proof.require_terminal(controller)
    try:
        controller.require_ready(receipt)
    except ValueError as error:
        require(str(error) == 'fixture-provision:terminal-attempt', 'old-readiness-refusal')
    else:
        raise system.Error('fixture-live-refresh:old-readiness-released-input')


def retain_a(lease, selection, source_selection, manifest, source_allocation):
    require(not os.path.lexists(lease.directory / NAME), 'prior-checkpoint-requires-recovery')
    origin = source_proof(source_allocation, selection, manifest)
    transport = maintenance.transport_for(lease)
    fixture_provision.Provisioner(lease, transport, register_staging=lambda _: None).wait_environment()
    before = proof.audit(transport, manifest, SUBSETS)
    require(not before['files'] and not before['unselected_present'] and not before['staging']
            and not before['installed'], 'clean-maintenance-required')
    receipt = maintenance.synchronize(lease, selection, subsets=SUBSETS, transport=transport)
    observed, witnesses = observed_runtime(lease, transport, manifest, receipt)
    proof.unchanged_policy(before, observed)
    checkpoint = write_checkpoint(lease, selection, source_selection, receipt)
    return {'phase': 'retain-a', 'outcome': 'passed', 'qualification_complete': False,
            'binding': receipt.binding, 'identity': checkpoint['identity'], 'source': origin,
            'runtime_witnesses': witnesses, 'readback': observed,
            'maintenance_preserved_for_host_build': True, 'scenario_input_released': False}


def replace_b(lease, selection, replacement, source_selection, manifest,
              replacement_manifest, source_allocation):
    control.resume(lease, fixture_maintenance=True)
    checkpoint, _ = read_checkpoint(lease)
    require(checkpoint['selection'] == selection.record()
            and checkpoint['source_selection'] == source_selection
            and checkpoint['identity'] == identity(lease), 'retained-a-owner-changed')
    origin = source_proof(source_allocation, selection, manifest, replacement, replacement_manifest)
    transport = maintenance.transport_for(lease)
    before = proof.audit(transport, manifest, SUBSETS)
    proof.validate_readback(before, manifest, SUBSETS, checkpoint['binding'], installed=False)
    boundary = proof.RecordingBoundary(transport)
    receipt = maintenance.synchronize(lease, replacement, subsets=SUBSETS,
                                      transport=transport, boundary=boundary)
    observed, witnesses = observed_runtime(lease, transport, replacement_manifest, receipt)
    members = proof.selected_members(replacement_manifest, SUBSETS, observed['accounts'])
    expected_transfer = {key: {field: member[field] for field in ('length', 'sha256')}
                         for key, member in members.items()}
    require(boundary.transfers == [expected_transfer], 'nonminimal-replacement-transfer')
    require(receipt.binding['generation'] == checkpoint['binding']['generation'] + 1
            and all(receipt.binding[name] == checkpoint['binding'][name]
                    for name in ('vm_uuid', 'boot_sha256', 'run', 'attempt_id', 'subsets')),
            'diagnostic-generation-or-instance-changed')
    require(checkpoint['identity'] == identity(lease), 'snapshot-or-domain-changed')
    proof.unchanged_policy(before, observed)
    first = proof.audit(transport, replacement_manifest, SUBSETS)
    repeated_boundary = proof.RecordingBoundary(transport)
    repeated = maintenance.synchronize(lease, replacement, subsets=SUBSETS,
        transport=transport, boundary=repeated_boundary)
    require(repeated == receipt and not repeated_boundary.transfers
            and not set(repeated_boundary.actions).intersection(
                {'reserve', 'stage', 'place', 'activate', 'clean'}), 'repeat-mutated')
    final = proof.audit(transport, replacement_manifest, SUBSETS)
    proof.verify_repeat(first, final)
    proof.unchanged_policy(before, final)
    # One real replacement loses its reply after SSH has staged A. Do not
    # repeat it or attempt same-boot repair; normal maintenance stop owns it.
    interrupted = proof.InterruptedBoundary(transport)
    try:
        maintenance.synchronize(lease, selection, subsets=SUBSETS,
                                transport=transport, boundary=interrupted)
    except proof.LostReply:
        terminal(lease, transport, receipt)
    else:
        raise system.Error('fixture-live-refresh:lost-reply-not-exercised')
    request = interrupted.interrupted_request
    require('replaces' in request and request['replaces']['binding'] == receipt.binding,
            'lost-reply-not-replacement')
    failed = proof.audit(transport, replacement_manifest, SUBSETS)
    require(failed['staging'] == [Path(request['staging']).name], 'lost-reply-staging-missing')
    proof.verify_repeat(final, {**failed, 'staging': []})
    staged_members = proof.selected_members(manifest, SUBSETS, failed['accounts'])
    staged = json.loads(transport.call(['/usr/bin/python3', '-I', '-c', proof.STAGING_AUDIT],
        input=system.baseline.encode({'staging': request['staging'],
            'stage_identity': request['stage_identity'],
            'stage_files': interrupted.stage_reply['identities'], 'members': staged_members}),
        timeout=60, attempts=1))
    require(staged == {'staging': request['staging'], 'selected': sorted(staged_members),
                      'retained': True}, 'lost-reply-independent-stage-proof')
    action_count = len(interrupted.actions)
    try:
        maintenance.synchronize(lease, replacement, subsets=SUBSETS,
                                transport=transport, boundary=interrupted)
    except system.Error as error:
        require(str(error) == 'fixture-maintenance:unavailable-until-owned-stop',
                'persistent-unavailable-refusal')
    else:
        raise system.Error('fixture-live-refresh:unavailable-owner-released-input')
    require(len(interrupted.actions) == action_count, 'lost-reply-retried')
    require(checkpoint['identity'] == identity(lease), 'fault-changed-instance-or-snapshots')
    return {'phase': 'replace-b', 'outcome': 'passed', 'qualification_complete': True,
            'source': origin, 'original_binding': checkpoint['binding'], 'binding': receipt.binding,
            'identity': checkpoint['identity'], 'runtime_witnesses': witnesses, 'readback': final,
            'replacement_actions': boundary.actions, 'repeat_actions': repeated_boundary.actions,
            'repeat_without_writes': True, 'lost_reply_actions': interrupted.actions,
            'lost_reply_staging': staged, 'unavailable_readiness_verified': True,
            'scenario_input_released': False, 'product_acceptance': False}


def main(*, phase, selection, source_selection, replacement_selection=None):
    directory = source = lease = None
    commands = cleanup_commands = None
    try:
        require(os.geteuid() == 0, 'root-required')
        selected_target()
        require(phase in ('retain-a', 'replace-b')
                and (replacement_selection is not None) == (phase == 'replace-b'), 'phase-arguments')
        selection = fixture_execution.Selection.from_record(selection)
        require(selection.target == 'ubuntu', 'input-target')
        source_selection = fixture_execution.validate_source_selection(source_selection, selection)
        replacement = (None if replacement_selection is None else
                       fixture_execution.Selection.from_record(replacement_selection))
        if replacement is not None:
            require(replacement.target == 'ubuntu' and replacement != selection, 'replacement-target')
        os.umask(0o077)
        with ExitStack() as pins:
            pins.enter_context(authenticated_input(selection.record()))
            source_allocation = pins.enter_context(authenticated_input(source_selection))
            manifest = fixture_execution.verify(selection)
            fixture_provision.authenticated_bundle(selection)
            replacement_manifest = None
            if replacement is not None:
                pins.enter_context(authenticated_input(replacement.record()))
                replacement_manifest = fixture_execution.verify(replacement)
                fixture_provision.authenticated_bundle(replacement)
            from tools.test_storage import scratch_directory
            scratch = Path(tempfile.mkdtemp(prefix='onpc-fixture-live-refresh-',
                                            dir=scratch_directory()))
            commands = system.EvidenceCommands(scratch)
            commands.directory = scratch
            source, guestfs = open_source()
            lease = system.Lease(source, commands,
                lambda disk, digest: system.baseline.inspect_guest(guestfs, disk, digest),
                graphics_type='vnc')

            def stop_owned(cleanup_directory):
                nonlocal lease, cleanup_commands
                lease.release()
                cleanup_directory.mkdir(mode=0o700)
                cleanup_commands = system.EvidenceCommands(cleanup_directory)
                cleanup_commands.directory = cleanup_directory
                lease = system.Lease(source, cleanup_commands,
                    lambda disk, digest: system.baseline.inspect_guest(guestfs, disk, digest),
                    graphics_type='vnc')
                control.operate(lease, 'stop', [])
                cleanup_checkpoint(lease)

            phase_completed = False
            try:
                if phase == 'retain-a':
                    require(not os.path.lexists(lease.directory / NAME),
                            'prior-checkpoint-requires-recovery')
                    # Match ordinary maintenance startup: its transport session
                    # closes before the detached keeper starts. The keeper must
                    # never inherit this phase report's diagnostic owner.
                    control.operate(lease, 'start', [], fixture_maintenance=True)
                with recovery_session():
                    directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-live-refresh-'))
                    private = directory / 'private'
                    private.mkdir(mode=0o700)
                    commands.evidence_path = private / 'commands.json'
                    commands._save()
                    with operation('Qualifying idle Ubuntu fixture refresh: ' + phase):
                        result = (retain_a(lease, selection, source_selection, manifest, source_allocation)
                            if phase == 'retain-a' else replace_b(lease, selection, replacement,
                                source_selection, manifest, replacement_manifest, source_allocation))
                    if phase == 'replace-b':
                        stop_owned(private / 'cleanup')
                        require(lease.state['phase'] == 'complete' and source.domain.ID() == -1,
                                'owned-recovery-incomplete')
                        result['owned_baseline_restoration_verified'] = True
                    (directory / 'result.json').write_bytes(system.baseline.encode(result))
                phase_completed = True
            finally:
                own_partial_start = (phase == 'retain-a' and not phase_completed
                    and lease.fd is not None and lease.original_id == -1
                    and type(lease.state) is dict
                    and lease.state.get('run') == lease.ownership_run
                    and lease.state.get('phase') != 'complete')
                if own_partial_start:
                    # Reopen through the ordinary persistent maintenance owner,
                    # exactly as a separate public stop command does.
                    stop_owned(scratch / 'cleanup')
        print('fixture-live-refresh: ' + phase + ' passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        failure = traceback.format_exc()
        # Startup can fail before a report owner exists. Retain that trace only
        # after the exact partial start has had its ordinary owned cleanup.
        try:
            with recovery_session():
                directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-live-refresh-error-'))
                (directory / 'controller-error.txt').write_text(failure)
                for name, recorded in (('commands.json', commands),
                                       ('cleanup-commands.json', cleanup_commands)):
                    if recorded is not None:
                        (directory / name).write_bytes(system.baseline.encode(recorded.records))
        except (Exception, KeyboardInterrupt) as diagnostic_error:
            print('fixture-live-refresh: diagnostic retention unavailable ('
                  + type(diagnostic_error).__name__ + ')', file=sys.stderr, flush=True)
        print('fixture-live-refresh: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is None and isinstance(error, ValueError) and str(error).startswith(
                ('input:', 'fixture execution:', 'fixture-provision:', 'fixture bundle:')):
            # These validators issue fixed categories, with no credential or
            # guest output. Keep pre-allocation refusals useful too.
            print('fixture-live-refresh: ' + str(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-live-refresh: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
    finally:
        try:
            if lease is not None:
                lease.release()
        finally:
            if source is not None:
                source.close()
