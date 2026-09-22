"""Cross-document invariants for the single, resumable E2E implementation queue.

These are host metadata checks. They neither import scenario executables nor
claim installed acceptance or provider qualification.
"""

from collections import Counter
import json
from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / 'docs/TestAutomation'
RETAINED_CASES = {1, 3, 4, 5, 6, 151, 193}


def queue_rows(text):
    rows = []
    deferred = False
    for line in text.splitlines():
        if line == '## Deferred future work':
            deferred = True
        if not re.match(r'^\| \[[ x]\] \|', line):
            continue
        fields = [value.strip() for value in line.split('|')[1:-1]]
        assert len(fields) == 6, line
        done, identity, title, requires, scope, minutes = fields
        assert re.fullmatch(r'\d{3}[a-z]*', identity), identity
        dependencies = [] if requires == 'Baseline' else requires.split(', ')
        assert all(re.fullmatch(r'\d{3}[a-z]*', item) for item in dependencies)
        case_match = re.match(r'Cases (\d+(?:, \d+)*)(?:;|$)', scope)
        regression = re.match(r'Retained regression (\d+);', scope)
        rows.append({
            'id': identity, 'done': done == '[x]', 'deferred': deferred,
            'title': title, 'requires': dependencies, 'scope': scope,
            'minutes': minutes,
            'cases': [] if case_match is None else [
                int(value) for value in case_match[1].split(', ')],
            'regression': None if regression is None else int(regression[1]),
        })
    assert rows
    return rows


def is_case(row):
    return bool(row['cases']) or row['regression'] is not None


def case_number(row):
    return row['regression'] if row['regression'] is not None else row['cases'][0]


@pytest.fixture(scope='module')
def rows():
    return queue_rows((DOCS / 'E2E-Task-Queue.md').read_text())


@pytest.fixture(scope='module')
def variants():
    inventory = json.loads((ROOT / 'tests/e2e/scenarios.json').read_text())
    return {variant['coverage_id']: (family, variant)
            for family in inventory['scenarios'] for variant in family['variants']}


def test_dependencies_are_unique_earlier_tasks_and_never_scenario_results(rows):
    by_id = {row['id']: row for row in rows}
    assert len(by_id) == len(rows), 'duplicate task ID'
    earlier = set()
    for row in rows:
        assert len(set(row['requires'])) == len(row['requires']), row['id']
        assert set(row['requires']) <= earlier, row['id']
        for dependency in row['requires']:
            assert not is_case(by_id[dependency]), (row['id'], dependency)
            assert row['deferred'] or not by_id[dependency]['deferred'], row['id']
        earlier.add(row['id'])


def test_next_pointer_is_exactly_the_first_unfinished_active_brief(rows):
    pending = [row for row in rows if not row['done'] and not row['deferred']]
    plan = (DOCS / 'E2E-Execution-Plan.md').read_text()
    pointers = re.findall(
        r'^Next task: \*\*(\d{3}[a-z]*) — \[[^\]]+\]\(([^)]+)\)\*\*\.',
        plan, re.M)
    if not pending:
        assert not pointers
        return
    assert len(pointers) == 1
    identity, path = pointers[0]
    assert identity == pending[0]['id']
    assert f']({path})' in pending[0]['title']


def test_every_unfinished_task_has_one_matching_brief_and_prerequisites(rows):
    linked = set()
    for row in rows:
        links = re.findall(r'\]\((E2E-Tasks/[^)]+\.md)\)', row['title'])
        if row['done']:
            assert not links, row['id']
            continue
        assert len(links) == 1, row['id']
        path = DOCS / links[0]
        assert path not in linked, row['id']
        linked.add(path)
        brief = path.read_text()
        assert brief.startswith(f"# {row['id']} — "), row['id']
        heading = ('Required tasks (queue IDs; use delivered scope, '
                   'not predecessor briefs):')
        if row['requires']:
            assert brief.count(heading) == 1, row['id']
            section = brief.split(heading, 1)[1].split('\n## ', 1)[0]
            dependencies = re.findall(r'^- \*\*(\d{3}[a-z]*)\*\* — ', section, re.M)
            assert dependencies == row['requires'], row['id']
        else:
            assert 'Required tasks: none (Baseline).' in brief, row['id']
        if is_case(row):
            selectors = re.findall(r"tools/run-tests e2e --id '(\d+)'", brief)
            assert selectors == [str(case_number(row))], row['id']
            assert 'generate_test_coverage' in brief, row['id']
    assert linked == set((DOCS / 'E2E-Tasks').glob('*.md')), 'orphan/missing brief'


def test_case_assignments_preserve_inventory_and_one_case_per_task(rows, variants):
    assignments = Counter(case for row in rows for case in row['cases'])
    assert all(count == 1 for count in assignments.values()), assignments
    assert all(len(row['cases']) <= 1 for row in rows), 'split paired case tasks'
    regressions = [row['regression'] for row in rows if row['regression'] is not None]
    assert Counter(regressions) == Counter(RETAINED_CASES)
    assert set(assignments) | set(regressions) == set(variants)
    assert set(variants).isdisjoint(range(140, 151))
    for number, (_, variant) in variants.items():
        if variant['status'] == 'pending':
            assert assignments[number] == 1, number
        if number in RETAINED_CASES:
            assert variant['status'] == 'ready' and variant['executable'], number
    for row in rows:
        for number in row['cases']:
            family, variant = variants[number]
            assert family['id'] in row['title'], row['id']
            assert variant['id'] in row['title'], row['id']
    obligations = [int(match[1]) for row in rows
                   if (match := re.fullmatch(r'System obligation (\d+)', row['scope']))]
    assert Counter(obligations) == Counter(range(140, 151))


def test_each_capability_is_followed_by_all_newly_enabled_cases_in_numeric_order(rows):
    active = [row for row in rows if not row['deferred']]
    available = {row['id'] for row in active if row['done']}
    pending = [row for row in active if not row['done']]
    for index, row in enumerate(pending):
        enabled = [candidate for candidate in pending[index:]
                   if is_case(candidate) and set(candidate['requires']) <= available]
        if enabled:
            assert row == min(enabled, key=case_number), row['id']
        available.add(row['id'])


def test_delivered_block_names_resolve_to_unique_catalogue_contracts(rows):
    catalogue = (DOCS / 'E2E-Building-Blocks.md').read_text()
    ids = re.findall(r'^\| ([A-Z]+\d{2}) \| [AC] \|', catalogue, re.M)
    assert len(ids) == len(set(ids)), 'duplicate block contract'
    for row in rows:
        declared = set(re.findall(r'\b[A-Z]+\d{2}\b', row['scope']))
        assert declared <= set(ids), row['id']
