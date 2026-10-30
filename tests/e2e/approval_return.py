"""FLOW20: explicit overlay choices, approval and the same child's usable work."""
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, native_activity_entry
from native_fixtures import fixture_actions
from request_flow import approval_and_return
from request_composition import KioskRequestJourney
from private_artifacts import require
from countdown import CountdownObservation


def qualification_plan(*, entry, child, approver, seconds, soft):
    role = 'child' if child == 'fixture-child' else 'other-child'
    choices = dict(child=child, approver=approver, duration_seconds=seconds, allow_soft=soft)
    flow = approval_and_return(prefix=entry, entry=entry, **choices)
    parent = parent_management()
    if role == 'other-child':
        parent.update({'child-picker-opened': 'ui:existing-child-picker-opened',
                       'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
                       'parent-selected': 'ui:discovery-ready'})
    child_entry = {'fresh-' + stage: operation for stage, operation in fresh_desktop(role).items()}
    # The activity adapter uses the declared child even for the second account.
    activity = native_activity_entry('activity')
    screens = {
        **fresh_desktop('parent'), **parent,
        'allowance-configured': 'ui:time-explanation-setup-thirty-read',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned', **child_entry, **activity,
        'before-countdown': 'ui:child-countdown-present',
        **({'independent-launch': 'ui:child-command-launch'} if entry == 'open' else {}),
        **flow, 'activity-returned': 'ui:overlay-native-activity',
        'activity-close': 'ui:overlay-native-close', 'activity-closed': 'ui:overlay-native-closed',
    }
    recipient = 'child' if role == 'child' else 'standard'
    return JourneyPlan(
        prefix='overlay-approval-return', worker_mode='approval_return_' + entry,
        screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        invocations=(*fresh_desktop('parent'), *child_entry),
        challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                    'child-login': (role, 'fresh-' + recipient + '-recipient-qualified',
                                   'fresh-' + recipient + '-recipient-rechecked')},
        stage_actions={'desktop': 'native-verify'},
        child_bindings={'allowance-configured': 'child' if role == 'child' else 'existing'},
        balance_checks={'allowance-configured': 1800},
        countdown_checks={'countdown': (entry + '-estimate', 'estimate', 1, 180)},
        activity_checks={'activity-returned': ('activity-capture', 'same')},
        overlay_request=(role, 'parent' if approver == 'fixture-parent' else 'other-parent', seconds, soft),
        assertions_after={'approval-success': 'explicit-child-owned-approval',
                          'returned': 'same-child-desktop-return',
                          'countdown': 'elapsed-public-balance-increment',
                          'activity-returned': 'same-usable-original-work'},
    )


NEW_PLAN = qualification_plan(entry='new', child='fixture-child', approver='fixture-parent', seconds=30, soft=False)
OPEN_PLAN = qualification_plan(entry='open', child='existing-fixture-child', approver='other-fixture-parent', seconds=75, soft=True)


class ApprovalReturnJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=NEW_PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions(include_refusal=False) if actions is None else actions)

    def check_settings(self, stage, observed):
        value = observed.get('ui', {})
        if 'valid_choice' in value:
            expected = self.plan.overlay_request[0]
            require(value['valid_choice']['request']['child'] == (
                'fixture-child' if expected == 'child' else 'existing-fixture-child'),
                'overlay-return:wrong-child-balance')
            require(self.balance is not None and self.balance['child'] ==
                    value['valid_choice']['request']['child'], 'overlay-return:wrong-child-balance')
        super().check_settings(stage, observed)
        if stage == 'before-countdown':
            self.before_countdown = CountdownObservation.from_value(value['countdown'], present=True,
                child='fixture-child' if self.plan.overlay_request[0] == 'child' else 'existing-fixture-child')
        if stage == 'countdown':
            before = self.before_countdown
            current = self.countdowns[stage]
            elapsed = (current.observed_monotonic_ns - before.observed_monotonic_ns) / 1e9
            require(0 < elapsed <= 180 and abs(current.seconds - (
                before.seconds + self.plan.overlay_request[2] - elapsed)) <= 2,
                'overlay-return:public-increment')
            observed.setdefault('comparison', {})['exact_public_increment'] = True
