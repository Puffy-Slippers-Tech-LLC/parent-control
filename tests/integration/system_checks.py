"""Registered installed system checks and separate host-only checks."""
import ast
import json
from pathlib import Path
import platform

# Register only assertions outside current or planned E2E composition. A new
# check_* wrapper is not automatically a test. Existing guarded selectors remain
# available for building-block qualification and engineering diagnostics.
SYSTEM_CHECKS = (
    # Credential-recipient refusal, single-use challenges and privileged workers.
    'check_e2e_auth_prompt',
    'check_e2e_challenges',
    'check_e2e_gdm_recipient',
    'check_e2e_overlay_prompt',
    'check_graphical_credentials',
    'check_graphical_vt6_authentication',
    # Engineering mutations, native witnesses and recovery, never customer setup.
    'check_e2e_active_grant_disable',
    'check_e2e_basic_locale_auth',
    'check_e2e_child_isolation',
    'check_e2e_kiosk_admission_contention',
    'check_e2e_kiosk_configuration_recovery',
    'check_e2e_kiosk_feedback_confinement',
    'check_e2e_kiosk_identity_helper',
    'check_e2e_kiosk_lease_variation',
    'check_e2e_kiosk_notification_wellbeing',
    'check_e2e_kiosk_optional_artwork',
    'check_e2e_kiosk_preferences_confinement',
    'check_e2e_kiosk_routing_variation',
    'check_e2e_kiosk_service_recovery',
    'check_e2e_kiosk_service_route',
    'check_e2e_kiosk_service_variation',
    'check_e2e_locale_discovery_auth',
    # Immutable installed fixture integrity.
    'check_fixture_e2e_installed',
)

# Host-only checks never acquire a VM or join installed-system coverage.
HOST_CHECKS = {
    'graphical-worker': 'check_graphical_worker',
    'package-notice': 'check_package_notice',
}


def host_check(category, *, host_os=None):
    host_os = platform.freedesktop_os_release()['ID'] if host_os is None else host_os
    if category == 'package-notice' and host_os not in ('ubuntu', 'debian'):
        raise ValueError('package-notice requires an Ubuntu/Debian host')
    return HOST_CHECKS[category]


def inventory(directory=Path(__file__).resolve().parent, *, host_os=None):
    result = []
    for name in sorted(SYSTEM_CHECKS):
        path = directory / (name + '.py')
        if path.is_symlink() or not path.is_file():
            raise ValueError('system:missing-registered-check:' + name)
        description = ast.get_docstring(ast.parse(path.read_text())) or ''
        result.append({'name': path.stem, 'description': description.split('\n')[0],
                       'excluded_reason': None})
    return result


def runnable(directory=Path(__file__).resolve().parent, *, host_os=None):
    return [item['name'] for item in inventory(directory, host_os=host_os)
            if item['excluded_reason'] is None]


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
