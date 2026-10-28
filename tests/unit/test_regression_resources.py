"""Critical scheduler resource and exclusivity guarantees."""

from types import SimpleNamespace

from regression_resources import Admission, GIB, Sample, compatible


def healthy():
    return Sample(20, 2, 32 * GIB, 24 * GIB, 0, 0, 0, False)


def gate():
    state = SimpleNamespace(now=0, sample=healthy())
    admission = Admission(SimpleNamespace(sample=lambda: state.sample), lambda: state.now)
    return state, admission


def warm(state, admission, active=('ui',)):
    for kind in active:
        admission.started(kind)
    admission.update()
    state.now += 20
    admission.update()


def test_exclusive_unit_waits_for_all_branches_despite_spare_capacity():
    state, admission = gate()
    warm(state, admission, active=('unit',))
    for active in (['unit', 'unit'], ['unit']):
        assert admission.allows('unit', active)
        assert not admission.allows('unit-exclusive', active)
        assert admission.reason == 'exclusive work waits for all host branches to finish'
    assert admission.allows('unit-exclusive', [])


def test_unknown_categories_are_exclusive_and_missing_metrics_fall_back_to_serial():
    state, admission = gate()
    warm(state, admission)
    assert not admission.allows('future-heavy-suite', ['ui'])
    assert admission.allows('future-heavy-suite', [])
    admission.monitor.sample = lambda: (_ for _ in ()).throw(OSError('missing'))
    state.now += 2
    assert not admission.allows('unit', ['ui'])
    assert admission.allows('unit', [])


def test_artifact_operations_keep_vm_and_unknown_work_exclusive():
    for other in ('system', 'e2e', 'ui-exclusive', 'future-job'):
        assert not compatible('artifacts', other)
        assert not compatible(other, 'artifacts')
