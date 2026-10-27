"""Read-only listing of the installed dispatcher's literal check bindings."""
import ast
import json
from pathlib import Path
import platform

# Operations are callable through the dispatcher, but are never tests. Keep
# exclusions visible in --list instead of treating every check_* as coverage.
EXCLUDED = {
    **{name: 'maintenance/recovery operation, not a test' for name in (
        'check_test_recovery', 'check_graphical_recovery', 'check_system_recovery',
        'check_tmp_storage', 'check_tmp_storage_cleanup', 'check_storage_migration',
        'check_retained_runs_cleanup')},
    **{name: 'legacy fixture envelope is not qualified for clean captures' for name in (
        'check_parent_about', 'check_parent_access')},
    'check_e2e_read_an_expanded_time_explanation':
        'same time_explanation qualification as check_e2e_time_explanation',
    'check_e2e_mate_prompt': 'same mate_prompt qualification as check_e2e_auth_prompt',
    'check_e2e_toggle': 'same parent_toggle qualification as check_e2e_parent_save',
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
