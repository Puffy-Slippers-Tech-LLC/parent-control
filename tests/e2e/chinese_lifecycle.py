"""Case 254: current installation, one reboot and two Chinese kiosk approvals."""
from chinese_current_install import current_actions
from chinese_journey import chinese_journey
from chinese_kiosk_lifecycle import renewed_desktop
from installed_journey import JourneyPlan, record_installed_journey
from journey_blocks import product_free_desktop, station_entry, prefixed_stages
from journey_checks import checked_language, policy_projection, approval_estimate, public_checks
from kiosk_approved_flow import chinese_approval
from request_flow import chinese_request
from accessible_ui import MATCH_APP


CHILD = renewed_desktop('language-', 'other-child', product_free=True)
CHILD['language-desktop'] = 'ui:chinese-standard-desktop'
ADMIN = renewed_desktop('install-', 'parent', product_free=True)
RETURN = renewed_desktop('return-', 'parent')
SETUP = renewed_desktop('setup-', 'parent')
FIRST = renewed_desktop('first-policy-', 'parent')
SECOND = renewed_desktop('second-policy-', 'parent')
MANAGEMENT = {
    'parent-command': 'ui:parent-command-launch', 'parent-window': 'ui:parent-window',
    'child-picker-opened': 'ui:existing-child-picker-opened',
    'child-choice-highlighted': 'ui:existing-child-choice-highlighted',
    'parent-selected': 'ui:discovery-ready',
}
INSTALL = {
    **product_free_desktop(),
    'language-setting': 'system:parent-command-context',
    'language-parent-logout': 'system:parent-logout', **CHILD,
    'language-child-logout': 'system:standard-logout', **ADMIN,
    'install-ready': 'system:parent-command-context',
    'package-submitted': 'system:parent-command-context',
    'package-result': 'system:parent-command-context',
    'package-reread': 'system:parent-command-context',
    'install-switch': 'system:parent-switch-user', **station_entry('initial-'),
    'initial-notice': 'ui:kiosk-initial-notice',
    'initial-notice-close': 'ui:kiosk-initial-notice-close',
    'initial-notice-return': 'ui:kiosk-initial-notice-return', **RETURN,
}
PRESENTATION = {
    'reboot-requested': 'system:parent-command-context', 'reboot-greeter': 'ui:gdm-list',
    **station_entry('renewed-'),
    'initial-language': 'ui:kiosk-initial-language',
    'initial-language-cancel': 'ui:kiosk-initial-language-cancel',
    'initial-form': 'ui:kiosk-initial-form',
    'setup-cancel': 'ui:kiosk-request-cancel', 'setup-returned': 'ui:gdm-station-returned',
    **SETUP, **prefixed_stages('setup-manage', MANAGEMENT),
    'other-enabled': 'ui:multiple-other-enable', 'other-saved': 'ui:multiple-other-saved',
    'policy-before': 'ui:kiosk-language-policy',
    'setup-logout': 'system:parent-logout', **station_entry(),
    'other-first-parent': 'ui:kiosk-language-jordan-jamie-chinese',
    'first-language': 'ui:chinese-language-save',
    'first-checked': 'ui:kiosk-language-open', 'first-close': 'ui:kiosk-language-cancel',
}
APPROVALS = {
    **chinese_request('first'), **chinese_approval('first'),
    'first-returned': 'ui:gdm-station-returned',
    **FIRST, **prefixed_stages('first-manage', MANAGEMENT),
    'first-policy': 'ui:kiosk-language-policy', 'first-logout': 'system:parent-logout',
    **station_entry('cancel-'),
    'second-language': 'ui:chinese-persisted-form',
    'second-checked': 'ui:kiosk-language-open', 'second-close': 'ui:kiosk-language-cancel',
    **chinese_request('second'), **chinese_approval('second'),
    'second-returned': 'ui:gdm-station-returned',
    **SECOND, **prefixed_stages('second-manage', MANAGEMENT),
    'second-policy': 'ui:kiosk-language-policy',
}
ASSERTIONS = {
    'command-context': 'chinese-assets-verified', 'language-setting': 'chinese-account-confirmed',
    'language-desktop': 'renewed-chinese-desktop',
    'package-result': 'latest-install-version-notice-same-boot',
    'package-reread': 'independent-install-reread',
    'initial-notice': 'first-chinese-restart-notice', 'reboot-greeter': 'changed-boot-greeter',
    'initial-language': 'first-chinese-chooser-and-default', 'initial-form': 'initial-chinese-form',
    'policy-before': 'ordinary-zero-policy', 'first-checked': 'saved-checked-chinese',
    **{prefix + suffix: prefix + assertion for prefix in ('first', 'second') for suffix, assertion in
       (('-choices', '-declared-request'), ('-approval-open', '-native-chinese-prompt'),
        ('-approval-rechecked', '-same-challenge'), ('-approval-success', '-real-approval'),
        ('-returned', '-usable-gdm-return'), ('-policy', '-public-time-and-policy'))},
    'second-language': 'persisted-chinese-form', 'second-checked': 'persisted-checked-chinese',
}
PLAN = JourneyPlan(prefix='chinese-lifecycle', worker_mode='chinese_lifecycle',
    screen_tags={**INSTALL, **PRESENTATION, **APPROVALS},
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in INSTALL}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in PRESENTATION},
            **{stage: 'step-3' for stage in APPROVALS}},
    invocations=(*CHILD, *ADMIN, *RETURN, *SETUP, *FIRST, *SECOND),
    challenges={
        'chinese-child': ('other-child', 'language-standard-recipient-qualified', 'language-standard-recipient-rechecked'),
        'install-parent': ('parent', 'install-recipient-qualified', 'install-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked'),
        **{prefix + '-parent': ('parent', prefix + '-recipient-qualified', prefix + '-recipient-rechecked')
           for prefix in ('setup', 'first-policy', 'second-policy')}},
    reboot_transition=('reboot-requested', 'reboot-greeter'),
    stage_actions={'command-context': 'native-verify', 'language-setting': 'language-setting',
                   'install-ready': 'renewed-entry', 'package-submitted': 'install-package'},
    assertions_after=ASSERTIONS)

CHOOSER = {'initial': False, 'checked': 'zh-hans',
    'choices': {'en': 'English', 'de': 'Deutsch', 'zh-Hans': '中文（简体）', 'he': 'עברית'},
    'heading': '选择语言', 'save': '保存', 'save_label': '保存', 'save_description': '保存语言偏好设置。'}
SETTINGS = {'child': 'existing-fixture-child', 'limit_enabled': True, 'allowance': ['0 minutes']}
CHECKS = {
    'first-checked': checked_language(CHOOSER), 'second-checked': checked_language(CHOOSER),
    'policy-before': policy_projection(SETTINGS, row=(MATCH_APP, 'allowed'),
                                       capture='policy', grant='zero'),
    **{prefix + '-choices': approval_estimate(capture=prefix + '-estimate') for prefix in ('first', 'second')},
    **{prefix + '-policy': public_checks(
        policy_projection(SETTINGS, row=(MATCH_APP, 'allowed'), same='policy', grant='positive'),
        approval_estimate(same=prefix + '-estimate')) for prefix in ('first', 'second')},
}


def execute(recorder, context):
    record_installed_journey(recorder, context, PLAN, timeout=3600,
        actions=current_actions(include_refusal=False), journey_type=chinese_journey(checks=CHECKS))


E2E_CASES = {'latest-install': execute}
