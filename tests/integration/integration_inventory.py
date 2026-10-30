"""Explicit standalone integration registrations, not E2E building blocks."""
import ast
import json
from pathlib import Path
import platform

# Register only assertions outside current or planned E2E composition. A new
# check_* wrapper is not automatically a test. Existing guarded selectors remain
# available for building-block qualification and engineering diagnostics.
INTEGRATION_CHECKS = (
    # Credential-recipient refusal, single-use challenges and privileged workers.
    'check_e2e_auth_prompt',
    'check_e2e_challenges',
    'check_e2e_gdm_recipient',
    'check_e2e_overlay_prompt',
    'check_graphical_credentials',
    'check_graphical_vt6_authentication',
    'check_graphical_worker',
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
    # Immutable fixture integrity and real package-manager hooks.
    'check_fixture_e2e_installed',
    'check_package_notice',
)

# These checks exercise host-native services/tools, independently of the guest.
HOSTS = {
    'check_package_notice': ('ubuntu', 'debian'),  # real APT/dpkg chroots
}


def inventory(directory=Path(__file__).resolve().parent, *, host_os=None):
    host_os = platform.freedesktop_os_release()['ID'] if host_os is None else host_os
    result = []
    for name in sorted(INTEGRATION_CHECKS):
        path = directory / (name + '.py')
        if path.is_symlink() or not path.is_file():
            raise ValueError('integration:missing-registered-check:' + name)
        description = ast.get_docstring(ast.parse(path.read_text())) or ''
        reason = None
        if path.stem in HOSTS and host_os not in HOSTS[path.stem]:
            reason = 'host-specific check; requires ' + '/'.join(HOSTS[path.stem])
        result.append({'name': path.stem, 'description': description.split('\n')[0],
                       'excluded_reason': reason})
    return result


def runnable(directory=Path(__file__).resolve().parent, *, host_os=None):
    return [item['name'] for item in inventory(directory, host_os=host_os)
            if item['excluded_reason'] is None]


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2))
