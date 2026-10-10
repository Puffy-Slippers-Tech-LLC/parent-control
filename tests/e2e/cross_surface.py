"""155: kiosk-to-overlay choices for both children, with no approval."""
from installed_journey import JourneyPlan
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages, station_entry
from request_flow import kiosk_to_overlay, transfer_allowances


SCREENS = transfer_allowances()
CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')}
LOGIN_STAGES = tuple(fresh_desktop('parent'))
for child, role in (('riley', 'child'), ('jordan', 'other-child')):
    prefix = child + '-seed'
    SCREENS.update(prefixed_stages(prefix + '-entry', desktop_entry(role, source='gdm', entry='fresh')))
    LOGIN_STAGES += tuple(prefixed_stages(prefix + '-entry', fresh_desktop(role)))
    recipient = 'child' if role == 'child' else 'standard'
    CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                    prefix + '-entry-' + recipient + '-recipient-rechecked')
    SCREENS.update({prefix + '-' + action: f'ui:transfer-overlay-{child}-{action}'
                    for action in ('launch', 'default', 'refused')})
    SCREENS[prefix + '-wrong-child'] = f'ui:reverse-overlay-{child}-wrong-child'
    SCREENS.update({prefix + '-' + action: f'ui:transfer-overlay-{child}-{action}'
                    for action in ('approver', 'cancel', 'returned')})
    SCREENS[prefix + '-logout'] = f'system:{recipient}-logout'
    SCREENS[prefix + '-greeter'] = 'ui:gdm-returned'
SCREENS.update(prefixed_stages('station', station_entry()))
for child, role in (('riley', 'child'), ('jordan', 'other-child')):
    SCREENS[child + '-select'] = f'ui:transfer-kiosk-{child}-select-default'
    SCREENS[child + '-approver'] = f'ui:transfer-kiosk-{child}-approver'
    SCREENS.update({child + '-' + action: f'ui:reverse-kiosk-{child}-{action}'
                    for action in ('custom', 'text', 'apps')})
    SCREENS[child + '-source'] = f'ui:reverse-kiosk-{child}-read'
    prefix = child + '-transfer'
    SCREENS.update(kiosk_to_overlay(prefix, child=child, entry='fresh'))
    LOGIN_STAGES += tuple(prefixed_stages(prefix + '-entry', fresh_desktop(role)))
    recipient = 'child' if role == 'child' else 'standard'
    CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                    prefix + '-entry-' + recipient + '-recipient-rechecked')
    if child == 'riley':
        SCREENS.update({child + '-exit': 'ui:transfer-overlay-riley-cancel',
                        child + '-desktop': 'ui:transfer-overlay-riley-returned',
                        child + '-switch': 'system:child-switch-user',
                        child + '-greeter': 'ui:gdm-returned'})
        SCREENS.update(prefixed_stages('next-station', station_entry()))

COMPARISONS = {child + '-transfer-read': child + '-source' for child in ('riley', 'jordan')}
PLAN = JourneyPlan(
    prefix='cross-surface', worker_mode='cross_surface', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES), challenges=CHALLENGES,
    child_bindings={'riley-allowance': 'child', 'jordan-allowance': 'existing'},
    balance_checks={'riley-allowance': 1800, 'jordan-allowance': 1800},
    request_transfer_checks=COMPARISONS,
    assertions_after={stage: stage[:-5] + '-shared-choices-local-approver' for stage in COMPARISONS},
)
