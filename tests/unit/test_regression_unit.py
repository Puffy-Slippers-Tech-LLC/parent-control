"""Unit partitions preserve exact coverage, module fixtures and isolation."""

from collections import Counter

import pytest

from regression_resources import compatible
from regression_unit import REVIEWED, buckets


def test_isolated_e2e_and_storage_contracts_share_unit_branches():
    reviewed = '''accessible_observation e2e_case_composition e2e_desktop_keyring
e2e_disabled_child e2e_fresh_desktop e2e_gdm_navigation e2e_gdm_product_free
e2e_gdm_recipient e2e_keyring_fixture_cleanup_safety e2e_kiosk_eligible_choices
e2e_kiosk_no_child e2e_license_viewer e2e_parent_search_launch e2e_plan
e2e_request_choices e2e_shell_search e2e_shell_search_results
e2e_startup_cache_cleanup_safety e2e_terminal_provider guest_inputs
storage_migration_cleanup_safety test_storage_cleanup_safety write_e2e
write_e2e_cleanup_safety'''.split()
    nodes = [f'tests/unit/test_{name}.py::test_case' for name in reviewed]
    plan = buckets(nodes)
    assert len(plan) == 4
    assert all(bucket.kind == 'unit' for bucket in plan)
    assert Counter(node for bucket in plan for node in bucket.nodeids) == Counter(nodes)


def test_balanced_buckets_keep_every_module_and_case_together_once():
    nodes = [f'tests/unit/test_{name}.py::test_case[{variant}]'
             for name in sorted(REVIEWED) for variant in ('first', 'second')]
    nodes += ['tests/unit/test_future.py::test_case',
              'tests/unit/nested/test_core.py::test_case',
              'tests/unit/test_test_applications.py::test_build']
    plan = buckets(nodes)
    shared = [bucket for bucket in plan if bucket.kind == 'unit']
    assert len(shared) == 4
    assert len(plan) == 7
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
