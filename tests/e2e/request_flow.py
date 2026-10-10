"""FLOW04's finite kiosk composition and independent open/new qualification.

The enabled target and earlier public balance are supplied by the caller.
This flow neither changes policy nor submits a request.
"""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry, overlay_entry
from request_composition import KioskRequestJourney
from private_artifacts import require


def overlay_to_kiosk(prefix, *, child, choices='qualification'):
    """FLOW12: cancel an explicitly captured overlay and read the destination untouched."""
    from journey_blocks import prefixed_stages
    require(child in ('riley', 'jordan'), 'request-transfer:child')
    require(choices in ('qualification', 'remembered'), 'request-transfer:choices')
    binding = 'transfer' if choices == 'qualification' else 'remembered'
    role = 'child' if child == 'riley' else 'standard'
    return prefixed_stages(prefix, {
        'cancel': f'ui:{binding}-overlay-{child}-cancel',
        'desktop': f'ui:{binding}-overlay-{child}-returned',
        'switch': f'system:{role}-switch-user', 'greeter': 'ui:gdm-returned',
        **station_entry(),
        'child': f'ui:{binding}-kiosk-{child}-select',
        'read': f'ui:{binding}-kiosk-{child}-read',
    })


def prepared_request(*, prefix, entry, initial, child, approver, duration_seconds, allow_soft,
                     surface='kiosk'):
    """Declare the qualified custom-duration binding with explicit entry state."""
    require(prefix in ('open', 'new'), 'request-flow:prefix')
    require(entry in ('open', 'new') and initial in ('default', 'selected'),
            'request-flow:entry')
    require(child == 'fixture-child' and approver == 'fixture-parent'
            and type(duration_seconds) is int and duration_seconds == 75
            and allow_soft is True, 'request-flow:choices')
    require(surface in ('kiosk', 'overlay'), 'request-flow:surface')
    if surface == 'overlay':
        stages = overlay_entry(prefix + '-entry', 'command', form_operation=(
            'overlay-request-form' if initial == 'default' else 'overlay-valid-fraction-soft-read')) if entry == 'new' else {}
        stages.update({
            prefix + '-form': 'ui:overlay-request-form' if initial == 'default' else 'ui:overlay-valid-fraction-soft-read',
            prefix + '-approver': 'ui:overlay-valid-approver-select' if initial == 'default' else 'ui:overlay-flow-approver-select',
            prefix + '-selections': 'ui:overlay-valid-approver-read' if initial == 'default' else 'ui:overlay-valid-fraction-soft-read',
            prefix + '-duration': 'ui:overlay-valid-custom-open',
            **{prefix + '-text-' + action: 'ui:text-overlay-fraction-' + action
               for action in ('focus', 'selected', 'read')},
            prefix + '-duration-read': 'ui:overlay-valid-fraction-read' if initial == 'default' else 'ui:overlay-valid-fraction-soft-read',
            prefix + '-apps': 'ui:overlay-valid-fraction-soft-select',
            prefix + '-estimate': 'ui:overlay-valid-fraction-soft-read',
        })
        return stages
    stages = station_entry('cancel-') if entry == 'new' else {}
    stages.update({
        prefix + '-form': 'ui:kiosk-request-form' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-child': 'ui:kiosk-child-select' if initial == 'default' else 'ui:kiosk-flow-child-select',
        prefix + '-approver': 'ui:kiosk-approver-select' if initial == 'default' else 'ui:kiosk-flow-approver-select',
        prefix + '-selections': 'ui:kiosk-enabled-form' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-duration': 'ui:kiosk-valid-custom-open',
        **{prefix + '-text-' + action: 'ui:text-kiosk-fraction-' + action
           for action in ('focus', 'selected', 'read')},
        prefix + '-duration-read': 'ui:kiosk-valid-fraction-read' if initial == 'default' else 'ui:kiosk-valid-fraction-soft-read',
        prefix + '-apps': 'ui:kiosk-valid-fraction-soft-select',
        prefix + '-estimate': 'ui:kiosk-valid-fraction-soft-read',
    })
    return stages


def daily_station_entry():
    """Save the qualified 15-minute preset, read balance and enter the station.

    Requires Parent with the fixture child selected. Request choices and exits
    remain separate so Cancel, Escape and approval share the same preparation.
    """
    return {
        'limit-enabled': 'ui:parent-toggle-enabled',
        'save-enabled': 'ui:parent-save-enabled',
        'allowance-15-select': 'ui:allowance-15-select',
        'allowance-15-read': 'ui:allowance-15-read',
        'time-explanation-read': 'ui:time-explanation-read',
        'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
        **station_entry(),
    }


def chinese_request(prefix):
    """Finite Jamie/Jordan/75-second request on an already Chinese owned form."""
    require(prefix in ('first', 'second'), 'request-flow:chinese-prefix')
    return {
        prefix + '-duration': 'ui:chinese-custom-open',
        **{prefix + '-text-' + action: 'ui:text-chinese-kiosk-fraction-' + action
           for action in ('focus', 'selected', 'read')},
        prefix + '-apps': 'ui:chinese-fraction-soft-select',
        prefix + '-choices': 'ui:chinese-fraction-soft-read',
    }


def overlay_authentication(*, result, prefix, exit='automatic'):
    """Declare Shell authentication separately from form/destination readback.

    Requires the prepared fixed overlay request. Cancel returns prompt absence;
    approval returns explicit success; rejection proves denial before Cancel.
    The caller owns preserved choices,
    automatic desktop return and activity comparisons. Renaming checkpoints
    does not qualify another request or provider tuple.
    """
    import re
    require(result in ('cancel', 'approval', 'rejection'), 'overlay-authentication:result')
    require(exit in ('automatic', 'immediate') and (result == 'approval' or exit == 'automatic'),
            'overlay-authentication:exit')
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'overlay-authentication:prefix')
    if result == 'cancel':
        return {
            prefix + '-cancel-ready': 'ui:overlay-shell-cancel-ready',
            prefix + '-dismissed': 'ui:overlay-shell-dismissed',
        }
    if result == 'rejection':
        return {
            prefix + '-open': 'ui:overlay-shell-rejection-open',
            prefix + '-qualified': 'ui:overlay-shell-rejection-qualified',
            prefix + '-rechecked': 'ui:overlay-shell-rejection-rechecked',
            prefix + '-submit-ready': 'ui:overlay-shell-rejection-submit-ready',
            prefix + '-cancel-ready': 'ui:overlay-shell-rejection-cancel-ready',
            prefix + '-dismissed': 'ui:overlay-shell-dismissed',
        }
    return {
        prefix + '-open': 'ui:overlay-shell-open',
        prefix + '-qualified': 'ui:overlay-shell-qualified',
        prefix + '-rechecked': 'ui:overlay-shell-rechecked',
        prefix + '-submit-ready': 'ui:overlay-shell-submit-ready',
        prefix + '-success': ('ui:overlay-approval-immediate' if exit == 'immediate'
                              else 'ui:overlay-approval-success'),
    }


def overlay_approved_request(*, child, approver, duration_seconds, allow_soft, exit):
    """FLOW05: fixed prepared overlay, explicit success and declared child return."""
    require(dict(child=child, approver=approver, duration_seconds=duration_seconds,
                 allow_soft=allow_soft) == CHOICES
            and type(duration_seconds) is int and allow_soft is True, 'overlay-flow:choices')
    return {**overlay_authentication(result='approval', prefix='approval', exit=exit),
            'returned': 'ui:overlay-desktop'}


def overlay_rejected_request(*, outcome, child, approver, duration_seconds, allow_soft):
    """FLOW07: one denial/Cancel and immutable readback; leave the form open."""
    overlay_approved_request(child=child, approver=approver, duration_seconds=duration_seconds,
                             allow_soft=allow_soft, exit='automatic')
    require(outcome in ('rejection', 'cancel'), 'overlay-flow:outcome')
    return {'flow-before': 'ui:overlay-valid-fraction-soft-read',
            **overlay_authentication(result=outcome, prefix='rejection' if outcome == 'rejection' else 'shell'),
            'flow-preserved': 'ui:overlay-valid-fraction-soft-read'}


CHOICES = dict(child='fixture-child', approver='fixture-parent', duration_seconds=75, allow_soft=True)
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-entry': 'ui:parent-kiosk-refused',
    'valid-wrong-entry': 'ui:parent-kiosk-valid-refused',
    **daily_station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default', **CHOICES),
    'open-cancel': 'ui:kiosk-request-cancel',
    'open-returned': 'ui:gdm-station-returned',
    **prepared_request(prefix='new', entry='new', initial='selected', **CHOICES),
    'new-cancel': 'ui:kiosk-request-cancel',
    'new-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(
    prefix='request-flow', worker_mode='request_flow', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in list(SCREENS)[list(SCREENS).index('switch-user'):]}},
    advance_after={'time-explanation-read': 'step-2'},
    request_checks={'new-estimate': ('open-estimate', 'request-flow:reproduced-choices',
                                     'reproduced_choices')},
)


class RequestFlowJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan=plan, actions=actions)
