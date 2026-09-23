"""GDM05 and DESK01 qualification for fresh fixture logins."""

from pathlib import Path

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop
from keyring_prompt_fixture import provider_metadata
from private_artifacts import require


def _plan(role):
    standard = role == 'standard'
    prefix = 'fresh-standard' if standard else 'fresh-parent'
    screens = fresh_desktop('other-child' if standard else 'parent')
    screens['desktop'] = 'ui:fresh-standard-desktop' if standard else 'ui:fresh-parent-desktop'
    return JourneyPlan(
        prefix=prefix, worker_mode=prefix.replace('-', '_') + '_desktop',
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'start' if stage == 'installed-greeter' else 'step-1'
                   for stage in screens}},
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
