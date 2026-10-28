"""Private decoder/recorder doubles; no live product or resource ownership."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import overlay_reminders as reminders
from private_artifacts import EvidenceError
from ui_observations import UiObservations


def reminder_value(records=None):
    records = deepcopy(reminders.DEFAULTS if records is None else records)
    return {'records': records, 'show_in_fullscreen': True, 'fullscreen_enabled': bool(records),
            'language': 'en', 'source': 'a' * 64}


@pytest.mark.parametrize('operation', [
    'overlay-reminder-create', 'overlay-reminder-edit', 'overlay-reminder-delete',
    'overlay-reminder-delete-all', 'overlay-reminder-save', 'overlay-reminder-cancel',
    'overlay-reminder-fullscreen-false', 'overlay-reminder-fullscreen-true',
    *sorted(accessible_ui.BINDING_REMINDER_MUTATIONS)])
def test_mutation_requires_prior_draft_and_carries_exact_source(operation):
    transport = SimpleNamespace(call=Mock(), commands=SimpleNamespace(progress=None))
    observer = UiObservations(transport)
    with pytest.raises(EvidenceError, match='reminder-source-required'):
        observer.observe(operation)
    transport.call.assert_not_called()
    observer = UiObservations(transport)
    attribute = ('binding_reminder_source' if operation.startswith('binding-') else
                 'overlay_reminder_source')
    setattr(observer, attribute, 'b' * 64)
    observer.boot_guard = 'c' * 64
    value = reminder_value()
    payload = {'operation': operation, 'outcome': 'passed',
               'interface': 'ApplicationUI+external-provider'}
    if not operation.endswith(('-save', '-cancel')):
        payload['reminders'] = value
    payload['boot_sha256'] = observer.boot_guard
    raw = json.dumps(payload).encode()

    def deliver(argv, **kwargs):
        assert argv[-2:] == ['c' * 64, 'b' * 64]
        kwargs['on_output'](raw + b'\n')
        return raw

    transport.call.side_effect = deliver
    result = observer.observe(operation)
    assert 'boot_sha256' not in result
    assert getattr(observer, attribute) == (None if operation.endswith(('-save', '-cancel')) else 'a' * 64)
