"""Worker progress messages are allowlisted and cannot export secrets."""

import json
import re

import inventory
from tools.e2e_progress import Progress, operation_labels
from tests.support.paths import ROOT
from tests.support.perl import LIB


def cases():
    document, _ = inventory.read_json(ROOT / 'tests/e2e/scenarios.json')
    return inventory.resolve_selection(document, None, root=ROOT)['cases']


def test_worker_messages_are_bounded_allowlisted_and_cleared_at_step_boundary(tmp_path):
    progress = Progress(cases()[:1])
    progress.case(progress.cases[0]['case_id'])
    label = 'Selecting [Existing child] from the child selector'
    progress.follow_worker(tmp_path, operation_labels(LIB))
    path = tmp_path / 'watch-operation.json'
    path.write_text(json.dumps(dict(sequence=1, operation=label)))
    assert progress.snapshot()['operation'] == label
    progress.step('Next step')
    assert progress.snapshot()['operation'] == ''
    progress.operation('Checking the selected child')
    assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.write_text(json.dumps(dict(sequence=2, operation=label)))
    assert progress.snapshot()['operation'] == label
    for invalid in (dict(sequence=3, operation='private-secret-canary'),
                    dict(sequence=True, operation=label), ['not-a-message'],
                    dict(sequence=3, operation=label, secret='private-secret-canary')):
        path.write_text(json.dumps(invalid))
        assert 'private-secret-canary' not in json.dumps(progress.snapshot())
        assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.write_text('x' * 4096)
    assert progress.snapshot()['operation'] == 'Checking the selected child'
    path.unlink()
    path.symlink_to(tmp_path / 'missing')
    assert progress.snapshot()['operation'] == 'Checking the selected child'


def test_new_worker_blocks_require_literal_nonsecret_operation_messages():
    # Bookkeeping helpers either do no customer operation or dispatch to blocks
    # which log it. New action blocks must opt into the shared progress contract.
    bookkeeping = {'onpc_journey::new', 'onpc_journey::seen',
                   'onpc_journey::consume_observation', 'onpc_journey::service_system_prompt',
                   'onpc_password::seal_capture'}
    for path in LIB.glob('*.pm'):
        if path.stem == 'onpc_progress':
            continue
        source = path.read_text()
        assert 'use onpc_progress ();' in source
        blocks = re.split(r'^sub (\w+) \{\n', source, flags=re.MULTILINE)
        for name, body in zip(blocks[1::2], blocks[2::2]):
            if name.startswith('_') or f'{path.stem}::{name}' in bookkeeping:
                continue
            assert re.match(r"    onpc_progress::operation\('[^'\n]+'\);", body), (path, name)
        assert not re.search(r'onpc_progress::operation\((?!\')', source)
