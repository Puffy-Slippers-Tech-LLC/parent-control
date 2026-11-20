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
    environment = test_launcher.environment(root)
    # Inventory belongs to the checkout being documented, even when the public
    # run-tests launcher has a different configured default branch.
    environment['ONPC_LAUNCHER_CONTROLLER_ROOT'] = str(root)
    result = subprocess.run(command, cwd=root, env=environment,
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


def collect_host_counts(root):
    """Collect host test inventory without running fixtures or tests."""
    rows = []
    for category, title, options, description in (
            ('unit', 'Unit, property and contract', [],
             'Checks isolated logic, invariants, interfaces and test-harness behavior.'),
            ('component', 'Private D-Bus component', [],
             'Checks broker behavior through a private D-Bus without changing the host system.'),
            ('ui', 'UI', ['--timeout', '1800s'],
             'Checks GTK and GNOME Shell functional results and accessibility in isolated sessions.'),
            ('fixture-runtime', 'Fixture runtime', [],
             'Checks that test fixtures prepare, validate and clean up their controlled environments.')):
        print(f'Collecting {category}...', file=sys.stderr, flush=True)
        output = capture(root, [str(root / 'tools/run-tests'), category, *options,
                                '--collect-only', '-q'])
        # Pytest reports selected/total when the launcher deselects live UI
        # cases. Count the selected suite, preserving its existing exclusions.
        count = single_count(output, r'^(\d+)(?:/\d+)? tests? collected\b', category)
        rows.append((title, count, description))

    commands, _ = test_commands.plan(root, 'child-node', [])
    # Node has no collect-only mode. Count the launcher's executable files,
    # explicitly, rather than execute their bodies or guess dynamic subtests.
    rows.append(('Child Node', len(commands[0][3:]),
                 'Checks child extension JavaScript logic in Node.js.'))

    commands, _ = test_commands.plan(root, 'child-gjs', [])
    rows.append(('Child GJS', len(commands),
                 'Checks child extension behavior that depends on the GNOME JavaScript runtime.'))
    inventory = runpy.run_path(str(root / 'tests/integration/system_checks.py'))
    for category in inventory['HOST_CHECKS']:
        description = {
            'graphical-worker': 'Checks privileged graphical worker containment with isolated host fixtures.',
            'package-notice': 'Checks native package-manager notices in isolated host fixtures.',
        }[category]
        rows.append((category, 1, description))
    return rows


def collect_vm_execution_counts(root):
    """Project the full VM selection through the same inventory as Watch."""
    from vm_test_queue import collect_families, execution_groups, selected_cases, vm_config
    from vm_selection import VARIABLE

    document = vm_config.read_document(validate_agent=False)
    _, configured = vm_config.parse_configuration(document)
    branch = vm_config.current_branch()
    original_vm = os.environ.get(VARIABLE)
    rows = []
    try:
        for family in document['families']:
            selector = family.get('id', family['family'])
            hosts = vm_config.default_vmhost(document, selector=selector)
            vms = [vm for vm in configured.values()
                   if vm.family == family['family'] and vm.enabled and vm.host.enabled
                   and (not vm.owning_branch or vm.owning_branch == branch)
                   and (not hosts or vm.host.name in hosts.split(','))]
            if not vms:
                continue
            print(f'Collecting VM executions for {selector}...', file=sys.stderr, flush=True)
            vm_config.select(vms[0].name)
            counts = Counter()
            for group in execution_groups(root, ['vm'], vms):
                args = group['args']
                families = collect_families(root, [configured[name] for name in group['vms']],
                                            test_commands.selections(root, args))
                counts[group['category']] += len(selected_cases(families, args))
            rows.append((selector, counts['system'], counts['e2e']))
    finally:
        if original_vm is None:
            os.environ.pop(VARIABLE, None)
        else:
            os.environ[VARIABLE] = original_vm
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


def inventory_table(host_counts, vm_counts):
    def row(*cells):
        return '| ' + ' | '.join(map(str, cells)) + ' |'

    return [
        row('Category', 'Host inventory', *(f'`{selector}`' for selector, _, _ in vm_counts),
            'Description'),
        row('---', *(['---:'] * (1 + len(vm_counts))), '---'),
        *[row(title, count, *(['—'] * len(vm_counts)), description)
          for title, count, description in host_counts],
        row('Installed system', '—', *(system for _, system, _ in vm_counts),
            'Checks installed behavior, lifecycle integration and engineering safety boundaries.'),
        row('E2E', '—', *(e2e for _, _, e2e in vm_counts),
            'Checks complete customer journeys through the installed product’s public interfaces.'),
        row('**Total**', f'**{sum(count for _, count, _ in host_counts)}**',
            *(f'**{system + e2e}**' for _, system, e2e in vm_counts), ''),
    ]


def render(document, host_counts, vm_counts, *, root=ROOT):
    api = runpy.run_path(str(root / 'tests/e2e/inventory.py'))
    api['validate_inventory'](document, root=root)
    cases = sorted(((variant['coverage_id'], family, variant)
                    for family in document['scenarios'] for variant in family['variants']),
                   key=lambda item: (item[2]['status'] == 'pending', item[0]))
    totals = Counter((family['category'], variant['status']) for _, family, variant in cases)
    categories = sorted({family['category'] for _, family, _ in cases})
    ready_total = sum(totals[category, 'ready'] for category in categories)
    pending_total = sum(totals[category, 'pending'] for category in categories)
    lines = [
        '> Generated by `tools/generate_test_coverage.sh`; do not manually modify.',
        '', '# Test coverage', '', '## Test inventory counts', '',
        'Each VM family column uses the [ONPC: Watch accounting](../tests/README.md#aggregate-execution-and-reconnection) '
        'for `tools/fix-tests vm --vm FAMILY` with this checkout and its configured default hosts.',
        '',
        *inventory_table(host_counts, vm_counts),
        '',
        'VM totals include selected installed-system phases, registered standalone checks and runnable '
        'E2E variants. Platform filters and additional GNOME Classic executions can change the total by family.',
        '',
        'The host inventory counts parametrized Python cases and executable script entries. '
        'Property-test examples and Node subtests are included in their parent cases or files. '
        'The inventory excludes aggregate, build, static-analysis and prerequisite commands.',
        '', '## E2E scenarios', '',
        '| Subcategory | Count (Ready/Pending/Total) |',
        '| --- | ---: |',
        *[f'| {category} | {count_cell(totals[category, "ready"], totals[category, "pending"])} |'
          for category in categories],
        f'| **Total** | **{count_cell(ready_total, pending_total)}** |',
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
    content = render(document, collect_host_counts(root), collect_vm_execution_counts(root), root=root)
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
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'test-coverage: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
