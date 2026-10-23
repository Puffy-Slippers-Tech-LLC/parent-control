"""Standalone Smoke native readiness at its owned post-SSH boundary."""
import e2e_fixture_preparation as shared
from system_fixture_preparation import guest_target


def validate_input(value, target=None):
    record = shared.selection_record(value, product_free=True)
    if record['target'] != 'ubuntu' or target not in (None, 'ubuntu'):
        raise ValueError('fixtures:transfer-target-not-qualified')
    return shared.validate_input(record, target=target, product_free=True)


def prepare(vm, lease, directory, selection):
    record = validate_input(selection, target=guest_target(lease.capture.state['guest']))
    if guest_target(lease.capture.state['guest']) != 'ubuntu':
        raise ValueError('fixtures:transfer-target-not-qualified')
    return {**shared.prepare(vm, lease, directory, record, product_free=True),
            'selection': record}
