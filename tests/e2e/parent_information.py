"""E2E-042/parent-links: offered links and unchanged Parent settings."""

from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import fresh_desktop, parent_management


PLAN = JourneyPlan(
    prefix='parent-links', worker_mode='parent_links',
    screen_tags={
        **fresh_desktop('parent'), **parent_management(),
        'help': 'ui:parent-help-clickable',
        'about': 'ui:parent-information-about',
        'license': 'ui:parent-information-clickable',
        'license-closed': 'ui:license-closed',
        'about-returned': 'ui:about-returned',
        'parent-returned': 'ui:parent-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
        'parent-focused': 'step-1', 'recipient-qualified': 'step-1',
        'recipient-rechecked': 'step-1', 'desktop': 'step-1',
        'parent-command': 'step-1', 'parent-window': 'step-1',
        'child-picker-opened': 'step-1', 'child-choice-highlighted': 'step-1',
        'parent-selected': 'step-1', 'help': 'step-2', 'about': 'step-2',
        'license': 'step-2', 'license-closed': 'step-3',
        'about-returned': 'step-3', 'parent-returned': 'step-3',
    },
    advance_after={'parent-selected': 'step-2', 'license': 'step-3'},
    settings_checks={'parent-returned': 'parent-selected'},
)


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN)


E2E_CASES = {'parent-links': execute}
