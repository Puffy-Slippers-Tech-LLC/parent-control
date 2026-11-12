"""289c: Jordan saves changing homework and recovers it after natural lock."""
from accessible_ui import KIOSK_BOUND_OPERATIONS, NAMED_CHILD_OPERATIONS
from game_expiry import GameExpiryJourney
from installed_journey import JourneyPlan
from journey_blocks import desktop_entry, fresh_desktop, parent_management, prefixed_stages
from kiosk_approved_flow import obtain_time
from native_fixtures import fixture_actions
from private_artifacts import require
from request_flow import approval_and_return
from synthetic_files import work_document_actions
from ui_observations import SettingsObservation


FIRST, SECOND = 'homework cycle 1', 'work again cycle 1'
SCREENS = {**fresh_desktop('parent'), **parent_management(child='existing'),
    'profile-before': 'ui:revoke-balances', 'parent-switch': 'system:parent-switch-user',
    'parent-gdm': 'ui:gdm-returned'}
LOGINS, CHALLENGES, TEXTS = {}, {
    'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked')}, {}


def entry(prefix, account, retained=False):
    screens = prefixed_stages(prefix, desktop_entry(account, source='gdm',
        entry='retained' if retained else 'fresh'))
    LOGINS.update(screens)
    role = 'recipient' if account == 'parent' else 'standard-recipient'
    CHALLENGES[prefix] = (account, prefix + '-' + role + '-qualified',
                         prefix + '-' + role + '-rechecked')
    return screens


def work(prefix, actions, text, submitted='No submitted draft'):
    screens = {prefix + '-' + action: 'ui:work-jordan-' +
               ('activity' if action == 'capture' else action) for action in actions}
    TEXTS.update({stage: (text, submitted) for stage in screens})
    return screens


SCREENS.update({**entry('work-entry', 'other-child'),
    **work('first', ('open', 'opened', 'edit', 'save', 'saved', 'submit', 'submitted', 'capture'), FIRST),
    **work('second', ('edit', 'save', 'saved', 'submit', 'submitted', 'capture'), SECOND, FIRST),
    **work('second', ('close', 'closed'), SECOND),
    **work('reopen', ('open', 'opened', 'submit', 'submitted', 'capture'), SECOND),
    'work-switch': 'system:standard-switch-user', 'work-gdm': 'ui:gdm-returned',
    **entry('profile-parent', 'parent', True),
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'saved-settings': 'ui:existing-returned', 'profile-switch': 'system:parent-switch-user',
    'profile-gdm': 'ui:gdm-returned'})
CHOICES = dict(child='existing-fixture-child', approver='fixture-parent',
               duration_seconds=600, allow_soft=True)
REQUEST = prefixed_stages('request', obtain_time(initial='observed', **CHOICES, exit='automatic'))
SCREENS.update({**REQUEST, **entry('jordan-entry', 'other-child', True),
    'initial-countdown': 'ui:child-countdown-present',
    **work('before-expiry', ('capture',), SECOND),
    'natural-expiry': 'ui:work-jordan-activity',
    'lock-input-ready': 'ui:child-natural-expiry-lock-ready',
    'lock-result': 'ui:child-natural-expiry-lock-result',
    'curtain': 'ui:child-lock-curtain', 'reveal-ready': 'ui:child-lock-reveal-ready',
    'time-denied': 'ui:child-lock-time-denied',
    'return-greeter': 'system:standard-return-greeter', 'denied-returned': 'ui:gdm-returned'})
RECOVERY = prefixed_stages('recovery', approval_and_return(prefix='new', entry='new',
    **{**CHOICES, 'duration_seconds': 1200}, surface='kiosk', child_entry='retained'))
SCREENS.update({**RECOVERY,
    **work('recovered', ('capture', 'resubmit', 'submitted'), SECOND),
    **work('final', ('capture', 'close', 'closed'), SECOND), 'cleanup': 'system:standard-desktop-identity'})
TEXTS['natural-expiry'] = (SECOND, SECOND)
LOGINS.update(prefixed_stages('recovery-retained', desktop_entry(
    'other-child', source='gdm', entry='retained')))
CHALLENGES['recovery-retained'] = ('other-child', 'recovery-retained-standard-recipient-qualified',
                                  'recovery-retained-standard-recipient-rechecked')
PLAN = JourneyPlan(
    prefix='repeated-saved-work', worker_mode='repeated_saved_work', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify', 'parent-switch': 'work-prepare',
                   'first-saved': 'first-saved-bytes', 'second-saved': 'second-saved-bytes',
                   'natural-expiry': 'natural-expiry', 'cleanup': 'work-cleanup'},
    work_texts=TEXTS,
    child_bindings={stage: 'existing' for stage, tag in SCREENS.items()
                    if tag.removeprefix('ui:') in NAMED_CHILD_OPERATIONS},
    settings_checks={'parent-selected': SettingsObservation('existing-fixture-child', False, ('0 minutes',)),
                     'saved-settings': SettingsObservation('existing-fixture-child', True, ('0 minutes',))},
    balance_checks={'allowance-configured': 0},
    countdown_checks={'initial-countdown': ('request-new-estimate', 600, 1, 300),
                      'recovery-countdown': ('recovery-new-estimate', 1200, 1, 300)},
    kiosk_request=('other-child', 'parent', 600, True),
    kiosk_requests={stage: ('other-child', 'parent', 1200, True)
                    for stage, tag in RECOVERY.items() if tag.removeprefix('ui:') in KIOSK_BOUND_OPERATIONS},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
        or stage in LOGINS and not stage.endswith('entry-guard')
        or stage in ('initial-countdown', 'natural-expiry', 'lock-input-ready', 'lock-result')),
    challenges=CHALLENGES,
    activity_entries={'jordan-entry-entry-guard': 'reopen-capture',
                      'natural-expiry': 'before-expiry-capture',
                      'recovery-retained-entry-guard': 'before-expiry-capture'},
    activity_checks={'reopen-capture': ('second-capture', 'replaced'),
                     'before-expiry-capture': ('reopen-capture', 'same'),
                     'natural-expiry': ('before-expiry-capture', 'same'),
                     'recovered-capture': ('before-expiry-capture', 'same'),
                     'final-capture': ('recovered-capture', 'same')},
)


class RepeatedSavedWorkJourney(GameExpiryJourney):
    def __init__(self, context, progress):
        work_actions = work_document_actions(saves={
            'first-saved-bytes': ('jordan', FIRST), 'second-saved-bytes': ('jordan', SECOND)})
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **work_actions, 'natural-expiry': self.natural_expiry})

    def check_estimate(self, observed):
        choice = observed.get('ui', {}).get('valid_choice')
        if choice is None or choice['request']['duration_seconds'] != 1200:
            return super().check_estimate(observed)
        require(self.natural_expiry_result is not None
                and choice['request']['child'] == 'existing-fixture-child'
                and choice['estimate']['kind'] == 'fixed' and choice['estimate']['seconds'] == 1200,
                'repeated-saved-work:replacement-estimate')
        observed.setdefault('comparison', {})['replacement_time_after_natural_expiry'] = True

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage == 'time-denied':
            require(self.natural_expiry_result is not None
                    and observed['ui']['lock']['surface_id'] ==
                        self.natural_expiry_result['lock']['surface_id'],
                    'repeated-saved-work:changed-expired-lock')

    def check_activity(self, stage, observed):
        super().check_activity(stage, observed)
        if stage == 'second-capture':
            first, second = (self.activity_observations[key] for key in ('first-capture', 'second-capture'))
            require((first.binding, first.pid, first.endpoint, first.owner) ==
                    (second.binding, second.pid, second.endpoint, second.owner)
                    and first.state[:2] == (FIRST, FIRST) and second.state[:2] == (SECOND, SECOND),
                    'repeated-saved-work:original-edited-window')
            observed['comparison'] = {'original_window_with_new_saved_work': True, 'outcome': 'passed'}
