"""Generate docs/Test-Coverage.md from test collection and the E2E inventory."""

import argparse
from collections import Counter
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import test_commands
import test_launcher


def capture(root, command):
    result = subprocess.run(command, cwd=root, env=test_launcher.environment(root),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, check=False)
    if result.returncode:
        raise ValueError(f'Collection failed ({result.returncode}): {command}\n{result.stdout}')
    return result.stdout


def single_count(output, pattern, category):
    matches = re.findall(pattern, output, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f'{category}: missing or ambiguous collection count')
    return int(matches[0])


def collect_counts(root):
    """Collect real parametrized pytest IDs; never run fixtures or use a VM."""
    rows = []
    for category, title, options, description in (
            ('unit', 'Unit, property and contract', [],
             'Checks isolated logic, invariants, interfaces and test-harness behavior.'),
            ('component', 'Private D-Bus component', [],
             'Checks broker behavior through a private D-Bus without changing the host system.'),
            ('ui', 'UI', ['--timeout', '1800s'],
             'Checks GTK and GNOME Shell interaction, accessibility and presentation in isolated sessions.'),
            ('fixture-runtime', 'Fixture runtime', [],
             'Checks that test fixtures prepare, validate and clean up their controlled environments.')):
        print(f'Collecting {category}...', file=sys.stderr, flush=True)
        output = capture(root, [str(root / 'tools/run-tests'), category, *options,
                                '--collect-only', '-q'])
        # Pytest reports selected/total when the launcher deselects live UI
        # cases. Count the selected suite, preserving its existing exclusions.
        count = single_count(output, r'^(\d+)(?:/\d+)? tests? collected\b', category)
        rows.append((title, count, description))

    print('Collecting installed system...', file=sys.stderr, flush=True)
    output = capture(root, [str(root / 'tools/run-tests'), 'system', '--list'])
    marker = '  available-selectors:\n'
    if output.count(marker) != 1:
        raise ValueError('system: missing or ambiguous selector inventory')
    cases = re.findall(r'^      (\S.*)$', output.split(marker)[1], re.MULTILINE)
    if not cases:
        raise ValueError('system: empty selector inventory')
    rows.append(('Installed system', len(cases),
                 'Checks installed product behavior and lifecycle integration on the test VM.'))

    commands, _ = test_commands.plan(root, 'child-node', [])
    # Node has no collect-only mode. Count the launcher's executable files,
    # explicitly, rather than execute their bodies or guess dynamic subtests.
    rows.append(('Child Node', len(commands[0][3:]),
                 'Checks child extension JavaScript logic in Node.js.'))

    commands, _ = test_commands.plan(root, 'child-gjs', [])
    rows.append(('Child GJS', len(commands),
                 'Checks child extension behavior that depends on the GNOME JavaScript runtime.'))
    integrations = sorted((root / 'tests/integration').glob('check_*.py'))
    rows.append(('Integration qualification', len(integrations),
                 'Checks installed-runner prerequisites, safety guards and integration building blocks.'))
    return rows


def prose(value):
    """Keep inventory prose on one Markdown line and escape literal markup."""
    value = ' '.join(value.split())
    return re.sub(r'([\\`*_{}\[\]<>|])', r'\\\1', value)


def scenario_title(family, variant):
    title = prose(family['title'])
    if len(family['variants']) > 1:
        parameters = '; '.join(f'{prose(key.replace("-", " "))}: '
                               f'{prose(value.replace("-", " "))}'
                               for key, value in sorted(variant['parameters'].items()))
        title += f' ({parameters})'
    return title


def count_cell(ready, pending):
    return (f'<span style="color: green">{ready}</span>/'
            f'<span style="color: gray">{pending}</span>/{ready + pending}')


def render(document, counts, *, root=ROOT):
    api = runpy.run_path(str(root / 'tests/e2e/inventory.py'))
    api['validate_inventory'](document, root=root)
    cases = sorted(((variant['coverage_id'], family, variant)
                    for family in document['scenarios'] for variant in family['variants']),
                   key=lambda item: (item[2]['status'] == 'pending', item[0]))
    totals = Counter((family['category'], variant['status']) for _, family, variant in cases)
    rows = [(title, count, 0, description) for title, count, description in counts]
    categories = sorted({family['category'] for _, family, _ in cases})
    rows.append(('E2E', sum(totals[category, 'ready'] for category in categories),
                 sum(totals[category, 'pending'] for category in categories),
                 'Checks complete customer journeys through the installed product\'s public interfaces.'))
    ready_total = sum(ready for _, ready, _, _ in rows)
    pending_total = sum(pending for _, _, pending, _ in rows)
    lines = [
        '> Generated by `tools/generate_test_coverage.sh`; do not manually modify.',
        '', '# Test coverage', '', '## Test case counts', '',
        '| Category | Count (Ready/Pending/Total) | Description |', '| --- | ---: | --- |',
        *[f'| {title} | {count_cell(ready, pending)} | {description} |'
          for title, ready, pending, description in rows],
        f'| **Total** | **{count_cell(ready_total, pending_total)}** | All test cases across the categories above, including pending E2E scenarios. |',
        '',
        'These are inventory counts, not passing results or code-coverage percentages. '
        'Python parameter combinations count separately; property-test examples do not. '
        'Script-based checks count once per executable entry point; Node subtests are not expanded. '
        'Installed-system cases count repeated phases and prerequisites once. '
        'Aggregate, build, static-analysis and prerequisite commands are not additional test cases.',
        '', '## E2E scenarios', '',
        '| Subcategory | Count (Ready/Pending/Total) |',
        '| --- | ---: |',
        *[f'| {category} | {count_cell(totals[category, "ready"], totals[category, "pending"])} |'
          for category in categories],
        '',
        'Each number selects exactly one variant. IDs are stored in '
        '`tests/e2e/scenarios.json` and stay unchanged when entries are reordered or become ready. '
        'Assign new variants fresh IDs; never renumber or reuse an existing ID.',
        '',
        'Inspect: `tools/run-tests e2e --list --id 1`. '
        'Run: `tools/run-tests e2e --id 1 --artifacts /tmp/onpc-test-artifacts-REPLACE` '
        '(use an existing verified package-artifact directory). '
        'Pending cases refuse execution. Ready means runnable, not passed.',
        '',
        'Titles and steps below come directly from the runtime inventory. '
        'Customer scope follows '
        '[E2E building blocks](TestAutomation/E2E-Building-Blocks.md). Runner smoke '
        'does not establish customer coverage; retired internal fault obligations '
        'remain in their separate system-test owners, outside this UI inventory.',
        '', '| ID | Scenario | Variant | Status |', '| ---: | --- | --- | --- |',
    ]
    for number, family, variant in cases:
        link = f'[{number}](#scenario-{number})'
        cells = [link, scenario_title(family, variant), f'`{family["id"]}/{variant["id"]}`', variant['status']]
        if variant['status'] == 'pending':
            cells = [f'<span style="color: gray">{cell}</span>' for cell in cells]
        lines.append('| ' + ' | '.join(cells) + ' |')
    for number, family, variant in cases:
        if variant['status'] == 'pending':
            lines.extend(['', '<div style="color: gray">'])
        lines.extend(['', f'### Scenario {number}', '',
                      f'**{scenario_title(family, variant)}**', '',
                      f'Case: `{family["id"]}/{variant["id"]}` · '
                      f'Category: {family["category"]} · Status: **{variant["status"]}**', '',
                      'Variant: ' + '; '.join(f'{prose(key.replace("-", " "))}: '
                                             f'{prose(value.replace("-", " "))}'
                                             for key, value in sorted(variant['parameters'].items())),
                      '', '**Steps:**', '',
                      *['- ' + prose(step['description']) for step in family['phases']['steps']]])
        if variant['pending_reason']:
            lines.extend(['', 'Pending: ' + prose(variant['pending_reason'])])
        if variant['status'] == 'pending':
            lines.extend(['', '</div>'])
    return '\n'.join(lines) + '\n'


def generate(root=ROOT):
    api = runpy.run_path(str(root / 'tests/e2e/inventory.py'))
    document, _ = api['read_json'](root / 'tests/e2e/scenarios.json')
    api['validate_inventory'](document, root=root)
    content = render(document, collect_counts(root), root=root)
    target = root / 'docs/Test-Coverage.md'
    # Leave the previous report intact on any collection or write failure.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=target.parent,
                                         prefix='.Test-Coverage-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('Generated docs/Test-Coverage.md')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        generate()
    except (ValueError, OSError) as error:
        print(f'test-coverage: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
