"""Transport setup for the installed extension Parent recovery history."""

from desktop_session import run_attached
from installed_journey import JourneyPlan
from journey_blocks import desktop_entry, prefixed_stages


SCREENS = {
    'child-before': 'system:child-entry-same',
    'child-switch': 'system:child-switch-user',
    'child-greeter': 'ui:gdm-returned',
    **prefixed_stages('parent', desktop_entry('parent', source='gdm', entry='fresh')),
}
PLAN = JourneyPlan(
    prefix='extension-parent', worker_mode='extension_parent', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}},
    invocations=tuple(stage for stage, tag in SCREENS.items() if tag.startswith('ui:')),
    challenges={'parent': ('parent', 'parent-recipient-qualified',
                           'parent-recipient-rechecked')},
)


def prepare_parent_desktop(directory, lease, transport, ledger, *, expected_inputs,
                           progress, context):
    """Stop at the usable parent desktop; the installed owner keeps the guest."""
    return run_attached(directory, lease, transport, ledger, PLAN,
        expected_inputs=expected_inputs, progress=progress, context=context)
