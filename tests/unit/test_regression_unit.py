"""Unit partitions preserve exact coverage, module fixtures and isolation."""

from collections import Counter

import pytest

from regression_resources import compatible
from regression_unit import REVIEWED, buckets
from tests.support.paths import ROOT


@pytest.mark.parametrize('category', ['unit', 'cleanup', 'ui'])
def test_host_module_inventory_has_no_unreviewed_fallback(category):
    from regression_cleanup import buckets as cleanup_buckets
    from regression_ui import buckets as ui_buckets

    directory = ROOT / 'tests' / ('ui' if category == 'ui' else 'unit')
    paths = sorted(directory.rglob('test_*.py'))
    if category == 'cleanup':
        paths = [path for path in paths if path.name.endswith('_cleanup_safety.py')
                 or path.name == 'test_graphical_lease.py']
    partition = {'unit': buckets, 'cleanup': cleanup_buckets, 'ui': ui_buckets}[category]
    nodes = [path.relative_to(ROOT).as_posix() + '::inventory_review' for path in paths]
    plan = partition(nodes)
    # A necessary exclusive module must be explicitly recorded here with its
    # concrete shared-resource reason after review. Unknown execution remains
    # safely exclusive, but is never a completed classification.
    reviewed_exclusive = {}
    exclusive = {path for bucket in plan if bucket.kind.endswith('-exclusive')
                 for path in bucket.paths}
    assert exclusive == set(reviewed_exclusive), 'Review new host modules for parallelism'
    assert all(reviewed_exclusive.values())
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)


def test_balanced_buckets_keep_every_module_and_case_together_once():
    nodes = [f'tests/unit/test_{name}.py::test_case[{variant}]'
             for name in sorted(REVIEWED) for variant in ('first', 'second')]
    nodes += ['tests/unit/test_future.py::test_case',
              'tests/unit/nested/test_core.py::test_case']
    plan = buckets(nodes)
    shared = [bucket for bucket in plan if bucket.kind == 'unit']
    assert len(shared) == 4
    assert len(plan) == 6
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)
    assert len({path for bucket in plan for path in bucket.paths}) == sum(len(b.paths) for b in plan)
    assert all(bucket.nodeids and bucket.estimate > 0 for bucket in plan)
    # Packing must not depend on collection order; case order inside a module
    # still follows discovery so class/session fixtures retain normal ordering.
    assert [b.paths for b in plan] == [b.paths for b in buckets(list(reversed(nodes)))]


def test_small_selection_has_no_empty_or_extra_buckets():
    nodes = ['tests/unit/test_core.py::test_case[chosen]',
             'tests/unit/test_core.py::test_case[other]']
    bucket, = buckets(nodes)
    assert bucket.nodeids == tuple(nodes)
    assert bucket.paths == ('tests/unit/test_core.py',)
    assert bucket.kind == 'unit'


@pytest.mark.parametrize('nodes', [None, [], ['tests/unit/test_core.py::test_case'] * 2,
    ['tests/ui/test_a.py::test_a'], ['tests/unit/../test_a.py::test_a'],
    ['/tests/unit/test_a.py::test_a'], ['tests/unit/test_a.py'],
    ['tests/unit/test_a.py::'], ['tests/unit/./test_a.py::test_a'],
    ['tests/unit/helper.py::test_a']])
def test_invalid_inventory_refuses_before_scheduling(nodes):
    with pytest.raises(ValueError, match='Unit inventory'):
        buckets(nodes)


@pytest.mark.parametrize('kind', ['unit', 'ui-request', 'publish', 'artifacts',
                                 'cleanup', 'unit-exclusive', 'system', 'e2e'])
def test_unreviewed_unit_work_is_exclusive_in_both_orders(kind):
    assert not compatible('unit-exclusive', kind)
    assert not compatible(kind, 'unit-exclusive')


def test_reviewed_unit_buckets_keep_existing_build_and_host_pairings():
    for kind in ('unit', 'ui-request', 'component', 'publish', 'artifacts'):
        assert compatible('unit', kind) and compatible(kind, 'unit')
