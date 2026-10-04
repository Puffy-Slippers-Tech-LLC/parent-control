"""Two fresh installed kiosk approvals; no upgrade or complete-case credit."""
from copy import deepcopy

from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, parent_management, station_entry
from kiosk_approved_flow import chinese_approval
from native_fixtures import fixture_actions
from private_artifacts import require
from request_flow import chinese_request

FORM = {'kiosk-child-account-caption': '孩子', 'kiosk-approver-account-caption': '批准人',
        'kiosk-duration-label-1800': '30 分钟', 'kiosk-request-submit': '提交请求',
        'kiosk-request-cancel': '取消'}

SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'chinese-assets': 'ui:parent-selected', 'wrong-entry': 'ui:parent-mate-refused',
    'existing-child-picker-opened': 'ui:existing-child-picker-opened',
    'existing-child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'existing-returned': 'ui:discovery-ready',
    'other-enabled': 'ui:multiple-other-enable', 'other-saved': 'ui:multiple-other-saved',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    'other-first-parent': 'ui:multiple-other-first-parent',
    'first-language': 'ui:chinese-language-save',
    **chinese_request('first'), **chinese_approval('first'),
    'first-returned': 'ui:gdm-station-returned',
    **station_entry('cancel-'),
    'second-language': 'ui:chinese-persisted-form',
    **chinese_request('second'), **chinese_approval('second'),
    'second-returned': 'ui:gdm-station-returned',
}
PLAN = JourneyPlan(prefix='chinese-native-auth', worker_mode='chinese_native_auth', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'chinese-assets': 'native-verify'},
    assertions_after={'chinese-assets': 'chinese-assets-verified', 'wrong-entry': 'wrong-entry-refused',
        **{prefix + suffix: prefix + assertion for prefix in ('first', 'second') for suffix, assertion in
           (('-language', '-chinese-form'), ('-choices', '-declared-request'),
            ('-approval-open', '-native-chinese-prompt'), ('-approval-rechecked', '-same-challenge'),
            ('-approval-success', '-real-approval'), ('-returned', '-usable-gdm-return'))}})


class ChineseNativeAuthJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=fixture_actions(
            profile='chinese', include_refusal=False) if actions is None else actions)
        self.native_challenges = {}
        self.request_choices = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage)
        value = observed.get('ui', {})
        if operation in ('ui:chinese-language-save', 'ui:chinese-persisted-form'):
            require(value['initial'] == {'kind': 'form', 'child': 'other-fixture-child',
                'texts': FORM, 'default_chinese': None, 'input_free': True}, 'chinese-auth:form-language')
        if operation == 'ui:chinese-fraction-soft-read':
            request = value['valid_choice']['request']
            require(request['child'] == 'existing-fixture-child' and request['approver'] == 'fixture-parent'
                    and request['duration_seconds'] == 75 and request['custom_text'] == '1.25'
                    and request['allow_soft'] is True, 'chinese-auth:choices')
            if self.request_choices is None:
                self.request_choices = deepcopy(request)
            else:
                require(request == self.request_choices, 'chinese-auth:reproduced-choices')
        if operation == 'ui:chinese-mate-open':
            require(stage not in self.native_challenges, 'chinese-auth:challenge-replay')
            approval = value['approval']
            require(approval['challenge_id'] not in {item['challenge_id'] for item in self.native_challenges.values()},
                    'chinese-auth:fresh-challenge')
            require(approval['agent_id'] not in {item['agent_id'] for item in self.native_challenges.values()},
                    'chinese-auth:fresh-agent')
            self.native_challenges[stage] = deepcopy(approval)
        if operation in ('ui:chinese-mate-qualified', 'ui:chinese-mate-rechecked'):
            entry = stage.rsplit('-', 1)[0] + '-open'
            require(entry in self.native_challenges and value['approval'] == {
                **self.native_challenges[entry], 'rejected_proofs': []}, 'chinese-auth:same-challenge')
