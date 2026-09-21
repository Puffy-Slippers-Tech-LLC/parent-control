"""Generated coverage and numeric E2E selection share exact persistent IDs."""

import copy
import json
import re
import runpy
import subprocess
import tempfile

import pytest

from tests.support.modules import load_module
from tests.support.paths import ROOT


coverage = load_module('onpc_coverage_generation', ROOT / 'tools/generate_test_coverage.py')
inventory = runpy.run_path(str(ROOT / 'tests/e2e/inventory.py'))
runner = runpy.run_path(str(ROOT / 'tests/e2e/runner.py'))


@pytest.fixture
def document():
    return inventory['read_json'](ROOT / 'tests/e2e/scenarios.json')[0]


def test_every_document_number_selects_exactly_its_documented_case(document):
    rendered = coverage.render(document, [('Example', 3, 'Collected cases')])
    links = re.findall(r'\[(\d+)\]\(#scenario-(\d+)\)', rendered)
    assert all(label == target for label, target in links)
    numbers = [int(label) for label, _ in links]
    headings = [int(number) for number in re.findall(r'^### Scenario (\d+)$', rendered, re.M)]
    assert numbers == headings
    pending_count = sum(v['status'] == 'pending'
                        for f in document['scenarios'] for v in f['variants'])
    gray_sections = re.findall(r'<div style="color: gray">\n(.*?)\n</div>', rendered, re.S)
    assert len(gray_sections) == pending_count
    assert all('Status: **pending**' in section for section in gray_sections)
    scenario_table = rendered.split('| ID | Scenario | Variant | Status |', 1)[1]
    gray_rows = [line for line in scenario_table.splitlines() if '<span style="color: gray">' in line]
    assert len(gray_rows) == pending_count
    assert all(line.count('<span style="color: gray">') == 4
               and '>pending</span>' in line for line in gray_rows)
    rendered = re.sub(r'<span style="color: (?:gray|green)">|</span>', '', rendered)
    rendered = re.sub(r'\[(\d+)\]\(#scenario-\d+\)', r'\1', rendered)
    rows = re.findall(r'^\| (\d+) \| .*? \| `(E2E-\d+/[^`]+)` \| (ready|pending) \|$',
                      rendered, re.M)
    assert [status for _, _, status in rows] == sorted(
        (status for _, _, status in rows), key=lambda status: status == 'pending')
    assert len(rows) == sum(len(f['variants']) for f in document['scenarios'])
    assert f'| **Total** | **{3 + len(rows) - pending_count}/{pending_count}/{3 + len(rows)}** |' in rendered
    for number, case_id, status in rows:
        plan = runner['preflight'](['--list', '--id', number])
        assert plan['selector'] == case_id
        assert len(plan['cases']) == 1
        assert plan['cases'][0]['coverage_id'] == int(number)
        assert plan['cases'][0]['case_id'] == case_id
        assert plan['cases'][0]['status'] == status


def test_reordering_and_new_variants_do_not_renumber_existing_cases(document):
    original = coverage.render(document, [])
    document['scenarios'].reverse()
    for family in document['scenarios']:
        family['variants'].reverse()
    assert coverage.render(document, []) == original
    old_ids = {v['coverage_id'] for f in document['scenarios'] for v in f['variants']}
    extra = copy.deepcopy(document['scenarios'][-1])
    extra.update(id='E2E-999', title='New smoke variant')
    extra['variants'][0].update(coverage_id=max(old_ids) + 1, status='pending',
                                pending_reason='New fixture', executable=None)
    document['scenarios'].insert(0, extra)
    assert inventory['resolve_selection'](document, coverage_id=1)['selector'] == 'E2E-001/gdm-observation'
    assert inventory['resolve_selection'](document, coverage_id=max(old_ids) + 1)['selector'] == 'E2E-999/gdm-observation'


def test_shared_scenario_titles_identify_each_variant(document):
    rendered = coverage.render(document, [])
    for number, variant, description in (
            (3, 'existing-and-new', 'children: existing and new'),
            (4, 'none', 'children: none')):
        title = f'Parent discovery and navigation ({description})'
        assert (f'| [{number}](#scenario-{number}) | {title} | '
                f'`E2E-003/{variant}` | ready |') in rendered
        assert f'### Scenario {number}\n\n**{title}**' in rendered


@pytest.mark.parametrize('number', [True, 0, -1, '1', 1.5, None])
def test_inventory_refuses_invalid_numeric_ids(document, number):
    document['scenarios'][0]['variants'][0]['coverage_id'] = number
    with pytest.raises(ValueError, match='variant:coverage-id'):
        coverage.render(document, [])


def test_duplicate_numeric_id_across_families_refuses(document):
    document['scenarios'][1]['variants'][0]['coverage_id'] = 1
    with pytest.raises(ValueError, match='duplicate-coverage-id'):
        coverage.render(document, [])


@pytest.mark.parametrize('options', [
    ['--id', '0'], ['--id', '-1'], ['--id', '999999'], ['--id', 'private-value'],
    ['--id', '1', '--ready'], ['--id', '1', '--scenario', 'E2E-001'],
    ['--id', '1', '--qualify-transfer'],
])
def test_invalid_numeric_selection_refuses_before_privileges(options, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Invalid selection must not invoke a process')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(ValueError):
        coverage.test_commands.plan(ROOT, 'e2e', ['--list', *options])


def test_pending_number_refuses_execution_before_artifact_or_privilege_checks():
    with pytest.raises(ValueError, match='selection:pending'):
        coverage.test_commands.plan(ROOT, 'e2e', ['--id', '2'])


def test_retired_numeric_execution_refuses_before_existing_installed_dispatcher():
    with tempfile.TemporaryDirectory(prefix='onpc-coverage-selector-', dir='/tmp') as directory:
        with pytest.raises(ValueError, match='selection:pending'):
            coverage.test_commands.plan(
                ROOT, 'e2e', ['--id', '1', '--artifacts', directory])


@pytest.fixture
def checkout(tmp_path, document):
    document['scenarios'] = document['scenarios'][:1]
    for relative in ('tests/e2e/inventory.py', 'tests/requirements.json',
                     'docs/TestAutomation/E2E-Building-Blocks.md',
                     'tests/e2e/controller_qualification.py'):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    (tmp_path / 'tests/e2e/scenarios.json').write_text(json.dumps(document))
    (tmp_path / 'docs/Test-Coverage.md').write_text('Old handwritten content\n')
    return tmp_path


def test_generation_replaces_entire_document_and_is_deterministic(checkout, monkeypatch):
    monkeypatch.setattr(coverage, 'collect_counts',
                        lambda root: [('Unit', 7, 'Checks isolated behavior.')])
    target = checkout / 'docs/Test-Coverage.md'
    coverage.generate(checkout)
    first = target.read_bytes()
    assert first.startswith(b'> Generated by `tools/generate_test_coverage.sh`; do not manually modify.')
    assert b'Old handwritten' not in first
    assert b'| Category | Count (Ready/Pending/Total) | Description |' in first
    assert (b'| Unit | <span style="color: green">7</span>/'
            b'<span style="color: gray">0</span>/7 | Checks isolated behavior. |') in first
    summary, scenarios = first.split(b'## E2E scenarios\n', 1)
    assert b'| E2E | <span style="color: green">0</span>/<span style="color: gray">1</span>/1 |' in summary
    subcategories = scenarios.split(b'| ID | Scenario | Variant | Status |', 1)[0]
    assert b'| runner-smoke | <span style="color: green">0</span>/<span style="color: gray">1</span>/1 |' in subcategories
    assert b'| **Total** | **<span style="color: green">7</span>/<span style="color: gray">1</span>/8** |' in first
    coverage.generate(checkout)
    assert target.read_bytes() == first
    assert not list(target.parent.glob('.Test-Coverage-*'))


@pytest.mark.parametrize('failure', ['collection', 'replacement'])
def test_failed_generation_preserves_existing_report(checkout, monkeypatch, failure):
    def fail(*args):
        raise OSError('Test failure')
    monkeypatch.setattr(coverage, 'collect_counts', fail if failure == 'collection' else lambda root: [])
    if failure == 'replacement':
        monkeypatch.setattr(coverage.os, 'replace', fail)
    with pytest.raises(OSError, match='Test failure'):
        coverage.generate(checkout)
    assert (checkout / 'docs/Test-Coverage.md').read_text() == 'Old handwritten content\n'
    assert not list((checkout / 'docs').glob('.Test-Coverage-*'))


def test_failed_or_ambiguous_collection_is_not_reported_as_zero(monkeypatch):
    for output in ('no tests ran', '1 test collected\n2 tests collected\n'):
        with pytest.raises(ValueError, match='collection count'):
            coverage.single_count(output, r'^(\d+) tests? collected\b', 'unit')
    monkeypatch.setattr(coverage.subprocess, 'run', lambda *args, **kwargs:
                        subprocess.CompletedProcess(args[0], 2, 'collection failure'))
    with pytest.raises(ValueError, match='collection failure'):
        coverage.capture(ROOT, ['unused'])


def test_inventory_prose_is_literal_markdown(document):
    document['scenarios'][0]['title'] = 'Title | <tag> [link] *literal*\nsecond line'
    rendered = coverage.render(document, [])
    assert r'Title \| \<tag\> \[link\] \*literal\* second line' in rendered
