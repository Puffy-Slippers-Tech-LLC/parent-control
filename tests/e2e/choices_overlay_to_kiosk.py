"""155a: both children's shared choices and user-local approvers, overlay to kiosk."""
from installed_journey import JourneyPlan
from journey_blocks import desktop_entry, fresh_desktop, prefixed_stages, station_entry
from request_flow import overlay_to_kiosk, transfer_allowances
from request_composition import KioskRequestJourney


SCREENS = {
    **transfer_allowances(), **prefixed_stages('seed', station_entry()),
    'seed-child': 'ui:transfer-kiosk-riley-select-default',
    'seed-approver': 'ui:transfer-kiosk-riley-approver',
    'seed-cancel': 'ui:kiosk-request-cancel', 'seed-returned': 'ui:gdm-station-returned',
}
CHALLENGES = {'initial': ('parent', 'recipient-qualified', 'recipient-rechecked')}
LOGIN_STAGES = tuple(fresh_desktop('parent'))
for prefix, child, role, entry in (('riley', 'riley', 'child', 'fresh'),
                                  ('jordan', 'jordan', 'other-child', 'fresh')):
    SCREENS.update(prefixed_stages(prefix + '-entry', desktop_entry(role, source='gdm', entry=entry)))
    login = prefixed_stages(prefix + '-entry', fresh_desktop(role))
    LOGIN_STAGES += tuple(login)
    recipient = 'child' if role == 'child' else 'standard'
    CHALLENGES[prefix + '-entry'] = (role, prefix + '-entry-' + recipient + '-recipient-qualified',
                                    prefix + '-entry-' + recipient + '-recipient-rechecked')
    SCREENS[prefix + '-launch'] = f'ui:transfer-overlay-{child}-launch'
    SCREENS.update({prefix + '-' + action: f'ui:transfer-overlay-{child}-{action}'
                    for action in ('default', 'refused', 'approver', 'custom', 'text', 'apps')})
    SCREENS[prefix + '-source'] = f'ui:transfer-overlay-{child}-read'
    SCREENS.update(overlay_to_kiosk(prefix + '-transfer', child=child))
    if prefix == 'riley':
        SCREENS.update({prefix + '-exit': 'ui:kiosk-request-cancel',
                        prefix + '-greeter': 'ui:gdm-station-returned'})
for child in ('riley', 'jordan'):
    SCREENS.update({child + '-revisit-select': f'ui:transfer-kiosk-{child}-select',
                    child + '-revisit-read': f'ui:transfer-kiosk-{child}-read'})

COMPARISONS = {**{child + '-transfer-read': child + '-source' for child in ('riley', 'jordan')},
               **{child + '-revisit-read': child + '-source' for child in ('riley', 'jordan')}}

PLAN = JourneyPlan(
    prefix='choices-overlay-to-kiosk', worker_mode='choices_overlay_to_kiosk', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup', 'installed-greeter': 'start',
            **{stage: 'step-1' for stage in SCREENS}},
    invocations=tuple(stage for stage in SCREENS if stage in LOGIN_STAGES), challenges=CHALLENGES,
    child_bindings={'riley-allowance': 'child', 'jordan-allowance': 'existing'},
    balance_checks={'riley-allowance': 1800, 'jordan-allowance': 1800},
    request_transfer_checks=COMPARISONS,
    assertions_after={stage: stage[:-5] + '-shared-choices-local-approver'
                      for stage in COMPARISONS},
)


class ChoicesOverlayToKioskJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
