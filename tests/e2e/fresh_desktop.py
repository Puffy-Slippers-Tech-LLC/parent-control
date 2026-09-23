"""GDM05 and DESK01 qualification for fresh fixture logins."""

from pathlib import Path

from installed_journey import InstalledJourney, JourneyPlan
from keyring_prompt_fixture import provider_metadata
from private_artifacts import require


def _plan(role):
    standard = role == 'standard'
    account = 'standard' if standard else 'parent'
    prefix = 'fresh-standard' if standard else 'fresh-parent'
    return JourneyPlan(
        prefix=prefix, worker_mode=prefix.replace('-', '_') + '_desktop',
        screen_tags={
            'installed-greeter': 'ui:gdm-other-list',
            'other-parent-focused': 'ui:gdm-other-focused',
            'wrong-recipient-refused': 'ui:' + (
                'gdm-standard-wrong-recipient-refused' if standard
                else 'gdm-wrong-recipient-refused'),
            account + '-list': 'ui:gdm-standard-list' if standard else 'ui:gdm-list',
            account + '-focused': 'ui:gdm-standard-focused' if standard else 'ui:gdm-focused',
            ('standard-' if standard else '') + 'recipient-qualified': 'ui:' + (
                'gdm-standard-recipient' if standard else 'gdm-parent-recipient'),
            ('standard-' if standard else '') + 'recipient-rechecked': 'ui:' + (
                'gdm-standard-recipient-rechecked' if standard
                else 'gdm-parent-recipient-rechecked'),
            'desktop': 'ui:fresh-standard-desktop' if standard else 'ui:fresh-parent-desktop',
        },
        phases={'ready': 'setup', 'setup-detached': 'setup',
                'installed-greeter': 'start',
                'other-parent-focused': 'step-1',
                'wrong-recipient-refused': 'step-1',
                account + '-list': 'step-1', account + '-focused': 'step-1',
                ('standard-' if standard else '') + 'recipient-qualified': 'step-1',
                ('standard-' if standard else '') + 'recipient-rechecked': 'step-1',
                'desktop': 'step-1'},
    )


PARENT_PLAN = _plan('parent')
STANDARD_PLAN = _plan('standard')
KEYRING_STANDARD_PLAN = JourneyPlan(
    prefix='keyring-standard', worker_mode='keyring_standard_desktop',
    screen_tags={**STANDARD_PLAN.screen_tags,
                 'keyring-cancelled-desktop': 'ui:keyring-cancel-standard'},
    phases={**STANDARD_PLAN.phases, 'keyring-cancelled-desktop': 'step-1'},
    stage_actions={'desktop': 'prepare-keyring'},
)


def prepare_keyring(journey, guard):
    """Request a real challenge on the bound fixture bus after fresh login."""
    guard()
    program = Path(__file__).with_name('keyring_prompt_fixture.py').read_bytes()
    response = journey.transport.call(
        ['/usr/bin/python3', '-I', '-', 'standard'], input=program, timeout=60)
    try:
        metadata = provider_metadata(response)
    except ValueError:
        require(False, 'keyring-fixture:preparation')
    guard()
    return {'profile': 'locked-login-keyring', **metadata}


class FreshDesktopJourney(InstalledJourney):
    def __init__(self, context, progress, *, role):
        require(role in ('parent', 'standard'), 'fresh-desktop:role')
        super().__init__(context, progress,
                         PARENT_PLAN if role == 'parent' else STANDARD_PLAN)


class KeyringDesktopJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, KEYRING_STANDARD_PLAN,
                         actions={'prepare-keyring': prepare_keyring})
