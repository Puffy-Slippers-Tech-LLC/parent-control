"""Read-only listing of the installed dispatcher's literal check bindings."""
import ast
import json
from pathlib import Path
import platform

# Explicit engineering probes and operations remain callable through the
# dispatcher. Routine integration covers product behavior and essential safety;
# keep exclusions visible in --list rather than scheduling every check_*.
EXCLUDED = {
    **{name: 'maintenance/recovery operation, not a test' for name in (
        'check_test_recovery', 'check_graphical_recovery', 'check_system_recovery',
        'check_tmp_storage', 'check_tmp_storage_cleanup', 'check_storage_migration',
        'check_retained_runs_cleanup')},
    **{name: 'standalone fixture preparation qualification; explicit engineering use only'
       for name in (
        'check_fixture_provisioning', 'check_fixture_snapshots',
        'check_fixture_live_refresh', 'check_fixture_transfer',
        'check_fixture_serial', 'check_fixture_recorded_serial',
        'check_fixture_system_product_free', 'check_fixture_system_installed',
        'check_fixture_e2e_product_free')},
    'check_graphical_attachment':
        'graphics API comparison/trace probe; explicit engineering use only',
    'check_e2e_app_row_observations':
        'duplicate complete row-read qualification; covered by check_e2e_native_fixtures',
    **{name: 'standalone harness qualification, not a product or essential safety check'
       for name in (
        'check_graphical_smoke', 'check_graphical_transport',
        'check_graphical_serial', 'check_graphical_vt6_prompt', 'check_e2e_watch',
        'check_e2e_gdm_product_free',
        'check_e2e_upgrade_assets', 'check_e2e_desktop_language',
        'check_e2e_give_repeated_public_operations_distinct_stages')},
}

# These checks exercise host-native services/tools, independently of the guest.
HOSTS = {
    'check_graphical_transport': ('ubuntu',),  # libvirtd's AppArmor profile
    'check_package_notice': ('ubuntu', 'debian'),  # real APT/dpkg chroots
}


def inventory(directory=Path(__file__).resolve().parent, *, host_os=None):
    host_os = platform.freedesktop_os_release()['ID'] if host_os is None else host_os
    result = []
    for path in sorted(directory.glob('check_*.py')):
        if path.is_symlink() or not path.is_file():
            continue
        description = ast.get_docstring(ast.parse(path.read_text())) or ''
        reason = EXCLUDED.get(path.stem)
        if reason is None and path.stem in HOSTS and host_os not in HOSTS[path.stem]:
            reason = 'host-specific check; requires ' + '/'.join(HOSTS[path.stem])
        result.append({'name': path.stem, 'description': description.split('\n')[0],
                       'excluded_reason': reason})
    return result


def runnable(directory=Path(__file__).resolve().parent, *, host_os=None):
    return [item['name'] for item in inventory(directory, host_os=host_os)
            if item['excluded_reason'] is None]


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
