"""Cases 58–61: both children's choices survive independent request-form visits."""
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages, station_entry
from request_flow import overlay_to_kiosk, kiosk_to_overlay, transfer_allowances
from request_composition import KioskRequestJourney


SCREENS = {
    **transfer_allowances(), **prefixed_stages('seed', station_entry()),
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


REVERSE_PLANS = {}
for choices, children in (('remembered', ('jordan', 'riley')),
                          ('remembered-second', ('riley', 'jordan'))):
    SCREENS = transfer_allowances()
    PHASES = {stage: 'step-1' for stage in SCREENS}
    CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')}
    LOGIN_STAGES = tuple(fresh_desktop('parent'))
    for child in children:
        role = 'child' if child == 'riley' else 'other-child'
        recipient = 'child' if child == 'riley' else 'standard'
        prefix = child + '-seed'
        SCREENS.update(prefixed_stages(prefix + '-entry', desktop_entry(role, source='gdm', entry='fresh')))
        LOGIN_STAGES += tuple(prefixed_stages(prefix + '-entry', fresh_desktop(role)))
        CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                        prefix + '-entry-' + recipient + '-recipient-rechecked')
        SCREENS.update({prefix + '-' + action: f'ui:{choices}-overlay-{child}-{action}'
                        for action in ('launch', 'default', 'approver', 'cancel', 'returned')})
        SCREENS.update({prefix + '-logout': f'system:{recipient}-logout',
                        prefix + '-greeter': 'ui:gdm-returned'})
    SCREENS.update(prefixed_stages('station', station_entry()))
    PHASES.update({stage: 'step-1' for stage in SCREENS})
    for child in children:
        stages = {child + '-' + action: f'ui:{choices}-kiosk-{child}-{action}'
                  for action in ('select-default', 'approver', 'custom', 'text', 'apps')}
        if child == children[-1]:
            stages[child + '-select-default'] = f'ui:{choices}-reverse-kiosk-{child}-select-default'
        stages[child + '-source'] = f'ui:{choices}-kiosk-{child}-read'
        transfer = kiosk_to_overlay(child + '-transfer', child=child, entry='fresh', choices=choices)
        stages.update(transfer)
        role = 'child' if child == 'riley' else 'other-child'
        recipient = 'child' if child == 'riley' else 'standard'
        prefix = child + '-transfer-entry'
        LOGIN_STAGES += tuple(prefixed_stages(prefix, fresh_desktop(role)))
        CHALLENGES[prefix] = (role, prefix + '-' + recipient + '-recipient-qualified',
                              prefix + '-' + recipient + '-recipient-rechecked')
        stages.update({child + '-exit': f'ui:{choices}-overlay-{child}-cancel',
                       child + '-desktop': f'ui:{choices}-overlay-{child}-returned',
                       child + '-logout': f'system:{recipient}-logout',
                       child + '-greeter': 'ui:gdm-returned'})
        if child == children[0]:
            stages.update(prefixed_stages('next-station', station_entry()))
        SCREENS.update(stages)
        PHASES.update({stage: 'step-1' if child == children[0] else 'step-3' for stage in stages})
        if child == children[0]:
            PHASES.update({stage: 'step-2' for stage in transfer})
            PHASES.update({stage: 'step-3' for stage in (
                *prefixed_stages('next-station', station_entry()),
                child + '-exit', child + '-desktop', child + '-logout', child + '-greeter')})
    for child in children:
        role = 'child' if child == 'riley' else 'other-child'
        recipient = 'child' if child == 'riley' else 'standard'
        prefix = child + '-revisit'
        SCREENS.update(prefixed_stages(prefix + '-entry', desktop_entry(role, source='gdm', entry='fresh')))
        LOGIN_STAGES += tuple(prefixed_stages(prefix + '-entry', fresh_desktop(role)))
        CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                        prefix + '-entry-' + recipient + '-recipient-rechecked')
        SCREENS.update({prefix + '-launch': f'ui:{choices}-overlay-{child}-launch',
                        prefix + '-read': f'ui:{choices}-overlay-{child}-read'})
        if child == children[0]:
            SCREENS.update({prefix + '-exit': f'ui:{choices}-overlay-{child}-cancel',
                            prefix + '-desktop': f'ui:{choices}-overlay-{child}-returned',
                            prefix + '-logout': f'system:{recipient}-logout',
                            prefix + '-greeter': 'ui:gdm-returned'})
    REVERSE_PLANS[choices] = JourneyPlan(
        prefix='remembered-reverse', worker_mode='remembered_reverse', screen_tags=SCREENS,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: PHASES[stage] if stage in PHASES else 'step-3' for stage in SCREENS},
                'installed-greeter': 'start'},
        advance_after={'installed-greeter': 'step-1', children[0] + '-source': 'step-2',
                       children[0] + '-transfer-read': 'step-3'},
        invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES), challenges=CHALLENGES,
        child_bindings=PLAN.child_bindings, balance_checks=PLAN.balance_checks,
        request_transfer_checks={
            **{child + '-transfer-read': child + '-source' for child in children},
            **{child + '-revisit-read': child + '-source' for child in children},
        },
        assertions_after={children[-1] + '-revisit-read': 'visible-result'},
    )
REVERSE_PLAN = REVERSE_PLANS['remembered']
REVERSE_SECOND_PLAN = REVERSE_PLANS['remembered-second']


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=1800, journey_type=KioskRequestJourney)


def execute_second(recorder, context):
    record_installed_journey(recorder, context, SECOND_PLAN, timeout=1800, journey_type=KioskRequestJourney)


def execute_reverse(recorder, context):
    record_installed_journey(recorder, context, REVERSE_PLAN, timeout=1800, journey_type=KioskRequestJourney)


def execute_reverse_second(recorder, context):
    record_installed_journey(recorder, context, REVERSE_SECOND_PLAN, timeout=1800, journey_type=KioskRequestJourney)


E2E_CASES = {'overlay-to-kiosk-first': execute, 'overlay-to-kiosk-second': execute_second,
             'kiosk-to-overlay-first': execute_reverse, 'kiosk-to-overlay-second': execute_reverse_second}
