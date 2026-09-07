"""Controller-owned, ordered execution records with durable failure checkpoints.

Trusted scenario code calls these methods as operations occur. No result loader,
worker-success shortcut, guest control, lease release, or pending-case override
is available. Raw identities remain only in the controller's private alias map.
"""

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import re
import sys
import time

from evidence import CLEANUP_FIELDS, fields, seconds, unique_strings
import inventory
from private_artifacts import EvidenceError, require


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def save_checkpoint(collector, sequence, event, document):
    """Shared durable snapshot envelope; a diagnostic is never an acceptance.

    Callers own their event vocabulary and supply only safe controller fields.
    The collector fsyncs each new report and refuses replacement.
    """
    require(type(sequence) is int and sequence > 0, 'recording:sequence')
    require(isinstance(event, str) and re.fullmatch(r'[a-z]+(?:-[a-z]+)*', event),
            'recording:event')
    collector.save_report(f'event-{sequence:06d}', {
        **document, 'schema_version': 1, 'run_id': collector.run_id,
        'event': event, 'sequence': sequence,
    })


class ScenarioRecorder:
    """Record one selected case at a time against an independently frozen plan.

    Checkpoints are new private reports, never replacements. A started action
    remains visibly incomplete if the process dies before its completion report.
    Report failure is latched in the contract before any further operation.
    """

    def __init__(self, contract, collector):
        require(contract.run_id == collector.run_id, 'recording:collector-run')
        self.contract, self.collector = contract, collector
        self._cases = contract.plan['cases']
        self._records = []
        self._case = self._record = self._active = None
        self._started = None
        self._sequence = 0
        self._boots, self._sessions = {}, {}
        self._closed = False
        self._next_step = 0

    @property
    def records(self):
        result = copy.deepcopy(self._records)
        for record in result:
            case_id = record['scenario_id'] + '/' + record['variant_id']
            record.update(self.contract.failure_state(case_id))
        return result

    def elapsed(self):
        value = time.monotonic() - self._started
        require(seconds(value), 'recording:clock')
        return value

    def _fail(self, category, code):
        case_id = self._case['case_id']
        self.contract.record_failure(case_id, category, code,
                                     step_id=self._active['step_id'] if self._active else None,
                                     monotonic_seconds=self.elapsed())
        self._record['outcomes'][category] = 'failed'
        print('e2e:scenario-' + category + '-failed', file=sys.stderr, flush=True)

    def checkpoint(self, event):
        """Only fixed controller events and structured records enter reports."""
        require(event in {'case-started', 'step-started', 'step-ended', 'assertion',
                          'failure', 'before-cleanup', 'case-ended', 'gate-rejected'},
                'recording:event')
        self._sequence += 1
        try:
            save_checkpoint(self.collector, self._sequence, event, {
                'active_step': self._active['step_id'] if self._active else None,
                'record': self.records[-1],
            })
        except BaseException:
            self._fail('collection', 'scenario-report-failed')
            raise

    def begin_case(self, case_id):
        require(not self._closed and self._case is None
                and len(self._records) < len(self._cases), 'recording:case-state')
        case = self._cases[len(self._records)]
        require(case_id == case['case_id'], 'recording:case-order')
        self._case = case
        self._next_step = 0
        self._started = time.monotonic()
        self._record = {
            'schema_version': 1, 'run_id': self.contract.run_id,
            'scenario_id': case['scenario_id'], 'variant_id': case_id.split('/', 1)[1],
            **self.contract.inputs, 'executable': copy.deepcopy(case['executable']),
            'started_at': utc_now(), 'ended_at': None, 'steps': [], 'assertions': [],
            'artifacts': [], 'outcomes': dict.fromkeys(inventory.OUTCOMES, 'not-run'),
            'cleanup': {key: None if key == 'lease_phase' else False for key in CLEANUP_FIELDS},
        }
        self._records.append(self._record)
        self.checkpoint('case-started')

    def run_case(self, case_id, *, execute, cleanup):
        """Always checkpoint before outer cleanup; preserve the original error.

        Both callbacks are trusted controller code. cleanup must finish the
        original held lease and verify preservation, returning CLEANUP_FIELDS;
        it must not release the lease. The caller retains outer ownership and
        calls validate before release. These callbacks are never CLI inputs.
        """
        require(self._case is None and not self._closed, 'recording:case-state')
        original = None
        cleanup_state = {key: None if key == 'lease_phase' else False for key in CLEANUP_FIELDS}
        try:
            self.begin_case(case_id)
            execute(self)
        except BaseException as error:
            original = error
            if self._case is not None:
                if not self.contract.failure_state(case_id)['failures']:
                    self._fail('infrastructure', 'scenario-interrupted'
                               if isinstance(error, KeyboardInterrupt) else 'scenario-execution-failed')
        finally:
            if self._case is not None:
                try:
                    self.checkpoint('before-cleanup')
                except BaseException as error:
                    original = original if original is not None else error
                try:
                    cleanup_state = cleanup(self)
                except BaseException as error:
                    original = original if original is not None else error
                    self._fail('cleanup', 'scenario-cleanup-failed')
                try:
                    self.end_case(cleanup_state)
                except BaseException as error:
                    original = original if original is not None else error
                    self._fail('cleanup', 'scenario-finalization-failed')
                    try:
                        self.checkpoint('case-ended')
                    except BaseException:
                        pass
        if original is not None:
            raise original
        return self.records[-1]

    def failure(self, category, code):
        """Trusted worker/controller reports a fixed safe code immediately."""
        require(self._case is not None and not self._closed, 'recording:case-state')
        self._fail(category, code)
        self.checkpoint('failure')

    def run_worker(self, verified, directory, lease, ledger, *, observe, validate, timeout=600):
        """Run the qualified worker; observed stages remain scenario code's job.

        Neither module success nor worker diagnostics manufacture step/assertion
        records. Their exceptions enter the scenario ledger before worker cleanup.
        """
        require(self._case is not None, 'recording:case-state')
        require(verified.lease is lease, 'recording:foreign-lease')
        try:
            verified.recheck_contract(self.contract)
        except BaseException:
            try:
                self.failure('infrastructure', 'input-preservation-failed')
            except BaseException:
                pass  # Preserve the input refusal if its checkpoint also fails.
            raise
        import e2e_worker
        before = len(self.contract.failure_state(self._case['case_id'])['failures'])
        try:
            return e2e_worker.run_distribution(directory, lease, ledger,
                expected_inputs=verified.source_files, observe=observe, validate=validate,
                timeout=timeout, on_failure=self.failure)
        except BaseException as error:
            # Adapter and directory refusals happen before the worker owns any
            # resource and therefore before its failure hook is installed.
            if len(self.contract.failure_state(self._case['case_id'])['failures']) == before:
                try:
                    self.failure('infrastructure', 'worker-interrupted'
                                 if isinstance(error, KeyboardInterrupt) else 'worker-execution-failed')
                except BaseException:
                    pass
            raise

    def continuity(self, *, boot, sessions=()):
        require(self._active is not None, 'recording:no-active-step')
        require(isinstance(boot, str) and bool(boot), 'recording:boot-identity')
        require(isinstance(sessions, (tuple, list)) and all(
            isinstance(value, str) and value for value in sessions)
            and len(set(sessions)) == len(sessions), 'recording:session-identities')
        self._boots.setdefault(boot, f'boot-{len(self._boots) + 1}')
        for session in sessions:
            # A logind session number may be reused after a real reboot.
            key = (boot, session)
            self._sessions.setdefault(key, f'session-{len(self._sessions) + 1}')
        self._active.update(boot_id=self._boots[boot],
                            session_ids=[self._sessions[(boot, s)] for s in sessions])

    def artifact(self, artifact_id, kind, data, *, reviewed=False):
        require(self._active is not None, 'recording:no-active-step')
        require(kind in self._case['expected_evidence'], 'recording:artifact-kind')
        try:
            record = self.collector.add(artifact_id, kind, data, reviewed=reviewed)
        except BaseException:
            try:
                self.failure('collection', 'scenario-artifact-failed')
            except BaseException:
                pass
            raise
        self._record['artifacts'].append(record)
        self._active['artifact_ids'].append(artifact_id)
        return artifact_id

    def assertion(self, assertion_id, *, artifact_ids, outcome='passed'):
        require(self._active is not None, 'recording:no-active-step')
        expected = {a['id']: (kind, a['step_id'])
                    for kind, items in self._case['assertions'].items() for a in items}
        require(isinstance(assertion_id, str) and assertion_id in expected
                and expected[assertion_id][1] == self._active['step_id']
                and assertion_id not in {a['assertion_id'] for a in self._record['assertions']},
                'recording:assertion-identity')
        require(outcome in ('passed', 'failed'), 'recording:assertion-outcome')
        unique_strings(artifact_ids, 'recording:assertion-artifacts')
        kind = expected[assertion_id][0]
        needed = {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[kind]
        require(bool(artifact_ids) and set(artifact_ids) <= set(self._active['artifact_ids'])
                and any(a['artifact_id'] in artifact_ids and a['kind'] == needed
                        for a in self._record['artifacts']), 'recording:assertion-artifacts')
        self._record['assertions'].append({'assertion_id': assertion_id,
            'kind': kind, 'step_id': self._active['step_id'], 'outcome': outcome,
            'artifact_ids': list(artifact_ids)})
        self._active['assertion_ids'].append(assertion_id)
        if outcome == 'failed':
            self._fail('infrastructure' if self._case['category'] == 'runner-smoke'
                       else 'product', 'scenario-assertion-failed')
        self.checkpoint('assertion')

    @contextmanager
    def step(self, step_id):
        require(self._case is not None and self._active is None and not self._closed,
                'recording:step-state')
        declared = [(phase, step) for phase in inventory.PHASES
                    for step in self._case['phases'][phase]]
        index = self._next_step
        failures = self.contract.failure_state(self._case['case_id'])['failures']
        # Cleanup still records what actually ran after an aborted journey;
        # missing intervening actions are never filled in or marked passed.
        if failures:
            index = next((i for i, (phase, item) in enumerate(declared)
                          if i >= index and phase == 'cleanup' and item['id'] == step_id), index)
        if not (index < len(declared) and declared[index][1]['id'] == step_id):
            self.failure('infrastructure', 'scenario-step-order')
            raise EvidenceError('recording:step-order')
        phase, expected = declared[index]
        self._next_step = index + 1
        step = {'step_id': step_id, 'phase': phase, 'operation': expected['operation'],
                'outcome': 'not-run', 'monotonic_seconds': self.elapsed(),
                'boot_id': None, 'session_ids': [], 'assertion_ids': [], 'artifact_ids': []}
        self._record['steps'].append(step)
        self._active = step
        before = len(self.contract.failure_state(self._case['case_id'])['failures'])
        original = None
        try:
            self.checkpoint('step-started')
            require(phase == 'cleanup' or self.elapsed() <= self._case['duration_seconds'],
                    'recording:deadline')
            yield self
            require(phase == 'cleanup' or self.elapsed() <= self._case['duration_seconds'],
                    'recording:deadline')
            require(phase in ('setup', 'cleanup') or step['boot_id'] is not None,
                    'recording:missing-boot')
            required = {a['id'] for items in self._case['assertions'].values()
                        for a in items if a['step_id'] == step_id}
            require(set(step['assertion_ids']) == required, 'recording:missing-assertions')
            require(len(self.contract.failure_state(self._case['case_id'])['failures']) == before,
                    'recording:step-failed')
            step['outcome'] = 'passed'
        except BaseException as error:
            original = error
            step['outcome'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
            if len(self.contract.failure_state(self._case['case_id'])['failures']) == before:
                self._fail('cleanup' if phase == 'cleanup' else 'infrastructure',
                           'scenario-step-interrupted' if isinstance(error, KeyboardInterrupt)
                           else 'scenario-step-failed')
            raise
        finally:
            step['monotonic_seconds'] = self.elapsed()
            try:
                self.checkpoint('step-ended')
            except BaseException:
                if original is None:
                    raise
            finally:
                self._active = None

    def end_case(self, cleanup):
        require(self._case is not None and self._active is None, 'recording:case-state')
        fields(cleanup, CLEANUP_FIELDS, 'recording:cleanup-fields')
        require(cleanup['lease_phase'] in (None, 'complete', 'incomplete') and all(
            type(cleanup[key]) is bool for key in CLEANUP_FIELDS if key != 'lease_phase'),
                'recording:cleanup-fields')
        self._record['cleanup'] = copy.deepcopy(cleanup)
        complete = cleanup['lease_phase'] == 'complete' and all(
            cleanup[key] for key in CLEANUP_FIELDS if key != 'lease_phase')
        if not complete:
            self._fail('cleanup', 'scenario-cleanup-incomplete')
        declared_count = sum(len(self._case['phases'][phase]) for phase in inventory.PHASES)
        if len(self._record['steps']) != declared_count:
            self._fail('infrastructure', 'scenario-steps-missing')
        if {a['kind'] for a in self._record['artifacts']} != set(self._case['expected_evidence']):
            self._fail('collection', 'scenario-evidence-missing')
        for category in inventory.OUTCOMES:
            if self._record['outcomes'][category] == 'not-run':
                if category == 'product' and (
                    len(self._record['assertions']) != sum(len(items) for items in self._case['assertions'].values())
                    or any(a['outcome'] != 'passed' for a in self._record['assertions'])
                ):
                    continue
                self._record['outcomes'][category] = 'passed'
        self._record['ended_at'] = utc_now()
        self.checkpoint('case-ended')
        self._case = self._record = None

    def validate(self, verified):
        """Call after outer cleanup, while the original lease is still held."""
        require(not self._closed and self._case is None, 'recording:case-state')
        self._closed = True
        try:
            require(verified.lease.fd is not None and verified.lease.state['phase'] == 'complete',
                    'provenance:cleanup-lease-required')
            summary = verified.validate(self.contract, self.records, self.collector)
            self.collector.save_report('acceptance', {'summary': summary, 'records': self.records})
            # Include the report copy in preservation/collector validation too.
            verified.validate(self.contract, self.records, self.collector)
            return summary
        except BaseException as error:
            # Gate implementations emit fixed codes; unrelated exception text
            # must never enter durable reports or user-visible output.
            code = str(error) if isinstance(error, EvidenceError) else ''
            if not re.fullmatch(r'(?:result|artifact|provenance):[a-z-]+', code):
                code = 'recording:acceptance-failed'
            if self._records:
                record = self._records[-1]
                category = 'collection' if code.startswith('artifact:') else 'infrastructure'
                self.contract.record_failure(record['scenario_id'] + '/' + record['variant_id'],
                    category, 'input-preservation-failed' if code.startswith('provenance:')
                    else 'scenario-acceptance-failed', monotonic_seconds=self.elapsed())
                record['outcomes'][category] = 'failed'
            try:
                self.collector.save_report('acceptance-rejected', {'run_id': self.contract.run_id,
                    'outcome': 'failed', 'code': code, 'records': self.records})
            except BaseException:
                # Earlier fsynced checkpoints remain available. A broken report
                # destination never changes which execution/gate error is raised.
                print('e2e:acceptance-report-failed', file=sys.stderr, flush=True)
            raise
