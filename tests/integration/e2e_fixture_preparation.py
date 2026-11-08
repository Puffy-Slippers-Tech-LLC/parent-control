"""Qualified E2E runtime closures after owned restoration and SSH readiness."""
from tools import fixture_execution, fixture_manifest
from system_fixture_preparation import attempt_id, guest_target, provision
import xml.etree.ElementTree as ET

SUBSETS = ('native',)
ACTIVITY_SUBSETS = ('native', 'activity', 'baseline-child')
ACTIVITY_CALLER = 'check_e2e_baseline_journey'
ACTIVITY_CALLERS = (ACTIVITY_CALLER, 'check_e2e_active_grant_disable',
                    'check_e2e_prepare_a_daily_balance_that_outlasts_a_soft_exception',
                    'E2E-038/none', 'E2E-038/unlock', 'E2E-038/fresh-login',
                    'E2E-038/allowance-edit', 'E2E-038/toggle', 'E2E-038/app-save', 'E2E-038/revoke',
                    'check_e2e_retained_app_visits',
                    'system-282', 'system-301',
                    'check_e2e_baseline_app_effects',
                    'check_e2e_natural_expiry',
                    'check_e2e_suspend_active_grant',
                    'check_e2e_suspend',
                    'check_e2e_overlay_approved_exit',
                    'check_e2e_compose_approval_and_return_to_the_child',
                    'check_e2e_kiosk_approval_return',
                    'check_e2e_overlay_approval',
                    'check_e2e_overlay_translated_approval',
                    'check_e2e_overlay_choices',
                    'E2E-005/combined-retained',
                    'E2E-006/enabled-precise', 'E2E-006/enabled-pattern',
                    'E2E-006/disabled-precise', 'E2E-006/disabled-pattern',
                    'E2E-007/zero-single', 'E2E-007/remaining-single',
                    'E2E-036/daily-positive',
                    'E2E-008/fresh-login', 'E2E-009/excluded', 'E2E-009/included',
                    'E2E-010/parent', 'E2E-010/other-child', 'E2E-011/daily-only',
                    'E2E-011/grant-only', 'E2E-011/combined',
                    'E2E-012/excluded-first', 'E2E-012/included-second',
                    'E2E-043/both-surfaces',
                    'E2E-013/child-overlay-recovery', 'E2E-013/kiosk-recovery',
                    'E2E-015/child-overlay-cancel', 'E2E-015/child-overlay-escape',
                    'E2E-015/child-overlay-approved',
                    'E2E-022/app-restart-expired',
                    'E2E-022/sign-out-in-active',
                    'E2E-022/reboot-active',
                    'E2E-022/reboot-expired',
                    'E2E-022/sign-out-in-expired',
                    'E2E-022/idle-active-expired',
                    'E2E-022/suspend-wake-active',
                    'E2E-022/suspend-wake-expired',
                    'E2E-025/excluded-new-login',
                    'E2E-025/excluded-retained-unlock',
                    'E2E-025/included-new-login',
                    'E2E-025/included-retained-unlock',
                    'E2E-059/overlay-hebrew',
                    'E2E-061/panel-expiry',
                    'E2E-048/daily-only-kiosk',
                    'E2E-048/grant-dominant-kiosk',
                    'E2E-019/native-grid-allowed-enabled',
                    'E2E-019/native-desktop-allowed-enabled',
                    'E2E-019/native-file-manager-allowed-enabled',
                    'E2E-019/native-file-manager-hard-blocked-enabled',
                    'E2E-019/native-file-manager-soft-blocked-enabled',
                    'E2E-019/native-grid-hard-blocked-enabled',
                    'E2E-019/native-grid-soft-blocked-enabled')
LIFECYCLE_SUBSETS = ('native', 'baseline-child')
LIFECYCLE_CALLER = 'E2E-027/continuous'
APP_SET_CALLER = 'check_e2e_compose_a_named_app_rule_set'


def qualified_subsets(subsets=SUBSETS, *, caller=None, product_free=False):
    """Bind additional fixture files to their fixed consumer and entry state."""
    if (type(subsets) is not tuple or
            (subsets != SUBSETS and not (subsets == ACTIVITY_SUBSETS
             and caller in ACTIVITY_CALLERS and not product_free)
             and not (subsets == LIFECYCLE_SUBSETS
                      and ((caller == LIFECYCLE_CALLER and product_free)
                           or (caller == APP_SET_CALLER and not product_free))))):
        raise ValueError('fixtures:e2e-profile-not-qualified')
    return subsets


def online_restore(lease):
    memory = ET.fromstring(lease.installed_xml).find('memory')
    return memory is not None and memory.get('snapshot') == 'internal'


def selection_record(value, target=None, *, product_free=False):
    if value is None:
        raise ValueError('fixtures:execution-selection-required')
    selection = fixture_execution.Selection.from_record(
        value.record() if isinstance(value, fixture_execution.Selection) else value)
    if (selection.target not in ('ubuntu', 'fedora')
            or (target is not None and selection.target != target)):
        raise ValueError('fixtures:e2e-' + ('product-free' if product_free else 'installed')
                         + '-target-not-qualified')
    return selection.record()


def validate_input(value, target=None, *, product_free=False):
    record = selection_record(value, target=target, product_free=product_free)
    fixture_execution.verify(record)
    return record


def require_product_free_restore(lease):
    """Only a qualified empty baseline may release graphical input."""
    if guest_target(lease.capture.state['guest']) is None:
        raise ValueError('fixtures:e2e-product-free-target-not-qualified')
    if (getattr(lease, 'online_pending', False) is True
            or (getattr(lease, 'installed_name', None) is not None
                and getattr(lease, '_restored_name', None) != lease.capture.state['proof']['name'])):
        raise ValueError('fixtures:e2e-product-free-baseline-required')


def prepare(vm, lease, directory, selection, *, product_free=False,
            subsets=SUBSETS, caller=None):
    subsets = qualified_subsets(subsets, caller=caller, product_free=product_free)
    guest = lease.capture.state['guest']
    target = guest_target(guest)
    if product_free:
        require_product_free_restore(lease)
    elif target is None:
        raise ValueError('fixtures:e2e-installed-target-not-qualified')
    record = validate_input(selection, target=target, product_free=product_free)
    if not product_free and (lease.online_pending is not False or not lease.installed_name
            or (online_restore(lease) and lease.online_bootstrap is not None)
            or (not online_restore(lease) and lease._restored_name != lease.installed_name)):
        raise ValueError('fixtures:e2e-installed-restored-rebound-required')
    return {**provision(vm, lease, directory, record, subsets=subsets),
            'subsets': subsets, 'caller': caller,
            **({'product_free': True} if product_free else {})}


def asset_hashes(selection, *, subsets=SUBSETS, caller=None, child=False, product_free=False):
    """Bind legacy public observation keys to the selected runtime bytes."""
    subsets = qualified_subsets(subsets, caller=caller, product_free=product_free)
    if type(child) is not bool or (child and not (subsets == ACTIVITY_SUBSETS
            or subsets == LIFECYCLE_SUBSETS and caller == APP_SET_CALLER and not product_free)):
        raise ValueError('fixtures:e2e-profile-not-qualified')
    manifest = fixture_execution.verify(selection_record(selection))
    from tests.fixtures import native_assets
    destinations = native_assets.source_destinations('@child@' if child else '@other@', alias=not child)
    if subsets == ACTIVITY_SUBSETS:
        destinations.update(zip(native_assets.activity_sources(), (
            (native_assets.ACTIVITY_EXECUTABLE, 0o755),
            *((native_assets.ACTIVITY_PREFIX + '/' + name, 0o644)
              for name in native_assets.GUI_FILES))))
    selected = fixture_manifest.select(subsets)
    return {source: next(manifest['members'][key]['sha256']
                        for key, item in selected.items()
                        if item['destination'] == destination)
            for source, (destination, _mode) in destinations.items()}
