"""Engineering proof of actual system preparation envelopes.

The ordinary runner's preparation-only seam stops before its first upload or
system phase. Assertions run while its lease and watched SSH transport are held.
"""
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
sys.path.insert(0, str(ROOT))

from execution import open_source
from qualification_storage import allocate, session
from suite_lease import Suite
import system_runner as system
import system_snapshots
import system_fixture_preparation as preparation
import fixture_provision_qualification as proof
from tools import fixture_bundle, fixture_execution, fixture_manifest, fixture_provision
from tools.test_storage import authenticated_input

TARGETS = {'onpc-Ubuntu26.04': 'ubuntu', 'onpc-Fedora44': 'fedora'}
INSTALLED_TARGETS = {'onpc-Ubuntu26.04': 'ubuntu'}


def selected_target(*, installed=False):
    target = proof.prepare_vm.vm_config.selected().name
    system.require(target in (INSTALLED_TARGETS if installed else TARGETS),
                   'fixture-system:target-not-qualified')
    return target


def refused_inputs(context, selection, *, installed=False):
    """Exercise the same live input boundary without releasing installation input."""
    wrong = deepcopy(selection.record())
    wrong['target'] = 'fedora' if selection.target == 'ubuntu' else 'ubuntu'
    wrong['allocation'] = wrong['allocation'].replace('onpc-native-runtime-' + selection.target + '-',
                                                     'onpc-native-runtime-' + wrong['target'] + '-')
    refusals = {}
    for label, record, reason in (
            ('missing', None, 'fixtures:execution-selection-required'),
            ('incompatible', wrong, 'fixtures:system-installed-target-not-qualified'
             if installed else 'fixtures:system-product-free-target-not-qualified')):
        try:
            preparation.prepare(context['vm'], context['lease'], context['directory'], record,
                                **({'installed': True} if installed else {}))
        except ValueError as error:
            system.require(str(error) == reason, 'fixture-system:unexpected-refusal')
            refusals[label] = reason
        else:
            raise system.Error('fixture-system:invalid-input-released')
    system.require(not (context['directory'] / 'fixture-staging-intent.json').exists(),
                   'fixture-system:refusal-wrote-staging')
    return refusals


def source_edit_proof(allocation, selection, manifest):
    """Read the authenticated actual producer checkout, edited after selection."""
    system.require(set(os.listdir(allocation)) == {'source', 'source-edit.json'},
                   'fixture-system:source-proof-inventory')
    data = fixture_manifest._decode(fixture_manifest._read(allocation, 'source-edit.json',
                                                          fixture_manifest.MAX_MANIFEST))
    system.require(type(data) is dict and set(data) == {
        'schema', 'selection', 'before', 'after', 'environment', 'edited'}
        and data['schema'] == 'onpc-fixture-source-edit-v1'
        and data['selection'] == selection.record()
        and data['before'] == manifest['inputs']['source']
        and data['environment'] == manifest['inputs']['toolchain']['environment']
        and data['edited'] == 'tests/fixtures/onpc_test_application.c',
        'fixture-system:source-proof-identity')
    before, after = data['before'], data['after']
    system.require(type(after) is dict and set(after) == set(before)
        and {name for name in before if before[name] != after[name]} == {data['edited']},
        'fixture-system:source-edit-not-observed')
    source = os.open('source', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=allocation)
    try:
        identity = os.fstat(source)
        root = Path('/proc/self/fd/' + str(source)).resolve(strict=True)
        current, _ = fixture_bundle.source_snapshot(root)
        current_entry = os.stat('source', dir_fd=allocation, follow_symlinks=False)
        system.require(current == after and
            (identity.st_dev, identity.st_ino) == (current_entry.st_dev, current_entry.st_ino),
            'fixture-system:producer-source-changed')
    finally:
        os.close(source)
    return {'original_source_sha256': fixture_bundle.digest(before),
            'edited_source_sha256': fixture_bundle.digest(after),
            'scope': 'actual-private-producer-checkout-edited-after-selection'}


def wait_environment(vm, lease, directory):
    try:
        fixture_provision.Provisioner(lease, vm,
            register_staging=lambda _: None).wait_environment()
    except Exception as failure:
        # The attempt is terminal. Preserve bounded read-only diagnostics
        # before its sole owner restores it; never repeat the failed operation.
        for name, command, limit in (
                ('status', ['/usr/bin/systemctl', 'show', 'fapolicyd.service',
                    '--property=ActiveState', '--property=SubState', '--property=Result',
                    '--property=MainPID', '--property=InvocationID',
                    '--property=ExecMainStatus'], 16384),
                ('journal', ['/usr/bin/journalctl', '--unit', 'fapolicyd.service',
                    '--boot', '--no-pager', '--lines', '80', '--output', 'short-monotonic'],
                    256 * 1024)):
            try:
                data = vm.call(command, timeout=30, attempts=1)
                system.require(type(data) is bytes and len(data) <= limit,
                               'fixture-system:diagnostic-size')
                (directory / ('failure-native-' + name + '.txt')).write_bytes(data)
            except Exception:
                try:
                    (directory / ('failure-native-' + name + '-error.txt')).write_text(
                        traceback.format_exc())
                except Exception:
                    failure.add_note('fixture-system:diagnostic-storage-unavailable')
        raise


def observer(selection, manifest, result, previous=None, source_allocation=None, *, installed=False):
    state = {}

    def observe(stage, context):
        vm, lease, directory = (context[key] for key in ('vm', 'lease', 'directory'))
        if stage == 'before':
            system.require(preparation.qualified_guest(lease.capture.state['guest'],
                           **({'installed': True} if installed else {})),
                           'fixture-system:clean-baseline-required')
            if installed:
                preparation.require_installed_restore(lease)
            state['refusals'] = refused_inputs(context, selection, installed=installed)
            wait_environment(vm, lease, directory)
            before = proof.audit(vm, manifest, preparation.SUBSETS)
            system.require(before['installed'] is installed and not before['files']
                           and not before['unselected_present'] and not before['staging']
                           and before['preserved']['@attempt-trust'] is None,
                           'fixture-system:capture-not-clean' if installed
                           else 'fixture-system:capture-not-product-and-fixture-free')
            state['before'] = before
            return
        system.require(stage == 'ready' and 'before' in state, 'fixture-system:observer-order')
        controller, receipt = context['controller'], context['receipt']
        observed = proof.audit(vm, manifest, preparation.SUBSETS)
        members = proof.validate_readback(observed, manifest, preparation.SUBSETS,
                                         receipt.binding, installed=installed)
        system.require(len(members) == 1 and receipt.binding['attempt_id'] == preparation.attempt_id(directory),
                       'fixture-system:nonminimal-or-unbound-readiness')
        proof.unchanged_policy(state['before'], observed)
        witnesses = proof.runtime_witnesses(vm, members, observed['accounts'], selection.target)
        before_repeat = proof.audit(vm, manifest, preparation.SUBSETS)
        edit = source_edit_proof(source_allocation, selection, manifest)
        # Reuse the exact original record. Source edits cannot cause a new
        # selection or silently replace nonempty execution-owned inputs.
        system.require(fixture_execution.verify(selection) == manifest,
                       'fixture-system:selected-input-changed')
        repeated = controller.provision(selection, preparation.SUBSETS,
                                        attempt_id=preparation.attempt_id(directory))
        controller.require_ready(repeated)
        system.require(repeated == receipt, 'fixture-system:version-switched')
        final = proof.audit(vm, manifest, preparation.SUBSETS)
        proof.verify_repeat(before_repeat, final)
        proof.unchanged_policy(state['before'], final)
        if previous:
            try:
                previous['controller'].require_ready(previous['receipt'])
            except ValueError as error:
                system.require(str(error) == 'fixture-provision:terminal-attempt',
                               'fixture-system:unexpected-stale-refusal')
            else:
                raise system.Error('fixture-system:old-readiness-accepted')
            result['prior_generation_refused'] = True
            controller.require_ready(receipt)
        if previous is not None:
            previous.update(controller=controller, receipt=receipt)
        result.update(binding=receipt.binding, readback=final, refusals=state['refusals'],
            runtime_witnesses=witnesses, host_edit=edit, repeat_without_writes=True,
            selected_input_unchanged=True, installation_input_released=False,
            system_phase_started=False)
        if installed:
            result.update(app_snapshot_mode='offline', installed_product_verified=True,
                          system_input_released=False)
        (directory / 'fixture-preparation-result.json').write_bytes(system.baseline.encode(result))
        return result

    return observe


def qualify(directory, assets, selection, source_selection, *, installed=False):
    target = selected_target(**({'installed': True} if installed else {}))
    selection = fixture_execution.Selection.from_record(
        preparation.selection_record(selection, target=TARGETS[target]))
    source_selection = fixture_execution.validate_source_selection(source_selection, selection)
    with authenticated_input(selection.record()):
        with authenticated_input(source_selection) as source_allocation:
            manifest = fixture_execution.verify(selection)
            fixture_provision.authenticated_bundle(selection)
            source_edit_proof(source_allocation, selection, manifest)
            return qualify_pinned(directory, assets, selection, manifest, source_allocation,
                                  **({'installed': True} if installed else {}))


def qualify_pinned(directory, assets, selection, manifest, source_allocation, *, installed=False):
    target = selected_target(**({'installed': True} if installed else {}))
    os_id = TARGETS[target]
    system.require(selection.target == os_id, 'fixture-system:target-not-qualified')
    private = directory / 'private'
    private.mkdir(mode=0o700)
    suite = Suite(open_source)
    if installed:
        # Suite's ordinary default is online. This selector qualifies the
        # distinct disk restore and new SSH bootstrap, never a memory resume.
        suite.snapshot_mode = 'offline'
    result = {'target': target, 'selection': selection.record(), 'attempts': []}
    try:
        suite.commands.directory = private
        source_assets = system.artifact_source(assets)
        # Verify the complete named input without copying its fixture collection
        # into this preparation-only result allocation.
        proof.preflight_source(source_assets)
        selected = system.resolve_selection(
            *(['authorization'] if installed else ['package', system.FIRST_CONFIGURE_CASE]),
            target_package_format='rpm' if os_id == 'fedora' else 'deb')
        ledger = system.RunLedger()
        source, _, lease = suite.acquire(ledger)
        system.require(source.domain.name() == target, 'fixture-system:target-not-qualified')
        previous = {}
        for index in range(2):
            if installed:
                # Each single-history call ends at the baseline (next_case is
                # None). Re-enter prepare_case's verified snapshot reuse path
                # so the second proof really restores the installed disk too.
                suite.prepared = False
            history = directory / ('history-' + str(index + 1))
            history.mkdir(mode=0o700)
            artifact_manifest = system.stage_assets(source_assets, history / 'input',
                                                     suite.commands, package_only=True)
            selected_digest = system.stage_selected_inputs(selected, history / 'input')
            attempt = {}
            system_snapshots.run_attempts(suite, history, selected, artifact_manifest,
                selected_digest, ledger, fixture_selection=selection.record(),
                preparation_only=True,
                preparation_observer=observer(selection, manifest, attempt, previous, source_allocation,
                    **({'installed': True} if installed else {})))
            system.require(lease.state['phase'] == 'complete' and lease.view.snapshot()[1]
                           and lease.view.domain_id is None, 'fixture-system:attempt-cleanup-incomplete')
            attempt['owned_restoration_verified'] = True
            result['attempts'].append(attempt)
            (directory / 'attempt-results.json').write_bytes(system.baseline.encode(result))
        first, second = (attempt['binding'] for attempt in result['attempts'])
        system.require(first['boot_sha256'] != second['boot_sha256']
                       and first['attempt_id'] != second['attempt_id']
                       and first['vm_uuid'] == second['vm_uuid']
                       and first['manifest_sha256'] == second['manifest_sha256']
                       and first['content_identity'] == second['content_identity'],
                       'fixture-system:fresh-readiness-required')
        fixture_execution.verify(selection)
    except BaseException:
        (private / 'controller-error.txt').write_text(traceback.format_exc())
        raise
    finally:
        suite.close()
    result['owned_baseline_restoration_verified'] = True
    return result


def main(*, assets, selection, source_selection, installed=False):
    directory = None
    try:
        system.require(os.geteuid() == 0, 'fixture-system:root-required')
        selected_target(**({'installed': True} if installed else {}))
        os.umask(0o077)
        with session():
            directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-fixture-system-'))
            result = qualify(directory, assets, selection, source_selection,
                             **({'installed': True} if installed else {}))
            (directory / 'result.json').write_bytes(system.baseline.encode(result))
        print('fixture-system: passed; evidence=' + str(directory), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        if directory is not None:
            (directory / 'controller-error.txt').write_text(traceback.format_exc())
        print('fixture-system: ' + system.error_category(error), file=sys.stderr, flush=True)
        if directory is not None:
            print('fixture-system: evidence=' + str(directory), file=sys.stderr, flush=True)
        return 1
