"""Guarded controller for public UI operations, with sanitized evidence."""

import json
import sys
from dataclasses import dataclass

import accessible_ui
import watch_activity
from private_artifacts import require
import system_runner as system


# Collection replies need room for their full bounded semantic projection.
# App rows still validate at most 256 fixed-format ID/access/match triples.
RESPONSE_BYTE_LIMITS = {
    'kiosk-approver-baseline': 65536,
    'parent-app-rows': 32768,
    'parent-app-rows-reopened': 32768,
}


# Fixed public descriptions only; never forward account labels, query text or
# credentials from the observed desktop. New operations must declare prose here.
OPERATION_LABELS = {
    'parent-mate-refused': 'Refusing kiosk authentication entry from Parent management',
    **{operation: 'Qualifying MATE request context, guarded Cancel and unchanged form return'
       for operation in accessible_ui.MATE_OPERATIONS},
    'parent-kiosk-valid-refused': 'Refusing kiosk duration input from Parent management',
    'parent-kiosk-invalid-refused': 'Refusing kiosk Request input from Parent management',
    **{operation: 'Checking invalid kiosk duration: ' + binding + ' / ' + action
       for operation, (binding, action) in accessible_ui.KIOSK_INVALID_OPERATIONS.items()},
    **{operation: 'Choosing and independently reading valid kiosk duration and app access'
       for operation in accessible_ui.KIOSK_VALID_OPERATIONS},
    **{operation: 'Reading idle Revoke availability and zero remaining balances'
       for operation in accessible_ui.REVOKE_DISABLED_OPERATIONS},
    **{operation: 'Qualifying saved time controls and non-collapsing balance reads'
       for operation in accessible_ui.TIME_EXPLANATION_OPERATIONS},
    **{operation: 'Qualifying custom daily allowance commits and saved readback'
       for operation in accessible_ui.CUSTOM_ALLOWANCE_OPERATIONS},
    **{operation: 'Observing rejected daily allowance and unchanged saved value'
       for operation in accessible_ui.INVALID_ALLOWANCE_OPERATIONS},
    **{operation: 'Qualifying daily allowance presets and saved readback'
       for operation in accessible_ui.ALLOWANCE_OPERATIONS},
    'gdm-installed-accounts': 'Checking preserved personal accounts and the installed request station',
    'parent-app-rows': 'Reading the complete App Limits row set',
    'parent-app-rows-reopened': 'Reopening App Limits and independently reading its rows',
    'parent-app-rows-wrong-child': 'Refusing app rows for a different child',
    'parent-app-rows-wrong-page': 'Refusing app rows outside App Limits',
    'gdm-list': 'Reading the greeter account list',
    'gdm-focused': 'Checking the intended greeter account is focused',
    'gdm-select-parent': 'Checking the Parent password prompt',
    'gdm-navigation-returned': 'Checking the greeter list after dismissing the password prompt',
    'gdm-product-free-list': 'Reading the product-free greeter account list',
    'gdm-product-free-provider': 'Recording the product-free greeter provider tuple',
    'gdm-product-free-focused': 'Checking the product-free Parent account is focused',
    'gdm-product-free-select-parent': 'Checking the product-free Parent password prompt',
    'gdm-product-free-returned': 'Checking the product-free greeter list after dismissal',
    'gdm-dismissed': 'Checking the password prompt was dismissed',
    'gdm-returned': 'Checking the greeter after returning to graphics',
    'gdm-other-list': 'Reading the wrong-account qualification list',
    'gdm-other-focused': 'Checking the wrong account is focused',
    'gdm-wrong-recipient-refused': 'Rejecting the wrong-account password prompt',
    'gdm-parent-recipient': 'Qualifying the empty masked Parent password field',
    'gdm-parent-recipient-rechecked': 'Freshly rechecking the Parent password recipient',
    'gdm-standard-list': 'Reading the standard-account greeter list',
    'gdm-standard-focused': 'Checking the standard account is focused',
    'gdm-standard-wrong-recipient-refused': 'Rejecting the wrong-account password prompt',
    'gdm-standard-recipient': 'Qualifying the empty masked standard-account password field',
    'gdm-standard-recipient-rechecked': 'Freshly rechecking the standard-account password recipient',
    'desktop': 'Waiting for the Parent desktop',
    'fresh-parent-desktop': 'Checking the fresh Parent desktop without a prompt',
    'parent-desktop-provider': 'Recording the Parent desktop provider tuple',
    'fresh-standard-desktop': 'Checking the fresh standard desktop without a prompt',
    'keyring-cancel-standard': 'Cancelling the standard login-keyring prompt',
    'parent-search-ready': 'Reading the empty Parent app search field',
    'parent-search-focused': 'Checking the Parent app search field is focused',
    'parent-search-entered': 'Checking the complete Parent app search query',
    'parent-search-close-ready': 'Checking the owned Parent window before closing',
    'parent-search-closed': 'Checking Parent closed and the desktop returned',
    'shell-search-started': 'Checking the first Parent search character',
    'shell-search-wrong-result-refused': 'Refusing an unrelated search result binding',
    'shell-search-dismissed': 'Checking search closed and the desktop returned',
    'shell-search-cleared': 'Checking the search query cleared before closing Overview',
    'app-grid': 'Finding the launchable Parent result in public app search',
    'parent-window': 'Waiting for the Parent window',
    'parent-new-window-absent': 'Checking a new Parent window can be opened',
    'parent-new-window-refused': 'Refusing new-window entry while Parent remains open',
    'parent-restart-ready': 'Checking the active Parent window for normal closure',
    'parent-restart-closed-refused': 'Refusing restart when Parent is already closed',
    'parent-restart-wrong-refused': 'Refusing a different named window for Parent restart',
    'parent-initial-selection': 'Reading the reopened Parent initial child selection',
    'parent-command-launch': 'Invoking the Parent command as [Parent user]',
    'standard-parent-command-launch': 'Invoking the Parent command as [Standard user]',
    'child-command-launch': 'Invoking the child overlay command as [Child user]',
    'standard-parent-closed': 'Checking denial dismissal returns to the standard desktop',
    'parent-empty': 'Checking the explanation for no eligible children',
    'child-picker-opened': 'Expanding the child selector for [Child user]',
    'child-choice-highlighted': 'Checking [Child user] is highlighted',
    'parent-selected': 'Checking the selected child and displayed settings',
    'parent-screen-page': 'Returning to Screen Limits and reading settings',
    'parent-apps-page': 'Opening App Limits and checking its controls',
    'parent-page-wrong-child-refused': 'Refusing page input for a different child',
    'about': 'Opening About and reading product information',
    'about-rechecked': 'Rechecking About after closing temporary documents',
    'license-unrelated-launched': 'Opening a synthetic unrelated viewer document',
    'license-unrelated-ready': 'Refusing unrelated license content and link entry',
    'license-unrelated-closed': 'Checking the unrelated document closed',
    'license-empty-launched': 'Opening an empty viewer document',
    'license-empty-ready': 'Refusing empty license content and link entry',
    'license-empty-closed': 'Checking the empty document closed',
    'license': 'Opening and reading the installed license',
    'license-ambiguous-launched': 'Opening a second viewer window',
    'license-ambiguous-ready': 'Refusing ambiguous viewer and close input',
    'license-ambiguous-closed': 'Checking the second window closed',
    'license-provider-refusals': 'Qualifying the installed license viewer and refusal guards',
    'license-closed': 'Checking the license window is closed',
    'about-returned': 'Reading the About footer',
    'parent-returned': 'Checking the returned child and unchanged settings',
    'parent-toggle-enabled': 'Enabling the Parent screen time limit',
    'parent-toggle-disabled': 'Disabling the Parent screen time limit',
    'parent-toggle-current': 'Reading the already-disabled Parent screen time limit',
    'parent-toggle-wrong-refused': 'Refusing an unregistered Parent toggle binding',
    'parent-toggle-hidden-refused': 'Refusing the hidden Parent screen time limit',
    'parent-toggle-disabled-settings': 'Reading settings while screen time is disabled',
    'parent-save-wrong-child-refused': 'Refusing a Parent save result for the wrong child',
    'parent-save-enabled': 'Reading the saved enabled Parent controls',
    'parent-save-reopened': 'Reading the saved state from a fresh Parent observation',
    'parent-save-disabled': 'Reading the saved disabled Parent controls',
    'discovery-ready': 'Checking existing-child settings and remaining time',
    'new-child-picker-opened': 'Expanding the child selector for [New child]',
    'new-child-choice-highlighted': 'Checking [New child] is highlighted',
    'new-child-selected': 'Checking the selected new child and displayed settings',
    'existing-child-picker-opened': 'Expanding the child selector for [Existing child]',
    'existing-child-choice-highlighted': 'Checking [Existing child] is highlighted',
    'existing-returned': 'Checking the returned existing child and displayed settings',
    'existing-apps': 'Reading App Limits for [Existing child]',
    'new-child-apps': 'Reading App Limits for [New child]',
    'new-child-screen': 'Reading screen-time settings for [New child]',
    'discovery-child-picker-opened': 'Expanding the child selector for [Existing child]',
    'discovery-child-choice-highlighted': 'Checking [Existing child] is highlighted',
    'discovery-selected': 'Checking existing-child settings and remaining time',
    'standard-desktop': 'Waiting for the standard-account desktop',
    'standard-system-prompt': 'Checking for a login-keyring prompt',
    'standard-app-grid': 'Opening public app search',
    'standard-search-focused': 'Checking the app search field is focused',
    'standard-search-started': 'Checking the first search character',
    'standard-search-entered': 'Checking the complete Parent search query',
    'standard-parent-unavailable': 'Checking Parent is unavailable to the standard account',
    'standard-search-qualified': 'Qualifying stable Parent search unavailability',
    'standard-management-denied': 'Reading administrator-access denial and checking management is absent',
}
OPERATION_LABELS.update({
    'help-desktop-clear': 'Checking the desktop after command documentation',
})
OPERATION_LABELS.update({
    'gdm-station-wrong-entry-refused': 'Checking a password account does not enter the request station',
    'gdm-station-list': 'Reading the greeter before request-station entry',
    'gdm-station-focused': 'Checking the request station is focused',
    'gdm-station-returned': 'Checking the usable greeter after leaving the request station',
    'kiosk-request-form': 'Reading the request-station form and unavailable controls',
    'kiosk-restriction-ready': 'Checking and focusing the request station before an ordinary shortcut',
    'kiosk-restriction-read': 'Verifying the station remains request-only after an ordinary shortcut',
    'kiosk-disabled-child-select': 'Selecting the disabled child in the request station',
    'kiosk-child-choices-open': 'Inspecting the exact eligible child choices',
    'kiosk-child-choices-closed': 'Collapsing child choices and checking the unchanged unavailable form',
    'kiosk-disabled-form': 'Reading the disabled child explanation and unavailable Request',
    'kiosk-child-select': 'Checking eligible children and selecting the enabled child',
    'kiosk-approver-select': 'Checking eligible approvers and selecting the parent',
    'kiosk-enabled-form': 'Independently reading the enabled station selections',
    'kiosk-choice-refusals': 'Refusing wrong and absent station account choices',
    'parent-kiosk-refused': 'Refusing station selection on the Parent surface',
    'gdm-no-child-refused': 'Refusing the station form on the greeter',
    'gdm-no-approver-refused': 'Refusing the approver form on the greeter',
    'kiosk-no-approver-form': 'Reading the exact empty approver set and unavailable request',
    'kiosk-approver-baseline': 'Reading the available approvers before temporary locking',
    'kiosk-no-child-form': 'Reading the exact empty child set and unavailable request',
    'kiosk-request-cancel': 'Cancelling the request station through its public control',
    'kiosk-request-escape-ready': 'Checking the request station recipient before Escape',
    'station-entry-branch': 'Observing the offered station session branch without input',
    'station-default-entry': 'Reading back the passwordless default request-station session',
})


OPERATION_LABELS.update({
    'feedback-open': 'Opening ordinary Parent feedback',
    'feedback-read': 'Reading the initial synthetic feedback draft',
    'feedback-close': 'Closing the owned feedback dialog',
    'feedback-wrong-entry': 'Refusing a feedback read outside its dialog',
    'feedback-reopen': 'Independently opening Parent feedback again',
    'feedback-reread': 'Comparing the independently observed synthetic draft',
    'feedback-finished': 'Closing feedback after read qualification',
})


OPERATION_LABELS.update({operation: 'Replacing and reading a declared nonsecret field value'
                         for operation in accessible_ui.TEXT_OPERATIONS})
OPERATION_LABELS.update({operation: 'Qualifying kiosk approval and its explicit public result'
                         for operation in accessible_ui.MATE_APPROVAL_OPERATIONS})
OPERATION_LABELS.update({
    'text-wrong-entry': 'Refusing text input outside feedback',
    'text-disabled': 'Refusing text input to a disabled control',
})

@dataclass(frozen=True)
class FeedbackObservation:
    draft: str
    attachments: tuple
    collection: str
    validation: str
    controls: str

    @classmethod
    def from_value(cls, value):
        require(type(value) is dict and value == {
            'draft': 'initial-empty', 'attachments': ['diagnostic-logs.zip'],
            'collection': 'ready', 'validation': 'none', 'controls': 'ready'},
            'ui:feedback-response')
        return cls('initial-empty', ('diagnostic-logs.zip',), 'ready', 'none', 'ready')


@dataclass(frozen=True)
class AppRowsObservation:
    """Immutable public ID/access/match values; expectations belong to callers."""

    rows: tuple

    @classmethod
    def from_rows(cls, rows):
        import re
        require(type(rows) is list and len(rows) <= 256, 'ui:app-rows')
        require(all(type(row) is list and len(row) == 3
                    and all(type(value) is str for value in row)
                    and re.fullmatch(r'parent-app-[0-9a-f]{16}', row[0])
                    and row[1] in ('allowed', 'conditional', 'permanent')
                    and row[2] in ('pattern', 'precise') for row in rows), 'ui:app-rows')
        require(len({row[0] for row in rows}) == len(rows), 'ui:app-rows')
        return cls(tuple(tuple(row) for row in rows))


@dataclass(frozen=True)
class SettingsObservation:
    """Immutable, sanitized UI values owned explicitly by a scenario."""

    child: str
    limit_enabled: bool
    allowance: tuple

    @classmethod
    def from_settings(cls, settings):
        require(type(settings) is dict and set(settings) == {'child', 'limit_enabled', 'allowance'}
                and settings['child'] in accessible_ui.CHILD_IDENTITIES.values()
                and type(settings['limit_enabled']) is bool
                and type(settings['allowance']) is list and 1 <= len(settings['allowance']) <= 2,
                'ui:settings')
        import re
        require(all(type(value) is str and re.fullmatch(
            r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', value)
            for value in settings['allowance']), 'ui:settings')
        return cls(settings['child'], settings['limit_enabled'], tuple(settings['allowance']))


@dataclass(frozen=True)
class RequestObservation:
    """Immutable REQUEST03 projection containing no customer account labels."""

    surface: str
    form_count: int
    child: str
    approver: str
    duration_seconds: int | None
    custom_text: str | None
    allow_soft: bool
    child_selector_enabled: bool
    approver_selector_enabled: bool
    duration_enabled: bool
    soft_choice_enabled: bool
    request_enabled: bool
    cancel_enabled: bool
    message: str
    mute: bool | None

    @classmethod
    def from_request(cls, value, *, operation='kiosk-request-form'):
        fields = tuple(cls.__dataclass_fields__)
        require(type(value) is dict and set(value) == set(fields), 'ui:request')
        observation = cls(**value)
        invalid = accessible_ui.KIOSK_INVALID_OPERATIONS.get(operation)
        require(type(observation.surface) is str and type(observation.form_count) is int
                and type(observation.child) is str and type(observation.approver) is str
                and (type(observation.duration_seconds) is int or (
                    invalid is not None and observation.duration_seconds is None))
                and (observation.custom_text is None or observation.custom_text == '1.25'
                     or invalid is not None and observation.custom_text ==
                     accessible_ui.KIOSK_INVALID_VALUES[invalid[0]])
                and all(type(getattr(observation, field)) is bool for field in (
                    'allow_soft', 'child_selector_enabled', 'approver_selector_enabled',
                    'duration_enabled', 'soft_choice_enabled', 'request_enabled',
                    'cancel_enabled'))
                and type(observation.message) is str and observation.mute is None,
                'ui:request')
        valid = accessible_ui.KIOSK_VALID_REQUESTS.get(operation)
        enabled = operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS or valid is not None or invalid is not None
        require(enabled or operation in accessible_ui.KIOSK_OPERATIONS
                or operation in accessible_ui.KIOSK_DISABLED_REQUESTS, 'ui:request-operation')
        child, approver = {**accessible_ui.KIOSK_ACCOUNT_REQUESTS,
                           **accessible_ui.KIOSK_DISABLED_REQUESTS}.get(
            operation, ('existing-fixture-child', 'other-fixture-parent'))
        no_child = operation == 'kiosk-no-child-form'
        if valid is not None or invalid is not None:
            child, approver = 'fixture-child', 'fixture-parent'
        no_approver = operation == 'kiosk-no-approver-form'
        if no_child:
            child = 'none'
        if no_approver:
            approver = 'none'
        require(observation == cls(
            surface='kiosk', form_count=1, child=child,
            approver=approver, duration_seconds=None if invalid else valid[0] if valid else 1800,
            custom_text=accessible_ui.KIOSK_INVALID_VALUES[invalid[0]] if invalid else valid[1] if valid else None,
            allow_soft=valid[2] if valid else False, child_selector_enabled=True,
            approver_selector_enabled=enabled, duration_enabled=enabled,
            soft_choice_enabled=enabled, request_enabled=enabled, cancel_enabled=True,
            message='no-child' if no_child else 'no-approver' if no_approver else (
                '' if enabled else 'screen-limit-disabled'), mute=None,
        ), 'ui:request')
        return observation


def compare_settings(observed, expected):
    """UI12: pure comparison; diagnostics contain only approved field names."""
    require(type(observed) is SettingsObservation and type(expected) is SettingsObservation,
            'ui:comparison-binding')
    different = [field for field in ('child', 'limit_enabled', 'allowance')
                 if getattr(observed, field) != getattr(expected, field)]
    require(not different, 'ui:settings-changed:' + ','.join(different))
    return {'fields': ['child', 'limit_enabled', 'allowance'], 'outcome': 'passed'}


class UiObservations:
    def __init__(self, transport, *, system_prompt=None, progress=None):
        self.transport = transport
        self.progress = progress
        self.last_operation = None
        self.challenges = set()
        self.pending_challenge = None
        self.challenge_failed = False
        self.approver_uids = None
        self.system_prompt = system_prompt
        self.boot_guard = None
        self.boot_proof = None

    @staticmethod
    def point(value):
        require(False, 'ui:pointer-route-refused')

    @staticmethod
    def retain_kiosk_diagnostic(value):
        """Validate before forwarding; guest text never becomes a diagnostic."""
        require(set(value) == {'event', 'phase', 'status', 'elapsed_ms', 'tree',
                'public_ids', 'tree_reads', 'nodes_read', 'incomplete_reads', 'query_errors'}
                and value['phase'] in accessible_ui.KIOSK_DIAGNOSTIC_PHASES
                and value['status'] in {'reading', 'missing', 'incomplete', 'query-error',
                                        'passed', 'failed'}
                and value['tree'] in {'unread', 'complete', 'incomplete'}, 'ui:diagnostic')
        require(all(type(value[key]) is int and 0 <= value[key] <= 10**9
                    for key in ('elapsed_ms', 'tree_reads', 'nodes_read',
                                'incomplete_reads', 'query_errors')), 'ui:diagnostic')
        counts = value['public_ids']
        require(type(counts) is dict and (not counts or
                set(counts) == set(accessible_ui.KIOSK_DIAGNOSTIC_IDS))
                and all(type(count) is int and 0 <= count <= 6000
                        for count in counts.values())
                and (value['tree'] == 'complete') == bool(counts), 'ui:diagnostic')
        # Controller stderr is retained by the owned command even when its SSH
        # child times out. Keep this evidence separate from the final UI result.
        line = json.dumps(value, sort_keys=True)
        print(line, file=sys.stderr, flush=True)
        watch_activity.event(line)

    def call(self, argv, operation, *, input=None):
        # Greeter startup: 300s identity + 20s bus + 45s UI, with transport
        # margin; still inside the worker's 420s checkpoint deadline.
        # Kiosk waits only for the public form, with transport margin.
        timeout = 390 if (operation in accessible_ui.GREETER_OPERATIONS
                          or operation in accessible_ui.STATION_BRANCH_OPERATIONS) else (
            120 if operation in accessible_ui.KIOSK_SESSION_OPERATIONS else 90)
        kiosk = operation in accessible_ui.KIOSK_SESSION_OPERATIONS
        if self.system_prompt is None and not kiosk:
            return self.transport.call(argv, input=input, timeout=timeout), []
        commands = self.transport.commands
        previous = commands.progress
        pending = bytearray()
        prompts, results = [], []
        received = 0
        diagnostic_count = 0

        def output(data):
            nonlocal received, diagnostic_count
            received += len(data)
            limit = 131072 if kiosk else 8192
            if operation in accessible_ui.APP_ROW_OPERATIONS:
                limit = max(limit, RESPONSE_BYTE_LIMITS.get(operation, 2048))
            require(received <= limit, 'ui:response-size')
            pending.extend(data)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                if type(value) is dict and value.get('event') == 'kiosk-form-observation':
                    diagnostic_count += 1
                    require(kiosk and not results and diagnostic_count <= 128,
                            'ui:diagnostic-order')
                    require(bytes(line) == json.dumps(value, sort_keys=True).encode(),
                            'ui:diagnostic')
                    self.retain_kiosk_diagnostic(value)
                elif type(value) is dict and value.get('event') == 'system-prompt':
                    require(False, 'ui:prompt-coordinate-route-refused')
                else:
                    require(not results, 'ui:response-replay')
                    results.append(bytes(line))
        try:
            self.transport.call(argv, input=input, timeout=timeout, on_output=output)
            require(not pending and len(results) == 1, 'ui:response-incomplete')
            return results[0], prompts
        finally:
            commands.progress = previous

    def observe(self, operation):
        import time
        previous_operation = getattr(self, 'last_mate_operation', None)
        self.last_mate_operation = None
        self.pending_challenge = None
        self.approver_uids = None
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        with watch_activity.operation(OPERATION_LABELS[operation]):
            try:
                if 0 < getattr(self, 'mate_approval_index', 0) < 4:
                    if operation not in accessible_ui.MATE_APPROVAL_OPERATIONS:
                        self.challenge_failed = True
                        require(False, 'ui:mate-intervening-operation')
                if operation in accessible_ui.MATE_APPROVAL_OPERATIONS:
                    require(not self.challenge_failed, 'ui:challenge-previous-failure')
                    order = ('kiosk-mate-open', 'kiosk-mate-qualified',
                             'kiosk-mate-rechecked', 'kiosk-mate-submit-success')
                    index = getattr(self, 'mate_approval_index', 0)
                    # A successful rejection ends its challenge. Only a subsequent,
                    # independently read form permits a deliberately new approval.
                    if (index == 4 and self.mate_rejection
                            and operation == 'kiosk-mate-open'
                            and previous_operation == 'kiosk-valid-fraction-soft-read'):
                        index = 0
                    if index == 0:
                        self.mate_rejection = operation == accessible_ui.MATE_REJECTION_ORDER[0]
                    if self.mate_rejection:
                        order = accessible_ui.MATE_REJECTION_ORDER
                    elif operation == 'kiosk-mate-submit-immediate':
                        order = (*order[:3], operation)
                    require(index < len(order) and operation == order[index], 'ui:mate-order')
                    if index:
                        require(time.monotonic() - self.mate_approval_checked < 30, 'ui:mate-stale-proof')
                    self.mate_approval_index = index + 1
                    self.mate_approval_checked = time.monotonic()
                if operation in accessible_ui.MATE_OPERATIONS:
                    require(not self.challenge_failed, 'ui:challenge-previous-failure')
                result = self._observe(operation)
                self.last_mate_operation = operation
                return result
            except BaseException:
                if operation in accessible_ui.MATE_OPERATIONS | accessible_ui.MATE_APPROVAL_OPERATIONS:
                    self.challenge_failed = True
                raise

    def observe_challenge(self, operation, challenge):
        """Two fresh same-challenge checks; no intervening operation or replay."""
        require(not self.challenge_failed, 'ui:challenge-previous-failure')
        try:
            require(type(challenge) is dict and set(challenge) == {
                'id', 'role', 'surface', 'check'} and challenge['surface'] == 'gdm'
                and challenge['role'] in ('parent', 'other-child')
                and challenge['check'] in ('qualified', 'rechecked')
                and type(challenge['id']) is str and bool(challenge['id']), 'ui:challenge')
            identity = (challenge['id'], challenge['role'], challenge['surface'])
            first = challenge['check'] == 'qualified'
            recipient = ('gdm-parent-recipient' if challenge['role'] == 'parent'
                         else 'gdm-standard-recipient')
            require(operation == recipient + ('' if first else '-rechecked'), 'ui:challenge')
            if first:
                require(challenge['id'] not in self.challenges, 'ui:challenge-replay')
                self.challenges.add(challenge['id'])
            else:
                require(self.pending_challenge == identity, 'ui:challenge-order')
            result = self.observe(operation)
            self.pending_challenge = identity if first else None
            return result
        except BaseException:
            self.challenge_failed = True
            self.pending_challenge = None
            raise

    def _observe(self, operation):
        import re
        # Qualifications lack a scenario recorder, but use the same existing
        # spectator command pane as customer cases. Keep private program/stdin
        # and raw UI replies hidden; expose the fixed operation and its result.
        watch_activity.event('SSH UI: ' + OPERATION_LABELS[operation])
        if self.progress is not None:
            self.progress.operation(OPERATION_LABELS[operation])
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        reader = (system.ROOT / 'tests/e2e/public_atspi.py').read_text()
        program = ('import sys, types\n'
                   'public_atspi = types.ModuleType("public_atspi")\n'
                   'sys.modules["public_atspi"] = public_atspi\n'
                   'exec(compile(' + repr(reader) + ', "public_atspi.py", "exec"), '
                   'public_atspi.__dict__)\n' + program)
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        self.boot_proof = None
        binding = []
        if self.boot_guard is not None:
            import re
            require(type(self.boot_guard) is str and (self.boot_guard == '' or
                    re.fullmatch(r'[0-9a-f]{64}', self.boot_guard)), 'ui:boot-binding')
            binding = [self.boot_guard]
        if operation in accessible_ui.MATE_APPROVAL_OPERATIONS and operation not in (
                'kiosk-mate-open', 'kiosk-mate-rejection-open'):
            binding = [self.boot_guard or '', self.mate_approval_identity]
        # The standalone observer can exceed Linux's per-argument limit after
        # SSH shell quoting. Carry its bytes on the existing guarded stdin pipe.
        try:
            raw, prompts = self.call(['/usr/bin/python3', '-I', '-', operation, version, *binding],
                                     operation, input=program.encode())
        except BaseException:
            watch_activity.event('SSH UI observation failed: ' + operation)
            raise
        require(isinstance(raw, bytes) and 0 < len(raw) <=
                RESPONSE_BYTE_LIMITS.get(operation, 2048), 'ui:response-size')
        result = json.loads(raw)
        if binding:
            proof = result.pop('boot_sha256', None) if type(result) is dict else None
            require(type(proof) is str and re.fullmatch(r'[0-9a-f]{64}', proof)
                    and (not self.boot_guard or proof == self.boot_guard), 'ui:boot-changed')
            self.boot_proof = proof
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation in accessible_ui.MATE_APPROVAL_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'approval'}, 'ui:mate-response')
            value = result['approval']
            if operation == 'kiosk-mate-submit-rejection':
                require(value == {'rejected': True, 'cancelled': True, 'no_error': True}
                        and all(type(item) is bool for item in value.values()), 'ui:mate-result')
            elif operation in ('kiosk-mate-submit-success', 'kiosk-mate-submit-immediate'):
                require(value == {'approved': True, 'form_success': True,
                                  **({'immediate_exit': True} if operation.endswith('immediate') else {})}
                        and all(type(item) is bool for item in value.values()), 'ui:mate-result')
            else:
                require(type(value) is dict and set(value) == {'challenge_id'} and
                        type(value['challenge_id']) is str and
                        re.fullmatch(r'[0-9a-f]{64}', value['challenge_id']), 'ui:mate-identity')
                if operation in ('kiosk-mate-open', 'kiosk-mate-rejection-open'):
                    require(value['challenge_id'] not in self.challenges, 'ui:challenge-replay')
                    self.challenges.add(value['challenge_id'])
                    self.mate_approval_identity = value['challenge_id']
                else:
                    require(value['challenge_id'] == self.mate_approval_identity, 'ui:mate-replacement')
            expected['approval'] = value
        if operation == 'parent-initial-selection':
            require(type(result) is dict and set(result) == {*expected, 'selection'}
                    and result['selection'] in ('fixture-child', 'existing-fixture-child'),
                    'ui:initial-selection')
            expected['selection'] = result['selection']
        if operation == 'kiosk-approver-baseline':
            require(type(result) is dict and set(result) == {*expected, 'approver_uids'},
                    'ui:approver-baseline')
            uids = result['approver_uids']
            require(type(uids) is list and bool(uids)
                    and all(type(uid) is int and 1000 <= uid <= (1 << 32) - 1 for uid in uids)
                    and len(uids) == len(set(uids)), 'ui:approver-baseline')
            # Bind the immediate fixture action in memory. Raw transport stays
            # private; journey records and worker replies receive only presence.
            expected['approver_uids'] = uids
        if operation in ('parent-search-close-ready', 'standard-search-qualified',
                         'license-provider-refusals', 'parent-desktop-provider'):
            require(type(result) is dict and set(result) == {*expected, 'provider'}, 'ui:response')
            expected['provider'] = accessible_ui.validate_shell_metadata(result['provider'])
        if operation == 'gdm-product-free-provider':
            require(type(result) is dict and set(result) == {*expected, 'provider'}, 'ui:response')
            expected['provider'] = accessible_ui.validate_gdm_metadata(result['provider'])
        if operation == 'station-entry-branch':
            require(type(result) is dict and set(result) == {*expected, 'branch'}, 'ui:response')
            branch = result['branch']
            require(type(branch) is dict and set(branch) == {'destination', 'controls'}
                    and type(branch['controls']) is list, 'ui:station-branch')
            controls = branch['controls']
            require((branch['destination'] == 'default-request-form' and not controls)
                    or (branch['destination'] == 'greeter-controls' and 0 < len(controls) <= 12),
                    'ui:station-branch')
            for control in controls:
                require(type(control) is dict and set(control) == {
                    'label', 'role', 'public_id_present', 'sensitive', 'focused'}
                    and control['label'] in {*accessible_ui.GDM_SESSION_LABELS.values(), 'unresolved'}
                    and control['role'] in {'button', 'push button', 'toggle button', 'radio button',
                                           'menu item', 'radio menu item', 'check menu item', 'combo box'}
                    and all(type(control[key]) is bool for key in
                            ('public_id_present', 'sensitive', 'focused')), 'ui:station-branch')
            expected['branch'] = branch
        if operation == 'station-default-entry':
            require(type(result) is dict and set(result) == {*expected, 'entry'}
                    and result['entry'] == {'destination': 'default-request-form'},
                    'ui:station-default-entry')
            expected['entry'] = {'destination': 'default-request-form'}
        if operation in accessible_ui.PICKER_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'focused'}
                    and result['focused'] is True, 'ui:response')
            expected['focused'] = True
        if operation in accessible_ui.GREETER_NAVIGATION:
            require(type(result) is dict and set(result) == {*expected, 'focused'}
                    and result['focused'] is True, 'ui:response')
            expected['focused'] = True
        if operation in accessible_ui.SETTINGS_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'settings'}, 'ui:response')
            settings = result['settings']
            require(type(settings) is dict and set(settings) == {'child', 'limit_enabled', 'allowance'}
                    and settings['child'] == accessible_ui.CHILD_IDENTITIES[
                        accessible_ui.SETTINGS_OPERATIONS[operation]]
                    and type(settings['limit_enabled']) is bool
                    and type(settings['allowance']) is list and 1 <= len(settings['allowance']) <= 2,
                    'ui:settings')
            import re
            require(all(type(value) is str and re.fullmatch(
                r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', value)
                        for value in settings['allowance']), 'ui:settings')
            expected['settings'] = settings
        if operation in accessible_ui.TOGGLE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'toggle'}
                    and result['toggle'] == accessible_ui.TOGGLE_OPERATIONS[operation],
                    'ui:toggle-response')
            expected['toggle'] = accessible_ui.TOGGLE_OPERATIONS[operation]
        if operation in accessible_ui.APP_ROW_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'apps'}, 'ui:response')
            apps = result['apps']
            if operation.endswith(('wrong-child', 'wrong-page')):
                require(apps == {'refusal': 'wrong-child' if operation.endswith('wrong-child')
                                  else 'wrong-page'}, 'ui:app-row-refusal')
            else:
                require(type(apps) is dict and set(apps) == {'rows'}, 'ui:app-rows')
                AppRowsObservation.from_rows(apps['rows'])
            expected['apps'] = apps
        if operation in ('feedback-open', 'feedback-read', 'feedback-reopen', 'feedback-reread'):
            require(type(result) is dict and set(result) == {*expected, 'feedback'},
                    'ui:feedback-response')
            FeedbackObservation.from_value(result['feedback'])
            expected['feedback'] = result['feedback']
        if operation in accessible_ui.TEXT_OPERATIONS and operation.endswith('-read'):
            binding, _ = accessible_ui.TEXT_OPERATIONS[operation]
            projection = {'binding': binding, 'exact': True,
                          'length': len(accessible_ui.TEXT_VALUES[binding][1])}
            require(type(result) is dict and set(result) == {*expected, 'text'}
                    and result['text'] == projection, 'ui:text-response')
            expected['text'] = projection
        if operation in accessible_ui.INVALID_ALLOWANCE_OPERATIONS:
            projection = {'binding': accessible_ui.INVALID_ALLOWANCE_OPERATIONS[operation],
                          'validation': 'rejected'}
            require(type(result) is dict and set(result) == {*expected, 'allowance_validation'}
                    and result['allowance_validation'] == projection,
                    'ui:allowance-validation-response')
            expected['allowance_validation'] = projection
        if operation in accessible_ui.CUSTOM_ALLOWANCE_OPERATIONS:
            minutes, action = accessible_ui.CUSTOM_ALLOWANCE_OPERATIONS[operation]
            projection = ({'refusal': action} if action in ('wrong-child', 'disabled')
                          else {'minutes': minutes, 'action': action})
            require(type(result) is dict and set(result) == {*expected, 'custom_allowance'}
                    and result['custom_allowance'] == projection, 'ui:custom-allowance-response')
            expected['custom_allowance'] = projection
        if operation in accessible_ui.ALLOWANCE_OPERATIONS:
            projection = ({'refusal': operation.removeprefix('allowance-')}
                          if operation in ('allowance-wrong-child', 'allowance-disabled')
                          else {'minutes': int(operation.split('-')[1]), 'saved': True})
            require(type(result) is dict and set(result) == {*expected, 'allowance'}
                    and result['allowance'] == projection, 'ui:allowance-response')
            expected['allowance'] = projection
        if operation in accessible_ui.TIME_EXPLANATION_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'time_explanation'},
                    'ui:time-response')
            value = result['time_explanation']
            if operation.endswith(('read', 'reread')):
                require(type(value) is dict and set(value) == {
                    'child', 'expanded', 'daily', 'one_time', 'total', 'observed_monotonic_ns'}
                    and value['child'] == 'fixture-child' and value['expanded'] is True
                    and type(value['observed_monotonic_ns']) is int
                    and 0 < value['observed_monotonic_ns'] < 10**20, 'ui:time-response')
                for key in ('daily', 'one_time', 'total'):
                    item = value[key]
                    require(type(item) is dict and set(item) == {'text', 'seconds', 'precision_seconds'},
                            'ui:time-response')
                    try:
                        parsed = accessible_ui.duration_projection(item['text'])
                    except accessible_ui.UiError:
                        require(False, 'ui:time-response')
                    require(type(item['seconds']) is int and type(item['precision_seconds']) is int
                            and item == parsed, 'ui:time-response')
            else:
                projection = ({'expanded': operation.endswith('-expand')}
                              if operation.endswith(('-expand', '-collapse')) else
                              {'refusal': operation.removeprefix('time-explanation-')})
                require(value == projection, 'ui:time-response')
            expected['time_explanation'] = value
        if operation in accessible_ui.REVOKE_DISABLED_OPERATIONS:
            projection = {'child': 'fixture-child',
                          'limit_enabled': accessible_ui.REVOKE_DISABLED_OPERATIONS[operation],
                          'idle': True, 'sensitive': False,
                          'daily_seconds': 0, 'one_time_seconds': 0, 'total_seconds': 0}
            require(type(result) is dict and set(result) == {*expected, 'revoke'}
                    and type(result['revoke']) is dict
                    and result['revoke'] == projection
                    and all(type(result['revoke'][key]) is type(value)
                            for key, value in projection.items()), 'ui:revoke-disabled-response')
            expected['revoke'] = projection
        if operation in accessible_ui.PARENT_SAVE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'save'}
                    and result['save'] == accessible_ui.PARENT_SAVE_OPERATIONS[operation],
                    'ui:parent-save-response')
            expected['save'] = accessible_ui.PARENT_SAVE_OPERATIONS[operation]
        if operation in accessible_ui.MATE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'mate'}, 'ui:mate-response')
            value = result['mate']
            projection = {'child': 'fixture-child', 'approver': 'fixture-parent',
                          'duration_seconds': 75, 'allow_soft': True, 'cancelled': True,
                          'unchanged_form': True, 'no_error': True,
                          'same_challenge_rechecked': True,
                          'rejected_proofs': list(accessible_ui.MATE_REFUSALS)
                          if operation == 'kiosk-mate-refusals-cancel' else [],
                          'refusals': operation == 'kiosk-mate-refusals-cancel'}
            require(type(value) is dict and set(value) == {*projection, 'provider', 'challenge_id'}
                    and all(value[key] == item and type(value[key]) is type(item)
                            for key, item in projection.items()), 'ui:mate-response')
            accessible_ui.validate_shell_metadata(value['provider'])
            challenge_id = value['challenge_id']
            require(type(challenge_id) is str and len(challenge_id) == 64
                    and all(char in '0123456789abcdef' for char in challenge_id), 'ui:challenge')
            require(not self.challenge_failed and challenge_id not in self.challenges,
                    'ui:challenge-replay')
            self.challenges.add(challenge_id)
            expected['mate'] = value
        if operation in accessible_ui.KIOSK_INVALID_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'invalid_choice'}, 'ui:response')
            value = result['invalid_choice']
            require(type(value) is dict and set(value) == {'request', 'validation', 'no_authentication'}
                    and value['no_authentication'] is True
                    and value['validation'] is (accessible_ui.KIOSK_INVALID_OPERATIONS[operation][1] != 'ready'),
                    'ui:kiosk-invalid-response')
            RequestObservation.from_request(value['request'], operation=operation)
            expected['invalid_choice'] = value
        if operation in accessible_ui.KIOSK_VALID_REQUESTS:
            require(type(result) is dict and set(result) == {*expected, 'valid_choice'}, 'ui:response')
            value = result['valid_choice']
            require(type(value) is dict and set(value) == {'request', 'estimate', 'observed_monotonic_ns'}
                    and type(value['observed_monotonic_ns']) is int
                    and value['observed_monotonic_ns'] > 0, 'ui:kiosk-valid-response')
            RequestObservation.from_request(value['request'], operation=operation)
            estimate = value['estimate']
            if accessible_ui.KIOSK_VALID_REQUESTS[operation][0] == 0:
                require(estimate == {'kind': 'midnight'}, 'ui:kiosk-valid-response')
            else:
                require(type(estimate) is dict and set(estimate) == {
                    'kind', 'text', 'seconds', 'precision_seconds'} and estimate['kind'] == 'fixed',
                    'ui:kiosk-valid-response')
                require(estimate == {'kind': 'fixed', **accessible_ui.duration_projection(estimate['text'])},
                        'ui:kiosk-valid-response')
            expected['valid_choice'] = value
        if (operation in accessible_ui.KIOSK_OPERATIONS
                or operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS
                or operation in accessible_ui.KIOSK_DISABLED_REQUESTS):
            require(type(result) is dict and set(result) == {*expected, 'request'}, 'ui:response')
            RequestObservation.from_request(result['request'], operation=operation)
            expected['request'] = result['request']
        require(result == expected, 'ui:response')
        if operation == 'gdm-wrong-recipient-refused':
            require(self.last_operation == 'gdm-other-focused', 'ui:recipient-order')
        elif operation == 'gdm-parent-recipient':
            require(self.last_operation in ('gdm-focused', 'gdm-product-free-focused'),
                    'ui:recipient-order')
        elif operation == 'gdm-parent-recipient-rechecked':
            require(self.last_operation == 'gdm-parent-recipient', 'ui:recipient-order')
        elif operation == 'gdm-standard-wrong-recipient-refused':
            require(self.last_operation == 'gdm-other-focused', 'ui:recipient-order')
        elif operation == 'gdm-standard-recipient':
            require(self.last_operation == 'gdm-standard-focused',
                    'ui:recipient-order')
        elif operation == 'gdm-standard-recipient-rechecked':
            require(self.last_operation == 'gdm-standard-recipient', 'ui:recipient-order')
        self.last_operation = operation
        if operation == 'kiosk-approver-baseline':
            self.approver_uids = tuple(result.pop('approver_uids'))
            result['approver_present'] = True
        watch_activity.event('SSH UI observation passed: ' + operation)
        if prompts:
            result['system_prompts'] = prompts
        return result
