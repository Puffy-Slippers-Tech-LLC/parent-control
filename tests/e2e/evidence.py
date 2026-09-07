"""Version 1 runtime reconciliation against frozen E2E selection and inputs.

No VM/worker imports. The guarded controller must obtain provenance from its
verified inputs, not from a result supplied by the guest or worker.
"""

import copy
from datetime import datetime
import json
import math
import re

import inventory
from private_artifacts import EvidenceError, require, token


INPUT_FIELDS = ('source_sha256', 'inventory_sha256', 'package_sha256', 'assets_sha256',
                'environment_id', 'baseline_sha256')
RESULT_FIELDS = (*inventory.RUN_FIELDS, 'schema_version', 'executable', 'assertions', 'failures')
STATES = {'passed', 'failed', 'skipped', 'interrupted', 'xfail', 'flaky', 'not-run'}
CLEANUP_FIELDS = ('lease_phase', 'owned_processes_stopped', 'vm_off', 'baseline_restored',
                  'host_preserved', 'source_preserved')


def fields(value, names, code):
    require(isinstance(value, dict) and set(value) == set(names), code)


def seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def state(value):
    return isinstance(value, str) and value in STATES


def unique_strings(value, code):
    require(isinstance(value, list) and all(isinstance(v, str) for v in value)
            and len(set(value)) == len(value), code)


def timestamp(value):
    require(isinstance(value, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value), 'result:timestamp')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise EvidenceError('result:timestamp') from None


class FailureLedger:
    """Append-only failure order; later success never clears earlier failure."""

    def __init__(self):
        self._events = []

    def record(self, category, code, *, step_id=None, monotonic_seconds):
        require(isinstance(category, str) and category in inventory.OUTCOMES and token(code)
                and (step_id is None or token(step_id)) and seconds(monotonic_seconds),
                'failure:fields')
        require(not self._events or monotonic_seconds >= self._events[-1]['monotonic_seconds'],
                'failure:order')
        event = {'sequence': len(self._events) + 1, 'category': category, 'code': code,
                 'step_id': step_id, 'monotonic_seconds': monotonic_seconds}
        self._events.append(event)

    def snapshot(self):
        return copy.deepcopy(self._events)

    @property
    def first_failure(self):
        return copy.deepcopy(self._events[0]) if self._events else None


class EvidenceContract:
    """Freeze a runnable plan before execution; pending inventory cannot pass.

    Synthetic tests use a separate temporary inventory with a dummy executable;
    there is deliberately no allow-pending or ignore-failures acceptance flag.
    """

    def __init__(self, *, inventory_path=inventory.INVENTORY, selector=None,
                 inputs, run_id, root=inventory.ROOT):
        require(token(run_id), 'result:run-id')
        document, digest = inventory.read_json(inventory_path)
        plan = inventory.resolve_selection(document, selector, require_runnable=True, root=root)
        fields(inputs, INPUT_FIELDS, 'result:input-fields')
        for key in INPUT_FIELDS:
            if key == 'environment_id':
                require(token(inputs[key]), 'result:environment')
            elif key == 'package_sha256' and inputs[key] is None:
                require(all(c['category'] == 'runner-smoke' for c in plan['cases']),
                        'result:package-required')
            else:
                require(isinstance(inputs[key], str) and re.fullmatch(r'[0-9a-f]{64}', inputs[key]),
                        'result:input-digest')
        require(inputs['inventory_sha256'] == digest, 'result:inventory-digest')
        self._plan = copy.deepcopy(plan)
        self._inputs = copy.deepcopy(inputs)
        self._failures_by_case = {case['case_id']: FailureLedger() for case in plan['cases']}
        self.run_id = run_id

    def record_failure(self, case_id, category, code, *, step_id=None, monotonic_seconds):
        """Controller records failures as observed, before cleanup or diagnostics."""
        require(isinstance(case_id, str) and case_id in self._failures_by_case, 'failure:case')
        self._failures_by_case[case_id].record(category, code, step_id=step_id,
                                              monotonic_seconds=monotonic_seconds)

    def failure_state(self, case_id):
        require(isinstance(case_id, str) and case_id in self._failures_by_case, 'failure:case')
        ledger = self._failures_by_case[case_id]
        return {'failures': ledger.snapshot(), 'first_failure': ledger.first_failure}

    @property
    def plan(self):
        """Controller schedule; callers cannot mutate the frozen acceptance plan."""
        return copy.deepcopy(self._plan)

    @property
    def inputs(self):
        return copy.deepcopy(self._inputs)

    def validate(self, records, collector):
        """Return a passing summary only after exact reconciliation and rehashing.

        Retain failed/interrupted records via collector.save_report regardless
        of this gate's refusal. The fixed error code is safe for public logs.
        """
        try:
            return self._validate(records, collector)
        except (KeyError, TypeError, OverflowError, UnicodeError):
            raise EvidenceError('result:invalid-shape') from None

    def _validate(self, records, collector):
        require(collector.run_id == self.run_id, 'result:collector-run')
        require(isinstance(records, list) and len(records) == len(self._plan['cases']),
                'result:case-count')
        all_artifacts = []
        for result, case in zip(records, self._plan['cases']):
            fields(result, RESULT_FIELDS, 'result:fields')
            require(type(result['schema_version']) is int and result['schema_version'] == 1,
                    'result:schema-version')
            require(result['run_id'] == self.run_id and result['scenario_id'] == case['scenario_id']
                    and result['variant_id'] == case['case_id'].split('/', 1)[1], 'result:identity')
            require(result['executable'] == case['executable'], 'result:executable')
            require(all(result[key] == value for key, value in self._inputs.items()),
                    'result:stale-inputs')
            elapsed = (timestamp(result['ended_at']) - timestamp(result['started_at'])).total_seconds()
            require(0 <= elapsed <= case['duration_seconds'], 'result:duration')
            artifacts = result['artifacts']
            require(isinstance(artifacts, list) and all(isinstance(a, dict) for a in artifacts),
                    'result:artifacts')
            artifact_ids = [a['artifact_id'] for a in artifacts]
            unique_strings(artifact_ids, 'result:artifact-ids')
            require({a['kind'] for a in artifacts} == set(case['expected_evidence']),
                    'result:evidence-kinds')
            all_artifacts.extend(artifacts)
            declared = [(phase, step) for phase in inventory.PHASES for step in case['phases'][phase]]
            require(isinstance(result['steps'], list) and len(result['steps']) == len(declared),
                    'result:step-count')
            assertions = {a['id']: (kind, a['step_id']) for kind, items in case['assertions'].items()
                          for a in items}
            self._assertions(result['assertions'], assertions, set(artifact_ids), artifacts)
            linked, previous = set(), 0
            for step, (phase, expected) in zip(result['steps'], declared):
                fields(step, inventory.STEP_FIELDS, 'result:step-fields')
                require(step['step_id'] == expected['id'] and step['phase'] == phase
                        and step['operation'] == expected['operation'], 'result:step-identity')
                require(state(step['outcome']), 'result:step-outcome')
                require(step['outcome'] == 'passed', 'result:step-not-passed')
                measured = step['monotonic_seconds']
                require(seconds(measured) and previous <= measured <= min(
                    case['duration_seconds'], elapsed + 1),
                        'result:step-time')
                previous = measured
                # Identity values are run-local aliases, never real account/session names.
                require(step['boot_id'] is None or re.fullmatch(r'boot-[1-9][0-9]*', step['boot_id']),
                        'result:boot-alias')
                require(phase in ('setup', 'cleanup') or step['boot_id'] is not None,
                        'result:missing-boot')
                unique_strings(step['session_ids'], 'result:session-ids')
                require(all(re.fullmatch(r'session-[1-9][0-9]*', s) for s in step['session_ids']),
                        'result:session-alias')
                unique_strings(step['assertion_ids'], 'result:assertion-ids')
                require(set(step['assertion_ids']) == {a for a, (_, sid) in assertions.items()
                                                       if sid == expected['id']},
                        'result:step-assertions')
                unique_strings(step['artifact_ids'], 'result:step-artifacts')
                require(set(step['artifact_ids']) <= set(artifact_ids), 'result:unknown-artifact')
                linked.update(step['artifact_ids'])
                for assertion in result['assertions']:
                    if assertion['step_id'] == step['step_id']:
                        require(set(assertion['artifact_ids']) <= set(step['artifact_ids']),
                                'result:assertion-step-artifacts')
            require(linked == set(artifact_ids), 'result:unlinked-artifact')
            self._failures(result, {s['id'] for _, s in declared}, case['duration_seconds'],
                           self.failure_state(case['case_id']))
            fields(result['cleanup'], CLEANUP_FIELDS, 'result:cleanup-fields')
            require(result['cleanup']['lease_phase'] == 'complete' and all(
                result['cleanup'][key] is True for key in CLEANUP_FIELDS if key != 'lease_phase'),
                'result:cleanup-incomplete')
            # Scan decoded strings as well as JSON escaping before any result is accepted.
            collector.check_secrets(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        collector.verify(all_artifacts)
        return {'schema_version': 1, 'run_id': self.run_id, 'outcome': 'passed',
                'scope': self._plan['scope'], 'case_ids': [c['case_id'] for c in self._plan['cases']],
                'inputs': copy.deepcopy(self._inputs)}

    @staticmethod
    def _assertions(actual, expected, artifact_ids, artifacts):
        require(isinstance(actual, list) and len(actual) == len(expected), 'result:assertion-count')
        seen = set()
        kinds = {a['artifact_id']: a['kind'] for a in artifacts}
        for item in actual:
            fields(item, ('assertion_id', 'step_id', 'kind', 'outcome', 'artifact_ids'),
                   'result:assertion-fields')
            aid = item['assertion_id']
            require(isinstance(aid, str) and aid not in seen and aid in expected,
                    'result:assertion-identity')
            seen.add(aid)
            require((item['kind'], item['step_id']) == expected[aid], 'result:assertion-identity')
            require(item['outcome'] == 'passed', 'result:assertion-not-passed')
            unique_strings(item['artifact_ids'], 'result:assertion-artifacts')
            require(bool(item['artifact_ids']) and set(item['artifact_ids']) <= artifact_ids,
                    'result:assertion-artifacts')
            needed = {'visible': 'screen', 'backend': 'backend', 'other_user': 'other-user'}[item['kind']]
            require(needed in {kinds[a] for a in item['artifact_ids']}, 'result:assertion-evidence-kind')

    @staticmethod
    def _failures(result, step_ids, duration, recorded):
        fields(result['outcomes'], inventory.OUTCOMES, 'result:outcomes')
        require(all(state(v) for v in result['outcomes'].values()), 'result:outcome-state')
        require(isinstance(result['failures'], list), 'result:failures')
        ledger = FailureLedger()
        for event in result['failures']:
            fields(event, ('sequence', 'category', 'code', 'step_id', 'monotonic_seconds'),
                   'result:failure-fields')
            require(type(event['sequence']) is int and event['sequence'] == len(ledger.snapshot()) + 1,
                    'result:failure-sequence')
            require(event['step_id'] is None or event['step_id'] in step_ids, 'result:failure-step')
            ledger.record(event['category'], event['code'], step_id=event['step_id'],
                          monotonic_seconds=event['monotonic_seconds'])
            require(event['monotonic_seconds'] <= duration, 'result:failure-time')
        require(result['first_failure'] == ledger.first_failure, 'result:first-failure')
        require(result['failures'] == recorded['failures']
                and result['first_failure'] == recorded['first_failure'], 'result:failure-history')
        require(not ledger.snapshot() and all(v == 'passed' for v in result['outcomes'].values()),
                'result:attempt-not-passed')
