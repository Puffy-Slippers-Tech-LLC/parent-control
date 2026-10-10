"""Cases 58/59: both children's choices survive independent overlay/kiosk visits."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import desktop_entry, fresh_desktop, parent_management, prefixed_stages, station_entry
from request_flow import overlay_to_kiosk
from request_composition import KioskRequestJourney


SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'riley-allowance': 'ui:time-explanation-setup-thirty-read',
    'existing-child-picker-opened': 'ui:existing-child-picker-opened',
    'existing-child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'existing-returned': 'ui:discovery-ready',
    'jordan-allowance': 'ui:time-explanation-setup-thirty-read',
    'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
    'gdm-switched': 'ui:gdm-returned', **prefixed_stages('seed', station_entry()),
    'seed-child': 'ui:remembered-kiosk-jordan-select-default',
    'seed-approver': 'ui:remembered-kiosk-jordan-approver',
    'seed-cancel': 'ui:kiosk-request-cancel', 'seed-returned': 'ui:gdm-station-returned',
}
CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')}
LOGIN_STAGES = tuple(fresh_desktop('parent'))
PHASES = {stage: 'step-1' for stage in SCREENS}
ENTRY_SCREENS = dict(SCREENS)
TRANSFERS = {}
for prefix, child, role, entry, phase in (
        ('jordan', 'jordan', 'other-child', 'fresh', 'step-1'),
        ('riley', 'riley', 'child', 'fresh', 'step-3'),
        ('jordan-return', 'jordan', 'other-child', 'retained', 'step-3'),
        ('riley-return', 'riley', 'child', 'retained', 'step-3')):
    stages = prefixed_stages(prefix + '-entry', desktop_entry(role, source='gdm', entry=entry))
    LOGIN_STAGES += tuple(prefixed_stages(prefix + '-entry', fresh_desktop(role)))
    recipient = 'child' if role == 'child' else 'standard'
    CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                    prefix + '-entry-' + recipient + '-recipient-rechecked')
    stages[prefix + '-launch'] = f'ui:remembered-overlay-{child}-launch'
    if entry == 'fresh':
        stages.update({prefix + '-' + action: f'ui:remembered-overlay-{child}-{action}'
                       for action in ('default', 'approver', 'custom', 'text', 'apps')})
    stages[prefix + '-source'] = f'ui:remembered-overlay-{child}-read'
    transfer = overlay_to_kiosk(prefix + '-transfer', child=child, choices='remembered')
    stages.update(transfer)
    if prefix != 'riley-return':
        stages.update({prefix + '-exit': 'ui:kiosk-request-cancel',
                       prefix + '-greeter': 'ui:gdm-station-returned'})
    SCREENS.update(stages)
    PHASES.update({stage: phase for stage in stages})
    if prefix == 'jordan':
        PHASES.update({stage: 'step-2' for stage in transfer})
        PHASES.update({prefix + '-exit': 'step-3', prefix + '-greeter': 'step-3'})
    TRANSFERS[prefix + '-transfer-read'] = prefix + '-source'

# Keep the old full history available only to the explicit maintenance probes.
# It is no longer customer acceptance for remembered request choices.
DIAGNOSTIC_PLAN = JourneyPlan(
    prefix='remembered-choices', worker_mode='remembered_choices', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', **PHASES, 'installed-greeter': 'start'},
    advance_after={'installed-greeter': 'step-1', 'jordan-source': 'step-2',
                   'jordan-transfer-read': 'step-3'},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES), challenges=CHALLENGES,
    child_bindings={'riley-allowance': 'child', 'jordan-allowance': 'existing'},
    balance_checks={'riley-allowance': 1800, 'jordan-allowance': 1800},
    request_transfer_checks=TRANSFERS,
    assertions_after={'riley-return-transfer-read': 'visible-result'},
)


PLANS = {}
for choices, children in (('remembered', ('jordan', 'riley')),
                          ('remembered-second', ('riley', 'jordan'))):
    SCREENS = dict(ENTRY_SCREENS)
    PHASES = {stage: 'step-1' for stage in SCREENS}
    CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')}
    LOGIN_STAGES = tuple(fresh_desktop('parent'))
    for child in children:
        role = 'child' if child == 'riley' else 'other-child'
        recipient = 'child' if role == 'child' else 'standard'
        stages = prefixed_stages(child + '-entry', desktop_entry(role, source='gdm', entry='fresh'))
        LOGIN_STAGES += tuple(prefixed_stages(child + '-entry', fresh_desktop(role)))
        CHALLENGES[child + '-entry'] = (
            role, child + '-entry-' + recipient + '-recipient-qualified',
            child + '-entry-' + recipient + '-recipient-rechecked')
        stages[child + '-launch'] = f'ui:{choices}-overlay-{child}-launch'
        stages.update({child + '-' + action: f'ui:{choices}-overlay-{child}-{action}'
                       for action in ('default', 'approver', 'custom', 'text', 'apps')})
        stages[child + '-source'] = f'ui:{choices}-overlay-{child}-read'
        transfer = overlay_to_kiosk(child + '-transfer', child=child, choices=choices)
        stages.update(transfer)
        if child == children[0]:
            stages.update({child + '-exit': 'ui:kiosk-request-cancel',
                           child + '-greeter': 'ui:gdm-station-returned'})
        SCREENS.update(stages)
        PHASES.update({stage: 'step-1' if child == children[0] else 'step-3' for stage in stages})
        if child == children[0]:
            PHASES.update({stage: 'step-2' for stage in transfer})
            PHASES.update({child + '-exit': 'step-3', child + '-greeter': 'step-3'})
    for child in children:
        SCREENS.update({f'{child}-revisit-select': f'ui:{choices}-kiosk-{child}-select',
                        f'{child}-revisit-read': f'ui:{choices}-kiosk-{child}-read'})
    PLANS[choices] = JourneyPlan(
        prefix='remembered-choices', worker_mode='remembered_choices', screen_tags=SCREENS,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: PHASES[stage] if stage in PHASES else 'step-3' for stage in SCREENS},
                'installed-greeter': 'start'},
        advance_after={'installed-greeter': 'step-1', children[0] + '-source': 'step-2',
                       children[0] + '-transfer-read': 'step-3'},
        invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES), challenges=CHALLENGES,
        child_bindings=DIAGNOSTIC_PLAN.child_bindings,
        balance_checks=DIAGNOSTIC_PLAN.balance_checks,
        request_transfer_checks={
            **{f'{child}-transfer-read': f'{child}-source' for child in children},
            **{f'{child}-revisit-read': f'{child}-source' for child in children},
        },
        assertions_after={children[-1] + '-revisit-read': 'visible-result'},
    )
PLAN = PLANS['remembered']
SECOND_PLAN = PLANS['remembered-second']


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800, journey_type=KioskRequestJourney)


def execute_second(recorder, context):
    record_installed_journey(recorder, context, SECOND_PLAN, timeout=1800, journey_type=KioskRequestJourney)


E2E_CASES = {'overlay-to-kiosk-first': execute, 'overlay-to-kiosk-second': execute_second}
