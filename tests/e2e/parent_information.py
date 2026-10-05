"""Historical Parent information composition retained for worker safety tests.

Installed product information and return are owned by case 151. Help/About
link availability is accepted by the production About component UI test.
"""

from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management


PLAN = JourneyPlan(
    prefix='parent-links', worker_mode='parent_links',
    screen_tags={
        **fresh_desktop('parent'), **parent_management(),
        'about': 'ui:parent-about-information',
        'about-returned': 'ui:about-returned',
        'parent-returned': 'ui:parent-returned',
    },
    phases={
        'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
        'parent-focused': 'step-1', 'recipient-qualified': 'step-1',
        'recipient-rechecked': 'step-1', 'desktop': 'step-1',
        'parent-command': 'step-1', 'parent-window': 'step-1',
        'child-picker-opened': 'step-1', 'child-choice-highlighted': 'step-1',
        'parent-selected': 'step-1', 'about': 'step-2',
        'about-returned': 'step-3', 'parent-returned': 'step-3',
    },
    advance_after={'parent-selected': 'step-2', 'about': 'step-3'},
    settings_checks={'parent-returned': 'parent-selected'},
)
