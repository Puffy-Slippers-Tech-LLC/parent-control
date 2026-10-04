"""Finite Chinese first-presentation history; no preference save or approval."""
import copy
from dataclasses import replace

from account_language import AccountLanguage, ROLE, LOCALE
from installed_journey import InstalledJourney
from journey_blocks import fresh_desktop, station_entry
from native_fixtures import fixture_actions
from package_command import PackageCommand
from package_upgrade import PLAN as UPGRADE_PLAN, PackageUpgradeJourney, upgrade_actions
from private_artifacts import require


def renewed_desktop(prefix, role):
    return {prefix + stage: tag for stage, tag in fresh_desktop(role).items()}


CHILD = renewed_desktop('language-', 'other-child')
CHILD['language-desktop'] = 'ui:chinese-standard-desktop'
ADMIN = renewed_desktop('upgrade-', 'parent')
RETURN = renewed_desktop('return-', 'parent')
tags = dict(UPGRADE_PLAN.screen_tags)
for stage in ('upgrade-submitted', 'upgrade-result', 'upgrade-reread'):
    del tags[stage]
tags.update({
    'language-setting': 'system:parent-command-context',
    'language-parent-logout': 'system:parent-logout', **CHILD,
    'language-child-logout': 'system:standard-logout', **ADMIN,
    'upgrade-ready': 'system:parent-command-context',
    **{stage: UPGRADE_PLAN.screen_tags[stage] for stage in
       ('upgrade-submitted', 'upgrade-result', 'upgrade-reread')},
    'upgrade-switch': 'system:parent-switch-user', **station_entry('initial-'),
    'initial-notice': 'ui:kiosk-initial-notice',
    'initial-notice-close': 'ui:kiosk-initial-notice-close',
    'initial-notice-return': 'ui:kiosk-initial-notice-return', **RETURN,
    'second-reboot-requested': 'system:parent-command-context',
    'second-reboot-greeter': 'ui:gdm-list', **station_entry('renewed-'),
    'initial-language': 'ui:kiosk-initial-language',
    'initial-language-cancel': 'ui:kiosk-initial-language-cancel',
    'initial-form': 'ui:kiosk-initial-form',
})
PLAN = replace(UPGRADE_PLAN, prefix='chinese-kiosk', worker_mode='chinese_kiosk_lifecycle',
    screen_tags=tags,
    phases={**UPGRADE_PLAN.phases, **{stage: 'step-5' for stage in tags
              if stage not in UPGRADE_PLAN.phases}},
    invocations=(*UPGRADE_PLAN.invocations, *CHILD, *ADMIN, *RETURN),
    challenges={**UPGRADE_PLAN.challenges,
        'chinese-child': ('other-child', 'language-standard-recipient-qualified', 'language-standard-recipient-rechecked'),
        'upgrade-parent': ('parent', 'upgrade-recipient-qualified', 'upgrade-recipient-rechecked'),
        'return-parent': ('parent', 'return-recipient-qualified', 'return-recipient-rechecked')},
    additional_reboot_transitions=(('second-reboot-requested', 'second-reboot-greeter'),),
    stage_actions={**UPGRADE_PLAN.stage_actions,
        'command-context': 'native-verify', 'language-setting': 'language-setting',
        'upgrade-ready': 'language-upgrade-entry'},
    assertions_after={**UPGRADE_PLAN.assertions_after,
        'language-setting': 'chinese-account-confirmed', 'language-desktop': 'renewed-chinese-desktop',
        'initial-notice': 'first-chinese-restart-notice',
        'second-reboot-greeter': 'second-changed-boot-greeter',
        'initial-language': 'first-chinese-chooser-and-default', 'initial-form': 'initial-chinese-form'})

# Literal independent customer expectations, not runtime catalogue lookups.
NOTICE = {'update-required-message': '请重启计算机，以使 Oh No! Parent Control 正常工作。',
          'update-required-close': '关闭', 'update-required-reboot': '立即重启'}
FORM = {'kiosk-child-account-caption': '孩子',
        'kiosk-approver-account-caption': '批准人',
        'kiosk-duration-label-1800': '30 分钟', 'kiosk-request-submit': '提交请求',
        'kiosk-request-cancel': '取消'}
CHOOSER = {'language-title': '选择语言', 'language-continue': '保存', 'language-cancel': '取消'}


def set_account_language(journey, guard):
    guard()
    require(journey.activated_entry is not None, 'chinese-kiosk:activation-required')
    require(not hasattr(journey, 'account_language'), 'chinese-kiosk:setting-replay')
    controller = journey.account_language = AccountLanguage(
        journey.transport, journey.context.verified, product_free=False)
    before = controller.read()
    require(controller.command('reject-inputs') == {
        'wrong_account_refused': True, 'undeclared_locale_refused': True}, 'chinese-kiosk:setting-refusals')
    require(controller.read() == before, 'chinese-kiosk:refusal-preservation')
    controller.submit(ROLE, LOCALE, controller.identity)
    guard()
    result = controller.confirm(before)
    journey.language_confirmation = copy.deepcopy(result)
    journey.language_uid = before['target_uid']
    guard()
    return result


def language_upgrade_entry(journey, guard):
    """Rebind the renewed admin session with only the declared language change."""
    require(journey.language_confirmation is not None and journey.chinese_desktop is not None,
            'chinese-kiosk:renewal-required')
    guard()
    command = PackageCommand(journey.transport, journey.context.verified)
    first, second = command.read_identity(), command.read_identity()
    require(first == second, 'chinese-kiosk:unstable-entry')
    expected = copy.deepcopy(journey.activated_entry)
    # AccountsService strips the encoding during SetLanguage; GNOME login can
    # restore it. Both independent boundaries must still name only DESK13's
    # declared Chinese locale. Preserve the actual renewed API representation
    # for the later package-upgrade comparison, with every other field exact.
    renewed_language = first['preserved']['accounts'][journey.language_uid]['language']
    require(journey.language_confirmation['confirmed_language'] in (LOCALE, 'zh_CN')
            and renewed_language in (LOCALE, 'zh_CN'), 'chinese-kiosk:renewed-language')
    expected['preserved']['accounts'][journey.language_uid]['language'] = renewed_language
    # The supported logout/login deliberately replaces only the bound admin
    # session. read_identity independently requires its active fixture owner.
    expected['session'] = first['session']
    require(first == expected and first['boot'] == journey.boot, 'chinese-kiosk:renewal-preservation')
    journey.activated_entry = copy.deepcopy(first)
    guard()
    return {'independent_readback': True, 'renewed_session': True, 'preservation_verified': True}


def lifecycle_actions():
    return {**upgrade_actions(), **fixture_actions(profile='chinese', include_refusal=False),
            'language-setting': set_account_language, 'language-upgrade-entry': language_upgrade_entry}


class ChineseKioskJourney(PackageUpgradeJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=lifecycle_actions() if actions is None else actions)
        self.language_confirmation = self.chinese_desktop = None
        self.language_uid = None
        self.initial_captures = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage)
        if operation == 'ui:chinese-standard-desktop':
            require(self.language_confirmation is not None and self.chinese_desktop is None,
                    'chinese-kiosk:desktop-entry')
            provider = observed['ui']['provider']
            require(provider['locale'] in ('zh_CN.UTF-8', 'zh_CN.utf8', 'zh_CN'),
                    'chinese-kiosk:desktop-language')
            self.chinese_desktop = copy.deepcopy(provider)
        if operation not in ('ui:kiosk-initial-notice', 'ui:kiosk-initial-notice-close',
                             'ui:kiosk-initial-language', 'ui:kiosk-initial-language-cancel',
                             'ui:kiosk-initial-form'):
            return
        require(operation not in self.initial_captures, 'chinese-kiosk:capture-replay')
        value = observed['ui']['initial']
        require(value['child'] == 'other-fixture-child' and value['input_free'] is True,
                'chinese-kiosk:initial-child')
        expected = NOTICE if value['kind'] == 'notice' else {**FORM, **(CHOOSER if value['kind'] == 'language' else {})}
        require(value['texts'] == expected and value['default_chinese'] is
                (True if value['kind'] == 'language' else None), 'chinese-kiosk:initial-language')
        previous = {'ui:kiosk-initial-notice-close': 'ui:kiosk-initial-notice',
                    'ui:kiosk-initial-language-cancel': 'ui:kiosk-initial-language'}.get(operation)
        if previous:
            require(previous in self.initial_captures and value == self.initial_captures[previous],
                    'chinese-kiosk:missing-or-changed-capture')
        if operation == 'ui:kiosk-initial-form':
            require('ui:kiosk-initial-language-cancel' in self.initial_captures and
                    value['texts'] == {key: self.initial_captures['ui:kiosk-initial-language']['texts'][key]
                                       for key in FORM}, 'chinese-kiosk:initial-form-preservation')
        self.initial_captures[operation] = copy.deepcopy(value)
