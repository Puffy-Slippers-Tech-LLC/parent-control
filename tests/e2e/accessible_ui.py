"""Bounded public AT-SPI interaction in the installed fixture's desktop.

This file also runs as a standalone program in the guarded guest. It reads only
public UI objects; it never imports product code or reads product storage/buses.
Only fixed operation names and sanitized results cross the controller boundary.
"""

from contextlib import contextmanager, nullcontext
from types import MappingProxyType
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time
import warnings
try:
    from download_destination import download_directory
except ModuleNotFoundError as error:
    if error.name != 'download_destination':
        raise
    # Host Shell probes import this reader as a package without the standalone
    # guest's module directory on sys.path.
    from tests.e2e.download_destination import download_directory

# Isolated guest Python receives this file on guarded stdin after the controller
# installs public_atspi.py as the public_atspi module. Keep finite public-input
# data here; controller modules may import these constants.
INVALID = {'empty': '', 'letters': 'abc', 'negative': '-1',
           'fraction': '0.5', 'maximum': '1440', 'over': '1441'}
INVALID_DESCRIPTION = 'Invalid daily allowance. Enter a whole number from 0 to 1439.'
PRESETS = (0, 15, 30, 45, *range(60, 1411, 30))
PRESET_LABELS = {value: (f'{value} minutes' if value < 60 else
                         '1 hour' if value == 60 else f'{value / 60:g} hours')
                 for value in PRESETS}

OPERATIONS = frozenset({
    'gdm-installed-accounts',
    'gdm-no-approver-refused',
    'gdm-no-child-refused',
    'gdm-list', 'gdm-focused', 'gdm-select-parent', 'gdm-navigation-returned',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-dismissed', 'gdm-returned',
    'desktop', 'app-grid', 'parent-window', 'parent-window-count', 'parent-empty', 'child-picker-opened', 'child-choice-highlighted', 'parent-selected',
    'about', 'about-interval-read', 'about-interval-refused', 'about-rechecked', 'license',
    'license-provider-refusals', 'website-clickable', 'privacy-clickable', 'support-clickable',
    'parent-help-clickable', 'parent-information-about', 'parent-information-clickable',
    'license-closed', 'about-returned', 'parent-returned',
    'discovery-ready', 'new-child-picker-opened', 'new-child-choice-highlighted',
    'new-child-selected', 'existing-child-picker-opened', 'existing-child-choice-highlighted',
    'existing-returned', 'existing-apps', 'new-child-apps', 'new-child-screen',
    'discovery-child-picker-opened', 'discovery-child-choice-highlighted', 'discovery-selected',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'fresh-parent-desktop', 'fresh-standard-desktop',
    'keyring-cancel-standard',
    'standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused',
    'gdm-station-returned', 'kiosk-request-form', 'kiosk-request-cancel',
    'kiosk-request-escape-ready', 'station-entry-branch', 'station-default-entry',
})
STANDARD_OPERATIONS = frozenset({
    'standard-desktop', 'fresh-standard-desktop', 'standard-system-prompt', 'standard-app-grid', 'standard-search-focused', 'standard-search-started', 'standard-search-entered', 'standard-parent-unavailable',
    'keyring-cancel-standard',
})
OPERATIONS |= frozenset({
    'parent-command-launch', 'standard-parent-command-launch', 'standard-parent-closed',
    'child-command-launch',
})
OPERATIONS |= frozenset({'parent-search-ready', 'parent-search-focused', 'parent-search-entered'})
OPERATIONS |= frozenset({'parent-search-close-ready', 'parent-search-closed'})
OPERATIONS |= frozenset({'shell-search-started', 'shell-search-wrong-result-refused',
                         'shell-search-cleared',
                         'shell-search-dismissed'})
OPERATIONS |= frozenset({'standard-management-denied'})
STANDARD_OPERATIONS |= frozenset({'standard-management-denied'})
STANDARD_OPERATIONS |= frozenset({'standard-parent-command-launch', 'standard-parent-closed'})
OPERATIONS |= frozenset({'standard-search-qualified'})
STANDARD_OPERATIONS |= frozenset({'standard-search-qualified'})
NATIVE_PRODUCT = 'ONPC Allowed Fixture'
NATIVE_APP_OPERATIONS = frozenset('native-' + suffix for suffix in (
    'desktop', 'search-ready', 'search-focused', 'search-entered', 'grid',
    'grid-refusals', 'command-launch', 'command-refusals', 'wrong-entry',
    'opened', 'submit', 'resubmit', 'submitted', 'close', 'closed',
    'activity', 'activity-wrong-entry'))
OPERATIONS |= NATIVE_APP_OPERATIONS
STANDARD_OPERATIONS |= NATIVE_APP_OPERATIONS
COUNTDOWN_OPERATIONS = frozenset({'child-countdown-present', 'child-countdown-absent'})
CHILD_DESKTOP_OPERATIONS = frozenset({'fresh-child-desktop'}) | COUNTDOWN_OPERATIONS
OVERLAY_OPERATIONS = frozenset({'overlay-request-form', 'overlay-panel-ready',
    'overlay-panel-launch', 'overlay-panel-reveal-ready', 'overlay-panel-overview',
    'overlay-qualification-cancel', 'overlay-desktop'})
CHILD_DESKTOP_OPERATIONS |= OVERLAY_OPERATIONS | frozenset({'child-command-launch'})
OVERLAY_NATIVE_OPERATIONS = frozenset('overlay-native-' + suffix for suffix in (
    'desktop', 'command-launch', 'opened', 'submit', 'resubmit', 'submitted', 'activity', 'close', 'closed'))
CHILD_DESKTOP_OPERATIONS |= OVERLAY_NATIVE_OPERATIONS
OPERATIONS |= frozenset({'overlay-wrong-account-refused'})
CHILD_GREETER_OPERATIONS = frozenset({
    'gdm-child-list', 'gdm-child-focused', 'gdm-child-wrong-recipient-refused',
    'gdm-child-recipient', 'gdm-child-recipient-rechecked',
    'gdm-child-time-denied', 'gdm-child-denied-return-ready', 'gdm-child-denied-returned',
})
OPERATIONS |= CHILD_DESKTOP_OPERATIONS | CHILD_GREETER_OPERATIONS
OPERATIONS |= frozenset({'child-countdown-wrong-account-refused'})
OPERATIONS |= frozenset({'help-desktop-clear'})
OPERATIONS |= frozenset({'gdm-product-free-provider', 'parent-desktop-provider'})
PRODUCT = 'Oh No! Parent Control'
FEEDBACK_READ_OPERATIONS = frozenset({
    'feedback-open', 'feedback-read', 'feedback-close',
    'feedback-wrong-entry', 'feedback-reopen', 'feedback-reread', 'feedback-finished',
})
OPERATIONS |= FEEDBACK_READ_OPERATIONS
OPERATIONS |= frozenset({'feedback-collection-ready'})
FEEDBACK_PRIVACY_OPERATIONS = frozenset({
    'feedback-draft', 'feedback-draft-reopen', 'feedback-draft-reread',
    'feedback-draft-closed', 'feedback-close-refused',
    'feedback-privacy-open', 'feedback-privacy-returned',
})
OPERATIONS |= FEEDBACK_PRIVACY_OPERATIONS
FEEDBACK_PROJECTIONS = {
    **{f'length-{family}-{units}': (f'body-{family}-{units}', 'reply-clear')
       for family in ('ascii', 'mixed') for units in (5000, 5001)},
    'initial-empty': ('body-clear', 'reply-clear'),
    'parent-rule-error': ('body-rule-error', 'reply-clear'),
    'trace-prefix': ('body-first', 'reply-clear'),
    'synthetic-first': ('body-first', 'reply-first'),
    'formatted': ('body-smoke', 'reply-first'),
    'formatted-file': ('body-smoke', 'reply-first'),
    'attachment-file': ('body-first', 'reply-first'),
    'states-whitespace': ('body-whitespace', 'reply-clear'),
    'states-no-reply': ('body-first', 'reply-clear'),
    'states-malformed': ('body-first', 'reply-malformed'),
    'rejection-hidden': ('body-hidden', 'reply-clear'),
    'rejection-complex': ('body-complex', 'reply-clear'),
}
FEEDBACK_STATE_PROJECTIONS = {
    'feedback-trace-sample': 'trace-prefix',
    'feedback-state-empty': 'initial-empty',
    'feedback-state-whitespace': 'states-whitespace',
    'feedback-state-no-reply': 'states-no-reply',
    'feedback-state-malformed': 'states-malformed',
    'feedback-state-valid': 'synthetic-first',
    'feedback-state-reopen': 'synthetic-first',
}
FEEDBACK_STATE_OPERATIONS = frozenset(FEEDBACK_STATE_PROJECTIONS) | {
    'feedback-state-close', 'feedback-state-wrong-entry'}
OPERATIONS |= FEEDBACK_STATE_OPERATIONS
# Exact public explanations only; never return arbitrary status/draft text.
FEEDBACK_VALIDATION = {
    'Feedback must be at most 5,000 UTF-16 characters (some emoji count as two).': 'length-invalid',
    '': 'none',
    'Please enter your feedback.': 'body-required',
    'Enter a bare reply email address, or leave it blank.': 'reply-invalid',
    'Your feedback contains an unsupported hidden character. Please retype it and try again.': 'hidden-invalid',
    'The formatted feedback is too complex. Remove some formatting and try again.': 'format-invalid',
}
# Fixed public fixtures; limits are regression-checked against the product.
COMPLEX_LINES = 1200
COMPLEX_BODY = '\n'.join(['x'] * COMPLEX_LINES)
REJECTION_CASES = {
    **{family + suffix: (f'length-{family}-5001', 'length-invalid')
       for family in ('ascii', 'mixed') for suffix in ('', '-reopened')},
    'empty': ('initial-empty', 'body-required'),
    'malformed': ('states-malformed', 'reply-invalid'),
    'hidden': ('rejection-hidden', 'hidden-invalid'),
    'complex': ('rejection-complex', 'format-invalid'),
    'reopened': ('rejection-complex', 'format-invalid'),
}
REJECTION_FORMATS = ('bold', 'italic', 'underline', 'strike')
REJECTION_OPERATIONS = frozenset({
    *(f'rejection-{case}-{action}' for case in REJECTION_CASES for action in ('send', 'read')),
    *(f'rejection-format-{kind}-{action}' for kind in REJECTION_FORMATS
      for action in ('focus', 'apply')),
    'rejection-valid-refusal', 'rejection-close', 'rejection-wrong-entry',
    'rejection-reopen', 'rejection-hidden-focus', 'rejection-hidden-caret',
    'rejection-hidden-input-read',
})
OPERATIONS |= REJECTION_OPERATIONS
LENGTH_OBSERVATIONS = {
    f'length-{family}-{action}': (f'length-{family}-{units}', 'none')
    for family in ('ascii', 'mixed') for action, units in (('valid', 5000), ('reopen', 5001))
}
LENGTH_OPERATIONS = frozenset(LENGTH_OBSERVATIONS) | {
    f'length-{family}-{action}' for family in ('ascii', 'mixed')
    for action in ('refusal', 'close', 'wrong-entry')}
OPERATIONS |= LENGTH_OPERATIONS
KIOSK_INVALID_VALUES = {
    'empty': '', 'letters': 'abc', 'negative': '-1', 'zero': '0',
    'below': '0.09', 'over': '1440.1', 'comma': '1,5',
}
TEXT_VALUES = {
    'match-wildcard': ('parent-match-rule-entry', '/opt/onpc-test-fixtures/Applications/Exact*.AppImage'),
    'match-wildcard-basename': ('parent-match-rule-entry', 'Exact*.AppImage'),
    'match-wildcard-appimages': ('parent-match-rule-entry', '/opt/onpc-test-fixtures/Applications/*.AppImage'),
    'match-rejected-directory': ('parent-match-rule-entry', '/opt/onpc-test-fixtures/Rejected/*.AppImage'),
    'match-precise': ('parent-match-rule-entry', '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage'),
    'match-precise-basename': ('parent-match-rule-entry', 'Exact Fixture.AppImage'),
    'match-invalid-empty': ('parent-match-rule-entry', ''),
    'match-invalid-whitespace': ('parent-match-rule-entry', '   '),
    'match-invalid-basename': ('parent-match-rule-entry', 'Unrelated.AppImage'),
    'match-invalid-absolute': ('parent-match-rule-entry', '/opt/onpc-test-fixtures/Applications/Unrelated.AppImage'),
    'catalogue-name': ('parent-app-search', 'ONPC Allowed Fixture'),
    'catalogue-description': ('parent-app-search', 'Exact native catalogue fixture'),
    'catalogue-identifier': ('parent-app-search', 'com.puffyslippers.ONPCTest.A.desktop'),
    'catalogue-absent': ('parent-app-search', 'ONPC Absent Catalogue Fixture 077b'),
    'catalogue-clear': ('parent-app-search', ''),
    **{f'body-ascii-{units}': ('feedback-editor-input', 'x' * units)
       for units in (5000, 5001)},
    **{f'body-mixed-{units}' + suffix: ('feedback-editor-input', 'x' * (units - 2) + emoji)
       for units in (5000, 5001) for suffix, emoji in (('', '\U0001f600'), ('-base', ''))},
    **{'kiosk-invalid-' + key: ('kiosk-custom-duration', value)
       for key, value in KIOSK_INVALID_VALUES.items()},
    **{'overlay-invalid-' + key: ('kiosk-custom-duration', value)
       for key, value in KIOSK_INVALID_VALUES.items()},
    'kiosk-fraction': ('kiosk-custom-duration', '1.25'),
    'overlay-fraction': ('kiosk-custom-duration', '1.25'),
    'body-first': ('feedback-editor-input', 'Synthetic feedback first'),
    'body-smoke': ('feedback-editor-input', 'Synthetic feedback first\U0001f600'),
    'body-second': ('feedback-editor-input', 'Synthetic feedback replacement'),
    'body-clear': ('feedback-editor-input', ''),
    'body-whitespace': ('feedback-editor-input', '   '),
    'body-hidden': ('feedback-editor-input', 'a\x01b'),
    'body-hidden-base': ('feedback-editor-input', 'ab'),
    'body-complex': ('feedback-editor-input', COMPLEX_BODY),
    'reply-first': ('feedback-reply-email', 'first@example.invalid'),
    'reply-second': ('feedback-reply-email', 'second@example.invalid'),
    'reply-clear': ('feedback-reply-email', ''),
    'reply-malformed': ('feedback-reply-email', 'invalid-reply'),
    **{'daily-' + str(value): ('parent-custom-daily-limit', str(value))
       for value in (0, 1, 2, 3, 6, 7, 15, 1439)},
}
TEXT_VALUES.update({'daily-invalid-' + key: ('parent-custom-daily-limit', value)
                    for key, value in INVALID.items()})
TEXT_VALUES.update({'body-complex-' + str(lines): ('feedback-editor-input', '\n'.join(['x'] * lines))
                    for lines in (75, 150, 300, 600)})
# UI16's reusable, finite copy/append/paste route. Every source and result has
# an exact declared public projection; no clipboard daemon or external GUI.
TEXT_DUPLICATIONS = {
    'body-complex-150': 'body-complex-75',
    'body-complex-300': 'body-complex-150',
    'body-complex-600': 'body-complex-300',
    'body-complex': 'body-complex-600',
}
TEXT_DUPLICATION_SEPARATORS = dict.fromkeys(TEXT_DUPLICATIONS, '\n')
# Four independently built boundary fixtures: 312 typed characters -> 4,992
# through four copies, then only 6–9 typed characters. Keep every intermediate
# source/result finite and exact so a failed paste never triggers input replay.
TEXT_REPETITIONS = {}
TEXT_SUFFIXES = {}
for _binding in ('body-ascii-5000', 'body-ascii-5001',
                 'body-mixed-5000-base', 'body-mixed-5001-base'):
    _identity, _value = TEXT_VALUES[_binding]
    _chain = (_binding + '-seed', *(_binding + '-double-' + str(i) for i in range(1, 5)))
    for _i, _part in enumerate(_chain):
        TEXT_VALUES[_part] = (_identity, _value[:len(_value) // 16] * (2 ** _i))
        if _i:
            TEXT_DUPLICATIONS[_part] = _chain[_i - 1]
            TEXT_DUPLICATION_SEPARATORS[_part] = ''
    TEXT_REPETITIONS[_binding] = _chain
    TEXT_SUFFIXES[_binding] = (_chain[-1], _value[len(TEXT_VALUES[_chain[-1]][1]):])
SUFFIX_OPERATIONS = {f'text-suffix-{binding}-{action}': (binding, action)
                     for binding in TEXT_SUFFIXES for action in ('focus', 'caret', 'read')}
OPERATIONS |= frozenset(SUFFIX_OPERATIONS)
DUPLICATE_OPERATIONS = {
    'text-duplicate-' + binding + '-' + action: (binding, action)
    for binding in TEXT_DUPLICATIONS
    for action in ('focus', 'select', 'selected', 'read')
}
OPERATIONS |= frozenset(DUPLICATE_OPERATIONS)
TEXT_SCALARS = {f'body-mixed-{units}': (f'body-mixed-{units}-base', '1f600')
                for units in (5000, 5001)}
TEXT_SCALARS['body-smoke'] = ('body-first', '1f600')
SCALAR_OPERATIONS = {f'text-scalar-{binding}-{action}': (binding, action)
                     for binding in TEXT_SCALARS for action in ('focus', 'caret', 'read')}
OPERATIONS |= frozenset(SCALAR_OPERATIONS)
FORMAT_OPERATIONS = frozenset({
    'format-before', 'format-focus', 'format-home', 'format-selected',
    'format-read', 'format-close', 'format-wrong-entry', 'format-reopen',
})
OPERATIONS |= FORMAT_OPERATIONS
# Host probes import this as a package; the isolated guest payload installs
# these same helpers as top-level modules before executing this file.
if __package__:
    from . import block_semantics, feedback_formats
else:
    import block_semantics
    import feedback_formats
TEXT_VALUES['link-target'] = ('feedback-link-target', feedback_formats.LINK)
TEXT_VALUES['link-initial'] = ('feedback-link-target', block_semantics.BODY[
    feedback_formats.START:feedback_formats.END])
OPERATIONS |= feedback_formats.OPERATIONS
TEXT_VALUES['body-blocks'] = ('feedback-editor-input', block_semantics.BODY)
OPERATIONS |= block_semantics.OPERATIONS
WINDOW_SWITCH_OPERATIONS = frozenset({
    'switch-parent-before', 'switch-viewer-launch', 'switch-parent',
    'switch-draft-before', 'switch-viewer', 'switch-feedback',
    'switch-viewer-again', 'switch-feedback-again', 'switch-viewer-close',
    'switch-viewer-absent',
})
WINDOW_SWITCH_TARGETS = {
    'switch-parent': ('parent', 'viewer'),
    'switch-viewer': ('viewer', 'feedback'),
    'switch-feedback': ('feedback', 'viewer'),
    'switch-viewer-again': ('viewer', 'feedback'),
    'switch-feedback-again': ('feedback', 'viewer'),
    'switch-viewer-close': ('viewer', 'feedback'),
}
WINDOW_SWITCH_OPERATIONS |= frozenset(stage + '-ready' for stage in WINDOW_SWITCH_TARGETS)
OPERATIONS |= WINDOW_SWITCH_OPERATIONS

TEXT_OPERATIONS = {
    'text-' + binding + '-' + action: (binding, action)
    # The qualification controller consumes this order. Each native-entry
    # anchor must precede its focus proof, matching the worker's keyboard route.
    for binding in TEXT_VALUES if binding != 'body-hidden'
    for action in (('anchor', 'focus', 'selected', 'read')
                   if binding.startswith('reply-') else ('focus', 'selected', 'read'))
}
OPERATIONS |= frozenset(TEXT_OPERATIONS) | {'text-wrong-entry', 'text-disabled'}
CHILD_DESKTOP_OPERATIONS |= frozenset(operation for operation, (binding, _) in TEXT_OPERATIONS.items()
                                    if binding.startswith('overlay-'))
ALLOWANCE_OPERATIONS = frozenset({
    'allowance-wrong-child', 'allowance-disabled',
}) | frozenset(f'allowance-{value}-{action}' for value in PRESETS
              for action in ('select', 'read', 'reopen'))
OPERATIONS |= ALLOWANCE_OPERATIONS
TIME_EXPLANATION_OPERATIONS = frozenset({
    'time-explanation-collapse', 'time-explanation-collapsed',
    'time-explanation-expand', 'time-explanation-wrong-child',
    'time-explanation-read', 'time-explanation-reread',
    'time-explanation-reach-read', 'time-explanation-reach-reread',
    'time-explanation-reach-wrong-child', 'time-explanation-config-wrong-child',
    'time-explanation-config-wrong-state',
    'time-explanation-off-read', 'time-explanation-positive-read',
    'time-explanation-zero-read', 'time-explanation-zero-reread',
    'time-explanation-setup-zero-read', 'time-explanation-setup-positive-read',
    'time-explanation-setup-thirty-read',
})
OPERATIONS |= TIME_EXPLANATION_OPERATIONS
REVOKE_DISABLED_OPERATIONS = {
    'parent-revoke-disabled-on': True,
    'parent-revoke-disabled-off': False,
}
OPERATIONS |= REVOKE_DISABLED_OPERATIONS.keys()
OPERATIONS |= frozenset({'parent-new-window-absent', 'parent-new-window-refused'})
OPERATIONS |= frozenset({'parent-restart-ready', 'parent-restart-closed-refused',
                         'parent-restart-wrong-refused', 'parent-initial-selection'})


def duration_projection(text):
    """Registered compact public duration, at the formatter's second precision."""
    require(type(text) is str and len(text) <= 32, 'ui:time-duration')
    match = re.fullmatch(r'(?:(\d{1,6})h(?: ([1-5]?\d)m)?|([0-5]?\d)m)(?: ([1-5]?\d)s)?', text)
    require(match is not None, 'ui:time-duration')
    hours, minutes, only_minutes, seconds = (int(value or 0) for value in match.groups())
    return {'text': text, 'seconds': hours * 3600 + (minutes + only_minutes) * 60 + seconds,
            'precision_seconds': 1}


CUSTOM_ALLOWANCE_OPERATIONS = {
    'custom-' + str(value) + '-' + action: (value, action)
    for value in (0, 1, 2, 3, 6, 7, 15, 1439)
    for action in ('open', 'saved', 'reopen')
}
CUSTOM_ALLOWANCE_OPERATIONS.update({
    'custom-wrong-child': (1, 'wrong-child'),
    'custom-disabled': (1, 'disabled'),
})
OPERATIONS |= frozenset(CUSTOM_ALLOWANCE_OPERATIONS)
INVALID_ALLOWANCE_OPERATIONS = {'custom-invalid-' + key: key for key in INVALID}
OPERATIONS |= frozenset(INVALID_ALLOWANCE_OPERATIONS)
LICENSE_LINK = 'GNU General Public License v3.0'
ABOUT_FOOTER = '© 2026 Puffy Slippers Tech LLC\nGPL-3.0-only · No warranty.'
CHILD = 'Riley (Child)'
EXISTING_CHILD = 'Jordan (Child)'
NEW_CHILD = 'Morgan (Child)'
CHILD_IDENTITIES = {CHILD: 'fixture-child', EXISTING_CHILD: 'existing-fixture-child',
                    NEW_CHILD: 'new-fixture-child'}
CHILD_ACCOUNTS = {CHILD: 'onpc-child-riley', EXISTING_CHILD: 'onpc-child-jordan',
                  NEW_CHILD: 'onpc-e2e-new-child'}
PICKER_OPERATIONS = {
    'child-picker-opened': CHILD, 'new-child-picker-opened': NEW_CHILD,
    'existing-child-picker-opened': EXISTING_CHILD, 'discovery-child-picker-opened': EXISTING_CHILD,
}
HIGHLIGHT_OPERATIONS = {
    'child-choice-highlighted': CHILD, 'new-child-choice-highlighted': NEW_CHILD,
    'existing-child-choice-highlighted': EXISTING_CHILD,
    'discovery-child-choice-highlighted': EXISTING_CHILD,
}
SETTINGS_OPERATIONS = {
    'parent-screen-page': CHILD,
    'parent-selected': CHILD, 'parent-returned': CHILD, 'discovery-ready': EXISTING_CHILD,
    'parent-toggle-disabled-settings': CHILD,
    'discovery-selected': EXISTING_CHILD,
    'new-child-selected': NEW_CHILD, 'new-child-screen': NEW_CHILD, 'existing-returned': EXISTING_CHILD,
}
OPERATIONS |= frozenset(SETTINGS_OPERATIONS)
OPERATIONS |= frozenset({'parent-apps-page', 'parent-page-wrong-child-refused'})
APP_ROW_OPERATIONS = frozenset({
    'parent-app-rows', 'parent-app-rows-reopened',
    'parent-app-rows-wrong-child', 'parent-app-rows-wrong-page',
})
APP_ROW_OPERATIONS |= frozenset('existing-' + operation for operation in APP_ROW_OPERATIONS)
APP_ROW_OPERATIONS |= {'catalogue-incomplete-refused'}
APP_ROW_OPERATIONS |= {'catalogue-filter-wrong-child', 'catalogue-filter-wrong-page'}
CATALOGUE_ROW_OPERATIONS = {
    'catalogue-name-rows': 'catalogue-name', 'catalogue-name-reopened': 'catalogue-name',
    'catalogue-absent-rows': 'catalogue-absent', 'catalogue-absent-reopened': 'catalogue-absent',
    'catalogue-clear-rows': 'catalogue-clear',
    'catalogue-description-rows': 'catalogue-description',
    'catalogue-identifier-rows': 'catalogue-identifier',
}
APP_ROW_OPERATIONS |= frozenset(CATALOGUE_ROW_OPERATIONS)
FILTER_OPTIONS = {'match-rule': ('pattern', 'precise'),
                  'access-rule': ('allowed', 'conditional', 'permanent')}
FILTER_OPERATIONS = {
    f'filter-{kind}-{mask}-{action}': (kind, mask, action)
    for kind, options in FILTER_OPTIONS.items() for mask in range(1 << len(options))
    for action in ('open', *options, 'read', 'closed')
}
OPERATIONS |= frozenset(FILTER_OPERATIONS)
OPERATIONS |= APP_ROW_OPERATIONS
MATCH_APP = 'parent-app-' + hashlib.sha256(b'com.puffyslippers.ONPCTest.A.desktop').hexdigest()[:16]
MATCH_OTHER_APP = 'parent-app-' + hashlib.sha256(b'com.puffyslippers.ONPCTest.N.desktop').hexdigest()[:16]
MATCH_RULES = ('/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
               '/opt/onpc-test-fixtures/Applications/Exact*.AppImage',
               '/opt/onpc-test-fixtures/Applications/*.AppImage')
MATCH_OPERATIONS = frozenset('match-' + action for action in
    ('open', 'read', 'row', 'save', 'cancel', 'reset', 'rejected', 'wrong-app', 'ambiguous'))
MATCH_INVALID = {key: ('A match rule is required' if key in ('empty', 'whitespace') else
                      "A precise match must be this app's execution path")
                 for key in ('empty', 'whitespace', 'basename', 'absolute')}
MATCH_OPERATIONS |= frozenset('match-invalid-' + key for key in MATCH_INVALID)
OPERATIONS |= MATCH_OPERATIONS
PARENT_REPORT_OPERATIONS = frozenset({'parent-report-refused', 'parent-report-read',
                                      'parent-report-actions'})
OPERATIONS |= PARENT_REPORT_OPERATIONS
TEXT_VALUES['body-rule-error'] = ('feedback-editor-input',
    'Something went wrong\nThe operation could not be completed. Please try again later.'
    '\n\nError categories: Error')
ACCESS_CHOICES = ('allowed', 'permanent', 'conditional')
ACCESS_OPERATIONS = frozenset('access-' + action for action in
    (*ACCESS_CHOICES, 'row', 'screen', 'wrong-row', 'disabled'))
OPERATIONS |= ACCESS_OPERATIONS
LEGEND_HEADINGS = ('App Access (What happens)', 'Match Rule (How apps are matched)')
LEGEND_RULES = (
    ('allowed', 'Always Allowed', 'App can always be used'),
    ('conditional', 'Soft Blocked', 'App is blocked and can be granted one-time extension per child request if time limit is enabled'),
    ('permanent', 'Hard Blocked', 'App is completely blocked and can only be allowed by admins'),
    ('pattern', 'Pattern Match', 'Matches by pattern to cover exec path with changing version numbers (e.g., Lunar Client-*-ow_*.AppImage)'),
    ('precise', 'Precise execution path', 'Matches exact app path (e.g., /usr/bin/firefox)'),
)
LEGEND_OPERATIONS = frozenset({'policy-legend-expand', 'policy-legend-read',
                             'policy-legend-wrong-child', 'policy-legend-wrong-page'})
OPERATIONS |= LEGEND_OPERATIONS
TOGGLE_OPERATIONS = {
    'multiple-other-enable': {'state': True, 'activated': True},
    'parent-toggle-enabled': {'state': True, 'activated': True},
    'parent-toggle-disabled': {'state': False, 'activated': True},
    'parent-toggle-current': {'state': False, 'activated': False},
    'parent-toggle-wrong-refused': {'refusal': 'wrong-control'},
    'parent-toggle-hidden-refused': {'refusal': 'hidden-control', 'state': False},
}
OPERATIONS |= frozenset(TOGGLE_OPERATIONS)
ACCESSIBILITY_TRACE_OPERATIONS = frozenset((
    'feedback-collection-events', 'feedback-collection-open', 'feedback-collection-refused',
    'parent-checked-events', 'parent-save-events', 'parent-trace-wrong-child-refused',
    'parent-trace-wrong-surface-refused',
    'parent-custom-events', 'parent-custom-trace-focus',
    'parent-custom-trace-disabled-refused',
))
OPERATIONS |= ACCESSIBILITY_TRACE_OPERATIONS
NAMED_CUSTOM_OPERATIONS = frozenset(
    operation for operation, (_, action) in CUSTOM_ALLOWANCE_OPERATIONS.items()
    if action in ('open', 'saved', 'reopen')) | frozenset(
    operation for operation, (binding, _) in TEXT_OPERATIONS.items()
    if binding in ('daily-6', 'daily-7') or binding.startswith(('catalogue-', 'match-'))) | frozenset(FILTER_OPERATIONS) | MATCH_OPERATIONS | ACCESS_OPERATIONS | {
        'parent-custom-events', 'parent-custom-trace-focus',
        'parent-custom-trace-disabled-refused', 'named-custom-setup',
        'named-custom-wrong-child-refused', 'parent-trace-wrong-surface-refused',
    }
NAMED_CUSTOM_CHILDREN = {'child': CHILD, 'existing': EXISTING_CHILD}
NAMED_TIME_OPERATIONS = frozenset({
    'time-explanation-setup-thirty-read', 'time-explanation-read',
    'time-explanation-config-wrong-child', 'time-explanation-config-wrong-state',
})
NAMED_CHILD_OPERATIONS = NAMED_CUSTOM_OPERATIONS | NAMED_TIME_OPERATIONS
OPERATIONS |= NAMED_CUSTOM_OPERATIONS
PARENT_SAVE_OPERATIONS = {
    'multiple-other-saved': {
        'child': 'existing-fixture-child', 'result': 'saved', 'limit_enabled': True,
        'child_selector_enabled': True, 'toggle_enabled': True, 'allowance_enabled': True,
    },
    'parent-save-wrong-child-refused': {'refusal': 'wrong-child'},
    'parent-save-enabled': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': True,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': True,
    },
    'parent-save-reopened': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': True,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': True,
    },
    'parent-save-disabled': {
        'child': 'fixture-child', 'result': 'saved', 'limit_enabled': False,
        'child_selector_enabled': True, 'toggle_enabled': True,
        'allowance_enabled': False,
    },
}
OPERATIONS |= frozenset(PARENT_SAVE_OPERATIONS)
PARENT = 'Jamie (Parent)'
OTHER_PARENT = 'Casey (Parent)'
KIOSK = 'Oh No! Parent Control'
KIOSK_USERNAME = 'oh-no-parent-control'
GREETER_IDENTITIES = {PARENT: 'parent', OTHER_PARENT: 'other-parent',
                      CHILD: 'child', EXISTING_CHILD: 'other-child',
                      KIOSK: 'station', KIOSK_USERNAME: 'station'}
GDM_PROVIDER_CONTROLS = (
    'account-list',
    *(f'account-choice::{identity}' for identity in dict.fromkeys(GREETER_IDENTITIES.values())),
    'selected-recipient', 'password', 'submit', 'cancel', 'session-chooser',
    'session-choice::<provider-session-id>',
)
GREETER_OPERATIONS = frozenset({'gdm-list', 'gdm-focused', 'gdm-select-parent',
    'gdm-no-approver-refused',
    'gdm-no-child-refused',
    'gdm-navigation-returned', 'gdm-dismissed', 'gdm-returned',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-other-list', 'gdm-other-focused', 'gdm-wrong-recipient-refused',
    'gdm-parent-recipient', 'gdm-parent-recipient-rechecked',
    'gdm-standard-list', 'gdm-standard-focused', 'gdm-standard-wrong-recipient-refused',
    'gdm-standard-recipient', 'gdm-standard-recipient-rechecked',
    'gdm-station-wrong-entry-refused', 'gdm-station-list', 'gdm-station-focused',
    'gdm-station-returned'})
GREETER_NAVIGATION = frozenset({'gdm-list', 'gdm-other-list', 'gdm-standard-list',
                                'gdm-station-list', 'gdm-product-free-list'})
GREETER_OPERATIONS |= frozenset({'gdm-product-free-provider', 'gdm-installed-accounts'})
GREETER_OPERATIONS |= CHILD_GREETER_OPERATIONS
GREETER_NAVIGATION |= frozenset({'gdm-child-list'})
GDM_NONSECRET_OPERATIONS = frozenset({
    'gdm-list', 'gdm-focused', 'gdm-other-list', 'gdm-other-focused',
    'gdm-standard-list', 'gdm-standard-focused',
    'gdm-product-free-list', 'gdm-product-free-focused',
    'gdm-product-free-select-parent', 'gdm-product-free-returned',
    'gdm-station-wrong-entry-refused',
    'gdm-station-list', 'gdm-station-focused', 'gdm-station-returned',
})
GDM_SEMANTIC_APPLICATION_NAMES = frozenset({'gnome-shell', 'gnome shell'})
GDM_NONSECRET_OPERATIONS |= frozenset({'gdm-child-list', 'gdm-child-focused'})
GDM_ACCOUNT_ROLES = frozenset({'button', 'push button'})
GDM_DIAGNOSTIC_ROLES = frozenset({
    'application', 'button', 'push button', 'label', 'password text',
    'toggle button', 'radio button', 'menu item', 'radio menu item',
    'check menu item', 'combo box',
})
# G03 observation only: these are provider labels, never invented public IDs.
GDM_SESSION_LABELS = {
    'Session': 'session-chooser', 'Select Session': 'session-chooser',
    'Choose Session': 'session-chooser',
    'Oh No! Parent Control': 'station', 'GNOME': 'gnome',
    'GNOME on Xorg': 'gnome-xorg', 'Ubuntu': 'ubuntu',
    'Ubuntu on Xorg': 'ubuntu-xorg', 'Sign In': 'sign-in',
    'Log In': 'sign-in', 'Cancel': 'cancel',
}
KIOSK_OPERATIONS = frozenset({'kiosk-request-form', 'kiosk-child-choices-closed',
                              'kiosk-no-child-form', 'kiosk-no-approver-form'})
KIOSK_CHOICE_OPERATIONS = frozenset({'kiosk-child-choices-open', 'kiosk-approver-baseline',
    'multiple-child-open', 'multiple-approver-open'})
OPERATIONS |= KIOSK_OPERATIONS | KIOSK_CHOICE_OPERATIONS
KIOSK_ACCOUNT_REQUESTS = {
    'multiple-child-closed': ('existing-fixture-child', 'other-fixture-parent'),
    'multiple-approver-closed': ('existing-fixture-child', 'other-fixture-parent'),
    'multiple-preserved': ('existing-fixture-child', 'fixture-parent'),
    'multiple-first-child': ('fixture-child', 'other-fixture-parent'),
    'multiple-first-parent': ('fixture-child', 'fixture-parent'),
    'multiple-other-parent': ('fixture-child', 'other-fixture-parent'),
    'multiple-other-child': ('existing-fixture-child', 'other-fixture-parent'),
    'multiple-other-first-parent': ('existing-fixture-child', 'fixture-parent'),
    'kiosk-child-select': ('fixture-child', 'other-fixture-parent'),
    'kiosk-approver-select': ('fixture-child', 'fixture-parent'),
    'kiosk-enabled-form': ('fixture-child', 'fixture-parent'),
}
KIOSK_DISABLED_REQUESTS = {
    'kiosk-disabled-child-select': ('fixture-child', 'other-fixture-parent'),
    'kiosk-disabled-form': ('fixture-child', 'other-fixture-parent'),
}
KIOSK_ACCOUNT_REFUSALS = frozenset({'kiosk-choice-refusals', 'parent-kiosk-refused'})
KIOSK_VALID_REQUESTS = {
    **{f'kiosk-valid-{choice}-{action}': (seconds, custom, soft)
       for choice, seconds, custom, soft in (
           ('preset', 300, None, False), ('fraction', 75, '1.25', False),
           ('rest', 0, None, False), ('soft', 0, None, True),
           ('excluded', 0, None, False))
       for action in ('select', 'read') if choice != 'fraction' or action == 'read'},
}
KIOSK_VALID_REQUESTS.update({f'kiosk-valid-fraction-soft-{action}': (75, '1.25', True)
                             for action in ('select', 'read')})
KIOSK_VALID_REQUESTS.update({f'kiosk-flow-{field}-select': (75, '1.25', True)
                             for field in ('child', 'approver')})
KIOSK_VALID_OPERATIONS = frozenset(KIOSK_VALID_REQUESTS) | {'kiosk-valid-custom-open'}
OVERLAY_VALID_REQUESTS = {
    operation.replace('kiosk-', 'overlay-', 1): value
    for operation, value in KIOSK_VALID_REQUESTS.items() if operation.startswith('kiosk-valid-')
}
OVERLAY_VALID_REQUESTS['overlay-valid-approver-select'] = (1800, None, False)
OVERLAY_VALID_REQUESTS['overlay-valid-approver-read'] = (1800, None, False)
OVERLAY_VALID_REQUESTS['overlay-flow-approver-select'] = (75, '1.25', True)
OVERLAY_VALID_REQUESTS['overlay-valid-fraction-excluded-select'] = (75, '1.25', False)
OVERLAY_VALID_REQUESTS['overlay-valid-fraction-excluded-read'] = (75, '1.25', False)
OVERLAY_VALID_OPERATIONS = frozenset(OVERLAY_VALID_REQUESTS) | {
    'overlay-valid-custom-open', 'overlay-valid-refusals', 'overlay-request-cancel',
    'overlay-request-escape-ready'}
CHILD_DESKTOP_OPERATIONS |= OVERLAY_VALID_OPERATIONS
OPERATIONS |= OVERLAY_VALID_OPERATIONS
KIOSK_INVALID_OPERATIONS = {
    f'kiosk-invalid-{key}-{action}': (key, action)
    for key in KIOSK_INVALID_VALUES for action in ('ready', 'submit', 'read')
}
OVERLAY_INVALID_OPERATIONS = {
    operation.replace('kiosk-', 'overlay-', 1): binding
    for operation, binding in KIOSK_INVALID_OPERATIONS.items()
}
INVALID_REQUEST_OPERATIONS = {**KIOSK_INVALID_OPERATIONS, **OVERLAY_INVALID_OPERATIONS}
CHILD_DESKTOP_OPERATIONS |= frozenset(OVERLAY_INVALID_OPERATIONS)
OPERATIONS |= frozenset(OVERLAY_INVALID_OPERATIONS)
OPERATIONS |= frozenset(KIOSK_INVALID_OPERATIONS) | {'parent-kiosk-invalid-refused'}
OPERATIONS |= KIOSK_VALID_OPERATIONS | {'parent-kiosk-valid-refused'}
MATE_OPERATIONS = frozenset({'kiosk-mate-cancel', 'kiosk-mate-refusals-cancel'})
MULTIPLE_MATE_BINDINGS = {
    'multiple-first-first-cancel': (CHILD, PARENT),
    'multiple-first-other-cancel': (CHILD, OTHER_PARENT),
    'multiple-other-other-cancel': (EXISTING_CHILD, OTHER_PARENT),
    'multiple-other-first-cancel': (EXISTING_CHILD, PARENT),
}
MATE_OPERATIONS |= frozenset(MULTIPLE_MATE_BINDINGS)
MATE_APPROVAL_OPERATIONS = frozenset({'kiosk-mate-open', 'kiosk-mate-qualified',
                                     'kiosk-mate-rechecked', 'kiosk-mate-submit-success'})
MATE_REJECTION_ORDER = ('kiosk-mate-rejection-open', 'kiosk-mate-rejection-qualified',
                        'kiosk-mate-rejection-rechecked', 'kiosk-mate-submit-rejection')
MATE_APPROVAL_OPERATIONS |= frozenset(MATE_REJECTION_ORDER)
MATE_APPROVAL_OPERATIONS |= frozenset({'kiosk-mate-submit-immediate'})
OPERATIONS |= MATE_APPROVAL_OPERATIONS
MATE_REFUSALS = ('wrong-agent', 'owner', 'recipient', 'child', 'duration', 'apps',
                 'multiple-fields', 'hidden', 'disabled', 'unfocused', 'nonempty',
                 'stale', 'replaced')
OPERATIONS |= MATE_OPERATIONS | {'parent-mate-refused'}
OPERATIONS |= frozenset(KIOSK_ACCOUNT_REQUESTS) | frozenset(KIOSK_DISABLED_REQUESTS) | KIOSK_ACCOUNT_REFUSALS
KIOSK_EXIT_OPERATIONS = frozenset({'kiosk-request-cancel',
                                   'kiosk-request-escape-ready'})
KIOSK_SESSION_OPERATIONS = (KIOSK_OPERATIONS | KIOSK_EXIT_OPERATIONS | KIOSK_CHOICE_OPERATIONS
                            | frozenset(KIOSK_ACCOUNT_REQUESTS) | frozenset(KIOSK_DISABLED_REQUESTS)
                            | {'kiosk-choice-refusals'})
KIOSK_SESSION_OPERATIONS |= KIOSK_VALID_OPERATIONS | frozenset(KIOSK_INVALID_OPERATIONS) | frozenset(
    operation for operation, (binding, _) in TEXT_OPERATIONS.items()
    if binding.startswith('kiosk-'))
STATION_BRANCH_OPERATIONS = frozenset({'station-entry-branch', 'station-default-entry'})
KIOSK_SESSION_OPERATIONS |= MATE_OPERATIONS | MATE_APPROVAL_OPERATIONS
KIOSK_RESTRICTION_OPERATIONS = frozenset({
    'kiosk-restriction-ready', 'kiosk-restriction-read',
    'kiosk-restriction-prepared-ready', 'kiosk-restriction-prepared-read',
})
OPERATIONS |= KIOSK_RESTRICTION_OPERATIONS
KIOSK_SESSION_OPERATIONS |= KIOSK_RESTRICTION_OPERATIONS
KIOSK_ABOUT_OPERATIONS = frozenset({'kiosk-about-open', 'kiosk-about-read',
                                   'kiosk-about-close-ready', 'kiosk-about-closed'})
OPERATIONS |= KIOSK_ABOUT_OPERATIONS | {'parent-kiosk-about-refused'}
KIOSK_SESSION_OPERATIONS |= KIOSK_ABOUT_OPERATIONS
APPROVER_IDENTITIES = {OTHER_PARENT: 'other-fixture-parent', PARENT: 'fixture-parent'}
APPROVER_ACCOUNTS = {OTHER_PARENT: 'onpc-parent-casey', PARENT: 'onpc-parent-jamie'}
# Public-ID inventory for external applications on the maintained Ubuntu 26.04
# host.  An observed Builder ID is recorded only when the installed provider
# owns it; it is not usable until the application and surface roots are also
# ID-addressable. ``None`` is an exact provider-ID gap. Scoped provider
# adapters such as G01 may still use the separately reviewed semantic contract;
# generic label, object-name, tree-position and geometry fallbacks stay refused.
EXTERNAL_PROVIDER_CONTRACTS = {
    'gnome-shell': {
        'application_id': None,
        'surfaces': {
            'desktop': (None, {
                'desktop': None, 'launcher': None,
            }),
            'panel': (None, {
                'activities': None, 'app-grid': None,
            }),
            'app-grid': (None, {
                'search': None, 'result::parent': None,
                'web-suggestion::parent': None,
            }),
            'notifications': (None, {'notification': None, 'dismiss': None}),
            'lock-screen': (None, {'recipient': None, 'password': None, 'unlock': None}),
        },
        # System session/power/network inputs use session_control and guarded
        # commands. Only their required public results need a GUI provider.
        'blocked_consumers': ('DESK01 desktop observation', 'DESK06-08 lock/unlock',
                              'DESK10 window activation', 'DESK12 panel reveal',
                              'SEARCH01-06', 'PANEL01-03'),
    },
    'ding-desktop': {
        'application_id': None,
        'surfaces': {
            'desktop': (None, {'desktop': None, 'file': None, 'launcher': None}),
        },
        'blocked_consumers': ('DESK desktop-icon routes', 'native desktop launch'),
    },
    'gdm': {
        'application_id': None,
        'surfaces': {
            'greeter': (None, {
                'account-list': None,
                'account-choice::parent': None,
                'account-choice::other-parent': None,
                'account-choice::child': None,
                'account-choice::other-child': None,
                'account-choice::station': None,
                'selected-recipient': None, 'password': None,
                'submit': None, 'cancel': None,
                'session-chooser': None,
                'session-choice::<provider-session-id>': None,
            }),
        },
        'blocked_consumers': ('GDM account selection/login', 'greeter result observation',
                              'kiosk entry'),
    },
    'gnome-shell-polkit-agent': {
        'application_id': None,
        'surfaces': {
            'polkit': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('authentication', 'recipient safety'),
    },
    'mate-polkit-agent': {
        'application_id': None,
        'surfaces': {
            'polkit': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('station authentication', 'recipient safety'),
    },
    'gcr-keyring-prompter': {
        'application_id': None,
        'surfaces': {
            'keyring': (None, {
                'recipient': None, 'secret': None, 'confirm': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('keyring unlock', 'recipient safety', 'prompt dismissal'),
    },
    'gtk-file-chooser': {
        'application_id': None,
        'surfaces': {
            'file-chooser': (None, {
                'location': None, 'file-choice': None,
                'accept': None, 'cancel': None,
            }),
        },
        'blocked_consumers': ('FILE03 native chooser route',
                              'FEED06 native chooser route',
                              'FEED08 native diagnostic-save route'),
    },
    'xdg-desktop-portal-gnome-nautilus': {
        'application_id': None,
        'surfaces': {
            'file-chooser': (None, {
                # These GTK 4 Builder IDs are published by the installed
                # Nautilus provider, but the dialog, cancel action and dynamic
                # file choices have no provider-owned IDs.
                'location': 'filename_entry', 'file-choice': None,
                'accept': 'accept_button', 'cancel': None,
            }),
        },
        'blocked_consumers': ('FILE03 portal route', 'FEED06 portal route',
                              'FEED08 portal diagnostic-save route'),
    },
    'gnome-text-editor': {
        'application_id': None,
        'surfaces': {
            'license-document': (None, {'content': None, 'close': None}),
            'ordinary-document': (None, {
                'content': None, 'save': None, 'close': None,
            }),
        },
        'blocked_consumers': ('ABOUT02', 'FILE08',
                              'FEED08 saved-output review', 'retained-work scenarios'),
    },
    'document-viewer': {
        'application_id': None,
        'surfaces': {
            'license-document': (None, {'content': None, 'close': None}),
        },
        'blocked_consumers': ('ABOUT02', 'ABOUT03'),
    },
    'gnome-papers': {
        'application_id': None,
        'surfaces': {
            'document': (None, {'content': None, 'close': None}),
        },
        'blocked_consumers': ('PDF saved-output review',),
    },
    'gnome-nautilus': {
        'application_id': None,
        'surfaces': {
            'files': (None, {'directory-row': None, 'file-row': None, 'open': None}),
        },
        'blocked_consumers': ('FILE04 tested file-manager launch',),
    },
    'gnome-file-roller': {
        'application_id': None,
        'surfaces': {
            'archive': (None, {'archive-content': None, 'extract': None, 'close': None}),
        },
        'blocked_consumers': ('FILE08 archive review', 'FEED08 archive review'),
    },
}


class UiError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise UiError(code)


def _public_automation_id(node, attributes):
    if attributes is None:
        # A provider can disappear between traversal and this query. With no
        # attributes its ID contract cannot be qualified, so treat the stale
        # node as unidentified rather than accepting a transient AccessibleId.
        return ''
    if attributes.get('toolkit') == 'WebKitGTK':
        return attributes.get('id', '')
    return node.get_accessible_id()


def public_automation_id(node):
    """Normalize the provider's public stable ID, without selector fallbacks.

    GTK/ATK publish application IDs as AccessibleId. WebKitGTK instead uses
    AccessibleId for a transient AX object number and publishes the document's
    explicit control ID in AT-SPI GetAttributes. Select that contract by the
    provider's toolkit attribute, never by a label, role or tree position.
    Keep this here so the standalone guest reader and preview reader share it.
    """
    return _public_automation_id(node, node.get_attributes())


def public_action_name(api, action, index):
    """Work around only GI's incorrect deprecation of the public rename."""
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',
                                message=r'^Atspi\.Action\.get_action_name is deprecated$',
                                category=DeprecationWarning)
        return api.Action.get_action_name(action, index)


def owned_surface_id(identity):
    """The public containing surface for repository-owned control namespaces.

    Longest/specialized prefixes precede their shared window namespace. These
    are product IDs, not external-provider aliases or label-derived selectors.
    A surface itself is discovered by its unique ID by the caller.
    """
    fixture = re.match(r'^(onpc-fixture-(?:native|flatpak|snap|game)-(?:primary|secondary))(?:-|$)', identity)
    if fixture:
        return None if identity == fixture[1] else fixture[1]
    if identity in ('child-request-tooltip', 'child-countdown-menu'):
        return None  # Shell chrome siblings; application ownership is checked separately.
    for prefix, surface in (
        ('parent-access-denied-', 'parent-access-denied-window'),
        ('parent-revoke-', 'parent-revoke-dialog'),
        ('parent-match-rule-', 'parent-match-rule-dialog'),
        ('language-', 'language-dialog'),
        ('feedback-full-privacy-', 'feedback-privacy-dialog'),
        ('feedback-privacy-', 'feedback-privacy-dialog'),
        ('feedback-success-', 'feedback-success-dialog'),
        ('error-report-unavailable-', 'error-report-unavailable-dialog'),
        ('startup-error-', 'startup-error-window'),
        ('preview-screen-', 'preview-screen-dialog'),
        ('preview-viewer-', 'preview-viewer-window'),
        ('e2e-watch-', 'watch-window'),
        ('ui-watch-', 'watch-window'),
        ('watch-', 'watch-window'),
        ('about-', 'about-dialog'),
        ('feedback-', 'feedback-dialog'),
        ('parent-', 'parent-window'),
        ('kiosk-', 'kiosk-request-window'),
        ('child-countdown-', 'child-countdown-menu'),
        ('child-', 'child-screen-time-indicator'),
    ):
        if identity.startswith(prefix):
            # The privacy link opens the modal and the revoke button opens its
            # confirmation; both belong to their original containing window.
            if identity == 'feedback-privacy-link':
                return 'feedback-dialog'
            if identity == 'parent-revoke-button':
                return 'parent-window'
            if identity in ('parent-language-loading', 'parent-language-ready'):
                return 'parent-window'
            return None if identity == surface else surface
    return None


PARENT_APPLICATION = 'com.puffyslippers.OhNoParentControl.Parent'
KIOSK_APPLICATION = 'com.puffyslippers.OhNoParentControl'
CHILD_APPLICATION = 'com.puffyslippers.OhNoParentControl.ChildRequest'
WATCH_APPLICATION = 'org.onpc.E2EWatch'
PRODUCT_APPLICATIONS = (PARENT_APPLICATION, KIOSK_APPLICATION, CHILD_APPLICATION)


def owned_applications(identity):
    fixture = re.match(r'^onpc-fixture-(native|flatpak|snap|game)-(primary|secondary)(?:-|$)', identity)
    if fixture:
        return (f'com.puffyslippers.ONPCFixture.{fixture[1]}.{fixture[2]}',)
    if identity.startswith(('e2e-watch-', 'ui-watch-', 'watch-')):
        return (WATCH_APPLICATION,)
    if identity.startswith('parent-'):
        return (PARENT_APPLICATION,)
    if identity.startswith(('kiosk-', 'preview-screen-')):
        return (KIOSK_APPLICATION, CHILD_APPLICATION)
    if identity.startswith('preview-viewer-'):
        return ('com.puffyslippers.ScreenPreview',)
    if identity.startswith(('language-', 'about-', 'feedback-', 'startup-error-', 'error-report-')):
        return PRODUCT_APPLICATIONS
    return ()


KIOSK_DIAGNOSTIC_IDS = (
    KIOSK_APPLICATION, CHILD_APPLICATION, 'kiosk-request-window', 'kiosk-request-form',
    'kiosk-child-selector', 'kiosk-approver-selector', 'kiosk-request-submit',
    'kiosk-request-cancel', 'kiosk-soft-apps-toggle', 'kiosk-screen-limit-notice',
    'kiosk-mute-button', 'kiosk-custom-duration',
    *(f'kiosk-duration-{value}' for value in (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')),
)
KIOSK_DIAGNOSTIC_PHASES = frozenset({
    'start', 'dispatch', 'prompt-check', 'public-tree', 'public-ids',
    'form-tree', 'form-states', 'duration-states', 'message',
    'selected-child', 'selected-approver', 'projection', 'reset-reader',
    *KIOSK_DIAGNOSTIC_IDS,
})


class KioskDiagnostic:
    """Bounded public-read progress, never an identity or acceptance proof.

    Flush first visits before accessibility calls so even a transport timeout
    retains the last phase. Counts describe only a completed public snapshot;
    failed snapshots explicitly invalidate them. No UI text or exception text.
    """

    def __init__(self):
        self.started = time.monotonic()
        self.phase = 'start'
        self.tree = 'unread'
        self.ids = {}
        self.tree_reads = self.nodes_read = self.incomplete = self.query_errors = 0
        self.emitted = set()

    def check(self):
        # A predicate can perform many individually bounded AT-SPI calls. The
        # wait-loop deadline alone does not bound that work. Native calls retain
        # Atspi.set_timeout's existing 2s/5s limits.
        require(time.monotonic() - self.started < 90, 'ui:timeout:kiosk-request-form')

    def emit(self, phase=None, status='reading'):
        if phase is not None:
            require(phase in KIOSK_DIAGNOSTIC_PHASES, 'ui:diagnostic-phase')
            self.phase = phase
        key = (self.phase, status)
        if key in self.emitted or (len(self.emitted) >= 64 and status == 'reading'):
            return
        self.emitted.add(key)
        print(json.dumps({
            'event': 'kiosk-form-observation', 'phase': self.phase, 'status': status,
            'elapsed_ms': int((time.monotonic() - self.started) * 1000),
            'tree': self.tree, 'public_ids': self.ids,
            'tree_reads': self.tree_reads, 'nodes_read': self.nodes_read,
            'incomplete_reads': self.incomplete, 'query_errors': self.query_errors,
        }, sort_keys=True), flush=True)


CHOOSER_FILES = ('Second note.txt', 'Synthetic note.txt')
CHOOSER_DIRECTORY = '/home/onpc-parent-jamie/.onpc-e2e-synthetic-files'
CHOOSER_OPERATIONS = frozenset('chooser-' + suffix for suffix in (
    'wrong-entry', 'open', 'location', 'files', 'accept', 'attachments',
    'reopen', 'cancel', 'preserved'))
OPERATIONS |= CHOOSER_OPERATIONS
SAVE_DIRECTORY = str(download_directory('/home/onpc-parent-jamie'))
SAVE_NAMES = ('Selected diagnostics.zip', 'Cancelled diagnostics.zip')
SAVE_OPERATIONS = frozenset('save-chooser-' + suffix for suffix in (
    'wrong-entry', 'open', 'name', 'location', 'navigated', 'destination', 'restored', 'accept',
    'result', 'reopen', 'cancel-name', 'cancel', 'preserved'))
SAVE_OPERATIONS |= frozenset('export-' + operation for operation in SAVE_OPERATIONS)
SAVE_OPERATIONS |= frozenset('denied-export-save-chooser-' + suffix for suffix in (
    'open', 'name', 'location', 'navigated', 'destination', 'restored', 'accept', 'result'))
OPERATIONS |= SAVE_OPERATIONS
DRAFT_OPERATIONS = frozenset('draft-' + name for name in (
    'chooser-open', 'chooser-location', 'chooser-files', 'chooser-accept',
    'feedback-draft', 'feedback-draft-reread', 'feedback-draft-reopen',
    'feedback-privacy-open', 'feedback-privacy-returned',
    'feedback-reopen', 'feedback-reread',
    'switch-draft-before', 'switch-feedback'))
OPERATIONS |= DRAFT_OPERATIONS
FILE_REVIEW_OPERATIONS = frozenset('files-' + name for name in (
    'feedback-draft', 'feedback-draft-reread', 'feedback-draft-reopen',
    'feedback-privacy-open', 'feedback-privacy-returned',
    'switch-draft-before', 'switch-feedback'))
OPERATIONS |= FILE_REVIEW_OPERATIONS
ATTACHMENT_OPERATIONS = frozenset(('attachment-details', 'attachment-remove',
                                  'attachment-remaining', 'attachment-wrong-entry',
                                  'attachment-preview', 'attachment-preview-return'))
OPERATIONS |= ATTACHMENT_OPERATIONS
ATTACHMENT_INPUTS = (('Second note.txt', b'ONPC second synthetic attachment\n'),
                     ('Synthetic note.txt', b'ONPC synthetic attachment\n'))
ATTACHMENT_LABEL_ACTIONS = frozenset((
    'clipboard.copy', 'selection.delete', 'clipboard.paste', 'link.open',
    'clipboard.cut', 'link.copy', 'menu.popup', 'selection.select-all'))

# Finite customer inputs, not an arbitrary-path or attachment injection API.
BOUNDARY_FILES = {
    'single': (('Synthetic note.txt', b'ONPC synthetic attachment\n'),),
    'count': tuple((f'Count {index}.txt', b'C') for index in range(1, 6)),
    'sixth': (('Count 6.txt', b'C'),),
    'maximum': (('Maximum.txt', b'M' * (5 * 1024 * 1024)),),
    'oversized': (('Oversized.txt', b'O' * (5 * 1024 * 1024 + 1)),),
    'total': (('Total.txt', b'T' * (3 * 1024 * 1024)),),
    'overflow': (('Overflow.txt', b'X' * (3 * 1024 * 1024 + 1)),),
    'name180': (('N' * 176 + '.txt', b'N'),),
    'name181': (('N' * 177 + '.txt', b'N'),),
    'hidden': (('Hidden\u200b.txt', b'H'),),
    'mixed': (('Accepted.txt', b'A'), ('Oversized.txt', b'O' * (5 * 1024 * 1024 + 1))),
}
CHANGED_ATTACHMENT = (('Synthetic note.txt', b'ONPC changed synthetic attachment\n'),)
BOUNDARY_STATES = {
    'empty': ((), '2 file attachments ready.', True),
    'count': (BOUNDARY_FILES['count'], '5 file attachments ready.', True),
    'count-rejected': (BOUNDARY_FILES['count'], 'Attach at most 5 files.', True),
    'cleared': ((), 'Attach at most 5 files.', True),
    'no-logs': ((), 'Attach at most 5 files.', False),
    'maximum': (BOUNDARY_FILES['maximum'], '1 file attachment ready.', False),
    'oversized-rejected': (BOUNDARY_FILES['maximum'], 'Each attachment must be 5 MB or smaller.', False),
    'total': (BOUNDARY_FILES['maximum'] + BOUNDARY_FILES['total'], '2 file attachments ready.', False),
    'maximum-again': (BOUNDARY_FILES['maximum'], '2 file attachments ready.', False),
    'overflow-rejected': (BOUNDARY_FILES['maximum'], 'Attachments and diagnostic logs must total 8 MB or less.', False),
    'large-cleared': ((), 'Attachments and diagnostic logs must total 8 MB or less.', False),
    'name180': (BOUNDARY_FILES['name180'], '1 file attachment ready.', False),
    'name-rejected': (BOUNDARY_FILES['name180'], 'Choose an attachment with a shorter valid filename.', False),
    'mixed-rejected': (BOUNDARY_FILES['name180'], 'Each attachment must be 5 MB or smaller.', False),
    'names-cleared': ((), 'Each attachment must be 5 MB or smaller.', False),
    'single': (BOUNDARY_FILES['single'], '1 file attachment ready.', False),
    'single-cleared': ((), '1 file attachment ready.', False),
    'changed': (CHANGED_ATTACHMENT, '1 file attachment ready.', False),
}
BOUNDARY_BATCHES = {
    'count': ('empty', 'count'), 'sixth': ('count', 'count-rejected'),
    'maximum': ('no-logs', 'maximum'), 'oversized': ('maximum', 'oversized-rejected'),
    'total': ('oversized-rejected', 'total'), 'overflow': ('maximum-again', 'overflow-rejected'),
    'name180': ('large-cleared', 'name180'), 'name181': ('name180', 'name-rejected'),
    'hidden': ('name-rejected', 'name-rejected'), 'mixed': ('name-rejected', 'mixed-rejected'),
    'single': ('names-cleared', 'single'), 'changed': ('single-cleared', 'changed'),
}
BOUNDARY_REMOVALS = {
    'boundary-clear-maximum': ('overflow-rejected', 'large-cleared'),
    'boundary-clear-name': ('mixed-rejected', 'names-cleared'),
    'boundary-remove-single': ('single', 'single-cleared'),
}
BOUNDARY_OPERATIONS = frozenset(
    ['boundary-clear-small', 'boundary-clear-count', 'boundary-exclude-logs', 'boundary-remove-total',
     'boundary-source-unchanged', *BOUNDARY_REMOVALS]
    + [f'boundary-{batch}-{step}' for batch in BOUNDARY_BATCHES
       for step in ('before', 'open', 'location', 'files', 'accept', 'result', 'preserved')])
OPERATIONS |= BOUNDARY_OPERATIONS


def attachment_size(data):
    size = len(data)
    return ('1 byte' if size == 1 else f'{size} bytes' if size < 1024 else f'{size / 1024:.1f} KB' if size < 1024 * 1024
            else f'{size / (1024 * 1024):.1f} MB')


def boundary_expected(operation):
    require(operation in BOUNDARY_OPERATIONS, 'ui:boundary-operation')
    transitions = {'boundary-clear-small': 'empty', 'boundary-clear-count': 'cleared',
                   'boundary-exclude-logs': 'no-logs', 'boundary-remove-total': 'maximum-again',
                   'boundary-source-unchanged': 'single',
                   **{key: value[1] for key, value in BOUNDARY_REMOVALS.items()}}
    if operation in transitions:
        state = BOUNDARY_STATES[transitions[operation]]
    else:
        _, batch, step = operation.split('-')
        if step in ('open', 'location', 'files', 'accept'):
            return {'checked': operation}
        state = BOUNDARY_STATES[BOUNDARY_BATCHES[batch][0 if step == 'before' else 1]]
    return {'checked': operation, 'items': [[name, attachment_size(data)] for name, data in state[0]],
            'status': state[1], 'include_logs': state[2]}


def validate_chooser_portal_owner(query, caller_pid, provider_pid):
    """Bind the sole Nautilus request to its public portal caller identity.

    Portal windows import a Wayland parent surface, not a GtkWindow, so GTK
    cannot publish CONTROLLED_BY across that boundary. The documented Request
    path embeds the caller's session-bus name. Nautilus exports that same
    handle for exactly the lifetime of its chooser. Require one request and
    one chooser, never infer ownership from a translated window title.
    """
    from xml.etree import ElementTree

    bus = 'org.freedesktop.DBus'
    bus_path = '/org/freedesktop/DBus'
    def dbus(method, name):
        return query(bus, bus_path, bus, method, 's', (name,))
    def inspect(owner, path):
        xml = query(owner, path, 'org.freedesktop.DBus.Introspectable', 'Introspect', '', ())
        require(type(xml) is str and len(xml) <= 65536 and '<!ENTITY' not in xml,
                'ui:chooser-request-observation')
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as error:
            raise UiError('ui:chooser-request-observation') from error
        require(root.tag == 'node', 'ui:chooser-request-observation')
        return root
    owner = dbus('GetNameOwner', 'org.gnome.Nautilus')
    require(type(owner) is str and re.fullmatch(r':[0-9]+\.[0-9]+', owner),
            'ui:chooser-provider-owner')
    require(dbus('GetConnectionUnixProcessID', owner) == provider_pid,
            'ui:chooser-provider-owner')
    base = '/org/freedesktop/portal/desktop/request'
    senders = inspect(owner, base).findall('node')
    require(len(senders) == 1, 'ui:chooser-request-ambiguous')
    sender = senders[0].get('name', '')
    require(re.fullmatch(r'[0-9]+_[0-9]+', sender), 'ui:chooser-request-caller')
    caller_name = ':' + sender.replace('_', '.')
    require(dbus('GetConnectionUnixProcessID', caller_name) == caller_pid,
            'ui:chooser-request-caller')
    tokens = inspect(owner, base + '/' + sender).findall('node')
    require(len(tokens) == 1, 'ui:chooser-request-ambiguous')
    token = tokens[0].get('name', '')
    require(re.fullmatch(r'[A-Za-z0-9_]{1,255}', token), 'ui:chooser-request-token')
    path = base + '/' + sender + '/' + token
    for service, interface in ((owner, 'org.freedesktop.impl.portal.Request'),
                               ('org.freedesktop.portal.Desktop', 'org.freedesktop.portal.Request')):
        interfaces = [item.get('name') for item in inspect(service, path).findall('interface')]
        require(interfaces.count(interface) == 1, 'ui:chooser-request-interface')
    require(dbus('GetNameOwner', 'org.gnome.Nautilus') == owner
            and dbus('GetConnectionUnixProcessID', caller_name) == caller_pid,
            'ui:chooser-request-replaced')


class AccessibleUI:
    """Fresh semantic lookup, bounded waits, unique targets and public actions.

    Appearance/coordinates are deliberately absent from the acceptance model.
    Hidden or disabled controls cannot authorize input. An action's return value
    is not success: callers must independently observe its resulting UI state.
    """

    def __init__(self, api, *, timeout=45, query_errors=(), dispatch=None,
                 reset_observer=None, provider_contracts=None, fixture_uids=None,
                 application_ids=None, owner_pids=None, application_owners=None,
                 application_owner_history=None, root=None, include_text_children=False,
                 timing=None):
        if root is None and getattr(api, '__name__', '') == 'gi.repository.Atspi':
            # Real previews and installed observers use the same public bus
            # client. In-memory doubles retain their small native facade.
            try:
                from public_atspi import PublicAtspi
            except ImportError:
                from tests.e2e.public_atspi import PublicAtspi
            api = PublicAtspi(api)
        self.api = api
        self.root = root if root is not None else lambda: self.api.get_desktop(0)
        self.include_text_children = include_text_children
        self.timing = timing
        self._timing = None
        self.timeout = timeout
        self.query_errors = query_errors
        self.dispatch = dispatch
        self.last_roles = set()
        self.prompt_enabled = False
        self.prompt_session = None
        self.handling_prompt = False
        self.reset_observer = reset_observer
        self.provider_contracts = (EXTERNAL_PROVIDER_CONTRACTS if provider_contracts is None
                                   else provider_contracts)
        # Preview callers provide their declared fixture UIDs. Installed callers
        # resolve the fixed fixture account, never infer identity from UI labels.
        self.fixture_uids = fixture_uids
        self.application_ids = application_ids
        self.owner_pids = owner_pids
        self.application_owners = application_owners
        self.application_owner_history = application_owner_history
        self._observation_cache = None
        self._observation_generation = 0
        self._projection_cache = {}
        self.input_uncertain = False
        self.incomplete_observations = []
        self.gdm_row_diagnostic_emitted = False
        self.kiosk_diagnostic = None

    @property
    def input_uncertain(self):
        return self._input_uncertain

    @input_uncertain.setter
    def input_uncertain(self, value):
        # Every public input sets this latch before dispatch. No read captured
        # before an action may authorize its result, even inside a predicate.
        if value:
            self.invalidate_observation()
        self._input_uncertain = value

    def invalidate_observation(self):
        """End the current read boundary before input, retry or client reset."""
        self._observation_generation += 1
        if self._observation_cache is not None:
            self._observation_cache.clear()
        self._projection_cache.clear()
        invalidate = getattr(self.api, 'invalidate_snapshot', None)
        if invalidate is not None:
            invalidate()

    @contextmanager
    def observation(self):
        """Share complete reads across composed helpers until input or retry.

        The operation entry point and standalone waits open this scope. Nested
        helpers reuse it without knowing the element/provider being observed.
        Input, a pending predicate, or an accessibility-client reset invalidates
        it. Leaving the outermost scope discards all observations.
        """
        previous = self._observation_cache
        if previous is None:
            self._observation_cache = []
        try:
            yield
        except BaseException:
            self.invalidate_observation()
            raise
        finally:
            if previous is None:
                self._observation_cache = None
                self._projection_cache.clear()

    def nodes(self, root=None, *, strict=False, protected_ids=(), protect_text=False,
              snapshot=None, facts=None, identities=None):
        """Reuse complete reads only within an explicit observation boundary."""
        protected_ids = frozenset(protected_ids)
        if self._observation_cache is None:
            yield from self._read_nodes(
                root, strict=strict, protected_ids=protected_ids, protect_text=protect_text,
                snapshot=snapshot, facts=facts, identities=identities)
            return
        root = root if root is not None else self.root()
        protection = (frozenset(protected_ids), protect_text)
        for policy, read_nodes, edges, read_facts, read_ids in reversed(self._observation_cache):
            if policy == protection and root in edges:
                selected = (read_nodes if root == read_nodes[0] else
                            self.snapshot_scope(read_nodes, edges, root))
                if not strict and not self.include_text_children:
                    # Preserve the legacy reader's text-child exclusion when
                    # projecting a complete strict read; never broaden a scope.
                    allowed, pending = set(), [root]
                    while pending:
                        node = pending.pop()
                        if node in allowed:
                            continue
                        allowed.add(node)
                        if read_facts[node]['role'] not in ('text', 'entry'):
                            pending.extend(edges[node])
                    selected = [node for node in selected if node in allowed]
                break
        else:
            if not strict:
                # A tolerant read can silently omit unavailable subtrees and
                # therefore can never seed a later complete observation.
                yield from self._read_nodes(
                    root, strict=False, protected_ids=protected_ids, protect_text=protect_text,
                    snapshot=snapshot, facts=facts, identities=identities)
                return
            edges, read_facts, read_ids = {}, {}, {}
            try:
                selected = list(self._read_nodes(
                    root, strict=True, protected_ids=protected_ids, protect_text=protect_text,
                    snapshot=edges, facts=read_facts, identities=read_ids))
            except BaseException:
                self.invalidate_observation()
                raise
            # Publish only after traversal completes. Partial reads, including
            # query errors and missing children, never enter the reusable set.
            # Freeze once so shared snapshots need no per-helper deep copies.
            edges = MappingProxyType({node: tuple(children) for node, children in edges.items()})
            read_facts = MappingProxyType({node: MappingProxyType(record)
                                          for node, record in read_facts.items()})
            read_ids = MappingProxyType(read_ids)
            selected = read_nodes = tuple(selected)
            self._observation_cache.append((protection, selected, edges, read_facts, read_ids))
        # The compatibility projections remain independent mutable containers.
        # Hot callers use read_snapshot() to share the immutable original.
        if snapshot is not None:
            snapshot.update({node: ([] if not strict and not self.include_text_children
                                   and read_facts[node]['role'] in
                                   ('text', 'entry') else list(edges[node]))
                             for node in selected})
        if facts is not None:
            facts.update({node: dict(read_facts[node]) for node in selected})
        if identities is not None:
            identities.update({node: read_ids[node] for node in selected})
        yield from selected

    def read_snapshot(self, root=None, *, protected_ids=(), protect_text=False):
        """Return an immutable complete observation, reusable until input/retry.

        Public nodes() projections may be edited by their caller. Only this
        engine's immutable originals can seed cached scopes or ID indexes.
        """
        root = self.root() if root is None else root
        protected_ids = frozenset(protected_ids)
        policy = (protected_ids, protect_text)
        with self.observation():
            for protection, nodes, edges, facts, identities in reversed(self._observation_cache):
                if protection == policy and root in edges:
                    break
            else:
                tuple(self.nodes(root, strict=True, protected_ids=protected_ids,
                                 protect_text=protect_text))
                protection, nodes, edges, facts, identities = self._observation_cache[-1]
            selected = nodes if root == nodes[0] else self.snapshot_scope(nodes, edges, root)
            return selected, edges, identities, facts

    def _read_nodes(self, root=None, *, strict=False, protected_ids=(), protect_text=False,
                    snapshot=None, facts=None, identities=None):
        started = time.monotonic() if self._timing is not None else None
        generation = self._observation_generation
        count = 0
        try:
            boundary = getattr(self.api, 'snapshot', nullcontext)
            with boundary():
                for node in self._walk_nodes(root, strict=strict, protected_ids=protected_ids,
                                             protect_text=protect_text, snapshot=snapshot,
                                             facts=facts, identities=identities):
                    require(generation == self._observation_generation, 'ui:incomplete-tree')
                    count += 1
                    yield node
                require(generation == self._observation_generation, 'ui:incomplete-tree')
        except getattr(self.api, 'read_errors', ()) as error:
            raise UiError('ui:incomplete-tree') from error
        finally:
            if self._timing is not None:
                self._timing['tree_reads'] += 1
                self._timing['nodes_read'] += count
                self._timing['reader_ms'] += (time.monotonic() - started) * 1000

    def _walk_nodes(self, root=None, *, strict=False, protected_ids=(), protect_text=False,
                    snapshot=None, facts=None, identities=None):
        diagnostic = self.kiosk_diagnostic
        if diagnostic is not None:
            diagnostic.check()
            diagnostic.tree_reads += 1
        root = root if root is not None else self.root()
        pending = [root]
        visited = 0
        seen = set()

        def descend(identity, role):
            return (identity not in protected_ids and role != 'password text'
                    and not (protect_text and role in ('text', 'entry'))
                    and (strict or self.include_text_children or role not in ('text', 'entry')))

        def prepare_descend(node):
            attributes = node.get_attributes()
            require(attributes is not None, 'ui:incomplete-tree')
            return descend(_public_automation_id(node, attributes), node.get_role_name())

        prepare = getattr(self.api, 'prepare_tree', None)
        if strict and prepare is not None:
            prepare(root, descend=prepare_descend,
                checkpoint=diagnostic.check if diagnostic is not None else None)
        while pending:
            if diagnostic is not None:
                diagnostic.check()
                diagnostic.nodes_read += 1
            node = pending.pop()
            if node is None:
                require(not strict, 'ui:incomplete-tree')
                continue
            visited += 1
            require(visited <= 6000, 'ui:tree-bound')
            # GTK can expose the same accessible through two parent paths
            # during a stack transition. Identity deduplication still refuses
            # two distinct matching controls and bounds malformed cycles.
            if node in seen:
                continue
            seen.add(node)
            try:
                node.clear_cache_single()
                attributes = node.get_attributes()
                if strict:
                    require(attributes is not None, 'ui:incomplete-tree')
                role = node.get_role_name()
                identity = _public_automation_id(node, attributes)
                if identities is not None:
                    identities[node] = identity
                if facts is not None:
                    states = getattr(node, 'snapshot_state_set', node.get_state_set)()
                    facts[node] = {
                        'identity': identity,
                        'role': role,
                        'name': node.get_name(),
                        'showing': (states.contains(self.api.StateType.SHOWING)
                                    and states.contains(self.api.StateType.VISIBLE)
                                    and not states.contains(self.api.StateType.DEFUNCT)),
                        'modal': states.contains(self.api.StateType.MODAL),
                    }
                yield node
                if diagnostic is not None:
                    diagnostic.check()
                # Never traverse password contents. Strict owned observations
                # include ordinary text descendants without reading text values.
                if descend(identity, role):
                    children = []
                    count = node.get_child_count()
                    require(count >= 0 or not strict, 'ui:incomplete-tree')
                    require(count <= 6000, 'ui:tree-bound')
                    for i in reversed(range(count)):
                        if diagnostic is not None:
                            diagnostic.check()
                        children.append(node.get_child_at_index(i))
                    if strict and None in children:
                        error = UiError('ui:incomplete-tree')
                        error.add_note('Null child under public automation-id: '
                                       + (public_automation_id(node) or '[unidentified]'))
                        raise error
                    if snapshot is not None:
                        snapshot.setdefault(node, []).extend(
                            child for child in children if child is not None)
                    pending.extend(children)
                elif snapshot is not None:
                    snapshot.setdefault(node, [])
            except self.query_errors:
                if strict:
                    raise
                # A dead unrelated subtree must not hide live controls.
                continue

    def snapshot_scope(self, nodes, snapshot, root):
        """Return root's scope from one complete traversal, without rereading it."""
        # Retain the input objects with the key: Python may otherwise recycle
        # their ids inside a composed operation. Nothing survives input/retry.
        cacheable = type(nodes) is tuple and any(
            snapshot is item[2] for item in self._observation_cache or ())
        cache = self._projection_cache if cacheable else {}
        key = ('scope', id(nodes), id(snapshot))
        if key not in cache:
            cache[key] = (nodes, snapshot, {node: index for index, node in enumerate(nodes)}, {})
        _nodes, _snapshot, positions, scopes = cache[key]
        require(root in snapshot and root in positions, 'ui:wrong-scope')
        if root in scopes:
            return scopes[root]
        pending = [root]
        descendants = set()
        while pending:
            node = pending.pop()
            if node in descendants:
                continue
            descendants.add(node)
            pending.extend(snapshot.get(node, ()))
        # Small application/control scopes should not scan the whole desktop.
        result = tuple(sorted((node for node in descendants if node in positions),
                              key=positions.__getitem__))
        scopes[root] = result
        return result

    def snapshot_matches(self, identity, nodes, *, showing=None, show=None, identities=None):
        """Resolve one ID from an already complete snapshot.

        ``show`` is injected by callers so this helper never starts another
        tree read while an input recipient is being qualified.
        """
        cacheable = type(nodes) is tuple and any(
            identities is item[4] for item in self._observation_cache or ())
        cache = self._projection_cache if cacheable else {}
        key = ('ids', id(nodes), id(identities))
        if key not in cache:
            index = {}
            for node in nodes:
                value = self.observed_id(node) if identities is None else identities[node]
                index.setdefault(value, []).append(node)
            cache[key] = (nodes, identities, index)
        matches = cache[key][2].get(identity, ())
        require(len(matches) <= 1, 'ui:ambiguous-automation-id')
        if not matches or (showing is True and not show(matches[0])):
            return None
        return matches[0]

    def owned_applications(self, identity):
        applications = owned_applications(identity)
        if applications == (WATCH_APPLICATION,):
            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                # Host launchers declare exact, configuration-validated VM IDs.
                # Never discover a watcher owner from a name or window title.
                applications = tuple(value for value in requested
                    if value == WATCH_APPLICATION or re.fullmatch(
                        re.escape(WATCH_APPLICATION) + r'\.vm_(?:[0-9a-f]{2}){1,63}', value))
        return applications

    def snapshot_owned_target(self, identity, *, root=None, showing=True,
                              check_prompt=False, observation=None,
                              allow_unmapped_surface=False):
        """Resolve one repository-owned ID from one complete public snapshot."""
        require(type(identity) is str and identity, 'ui:automation-id')
        applications = self.owned_applications(identity)
        shell_owned = identity.startswith('child-')
        require(applications or shell_owned, 'ui:unowned-automation-id')
        if observation is None:
            nodes, snapshot, identities, facts = self.read_snapshot()
        else:
            nodes, snapshot, identities, facts = observation
            require(all(node in snapshot and node in identities for node in nodes),
                    'ui:incomplete-tree')
        if check_prompt:
            require(facts is not None and all(node in facts for node in nodes),
                    'ui:incomplete-tree')
            self.handle_system_prompt(observation=(nodes, snapshot, facts))

        if shell_owned:
            anchors = [node for node in nodes
                       if identities[node] == 'child-screen-time-indicator']
            require(len(anchors) <= 1, 'ui:ambiguous-automation-id')
            if not anchors:
                return None
            application = anchors[0].get_application()
            require(application is not None and application in nodes,
                    'ui:missing-application-owner')
            scope = self.snapshot_scope(nodes, snapshot, application)
            require(anchors[0] in scope, 'ui:wrong-application-owner')
        else:
            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                applications = tuple(value for value in applications if value in requested)
            owners = [node for node in nodes if identities[node] in applications]
            require(len(owners) <= 1, 'ui:ambiguous-application')
            if not owners:
                return None
            application = owners[0]
            if self.owner_pids is not None:
                require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
            if self.application_owners is not None:
                owners_by_id = self.application_owners()
                require(application.get_process_id() in owners_by_id.get(
                    identities[application], ()), 'ui:wrong-application-owner')
            scope = self.snapshot_scope(nodes, snapshot, application)

        surface_id = owned_surface_id(identity)
        if surface_id is not None:
            surface = self.snapshot_matches(
                surface_id, scope, showing=False, show=self.showing, identities=identities)
            if surface is None:
                return None
            if not shell_owned:
                self.validate_owned_surface(
                    surface, application, nodes=nodes, snapshot=snapshot, identities=identities)
            scope = self.snapshot_scope(nodes, snapshot, surface)
        elif not shell_owned and identity.endswith(('-dialog', '-window')):
            surface = self.snapshot_matches(
                identity, scope, showing=False, show=self.showing, identities=identities)
            if surface is not None:
                self.validate_owned_surface(
                    surface, application, nodes=nodes, snapshot=snapshot,
                    identities=identities, allow_unmapped=allow_unmapped_surface)

        if root is not None:
            root_id = identities.get(root, '')
            require(bool(root_id), 'ui:unidentified-scope')
            application_scope = self.snapshot_scope(nodes, snapshot, application)
            current = [node for node in application_scope if identities[node] == root_id]
            require(len(current) == 1 and current[0] == root, 'ui:wrong-scope')
            subtree = set(self.snapshot_scope(nodes, snapshot, root))
            scope = [node for node in scope if node in subtree]
        return self.snapshot_matches(
            identity, scope, showing=showing, show=self.showing, identities=identities)

    def snapshot_provider_target(self, provider, surface, control, *, showing=True,
                                 check_prompt=False):
        """Resolve a registered provider surface/control with one tree read."""
        application_id, surface_id, registered = self.require_provider_contract(
            provider, surface, (control,))
        protected = tuple(registered[key] for key in ('password', 'secret')
                          if key in registered and registered[key])
        nodes, snapshot, identities, facts = self.read_snapshot(protected_ids=protected)
        if check_prompt:
            self.handle_system_prompt(observation=(nodes, snapshot, facts))
        application = self.snapshot_matches(
            application_id, nodes, showing=showing, show=self.showing, identities=identities)
        if application is None:
            return None
        application_nodes = self.snapshot_scope(nodes, snapshot, application)
        surface_root = self.snapshot_matches(
            surface_id, application_nodes, showing=showing, show=self.showing, identities=identities)
        if surface_root is None:
            return surface_root
        surface_nodes = self.snapshot_scope(nodes, snapshot, surface_root)
        return self.snapshot_matches(
            registered[control], surface_nodes, showing=showing, show=self.showing, identities=identities)

    def find_id(self, identity, *, root=None, nodes=None, showing=True):
        """Resolve exactly one public automation ID without selector fallbacks."""
        require(type(identity) is str and identity, 'ui:automation-id')
        if owned_applications(identity) or identity.startswith('child-'):
            found = self.snapshot_owned_target(identity, root=root, showing=showing)
            return found if nodes is None or found is None or found in nodes else None
        identities = {} if nodes is None else None
        candidates = self.nodes(root, identities=identities) if nodes is None else nodes
        found = None
        for node in candidates:
            try:
                if (identities[node] if identities is not None else public_automation_id(node)) != identity:
                    continue
                require(found is None, 'ui:ambiguous-automation-id')
                found = node
            except self.query_errors:
                continue
        if found is None or (showing and not self.showing(found)):
            return None
        return found

    def find_all_ids(self, identity, *, root=None, nodes=None):
        require(not owned_applications(identity) and not identity.startswith('child-'),
                'ui:owned-id-requires-direct-lookup')
        identities = {} if nodes is None else None
        candidates = self.nodes(root, identities=identities) if nodes is None else nodes
        found = []
        for node in candidates:
            try:
                if (identities[node] if identities is not None else public_automation_id(node)) != identity:
                    continue
                found.append(node)
            except self.query_errors:
                continue
        return found

    def validate_owned_surface(self, surface, application, *, visited=(), nodes=None,
                               snapshot=None, identities=None, allow_unmapped=False):
        """Bind a dialog to its actual originating surface in the same app."""
        identify = public_automation_id if identities is None else identities.__getitem__
        identity = identify(surface)
        app_id = identify(application)
        primary = ((f'onpc-fixture-{"-".join(app_id.split(".")[-2:])}',)
                   if app_id.startswith('com.puffyslippers.ONPCFixture.') else
                   ('watch-window',) if app_id in self.owned_applications('watch-window') else
                   ('parent-window', 'parent-access-denied-window', 'startup-error-window')
                   if app_id == PARENT_APPLICATION else
                   ('kiosk-request-window', 'startup-error-window')
                   if app_id in (KIOSK_APPLICATION, CHILD_APPLICATION) else
                   ('preview-viewer-window',))
        require(identity not in visited and len(visited) < 8, 'ui:surface-owner-cycle')
        if identity in primary:
            return
        expected = (('feedback-dialog',) if identity == 'feedback-privacy-dialog' else
                    ('parent-window',) if identity in ('parent-revoke-dialog', 'parent-match-rule-dialog') else
                    ('parent-window', 'kiosk-request-window') if identity == 'language-dialog' else
                    ('kiosk-request-window',) if identity == 'preview-screen-dialog' else
                    tuple(value for value in primary if value != 'parent-access-denied-window'))
        if nodes is None or snapshot is None:
            snapshot = {}
            app_nodes = list(self.nodes(application, strict=True, snapshot=snapshot))
            nodes = app_nodes
        else:
            app_nodes = self.snapshot_scope(nodes, snapshot, application)
        # Embedded Adw dialogs can retain true containment. Separate GTK
        # toplevels publish CONTROLLED_BY from their native transient parent.
        containers = [node for node in app_nodes if identify(node) in expected]
        for container in containers:
            if surface in self.snapshot_scope(nodes, snapshot, container):
                self.validate_owned_surface(
                    container, application, visited=(*visited, identity),
                    nodes=nodes, snapshot=snapshot, identities=identities)
                return
        parents = []
        for relation in surface.get_relation_set():
            if relation.get_relation_type() == self.api.RelationType.CONTROLLED_BY:
                parents.extend(relation.get_target(index)
                               for index in range(relation.get_n_targets()))
        # Repository surfaces deliberately remove CONTROLLED_BY when they
        # unmap. A complete negative observation may still see the hidden GTK
        # accessible briefly, so its application scope proves ownership while
        # its missing relation proves that it is no longer mapped. Showing
        # surfaces and any relation that remains retain the full owner checks.
        if allow_unmapped and not parents and not self.showing(surface):
            return
        require(len(parents) == 1 and parents[0] in app_nodes, 'ui:missing-surface-owner')
        parent = parents[0]
        require(identities is None or parent in identities, 'ui:wrong-surface-owner')
        parent_id = identify(parent)
        require(parent_id in expected, 'ui:wrong-surface-owner')
        matches = [node for node in app_nodes if identify(node) == parent_id]
        require(len(matches) == 1, 'ui:ambiguous-surface-owner')
        self.validate_owned_surface(
            parent, application, visited=(*visited, identity),
            nodes=nodes, snapshot=snapshot, identities=identities)

    def absent_id(self, identity, *, within, incomplete_raises=False):
        """Complete negative proof; optionally distinguish unknown from present.

        The default retains False for unavailable proof. Input preconditions
        can opt in to read retries while refusing a positively showing target.
        """
        require(type(incomplete_raises) is bool, 'ui:absence-mode')
        def indeterminate(reason, cause=None):
            if not incomplete_raises:
                return False
            error = UiError('ui:incomplete-tree')
            error.add_note('ui:absence-read:' + reason)
            raise error from cause
        try:
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            if not nodes:
                return indeterminate('empty-tree')
            if any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes):
                return indeterminate('defunct-tree')
            observation = (nodes, snapshot, identities, None)
            anchor = (self.snapshot_owned_target(
                within, observation=observation)
                if owned_applications(within) or within.startswith('child-') else
                self.snapshot_matches(
                    within, nodes, showing=True, show=self.showing,
                    identities=identities))
            if anchor is None:
                return indeterminate('missing-anchor')
            matches = [node for node in nodes if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if matches:
                target = (self.snapshot_owned_target(
                    identity, showing=False, observation=observation,
                    allow_unmapped_surface=True)
                    if owned_applications(identity) or identity.startswith('child-') else
                    self.snapshot_matches(
                        identity, nodes, showing=False, show=self.showing,
                        identities=identities))
                if target != matches[0]:
                    # A launched process can exit before AT-SPI removes its
                    # last cached node. That node cannot prove absence and is
                    # no longer eligible for input, but it is not a foreign
                    # owner. Retry until a fresh complete tree drops it.
                    history = (self.application_owner_history()
                               if self.application_owner_history is not None else {})
                    expected = self.owned_applications(identity)
                    known_pids = {
                        pid for application in expected
                        for pid in history.get(application, ())
                    }
                    if expected and matches[0].get_process_id() in known_pids:
                        return indeterminate('stale-owner')
                    raise UiError('ui:wrong-absence-owner')
                if self.showing(target):
                    return False
            return True
        except self.query_errors as error:
            return indeterminate('query', error)
        except UiError as error:
            if str(error) == 'ui:incomplete-tree':
                if incomplete_raises:
                    raise  # Preserve the original complete-read notes/cause.
                return False
            raise

    def find_provider_control(self, provider, surface, control, *, root=None, showing=True):
        """Resolve one registered control inside its provider-owned ID scopes.

        All three identities are mandatory.  Partial provider observations stay
        useful audit evidence but cannot become selectors until the owning
        application and surface publish stable IDs too.
        """
        require(root is None, 'ui:provider-root-unsupported')
        return self.snapshot_provider_target(
            provider, surface, control, showing=showing)

    def require_provider_contract(self, provider, surface, controls):
        """Validate a complete mapping before the first public-tree read."""
        require(type(provider) is str and provider and type(surface) is str and surface
                and type(controls) is tuple and controls
                and all(type(control) is str and control for control in controls),
                'ui:provider-binding')
        contract = self.provider_contracts.get(provider)
        require(contract is not None, 'ui:unregistered-provider')
        application_id = contract.get('application_id')
        require(type(application_id) is str and application_id,
                'ui:unqualified-provider-application')
        surface_contract = contract.get('surfaces', {}).get(surface)
        require(surface_contract is not None, 'ui:unregistered-provider-surface')
        surface_id, registered = surface_contract
        require(type(surface_id) is str and surface_id,
                'ui:unqualified-provider-surface')
        for control in controls:
            require(control in registered, 'ui:unregistered-provider-control')
            require(type(registered[control]) is str and registered[control],
                    'ui:unqualified-provider-control')
        return application_id, surface_id, registered

    def provider_surface(self, provider, surface, controls, *, showing=True):
        """Resolve a qualified provider surface without label/role fallbacks."""
        application_id, surface_id, registered = self.require_provider_contract(
            provider, surface, controls)
        protected = tuple(registered[key] for key in ('password', 'secret')
                          if key in registered and registered[key])
        snapshot = {}
        identities = {}
        desktop = list(self.nodes(
            strict=True, protected_ids=protected, snapshot=snapshot, identities=identities))
        application = self.snapshot_matches(
            application_id, desktop, showing=showing, show=self.showing, identities=identities)
        if application is None:
            return None, registered
        application_nodes = self.snapshot_scope(desktop, snapshot, application)
        return self.snapshot_matches(
            surface_id, application_nodes, showing=showing, show=self.showing,
            identities=identities), registered

    def observed_fact(self, node):
        """Reuse one node's facts only inside the current complete read boundary."""
        for _policy, _nodes, _edges, facts, _ids in reversed(self._observation_cache or ()):
            if node in facts:
                return facts[node]
        return None

    def observed_id(self, node):
        fact = self.observed_fact(node)
        return fact['identity'] if fact is not None else public_automation_id(node)

    def showing(self, node):
        states = node.get_state_set()
        return (states.contains(self.api.StateType.SHOWING)
                and states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT))

    def has_state(self, node, state):
        node.clear_cache_single()
        return node.get_state_set().contains(state)

    def find(self, name=None, roles=(), *, root=None, sensitive=False, contains=None,
             showing=True, editable=False):
        """Retired name/role selector; public automation IDs are mandatory."""
        raise UiError('ui:legacy-selector-refused')

    def wait(self, predicate, code, *, prompt_in_predicate=False):
        deadline = time.monotonic() + self.timeout
        incomplete = None
        while True:
            # Deliver pending public AT-SPI events before fresh reads. Cache
            # invalidation alone cannot deliver focus/text/registry changes.
            if self.kiosk_diagnostic is not None:
                self.kiosk_diagnostic.emit('dispatch')
                self.kiosk_diagnostic.check()
            # Composed read helpers can share an already complete snapshot.
            # Dispatch before a new read boundary, never midway through one.
            if self.dispatch is not None and not self._observation_cache:
                for _ in range(32):
                    if not self.dispatch():
                        break
            try:
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.emit('prompt-check')
                with self.observation():
                    if not prompt_in_predicate:
                        self.handle_system_prompt()
                    value = predicate()
            except self.query_errors:
                # UI objects can disappear during search/animation. Retry only
                # the read, never replay an action whose effect is uncertain.
                value = None
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.query_errors += 1
                    self.kiosk_diagnostic.emit(status='query-error')
            except UiError as error:
                if str(error) not in (
                        'ui:incomplete-tree', 'ui:stale-picker', 'ui:gdm-stale-tree',
                        'ui:system-prompt-observation-failed'):
                    raise
                # Discard the entire observation. A child can disappear between
                # ChildCount and GetChildAtIndex during a public UI transition.
                # GTK can likewise leave a defunct picker node in one AT-SPI
                # snapshot while removing a closed popover. GDM can leave a
                # defunct node while replacing its authentication prompt.
                # Prompt scans can
                # encounter the same disappearing objects; a failed scan never
                # authorizes the predicate or any input.
                # Only a later complete read may satisfy the predicate; no
                # action is replayed and the original deadline is retained.
                incomplete = error
                if self.kiosk_diagnostic is not None:
                    self.kiosk_diagnostic.incomplete += 1
                    self.kiosk_diagnostic.emit(status='incomplete')
                self.incomplete_observations.append({
                    'checkpoint': code, 'notes': getattr(error, '__notes__', [])})
                self.incomplete_observations = self.incomplete_observations[-16:]
                value = None
            if value:
                return value
            self.invalidate_observation()
            if time.monotonic() >= deadline:
                if incomplete is not None and str(incomplete) in (
                        'ui:stale-picker', 'ui:gdm-stale-tree',
                        'ui:system-prompt-observation-failed'):
                    raise incomplete
                raise UiError('ui:timeout:' + code) from incomplete
            time.sleep(.2)

    def target(self, name=None, roles=(), **kwargs):
        raise UiError('ui:legacy-selector-refused')

    def id_target(self, identity, *, root=None, sensitive=False, showing=True):
        """Wait for one public ID, optionally requiring an actionable state."""
        owned = bool(owned_applications(identity) or identity.startswith('child-'))
        node = self.wait(
            (lambda: self.snapshot_owned_target(
                identity, root=root, showing=showing, check_prompt=True))
            if owned else
            (lambda: self.find_id(identity, root=root, showing=showing)),
            'automation-id',
            prompt_in_predicate=owned,
        )
        if sensitive:
            require(self.has_state(node, self.api.StateType.SENSITIVE),
                    'ui:unusable-target')
        return node

    def _invoke_target(self, node, action_name=None):
        """Invoke an ID-qualified target without another public-tree traversal."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        states = node.get_state_set()
        # SHOWING is a viewport/rendering state. A clipped or covered control
        # remains directly actionable while the application keeps it VISIBLE
        # and SENSITIVE; truly hidden or disabled application state still
        # refuses input.
        require(states.contains(self.api.StateType.VISIBLE)
                and states.contains(self.api.StateType.SENSITIVE)
                and not states.contains(self.api.StateType.DEFUNCT),
                'ui:unusable-target')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-action')
        count = self.api.Action.get_n_actions(action)
        if action_name is None:
            # Native focus actions navigate to descendants; they are never a
            # control's default activation, on either host or installed UI.
            matches = [index for index in range(count)
                       if not public_action_name(self.api, action, index).startswith('focus.')]
        else:
            matches = [index for index in range(count)
                       if public_action_name(self.api, action, index) == action_name]
        require(len(matches) == 1, 'ui:missing-or-ambiguous-action')
        self.input_uncertain = True
        if self._timing is not None and len(self._timing['input_ms']) < 64:
            self._timing['input_ms'].append(round(
                (time.monotonic() - self._timing['started']) * 1000, 3))
        require(self.api.Action.do_action(action, matches[0]), 'ui:action-refused')
        self.input_uncertain = False
        return node

    def activate_id(self, identity, *, action_name=None):
        """Resolve and invoke one repository-owned automation ID in one snapshot."""
        require(type(identity) is str and identity, 'ui:automation-id')
        require(owned_applications(identity) or identity.startswith('child-'),
                'ui:unowned-automation-id')
        node = self.wait(
            lambda: self.snapshot_owned_target(
                identity, showing=False, check_prompt=True),
            'automation-id', prompt_in_predicate=True,
        )
        return self._invoke_target(node, action_name)

    def activate_provider(self, provider, surface, control, *, action_name=None):
        """Resolve and invoke one qualified external-provider ID in one snapshot."""
        node = self.wait(
            lambda: self.snapshot_provider_target(
                provider, surface, control, showing=False, check_prompt=True),
            'provider-automation-id', prompt_in_predicate=True,
        )
        return self._invoke_target(node, action_name)

    def clickable_link(self, identity, *, root=None):
        """Read a product link's actionable state without following its URI."""
        require(identity in (
            'about-website-value', 'about-privacy-value', 'about-support-value',
            'about-license-value', 'about-legal-notices-value',
            'feedback-full-privacy-link', 'parent-menu-help', 'kiosk-menu-item-help'),
            'ui:link-binding')
        node = self.id_target(identity, root=root, sensitive=True, showing=False)
        roles = (('menu item', 'button', 'push button')
                 if identity in ('parent-menu-help', 'kiosk-menu-item-help') else ('link',))
        require(node.get_role_name() in roles, 'ui:link-role')
        require(self.has_state(node, self.api.StateType.VISIBLE)
                and not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:unusable-link')
        action = node.get_action_iface()
        require(action is not None, 'ui:missing-link-action')
        actions = [index for index in range(self.api.Action.get_n_actions(action))
                   if not public_action_name(self.api, action, index).startswith('focus.')]
        require(len(actions) == 1, 'ui:missing-or-ambiguous-link-action')
        return True

    def activate(self, node):
        return self._invoke_target(self.fresh_owned_target(node))

    def activate_named(self, node, action_name):
        """Invoke one named public action on an already ID-resolved control."""
        return self._invoke_target(self.fresh_owned_target(node), action_name)

    def fresh_owned_target(self, node):
        identity = public_automation_id(node)
        require(bool(identity), 'ui:unidentified-action-target')
        if owned_applications(identity) or identity.startswith('child-'):
            current = self.snapshot_owned_target(
                identity, showing=False, check_prompt=True)
            require(current is not None and current == node, 'ui:wrong-action-owner')
            return current
        bindings = [(provider, surface, control)
                    for provider, contract in self.provider_contracts.items()
                    for surface, (_surface_id, controls) in contract.get('surfaces', {}).items()
                    for control, registered_id in controls.items() if registered_id == identity]
        require(len(bindings) == 1, 'ui:unregistered-or-ambiguous-action-target')
        current = self.snapshot_provider_target(
            *bindings[0], showing=False, check_prompt=True)
        require(current is not None and current == node, 'ui:wrong-action-owner')
        return current

    def reveal(self, name, roles, *, root):
        raise UiError('ui:legacy-selector-refused')

    def scroll_target(self, name, roles, *, root):
        raise UiError('ui:legacy-selector-refused')

    def find_labelled_control(self, name, roles, *, root=None):
        raise UiError('ui:legacy-selector-refused')

    def find_labelled_button(self, name, *, root=None):
        raise UiError('ui:legacy-selector-refused')

    def labelled_button(self, name):
        raise UiError('ui:legacy-selector-refused')

    def parent(self):
        return self.id_target('parent-window')

    def complete_parent_language_setup(self):
        self.complete_language_setup('parent')

    def complete_request_language_setup(self):
        self.complete_language_setup('kiosk')

    def complete_language_setup(self, surface):
        """Scope shared language IDs to the requested frontend application."""
        with self.language_scope(surface):
            self._complete_language_setup(surface)

    @contextmanager
    def language_scope(self, surface):
        """Share the owning-account chooser boundary between previews and E2E."""
        require(surface in ('parent', 'kiosk'), 'ui:language-surface')
        original = self.application_ids
        requested = original() if callable(original) else original
        allowed = ((PARENT_APPLICATION,) if surface == 'parent'
                   else (KIOSK_APPLICATION, CHILD_APPLICATION))
        self.application_ids = tuple(value for value in allowed
                                     if requested is None or value in requested)
        try:
            yield
        finally:
            self.application_ids = original

    def open_language_preferences(self, surface):
        with self.language_scope(surface):
            self.id_target('parent-window' if surface == 'parent' else 'kiosk-request-window')
            self.activate_id(f'{surface}-menu-button')
            self.activate_id('parent-menu-preferences' if surface == 'parent'
                             else 'kiosk-menu-item-preferences')
            self.input_uncertain = True
            self.wait(lambda: self.snapshot_owned_target('language-dialog', check_prompt=True),
                      'language-preferences-open', prompt_in_predicate=True)
            self.input_uncertain = False

    def choose_language(self, surface, language):
        # Finite customer input; never derive target identities from translated names.
        require(language in ('en', 'de', 'fr', 'ru', 'pl', 'ja', 'zh-Hans'),
                'ui:language-test-choice')
        with self.language_scope(surface):
            identity = 'language-choice-' + language.lower()
            self.activate_id(identity)
            self.input_uncertain = True
            self.wait(lambda: self.has_state(self.id_target(identity, showing=False),
                                             self.api.StateType.CHECKED),
                      'language-candidate-selected')
            self.input_uncertain = False

    def language_save_completed(self, surface):
        """Observe readiness and closure together; do not replay an uncertain Save."""
        with self.language_scope(surface):
            def completed():
                observation = self.read_snapshot()
                if any(self.has_state(node, self.api.StateType.DEFUNCT)
                       for node in observation[0]):
                    return False
                if self.snapshot_owned_target(f'{surface}-language-ready', check_prompt=True,
                                              observation=observation) is None:
                    return False
                dialog = self.snapshot_owned_target('language-dialog', showing=False,
                    observation=observation, allow_unmapped_surface=True)
                return dialog is None or not self.showing(dialog)

            self.wait(completed, 'language-saved', prompt_in_predicate=True)
            self.input_uncertain = False

    def save_language(self, surface):
        with self.language_scope(surface):
            self.activate_id('language-continue')
            self.input_uncertain = True
            self.language_save_completed(surface)

    def cancel_language(self, surface):
        with self.language_scope(surface):
            self.activate_id('language-cancel')
            self.input_uncertain = True
            self.language_save_completed(surface)

    def _complete_language_setup(self, surface):
        """Accept the first-run default once, using the same host/E2E public IDs.

        Readiness distinguishes an asynchronous initial read from no dialog.
        A Preferences dialog opened after startup is deliberately left alone.
        """
        require(surface in ('parent', 'kiosk'), 'ui:language-surface')
        window_id = 'parent-window' if surface == 'parent' else 'kiosk-request-window'
        ready_id = f'{surface}-language-ready'

        def entry():
            observation = self.read_snapshot()
            for identity in (ready_id, 'language-dialog', f'{surface}-language-load-error',
                             'parent-access-denied-window', 'startup-error-window'):
                target = self.snapshot_owned_target(identity, check_prompt=True,
                                                    observation=observation)
                if target is not None:
                    if identity == 'language-dialog':
                        window = self.snapshot_owned_target(window_id, observation=observation)
                        nodes, edges, identities, _facts = observation
                        require(window is not None and any(
                            identities[node] in self.owned_applications(window_id)
                            and window in self.snapshot_scope(nodes, edges, node)
                            and target in self.snapshot_scope(nodes, edges, node)
                            for node in nodes), 'ui:language-owner')
                    return identity
            return None

        state = self.wait(entry, f'{surface}-language-entry', prompt_in_predicate=True)
        require(state != f'{surface}-language-load-error', 'ui:language-load-failed')
        if state != 'language-dialog':
            return
        self.activate_id('language-continue')
        # Keep input uncertain until a fresh public result confirms completion.
        # A save error or timeout must not replay Continue.
        self.input_uncertain = True
        self.language_save_completed(surface)

    def parent_window_count(self):
        """UI13: count the sole owned management window in a complete snapshot."""
        observation = self.read_snapshot()
        window = self.snapshot_owned_target(
            'parent-window', check_prompt=True, observation=observation)
        count = 0 if window is None else 1
        require(count == 1, 'ui:parent-window-count')
        return count

    def about(self):
        return self.id_target('about-dialog')

    def chooser_snapshot(self, *, mode='open', absent=False):
        """FILE03 provider exception, scoped to feedback's transient chooser.

        Native GTK and Nautilus portal routes are separate. Dynamic entries use
        provider-local names only after owner, transient caller and mode proofs.
        No title, geometry, global label or positional target fallback.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(mode in ('open', 'save'), 'ui:chooser-mode')
        nodes, edges, ids, facts = self.read_snapshot()
        observation = (nodes, edges, ids, facts)
        caller = self.snapshot_owned_target('feedback-dialog', observation=observation,
                                            check_prompt=False)
        require(caller is not None, 'ui:chooser-caller')
        caller_pid = caller.get_process_id()
        candidates = []
        for node in nodes:
            if ids[node] not in ('', 'NautilusFileChooser', 'GtkFileChooserDialog') or not facts[node]['showing'] or facts[node]['role'] not in (
                    'dialog', 'file chooser', 'frame', 'window'):
                continue
            scoped = self.snapshot_scope(nodes, edges, node)
            accepts = [item for item in scoped if ids[item] == 'accept_button']
            # Native GTK does not expose an accept Builder ID.
            if not accepts and node.get_process_id() == caller_pid:
                accepts = [item for item in scoped if facts[item]['role'] in ('button', 'push button')
                           and facts[item]['name'] in ('Open', 'Save')]
            if accepts:
                candidates.append((node, scoped, accepts))
        require(len(candidates) <= 1, 'ui:chooser-ambiguous')
        if not candidates:
            self.handle_system_prompt(observation=(nodes, edges, facts))
            if absent:
                return True
        require(len(candidates) == 1, 'ui:chooser-entry')
        window, scoped, accepts = candidates[0]
        pid = window.get_process_id()
        route = 'gtk-native' if pid == caller_pid else 'nautilus-portal'
        if route == 'nautilus-portal':
            application = window.get_application()
            require(application in nodes and application.get_process_id() == pid
                    and facts[application]['role'] == 'application'
                    and (ids[application] == 'org.gnome.Nautilus' or
                         facts[application]['name'] in ('org.gnome.Nautilus', 'nautilus', 'Files')),
                    'ui:chooser-provider-owner')
        relations = [relation for relation in window.get_relation_set()
                     if relation.get_relation_type() == self.api.RelationType.CONTROLLED_BY]
        print(json.dumps({'event': 'chooser-ownership', 'route': route,
                          'caller_relations': len(relations)}, sort_keys=True), file=sys.stderr, flush=True)
        if route == 'nautilus-portal':
            # An explicit contradictory relation must never fall back to the
            # portal proof. The expected imported Wayland parent has no GTK
            # relation; bind its live request to the already validated caller.
            require(not relations or (len(relations) == 1 and relations[0].get_n_targets() == 1
                    and relations[0].get_target(0) == caller), 'ui:chooser-transient-caller')
            self.chooser_portal_owner(caller_pid, pid)
        else:
            require(len(relations) == 1 and relations[0].get_n_targets() == 1
                    and relations[0].get_target(0) == caller, 'ui:chooser-transient-caller')
        require(self.has_state(window, self.api.StateType.ACTIVE)
                and self.has_state(window, self.api.StateType.MODAL), 'ui:chooser-active')
        require(len(accepts) == 1 and facts[accepts[0]]['name'] ==
                ('Open' if mode == 'open' else 'Save'), 'ui:chooser-mode')
        require(mode != 'save' or route == 'nautilus-portal', 'ui:chooser-save-provider')
        # Nautilus sends RESPONSE_USER_CANCELLED from its window close
        # request. Its GTK window control exposes "Close", with no Builder
        # ID or separate Cancel button. Keep this binding provider-local;
        # native GTK still requires its explicit Cancel action.
        cancel_name = 'Close' if route == 'nautilus-portal' else 'Cancel'
        # AT-SPI now names PUSH_BUTTON "button"; older readers use
        # "push button". Both denote the same public control role.
        cancels = [item for item in scoped if facts[item]['role'] in ('button', 'push button')
                   and facts[item]['name'] == cancel_name]
        if len(cancels) != 1:
            print(json.dumps({'event': 'chooser-cancel-resolution', 'route': route,
                'label_matches': sum(facts[item]['name'] == cancel_name for item in scoped),
                'button_matches': len(cancels)}, sort_keys=True), file=sys.stderr, flush=True)
        require(len(cancels) == 1, 'ui:chooser-cancel')
        require(all(item.get_process_id() == pid for item in (accepts[0], cancels[0])),
                'ui:chooser-control-owner')
        require(all(not self.has_state(item, self.api.StateType.DEFUNCT) for item in scoped),
                'ui:chooser-stale')
        require(not any(facts[item]['role'] == 'password text' for item in scoped),
                'ui:chooser-secret-surface')
        # The external modal is expected only after this exact snapshot proves
        # its provider, caller, mode and controls. Other modals (including any
        # nested prompt) still refuse; this does not exempt the provider app.
        self.handle_system_prompt(observation=(nodes, edges, facts),
                                  nonsecret_surface=window)
        if absent:
            return False
        return window, scoped, ids, facts, accepts[0], cancels[0], route

    def chooser_portal_owner(self, caller_pid, provider_pid):
        from gi.repository import Gio, GLib
        address = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
        require(bool(address), 'ui:chooser-session-bus')
        connection = Gio.DBusConnection.new_for_address_sync(
            address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT |
            Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        connection.set_exit_on_close(False)
        def query(bus, path, interface, method, signature, args):
            return connection.call_sync(
                bus, path, interface, method,
                GLib.Variant('(' + signature + ')', args) if signature else None,
                None, Gio.DBusCallFlags.NO_AUTO_START, 2000, None).unpack()[0]
        try:
            validate_chooser_portal_owner(query, caller_pid, provider_pid)
        finally:
            connection.close_sync(None)

    def chooser_metadata(self, *, mode='open'):
        from gi.repository import Gio
        window, _, _, _, _, _, route = self.chooser_snapshot(mode=mode)
        pid = window.get_process_id()
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0') if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        package = 'nautilus' if route == 'nautilus-portal' else 'libgtk-4-1'
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', package],
            text=True, timeout=5).strip()
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        return {'route': route, **validate_shell_metadata({
            'version': version, 'locale': locale, 'keyboard': [list(source) for source in sources]})}

    def chooser_selection(self, expected=None, *, profile='standard'):
        require(profile == 'standard' or profile in BOUNDARY_FILES, 'ui:chooser-profile')
        files = CHOOSER_FILES if profile == 'standard' else tuple(name for name, _ in BOUNDARY_FILES[profile])
        window, scoped, ids, facts, accept, cancel, route = self.chooser_snapshot()
        views = [node for node in scoped
                 if (self.has_state(node, self.api.StateType.MULTISELECTABLE)
                     or (route == 'nautilus-portal' and facts[node]['name'] == 'Content View'))
                 and node.get_selection_iface() is not None]
        # GtkGridView advertises MULTISELECTABLE only for GtkMultiSelection,
        # but Nautilus uses its own GtkSelectionModel implementation. Bind its
        # scoped Content View instead; exact two-file readback, not that model
        # type hint, proves successful multi-selection before Open.
        require(len(views) == 1, 'ui:chooser-multiple-mode')
        view = views[0]
        children = [view.get_child_at_index(index) for index in range(view.get_child_count())]
        require(len(children) == len(files) and all(child in scoped for child in children),
                'ui:chooser-file-set')
        # Nautilus's a11y-name includes the file role, even though the visible
        # basename does not. Keep this exact English provider binding local;
        # do not strip arbitrary suffixes or accept similarly named folders.
        labels = {name + ('. File' if route == 'nautilus-portal' else ''): name
                  for name in files}
        names = [child.get_name() for child in children]
        if sorted(names) != sorted(labels):
            print(json.dumps({'event': 'chooser-file-labels', 'route': route,
                'expected_matches': sum(name in labels for name in names)}, sort_keys=True),
                file=sys.stderr, flush=True)
        require(sorted(names) == sorted(labels), 'ui:chooser-file-set')
        selection = view.get_selection_iface()
        count = self.api.Selection.get_n_selected_children(selection)
        require(type(count) is int and 0 <= count <= len(files), 'ui:chooser-selection')
        selected = [self.api.Selection.get_selected_child(selection, index) for index in range(count)]
        require(len(set(selected)) == count and all(child in children for child in selected),
                'ui:chooser-selection')
        names_selected = sorted(labels[child.get_name()] for child in selected)
        require(expected is None or names_selected == list(expected), 'ui:chooser-partial-selection')
        return view, children, names_selected, accept, cancel, route

    def chooser_select_files(self, *, profile='standard'):
        # The prepared directory contains only the two declared synthetic
        # files. SelectAll avoids individual row navigation and modifier state.
        view, _, _, _, _, _ = self.chooser_selection(profile=profile)
        require(all(self.has_state(view, state) for state in (
                    self.api.StateType.SENSITIVE, self.api.StateType.VISIBLE,
                    self.api.StateType.SHOWING)),
                'ui:chooser-file-target')
        self.input_uncertain = True
        require(self.api.Selection.select_all(view.get_selection_iface()),
                'ui:chooser-selection-refused')
        self.input_uncertain = False
        try:
            files = CHOOSER_FILES if profile == 'standard' else tuple(name for name, _ in BOUNDARY_FILES[profile])
            self.wait(lambda: self.chooser_selection(files, profile=profile), 'chooser-selection',
                      prompt_in_predicate=True)
        except BaseException:
            self.input_uncertain = True
            raise

    def chooser_location_field(self, *, mode='open'):
        window, scoped, ids, facts, _, _, _ = self.chooser_snapshot(mode=mode)
        fields = [node for node in scoped if facts[node]['role'] in ('text', 'entry')
                  and all(self.has_state(node, state) for state in (
                      self.api.StateType.EDITABLE, self.api.StateType.FOCUSED,
                      self.api.StateType.SENSITIVE, self.api.StateType.VISIBLE,
                      self.api.StateType.SHOWING))]
        require(len(fields) == 1, 'ui:chooser-location-focus')
        field = fields[0]
        require(ids[field] in ('filename_entry', 'location_entry', 'entry')
                and field.get_process_id() == window.get_process_id(), 'ui:chooser-location-id')
        return field

    def save_chooser_field(self, kind, *, focused=True):
        window, scoped, ids, facts, _, _, _ = self.chooser_snapshot(mode='save')
        require(kind in ('name', 'location'), 'ui:save-field-kind')
        fields = [node for node in scoped if ids[node] ==
                  ('filename_entry' if kind == 'name' else 'location_entry')]
        if len(fields) != 1:
            target = 'filename_entry' if kind == 'name' else 'location_entry'
            print(json.dumps({'event': 'save-field-resolution', 'kind': kind,
                'id_matches': sum(ids[node] == target for node in scoped),
                'role_matches': sum(facts[node]['role'] in ('text', 'entry') for node in fields),
                'showing_matches': sum(facts[node]['showing'] for node in fields)},
                sort_keys=True), file=sys.stderr, flush=True)
        require(bool(fields), 'ui:save-field-missing')
        require(len(fields) == 1, 'ui:save-field-ambiguous')
        field = fields[0]
        require(facts[field]['role'] in ('text', 'entry'), 'ui:save-field-role')
        require(field.get_process_id() == window.get_process_id(), 'ui:save-field-owner')
        if focused:
            require(all(self.has_state(field, state) for state in (
                self.api.StateType.EDITABLE, self.api.StateType.FOCUSED,
                self.api.StateType.SENSITIVE, self.api.StateType.VISIBLE,
                self.api.StateType.SHOWING)), 'ui:save-field-focus')
        return field

    def save_chooser_text(self, kind, expected, *, replace=False, focused=True):
        field = self.save_chooser_field(kind, focused=focused)
        if replace:
            editable = field.get_editable_text_iface()
            require(editable is not None, 'ui:save-field-editable')
            self.input_uncertain = True
            require(self.api.EditableText.set_text_contents(editable, expected),
                    'ui:save-field-refused')
            self.input_uncertain = False
        try:
            field = self.save_chooser_field(kind, focused=focused)
            text = field.get_text_iface()
            require(text is not None and self.api.Text.get_character_count(text) == len(expected)
                    and self.api.Text.get_text(text, 0, len(expected)) == expected,
                    'ui:save-field-readback')
        except BaseException:
            if replace:
                self.input_uncertain = True
            raise

    def save_chooser_location_closed(self, snapshot):
        _, scoped, ids, facts, _, _, _ = snapshot
        fields = [node for node in scoped if ids[node] == 'location_entry']
        require(len(fields) <= 1, 'ui:save-field-ambiguous')
        require(not fields or not facts[fields[0]]['showing'], 'ui:save-location-still-open')

    def save_chooser_restore_name(self):
        # Nautilus collapses its transient filename entry on focus loss. Escape
        # dismisses Location, not that collapsed state. Its no-ID edit button
        # is publicly LABELLED_BY the provider's filename_label; Reset is a
        # separate control and must never be used to recover the chosen name.
        snapshot = self.chooser_snapshot(mode='save')
        self.save_chooser_location_closed(snapshot)
        window, scoped, ids, facts, _, _, _ = snapshot
        labels = [node for node in scoped if ids[node] == 'filename_label']
        require(len(labels) == 1, 'ui:save-name-label')
        label = labels[0]
        require(facts[label]['role'] == 'label' and facts[label]['name'] == SAVE_NAMES[0]
                and label.get_process_id() == window.get_process_id(), 'ui:save-name-label')
        buttons = []
        for node in scoped:
            if facts[node]['role'] not in ('button', 'push button'):
                continue
            targets = [relation.get_target(index) for relation in node.get_relation_set()
                       if relation.get_relation_type() == self.api.RelationType.LABELLED_BY
                       for index in range(relation.get_n_targets())]
            if label in targets:
                require(targets == [label], 'ui:save-name-edit-label')
                buttons.append(node)
        require(len(buttons) == 1, 'ui:save-name-edit-ambiguous')
        button = buttons[0]
        require(button.get_process_id() == window.get_process_id()
                and facts[button]['name'] == SAVE_NAMES[0], 'ui:save-name-edit-owner')
        self._invoke_target(button)
        try:
            def ready():
                try:
                    return self.save_chooser_field('name')
                except UiError as error:
                    if str(error) == 'ui:save-field-missing':
                        return None
                    raise
            self.wait(ready, 'save-chooser-name-revealed', prompt_in_predicate=True)
            self.save_chooser_text('name', SAVE_NAMES[0])
        except BaseException:
            self.input_uncertain = True
            raise

    def save_chooser_operation(self, operation):
        """Nautilus Save binding; destination readback precedes the real Save."""
        require(operation in SAVE_OPERATIONS, 'ui:save-operation')
        denied = operation.startswith('denied-')
        normalized = operation.removeprefix('denied-')
        projection = 'synthetic-first' if normalized.startswith('export-') else 'initial-empty'
        step = normalized.removeprefix('export-').removeprefix('save-chooser-')
        directory = SAVE_DIRECTORY + ('/Unwritable' if denied else '')
        result = {'checked': operation}
        if step == 'wrong-entry':
            self.feedback_snapshot(projection)
            try:
                self.chooser_snapshot(mode='save')
            except UiError as error:
                require(str(error) == 'ui:chooser-entry', 'ui:save-refusal')
            else:
                raise UiError('ui:save-refusal-missing')
        elif step in ('open', 'reopen'):
            self.wait_feedback_collection()
            require(self.chooser_snapshot(mode='save', absent=True), 'ui:chooser-already-open')
            self.activate_id('feedback-download-logs')
            def ready():
                try:
                    return self.chooser_snapshot(mode='save')
                except UiError as error:
                    if str(error) in ('ui:chooser-entry', 'ui:chooser-active'):
                        return None
                    raise
            self.wait(ready, operation, prompt_in_predicate=True)
            try:
                self.chooser_snapshot(mode='open')
            except UiError as error:
                require(str(error) == 'ui:chooser-mode', 'ui:save-refusal')
            else:
                raise UiError('ui:save-refusal-missing')
            result['provider'] = {**self.chooser_metadata(mode='save'),
                                  'mode': 'save', 'caller': 'parent-feedback'}
        elif step in ('name', 'cancel-name'):
            self.save_chooser_text('name', SAVE_NAMES[step == 'cancel-name'], replace=True)
        elif step == 'location':
            self.save_chooser_text('location', directory + '/', replace=True)
        elif step == 'navigated':
            def navigated():
                _, scoped, ids, facts, _, _, _ = self.chooser_snapshot(mode='save')
                fields = [node for node in scoped if ids[node] == 'location_entry']
                require(len(fields) <= 1, 'ui:save-field-ambiguous')
                return not fields or not facts[fields[0]]['showing']
            self.wait(navigated, operation, prompt_in_predicate=True)
        elif step == 'destination':
            # Ctrl+L after navigation exposes the provider's current directory,
            # independently of the earlier text supplied before Enter.
            # Editor disappearance is not navigation completion. After the
            # single worker shortcut, wait only for its accessibility projection;
            # ambiguity and unsafe fields still refuse without replaying input.
            def ready():
                try:
                    return self.save_chooser_field('location')
                except UiError as error:
                    if str(error) == 'ui:save-field-missing':
                        return None
                    raise
            self.wait(ready, operation, prompt_in_predicate=True)
            self.save_chooser_text('location', directory)
        elif step in ('restored', 'accept'):
            if step == 'restored':
                self.save_chooser_restore_name()
            else:
                self.save_chooser_location_closed(self.chooser_snapshot(mode='save'))
                self.save_chooser_text('name', SAVE_NAMES[0])
            if step == 'accept':
                self._invoke_target(self.chooser_snapshot(mode='save')[4])
                try:
                    self.wait(lambda: self.chooser_snapshot(mode='save', absent=True),
                              'save-chooser-closed', prompt_in_predicate=True)
                except BaseException:
                    self.input_uncertain = True
                    raise
        elif step == 'cancel':
            self.save_chooser_text('name', SAVE_NAMES[1])
            self._invoke_target(self.chooser_snapshot(mode='save')[5])
            try:
                self.wait(lambda: self.chooser_snapshot(mode='save', absent=True),
                          'save-chooser-closed', prompt_in_predicate=True)
            except BaseException:
                self.input_uncertain = True
                raise
        else:
            self.wait_feedback_collection()
            if step == 'result':
                self.save_app_result('Could not save logs. Try another location.' if denied
                                     else 'Downloaded · Ready to examine')
            self.feedback_snapshot(projection)
        return result

    def save_app_result(self, expected):
        """Wait for the app's exact public outcome after the chooser has closed."""
        require(expected in ('Could not save logs. Try another location.',
                             'Downloaded · Ready to examine'), 'ui:save-app-expectation')
        def ready():
            require(self.chooser_snapshot(mode='save', absent=True), 'ui:save-chooser-remains')
            row = self.id_target('feedback-logs-row')
            require(row.get_process_id() == self.id_target('feedback-dialog').get_process_id(),
                    'ui:save-app-owner')
            descriptions = [relation.get_target(index)
                for relation in row.get_relation_set()
                if relation.get_relation_type() == self.api.RelationType.DESCRIBED_BY
                for index in range(relation.get_n_targets())]
            require(len(descriptions) == 1 and descriptions[0] in self.read_snapshot(row)[0],
                    'ui:save-app-result')
            require(descriptions[0].get_process_id() == row.get_process_id(), 'ui:save-app-owner')
            return descriptions[0].get_name() == expected
        self.wait(ready, 'save-app-result')

    def chooser_set_location(self, *, profile='standard'):
        require(profile == 'standard' or profile in BOUNDARY_FILES, 'ui:chooser-profile')
        field = self.chooser_location_field()
        editable = field.get_editable_text_iface()
        require(editable is not None, 'ui:chooser-location-editable')
        # A trailing slash denotes the prepared directory and avoids path
        # completion extending the final component during keyboard typing.
        location = CHOOSER_DIRECTORY + ('' if profile == 'standard' else '-' + profile) + '/'
        self.input_uncertain = True
        require(self.api.EditableText.set_text_contents(editable, location),
                'ui:chooser-location-refused')
        self.input_uncertain = False
        try:
            # Reacquire after the mutation; API success alone is not readback.
            text = self.chooser_location_field().get_text_iface()
            require(text is not None and self.api.Text.get_character_count(text) == len(location)
                    and self.api.Text.get_text(text, 0, len(location)) == location,
                    'ui:chooser-location')
        except BaseException:
            self.input_uncertain = True
            raise

    def chooser_operation(self, operation, *, profile='standard', boundary=None):
        require(operation in CHOOSER_OPERATIONS, 'ui:chooser-operation')
        require(boundary is None or boundary in BOUNDARY_BATCHES
                and profile == ('single' if boundary == 'changed' else boundary), 'ui:chooser-boundary')
        require(profile == 'standard' or (profile in (*BOUNDARY_BATCHES, 'single') and operation in (
            'chooser-open', 'chooser-location', 'chooser-files', 'chooser-accept')), 'ui:chooser-profile')
        def ready(read, pending):
            def observe():
                try:
                    return read()
                except UiError as error:
                    if str(error) in pending:
                        return None
                    raise
            return self.wait(observe, operation, prompt_in_predicate=True)
        if operation == 'chooser-wrong-entry':
            self.feedback_snapshot()
            try:
                self.chooser_snapshot()
            except UiError as error:
                require(str(error) == 'ui:chooser-entry', 'ui:chooser-refusal')
            else:
                raise UiError('ui:chooser-refusal-missing')
        elif operation in ('chooser-open', 'chooser-reopen'):
            if boundary is not None:
                self.feedback_snapshot(attachment_state=BOUNDARY_STATES[BOUNDARY_BATCHES[boundary][0]])
            elif profile == 'single':
                self.feedback_snapshot('formatted')
            elif profile == 'standard':
                self.feedback_snapshot(attachments=operation == 'chooser-reopen')
            else:
                self.feedback_snapshot(attachment_state=BOUNDARY_STATES[BOUNDARY_BATCHES[profile][0]])
            require(self.chooser_snapshot(absent=True), 'ui:chooser-already-open')
            self.activate_id('feedback-add-files')
            ready(self.chooser_snapshot, ('ui:chooser-entry', 'ui:chooser-active'))
            try:
                self.chooser_snapshot(mode='save')
            except UiError as error:
                require(str(error) == 'ui:chooser-mode', 'ui:chooser-refusal')
            else:
                raise UiError('ui:chooser-refusal-missing')
        elif operation == 'chooser-location':
            self.chooser_set_location(profile=profile)
        elif operation == 'chooser-files':
            ready(lambda: self.chooser_selection(profile=profile), ('ui:chooser-file-set',))
            self.chooser_select_files(profile=profile)
        elif operation in ('chooser-accept', 'chooser-cancel'):
            if operation == 'chooser-accept':
                files = CHOOSER_FILES if profile == 'standard' else tuple(name for name, _ in BOUNDARY_FILES[profile])
                _, _, _, accept, cancel, _ = self.chooser_selection(files, profile=profile)
            else:
                _, _, _, _, accept, cancel, _ = self.chooser_snapshot()
            self._invoke_target(accept if operation == 'chooser-accept' else cancel)
            try:
                self.wait(lambda: self.chooser_snapshot(absent=True), 'chooser-closed',
                          prompt_in_predicate=True)
            except BaseException:
                self.input_uncertain = True
                raise
        else:
            ready(lambda: self.feedback_snapshot(attachments=True),
                  ('ui:feedback-attachment-set', 'ui:feedback-control', 'ui:feedback-validation'))
        result = {'checked': operation}
        if operation in ('chooser-open', 'chooser-reopen'):
            result['provider'] = self.chooser_metadata()
        if operation in ('chooser-attachments', 'chooser-preserved'):
            result['attachments'] = ['diagnostic-logs.zip', *CHOOSER_FILES]
        return result

    def attachment_operation(self, operation):
        require(operation in ATTACHMENT_OPERATIONS, 'ui:attachment-operation')
        if operation == 'attachment-wrong-entry':
            self.feedback_snapshot()
            try:
                self.feedback_snapshot(attachments='details')
            except UiError as error:
                require(str(error) == 'ui:feedback-attachment-set', 'ui:attachment-refusal')
            else:
                raise UiError('ui:attachment-refusal-missing')
            return {'checked': operation}
        profile = 'remaining' if operation == 'attachment-remaining' else 'details'
        value = self.feedback_snapshot(attachments=profile)
        if operation == 'attachment-preview':
            self.feedback_snapshot(attachments='preview')
            # This binding qualifies the explicitly inapplicable branch only.
            # A newly offered action must refuse until its public preview route
            # is bound; never open an external editor or inspect private bytes.
            return {'checked': operation, 'items': value['items'], 'preview': 'not-offered'}
        if operation == 'attachment-remove':
            name, data = ATTACHMENT_INPUTS[0]
            value = self.remove_attachment(name, data,
                before=lambda: self.feedback_snapshot(attachments='details'),
                after=lambda: self.feedback_snapshot(attachments='remaining'))
        return {'checked': operation, 'items': value['items']}

    def remove_attachment(self, name, data, *, before, after):
        """One ID-bound removal, with independent complete before/after reads."""
        before()
        key = hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]
        self.activate_id('feedback-remove-attachment-' + key)
        def remaining():
            try:
                return after()
            except UiError as error:
                if str(error) != 'ui:feedback-attachment-set':
                    raise
                # Only the unchanged valid old list is pending. Wrong-item
                # removal or changed metadata refuses without replaying input.
                before()
                return None
        try:
            return self.wait(remaining, 'attachment-remaining', prompt_in_predicate=True)
        except BaseException:
            self.input_uncertain = True
            raise

    def boundary_operation(self, operation):
        require(operation in BOUNDARY_OPERATIONS, 'ui:boundary-operation')
        if operation == 'boundary-source-unchanged':
            value = self.feedback_snapshot(attachment_state=BOUNDARY_STATES['single'])
        elif operation in ('boundary-clear-small', 'boundary-clear-count', 'boundary-remove-total',
                           *BOUNDARY_REMOVALS):
            if operation == 'boundary-clear-small':
                state = (ATTACHMENT_INPUTS[1:], '2 file attachments ready.', True)
                remove = ATTACHMENT_INPUTS[1:]
            elif operation == 'boundary-clear-count':
                state = BOUNDARY_STATES['count-rejected']
                remove = state[0]
            elif operation == 'boundary-remove-total':
                state = BOUNDARY_STATES['total']
                remove = BOUNDARY_FILES['total']
            else:
                state = BOUNDARY_STATES[BOUNDARY_REMOVALS[operation][0]]
                remove = state[0]
            for name, data in remove:
                new_state = (tuple(item for item in state[0] if item[0] != name), *state[1:])
                self.remove_attachment(name, data,
                    before=lambda: self.feedback_snapshot(attachment_state=state),
                    after=lambda: self.feedback_snapshot(attachment_state=new_state))
                state = new_state
            value = self.feedback_snapshot(attachment_state=state)
        elif operation == 'boundary-exclude-logs':
            self.feedback_snapshot(attachment_state=BOUNDARY_STATES['cleared'])
            self.activate_id('feedback-toggle-logs')
            pending = None
            def excluded():
                nonlocal pending
                try:
                    return self.feedback_snapshot(attachment_state=BOUNDARY_STATES['no-logs'])
                except UiError as error:
                    if str(error) != 'ui:feedback-logs':
                        raise
                    # Name and visibility are separate public reads during the
                    # transition. A second read of the old state can race with
                    # the completed new state. Retry this result comparison;
                    # only a complete no-logs snapshot can finish the wait.
                    pending = error
                    return None
            try:
                value = self.wait(excluded, operation, prompt_in_predicate=True)
            except BaseException as error:
                self.input_uncertain = True
                if pending is not None:
                    error.add_note(str(pending))
                    for note in getattr(pending, '__notes__', ()):
                        error.add_note(note)
                raise
        else:
            _, batch, step = operation.split('-')
            before, after = (BOUNDARY_STATES[key] for key in BOUNDARY_BATCHES[batch])
            if step in ('open', 'location', 'files', 'accept'):
                chooser = self.chooser_operation('chooser-' + step,
                    profile='single' if batch == 'changed' else batch, boundary=batch)
                return {'checked': operation, **({'provider': chooser['provider']} if step == 'open' else {})}
            state = before if step == 'before' else after
            def observed():
                try:
                    return self.feedback_snapshot(attachment_state=state)
                except UiError as error:
                    if step == 'result' and str(error) in ('ui:feedback-validation',
                            'ui:feedback-attachment-set', 'ui:feedback-control', 'ui:feedback-editor'):
                        return None
                    raise
            value = self.wait(observed, operation, prompt_in_predicate=True)
        return {'checked': operation, 'items': value['items'], 'status': value['status'],
                'include_logs': value['include_logs']}

    def feedback_snapshot(self, projection='initial-empty', *, states=False, attachments=False,
                          attachment_state=None):
        """FEED03: compare a declared synthetic draft, never project arbitrary text.

        One complete public snapshot supplies ownership, the exact attachment
        set and controls. Only closed comparison values leave this method.
        """
        require(projection in FEEDBACK_PROJECTIONS, 'ui:feedback-projection')
        if projection == 'formatted-file':
            require(not states and not attachments and attachment_state is None,
                    'ui:attachment-profile')
            # Collection on reopening clears the previous attachment status;
            # both states are successful, while the exact file list is fixed.
            attachment_state = (BOUNDARY_FILES['single'], ('', '1 file attachment ready.'), True)
        if projection == 'attachment-file':
            require(not states and not attachments and attachment_state is None,
                    'ui:attachment-profile')
            attachment_state = (CHANGED_ATTACHMENT, ('', '1 file attachment ready.'), False)
        edges, identities, facts = {}, {}, {}
        nodes = list(self.nodes(strict=True, snapshot=edges, identities=identities, facts=facts))
        observation = (nodes, edges, identities, facts)
        root = self.snapshot_owned_target('feedback-dialog', observation=observation,
                                          check_prompt=True)
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:feedback-entry')
        scoped = self.snapshot_scope(nodes, edges, root)
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT) for node in scoped),
                'ui:feedback-stale')
        # GTK implementation IDs such as "box" and "title" are reusable
        # inside compound widgets. Only the feedback namespace is our public
        # control contract; its IDs must remain unique, including hidden ones.
        ids = [identities[node] for node in scoped
               if identities[node].startswith('feedback-')]
        require(len(ids) == len(set(ids)), 'ui:feedback-duplicate')

        def target(identity):
            node = self.snapshot_owned_target(identity, root=root, showing=False,
                                              observation=observation)
            require(node is not None and self.has_state(node, self.api.StateType.VISIBLE),
                    'ui:feedback-target')
            return node

        for binding in FEEDBACK_PROJECTIONS[projection]:
            identity, expected = TEXT_VALUES[binding]
            node = target(identity)
            require(node.get_role_name() != 'password text'
                    and self.has_state(node, self.api.StateType.EDITABLE)
                    and self.has_state(node, self.api.StateType.SENSITIVE),
                    'ui:feedback-editor')
            text = node.get_text_iface()
            require(text is not None, 'ui:feedback-editor')
            count = self.api.Text.get_character_count(text)
            # Quill exposes a terminal paragraph newline in WebKit. Only read
            # declared lengths; never project mismatching text into evidence.
            allowed = ((expected, expected + '\n')
                       if identity == 'feedback-editor-input' else (expected,))
            tracing = projection == 'trace-prefix' and identity == 'feedback-editor-input'
            require((0 <= count <= len(expected) + 1) if tracing else
                    count in {len(value) for value in allowed},
                    'ui:feedback-nonempty-draft')
            actual = (''.join(chr(self.api.Text.get_character_at_offset(text, offset))
                              for offset in range(count)) if binding == 'body-hidden' else
                      self.api.Text.get_text(text, 0, count) if count else '')
            require((expected.startswith(actual.removesuffix('\n'))) if tracing else actual in allowed,
                    'ui:feedback-nonempty-draft')
            if tracing:
                body = actual.removesuffix('\n')
                trace_draft = ('initial-empty' if not body else
                               'states-no-reply' if body == expected else 'trace-prefix')
        require(attachments in (False, True, 'details', 'remaining', 'preview'), 'ui:attachment-profile')
        inputs = tuple((name, data) for name, data in ATTACHMENT_INPUTS
                       if attachments != 'remaining' or name == 'Synthetic note.txt') if attachments else ()
        include_logs = True
        status_expected = '2 file attachments ready.' if attachments else None
        if attachment_state is not None:
            require(not states and not attachments and type(attachment_state) is tuple
                    and len(attachment_state) == 3, 'ui:attachment-profile')
            inputs, status_expected, include_logs = attachment_state
            attachments = 'details'
        expected_attachments = ({'feedback-attachment-' + hashlib.sha256(name.encode() + b'\0' + data).hexdigest()[:16]: name
            for name, data in inputs})
        require({value for value in ids if value.startswith('feedback-attachment-')} == set(expected_attachments),
                'ui:feedback-attachment-set')
        for identity, name in expected_attachments.items():
            require(target(identity).get_name() == name, 'ui:feedback-attachment-name')
        items = []
        if attachments in ('details', 'remaining', 'preview'):
            # Tree order is an observed result, never a target selector. Resolve
            # each row by its owned ID before reading its public name and size.
            # AdwActionRow exposes its subtitle via DESCRIBED_BY, not Description.
            for node in scoped:
                identity = identities[node]
                if identity in expected_attachments:
                    row = target(identity)
                    if attachments == 'preview':
                        row_nodes = self.snapshot_scope(nodes, edges, row)
                        require(all(child.get_process_id() == root.get_process_id()
                                    for child in row_nodes), 'ui:attachment-preview-owner')
                        availability = target(identity.replace('feedback-attachment-',
                                                               'feedback-preview-availability-'))
                        require(availability in row_nodes
                                and availability.get_name() == 'Preview is not available',
                                'ui:attachment-preview-availability')
                        remove_id = identity.replace('feedback-attachment-', 'feedback-remove-attachment-')
                        remove = target(remove_id)
                        require(remove in row_nodes, 'ui:attachment-remove-owner')
                        for child in row_nodes:
                            action = child.get_action_iface()
                            count = self.api.Action.get_n_actions(action) if action is not None else 0
                            require(type(count) is int and 0 <= count <= 32, 'ui:attachment-actions')
                            # set_automation_id publishes row.activate for all
                            # ListBoxRows, including nonactivatable attachments.
                            # That generic action is not a preview affordance.
                            names = [public_action_name(self.api, action, index) for index in range(count)]
                            expected = ({'row.activate'} if child == row else {'click'} if child == remove else
                                ATTACHMENT_LABEL_ACTIONS if child.get_role_name() == 'label' and count else set())
                            # GtkLabel publishes generic text/clipboard/link
                            # actions even for these plain synthetic labels.
                            # They are not attachment preview affordances.
                            matched = len(names) == len(expected) and set(names) == expected
                            if not matched:
                                print(json.dumps({'event': 'attachment-action-mismatch',
                                    'target': 'row' if child == row else 'remove' if child == remove else 'descendant',
                                    'action_count': count}, sort_keys=True),
                                    file=sys.stderr, flush=True)
                            require(matched, 'ui:attachment-preview-offered')
                    descriptions = [relation.get_target(index)
                        for relation in row.get_relation_set()
                        if relation.get_relation_type() == self.api.RelationType.DESCRIBED_BY
                        for index in range(relation.get_n_targets())]
                    require(len(descriptions) == 1, 'ui:attachment-size-relation')
                    subtitle = descriptions[0]
                    require(subtitle != row
                            and subtitle in self.snapshot_scope(nodes, edges, row)
                            and self.has_state(subtitle, self.api.StateType.VISIBLE),
                            'ui:attachment-size-owner')
                    size = subtitle.get_name()
                    expected_size = next(attachment_size(data) for name, data in inputs
                                         if name == expected_attachments[identity])
                    require(size == expected_size, 'ui:attachment-size')
                    items.append([row.get_name(), size])
            expected_items = [[name, attachment_size(data)] for name, data in inputs]
            require(items == expected_items, 'ui:attachment-details')
        logs = target('feedback-logs-row')
        expected_logs_name = 'diagnostic-logs.zip' if include_logs else 'No logs attached'
        logs_name = logs.get_name()
        if logs_name != expected_logs_name:
            error = UiError('ui:feedback-logs')
            observed_name = (logs_name if logs_name in ('diagnostic-logs.zip', 'No logs attached')
                             else '[unrecognized name]')
            error.add_note(f'Expected logs row: {expected_logs_name!r}; observed: {observed_name!r}')
            raise error
        for identity in ('feedback-collection-status', 'feedback-retry-logs',
                         'feedback-send-without-logs'):
            node = self.snapshot_owned_target(identity, root=root, showing=False,
                                              observation=observation)
            require(node is None or not self.has_state(node, self.api.StateType.VISIBLE),
                    'ui:feedback-collection')
        status = self.snapshot_owned_target('feedback-status', root=root, showing=False,
                                            observation=observation)
        status_text = (status.get_name() if status is not None
                       and self.has_state(status, self.api.StateType.VISIBLE) else '')
        require((status_text in status_expected if type(status_expected) is tuple
                 else status_text == status_expected) if attachments else
                status_text in FEEDBACK_VALIDATION if states else status_text == '',
                'ui:feedback-validation')
        for identity in ('feedback-close', 'feedback-send', 'feedback-add-files',
                         'feedback-download-logs', 'feedback-toggle-logs'):
            if not include_logs and identity == 'feedback-download-logs':
                node = self.snapshot_owned_target(identity, root=root, showing=False,
                                                  observation=observation)
                require(node is None or not self.has_state(node, self.api.StateType.VISIBLE),
                        'ui:feedback-logs')
                continue
            if states and identity == 'feedback-send':
                continue
            require(self.has_state(target(identity), self.api.StateType.SENSITIVE),
                    'ui:feedback-control')
        if states:
            return {'draft': trace_draft if projection == 'trace-prefix' else projection,
                    'attachments': ['diagnostic-logs.zip'],
                    'collection': 'ready', 'validation': FEEDBACK_VALIDATION[status_text],
                    'controls': 'ready',
                    'send_enabled': bool(self.has_state(target('feedback-send'),
                                                       self.api.StateType.SENSITIVE))}
        result = {'draft': projection, 'attachments': [*(['diagnostic-logs.zip'] if include_logs else []), *sorted(expected_attachments.values())],
                  'collection': 'ready', 'validation': 'none', 'controls': 'ready'}
        if attachments in ('details', 'remaining', 'preview'):
            result['items'] = items
        if attachment_state is not None:
            result['status'] = status_text
            result['include_logs'] = include_logs
        if projection in ('formatted', 'formatted-file'):
            result['formats'] = self.basic_feedback_formatting()
        return result

    def basic_feedback_formatting(self):
        """Installed sample: exact ordinary text/emoji and one bold range."""
        self.read_synthetic_text('body-smoke')
        root = self.text_recipient('feedback-editor-input')
        require(block_semantics.read_blocks(root, require) == []
                and feedback_formats.read_links(root, require) is None, 'ui:draft-basic-format')
        for start, end, weight in ((0, 9, 'bold'), (9, len(TEXT_VALUES['body-smoke'][1]), 'normal')):
            require(self.formatting_attributes(start, end, binding='body-smoke')['weight'] == weight,
                    'ui:draft-basic-format')
        return {'blocks': [], 'inline': ['bold'], 'link': None,
                'normal_comparison': True, 'text_exact': True}

    def feedback_draft_operation(self, operation):
        """Shared formatted/file-bearing observations around public lifecycle actions."""
        require(operation in DRAFT_OPERATIONS, 'ui:draft-operation')
        base = operation.removeprefix('draft-')
        if base.startswith('chooser-'):
            return {'chooser': self.chooser_operation(base, profile='single')}
        if base.startswith('switch-'):
            return {'window': self.window_switch_operation(base, projection='formatted-file')}
        if base in ('feedback-reopen', 'feedback-reread'):
            value = self.feedback_read_operation(base)
            root = self.text_recipient('feedback-editor-input')
            require(block_semantics.read_blocks(root, require) == []
                    and feedback_formats.read_links(root, require) is None, 'ui:draft-reset-format')
            text = root.get_text_iface()
            attrs, first, last = text.get_attribute_run(0, True)
            require(type(attrs) is dict and first == 0 and last >= 0
                    and all(attrs.get(key) == expected for key, expected in (
                        ('weight', '400'), ('style', 'normal'), ('underline', 'none'),
                        ('strikethrough', 'false'))), 'ui:draft-reset-format')
            return {'draft_state': {**value, 'items': [], 'formats': {
                'blocks': [], 'inline': [], 'link': None, 'normal_comparison': True,
                'text_exact': True}}}
        value = self.feedback_privacy_operation(base, projection='formatted-file')
        if value is None:
            return {}
        return {'draft_state': {key: item for key, item in value.items()
                                if key not in ('status', 'include_logs')}}

    def attachment_review_operation(self, operation):
        require(operation in FILE_REVIEW_OPERATIONS, 'ui:file-review-operation')
        base = operation.removeprefix('files-')
        if base.startswith('switch-'):
            return {'window': self.window_switch_operation(base, projection='attachment-file')}
        value = self.feedback_privacy_operation(base, projection='attachment-file')
        return {} if value is None else {'file_draft': {
            key: item for key, item in value.items() if key != 'status'}}

    def feedback_state_operation(self, operation):
        """FEED09 reads after caller-owned edits; never invokes Send."""
        require(operation in FEEDBACK_STATE_OPERATIONS, 'ui:feedback-operation')
        if operation == 'feedback-state-wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'),
                    'ui:feedback-wrong-entry')
            try:
                self.feedback_snapshot('synthetic-first', states=True)
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:feedback-refusal')
            else:
                raise UiError('ui:feedback-wrong-entry-accepted')
            return None
        if operation == 'feedback-state-close':
            self.feedback_snapshot('synthetic-first', states=True)
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'),
                      'feedback-closed')
            self.parent()
            return None
        projection = FEEDBACK_STATE_PROJECTIONS[operation]
        if operation == 'feedback-state-reopen':
            self.open_feedback(projection)
        return self.feedback_snapshot(projection, states=True)

    def rejection_formatting(self):
        """Read each synthetic line's public attributes, never HTML or a draft."""
        self.read_synthetic_text('body-complex')
        text = self.text_recipient('feedback-editor-input').get_text_iface()
        offset = 0
        while offset < len(COMPLEX_BODY):
            attributes, first, last = self.api.Text.get_attribute_run(text, offset, True)
            require(type(attributes) is dict and 0 <= first <= offset < last
                    <= len(COMPLEX_BODY) + 1, 'ui:rejection-format-range')
            for key, value in (
                ('weight', '700'), ('style', 'italic'), ('underline', 'single'),
                ('strikethrough', 'true')):
                require(attributes.get(key) == value,
                        f'ui:rejection-format-proof:{key}:{offset}')
            # The public run proves every character up to its exclusive end.
            # Continue at the first unproven x, skipping only paragraph breaks.
            offset = last + last % 2

    def reject_invalid_feedback(self, case):
        """One invalid-only action. No valid-body fallback or input repair."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(case in REJECTION_CASES, 'ui:rejection-valid-refused')
        projection, _ = REJECTION_CASES[case]
        state = self.feedback_snapshot(projection, states=True)
        require(state['send_enabled'], 'ui:rejection-send-disabled')
        if projection.startswith('length-'):
            body = TEXT_VALUES[FEEDBACK_PROJECTIONS[projection][0]][1]
            require(len(body.encode('utf-16-le')) // 2 == 5001, 'ui:rejection-length-limit')
            self.feedback_plain_text(projection)
        if projection == 'rejection-complex':
            self.rejection_formatting()
            # Quill's four inline formats in each normal paragraph require
            # at least <p><strong><em><u><s>x</s></u></em></strong></p>.
            # This is a conservative size proof, not acceptance evidence.
            require(COMPLEX_LINES * 48 > 50000 and len(COMPLEX_BODY) <= 5000,
                    'ui:rejection-format-limit')
        # Reacquire the exact public draft after the potentially lengthy range
        # read. Prompt/ownership/duplicate/stale guards all run again.
        self.feedback_snapshot(projection, states=True)
        self.activate_id('feedback-send')

    def feedback_plain_text(self, projection):
        """Prove normal public attributes over every declared body character."""
        binding = FEEDBACK_PROJECTIONS[projection][0]
        self.read_synthetic_text(binding)
        value = TEXT_VALUES[binding][1]
        text = self.text_recipient('feedback-editor-input').get_text_iface()
        offset = 0
        while offset < len(value):
            attrs, first, last = self.api.Text.get_attribute_run(text, offset, True)
            require(type(attrs) is dict and 0 <= first <= offset < last <= len(value) + 1,
                    'ui:length-attribute-range')
            require(attrs.get('weight') == '400' and attrs.get('style') == 'normal'
                    and attrs.get('underline') == 'none' and attrs.get('strikethrough') == 'false',
                    'ui:length-formatting')
            offset = last

    def length_operation(self, operation):
        require(operation in LENGTH_OPERATIONS, 'ui:length-operation')
        _, family, action = operation.split('-', 2)
        projection = f'length-{family}-5001'
        if action == 'wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'), 'ui:length-entry')
            try:
                self.reject_invalid_feedback(family)
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:length-refusal')
            else:
                raise UiError('ui:length-refusal-missing')
            return
        if action == 'refusal':
            self.feedback_snapshot(f'length-{family}-5000', states=True)
            try:
                self.reject_invalid_feedback(family)
            except UiError as error:
                require(str(error) == 'ui:feedback-nonempty-draft', 'ui:length-refusal')
            else:
                raise UiError('ui:length-refusal-missing')
            return
        if action == 'close':
            self.feedback_snapshot(projection, states=True)
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'), 'feedback-closed')
            self.parent()
            return
        if action == 'reopen':
            self.open_feedback(projection)
        projection, _ = LENGTH_OBSERVATIONS[operation]
        self.feedback_plain_text(projection)
        return self.feedback_snapshot(projection, states=True)

    def rejection_operation(self, operation):
        require(operation in REJECTION_OPERATIONS, 'ui:rejection-operation')
        if operation == 'rejection-valid-refusal':
            self.feedback_snapshot('states-no-reply', states=True)
            try:
                self.reject_invalid_feedback('valid')
            except UiError as error:
                require(str(error) == 'ui:rejection-valid-refused', 'ui:rejection-refusal')
            else:
                raise UiError('ui:rejection-refusal-missing')
            return
        if operation == 'rejection-wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'),
                    'ui:rejection-entry')
            try:
                self.reject_invalid_feedback('complex')
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:rejection-refusal')
            else:
                raise UiError('ui:rejection-refusal-missing')
            return
        if operation == 'rejection-hidden-focus':
            self.read_synthetic_text('body-hidden-base')
            self.focus_text('feedback-editor-input')
            return
        if operation == 'rejection-hidden-caret':
            self.read_synthetic_text('body-hidden-base')
            node = self.text_recipient('feedback-editor-input', focused=True)
            require(self.api.Text.get_caret_offset(node.get_text_iface()) == 1,
                    'ui:rejection-hidden-caret')
            return
        if operation == 'rejection-hidden-input-read':
            self.read_synthetic_text('body-hidden')
            return
        if operation.startswith('rejection-format-'):
            kind, action = operation.removeprefix('rejection-format-').rsplit('-', 1)
            self.read_synthetic_text('body-complex')
            if action == 'focus':
                self.focus_text('feedback-editor-input')
            else:
                text = self.text_recipient('feedback-editor-input', focused=True).get_text_iface()
                require(self.api.Text.get_n_selections(text) == 1, 'ui:rejection-selection')
                selection = self.api.Text.get_selection(text, 0)
                require(selection.start_offset == 0 and selection.end_offset
                        in (len(COMPLEX_BODY), len(COMPLEX_BODY) + 1), 'ui:rejection-selection')
                self.activate_id('feedback-format-' + kind)
            return
        if operation == 'rejection-close':
            self.feedback_snapshot('rejection-complex', states=True)
            self.rejection_formatting()
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'),
                      'feedback-closed')
            self.parent()
            return
        if operation == 'rejection-reopen':
            self.activate_id('parent-feedback-button')
            self.id_target('feedback-editor-input', sensitive=True)
            def ready():
                try:
                    return self.feedback_snapshot('rejection-complex', states=True)
                except UiError as error:
                    if str(error) in ('ui:feedback-collection', 'ui:feedback-target'):
                        return None
                    raise
            result = self.wait(ready, 'feedback-ready')
            self.rejection_formatting()
            return result
        case, action = operation.removeprefix('rejection-').rsplit('-', 1)
        if action == 'send':
            self.reject_invalid_feedback(case)
            return
        projection, explanation = REJECTION_CASES[case]
        def rejected():
            result = self.feedback_snapshot(projection, states=True)
            return result if result['validation'] == explanation and result['send_enabled'] else None
        return self.wait(rejected, 'rejection-explanation')

    def block_semantics(self):
        self.read_synthetic_text('body-blocks')
        return block_semantics.read_blocks(self.text_recipient('feedback-editor-input'), require)

    def block_operation(self, operation):
        require(operation in block_semantics.OPERATIONS, 'ui:block-operation')
        if operation == 'block-wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'), 'ui:block-entry')
            try:
                self.block_semantics()
            except UiError as error:
                require(str(error) == 'ui:text-entry', 'ui:block-refusal')
            else:
                raise UiError('ui:block-refusal-missing')
            return None
        if operation == 'block-reopen':
            self.activate_id('parent-feedback-button')
            self.wait(lambda: self.id_target('feedback-editor-input', sensitive=True),
                      'block-editor')
        self.read_synthetic_text('body-blocks')
        if operation == 'block-close':
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'),
                      'feedback-closed')
            self.parent()
        elif operation.endswith('-focus'):
            self.focus_text('feedback-editor-input')
        elif operation.endswith(('-home', '-selected')):
            text = self.text_recipient('feedback-editor-input', focused=True).get_text_iface()
            if operation.endswith('-home'):
                require(self.api.Text.get_caret_offset(text) == 0, 'ui:block-caret')
            else:
                kind = operation.removeprefix('block-').removesuffix('-selected')
                require(self.api.Text.get_n_selections(text) == 1, 'ui:block-selection')
                selected = self.api.Text.get_selection(text, 0)
                require((selected.start_offset, selected.end_offset) == block_semantics.RANGES[kind],
                        'ui:block-selection')
                if kind.startswith('heading-'):
                    self.activate_id('feedback-format-style')
                self.activate_id('feedback-format-' + kind)
        else:
            result = self.block_semantics()
            require(result == block_semantics.expected(operation), 'ui:block-result')
            return result
        return None

    def formatting_attributes(self, start, end, *, binding='body-first'):
        """UI24: bounded public weight runs over the declared synthetic body."""
        require(binding in ('body-first', 'body-smoke') and type(start) is int and type(end) is int
                and 0 <= start < end <= len(TEXT_VALUES[binding][1]),
                'ui:format-range')
        self.read_synthetic_text(binding)
        node = self.text_recipient('feedback-editor-input')
        text = node.get_text_iface()
        # Query inside the requested run: WebKit can report the preceding run
        # at its exclusive end. The returned bounds must nevertheless cover
        # EVERY requested character; a mixed or unavailable range still refuses.
        offset = (start + end) // 2
        attributes, first, last = self.api.Text.get_attribute_run(text, offset, True)
        require(type(attributes) is dict and 0 <= first <= start < end <= last
                and last <= self.api.Text.get_character_count(text),
                'ui:format-attributes')
        weight = attributes.get('weight', '')
        require(weight in ('400', '700'), 'ui:format-weight-unavailable')
        return {'start': start, 'end': end, 'weight': 'bold' if weight == '700' else 'normal'}

    def format_operation(self, operation):
        require(operation in FORMAT_OPERATIONS, 'ui:format-operation')
        if operation == 'format-wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'),
                    'ui:format-entry')
            try:
                self.formatting_attributes(0, 9)
            except UiError as error:
                require(str(error) == 'ui:text-entry', 'ui:format-refusal')
            else:
                raise UiError('ui:format-refusal-missing')
            return None
        if operation == 'format-reopen':
            self.open_feedback('states-no-reply')
        self.read_synthetic_text('body-first')
        if operation == 'format-focus':
            self.focus_text('feedback-editor-input')
        elif operation in ('format-home', 'format-selected'):
            node = self.text_recipient('feedback-editor-input', focused=True)
            text = node.get_text_iface()
            if operation == 'format-home':
                require(self.api.Text.get_caret_offset(text) == 0, 'ui:format-caret')
            else:
                require(self.api.Text.get_n_selections(text) == 1, 'ui:format-selection')
                selected = self.api.Text.get_selection(text, 0)
                require((selected.start_offset, selected.end_offset) == (0, 9),
                        'ui:format-selection')
                self.activate_id('feedback-format-bold')
        elif operation == 'format-close':
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'),
                      'feedback-closed')
            self.parent()
        else:
            result = [self.formatting_attributes(0, 9), self.formatting_attributes(9, 23)]
            expected = 'normal' if operation == 'format-before' else 'bold'
            require(result[0]['weight'] == expected and result[1]['weight'] == 'normal',
                    'ui:format-result')
            return result
        return None

    def text_recipient(self, identity, *, focused=False, child=CHILD):
        """Fresh UI16 recipient proof; refuse before focus, keys or Text access."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        node = self.snapshot_owned_target(identity, showing=False, check_prompt=True)
        require(node is not None, 'ui:text-entry')
        require(self.has_state(node, self.api.StateType.VISIBLE)
                and self.has_state(node, self.api.StateType.SENSITIVE)
                and not self.has_state(node, self.api.StateType.DEFUNCT),
                'ui:text-disabled')
        require(identity in {item[0] for item in TEXT_VALUES.values()}, 'ui:text-binding')
        require(node.get_role_name() != 'password text'
                and self.has_state(node, self.api.StateType.EDITABLE), 'ui:text-editor')
        surface = ('parent-match-rule-dialog' if identity == 'parent-match-rule-entry' else
                   'kiosk-request-window' if identity == 'kiosk-custom-duration' else
                   'parent-window' if identity in ('parent-custom-daily-limit', 'parent-app-search')
                   else 'feedback-dialog')
        root = self.snapshot_owned_target(surface, check_prompt=True)
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:text-entry')
        require(self.snapshot_owned_target(identity, root=root, showing=False) is not None,
                'ui:text-entry')
        if identity == 'parent-custom-daily-limit':
            self.allowance_entry(child)
        if identity == 'parent-app-search':
            picker = self.id_target('parent-child-selector', root=root, sensitive=True)
            require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                          showing=True) is not None, 'ui:wrong-child')
            page = self.snapshot_owned_target('parent-app-limits-page', root=root, showing=False)
            require(page is not None and self.has_state(page, self.api.StateType.VISIBLE)
                    and self.snapshot_owned_target(identity, root=page, showing=False) is not None,
                    'ui:app-row-page')
        if identity == 'kiosk-custom-duration':
            self.kiosk_valid_target(identity, overlay=getattr(self, 'text_overlay', False))
        if identity == 'parent-match-rule-entry':
            self.match_entry(child, MATCH_APP, editor=True)
        require(not focused or self.has_state(node, self.api.StateType.FOCUSED),
                'ui:text-focus')
        return node

    def focus_text(self, identity, *, child=CHILD):
        # Retry only the complete read before dispatch, never the focus action.
        node = self.wait(lambda: self.text_recipient(identity, child=child),
                         'text-focus-entry')
        if identity in ('parent-custom-daily-limit', 'parent-app-search', 'kiosk-custom-duration', 'parent-match-rule-entry'):
            surface = ('parent-match-rule-dialog' if identity == 'parent-match-rule-entry' else
                       'kiosk-request-window' if identity == 'kiosk-custom-duration' else 'parent-window')
            self.activate_id(surface, action_name='focus.' + identity)
            self.wait(lambda: self.has_state(self.text_recipient(identity, child=child),
                                            self.api.StateType.FOCUSED), 'text-focus')
            self.text_recipient(identity, focused=True, child=child)
            return
        # Native GTK entries do not implement Component.GrabFocus. Their
        # composite uses Ctrl-Tab from this ID-resolved WebKit editor instead.
        require(identity == 'feedback-editor-input', 'ui:text-focus-route')
        component = node.get_component_iface()
        require(component is not None, 'ui:text-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:text-focus-refused')
        def focused():
            current = self.snapshot_owned_target(identity, check_prompt=True)
            return current is not None and self.has_state(current, self.api.StateType.FOCUSED)
        self.wait(focused, 'text-focus')
        self.input_uncertain = False
        self.text_recipient(identity, focused=True)

    def read_synthetic_text(self, binding, *, child=CHILD):
        """Bounded exact public comparison; mismatching/private text never leaves."""
        require(binding in TEXT_VALUES, 'ui:text-binding')
        identity, expected = TEXT_VALUES[binding]
        node = self.text_recipient(identity, child=child)
        text = node.get_text_iface()
        require(text is not None, 'ui:text-editor')
        count = self.api.Text.get_character_count(text)
        allowed = (expected, expected + '\n') if identity == 'feedback-editor-input' else (expected,)
        require(count in {len(value) for value in allowed}, 'ui:text-value')
        actual = (''.join(chr(self.api.Text.get_character_at_offset(text, offset))
                          for offset in range(count)) if binding == 'body-hidden' else
                  self.api.Text.get_text(text, 0, count) if count else '')
        require(actual in allowed, 'ui:text-value')
        return {'binding': binding, 'exact': True, 'length': len(expected)}

    def text_operation(self, operation, *, child=CHILD):
        if operation in ('text-wrong-entry', 'text-disabled'):
            identity = ('feedback-editor-input' if operation == 'text-wrong-entry'
                        else 'parent-daily-limit-selector')
            expected = 'ui:text-entry' if operation == 'text-wrong-entry' else 'ui:text-disabled'
            try:
                self.focus_text(identity)
            except UiError as error:
                require(str(error) == expected, 'ui:text-refusal')
            else:
                raise UiError('ui:text-refusal-missing')
            return None
        require(operation in TEXT_OPERATIONS, 'ui:text-operation')
        binding, action = TEXT_OPERATIONS[operation]
        identity, _ = TEXT_VALUES[binding]
        if action == 'anchor':
            self.wait(lambda: self.text_recipient(identity), 'text-anchor-entry')
            self.focus_text('feedback-editor-input')
        elif action == 'focus' and identity == 'feedback-reply-email':
            def focused():
                node = self.text_recipient(identity)
                return self.has_state(node, self.api.StateType.FOCUSED)
            self.wait(focused, 'text-focus')
        elif action == 'focus':
            self.focus_text(identity, child=child)
        elif action == 'selected':
            # A toast or animation may disappear after Ctrl+A. Reacquire the
            # complete focused-recipient proof; never repeat the keyboard input.
            self.wait(lambda: self.text_recipient(identity, focused=True, child=child),
                      'text-selected')
        else:
            if identity == 'parent-custom-daily-limit':
                # Debounce/Return/Tab may already have started an asynchronous
                # save. Read only after its public controls are usable again.
                self.parent_save_snapshot(child, True)
            def ready():
                try:
                    return self.read_synthetic_text(binding, child=child)
                except UiError as error:
                    if str(error) == 'ui:text-value':
                        return None
                    raise
            return self.wait(ready, 'text-exact-value')
        return None

    def duplicate_text_operation(self, operation):
        """Select/copy only declared text; independently verify each doubled result."""
        require(operation in DUPLICATE_OPERATIONS, 'ui:duplicate-operation')
        binding, action = DUPLICATE_OPERATIONS[operation]
        source = TEXT_DUPLICATIONS[binding]
        identity, value = TEXT_VALUES[source]
        separator = TEXT_DUPLICATION_SEPARATORS[binding]
        require(TEXT_VALUES[binding] == (identity, value + separator + value),
                'ui:duplicate-binding')
        if action == 'read':
            return self.text_operation('text-' + binding + '-read')
        self.read_synthetic_text(source)
        if action == 'focus':
            self.focus_text(identity)
            return
        text = self.text_recipient(identity, focused=True).get_text_iface()
        require(self.api.Text.get_n_selections(text) == 1, 'ui:duplicate-selection')
        if action == 'select':
            # Exclude Quill's implicit terminal paragraph newline explicitly.
            # Otherwise copy/paste can add blank paragraphs or join two lines.
            self.input_uncertain = True
            require(self.api.Text.set_selection(text, 0, 0, len(value)),
                    'ui:duplicate-selection-refused')
            self.input_uncertain = False
            return
        selected = self.api.Text.get_selection(text, 0)
        require((selected.start_offset, selected.end_offset) == (0, len(value)),
                'ui:duplicate-selection')
        return None

    def scalar_text_operation(self, operation):
        """Prove the exact source and scalar caret before ordinary Unicode input."""
        require(operation in SCALAR_OPERATIONS, 'ui:scalar-operation')
        binding, action = SCALAR_OPERATIONS[operation]
        source, codepoint = TEXT_SCALARS[binding]
        return self.append_text_operation(binding, action, source, chr(int(codepoint, 16)))

    def suffix_text_operation(self, operation):
        """Prove the clipboard-built source before typing its short remainder."""
        require(operation in SUFFIX_OPERATIONS, 'ui:suffix-operation')
        binding, action = SUFFIX_OPERATIONS[operation]
        source, suffix = TEXT_SUFFIXES[binding]
        return self.append_text_operation(binding, action, source, suffix)

    def append_text_operation(self, binding, action, source, suffix):
        identity, value = TEXT_VALUES[source]
        require(TEXT_VALUES[binding] == (identity, value + suffix),
                'ui:scalar-binding')
        if action == 'read':
            return self.text_operation('text-' + binding + '-read')
        self.read_synthetic_text(source)
        if action == 'focus':
            self.focus_text(identity)
        else:
            text = self.text_recipient(identity, focused=True).get_text_iface()
            require(self.api.Text.get_caret_offset(text) == len(value), 'ui:scalar-caret')
        return None

    def open_feedback(self, projection='initial-empty'):
        """FEED01: ordinary Parent entry, with an independently observed result."""
        require(projection in FEEDBACK_PROJECTIONS, 'ui:feedback-projection')
        self.activate_id('parent-feedback-button')
        self.id_target('feedback-editor-input', sensitive=True)
        def ready():
            try:
                return self.feedback_snapshot(projection)
            except UiError as error:
                if str(error) in ('ui:feedback-collection', 'ui:feedback-target'):
                    return None
                raise
        return self.wait(ready, 'feedback-ready')

    def feedback_collection_source(self):
        """Pin an active management entry before the dialog exists."""
        import hashlib
        observation = self.read_snapshot()
        root = self.snapshot_owned_target('parent-window', observation=observation, check_prompt=True)
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:collection-entry')
        require(self.snapshot_owned_target('feedback-dialog', observation=observation,
                                          showing=False) is None, 'ui:collection-entry')
        button = self.snapshot_owned_target('parent-feedback-button', root=root,
                                            observation=observation)
        require(button is not None and self.has_state(button, self.api.StateType.SENSITIVE)
                and root.bus == button.bus and root.bus.startswith(':'), 'ui:collection-entry')
        self.collection_owner = (root.bus, root.path)
        nodes, _edges, identities, _facts = observation
        self.collection_application = self.snapshot_matches(
            PARENT_APPLICATION, nodes, showing=False, identities=identities)
        require(self.collection_application is not None
                and self.collection_application.bus == root.bus, 'ui:collection-entry')
        return hashlib.sha256(json.dumps([(n.bus, n.path) for n in (root, button)]).encode()).hexdigest()

    def feedback_collection_sample(self):
        """Read only ID-owned collection and Download public state."""
        # Entry/input and final verification retain full-desktop prompt guards.
        # This read-only trace must not traverse unrelated applications between
        # samples: GTK creates these controls with their initial state already
        # set, without emitting collection-visible/Download-sensitive events.
        # Keep the entire pinned application for unique-ID and surface ownership
        # checks; never narrow to an unverified event subtree.
        dialog_root = getattr(self, 'collection_dialog', None)
        observation = self.read_snapshot(dialog_root or self.collection_application)
        if dialog_root is not None:
            nodes, edges, identities, facts = observation
            root = self.snapshot_matches('feedback-dialog', nodes, showing=False,
                                         identities=identities)
            require(root is dialog_root and root.bus == self.collection_owner[0],
                    'ui:trace-source-changed')
            row = self.snapshot_matches('feedback-collection-status', nodes, showing=False,
                                         identities=identities)
            download = self.snapshot_matches('feedback-download-logs', nodes, showing=False,
                                             identities=identities)
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in (root, row, download) if node is not None),
                    'ui:feedback-stale')
            collecting = row is not None and self.has_state(row, self.api.StateType.VISIBLE)
            if collecting:
                if row.get_name() != 'Collecting diagnostic information...':
                    return None
            if download is None and not collecting:
                return None
            return {'collecting': bool(collecting), 'download': bool(
                download is not None and self.has_state(download, self.api.StateType.VISIBLE)
                and self.has_state(download, self.api.StateType.SENSITIVE))}
        parent = self.snapshot_owned_target('parent-window', observation=observation,
                                            check_prompt=False)
        require(parent is not None and (parent.bus, parent.path) == self.collection_owner,
                'ui:trace-source-changed')
        root = self.snapshot_owned_target('feedback-dialog', observation=observation,
                                          check_prompt=False, showing=False)
        if root is None:
            return None
        require(root.bus == self.collection_owner[0], 'ui:trace-source-changed')
        require(not self.has_state(root, self.api.StateType.DEFUNCT), 'ui:feedback-stale')
        row = self.snapshot_owned_target('feedback-collection-status', root=root,
                                         observation=observation, showing=False)
        download = self.snapshot_owned_target('feedback-download-logs', root=root,
                                              observation=observation, showing=False)
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                    for node in (row, download) if node is not None), 'ui:feedback-stale')
        collecting = row is not None and self.has_state(row, self.api.StateType.VISIBLE)
        if collecting:
            if row.get_name() != 'Collecting diagnostic information...':
                return None
        # Collection hides the attachment subtree containing Download. Its
        # absence in this complete owned surface is observed unavailability,
        # not a missing sample or an inferred sensitive-state transition.
        # Before either control appears there is no collection sample yet.
        if download is None and not collecting:
            return None
        return {'collecting': bool(collecting), 'download': bool(
            download is not None and
            self.has_state(download, self.api.StateType.VISIBLE) and
            self.has_state(download, self.api.StateType.SENSITIVE))}

    def feedback_collection_event_target(self, path, field=None):
        """Resolve one dynamic event by public ID within the owned dialog."""
        node = self.api.node((self.collection_owner[0], path))
        identity = public_automation_id(node)
        self.collection_event_identity = identity if identity in (
            'feedback-dialog', 'feedback-webview', 'feedback-collection-status',
            'feedback-download-logs', 'feedback-send', 'feedback-close',
            'feedback-add-files') else 'other'
        if identity not in ('feedback-collection-status', 'feedback-download-logs'):
            return None
        if field is not None and field != (
                'visible' if identity == 'feedback-collection-status' else 'sensitive'):
            # GTK also emits sensitivity changes for the now-hidden status
            # row. Its label is no longer exposed and that event contributes
            # nothing to the collection/Download projection.
            return None
        require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:feedback-stale')
        seen = set()
        parent = node.get_parent()
        while parent is not None and len(seen) < 32:
            key = (parent.bus, parent.path)
            require(key not in seen and parent.bus == self.collection_owner[0],
                    'ui:trace-source-changed')
            seen.add(key)
            if public_automation_id(parent) == 'feedback-dialog':
                return ('row' if identity == 'feedback-collection-status' else 'download',
                        parent.path)
            parent = parent.get_parent()
        raise UiError('ui:collection-event-owner')

    def feedback_collection_pins(self):
        """Bind both dynamic controls to one complete, owned public surface."""
        self.invalidate_observation()
        observation = self.read_snapshot(self.collection_application)
        parent = self.snapshot_owned_target('parent-window', observation=observation,
                                            check_prompt=False)
        require(parent is not None and (parent.bus, parent.path) == self.collection_owner,
                'ui:trace-source-changed')
        dialog = self.snapshot_owned_target('feedback-dialog', observation=observation,
                                            check_prompt=False, showing=False)
        require(dialog is not None and dialog.bus == parent.bus, 'ui:collection-event-owner')
        row = self.snapshot_owned_target('feedback-collection-status', root=dialog,
                                         observation=observation, showing=False)
        download = self.snapshot_owned_target('feedback-download-logs', root=dialog,
                                              observation=observation, showing=False)
        # These controls are exposed at different points in collection. Keep
        # their identities when present without requiring both in every tree.
        return {'dialog': dialog.path,
                'row': row.path if row is not None else None,
                'download': download.path if download is not None else None}

    def wait_feedback_collection(self):
        """FEED09: wait for observed ready diagnostics, without requiring a transient.

        This Parent feedback block uses the shared predicate wait, including its
        prompt, fresh-read and deadline guards. Time alone never satisfies it.
        """
        observation = self.read_snapshot()
        parent = self.snapshot_owned_target('parent-window', observation=observation,
                                            check_prompt=True)
        require(parent is not None, 'ui:collection-entry')
        nodes, _edges, identities, _facts = observation
        application = self.snapshot_matches(PARENT_APPLICATION, nodes, showing=False,
                                             identities=identities)
        require(application is not None and application.bus == parent.bus,
                'ui:collection-entry')
        self.collection_owner = (parent.bus, parent.path)
        self.collection_application = application

        def ready():
            value = self.feedback_collection_sample()
            return value if value == {'collecting': False, 'download': True} else None

        return self.wait(ready, 'feedback-collection-ready')

    def feedback_collection_events(self, operation):
        """Open once under the existing input guard and wait for ready diagnostics."""
        if operation == 'feedback-collection-refused':
            self.feedback_snapshot(states=True)
            try:
                self.feedback_collection_source()
            except UiError as error:
                require(str(error) == 'ui:collection-entry', 'ui:collection-refusal')
                return {'refusal': 'wrong-surface'}
            raise UiError('ui:collection-refusal-missing')
        source = self.feedback_collection_source()
        if operation == 'feedback-collection-open':
            require(source == self.trace_request, 'ui:trace-source-changed')
            self.open_feedback()
            return {'opened': True}
        token = self.trace_request
        require(type(token) is str and re.fullmatch(r'[0-9a-f]{32}', token), 'ui:trace-token')
        started = time.monotonic()
        print(json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                          'source': source, 'boot_sha256': self.trace_boot,
                          'checked': False}, sort_keys=True), flush=True)
        current = self.wait_feedback_collection()
        self.invalidate_observation()
        self.feedback_snapshot(states=True)
        elapsed = int((time.monotonic() - started) * 1000)
        require(elapsed < 60000, 'ui:collection-not-ready')
        return {'token': token, 'source': source, 'terminal': True,
                'samples': [{'elapsed_ms': elapsed, **current}]}

    def feedback_read_operation(self, operation):
        require(operation in FEEDBACK_READ_OPERATIONS, 'ui:feedback-operation')
        if operation in ('feedback-open', 'feedback-reopen'):
            return self.open_feedback()
        if operation in ('feedback-close', 'feedback-finished'):
            self.feedback_snapshot()
            self.activate_id('feedback-close')
            self.wait(lambda: self.absent_id('feedback-dialog', within='parent-window'),
                      'feedback-closed')
            self.parent()
            return None
        if operation == 'feedback-wrong-entry':
            require(self.absent_id('feedback-dialog', within='parent-window'),
                    'ui:feedback-wrong-entry')
            try:
                self.feedback_snapshot()
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:feedback-refusal')
            else:
                raise UiError('ui:feedback-wrong-entry-accepted')
            return None
        return self.feedback_snapshot()

    def feedback_privacy(self, projection):
        """FEED05 entry and actual public disclosure, with no external navigation."""
        self.feedback_snapshot(projection)
        self.activate_id('feedback-privacy-link')
        root = self.id_target('feedback-privacy-dialog')
        self.window_ready_to_close('feedback-privacy')
        node = self.id_target('feedback-privacy-text', root=root)
        text = node.get_name()
        require(type(text) is str and 0 < len(text) <= 2048,
                'ui:feedback-privacy-text')
        for fragment in (
            'Feedback, reply email addresses, attachments, and diagnostic logs are emailed to support.',
            'Retention depends on our support mailbox and service providers, including their backup policies.',
            'We do not currently guarantee deletion within a fixed period.',
            'Diagnostic logs do not collect account names, email addresses, file contents, raw system journals, or exception messages.',
            'Automatic diagnostics contain validated technical events, health checks, and system information:',
            'Your own feedback, reply email, and selected files are separate and may contain personal information.',
            'Review them before sending.',
        ):
            require(fragment in text, 'ui:feedback-privacy-disclosure')

    def parent_report_operation(self, operation):
        """FEED15 Parent: read an automatic report; never open or send it."""
        require(operation in PARENT_REPORT_OPERATIONS, 'ui:parent-report-binding')
        if operation == 'parent-report-refused':
            require(self.absent_id('feedback-dialog', within='parent-window',
                                   incomplete_raises=True), 'ui:parent-report-present')
            try:
                self.window_ready_to_close('feedback')
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:parent-report-refusal')
                return {'refusal': 'absent'}
            raise UiError('ui:parent-report-wrong-entry-accepted')
        projection = ('parent-rule-error' if operation == 'parent-report-read'
                      else 'synthetic-first')
        def ready():
            try:
                value = self.feedback_snapshot(projection)
            except UiError as error:
                if str(error) in ('ui:feedback-collection', 'ui:feedback-target'):
                    return None
                raise
            root = self.id_target('feedback-dialog')
            for identity in ('feedback-close', 'feedback-send', 'feedback-add-files',
                             'feedback-download-logs', 'feedback-toggle-logs',
                             'feedback-privacy-link'):
                node = self.id_target(identity, root=root, sensitive=True, showing=False)
                require(self.has_state(node, self.api.StateType.VISIBLE)
                        and not self.has_state(node, self.api.StateType.DEFUNCT),
                        'ui:parent-report-control')
                action = node.get_action_iface()
                require(action is not None and sum(
                    not public_action_name(self.api, action, index).startswith('focus.')
                    for index in range(self.api.Action.get_n_actions(action))) == 1,
                    'ui:parent-report-action')
            self.window_ready_to_close('feedback')
            return value
        return self.wait(ready, 'parent-report')

    def feedback_privacy_operation(self, operation, *, projection='synthetic-first'):
        require(operation in FEEDBACK_PRIVACY_OPERATIONS, 'ui:feedback-operation')
        if operation == 'feedback-privacy-open':
            self.feedback_privacy(projection)
        elif operation == 'feedback-privacy-returned':
            self.window_closed('feedback-privacy', 'feedback')
            return self.feedback_snapshot(projection)
        elif operation == 'feedback-draft-closed':
            self.window_closed('feedback', 'parent')
        elif operation == 'feedback-close-refused':
            require(self.absent_id('feedback-dialog', within='parent-window'),
                    'ui:feedback-wrong-entry')
            try:
                self.window_ready_to_close('feedback')
            except UiError as error:
                require(str(error) == 'ui:feedback-entry', 'ui:feedback-refusal')
            else:
                raise UiError('ui:feedback-wrong-entry-accepted')
        elif operation == 'feedback-draft-reopen':
            return self.open_feedback(projection)
        else:
            value = self.feedback_snapshot(projection)
            self.window_ready_to_close('feedback')
            return value
        return None

    def check_parent_help(self):
        """INFO01: open the owned menu and read Help without invoking it."""
        self.parent()
        self.activate_id('parent-menu-button', action_name='menu.popup')
        return self.clickable_link('parent-menu-help', root=self.parent())

    def check_parent_information(self):
        """Compose all offered About link readers, without activation or URI reads."""
        root = self.about()
        for identity in ('about-website-value', 'about-privacy-value',
                         'about-support-value', 'about-license-value',
                         'about-legal-notices-value'):
            self.clickable_link(identity, root=root)

    def open_about(self, version, *, menu_open=False):
        """ABOUT01: independent Parent entry; menu, About, text and license link."""
        if menu_open:
            self.clickable_link('parent-menu-help', root=self.parent())
        else:
            self.activate_id('parent-menu-button', action_name='menu.popup')
        self.activate_id('parent-menu-about')
        root = self.about()
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        self.reveal_id('about-license-value', root=root)

    def read_about_interval(self, version):
        """Read an already open ID-owned About window without opening/repairing it."""
        root = self.snapshot_owned_target('about-dialog', check_prompt=True)
        require(root is not None, 'ui:about-interval-entry')
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        pid, bus, path = root.get_process_id(), root.bus, root.path
        require(type(pid) is int and pid > 0 and type(bus) is str and bus.startswith(':')
                and type(path) is str and path.startswith('/'), 'ui:about-interval-endpoint')
        return {'pid': pid, 'endpoint': [bus, path], 'product': PRODUCT, 'version': version}

    def kiosk_about_entry(self):
        """ABOUT01 kiosk entry: a caller-owned station, never Parent/overlay."""
        observation = self.read_snapshot()
        nodes, edges, identities, _facts = observation
        application = self.snapshot_matches(KIOSK_APPLICATION, nodes, identities=identities)
        require(application is not None, 'ui:kiosk-about-entry')
        window = self.snapshot_owned_target('kiosk-request-window',
            observation=observation, check_prompt=True)
        require(window is not None and window in self.snapshot_scope(nodes, edges, application)
                and self.has_state(window, self.api.StateType.ACTIVE), 'ui:kiosk-about-entry')
        require(self.snapshot_owned_target('kiosk-request-form', root=window,
                observation=observation) is not None, 'ui:kiosk-about-entry')
        require(self.snapshot_owned_target('about-dialog', observation=observation) is None,
                'ui:kiosk-about-already-open')
        return window

    def open_kiosk_about(self):
        """Open the real station menu/About controls once from valid entry."""
        self.kiosk_about_entry()
        self.activate_id('kiosk-menu-button', action_name='menu.popup')
        self.activate_id('kiosk-menu-item-about')
        self.window_ready_to_close('about')

    def kiosk_about_snapshot(self):
        """Fresh active About surface owned by the station, including close input."""
        observation = self.read_snapshot()
        nodes, edges, identities, facts = observation
        application = self.snapshot_matches(KIOSK_APPLICATION, nodes, identities=identities)
        require(application is not None, 'ui:kiosk-about-entry')
        root = self.snapshot_owned_target('about-dialog', observation=observation, check_prompt=True)
        require(root is not None and root in self.snapshot_scope(nodes, edges, application)
                and self.has_state(root, self.api.StateType.ACTIVE), 'ui:kiosk-about-entry')
        require(not any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes),
                'ui:kiosk-about-stale')
        return root, observation

    def read_kiosk_about(self, version):
        """Read public information and prove external actions are not offered.

        A complete owned snapshot is mandatory; traversal failures never become
        evidence of absence. Toolkit window buttons are confined to their ID owner.
        """
        root, observation = self.kiosk_about_snapshot()
        nodes, edges, identities, facts = observation
        controls = self.snapshot_owned_target('about-window-controls', root=root,
                                              observation=observation)
        require(controls is not None, 'ui:kiosk-about-window-controls')
        toolkit = set(self.snapshot_scope(nodes, edges, controls))
        for node in self.snapshot_scope(nodes, edges, root):
            if self.has_state(node, self.api.StateType.VISIBLE) and node not in toolkit:
                require(facts[node]['role'] not in (
                    'link', 'push button', 'button', 'toggle button', 'menu item',
                    'entry', 'check box', 'radio button', 'combo box'),
                    'ui:kiosk-about-external-action')
        require(not any(identities[node] == 'kiosk-menu-item-help' and facts[node]['showing']
                        for node in nodes), 'ui:kiosk-about-external-action')
        self.read_label(root, 'about-product', maximum=80)
        self.read_label(root, 'about-version', maximum=80, expected=version)
        for field, expected in (
                ('website', None), ('privacy', 'Privacy policy'), ('support', None),
                ('license', 'GNU General Public License v3.0'),
                ('legal-notices', 'Malcontent integration and bundled-font notices')):
            node = self.reveal_id('about-' + field + '-value', root=self.about())
            text = node.get_name()
            require(node.get_role_name() == 'label' and type(text) is str
                    and 0 < len(text) <= 256 and (expected is None or text == expected),
                    'ui:kiosk-about-information')
        self.about_footer()
        return True

    def reveal_id(self, identity, *, root):
        node = self.id_target(identity, root=root, showing=False)
        if not self.showing(node):
            surface = owned_surface_id(identity)
            require(surface is not None, 'ui:missing-reveal-surface')
            self.activate_id(surface, action_name='focus.' + identity)
        return self.id_target(identity)

    def read_document(self, root, projection, *, maximum, require_active=True):
        """UI03: only the bounded GPL heading projection; never return raw text."""
        require(type(require_active) is bool and projection == 'gpl-heading' and type(maximum) is int
                and 64 <= maximum <= 1024, 'ui:document-binding')
        if self.provider_contracts['document-viewer']['application_id']:
            _application_id, _surface_id, registered = self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
            require(public_automation_id(root) == registered['content']
                    and self.find_provider_control(
                        'document-viewer', 'license-document', 'content') is root,
                    'ui:document-owner')
        else:
            window, content, _observation = self.license_viewer_snapshot()
            require(root is content and window is not None
                    and (not require_active or self.has_state(window, self.api.StateType.ACTIVE)),
                    'ui:document-owner')
        require(root.get_role_name() in ('text', 'document text') and self.showing(root),
                'ui:document-surface')
        text = root.get_text_iface()
        if text is None:
            return False
        count = self.api.Text.get_character_count(text)
        require(type(count) is int and count >= 0, 'ui:document-bound')
        value = self.api.Text.get_text(text, 0, min(count, maximum))
        require(type(value) is str and len(value) <= maximum, 'ui:document-bound')
        return self.license_headings_match(value)

    @staticmethod
    def license_headings_match(value):
        return ('GNU GENERAL PUBLIC LICENSE' in value
                and 'Version 3, 29 June 2007' in value)

    def license_provider_metadata(self):
        """Record the actual viewer locale, installed package and input sources."""
        from gi.repository import Gio
        window, content, _observation = self.license_viewer_snapshot()
        require(window is not None and content is not None,
                'ui:license-provider-owner')
        pid = window.get_process_id()
        require(type(pid) is int and pid > 0, 'ui:license-provider-owner')
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                           if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}',
             'gnome-text-editor'], text=True, timeout=5).strip()
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        return validate_shell_metadata({'version': version, 'locale': locale,
                                        'keyboard': [list(source) for source in sources]})

    def license_viewer_snapshot(self):
        """GNOME Text Editor 50 provider exception for ABOUT02/03 only.

        The application/window have no usable public IDs. Resolve the registry
        application and its sole showing window by scoped public semantics, then
        use the provider's Builder ID ``view`` for the document. Never identify
        a document by its title, contents, position or geometry. Other handlers,
        multiple windows/documents and prompts cannot authorize reading/closing.
        """
        desktop = self.api.get_desktop(0)
        require(desktop is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(desktop, strict=True, snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        owners = [node for node in snapshot[desktop]
                  if facts[node]['role'] == 'application'
                  and (facts[node]['identity'] == 'org.gnome.TextEditor'
                       or (not facts[node]['identity'] and facts[node]['name'].casefold()
                           in ('gnome-text-editor', 'org.gnome.texteditor', 'text editor')))]
        require(len(owners) <= 1, 'ui:license-provider-ambiguous')
        observation = (nodes, snapshot, facts)
        if not owners:
            return None, None, observation
        owner = owners[0]
        owned = self.snapshot_scope(nodes, snapshot, owner)
        windows = [node for node in owned if facts[node]['role'] in ('frame', 'window')
                   and facts[node]['showing']]
        require(len(windows) <= 1, 'ui:license-window-ambiguous')
        if not windows:
            return None, None, observation
        window = windows[0]
        scoped = self.snapshot_scope(nodes, snapshot, window)
        documents = [node for node in scoped if facts[node]['identity'] == 'view']
        require(len(documents) <= 1, 'ui:license-document-ambiguous')
        content = documents[0] if documents else None
        require(owner.get_process_id() > 0
                and window.get_process_id() == owner.get_process_id()
                and (content is None or content.get_process_id() == owner.get_process_id()),
                'ui:document-owner')
        if content is not None and (facts[content]['role'] not in ('text', 'document text')
                                    or not facts[content]['showing']):
            content = None
        return window, content, observation

    def existing_window(self, binding):
        """DESK10: resolve an existing surface; never launch or infer a title."""
        require(binding in ('parent', 'feedback', 'viewer'), 'ui:switch-binding')
        if binding == 'viewer':
            root, content, _ = self.license_viewer_snapshot()
            require(root is not None and content is not None, 'ui:switch-absent')
            require(self.read_document(content, 'gpl-heading', maximum=1024, require_active=False),
                    'ui:switch-document')
        else:
            root = self.snapshot_owned_target(
                'parent-window' if binding == 'parent' else 'feedback-dialog',
                check_prompt=True)
            require(root is not None, 'ui:switch-absent')
        require(self.showing(root) and self.has_state(root, self.api.StateType.SENSITIVE),
                'ui:switch-unusable')
        return root

    def existing_window_active(self, binding, *, expected=None):
        root = self.existing_window(binding)
        require(expected is None or root == expected, 'ui:switch-replaced')
        return root if self.has_state(root, self.api.StateType.ACTIVE) else None

    def window_switch_ready(self, binding, source):
        """Resolve both endpoints before the shared worker's single Alt+Tab.

        GTK toplevel Component.GrabFocus is unsupported. No action is tried
        before selecting this keyboard route, and a wrong destination stops
        the worker rather than trying another key or relaunching anything.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(binding != source and self.existing_window_active(source) is not None,
                'ui:switch-source')
        require(self.existing_window_active(binding) is None, 'ui:switch-already-active')
        return self.window_switch_proof(binding, active=False)

    def window_switch_proof(self, binding, *, active=True, projection='synthetic-first'):
        root = self.existing_window(binding)
        require(self.has_state(root, self.api.StateType.ACTIVE) is active, 'ui:switch-active')
        # Public AT-SPI endpoint identity distinguishes two windows of one PID.
        pid, bus, path = root.get_process_id(), root.bus, root.path
        require(type(pid) is int and pid > 0 and type(bus) is str
                and bus.startswith(':') and type(path) is str and path.startswith('/'),
                'ui:switch-endpoint')
        proof = {'binding': binding, 'pid': pid, 'endpoint': [bus, path], 'active': active}
        if binding == 'feedback' and active:
            proof['feedback'] = self.feedback_snapshot(projection)
            if projection == 'formatted-file':
                proof['feedback'] = {key: item for key, item in proof['feedback'].items()
                                     if key not in ('status', 'include_logs')}
            elif projection == 'attachment-file':
                proof['feedback'].pop('status')
        return proof

    def window_switch_operation(self, operation, *, projection='synthetic-first'):
        require(operation in WINDOW_SWITCH_OPERATIONS, 'ui:switch-operation')
        if operation.endswith('-ready'):
            return self.window_switch_ready(*WINDOW_SWITCH_TARGETS[operation[:-6]])
        if operation == 'switch-viewer-launch':
            require(not self.input_uncertain, 'ui:uncertain-input')
            def entry():
                require(self.existing_window_active('parent') is not None, 'ui:switch-entry')
                viewer, _, _ = self.license_viewer_snapshot()
                require(viewer is None, 'ui:switch-viewer-exists')
                return True
            # A transitioning public tree cannot establish entry or absence.
            # Retry only complete observations, never the launch command.
            self.wait(entry, 'switch-viewer-entry', prompt_in_predicate=True)
            self.input_uncertain = True
            self.invalidate_observation()
            subprocess.run([
                '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
                '--service-type=exec', '/usr/bin/gnome-text-editor', '--new-window',
                '/usr/share/oh-no-parent-control/LICENSE',
            ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
            self.license_content()
            proof = self.wait(lambda: self.window_switch_proof('viewer'),
                              'switch-viewer-proof', prompt_in_predicate=True)
            self.input_uncertain = False
            return proof
        if operation == 'switch-viewer-absent':
            viewer, _, _ = self.license_viewer_snapshot()
            require(viewer is None, 'ui:switch-viewer-exists')
            try:
                self.window_switch_ready('viewer', 'feedback')
            except UiError as error:
                require(str(error) == 'ui:switch-absent', 'ui:switch-refusal')
            else:
                raise UiError('ui:switch-refusal-missing')
            return self.window_switch_proof('feedback')
        binding = ('parent' if operation in ('switch-parent-before', 'switch-parent') else
                   'viewer' if operation in ('switch-viewer', 'switch-viewer-again',
                                              'switch-viewer-close') else 'feedback')
        if operation not in ('switch-parent-before', 'switch-draft-before'):
            self.wait(lambda: self.existing_window_active(binding), 'switch-active',
                      prompt_in_predicate=True)
        return self.window_switch_proof(binding, projection=projection)

    def license_content(self):
        """Read the ID-scoped registered viewer, without title discovery."""
        def document():
            if not self.provider_contracts['document-viewer']['application_id']:
                window, node, _observation = self.license_viewer_snapshot()
                return (node is not None and self.has_state(window, self.api.StateType.ACTIVE)
                        and self.read_document(node, 'gpl-heading', maximum=1024))
            surface, registered = self.provider_surface(
                'document-viewer', 'license-document', ('content', 'close'))
            if surface is None:
                return False
            node = self.find_id(registered['content'], root=surface)
            return (node is not None and node.get_role_name() in ('text', 'document text')
                    and self.showing(node)
                    and self.read_document(node, 'gpl-heading', maximum=1024))
        return self.wait(document, 'license-content')

    def open_license(self):
        """ABOUT02: compatibility name for checking the license link only."""
        return self.clickable_link('about-license-value', root=self.about())

    def window_ready_to_close(self, window):
        """UI01/02: fresh active named window before a worker's Alt-F4."""
        require(window in ('license', 'about', 'feedback', 'feedback-privacy'), 'ui:window-binding')
        if window in ('feedback', 'feedback-privacy'):
            root = self.snapshot_owned_target(window + '-dialog', check_prompt=True)
            require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                    'ui:feedback-entry')
            return
        def active():
            if window == 'license':
                if not self.provider_contracts['document-viewer']['application_id']:
                    root, content, _observation = self.license_viewer_snapshot()
                    if content is None:
                        return False
                    # Reacquire and verify the document again at the close input
                    # boundary; successful launch alone never authorizes input.
                    if not self.read_document(content, 'gpl-heading', maximum=1024):
                        return False
                else:
                    root, _registered = self.provider_surface(
                        'document-viewer', 'license-document', ('content', 'close'))
            else:
                root = self.find_id('about-dialog')
            return root is not None and self.has_state(root, self.api.StateType.ACTIVE)
        self.wait(active, 'active-' + window)

    def window_closed(self, window, destination):
        """UI11: complete fresh absence within the positively recognized return UI."""
        require((window, destination) in (('license', 'about'), ('about', 'parent'),
                                         ('about', 'kiosk'), ('feedback', 'parent'),
                                         ('feedback-privacy', 'feedback')),
                'ui:window-binding')
        if window in ('feedback', 'feedback-privacy'):
            underlying = 'parent-window' if destination == 'parent' else 'feedback-dialog'
            def returned():
                if not self.absent_id(window + '-dialog', within=underlying):
                    return False
                root = self.snapshot_owned_target(underlying, check_prompt=True)
                return root is not None and self.has_state(root, self.api.StateType.ACTIVE)
            self.wait(returned, window + '-close')
            return
        semantic_license = (window == 'license'
                            and not self.provider_contracts['document-viewer']['application_id'])
        if window == 'license' and not semantic_license:
            _application_id, surface_id, registered = self.require_provider_contract(
                'document-viewer', 'license-document', ('content', 'close'))
        def closed():
            if window == 'about':
                return self.absent_id('about-dialog', within=(
                    'kiosk-request-window' if destination == 'kiosk' else 'parent-window'))
            if semantic_license:
                viewer, _content, (nodes, snapshot, facts) = self.license_viewer_snapshot()
                identities = {node: facts[node]['identity'] for node in nodes}
                underlying = self.snapshot_owned_target(
                    'about-dialog', observation=(nodes, snapshot, identities, facts))
                return (viewer is None and underlying is not None
                        and self.has_state(underlying, self.api.StateType.ACTIVE))
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            if not nodes:
                return False
            for node in nodes:
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-window')
            underlying = self.snapshot_owned_target(
                'about-dialog', observation=(nodes, snapshot, identities, None))
            if underlying is None:
                return False
            external_ids = (surface_id, registered['content'], registered['close'])
            return not any(identities[node] in external_ids and self.showing(node)
                           for node in nodes)
        self.wait(closed, window + '-close')

    def about_footer(self):
        """ABOUT04's public reveal/read, in an independently opened About window."""
        self.reveal_id('about-copyright', root=self.about())
        self.read_label(self.about(), 'about-footer', maximum=80)

    def settings(self, child=CHILD):
        """PARENT03: explicit child, public settings; no scenario expectations."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        selected = self.child_id_control(
            child, 'parent-child-selected-', root=picker, showing=True,
        )
        require(selected is not None, 'ui:selected-child')
        self.read_label(selected, 'child', expected=child, maximum=80)
        toggle = self.id_target('parent-screen-limit-toggle', root=root, sensitive=True)
        allowance = self.id_target('parent-daily-limit-selector', root=root)
        labels = self.read_label(allowance, 'allowance', maximum=80)
        if labels == ['Custom value']:
            # The selector names the mode; the identified editor exposes the
            # numeric value. Keep settings snapshots value-bearing so changing
            # one custom amount to another cannot compare equal.
            editor = self.id_target('parent-custom-daily-limit', root=root)
            require(editor.get_role_name() != 'password text', 'ui:masked-text')
            text = editor.get_text_iface()
            count = self.api.Text.get_character_count(text) if text is not None else -1
            require(1 <= count <= 4, 'ui:allowance-value')
            value = self.api.Text.get_text(text, 0, count)
            import re
            require(type(value) is str and re.fullmatch(r'[0-9]{1,4}', value)
                    and int(value) <= 1439, 'ui:allowance-value')
            labels = [value + ' minutes']
        if child in (EXISTING_CHILD, NEW_CHILD):
            self.reveal_id('parent-time-status', root=root)
        return {'child': CHILD_IDENTITIES[child],
                'limit_enabled': toggle.get_state_set().contains(self.api.StateType.CHECKED),
                'allowance': labels}

    def set_toggle(self, identity, desired, *, root):
        """UI17: set a registered owned switch to an explicit state."""
        require(identity in ('parent-screen-limit-toggle', 'kiosk-soft-apps-toggle',
                *(f'parent-filter-{kind}-{option}' for kind, options in FILTER_OPTIONS.items()
                  for option in options))
                and type(desired) is bool,
                'ui:toggle-binding')
        # A complete lookup may legitimately omit a hidden GTK stack page.
        # Retry incomplete reads, but never wait for a missing input target to
        # appear or substitute another control.
        target, = self.wait(lambda: (self.snapshot_owned_target(
            identity, root=root, showing=False, check_prompt=True),),
            'toggle-target', prompt_in_predicate=True)
        require(target is not None, 'ui:unusable-target')
        states = target.get_state_set()
        require(states.contains(self.api.StateType.VISIBLE)
                and not states.contains(self.api.StateType.DEFUNCT),
                'ui:unusable-target')
        initial = self.has_state(target, self.api.StateType.CHECKED)
        activated = initial != desired
        if activated:
            self._invoke_target(target)

        def desired_state():
            current = self.snapshot_owned_target(
                identity, root=root, showing=False, check_prompt=True)
            if current is None:
                return None
            return current if self.has_state(current, self.api.StateType.CHECKED) == desired else None

        current = self.wait(desired_state, 'toggle-state', prompt_in_predicate=True)
        require(self.has_state(current, self.api.StateType.CHECKED) == desired,
                'ui:toggle-state')
        return {'state': desired, 'activated': activated}

    def parent_toggle_operation(self, operation):
        """Installed Parent binding and bounded refusal checks for UI17."""
        require(operation in TOGGLE_OPERATIONS, 'ui:toggle-operation')
        root = self.parent()
        if getattr(self, 'expected_trace_source', None) is not None:
            require(operation == 'parent-toggle-enabled', 'ui:trace-input-binding')
            self.parent_save_snapshot(CHILD, False)
            source = (self.parent_save_trace_source()[0]
                      if self.expected_trace_source.startswith('save:')
                      else self.parent_trace_source()[0])
            require(source == self.expected_trace_source.removeprefix('save:'),
                    'ui:trace-source-changed')
        if operation == 'multiple-other-enable':
            self.parent_save_snapshot(EXISTING_CHILD, False)
            return self.set_toggle('parent-screen-limit-toggle', True, root=root)
        if operation == 'parent-toggle-wrong-refused':
            try:
                self.set_toggle('parent-legend-toggle', True, root=root)
            except UiError as error:
                require(str(error) == 'ui:toggle-binding', 'ui:toggle-wrong-refusal')
                return {'refusal': 'wrong-control'}
            raise UiError('ui:toggle-wrong-accepted')
        if operation == 'parent-toggle-hidden-refused':
            self.activate_id('parent-page-app-limits')

            def hidden():
                snapshot, identities, facts = {}, {}, {}
                nodes = list(self.nodes(strict=True, snapshot=snapshot,
                                        identities=identities, facts=facts))
                observation = (nodes, snapshot, identities, facts)
                current_root = self.snapshot_owned_target(
                    'parent-window', check_prompt=True, observation=observation)
                if current_root is None:
                    return False
                target = self.snapshot_owned_target(
                    'parent-screen-limit-toggle', root=current_root, showing=False,
                    observation=observation)
                return target is None or not self.has_state(target, self.api.StateType.VISIBLE)

            self.wait(hidden, 'toggle-hidden', prompt_in_predicate=True)
            try:
                self.set_toggle('parent-screen-limit-toggle', True, root=root)
            except UiError as error:
                require(str(error) == 'ui:unusable-target', 'ui:toggle-hidden-refusal')
            else:
                raise UiError('ui:toggle-hidden-accepted')
            self.activate_id('parent-page-screen-limits')
            target = self.id_target('parent-screen-limit-toggle')
            require(not self.has_state(target, self.api.StateType.CHECKED),
                    'ui:toggle-hidden-state-changed')
            return {'refusal': 'hidden-control', 'state': False}
        desired = operation == 'parent-toggle-enabled'
        return self.set_toggle('parent-screen-limit-toggle', desired, root=root)

    def parent_trace_source(self, child=CHILD, surface='parent-window'):
        """Resolve the bounded public projection and pin its window/object owner."""
        import hashlib
        require(surface == 'parent-window', 'ui:trace-surface')
        # PARENT03 checks the exact selected child through its owned public ID.
        self.settings(child)
        root = self.parent()
        target = self.id_target('parent-screen-limit-toggle', root=root, sensitive=True)
        require(not self.has_state(target, self.api.StateType.DEFUNCT), 'ui:trace-stale')
        references = [(node.bus, node.path) for node in (root, target)]
        require(references[0][0] == references[1][0] and
                references[0][0].startswith(':'), 'ui:trace-owner')
        digest = hashlib.sha256(json.dumps(references).encode()).hexdigest()
        return digest, target

    def parent_save_trace_source(self, custom=False, child=CHILD):
        """Pin the window and all four public transition endpoints."""
        import hashlib
        self.settings(child)
        root = self.parent()
        controls = {
            name: self.id_target(identity, root=root)
            for name, identity in (
                ('toggle', 'parent-screen-limit-toggle'),
                ('child', 'parent-child-selector'),
                ('allowance', 'parent-daily-limit-selector'))
        }
        if custom:
            controls['editor'] = self.id_target('parent-custom-daily-limit', root=root)
        references = [(node.bus, node.path) for node in (root, *controls.values())]
        require(len(set(references)) == len(controls) + 1 and len({bus for bus, _ in references}) == 1
                and references[0][0].startswith(':'), 'ui:trace-owner')
        return hashlib.sha256(json.dumps([CHILD_IDENTITIES[child], references]).encode()).hexdigest(), controls

    def parent_checked_events(self, operation):
        """Input-free UI25/26 leaf; the controller owns the separate UI17 call."""
        if operation != 'parent-checked-events':
            child, surface, category = (
                (EXISTING_CHILD, 'parent-window', 'ui:selected-child')
                if operation == 'parent-trace-wrong-child-refused' else
                (CHILD, 'feedback-dialog', 'ui:trace-surface'))
            try:
                self.parent_trace_source(child, surface)
            except UiError as error:
                require(str(error) == category, 'ui:trace-refusal')
                return {'refusal': 'wrong-child' if child == EXISTING_CHILD else 'wrong-surface'}
            raise UiError('ui:trace-wrong-entry-accepted')
        token = self.trace_request
        require(type(token) is str and re.fullmatch(r'[0-9a-f]{32}', token), 'ui:trace-token')
        self.parent_save_snapshot(CHILD, False)
        source, target = self.parent_trace_source()
        started = time.monotonic()
        samples, failures = [], []
        armed = False

        def receive(checked, error):
            if error is not None:
                failures.append(True)
                return
            if not armed or len(samples) >= 32:
                failures.append(True)
                return
            samples.append({'elapsed_ms': int((time.monotonic() - started) * 1000),
                            'checked': checked, 'source': 'event'})

        with self.api.checked_events(target, receive) as context:
            self.invalidate_observation()
            require(self.parent_trace_source()[0] == source and
                    not self.has_state(target, self.api.StateType.CHECKED), 'ui:trace-entry')
            # Drain anything queued during registration before arming. An
            # unexpected earlier event invalidates entry, never becomes proof.
            for _ in range(64):
                if not context.pending():
                    break
                context.iteration(False)
            require(not context.pending(), 'ui:trace-event-limit')
            require(not failures, 'ui:trace-entry')
            armed = True
            print(json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                              'source': source, 'boot_sha256': self.trace_boot,
                              'checked': False}, sort_keys=True), flush=True)
            while not samples and not failures and time.monotonic() - started < 60:
                context.iteration(False)
                time.sleep(0.01)
            require(not failures and samples and samples[-1]['checked'] is True,
                    'ui:trace-event-missing')
            require(time.monotonic() - started < 60, 'ui:trace-deadline')
            # Read continuity afresh after the event. This saved-state read is
            # not substituted for the event nor for the caller's later PARENT08.
            self.invalidate_observation()
            self.parent_save_snapshot(CHILD, True)
            require(self.parent_trace_source()[0] == source, 'ui:trace-source-changed')
        return {'token': token, 'source': source, 'terminal': True, 'samples': samples}

    def parent_save_events(self, custom=False, child=CHILD):
        """Observe the public inhibited interval and recovery during one UI17 input."""
        token = self.trace_request
        require(type(token) is str and re.fullmatch(r'[0-9a-f]{32}', token), 'ui:trace-token')
        self.parent_save_snapshot(child, custom)
        source, controls = self.parent_save_trace_source(custom, child)
        state = {'checked': custom, 'child': True, 'toggle': True, 'allowance': custom}
        if custom:
            self.text_recipient('parent-custom-daily-limit', focused=True, child=child)
            state['editor'] = True
        events, failures = [], []
        started = time.monotonic()
        armed = False
        endpoints = {(node.bus, node.path, 'sensitive'): name
                     for name, node in controls.items()}
        endpoints[(controls['toggle'].bus, controls['toggle'].path, 'checked')] = 'toggle'

        def receive(target, field, value, error):
            if error is not None or not armed or len(events) >= 32:
                failures.append(True)
                return
            events.append({'elapsed_ms': int((time.monotonic() - started) * 1000),
                           'target': target, 'state': field, 'value': value})

        with self.api.state_events(endpoints, receive) as context:
            self.invalidate_observation()
            require(self.parent_save_trace_source(custom, child)[0] == source, 'ui:trace-source-changed')
            require(self.has_state(controls['toggle'], self.api.StateType.CHECKED) == custom and
                    self.has_state(controls['child'], self.api.StateType.SENSITIVE) and
                    self.has_state(controls['toggle'], self.api.StateType.SENSITIVE) and
                    self.has_state(controls['allowance'], self.api.StateType.SENSITIVE) == custom and
                    (not custom or self.has_state(controls['editor'], self.api.StateType.SENSITIVE)),
                    'ui:trace-entry')
            for _ in range(64):
                if not context.pending():
                    break
                context.iteration(False)
            require(not context.pending() and not failures, 'ui:trace-entry')
            armed = True
            print(json.dumps({'event': 'accessibility-trace-ready', 'token': token,
                              'source': source, 'boot_sha256': self.trace_boot,
                              'checked': custom}, sort_keys=True), flush=True)
            inhibited = recovered = False
            saw_child_off = saw_toggle_off = False
            examined = 0
            while not recovered and not failures and time.monotonic() - started < 60:
                context.iteration(False)
                while examined < len(events):
                    event = events[examined]
                    examined += 1
                    key = 'checked' if event['state'] == 'checked' else event['target']
                    state[key] = event['value']
                    if key == 'child' and not event['value']:
                        saw_child_off = True
                    if key == 'toggle' and event['state'] == 'sensitive' and not event['value']:
                        saw_toggle_off = True
                    if custom:
                        require(state['checked'] and state['allowance'] and state['editor'],
                                'ui:custom-trace-controls')
                    if saw_child_off and saw_toggle_off and not any(
                            state[name] for name in (('child', 'toggle') if custom else
                                                    ('child', 'toggle', 'allowance'))):
                        inhibited = True
                    if inhibited and all(state.values()):
                        recovered = True
                if custom:
                    recovered = inhibited and all(state.values())
                if custom and recovered:
                    # A first save may drain before the second edit arrives.
                    # Only the declared final public draft can end observation.
                    self.invalidate_observation()
                    try:
                        self.read_custom_trace_draft(child)
                    except UiError as error:
                        require(str(error) == 'ui:text-value', 'ui:custom-trace-result')
                        recovered = False
                time.sleep(0.01)
            require(not failures and inhibited and recovered and len(events) <= 32,
                    'ui:save-trace-missing')
            require(time.monotonic() - started < 60, 'ui:trace-deadline')
            self.invalidate_observation()
            self.parent_save_snapshot(child, True)
            require(self.parent_save_trace_source(custom, child)[0] == source, 'ui:trace-source-changed')
        return {'token': token, 'source': source, 'terminal': True, 'samples': events}

    def read_custom_trace_draft(self, child=CHILD):
        """Read the pinned custom editor while a queued save inhibits navigation."""
        root = self.parent()
        require(self.has_state(root, self.api.StateType.ACTIVE), 'ui:trace-surface')
        picker = self.id_target('parent-child-selector', root=root)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:wrong-child')
        allowance = self.id_target('parent-daily-limit-selector', root=root)
        editor = self.id_target('parent-custom-daily-limit', root=root, showing=False)
        require(all(self.has_state(node, self.api.StateType.VISIBLE) and
                    self.has_state(node, self.api.StateType.SENSITIVE) and
                    not self.has_state(node, self.api.StateType.DEFUNCT)
                    for node in (allowance, editor)), 'ui:custom-trace-controls')
        require(editor.get_role_name() != 'password text' and
                self.has_state(editor, self.api.StateType.EDITABLE), 'ui:text-editor')
        value = editor.get_text_iface()
        require(value is not None, 'ui:text-editor')
        count = self.api.Text.get_character_count(value)
        require(count == 1 and self.api.Text.get_text(value, 0, count) == '6',
                'ui:text-value')

    def custom_trace_focus(self, child=CHILD):
        self.parent_save_snapshot(child, True)
        source, _controls = self.parent_save_trace_source(True, child)
        require(source == self.trace_request, 'ui:trace-source-changed')
        self.text_recipient('parent-custom-daily-limit', focused=True, child=child)
        return {'focused': True}

    def parent_save_snapshot(self, child, expected_enabled):
        """PARENT08: wait for one terminal saved/control-state snapshot."""
        require(child in CHILD_IDENTITIES and type(expected_enabled) is bool,
                'ui:parent-save-binding')
        uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
        expected_selected = 'parent-child-selected-' + str(uid)

        def saved():
            snapshot, identities, facts = {}, {}, {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities, facts=facts))
            observation = (nodes, snapshot, identities, facts)
            root = self.snapshot_owned_target(
                'parent-window', check_prompt=True, observation=observation)
            if root is None:
                return False
            require(not any(
                identities[node] in ('feedback-dialog',
                                     'error-report-unavailable-dialog')
                and self.showing(node)
                for node in nodes
            ), 'ui:parent-save-error-report')
            root_nodes = self.snapshot_scope(nodes, snapshot, root)
            picker = self.snapshot_matches(
                'parent-child-selector', root_nodes, showing=True, show=self.showing)
            toggle = self.snapshot_matches(
                'parent-screen-limit-toggle', root_nodes, showing=True, show=self.showing)
            allowance = self.snapshot_matches(
                'parent-daily-limit-selector', root_nodes, showing=True, show=self.showing)
            if picker is None or toggle is None or allowance is None:
                return False
            picker_nodes = self.snapshot_scope(nodes, snapshot, picker)
            selected = [node for node in picker_nodes
                        if re.fullmatch(r'parent-child-selected-[0-9]+', identities[node])
                        and self.showing(node)]
            require(len(selected) == 1, 'ui:selected-child')
            require(identities[selected[0]] == expected_selected, 'ui:wrong-child')
            # The UID belongs to the selected-content box. Verify its label
            # inside this same complete snapshot, as UI03 does for selection.
            selected_nodes = self.snapshot_scope(nodes, snapshot, selected[0])
            labels = [node.get_name() for node in selected_nodes
                      if node.get_role_name() == 'label' and self.showing(node)]
            require(labels == [child], 'ui:wrong-child')
            value = {
                'child': CHILD_IDENTITIES[child], 'result': 'saved',
                'limit_enabled': self.has_state(toggle, self.api.StateType.CHECKED),
                'child_selector_enabled': self.has_state(
                    picker, self.api.StateType.SENSITIVE),
                'toggle_enabled': self.has_state(toggle, self.api.StateType.SENSITIVE),
                'allowance_enabled': self.has_state(
                    allowance, self.api.StateType.SENSITIVE),
            }
            expected = {
                'child': CHILD_IDENTITIES[child], 'result': 'saved',
                'limit_enabled': expected_enabled, 'child_selector_enabled': True,
                'toggle_enabled': True, 'allowance_enabled': expected_enabled,
            }
            return value if value == expected else False

        return self.wait(saved, 'parent-save', prompt_in_predicate=True)

    def revoke_disabled(self, child, enabled):
        """Read idle Revoke availability and zero balances without button input."""
        self.parent_save_snapshot(child, enabled)
        root = self.time_explanation_entry(child)
        button = self.id_target('parent-revoke-button', root=root)
        sensitive = self.has_state(button, self.api.StateType.SENSITIVE)
        balances = self.time_explanation(child)
        return {'child': CHILD_IDENTITIES[child], 'limit_enabled': enabled,
                'idle': True, 'sensitive': sensitive,
                **{key + '_seconds': balances[key]['seconds']
                   for key in ('daily', 'one_time', 'total')}}

    def time_explanation_entry(self, child):
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:wrong-child')
        return root

    def time_explanation(self, child):
        """PARENT20: one read-only showing explanation; never reveal or expand."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        edges, identities, facts = {}, {}, {}
        nodes = list(self.nodes(strict=True, snapshot=edges, identities=identities, facts=facts))
        observation = (nodes, edges, identities, facts)
        root = self.snapshot_owned_target('parent-window', observation=observation,
                                          check_prompt=True)
        require(root is not None, 'ui:time-entry')
        scoped = self.snapshot_scope(nodes, edges, root)
        picker = self.snapshot_matches('parent-child-selector', scoped,
                                       showing=True, show=self.showing)
        require(picker is not None, 'ui:time-entry')
        uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
        selected = [node for node in self.snapshot_scope(nodes, edges, picker)
                    if re.fullmatch(r'parent-child-selected-[0-9]+', identities[node])
                    and self.showing(node)]
        require(len(selected) == 1 and identities[selected[0]] ==
                'parent-child-selected-' + str(uid), 'ui:wrong-child')
        labels = [node.get_name() for node in self.snapshot_scope(nodes, edges, selected[0])
                  if node.get_role_name() == 'label' and self.showing(node)]
        require(labels == [child], 'ui:wrong-child')
        section = self.snapshot_matches('parent-time-status', scoped,
                                        showing=True, show=self.showing)
        require(section is not None, 'ui:time-entry')
        section_nodes = self.snapshot_scope(nodes, edges, section)
        explanation = self.snapshot_matches('parent-time-explanation', section_nodes,
                                             showing=True, show=self.showing)
        collapse = self.snapshot_matches('parent-time-calculation-collapse', section_nodes,
                                         showing=True, show=self.showing)
        require(explanation is not None and collapse is not None, 'ui:time-collapsed')
        require(explanation.get_role_name() == 'label', 'ui:time-label')
        text = explanation.get_name()
        require(type(text) is str and len(text) <= 256, 'ui:time-label')
        match = re.fullmatch(
            r'Daily allowance remaining: ([^\n]+)\nOne-time grant remaining: ([^\n]+)\n'
            r'Remaining time: ([^\n]+) — the larger of the two amounts\.', text)
        require(match is not None, 'ui:time-label')
        return {'child': CHILD_IDENTITIES[child], 'expanded': True,
                **{key: duration_projection(value) for key, value in
                   zip(('daily', 'one_time', 'total'), match.groups())},
                'observed_monotonic_ns': time.monotonic_ns()}

    def time_explanation_operation(self, operation, *, child=CHILD):
        require(operation in TIME_EXPLANATION_OPERATIONS, 'ui:time-operation')
        require(child in (CHILD, EXISTING_CHILD) and
                (child == CHILD or operation in NAMED_TIME_OPERATIONS), 'ui:time-child-binding')
        other_child = EXISTING_CHILD if child == CHILD else CHILD
        configurations = {
            'time-explanation-setup-zero-read': (False, 0, True),
            'time-explanation-setup-positive-read': (True, 15, True),
            'time-explanation-setup-thirty-read': (False, 30, True),
            'time-explanation-off-read': (True, 15, False),
            'time-explanation-positive-read': (False, 15, True),
            'time-explanation-zero-read': (True, 0, True),
        }
        if operation in configurations:
            initial, minutes, final = configurations[operation]
            return self.configure_time_controls(
                child, initial_enabled=initial, minutes=minutes, final_enabled=final)
        if operation in ('time-explanation-reach-read', 'time-explanation-reach-reread',
                         'time-explanation-zero-reread'):
            return self.reach_time_explanation(CHILD)
        if operation in ('time-explanation-reach-wrong-child',
                         'time-explanation-config-wrong-child',
                         'time-explanation-config-wrong-state'):
            wrong_state = operation.endswith('wrong-state')
            try:
                if operation == 'time-explanation-reach-wrong-child':
                    self.reach_time_explanation(EXISTING_CHILD)
                else:
                    self.configure_time_controls(
                        child if wrong_state else other_child,
                        initial_enabled=False, minutes=15, final_enabled=True)
            except UiError as error:
                require(str(error) == ('ui:time-initial-state' if wrong_state else
                                       'ui:wrong-child'), 'ui:time-refusal')
                return {'refusal': operation.removeprefix('time-explanation-')}
            raise UiError('ui:time-refusal-missing')
        if operation in ('time-explanation-read', 'time-explanation-reread'):
            return self.time_explanation(child)
        if operation.endswith(('wrong-child', 'collapsed')):
            child = EXISTING_CHILD if operation.endswith('wrong-child') else CHILD
            expected = 'ui:wrong-child' if child == EXISTING_CHILD else 'ui:time-collapsed'
            try:
                self.time_explanation(child)
            except UiError as error:
                require(str(error) == expected, 'ui:time-refusal')
                return {'refusal': operation.removeprefix('time-explanation-')}
            raise UiError('ui:time-refusal-missing')
        # Explicit preparation is separate from the observer. No input in PARENT20.
        self.time_explanation_entry(CHILD)
        if operation == 'time-explanation-collapse':
            self.activate_id('parent-time-calculation-collapse')
            self.wait(lambda: self.find_id('parent-time-explanation', showing=True) is None,
                      'time-collapsed')
            return {'expanded': False}
        require(self.find_id('parent-time-explanation', showing=True) is None,
                'ui:time-already-expanded')
        self.activate_id('parent-time-status', action_name='row.activate')
        self.id_target('parent-time-explanation')
        return {'expanded': True}

    def reach_time_explanation(self, child):
        """PARENT09: expand only a proven collapsed section, then use PARENT20."""
        self.time_explanation_entry(child)
        try:
            return self.time_explanation(child)
        except UiError as error:
            if str(error) != 'ui:time-collapsed':
                raise
        self.activate_id('parent-time-status', action_name='row.activate')
        self.id_target('parent-time-explanation')
        return self.time_explanation(child)

    def configure_time_controls(self, child, *, initial_enabled, minutes, final_enabled):
        """FLOW02: finite preset inputs, real saves and explicit final enablement.

        Enter Screen Limits for the selected child. Refuse mismatched declared
        state before edits; disabling is an intentional grant reset.
        """
        require(type(initial_enabled) is bool and type(final_enabled) is bool
                and type(minutes) is int
                and (minutes in (0, 15) or
                     minutes == 30 and not initial_enabled and final_enabled), 'ui:time-binding')
        self.time_explanation_entry(child)
        if minutes == 30:
            initial = self.settings(child)
            require(initial['limit_enabled'] == initial_enabled, 'ui:time-initial-state')
            require(initial['allowance'] == ['0 minutes'], 'ui:time-initial-allowance')
        self.activate_id('parent-page-screen-limits')
        if minutes != 30:
            initial = self.settings(child)
        require(initial['limit_enabled'] == initial_enabled, 'ui:time-initial-state')
        if not initial_enabled:
            self.set_toggle('parent-screen-limit-toggle', True, root=self.parent())
            self.parent_save_snapshot(child, True)
        self.allowance_preset(child, minutes, action='select')
        self.parent_save_snapshot(child, True)
        self.set_toggle('parent-screen-limit-toggle', final_enabled, root=self.parent())
        self.parent_save_snapshot(child, final_enabled)
        require(self.settings(child) == {
            'child': CHILD_IDENTITIES[child], 'limit_enabled': final_enabled,
            'allowance': [str(minutes) + ' minutes']}, 'ui:time-saved-settings')
        return self.reach_time_explanation(child)

    def allowance_entry(self, child):
        require(child in CHILD_IDENTITIES, 'ui:allowance-binding')
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:wrong-child')
        self.id_target('parent-daily-limit-selector', root=root, sensitive=True)

    def custom_allowance(self, child, minutes, *, action):
        """Read a saved editor after reload or reopen its retained custom choice.

        ``reopen`` follows a child/window reload, which canonicalizes 0/15 to
        presets. ``reopen-current`` keeps the existing custom selection, as
        autosave intentionally preserves the ongoing editor and its focus.
        """
        require(type(minutes) is int and minutes in (0, 1, 2, 3, 6, 7, 15, 1439)
                and action in ('open', 'saved', 'reopen', 'reopen-current'),
                'ui:allowance-binding')
        self.allowance_entry(child)
        if action == 'open':
            editor = self.snapshot_owned_target('parent-custom-daily-limit', showing=False)
            if editor is not None and self.has_state(editor, self.api.StateType.VISIBLE):
                # The previous reopen may already have returned this editor.
                # Reuse that visible editor without an unnecessary picker action.
                self.text_recipient('parent-custom-daily-limit', child=child)
                return {'minutes': minutes, 'action': action}
        if action in ('open', 'reopen', 'reopen-current'):
            self.parent_save_snapshot(child, True)
            if action == 'reopen' and minutes in (0, 15):
                self.allowance_preset(child, minutes, action='read')
            self.activate_id('parent-daily-limit-selector')
            choice = self.id_target('parent-daily-limit-custom', sensitive=True)
            if action == 'reopen-current' or action == 'reopen' and minutes not in (0, 15):
                require(choice.get_description() == 'Selected daily allowance: Custom amount',
                        'ui:allowance-selection')
            self.activate_id('parent-daily-limit-custom')
            self.wait(lambda: self.absent_id('parent-daily-limit-choices',
                                            within='parent-window'), 'allowance-picker-close')
            self.text_recipient('parent-custom-daily-limit', child=child)
        if action in ('saved', 'reopen', 'reopen-current'):
            if action == 'saved' and minutes == 1:
                # No navigation/input before this pause. Observe the save
                # independently of the editor's retained typing focus.
                started = time.monotonic()
                self.wait(lambda: time.monotonic() - started >= 0.5, 'custom-pause')
            if action == 'saved' and minutes == 3:
                require(not self.has_state(self.text_recipient('parent-custom-daily-limit', child=child),
                                           self.api.StateType.FOCUSED), 'ui:custom-focus-leave')
            self.parent_save_snapshot(child, True)
            self.read_synthetic_text('daily-' + str(minutes), child=child)
        return {'minutes': minutes, 'action': action}

    def custom_allowance_operation(self, operation, *, child=CHILD):
        require(operation in CUSTOM_ALLOWANCE_OPERATIONS, 'ui:allowance-operation')
        minutes, action = CUSTOM_ALLOWANCE_OPERATIONS[operation]
        if action in ('wrong-child', 'disabled'):
            child = EXISTING_CHILD if action == 'wrong-child' else CHILD
            expected = 'ui:wrong-child' if action == 'wrong-child' else 'ui:unusable-target'
            try:
                self.custom_allowance(child, minutes, action='open')
            except UiError as error:
                require(str(error) == expected, 'ui:allowance-refusal')
                return {'refusal': action}
            raise UiError('ui:allowance-refusal-missing')
        return self.custom_allowance(child, minutes, action=action)

    def invalid_allowance(self, binding):
        """PARENT08 validation: exact rejected draft and public error description."""
        require(binding in INVALID, 'ui:allowance-binding')
        self.allowance_entry(CHILD)
        self.parent_save_snapshot(CHILD, True)
        self.read_synthetic_text('daily-invalid-' + binding)
        self.wait(lambda: self.text_recipient('parent-custom-daily-limit').get_description()
                  == INVALID_DESCRIPTION, 'allowance-validation')
        return {'binding': binding, 'validation': 'rejected'}

    def allowance_preset(self, child, minutes, *, action):
        """PARENT05: saved preset readback; reopen returns the picker open."""
        require(child in CHILD_IDENTITIES and type(minutes) is int
                and minutes in PRESETS and action in ('select', 'read', 'reopen'),
                'ui:allowance-binding')
        # Refuse the wrong child and disabled controls before any input.
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:wrong-child')
        self.id_target('parent-daily-limit-selector', root=root, sensitive=True)
        self.parent_save_snapshot(child, True)
        if action == 'select':
            self.activate_id('parent-daily-limit-selector')
            self.activate_id('parent-daily-limit-' + str(minutes))
        self.parent_save_snapshot(child, True)
        # Selection closes the popover asynchronously. Its labels remain
        # selector descendants until closure, so read the saved label only
        # after a complete negative observation of the choices.
        self.wait(lambda: self.absent_id('parent-daily-limit-choices',
                                        within='parent-window'),
                  'allowance-picker-close')
        selector = self.id_target('parent-daily-limit-selector', sensitive=True)
        require(self.read_label(selector, 'allowance', maximum=32)
                == [PRESET_LABELS[minutes]], 'ui:allowance-value')
        if action == 'reopen':
            self.activate_id('parent-daily-limit-selector')
            choice = self.id_target('parent-daily-limit-' + str(minutes), sensitive=True)
            require(choice.get_description() == 'Selected daily allowance: '
                    + PRESET_LABELS[minutes], 'ui:allowance-selection')
            # The public menu.popup action opens; it is not a close toggle.
            # Leave the verified picker open for the next selection.
        return {'minutes': minutes, 'saved': True}

    def allowance_operation(self, operation):
        require(operation in ALLOWANCE_OPERATIONS, 'ui:allowance-operation')
        if operation in ('allowance-wrong-child', 'allowance-disabled'):
            child = EXISTING_CHILD if operation == 'allowance-wrong-child' else CHILD
            expected = 'ui:wrong-child' if child == EXISTING_CHILD else 'ui:unusable-target'
            try:
                self.allowance_preset(child, 0, action='select')
            except UiError as error:
                require(str(error) == expected, 'ui:allowance-refusal')
                return {'refusal': operation.removeprefix('allowance-')}
            raise UiError('ui:allowance-refusal-missing')
        _, value, action = operation.split('-')
        return self.allowance_preset(CHILD, int(value), action=action)

    def parent_save_operation(self, operation):
        """Installed PARENT08 saved snapshot and wrong-child refusal."""
        require(operation in PARENT_SAVE_OPERATIONS, 'ui:parent-save-operation')
        if operation == 'parent-save-wrong-child-refused':
            try:
                self.parent_save_snapshot(EXISTING_CHILD, True)
            except UiError as error:
                require(str(error) == 'ui:wrong-child', 'ui:parent-save-wrong-refusal')
                return {'refusal': 'wrong-child'}
            raise UiError('ui:parent-save-wrong-accepted')
        return self.parent_save_snapshot(
            EXISTING_CHILD if operation == 'multiple-other-saved' else CHILD,
            operation != 'parent-save-disabled')

    def read_label(self, root, projection, *, maximum, expected=None):
        """UI03: bounded registered nonsecret projections; no arbitrary text."""
        require(projection in ('child', 'allowance', 'empty-explanation', 'empty-picker',
                               'search-query', 'web-suggestion', 'about-product',
                               'about-version', 'about-footer')
                and type(maximum) is int
                and 1 <= maximum <= 80, 'ui:text-binding')
        require(root.get_role_name() != 'password text', 'ui:masked-text')
        if projection.startswith('about-'):
            if projection == 'about-version':
                import re
                require(type(expected) is str and re.fullmatch(r'[0-9][0-9A-Za-z.+:~\-]{0,63}', expected),
                        'ui:version-binding')
                label = 'Version ' + expected
            else:
                label = PRODUCT if projection == 'about-product' else ABOUT_FOOTER
            require(len(label) <= maximum, 'ui:text-bound')
            identity = {'about-product': 'about-product-name',
                        'about-version': 'about-version',
                        'about-footer': 'about-copyright'}[projection]
            node = self.id_target(identity, root=root)
            require(node.get_name() == label, 'ui:about-label')
            return True
        if projection == 'search-query':
            require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal') and len(expected) <= maximum,
                    'ui:search-binding')
            _application_id, _surface_id, registered = self.require_provider_contract(
                'gnome-shell', 'app-grid', ('search',))
            require(public_automation_id(root) == registered['search']
                    and self.find_provider_control(
                        'gnome-shell', 'app-grid', 'search') is root,
                    'ui:search-owner')
            require(root.get_role_name() in ('text', 'entry') and self.showing(root)
                    and self.has_state(root, self.api.StateType.EDITABLE), 'ui:search-field')
            text = root.get_text_iface()
            count = self.api.Text.get_character_count(text) if text is not None else -1
            matches = (count == len(expected)
                       and self.api.Text.get_text(text, 0, count) == expected)
            self.search_status = ('query-matched' if matches else
                                  'query-mismatch-length=' + str(min(count, 256)))
            return matches
        if projection == 'web-suggestion':
            require(expected == PRODUCT, 'ui:search-binding')
            _application_id, _surface_id, registered = self.require_provider_contract(
                'gnome-shell', 'app-grid', ('web-suggestion::parent',))
            require(public_automation_id(root) == registered['web-suggestion::parent']
                    and self.find_provider_control(
                        'gnome-shell', 'app-grid', 'web-suggestion::parent') is root,
                    'ui:search-owner')
            label = 'Search "' + expected + '" on the web'
            require(len(label) <= maximum, 'ui:text-bound')
            matches = []
            for node in self.nodes(root, strict=True):
                if (node.get_role_name() == 'label' and self.showing(node)
                        and ' '.join(node.get_name().split()) == label):
                    matches.append(node)
            require(len(matches) <= 1, 'ui:ambiguous-text-projection')
            return len(matches) == 1
        if projection == 'empty-explanation':
            text = 'No interactive non-administrator account was found.'
            require(len(text) <= maximum, 'ui:text-bound')
            require(public_automation_id(root) == 'parent-no-users-message',
                    'ui:text-surface')
            return (self.showing(root) and root.get_role_name() == 'label'
                    and ' '.join(root.get_name().split()) == text)
        if projection == 'empty-picker':
            labels = []
            for node in self.nodes(root, strict=True):
                require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-picker')
                if node.get_role_name() == 'label' and self.showing(node):
                    text = node.get_name().strip()
                    require(len(text) <= maximum, 'ui:text-bound')
                    labels.append(text)
            return labels == ['(None)']
        if projection == 'child':
            require(expected in CHILD_IDENTITIES and len(expected) <= maximum, 'ui:child-binding')
            labels = [node.get_name() for node in self.nodes(root, strict=True)
                      if node.get_role_name() == 'label' and self.showing(node)]
            require(labels == [expected], 'ui:child-label')
            return CHILD_IDENTITIES[expected]
        import re
        labels = sorted({node.get_name() for node in self.nodes(root, strict=True)
                         if node.get_role_name() == 'label' and self.showing(node)})
        if labels == ['Custom value']:
            require(len(labels[0]) <= maximum, 'ui:text-bound')
            return labels
        require(1 <= len(labels) <= 2 and all(len(text) <= maximum and re.fullmatch(
            r'[0-9]+(?:\.[0-9]+)? (?:minutes?|hours?)', text) for text in labels),
            'ui:allowance-label')
        return labels

    def parent_empty(self):
        """PARENT19: fresh explanation and sole empty picker label, without input."""
        def empty():
            root = self.find_id('parent-window')
            if root is None:
                return False
            require(root.get_name() == PRODUCT, 'ui:parent-surface')
            picker = self.find_id('parent-child-selector', root=root)
            explanation = self.find_id('parent-no-users-message', root=root)
            placeholder = (self.find_id('parent-child-selected-none', root=picker)
                           if picker is not None else None)
            return (picker is not None and explanation is not None and placeholder is not None
                    and self.read_label(explanation, 'empty-explanation', maximum=80)
                    and self.read_label(picker, 'empty-picker', maximum=80))
        self.wait(empty, 'parent-empty')

    def child_id_control(self, child, prefix, *, root, showing):
        """Resolve a UID-scoped child control, then verify its public label."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
        require(prefix in ('parent-child-choice-', 'parent-child-selected-'),
                'ui:child-control-binding')
        nodes = list(self.nodes(root, strict=True))
        identities = set()
        for node in nodes:
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-picker')
            identity = self.observed_id(node)
            if re.fullmatch(re.escape(prefix) + r'[0-9]+', identity) is None:
                continue
            require(identity not in identities, 'ui:ambiguous-automation-id')
            identities.add(identity)
        node = self.snapshot_matches(
            prefix + str(uid), nodes, showing=showing, show=self.showing,
        )
        if node is not None:
            self.read_label(node, 'child', expected=child, maximum=80)
        return node

    def focus(self, node):
        """Focus one already ID-resolved public control without keyboard routing."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        identity = self.observed_id(node)
        match = re.fullmatch(r'parent-child-choice-([0-9]+)', identity)
        require(match is not None, 'ui:child-choice-id')
        current = self.find_id(identity, root=self.parent(), showing=False)
        require(current is not None and current == node, 'ui:wrong-focus-owner')
        node = current
        labels = []
        for label in CHILD_IDENTITIES:
            if self.fixture_uids is not None:
                uid = self.fixture_uids.get(label)
            else:
                try:
                    uid = pwd.getpwnam(CHILD_ACCOUNTS[label]).pw_uid
                except KeyError:
                    continue
            if uid is not None and str(uid) == match.group(1):
                labels.append(label)
        require(len(labels) == 1, 'ui:fixture-child-uid')
        self.read_label(node, 'child', expected=labels[0], maximum=80)
        require(not self.has_state(node, self.api.StateType.DEFUNCT)
                and self.has_state(node, self.api.StateType.VISIBLE)
                and self.has_state(node, self.api.StateType.SENSITIVE),
                'ui:unusable-target')
        if self.showing(node) and self.has_state(node, self.api.StateType.FOCUSED):
            return True
        self.activate_id(
            'parent-child-selector', action_name='child.focus-' + match.group(1),
        )
        self.input_uncertain = True
        def focused():
            current = self.find_id(identity)
            return (current is not None
                    and self.has_state(current, self.api.StateType.SENSITIVE)
                    and self.has_state(current, self.api.StateType.FOCUSED))
        result = self.wait(focused, 'focus')
        self.input_uncertain = False
        return result

    def open_child_picker(self, child):
        """UI15 opening: activate by ID and focus the UID-scoped choice by ID."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        self.activate_id('parent-child-selector', action_name='menu.popup')
        choices = self.id_target('parent-child-choices')
        choice = self.wait(
            lambda: self.child_id_control(
                child, 'parent-child-choice-', root=choices, showing=False,
            ),
            'child-choice',
        )
        self.focus(choice)
        return True

    def child_highlighted(self, child):
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        def highlighted():
            root = self.find_id('parent-window')
            if root is None:
                return False
            popover = self.find_id('parent-child-popover', root=root)
            if popover is None:
                return False
            choices = self.find_id('parent-child-choices', root=popover)
            if choices is None:
                return False
            choice = self.child_id_control(
                child, 'parent-child-choice-', root=choices, showing=True,
            )
            return (choice is not None
                    and self.has_state(choice, self.api.StateType.SENSITIVE)
                    and self.has_state(choice, self.api.StateType.FOCUSED))
        return self.wait(highlighted, 'choice-highlight')

    def selected_child(self, child):
        """UI15 closed-picker result followed by PARENT03, after caller's Enter."""
        require(child in CHILD_IDENTITIES, 'ui:child-binding')
        def closed():
            root = self.find_id('parent-window')
            if root is None:
                return False
            nodes = list(self.nodes(root, strict=True))
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in nodes), 'ui:stale-picker')
            return self.absent_id('parent-child-popover', within='parent-window')
        self.wait(closed, 'picker-close')
        return self.settings(child)

    def parent_page(self, child, page):
        """PARENT04: select the declared page and observe its usable controls."""
        require(child in CHILD_IDENTITIES and page in ('Screen Limits', 'App Limits'),
                'ui:page-binding')
        print('ui:parent-page=started', file=sys.stderr, flush=True)
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        require(self.child_id_control(child, 'parent-child-selected-', root=picker,
                                      showing=True) is not None, 'ui:selected-child')
        page_id = {'Screen Limits': 'parent-page-screen-limits',
                   'App Limits': 'parent-page-app-limits'}[page]
        self.activate_id(page_id)
        print('ui:parent-page=activated', file=sys.stderr, flush=True)
        if page == 'Screen Limits':
            return self.selected_child(child)
        # Reacquire once after the page transition. Local target roots can be
        # shared within this invocation; scanning the entire installed catalogue
        # again for every filter needlessly exhausts the observation deadline.
        root = self.parent()
        self.id_target('parent-app-search', root=root, sensitive=True)
        print('ui:parent-page=search-ready', file=sys.stderr, flush=True)
        self.reveal_id('parent-filter-access-rule', root=root)
        self.reveal_id('parent-filter-match-rule', root=root)
        print('ui:parent-page=filters-ready', file=sys.stderr, flush=True)

    def app_rows(self, child, *, maximum=256, expected_ids=None):
        """PARENT12/UI13: complete public row projection, without policy expectations.

        Off-viewport controls remain readable through AT-SPI. Visibility means
        application visibility, not viewport clipping; no scroll-position inference
        or catalogue/backend query is used. Return immutable (ID, access, match)
        tuples only after a complete owned traversal and loaded-page check.
        """
        require(child in CHILD_IDENTITIES and type(maximum) is int
                and 0 <= maximum <= 256, 'ui:app-row-binding')
        require(expected_ids is None or (type(expected_ids) is tuple
                and len(set(expected_ids)) == len(expected_ids)
                and all(type(value) is str and re.fullmatch(
                    r'parent-app-[0-9a-f]{16}', value) for value in expected_ids)),
                'ui:app-row-binding')
        deadline = time.monotonic() + 45
        def check_deadline():
            require(time.monotonic() < deadline, 'ui:app-row-deadline')
        edges, identities, facts = {}, {}, {}
        nodes = []
        for node in self.nodes(strict=True, snapshot=edges, identities=identities, facts=facts):
            check_deadline()
            nodes.append(node)
        observation = (nodes, edges, identities, facts)
        root = self.snapshot_owned_target('parent-window', observation=observation,
                                          check_prompt=True)
        require(root is not None, 'ui:app-row-window')
        def target(identity, scope=root):
            check_deadline()
            node = self.snapshot_owned_target(identity, root=scope, showing=False,
                                              observation=observation)
            require(node is not None and self.has_state(node, self.api.StateType.VISIBLE)
                    and not self.has_state(node, self.api.StateType.DEFUNCT),
                    'ui:app-row-target')
            return node
        picker = target('parent-child-selector')
        uid = (self.fixture_uids[child] if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        selected = self.snapshot_owned_target(
            'parent-child-selected-' + str(uid), root=picker, observation=observation)
        require(selected is not None, 'ui:app-row-child')
        page = self.snapshot_owned_target('parent-app-limits-page', root=root,
                                         showing=False, observation=observation)
        require(page is not None and self.has_state(page, self.api.StateType.VISIBLE),
                'ui:app-row-page')
        search = target('parent-app-search', page)
        require(self.has_state(search, self.api.StateType.SENSITIVE), 'ui:app-row-loading')
        collection = target('parent-app-rows', page)
        scoped = self.snapshot_scope(nodes, edges, collection)
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT) for node in scoped),
                'ui:app-row-stale')
        public_ids = [identities[node] for node in scoped
                      if identities[node].startswith('parent-app-')]
        require(len(public_ids) == len(set(public_ids)), 'ui:app-row-duplicate')
        rows = [node for node in scoped
                if re.fullmatch(r'parent-app-[0-9a-f]{16}', identities[node])]
        require(len(rows) <= maximum, 'ui:app-row-bound')
        row_ids = {identities[node] for node in rows}
        # Orphan policy controls cannot silently disappear from the collection.
        require(all(value.rsplit('-access-', 1)[0] in row_ids
                    for value in public_ids if '-access-' in value
                    and value.startswith('parent-app-')), 'ui:app-row-orphan')
        result = []
        for row in rows:
            identity = identities[row]
            if not self.has_state(row, self.api.StateType.VISIBLE):
                continue  # Explicitly filtered out, not clipped by the viewport.
            choices = []
            for access in ('allowed', 'conditional', 'permanent'):
                control = target(identity + '-access-' + access, row)
                require(self.has_state(control, self.api.StateType.SENSITIVE),
                        'ui:app-row-loading')
                if self.has_state(control, self.api.StateType.PRESSED):
                    choices.append(access)
            require(len(choices) == 1, 'ui:app-row-access')
            match_control = target(identity + '-match-rule', row)
            matches = [value for value in ('pattern', 'precise')
                       if self.snapshot_owned_target(identity + '-match-' + value,
                           root=match_control, showing=False, observation=observation) is not None]
            require(len(matches) == 1, 'ui:app-row-match')
            target(identity + '-match-' + matches[0], match_control)
            result.append((identity, choices[0], matches[0]))
        result = tuple(sorted(result))
        require(expected_ids is None or {row[0] for row in result} == set(expected_ids),
                'ui:app-row-set')
        check_deadline()
        return result

    def match_entry(self, child, app, *, editor=False, access=None):
        """Fresh complete child/page/app and transient-owner proof before input."""
        require(child in CHILD_IDENTITIES and app in (MATCH_APP, MATCH_OTHER_APP), 'ui:match-binding')
        require(access is None or (access in ACCESS_CHOICES and not editor), 'ui:access-binding')
        require(not self.input_uncertain, 'ui:uncertain-input')
        observation = self.read_snapshot()
        nodes, edges, identities, facts = observation
        root = self.snapshot_owned_target('parent-window', check_prompt=True, observation=observation)
        require(root is not None, 'ui:match-window')
        def target(identity, scope=root):
            node = self.snapshot_owned_target(identity, root=scope, showing=False, observation=observation)
            require(node is not None and self.has_state(node, self.api.StateType.VISIBLE)
                    and not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:match-target')
            return node
        picker = target('parent-child-selector')
        uid = (self.fixture_uids[child] if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        require(self.snapshot_owned_target('parent-child-selected-' + str(uid), root=picker,
                    observation=observation) is not None, 'ui:match-child')
        page = target('parent-app-limits-page')
        search = target('parent-app-search', page)
        require(self.has_state(search, self.api.StateType.SENSITIVE), 'ui:match-loading')
        row = target(app, target('parent-app-rows', page))
        button = target(app + ('-match-rule' if access is None else '-access-' + access), row)
        if not editor:
            require(self.has_state(root, self.api.StateType.ACTIVE)
                    and self.has_state(button, self.api.StateType.SENSITIVE), 'ui:match-inactive')
            return button
        dialog = self.snapshot_owned_target('parent-match-rule-dialog', check_prompt=True,
                                           observation=observation)
        require(dialog is not None and self.has_state(dialog, self.api.StateType.ACTIVE), 'ui:match-editor')
        marker = self.snapshot_owned_target('parent-match-rule-app-' + app.removeprefix('parent-app-'),
            root=dialog, showing=False, observation=observation)
        require(marker is not None, 'ui:match-wrong-app')
        entry = target('parent-match-rule-entry', marker)
        require(self.has_state(entry, self.api.StateType.SENSITIVE)
                and self.has_state(entry, self.api.StateType.EDITABLE), 'ui:match-entry')
        return dialog, entry

    def choose_app_access(self, child, app, control):
        """UI15 → PARENT08; one ID-scoped action, never replay uncertain input."""
        require(type(control) is str and control in
                tuple(app + '-access-' + choice for choice in ACCESS_CHOICES),
                'ui:access-wrong-row')
        choice = control.rsplit('-access-', 1)[1]
        target = self.wait(lambda: self.match_entry(child, app, access=choice),
                           'access-entry')
        self._invoke_target(target)
        self.invalidate_observation()
        self.parent_app_save_snapshot(child, app)
        return {'chosen': choice}

    def read_app_access(self, child, app):
        """PARENT12 independent read; caller owns the expected saved choice."""
        require(app in (MATCH_APP, MATCH_OTHER_APP), 'ui:access-binding')
        def read():
            rows = self.app_rows(child)
            values = [access for identity, access, _ in rows if identity == app]
            require(len(values) == 1, 'ui:access-row')
            return {'app': app, 'choice': values[0]}
        return self.wait(read, 'access-row')

    def access_operation(self, operation, *, child=EXISTING_CHILD):
        require(operation in ACCESS_OPERATIONS, 'ui:access-operation')
        action = operation.removeprefix('access-')
        if action == 'screen':
            self.parent_page(child, 'Screen Limits')
            return {'page': 'screen'}
        if action in ('wrong-row', 'disabled'):
            control = (MATCH_OTHER_APP if action == 'wrong-row' else MATCH_APP) + '-access-allowed'
            try:
                self.choose_app_access(child, MATCH_APP, control)
            except UiError as error:
                require(str(error) == ('ui:access-wrong-row' if action == 'wrong-row'
                                      else 'ui:match-inactive'), 'ui:access-refusal')
                return {'refusal': action}
            raise UiError('ui:access-wrong-accepted')
        if action == 'row':
            return self.read_app_access(child, MATCH_APP)
        return self.choose_app_access(child, MATCH_APP, MATCH_APP + '-access-' + action)

    def read_match_rule(self, child, app, *, editor=False):
        """Exact finite public value; no backend reads or arbitrary text exports."""
        def read():
            value = self.match_entry(child, app, editor=editor)
            if editor:
                _, entry = value
                text = entry.get_text_iface()
                require(text is not None, 'ui:match-text')
                count = self.api.Text.get_character_count(text)
                require(0 < count <= 128, 'ui:match-text-bound')
                rule = self.api.Text.get_text(text, 0, count)
            else:
                description = value.get_description()
                require(description.startswith('Current match rule: '), 'ui:match-description')
                rule = description.removeprefix('Current match rule: ')
            require(rule in MATCH_RULES, 'ui:match-value')
            return {'app': app, 'rule': rule}
        # Independent read invocations can also encounter a disappearing toast.
        # Retry no input, and keep semantic recipient/value refusals immediate.
        return self.wait(read, 'match-rule')

    def open_match_rule(self, child, app):
        def recipient():
            require(self.absent_id('parent-match-rule-dialog', within='parent-window',
                                   incomplete_raises=True), 'ui:match-already-open')
            return self.match_entry(child, app)
        button = self.wait(recipient, 'match-before-open')
        self._invoke_target(button)
        self.invalidate_observation()
        def opened():
            try:
                return self.read_match_rule(child, app, editor=True)
            except UiError as error:
                if str(error) in ('ui:match-editor', 'ui:match-target'):
                    return None  # Native dialog map; no input replay.
                raise
        return self.wait(opened, 'match-open')

    def parent_app_save_snapshot(self, child, app):
        """PARENT08 App Limits terminal: usable controls and no failure report."""
        def saved():
            observation = self.read_snapshot()
            nodes, _, identities, _ = observation
            require(not any(identities[node] in ('feedback-dialog', 'error-report-unavailable-dialog')
                            and self.showing(node) for node in nodes), 'ui:parent-save-error-report')
            try:
                self.match_entry(child, app)
            except UiError as error:
                if str(error) in ('ui:match-loading', 'ui:match-inactive'):
                    return None
                raise
            picker = self.snapshot_owned_target('parent-child-selector', observation=observation)
            return picker is not None and self.has_state(picker, self.api.StateType.SENSITIVE)
        return self.wait(saved, 'parent-app-save')

    def respond_match_rule(self, child, app, action):
        require(type(action) is str and action in ('save', 'cancel', 'reset', 'rejected', *MATCH_INVALID),
                'ui:match-response-binding')
        invalid = action in MATCH_INVALID
        if invalid:
            self.read_synthetic_text('match-invalid-' + action, child=child)
        if action == 'rejected':
            self.read_synthetic_text('match-rejected-directory', child=child)
        # Invalid Save can leave a short-lived toast in the public tree. Retry
        # only the complete recipient proof before dispatch, with the existing
        # deadline and fresh ownership/child checks after every failed read.
        dialog, _ = self.wait(lambda: self.match_entry(child, app, editor=True),
                              'match-response-entry')
        target = self.id_target('parent-match-rule-' + ('save' if invalid or action == 'rejected' else action),
                                root=dialog, sensitive=True)
        try:
            self._invoke_target(target)
        except self.query_errors as error:
            # Action queries/dispatch are outside the retry boundary. Preserve
            # the uncertain-input latch and expose a fixed, nonsecret location.
            raise UiError('ui:match-response-query:action') from error
        self.invalidate_observation()
        if invalid:
            def rejected():
                _, entry = self.match_entry(child, app, editor=True)
                self.read_synthetic_text('match-invalid-' + action, child=child)
                return entry.get_description() == MATCH_INVALID[action]
            self.wait(rejected, 'match-invalid')
            return {'invalid': action, 'message': MATCH_INVALID[action]}
        self.wait(lambda: self.absent_id('parent-match-rule-dialog', within='parent-window'), 'match-closed')
        if action == 'rejected':
            self.wait(lambda: self.snapshot_owned_target('feedback-dialog', check_prompt=True),
                      'match-error-report')
            return {'closed': 'rejected'}
        # Public saved/control snapshot is independent of the response action.
        self.parent_app_save_snapshot(child, app)
        return {'closed': action}

    def match_operation(self, operation, *, child=EXISTING_CHILD):
        require(operation in MATCH_OPERATIONS, 'ui:match-operation')
        action = operation.removeprefix('match-')
        if action in ('wrong-app', 'ambiguous'):
            try:
                if action == 'wrong-app':
                    self.match_entry(child, MATCH_OTHER_APP, editor=True)
                else:
                    self.respond_match_rule(child, MATCH_APP, ('save', 'cancel'))
            except UiError as error:
                require(str(error) == ('ui:match-wrong-app' if action == 'wrong-app' else
                                      'ui:match-response-binding'), 'ui:match-refusal')
                return {'refusal': action}
            raise UiError('ui:match-wrong-accepted')
        if action == 'open':
            return self.open_match_rule(child, MATCH_APP)
        if action.startswith('invalid-'):
            return self.respond_match_rule(child, MATCH_APP, action.removeprefix('invalid-'))
        if action in ('save', 'cancel', 'reset', 'rejected'):
            return self.respond_match_rule(child, MATCH_APP, action)
        return self.read_match_rule(child, MATCH_APP, editor=action == 'read')

    def legend_entry(self, child):
        """One complete fresh Parent/child/page proof before legend input or read."""
        require(child in CHILD_IDENTITIES, 'ui:legend-binding')
        require(not self.input_uncertain, 'ui:uncertain-input')
        observation = self.read_snapshot()
        nodes, edges, identities, facts = observation
        root = self.snapshot_owned_target('parent-window', check_prompt=True,
                                          observation=observation)
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:legend-window')
        def target(identity):
            node = self.snapshot_owned_target(identity, root=root, showing=False,
                                              observation=observation)
            require(node is not None and self.has_state(node, self.api.StateType.VISIBLE)
                    and not self.has_state(node, self.api.StateType.DEFUNCT),
                    'ui:legend-target')
            return node
        picker = target('parent-child-selector')
        uid = (self.fixture_uids[child] if self.fixture_uids is not None
               else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
        selected = self.snapshot_owned_target('parent-child-selected-' + str(uid),
            root=picker, observation=observation)
        require(selected is not None, 'ui:legend-child')
        page = target('parent-app-limits-page')
        scope = set(self.snapshot_scope(nodes, edges, page))
        search = target('parent-app-search')
        toggle = target('parent-legend-toggle')
        require(search in scope and toggle in scope
                and self.has_state(search, self.api.StateType.SENSITIVE)
                and self.has_state(toggle, self.api.StateType.SENSITIVE), 'ui:legend-page')
        # Resolve across the complete window before checking page containment,
        # so misplaced or duplicate IDs cannot hide outside the desired subtree.
        content = self.snapshot_owned_target('parent-legend-content', root=root,
            showing=False, observation=observation)
        # GTK omits the collapsed Revealer subtree. Input is guarded by its
        # toggle ID; a read must resolve the content independently after reveal.
        require(content is None or content in scope, 'ui:legend-content')
        require(not self.has_state(toggle, self.api.StateType.PRESSED)
                or content is not None, 'ui:legend-content-missing')
        return toggle, content, observation

    def read_policy_legend(self, child):
        """UI03: bounded full explanations below the owned content ID; no input."""
        toggle, content, (nodes, edges, identities, facts) = self.legend_entry(child)
        require(self.has_state(toggle, self.api.StateType.PRESSED), 'ui:legend-closed')
        scoped = self.snapshot_scope(nodes, edges, content)
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT) for node in scoped),
                'ui:legend-stale')
        labels = [' '.join(facts[node]['name'].split()) for node in scoped
                  if facts[node]['role'] == 'label'
                  and self.has_state(node, self.api.StateType.VISIBLE)]
        require(len(labels) <= 32 and sum(map(len, labels)) <= 4096, 'ui:legend-bound')
        expected = (*LEGEND_HEADINGS, *(value for _, title, text in LEGEND_RULES
                                      for value in (title, text)))
        require(all(labels.count(value) == 1 for value in expected), 'ui:legend-explanations')
        return {'headings': list(LEGEND_HEADINGS), 'rules': [list(rule) for rule in LEGEND_RULES]}

    def expand_policy_legend(self, child):
        """UI04 once, followed by fresh independent UI03; never replay expansion."""
        toggle, _, _ = self.legend_entry(child)
        activated = not self.has_state(toggle, self.api.StateType.PRESSED)
        if activated:
            self._invoke_target(toggle)
        self.invalidate_observation()
        def ready():
            try:
                return self.read_policy_legend(child)
            except UiError as error:
                if str(error) not in ('ui:legend-closed', 'ui:legend-explanations',
                                     'ui:legend-content-missing'):
                    raise
                return None  # Reveal transition; observation retries never send input.
        result = self.wait(ready, 'legend-expanded')
        return {'activated': activated, **result}

    def policy_legend_operation(self, operation):
        require(operation in LEGEND_OPERATIONS, 'ui:legend-operation')
        if operation.endswith(('wrong-child', 'wrong-page')):
            wrong_child = operation.endswith('wrong-child')
            if not wrong_child:
                self.parent_page(EXISTING_CHILD, 'Screen Limits')
            try:
                self.expand_policy_legend(CHILD if wrong_child else EXISTING_CHILD)
            except UiError as error:
                require(str(error) in (('ui:legend-child',) if wrong_child else
                        ('ui:legend-target', 'ui:legend-page')), 'ui:legend-wrong-refusal')
            else:
                raise UiError('ui:legend-wrong-accepted')
            return {'refusal': 'wrong-child' if wrong_child else 'wrong-page'}
        return (self.expand_policy_legend(EXISTING_CHILD) if operation.endswith('expand')
                else self.read_policy_legend(EXISTING_CHILD))

    def catalogue_filter(self, child, kind, mask, action):
        """PARENT11 leaves: owned entry, UI17 options, exact read and closure.

        The caller sends Escape only after the independently checked selection.
        Each input reacquires its child/page/owner and public option identity.
        """
        require(kind in FILTER_OPTIONS and type(mask) is int
                and 0 <= mask < (1 << len(FILTER_OPTIONS[kind]))
                and action in ('open', *FILTER_OPTIONS[kind], 'read', 'closed'),
                'ui:filter-binding')
        self.text_recipient('parent-app-search', child=child)
        root = self.parent()
        choices_id = f'parent-filter-{kind}-choices'
        if action == 'closed':
            self.wait(lambda: self.absent_id(choices_id, within='parent-window'),
                      'filter-closed')
            return {'closed': kind}
        if action == 'open':
            require(self.absent_id(choices_id, within='parent-window'), 'ui:filter-already-open')
            self.activate_id(f'parent-filter-{kind}', action_name='menu.popup')
        choices = self.id_target(choices_id, root=root, sensitive=True)
        if action in FILTER_OPTIONS[kind]:
            desired = bool(mask & (1 << FILTER_OPTIONS[kind].index(action)))
            return self.set_toggle(f'parent-filter-{kind}-{action}', desired, root=choices)
        selected = []
        # Read every declared option independently, including unselected values.
        for option in FILTER_OPTIONS[kind]:
            target = self.id_target(f'parent-filter-{kind}-{option}', root=choices, sensitive=True)
            if self.has_state(target, self.api.StateType.CHECKED):
                selected.append(option)
        if action == 'open':
            return {'opened': kind}
        expected = [option for index, option in enumerate(FILTER_OPTIONS[kind])
                    if mask & (1 << index)]
        require(selected == expected, 'ui:filter-selection')
        return {'selected': selected, 'filter': kind}

    def app_row_operation(self, operation):
        require(operation in APP_ROW_OPERATIONS, 'ui:app-row-operation')
        if operation in ('catalogue-filter-wrong-child', 'catalogue-filter-wrong-page'):
            wrong_child = operation.endswith('wrong-child')
            if not wrong_child:
                self.parent_page(EXISTING_CHILD, 'Screen Limits')
            try:
                self.catalogue_filter(CHILD if wrong_child else EXISTING_CHILD,
                                      'match-rule', 2, 'open')
            except UiError as error:
                require(str(error) in (('ui:wrong-child',) if wrong_child else
                        ('ui:text-entry', 'ui:text-disabled', 'ui:app-row-page')),
                        'ui:filter-wrong-refusal')
            else:
                raise UiError('ui:filter-wrong-accepted')
            return {'refusal': 'wrong-child' if wrong_child else 'wrong-page'}
        if operation in CATALOGUE_ROW_OPERATIONS:
            binding = CATALOGUE_ROW_OPERATIONS[operation]
            if operation.endswith('reopened'):
                self.parent_page(EXISTING_CHILD, 'Screen Limits')
                self.parent_page(EXISTING_CHILD, 'App Limits')
            self.read_synthetic_text(binding, child=EXISTING_CHILD)
            expected = (() if binding == 'catalogue-absent' else
                        ('parent-app-' + hashlib.sha256(
                            b'com.puffyslippers.ONPCTest.A.desktop').hexdigest()[:16],))
            def ready():
                try:
                    if binding == 'catalogue-clear':
                        rows = self.app_rows(EXISTING_CHILD)
                        fixtures = {'parent-app-' + hashlib.sha256(
                            ('com.puffyslippers.ONPCTest.' + role + '.desktop').encode()
                            ).hexdigest()[:16] for role in ('A', 'H', 'S', 'N')}
                        return {'rows': rows} if fixtures <= {row[0] for row in rows} else None
                    return {'rows': self.app_rows(EXISTING_CHILD, expected_ids=expected)}
                except UiError as error:
                    if str(error) == 'ui:app-row-set':
                        return None  # SearchEntry's public debounce may still be pending.
                    raise
            return self.wait(ready, 'catalogue-results')
        if operation == 'catalogue-incomplete-refused':
            try:
                self.app_rows(EXISTING_CHILD, expected_ids=())
            except UiError as error:
                require(str(error) == 'ui:app-row-set', 'ui:app-row-wrong-refusal')
            else:
                raise UiError('ui:app-row-wrong-accepted')
            return {'refusal': 'incomplete-result'}
        child = EXISTING_CHILD if operation.startswith('existing-') else CHILD
        other = CHILD if child == EXISTING_CHILD else EXISTING_CHILD
        operation = operation.removeprefix('existing-')
        if operation == 'parent-app-rows-reopened':
            self.parent_page(child, 'Screen Limits')
            self.parent_page(child, 'App Limits')
        if operation in ('parent-app-rows-wrong-child', 'parent-app-rows-wrong-page'):
            wrong_child = operation == 'parent-app-rows-wrong-child'
            if not wrong_child:
                self.parent_page(child, 'Screen Limits')
            try:
                self.app_rows(other if wrong_child else child)
            except UiError as error:
                require(str(error) == ('ui:app-row-child' if wrong_child else 'ui:app-row-page'),
                        'ui:app-row-wrong-refusal')
            else:
                raise UiError('ui:app-row-wrong-accepted')
            return {'refusal': 'wrong-child' if wrong_child else 'wrong-page'}
        return {'rows': self.app_rows(child)}

    def launchable_result(self, product):
        """SEARCH04's owned Shell launcher branch, without input."""
        require(product in (PRODUCT, NATIVE_PRODUCT), 'ui:search-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            owner, nodes, snapshot, facts = self.shell_search_snapshot()
            if owner is None:
                return None
            scoped = self.snapshot_scope(nodes, snapshot, owner)
            candidates = []
            for node in scoped:
                if (facts[node]['role'] not in ('button', 'push button')
                        or not facts[node]['showing']
                        or not self.has_state(node, self.api.StateType.SENSITIVE)):
                    continue
                labels = [facts[child]['name'] for child in self.snapshot_scope(
                    nodes, snapshot, node) if facts[child]['role'] == 'label'
                    and facts[child]['showing']]
                if (facts[node]['name'] == product or labels == [product]):
                    candidates.append(node)
            require(len(candidates) <= 1, 'ui:shell-result-ambiguous')
            return candidates[0] if candidates else None
        require(product == PRODUCT, 'ui:search-provider-binding')
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid', ('result::parent',))
        if surface is None:
            return None
        target = self.find_id(registered['result::parent'], root=surface)
        if target is None:
            return None
        require(target.get_role_name() in ('button', 'push button')
                and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:search-result')
        labels = [' '.join(node.get_name().split()) for node in self.nodes(target, strict=True)
                  if self.showing(node) and node.get_role_name() == 'label']
        require(' '.join(target.get_name().split()) == product or labels == [product],
                'ui:search-result')
        return target

    def help_desktop_clear(self):
        """Check the parent desktop after each stream read, with no product window."""
        self.standard_shell_desktop(no_prompt=True)
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        nodes = list(self.nodes(root, strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:stale-surface')
        forbidden = {'parent-window', 'parent-access-denied-window',
                     'kiosk-request-window', 'kiosk-request-form',
                     'feedback-dialog', 'startup-error-window'}
        require(not any(self.showing(node) and public_automation_id(node) in forbidden
                        for node in nodes), 'ui:help-product-window')

    def launch_parent_command(self, *, standard=False):
        """PARENT01: submit one fixed public executable as the desktop user.

        The user service manager supplies the graphical session environment.
        No shell, terminal, product API, policy write or success inference is
        involved. The journey observes the expected product window separately.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require_active_launch_session()
        self.desktop_result(EXISTING_CHILD if standard else PARENT, 'success')
        self.handle_system_prompt()
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-parent',
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)
        # Keep the input latch set: even a successful submission cannot be
        # repeated by this adapter instance. The next checkpoint is a new read.

    def new_parent_window_entry(self):
        """Refuse a new-window declaration while an owned Parent window exists."""
        self.desktop_result(PARENT, 'success')
        require(self.parent_search_closed(), 'ui:parent-window-exists')

    def parent_restart_entry(self, window, destination):
        """LIFE01 entry is observation only; never launch or focus to repair it."""
        require(window == 'parent' and destination == 'management', 'ui:restart-binding')
        root = self.snapshot_owned_target('parent-window', check_prompt=True)
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:restart-window')

    def parent_initial_selection(self):
        """Read the unopened child selector before any selection or edit."""
        root = self.parent()
        picker = self.id_target('parent-child-selector', root=root, sensitive=True)
        nodes = list(self.nodes(picker, strict=True))
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes),
                'ui:stale-picker')
        selected = [node for node in nodes if self.showing(node)
                    and public_automation_id(node).startswith('parent-child-selected-')]
        require(len(selected) == 1, 'ui:initial-selection')
        for child in (CHILD, EXISTING_CHILD):
            uid = (self.fixture_uids.get(child) if self.fixture_uids is not None
                   else pwd.getpwnam(CHILD_ACCOUNTS[child]).pw_uid)
            if public_automation_id(selected[0]) == 'parent-child-selected-' + str(uid):
                self.read_label(selected[0], 'child', expected=child, maximum=80)
                return CHILD_IDENTITIES[child]
        raise UiError('ui:initial-selection')

    def parent_search_closed(self):
        """Independent complete window absence on the qualified Parent desktop."""
        self.standard_shell_desktop(no_prompt=True)
        _owner, nodes, _snapshot, facts = self.shell_search_snapshot()
        forbidden = {'parent-window', 'parent-access-denied-window', 'startup-error-window'}
        return not any(facts[node]['showing'] and facts[node]['identity'] in forbidden
                       for node in nodes)

    def shell_provider_metadata(self):
        """Qualification provenance only; no product state or arbitrary text."""
        owner, _nodes, _snapshot, _facts = self.shell_search_snapshot()
        return self._shell_provider_metadata(owner)

    def gdm_provider_metadata(self, *, installed_child=False):
        """Read the actual declared greeter provider, never observer locale."""
        owner, _rows = (self.gdm_semantic_rows((PARENT, KIOSK, CHILD)) if installed_child else
                        self.gdm_semantic_rows((PARENT,), excluded=(KIOSK,)))
        shell = self._shell_provider_metadata(owner, greeter=True)
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'gdm3'],
            text=True, timeout=5).strip()
        return validate_gdm_metadata({'shell': shell, 'gdm_version': version})

    def _shell_provider_metadata(self, owner, *, greeter=False):
        from gi.repository import Gio
        require(owner is not None, 'ui:shell-provider-owner')
        pid = owner.get_process_id()
        require(type(pid) is int and pid > 0, 'ui:shell-provider-owner')
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                           if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'gnome-shell'],
            text=True, timeout=5).strip()
        # Shell's InputSourceManager uses locale1 for the greeter, not the
        # account's desktop GSettings (which can legitimately be empty).
        # https://github.com/GNOME/gnome-shell/blob/50.1/js/ui/status/keyboard.js
        sources = (greeter_keyboard_sources() if greeter else
                   Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack())
        return validate_shell_metadata({'version': version, 'locale': locale,
                                        'keyboard': [list(source) for source in sources]})

    def launch_child_command(self, *, child=EXISTING_CHILD):
        """REQUEST02 input: submit the installed child overlay command once.

        A separate form observation must establish the child and usable result.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require_active_launch_session()
        require(child in (CHILD, EXISTING_CHILD), 'ui:overlay-child-binding')
        self.desktop_result(child, 'success')
        self.handle_system_prompt()
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec', '/usr/bin/oh-no-parent-control-child',
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)

    def parent_denial_closed(self):
        """Read the public desktop and complete absence after denial dismissal."""
        self.desktop_result(EXISTING_CHILD, 'success')
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        nodes = list(self.nodes(root, strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:stale-surface')
        forbidden = {'parent-access-denied-window', 'parent-window',
                     'parent-screen-limits-page', 'parent-app-limits-page',
                     'parent-screen-limit-toggle'}
        return not any(self.showing(node) and public_automation_id(node) in forbidden
                       for node in nodes)

    def management_denied(self):
        """FILE06: the specific visible refusal, never generic error or echo."""
        root = self.id_target('parent-access-denied-window')
        message = self.id_target('parent-access-denied-message', root=root)
        require(message.get_role_name() == 'label' and message.get_name() ==
                'Only an administrator can manage parental controls. '
                'Sign in with an administrator account to open the Parent App.',
                'ui:denial-message')
        self.id_target('parent-access-denied-close', root=root, sensitive=True)
        require(self.has_state(root, self.api.StateType.ACTIVE), 'ui:denial-not-active')
        self.management_absent()

    def management_absent(self, *, within='parent-access-denied-window'):
        """UI11: complete fresh exclusion; stale or missing trees refuse."""
        require(self.find_id(within) is not None, 'ui:missing-surrounding-surface')
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:missing-surface')
        for node in self.nodes(root, strict=True):
            require(not self.has_state(node, self.api.StateType.DEFUNCT), 'ui:stale-surface')
            if self.showing(node):
                require(public_automation_id(node) not in (
                    'parent-window', 'parent-screen-limits-page', 'parent-app-limits-page',
                    'parent-screen-limit-toggle'), 'ui:management-exposed')

    def search_result(self, product, expected, *, stable_seconds=2):
        """SEARCH04: observe the explicit registered result, without launching."""
        require(product == PRODUCT and expected in ('launchable', 'unavailable'),
                'ui:search-binding')
        if expected == 'launchable':
            return self.launchable_result(product)
        return self.observe_absence('overview', 'launcher-and-window', name=product,
                                    mode='stable', stable_seconds=stable_seconds)

    def desktop_result(self, account, expected):
        """GDM06 success on the caller's qualified public desktop connection."""
        require(account in (PARENT, EXISTING_CHILD, CHILD) and expected == 'success',
                'ui:desktop-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            return self.standard_shell_desktop()
        surface, registered = self.provider_surface(
            'gnome-shell', 'desktop', ('desktop',))
        target = (self.find_id(registered['desktop'], root=surface)
                  if surface is not None else None)
        require(target is not None, 'ui:desktop')
        return target

    def shell_desktop_observation(self, *, no_prompt=False):
        """One complete Shell desktop read, shared by entry and TIME01."""
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        snapshot, facts, identities = {}, {}, {}
        nodes = list(self.nodes(root, strict=True, protect_text=True,
                                snapshot=snapshot, facts=facts, identities=identities))
        if any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes):
            error = UiError('ui:incomplete-tree')
            error.add_note('desktop observation contains a defunct node')
            raise error
        if no_prompt:
            require(self.system_prompt_kind(observation=(nodes, snapshot, facts)) is None,
                    'ui:fresh-desktop-prompt')
        owners = [node for node in nodes if node.get_parent() == root
                  and node.get_role_name() == 'application'
                  and node.get_name().casefold() in GDM_SEMANTIC_APPLICATION_NAMES]
        require(len(owners) <= 1, 'ui:shell-provider-owner')
        if not owners:
            return None
        panels = [node for node in self.snapshot_scope(nodes, snapshot, owners[0])
                  if node.get_role_name() == 'toggle button' and node.get_name() == 'Activities'
                  and self.showing(node)
                  and self.has_state(node, self.api.StateType.SENSITIVE)]
        require(len(panels) <= 1, 'ui:shell-desktop-ambiguous')
        if not panels:
            return None
        return owners[0], panels[0], (nodes, snapshot, identities, facts)

    def child_countdown(self, present):
        """TIME01: read-only child-desktop text or two seconds of complete absence."""
        require(type(present) is bool, 'ui:countdown-binding')
        uid = pwd.getpwnam(CHILD_ACCOUNTS[CHILD]).pw_uid
        require(uid >= 1000 and os.getuid() == uid and os.geteuid() == uid,
                'ui:countdown-account')
        require_active_launch_session()
        stable_since = None

        def observe():
            nonlocal stable_since
            try:
                value = self.shell_desktop_observation(no_prompt=True)
                if value is None:
                    stable_since = None
                    return None
                owner, _, (nodes, edges, identities, facts) = value
                scope = self.snapshot_scope(nodes, edges, owner)
                controls = {}
                for identity in ('child-screen-time-indicator', 'child-request-button',
                                 'child-remaining-time'):
                    matches = [node for node in nodes if identities[node] == identity]
                    require(len(matches) <= 1, 'ui:ambiguous-automation-id')
                    require(all(node in scope for node in matches), 'ui:countdown-owner')
                    controls[identity] = matches[0] if matches else None
                label = controls['child-remaining-time']
                if present:
                    anchor = controls['child-screen-time-indicator']
                    button = controls['child-request-button']
                    if any(node is None or not self.showing(node)
                           for node in (anchor, button, label)):
                        return None
                    descendants = self.snapshot_scope(nodes, edges, anchor)
                    require(button in descendants and label in
                            self.snapshot_scope(nodes, edges, button), 'ui:countdown-owner')
                    require(facts[label]['role'] == 'label', 'ui:countdown-label')
                    text = facts[label]['name']
                    countdown_seconds(text)  # Bound public text before transport/storage.
                    return {'child': 'fixture-child', 'surface': 'desktop', 'present': True,
                            'text': text, 'observed_monotonic_ns': time.monotonic_ns(),
                            'stable_ms': 0}
                if any(node is not None and self.showing(node) for node in controls.values()):
                    stable_since = None
                    return None
                now = time.monotonic_ns()
                if stable_since is None:
                    stable_since = now
                if now - stable_since < 2_000_000_000:
                    return None
                return {'child': 'fixture-child', 'surface': 'desktop', 'present': False,
                        'text': None, 'observed_monotonic_ns': now,
                        'stable_ms': (now - stable_since) // 1_000_000}
            except BaseException:
                stable_since = None
                raise

        result = self.wait(observe, 'child-countdown', prompt_in_predicate=True)
        require_active_launch_session()
        return result

    def standard_shell_desktop(self, *, no_prompt=False):
        """Shell 50 English desktop observation on the bound fixture user's bus.

        This external-provider adapter recognizes Shell's public Activities toggle;
        it authorizes no Shell input, menu, search, lock or retained-session route.
        """
        def observe():
            value = self.shell_desktop_observation(no_prompt=no_prompt)
            return value[1] if value else None
        if not no_prompt:
            return self.wait(observe, 'shell-desktop')
        # A complete positive desktop and repeated complete prompt-free reads
        # make the declared fresh-keyring profile observable, including late
        # dialogs. No prompt input is delivered by this qualification.
        stable_since = None
        def stable():
            nonlocal stable_since
            try:
                desktop = observe()
            except Exception:
                stable_since = None
                raise
            if desktop is None:
                stable_since = None
                return None
            stable_since = stable_since or time.monotonic()
            return desktop if time.monotonic() - stable_since >= 2 else None
        return self.wait(stable, 'fresh-shell-desktop', prompt_in_predicate=True)

    def keyring_cancel_target(self):
        """Resolve the real gcr login-keyring Cancel through one complete tree."""
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(root, strict=True, protect_text=True,
                                snapshot=snapshot, facts=facts))
        kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
        require(kind in (None, 'keyring'), 'ui:keyring-prompt-replaced')
        if kind is None:
            return None
        applications = [node for node in nodes if node.get_parent() == root
                        and facts[node]['role'] == 'application'
                        and self._prompt_application_kind(facts[node]['name']) == 'keyring']
        require(len(applications) == 1, 'ui:keyring-owner')
        # GTK's application container has no window visibility state. Require
        # a live owner here and visible dialog/controls below, as for Shell.
        require(not self.has_state(applications[0], self.api.StateType.DEFUNCT),
                'ui:stale-surface')
        scopes = self.snapshot_scope(nodes, snapshot, applications[0])
        dialogs = [node for node in scopes if node is not applications[0]
                   and facts[node]['showing']
                   and (facts[node]['role'] in ('dialog', 'alert') or facts[node]['modal'])]
        require(len(dialogs) == 1
                and facts[dialogs[0]]['name'].casefold() == 'unlock login keyring',
                'ui:keyring-dialog')
        controls = self.snapshot_scope(nodes, snapshot, dialogs[0])
        fields = [node for node in controls if facts[node]['role'] == 'password text'
                  and facts[node]['showing']]
        require(len(fields) == 1 and self.has_state(fields[0], self.api.StateType.SENSITIVE)
                and self.has_state(fields[0], self.api.StateType.FOCUSED),
                'ui:keyring-focus')
        interface = fields[0].get_text_iface()
        require(interface is not None and self.api.Text.get_character_count(interface) == 0,
                'ui:keyring-secret-state')
        buttons = [node for node in controls if facts[node]['role'] in ('push button', 'button')
                   and facts[node]['name'] == 'Cancel' and facts[node]['showing']]
        require(len(buttons) == 1 and self.has_state(buttons[0], self.api.StateType.SENSITIVE),
                'ui:keyring-cancel')
        self._keyring_challenge = (applications[0], dialogs[0], fields[0], buttons[0])
        return buttons[0]

    def cancel_keyring_prompt(self):
        """Cancel once, then independently observe a stable prompt-free desktop."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.wait(self.keyring_cancel_target, 'keyring-prompt',
                           prompt_in_predicate=True)
        challenge = self._keyring_challenge
        self._invoke_target(target)
        def dismissed():
            root = self.api.get_desktop(0)
            require(root is not None, 'ui:incomplete-tree')
            snapshot, facts = {}, {}
            nodes = list(self.nodes(root, strict=True, protect_text=True,
                                    snapshot=snapshot, facts=facts))
            kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
            require(kind in (None, 'keyring'), 'ui:keyring-prompt-replaced')
            if kind == 'keyring':
                require(all(node in nodes for node in challenge),
                        'ui:keyring-prompt-replaced')
            return kind is None
        self.wait(dismissed, 'keyring-dismissed', prompt_in_predicate=True)
        self.standard_shell_desktop(no_prompt=True)

    def greeter_list(self, name=PARENT):
        """GDM01: resolve the greeter/list/account entirely by provider IDs."""
        require(name in GREETER_IDENTITIES, 'ui:gdm-account-binding')
        logical = 'account-choice::' + GREETER_IDENTITIES[name]

        def account():
            surface, registered = self.provider_surface(
                'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
            if surface is None:
                return None
            account_list = self.find_id(registered['account-list'], root=surface)
            if account_list is None:
                return None
            target = self.find_id(registered[logical], root=account_list)
            if target is None:
                return None
            names = (KIOSK, KIOSK_USERNAME) if name == KIOSK else (name,)
            require(' '.join(target.get_name().split()) in names,
                    'ui:gdm-account-label')
            return target

        target = self.wait(account, 'gdm-account-id')
        self.observe_absence('greeter', 'password', name=name, mode='snapshot')
        return target

    def gdm_nonsecret_has_id_route(self):
        """Whether G01 can use a complete public-ID route without tree reads."""
        contract = self.provider_contracts.get('gdm', {})
        surface = contract.get('surfaces', {}).get('greeter')
        if not (type(contract.get('application_id')) is str
                and contract['application_id'] and surface is not None
                and type(surface[0]) is str and surface[0]):
            return False
        registered = surface[1]
        required = ('account-list', 'account-choice::parent',
                    'account-choice::other-parent', 'account-choice::other-child',
                    'account-choice::station', 'selected-recipient', 'password')
        return all(type(registered.get(control)) is str and registered[control]
                   for control in required)

    @staticmethod
    def gdm_semantic_name(node):
        return ' '.join(node.get_name().split())

    def gdm_semantic_owner(self):
        """Resolve the one Shell application on the active greeter bus."""
        return self.gdm_semantic_nodes(protect_text=True)[0]

    def gdm_semantic_nodes(self, *, protect_text=False):
        """Resolve owner and its complete scope from the same public snapshot.

        This is the deliberately narrow provider-specific exception for G01.
        It is not a generic name/role selector: the standalone process is bound
        to the sole active local greeter account before this tree is read.
        """
        def owner():
            desktop = self.api.get_desktop(0)
            require(desktop is not None, 'ui:incomplete-tree')
            snapshot = {}
            nodes = list(self.nodes(desktop, strict=True, protect_text=protect_text,
                                    snapshot=snapshot))
            owners = [node for node in nodes
                      if node.get_parent() == desktop
                      and node.get_role_name() == 'application'
                      and self.gdm_semantic_name(node).casefold()
                      in GDM_SEMANTIC_APPLICATION_NAMES]
            require(len(owners) <= 1, 'ui:gdm-provider-owner')
            if not owners:
                return None
            scope = self.snapshot_scope(nodes, snapshot, owners[0])
            # Reject this entire read before returning any provider scope.
            # The existing bounded wait may reacquire after a GDM transition;
            # no stale node can authorize a result or input.
            require(scope and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                      for node in scope), 'ui:gdm-stale-tree')
            return owners[0], scope

        # The greeter session and bus can precede Shell's public application.
        # Absence permits another read, never input or a replacement owner.
        return self.wait(owner, 'gdm-provider-owner')

    def gdm_semantic_account_rows(self, owner, nodes, names):
        """Resolve exact account labels to their GDM button ancestors."""
        rows = []
        for node in nodes:
            if not self.showing(node) or self.gdm_semantic_name(node) not in names:
                continue
            candidate = node if node.get_role_name() in GDM_ACCOUNT_ROLES else None
            if node.get_role_name() == 'label':
                current = node.get_parent()
                while current is not None and current != owner:
                    if current.get_role_name() in GDM_ACCOUNT_ROLES:
                        candidate = current
                        break
                    current = current.get_parent()
            if (candidate is not None and self.showing(candidate)
                    and candidate not in rows):
                rows.append(candidate)
        return rows

    def gdm_semantic_row_diagnostic(self, owner):
        """Return only fixed categories describing failed account matching."""
        desktop = self.api.get_desktop(0)
        all_nodes = list(self.nodes(desktop, strict=True))

        def ownership(node):
            current = node
            visited = set()
            while current is not None and current not in visited:
                if current == owner:
                    return 'provider-owner'
                visited.add(current)
                current = current.get_parent()
            return 'other-owner'

        def role(node):
            observed = node.get_role_name()
            return observed if observed in GDM_DIAGNOSTIC_ROLES else 'other'

        def matches(names):
            found = [node for node in all_nodes
                     if self.gdm_semantic_name(node) in names]
            provider_nodes = [node for node in all_nodes
                              if ownership(node) == 'provider-owner']
            roles = {}
            visibility = {'showing': 0, 'hidden': 0}
            owners = {'provider-owner': 0, 'other-owner': 0}
            for node in found:
                observed_role = role(node)
                roles[observed_role] = roles.get(observed_role, 0) + 1
                observed_visibility = 'showing' if self.showing(node) else 'hidden'
                visibility[observed_visibility] += 1
                observed_owner = ownership(node)
                owners[observed_owner] += 1
            return {
                'matching_nodes': len(found),
                'matching_rows': len(self.gdm_semantic_account_rows(
                    owner, provider_nodes, names)),
                'roles': {key: roles[key] for key in sorted(roles)},
                'visibility': visibility,
                'ownership': owners,
            }

        return {
            'event': 'gdm-account-observation',
            'owner': {
                'role': role(owner),
                'showing': self.showing(owner),
            },
            'matches': {
                'ordinary': matches((PARENT,)),
                'other-ordinary': matches((OTHER_PARENT,)),
                'standard': matches((EXISTING_CHILD,)),
                'station': matches((KIOSK, KIOSK_USERNAME)),
            },
        }

    def gdm_semantic_rows(self, expected, *, excluded=()):
        """Return declared fixture rows from one complete account-list snapshot."""
        require(type(expected) is tuple and expected
                and len(set(expected)) == len(expected)
                and set(expected) <= {PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD, KIOSK}
                and type(excluded) is tuple
                and len(set(excluded)) == len(excluded)
                and set(excluded) <= {PARENT, OTHER_PARENT, EXISTING_CHILD, KIOSK}
                and not set(expected) & set(excluded),
                'ui:gdm-account-binding')
        owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        require(not any(node.get_role_name() == 'password text' for node in showing),
                'ui:gdm-list-prompt-overlap')

        bindings = {
            PARENT: (PARENT,),
            OTHER_PARENT: (OTHER_PARENT,),
            EXISTING_CHILD: (EXISTING_CHILD,),
            CHILD: (CHILD,),
            KIOSK: (KIOSK, KIOSK_USERNAME),
        }
        identities = (*expected, *excluded)
        rows = {name: self.gdm_semantic_account_rows(
            owner, showing, bindings[name]) for name in identities}
        expected_rows = {name: rows[name] for name in expected}
        complete = (all(len(matches) == 1 for matches in expected_rows.values())
                    and len({matches[0] for matches in expected_rows.values()})
                    == len(expected_rows))
        if excluded:
            complete = complete and all(not rows[name] for name in excluded)
        if not complete and not self.gdm_row_diagnostic_emitted:
            print(json.dumps(self.gdm_semantic_row_diagnostic(owner), sort_keys=True),
                  file=sys.stderr, flush=True)
            self.gdm_row_diagnostic_emitted = True
        require(complete, 'ui:gdm-account-cardinality')
        result = {name: matches[0] for name, matches in expected_rows.items()}
        for row in result.values():
            require(self.has_state(row, self.api.StateType.SENSITIVE),
                    'ui:gdm-account-unavailable')
        return owner, result

    def gdm_nonsecret_account(self, name):
        require(name in (PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD, KIOSK),
                'ui:gdm-nonsecret-binding')
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_list(name)
        # Station entry must also work when every parent is locked, hidden or
        # differently named. Its own usable row is the required destination.
        expected = (KIOSK,) if name == KIOSK else tuple(dict.fromkeys((PARENT, KIOSK, name)))
        _owner, rows = self.gdm_semantic_rows(expected)
        return rows[name]

    def gdm_product_free_account(self):
        """Resolve case 1's declared Parent row while proving station absence."""
        require(not self.gdm_nonsecret_has_id_route(),
                'ui:gdm-product-free-binding')
        _owner, rows = self.gdm_semantic_rows((PARENT,), excluded=(KIOSK,))
        return rows[PARENT]

    def gdm_nonsecret_navigation(self, name):
        """Focus one fresh G01 row without deriving input from list position."""
        if self.gdm_nonsecret_has_id_route():
            return self.greeter_navigation(name)
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.gdm_nonsecret_account(name)
        if self.has_state(target, self.api.StateType.FOCUSED):
            return True
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')

        def focused():
            refreshed = self.gdm_nonsecret_account(name)
            require(refreshed == target, 'ui:gdm-stale-focus')
            return self.has_state(refreshed, self.api.StateType.FOCUSED)

        self.wait(focused, 'gdm-account-focus')
        self.input_uncertain = False
        return True

    def gdm_product_free_navigation(self):
        """Focus case 1's fresh Parent row without accepting another binding."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.gdm_product_free_account()
        if self.has_state(target, self.api.StateType.FOCUSED):
            return True
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')

        def focused():
            refreshed = self.gdm_product_free_account()
            require(refreshed == target, 'ui:gdm-stale-focus')
            return self.has_state(refreshed, self.api.StateType.FOCUSED)

        self.wait(focused, 'gdm-account-focus')
        self.input_uncertain = False
        return True

    def kiosk_gdm_returned(self):
        """Observe the exited station's usable greeter and absent owned UI."""
        self.gdm_semantic_rows((KIOSK,))
        nodes = list(self.nodes(strict=True))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:gdm-stale-tree')
        forbidden = {
            KIOSK_APPLICATION, 'kiosk-request-window', 'kiosk-request-form',
            'feedback-dialog', 'startup-error-window',
            'error-report-unavailable-dialog',
        }
        require(not any(public_automation_id(node) in forbidden and self.showing(node)
                        for node in nodes), 'ui:kiosk-exit-incomplete')

    def gdm_semantic_prompt(self):
        """Resolve one prepared prompt without traversing its protected field."""
        owner, nodes = self.gdm_semantic_nodes(protect_text=True)
        showing = [node for node in nodes if self.showing(node)]
        account_rows = self.gdm_semantic_account_rows(
            owner, showing, tuple(GREETER_IDENTITIES))
        require(not account_rows, 'ui:gdm-list-prompt-overlap')
        recipients = [node for node in showing
                      if node.get_role_name() == 'label'
                      and self.gdm_semantic_name(node)
                      in (PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD)]
        fields = [node for node in showing
                  if node.get_role_name() == 'password text']
        require(len(recipients) == 1, 'ui:gdm-recipient')
        require(len(fields) == 1
                and self.has_state(fields[0], self.api.StateType.SENSITIVE)
                and self.has_state(fields[0], self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')
        return self.gdm_semantic_name(recipients[0]), fields[0]

    def gdm_nonsecret_prompt(self):
        """Observe Parent's prompt without reading or authorizing its secret."""
        self.greeter_prompt()

    def gdm_child_time_denied(self):
        """GDM06: exact English-GDM expiry explanation on the bound greeter bus.

        The provider's PAM account-expiry message is distinct from failed
        password authentication. Read only public labels, never password text.
        A fresh snapshot must still identify the child and hide the account list.
        """
        def denied():
            owner, nodes = self.gdm_semantic_nodes(protect_text=True)
            showing = [node for node in nodes if self.showing(node)]
            require(not self.gdm_semantic_account_rows(owner, showing, tuple(GREETER_IDENTITIES)),
                    'ui:gdm-denial-list-overlap')
            recipients = [node for node in showing if node.get_role_name() == 'label'
                          and self.gdm_semantic_name(node) in (PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD)]
            require(len(recipients) == 1 and self.gdm_semantic_name(recipients[0]) == CHILD,
                    'ui:gdm-denial-recipient')
            messages = [node for node in showing if node.get_role_name() == 'label'
                        and self.gdm_semantic_name(node) ==
                        'Your account was given a time limit that’s now passed.']
            require(len(messages) <= 1, 'ui:gdm-denial-ambiguous')
            return bool(messages)

        self.wait(denied, 'gdm-child-time-denied', prompt_in_predicate=True)
        return {'recipient': 'fixture-child', 'reason': 'time-limit', 'desktop_access': False}

    def station_entry_branch(self, owner):
        """Read the offered branch without selecting or dismissing any control."""
        require(owner in ('greeter', 'station'), 'ui:station-branch-owner')
        if owner == 'station':
            def destination():
                snapshot = {}
                identities = {}
                nodes = list(self.nodes(
                    strict=True, snapshot=snapshot, identities=identities))
                require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                for node in nodes), 'ui:station-stale-tree')
                observation = (nodes, snapshot, identities, None)
                window = self.snapshot_owned_target(
                    'kiosk-request-window', observation=observation)
                if window is None:
                    return None
                form = self.snapshot_owned_target(
                    'kiosk-request-form', root=window, observation=observation)
                if form is None:
                    return None
                return {'destination': 'default-request-form', 'controls': []}
            return self.wait(destination, 'station-default-destination')
        _owner, nodes = self.gdm_semantic_nodes()
        showing = [node for node in nodes if self.showing(node)]
        recipients = [node for node in showing if node.get_role_name() == 'label'
                      and self.gdm_semantic_name(node) in (KIOSK, KIOSK_USERNAME)]
        require(len(recipients) == 1, 'ui:station-branch-recipient')
        require(not any(node.get_role_name() == 'password text' for node in showing),
                'ui:station-unexpected-password')
        roles = {'button', 'push button', 'toggle button', 'radio button',
                 'menu item', 'radio menu item', 'check menu item', 'combo box'}
        controls = []
        for node in showing:
            role = node.get_role_name()
            if role not in roles:
                continue
            label = GDM_SESSION_LABELS.get(self.gdm_semantic_name(node), 'unresolved')
            controls.append({'label': label, 'role': role,
                             'public_id_present': bool(public_automation_id(node)),
                             'sensitive': self.has_state(node, self.api.StateType.SENSITIVE),
                             'focused': self.has_state(node, self.api.StateType.FOCUSED)})
        require(0 < len(controls) <= 12, 'ui:station-branch-controls')
        known = [control['label'] for control in controls if control['label'] != 'unresolved']
        require(len(known) == len(set(known)), 'ui:station-branch-ambiguous')
        return {'destination': 'greeter-controls', 'controls': controls}

    def station_default_entry(self, owner):
        """Read back the one qualified passwordless default-session result."""
        require(owner == 'station', 'ui:station-default-branch')

        def destination():
            snapshot = {}
            identities = {}
            nodes = list(self.nodes(
                strict=True, snapshot=snapshot, identities=identities))
            require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                            for node in nodes), 'ui:station-stale-tree')
            observation = (nodes, snapshot, identities, None)
            window = self.snapshot_owned_target(
                'kiosk-request-window', observation=observation)
            if window is None:
                return None
            require(self.showing(window), 'ui:station-default-window')
            form = self.snapshot_owned_target(
                'kiosk-request-form', root=window, observation=observation)
            if form is None:
                return None
            require(self.showing(form), 'ui:station-default-form')
            return {'destination': 'default-request-form'}

        return self.wait(destination, 'station-default-destination')

    def observe_absence(self, surface, target, *, name, mode, stable_seconds=None):
        """UI11: registered positive surfaces and complete fresh exclusion reads."""
        if surface == 'overview':
            require(target == 'launcher-and-window' and name == PRODUCT and mode == 'stable'
                    and type(stable_seconds) in (int, float) and 0 < stable_seconds <= 10,
                    'ui:absence-binding')
            return self.search_absence(name, stable_seconds=stable_seconds)
        require(stable_seconds is None, 'ui:absence-binding')
        if surface == 'parent':
            require(target == 'child-popup' and name in CHILD_IDENTITIES
                    and mode == 'snapshot', 'ui:absence-binding')
            def closed():
                root = self.parent()
                picker = self.id_target('parent-child-selector', root=root, sensitive=True)
                if self.child_id_control(name, 'parent-child-selected-',
                                         root=picker, showing=True) is None:
                    return False
                nodes = list(self.nodes(root, strict=True))
                return (not any(self.has_state(node, self.api.StateType.DEFUNCT) for node in nodes)
                        and self.absent_id('parent-child-popover', within='parent-window'))
            return self.wait(closed, 'picker-close')
        require(surface == 'greeter' and target in ('password', 'account')
                and name in GREETER_IDENTITIES and mode == 'snapshot', 'ui:absence-binding')

        def absent():
            account_control = 'account-choice::' + GREETER_IDENTITIES[name]
            positive_control = account_control if target == 'password' else 'selected-recipient'
            absent_control = 'password' if target == 'password' else 'account-list'
            surface_root, registered = self.provider_surface(
                'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
            if surface_root is None:
                return False
            nodes = list(self.nodes(surface_root, strict=True))
            positive = self.find_id(registered[positive_control], nodes=nodes)
            if positive is None:
                return False
            if target == 'account':
                require(' '.join(positive.get_name().split()) == name,
                        'ui:gdm-recipient')
            for node in nodes:
                if self.has_state(node, self.api.StateType.DEFUNCT):
                    return False
            absent = self.find_id(registered[absent_control], nodes=nodes, showing=False)
            return absent is None or not self.showing(absent)

        return self.wait(absent, 'gdm-prompt-dismissed' if target == 'password' else 'gdm-list-hidden')

    def choice_order(self, root, *, identities, maximum, cardinality, projection):
        """UI13: fresh complete collection, returning only canonical identities.

        Rows may be outside the viewport in a scrolling account list. Their
        order is readable; the separate focus checkpoint qualifies the input.
        """
        require(root is not None and type(maximum) is int and 1 <= maximum <= 32
                and type(cardinality) is tuple and len(cardinality) == 2
                and 0 <= cardinality[0] <= cardinality[1] <= maximum
                and identities == CHILD_IDENTITIES and projection == 'child-picker-order',
                'ui:collection-binding')
        choices = []
        if projection == 'child-picker-order':
            require(public_automation_id(root) == 'parent-child-choices',
                    'ui:child-collection-surface')
            require(self.find_id('parent-child-choices', showing=False) == root,
                    'ui:wrong-collection-owner')
            bindings = {}
            for label, canonical in CHILD_IDENTITIES.items():
                if self.fixture_uids is not None:
                    if label not in self.fixture_uids:
                        continue  # The new account may not have been created yet.
                    uid = self.fixture_uids[label]
                else:
                    try:
                        uid = pwd.getpwnam(CHILD_ACCOUNTS[label]).pw_uid
                    except KeyError:
                        continue
                require(type(uid) is int and uid >= 1000, 'ui:fixture-child-uid')
                identity = 'parent-child-choice-' + str(uid)
                require(identity not in bindings, 'ui:duplicate-choice-identity')
                bindings[identity] = (label, canonical)
            for node in self.nodes(root, strict=True):
                require(not self.has_state(node, self.api.StateType.DEFUNCT),
                        'ui:stale-collection')
                identity = public_automation_id(node)
                if re.fullmatch(r'parent-child-choice-[0-9]+', identity) is None:
                    continue
                require(identity in bindings, 'ui:unregistered-child-choice')
                label, canonical = bindings[identity]
                self.read_label(node, 'child', expected=label, maximum=80)
                require(canonical not in choices, 'ui:duplicate-choice-identity')
                choices.append(canonical)
                require(len(choices) <= maximum, 'ui:collection-bound')
            require(cardinality[0] <= len(choices) <= cardinality[1],
                    'ui:collection-cardinality')
            return tuple(choices)
    def greeter_navigation(self, name):
        """Focus one ID-addressed row without calculating input from list order."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.fresh_owned_target(self.greeter_list(name))
        component = target.get_component_iface()
        require(component is not None, 'ui:gdm-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:gdm-focus-refused')
        self.wait(lambda: self.has_state(self.greeter_list(name), self.api.StateType.FOCUSED),
                  'gdm-account-focus')
        self.input_uncertain = False
        return True

    def greeter_prompt(self, name=PARENT):
        # This observation submits no secret and cannot authorize one.
        require(name in (PARENT, OTHER_PARENT), 'ui:gdm-account-binding')
        if not self.gdm_nonsecret_has_id_route():
            recipient, _field = self.gdm_semantic_prompt()
            require(recipient == name, 'ui:gdm-recipient')
            return
        surface, registered = self.provider_surface(
            'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
        require(surface is not None, 'ui:gdm-surface')
        recipient = self.find_id(registered['selected-recipient'], root=surface)
        require(recipient is not None and ' '.join(recipient.get_name().split()) == name,
                'ui:gdm-recipient')
        self.observe_absence('greeter', 'account', name=name, mode='snapshot')
        field = self.find_id(registered['password'], root=surface)
        require(field is not None and field.get_role_name() == 'password text'
                and self.has_state(field, self.api.StateType.SENSITIVE)
                and self.has_state(field, self.api.StateType.FOCUSED),
                'ui:gdm-password-focus')

    def kiosk_request_form(self, *, enabled=False, expected_selection=None, no_child=False,
                           no_approver=False, duration_seconds=1800, custom_text=None,
                           overlay=False):
        """Read REQUEST03's default-duration station state after accounts load."""
        require(type(enabled) is bool, 'ui:kiosk-enabled-binding')
        require(type(overlay) is bool and (not overlay or (
            enabled and not no_child and not no_approver and (
                expected_selection is None or expected_selection[0] == 'approver'))),
            'ui:overlay-form-binding')
        if overlay:
            self.require_child_overlay_session()
        application_id = CHILD_APPLICATION if overlay else KIOSK_APPLICATION
        require(type(no_child) is bool and (not no_child or (
                not enabled and expected_selection is None)), 'ui:kiosk-profile-binding')
        require(type(no_approver) is bool and (not no_approver or (
                not no_child and not enabled and expected_selection is None)),
                'ui:kiosk-profile-binding')
        require(expected_selection is None or (type(expected_selection) is tuple and len(expected_selection) == 2
                and expected_selection[0] in ('child', 'approver')
                and expected_selection[1] in (CHILD_IDENTITIES if expected_selection[0] == 'child'
                                   else APPROVER_IDENTITIES).values()),
                'ui:kiosk-selected-binding')
        last_reset = None
        diagnostic = KioskDiagnostic()
        self.kiosk_diagnostic = diagnostic
        diagnostic.emit()

        def lookup(identity, nodes, identities, *, showing=True, emit=True):
            if emit:
                diagnostic.emit(identity)
            diagnostic.check()
            matches = [node for node in nodes if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if not matches or (showing and not self.showing(matches[0])):
                return None
            return matches[0]

        def fresh_reader():
            nonlocal last_reset
            now = time.monotonic()
            if self.reset_observer is not None and (last_reset is None or now - last_reset >= 2):
                # Drop only this reader's stale accessibility objects when the
                # graphical session changes. Never start or inspect services.
                diagnostic.emit('reset-reader')
                self.invalidate_observation()
                self.reset_observer()
                last_reset = now

        def observe():
            diagnostic.tree = 'unread'
            diagnostic.ids = {}
            diagnostic.emit('public-tree')
            try:
                snapshot = {}
                public_nodes = list(self.nodes(strict=True, snapshot=snapshot))
                diagnostic.emit('public-ids')
                counts = dict.fromkeys(KIOSK_DIAGNOSTIC_IDS, 0)
                identity_by_node = {}
                for node in public_nodes:
                    diagnostic.check()
                    identity = public_automation_id(node)
                    identity_by_node[node] = identity
                    if identity in counts:
                        counts[identity] += 1
                diagnostic.ids = counts
                diagnostic.tree = 'complete'
            except self.query_errors:
                diagnostic.tree = 'incomplete'
                diagnostic.query_errors += 1
                diagnostic.emit(status='query-error')
                fresh_reader()
                return None
            except UiError:
                diagnostic.tree = 'incomplete'
                raise

            application = lookup(application_id, public_nodes, identity_by_node,
                                 showing=False)
            if application is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None

            requested = (self.application_ids() if callable(self.application_ids)
                         else self.application_ids)
            if requested is not None:
                require(application_id in requested, 'ui:wrong-application-owner')
            if self.owner_pids is not None:
                require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
            if self.application_owners is not None:
                owners = self.application_owners()
                require(application.get_process_id() in owners.get(application_id, ()),
                        'ui:wrong-application-owner')

            application_nodes = self.snapshot_scope(public_nodes, snapshot, application)
            if overlay:
                for identity in ('kiosk-request-window', 'kiosk-request-form'):
                    matches = [node for node in public_nodes
                               if identity_by_node[node] == identity and self.showing(node)]
                    require(len(matches) <= 1 and all(node in application_nodes for node in matches),
                            'ui:overlay-form-count')
            window = lookup('kiosk-request-window', application_nodes, identity_by_node)
            if window is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None
            self.validate_owned_surface(window, application)
            window_nodes = self.snapshot_scope(public_nodes, snapshot, window)
            if lookup('kiosk-language-ready', window_nodes, identity_by_node, emit=False) is None:
                self.complete_request_language_setup()
                # The helper may have entered input. Discard this observation
                # and independently read the usable form on the next pass.
                return None
            form = lookup('kiosk-request-form', window_nodes, identity_by_node)
            if form is None:
                diagnostic.emit(status='missing')
                fresh_reader()
                return None

            # A matching ID in another window must never fill a missing field
            # in this form. Keep a complete fresh read for absence checks too.
            diagnostic.emit('form-tree')
            form_nodes = self.snapshot_scope(public_nodes, snapshot, form)
            diagnostic.emit('form-states')
            require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in form_nodes), 'ui:stale-request-form')
            child = lookup('kiosk-child-selector', form_nodes, identity_by_node)
            approver = lookup('kiosk-approver-selector', form_nodes, identity_by_node)
            request = lookup('kiosk-request-submit', form_nodes, identity_by_node)
            cancel = lookup('kiosk-request-cancel', form_nodes, identity_by_node)
            allow_soft = lookup('kiosk-soft-apps-toggle', form_nodes, identity_by_node)
            if None in (child, approver, request, cancel, allow_soft):
                return None
            if overlay:
                require(not self.has_state(child, self.api.StateType.SENSITIVE),
                        'ui:overlay-child-unlocked')
                require(not any(self.showing(node) and identity_by_node[node].startswith(
                    'kiosk-child-choice-') for node in form_nodes), 'ui:overlay-child-expanded')

            def selected_identity(control, canonical_identities, code):
                namespace = 'child' if canonical_identities == CHILD_IDENTITIES else 'approver'
                diagnostic.emit('selected-' + namespace)
                accounts = CHILD_ACCOUNTS if namespace == 'child' else APPROVER_ACCOUNTS
                control_nodes = self.snapshot_scope(public_nodes, snapshot, control)
                selected_nodes = [node for node in control_nodes
                                  if identity_by_node[node].startswith(
                                      f'kiosk-{namespace}-selected-')
                                  and self.showing(node)]
                require(len(selected_nodes) == 1, 'ui:' + code)
                selected = []
                for name, canonical in canonical_identities.items():
                    if self.fixture_uids is not None:
                        uid = self.fixture_uids.get(name)
                        if uid is None:
                            continue
                    else:
                        try:
                            uid = pwd.getpwnam(accounts[name]).pw_uid
                        except KeyError:
                            continue
                    require(type(uid) is int and uid >= 1000, 'ui:fixture-account-uid')
                    node = lookup(f'kiosk-{namespace}-selected-{uid}',
                                  control_nodes, identity_by_node, emit=False)
                    if node is not None and node == selected_nodes[0]:
                        selected.append((name, canonical))
                require(len(selected) == 1, 'ui:' + code)
                name, canonical = selected[0]
                control.clear_cache_single()
                description = ' '.join(control.get_description().split())
                if description != f'Selected account: {name}.':
                    # The selected label ID and the trigger description are
                    # published separately. Read both again after the update.
                    return None
                return canonical

            duration_ids = (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')
            durations = [
                lookup(f'kiosk-duration-{identity}', form_nodes, identity_by_node)
                for identity in duration_ids
            ]
            if any(button is None for button in durations):
                return None
            diagnostic.emit('duration-states')
            selected = [index for index, button in enumerate(durations)
                        if self.has_state(button, self.api.StateType.PRESSED)]
            wanted = 'custom' if custom_text is not None else duration_seconds
            require(selected == [duration_ids.index(wanted)], 'ui:kiosk-duration-selection')
            if enabled:
                if not all(self.has_state(button, self.api.StateType.SENSITIVE)
                           for button in durations):
                    return None
            else:
                require(not any(self.has_state(button, self.api.StateType.SENSITIVE)
                                for button in durations), 'ui:kiosk-duration-availability')

            notice = lookup('kiosk-screen-limit-notice', form_nodes, identity_by_node)
            if enabled and notice is not None:
                return None
            if not enabled and not no_child and not no_approver and notice is None:
                return None
            diagnostic.emit('message')
            if no_child or no_approver:
                field = 'child' if no_child else 'approver'
                status = lookup('kiosk-request-status', form_nodes, identity_by_node, emit=False)
                if status is None or ' '.join(status.get_name().split()) in (
                        'Loading accounts…', 'Loading request details…'):
                    return None
                expected_message = (
                    'No local standard accounts are available. Create one, then reopen this screen.'
                    if no_child else 'No local interactive administrator accounts are available.')
                require(' '.join(status.get_name().split()) == expected_message,
                        f'ui:kiosk-no-{field}-message')
                # Include hidden choices: an empty selection alone does not
                # prove the form's complete offered child set is empty.
                require(not any(identity_by_node[node].startswith(f'kiosk-{field}-choice-')
                                for node in form_nodes), f'ui:kiosk-no-{field}-choices')
                control_nodes = self.snapshot_scope(public_nodes, snapshot,
                                                    child if no_child else approver)
                selected = [node for node in control_nodes if identity_by_node[node].startswith(
                    f'kiosk-{field}-selected-')]
                require(len(selected) == 1 and identity_by_node[selected[0]] ==
                        f'kiosk-{field}-selected-none' and self.showing(selected[0]),
                        f'ui:kiosk-no-{field}-selection')
            elif not enabled:
                message = ' '.join(notice.get_name().split())
                require(message == 'Screen limit is not enabled in Parent App',
                        'ui:kiosk-disabled-message')
            custom = lookup('kiosk-custom-duration', form_nodes, identity_by_node)
            if custom_text is not None:
                require(custom is not None, 'ui:kiosk-custom-missing')
                text = custom.get_text_iface()
                require(text is not None and self.api.Text.get_character_count(text) == len(custom_text)
                        and self.api.Text.get_text(text, 0, len(custom_text)) == custom_text,
                        'ui:kiosk-custom-value')
            require(lookup('kiosk-mute-button', window_nodes, identity_by_node) is None,
                    'ui:kiosk-mute-present')
            diagnostic.emit('projection')
            projection = {
                'surface': 'child-overlay' if overlay else 'kiosk', 'form_count': 1,
                'child': 'none' if no_child else selected_identity(
                    child, CHILD_IDENTITIES, 'kiosk-child'),
                'approver': 'none' if no_approver else selected_identity(
                    approver, APPROVER_IDENTITIES,
                    'kiosk-approver'),
                'duration_seconds': duration_seconds,
                'custom_text': custom_text if custom_text is not None else (
                    None if custom is None else 'unexpected-visible-value'),
                'allow_soft': self.has_state(allow_soft, self.api.StateType.CHECKED),
                'child_selector_enabled': self.has_state(child, self.api.StateType.SENSITIVE),
                'approver_selector_enabled': self.has_state(approver, self.api.StateType.SENSITIVE),
                'duration_enabled': enabled,
                'soft_choice_enabled': self.has_state(allow_soft, self.api.StateType.SENSITIVE),
                'request_enabled': self.has_state(request, self.api.StateType.SENSITIVE),
                'cancel_enabled': self.has_state(cancel, self.api.StateType.SENSITIVE),
                'message': 'no-child' if no_child else 'no-approver' if no_approver else (
                    '' if enabled else 'screen-limit-disabled'), 'mute': None,
            }
            if projection['child'] is None or projection['approver'] is None:
                return None
            if overlay:
                require(projection['child'] == CHILD_IDENTITIES[CHILD], 'ui:overlay-fixed-child')
            if expected_selection is not None and projection[expected_selection[0]] != expected_selection[1]:
                return None
            return projection
        try:
            result = self.wait(observe, 'kiosk-request-form')
            diagnostic.emit(status='passed')
            return result
        except BaseException:
            diagnostic.emit(status='failed')
            raise
        finally:
            self.kiosk_diagnostic = None

    def require_child_overlay_session(self):
        uid = pwd.getpwnam(CHILD_ACCOUNTS[CHILD]).pw_uid
        require(uid >= 1000 and os.getuid() == uid and os.geteuid() == uid,
                'ui:overlay-account')
        require_active_launch_session()

    def overlay_panel_target(self):
        """DESK12 normal desktop binding; fullscreen reveal is separate."""
        self.require_child_overlay_session()

        def observe():
            value = self.shell_desktop_observation(no_prompt=True)
            if value is None:
                return None
            owner, _, observation = value
            nodes, edges, identities, _facts = observation
            require(sum(identities[node] == 'child-request-button' for node in nodes) <= 1,
                    'ui:ambiguous-automation-id')
            target = self.snapshot_owned_target('child-request-button',
                showing=False, observation=observation)
            if target is None:
                return None
            require(target in self.snapshot_scope(nodes, edges, owner), 'ui:overlay-panel-owner')
            require(self.has_state(target, self.api.StateType.VISIBLE)
                    and self.has_state(target, self.api.StateType.SENSITIVE), 'ui:unusable-target')
            return target

        return self.wait(observe, 'overlay-panel', prompt_in_predicate=True)

    def overlay_panel_launch(self):
        """Qualify the ID-owned keyboard recipient; the worker sends Enter once.

        GNOME Shell 50's StButtonAccessible has no AT-SPI Action interface.
        Use its public Component focus API, never an attempted activation with
        a fallback after uncertain input.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        target = self.overlay_panel_target()
        if not self.has_state(target, self.api.StateType.FOCUSED):
            component = target.get_component_iface()
            require(component is not None, 'ui:overlay-focus-unavailable')
            self.input_uncertain = True
            require(component.grab_focus(), 'ui:overlay-focus-refused')

        def focused():
            refreshed = self.overlay_panel_target()
            require(refreshed == target, 'ui:overlay-stale-focus')
            return self.has_state(refreshed, self.api.StateType.FOCUSED)

        self.wait(focused, 'overlay-panel-focus', prompt_in_predicate=True)
        # This single-use proof releases exactly one worker keyboard input.
        self.input_uncertain = True

    def overlay_desktop(self):
        """Independent complete absence and usable child desktop after Cancel."""
        self.require_child_overlay_session()

        def observe():
            value = self.shell_desktop_observation(no_prompt=True)
            if value is None:
                return None
            nodes, _edges, identities, _facts = value[2]
            return not any(self.showing(node) and identities[node] in (
                'kiosk-request-window', 'kiosk-request-form') for node in nodes)

        self.wait(observe, 'overlay-desktop', prompt_in_predicate=True)

    def request_surface(self, observation, *, overlay=False):
        """Bind shared request IDs to the declared application before input."""
        require(type(overlay) is bool, 'ui:request-surface-binding')
        if overlay:
            self.require_child_overlay_session()
        nodes, _edges, identities, _facts = observation
        application = self.snapshot_matches(CHILD_APPLICATION if overlay else KIOSK_APPLICATION,
            nodes, showing=False, identities=identities)
        require(application is not None, 'ui:kiosk-valid-entry')
        window = self.snapshot_owned_target('kiosk-request-window', root=application,
                                            observation=observation, check_prompt=True)
        require(window is not None, 'ui:kiosk-valid-entry')
        return window

    def kiosk_valid_target(self, identity, *, awaiting_custom=False, child=CHILD, approver=PARENT,
                           overlay=False):
        """Resolve a valid-choice input on the enabled, explicitly selected kiosk child."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(child in (CHILD, EXISTING_CHILD) and approver in (PARENT, OTHER_PARENT),
                'ui:kiosk-valid-binding')
        require(not awaiting_custom or identity == 'kiosk-custom-duration',
                'ui:kiosk-valid-binding')
        observation = self.read_snapshot()
        window = self.request_surface(observation, overlay=overlay)
        form = self.snapshot_owned_target('kiosk-request-form', root=window, observation=observation)
        require(form is not None, 'ui:kiosk-valid-entry')
        for field, name in (('child', child), ('approver', approver)):
            uid = self.fixture_uids[name] if self.fixture_uids is not None else pwd.getpwnam(
                (CHILD_ACCOUNTS if field == 'child' else APPROVER_ACCOUNTS)[name]).pw_uid
            require(self.snapshot_owned_target(f'kiosk-{field}-selected-{uid}', root=form,
                                               observation=observation) is not None,
                    'ui:kiosk-valid-selection')
        if overlay:
            selector = self.snapshot_owned_target('kiosk-child-selector', root=form,
                                                  observation=observation)
            require(child == CHILD and selector is not None
                    and not self.has_state(selector, self.api.StateType.SENSITIVE),
                    'ui:overlay-child-unlocked')
        target = self.snapshot_owned_target(identity, root=form, observation=observation)
        request = self.snapshot_owned_target('kiosk-request-submit', root=form, observation=observation)
        require(request is not None and self.has_state(request, self.api.StateType.SENSITIVE),
                'ui:kiosk-valid-disabled')
        # GTK publishes the newly revealed entry asynchronously after the
        # Custom action. Only this post-input read may wait for its appearance;
        # existing targets and disabled controls still refuse immediately.
        if target is None and awaiting_custom:
            return None
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:kiosk-valid-disabled')
        return target

    def kiosk_valid_choice(self, operation):
        """Finite valid choices, independently read back without submitting a request."""
        try:
            return self._kiosk_valid_choice(operation)
        except BaseException:
            # A missing result after accepted input cannot authorize replay.
            self.input_uncertain = True
            raise

    def _kiosk_valid_choice(self, operation):
        require(not self.input_uncertain, 'ui:uncertain-input')
        overlay = operation in OVERLAY_VALID_OPERATIONS
        require(operation in KIOSK_VALID_OPERATIONS or overlay, 'ui:kiosk-valid-binding')
        action = operation.replace('overlay-', 'kiosk-', 1) if overlay else operation
        if action == 'kiosk-valid-custom-open':
            self._invoke_target(self.kiosk_valid_target('kiosk-duration-custom', overlay=overlay))
            self.invalidate_observation()
            self.wait(lambda: self.kiosk_valid_target('kiosk-custom-duration', awaiting_custom=True,
                                                     overlay=overlay),
                      'kiosk-custom-open')
            return None
        seconds, custom, soft = (OVERLAY_VALID_REQUESTS if overlay else KIOSK_VALID_REQUESTS)[operation]
        if operation in ('overlay-valid-approver-select', 'overlay-flow-approver-select'):
            self.select_kiosk_account('approver', PARENT, expected=(PARENT, OTHER_PARENT),
                duration_seconds=seconds, custom_text=custom, overlay=True)
        elif operation in ('kiosk-flow-child-select', 'kiosk-flow-approver-select'):
            field = operation.split('-')[2]
            self.select_kiosk_account(
                field, CHILD if field == 'child' else PARENT,
                expected=(CHILD, EXISTING_CHILD) if field == 'child' else (PARENT, OTHER_PARENT),
                duration_seconds=seconds, custom_text=custom)
        elif operation.endswith('-select'):
            identity = ('kiosk-soft-apps-toggle' if action in (
                'kiosk-valid-soft-select', 'kiosk-valid-excluded-select',
                'kiosk-valid-fraction-soft-select', 'kiosk-valid-fraction-excluded-select')
                else f'kiosk-duration-{seconds}')
            target = self.kiosk_valid_target(identity, overlay=overlay)
            if identity == 'kiosk-soft-apps-toggle':
                root = self.snapshot_owned_target('kiosk-request-form', check_prompt=True)
                self.set_toggle(identity, soft, root=root)
            else:
                self._invoke_target(target)
                self.invalidate_observation()
        request = self.kiosk_request_form(enabled=True,
            expected_selection=('approver', 'fixture-parent') if overlay else ('child', 'fixture-child'),
            duration_seconds=seconds, custom_text=custom, overlay=overlay)
        require(request['approver'] == 'fixture-parent' and request['allow_soft'] is soft,
                'ui:kiosk-valid-choice')
        def estimate():
            node = self.snapshot_owned_target('kiosk-request-status', check_prompt=True)
            require(node is not None, 'ui:kiosk-estimate-missing')
            message = ' '.join(node.get_name().split())
            if message == 'Calculating time estimate…':
                return None
            if seconds == 0:
                require(message == 'If approved, access until midnight.', 'ui:kiosk-rest-estimate')
                return {'kind': 'midnight'}
            prefix = 'Estimated time remaining if approved: '
            require(message.startswith(prefix), 'ui:kiosk-estimate:request-denied'
                    if message == 'Request denied' else 'ui:kiosk-estimate')
            return {'kind': 'fixed', **duration_projection(message.removeprefix(prefix))}
        value = self.wait(estimate, 'kiosk-estimate')
        return {'request': request, 'estimate': value, 'observed_monotonic_ns': time.monotonic_ns()}

    def mate_agent_pid(self):
        """Bind AT-SPI to the kiosk session's maintained agent service."""
        value = subprocess.check_output([
            '/usr/bin/systemctl', '--user', 'show', '--property=MainPID', '--value',
            'oh-no-parent-control-polkit-agent.service'], text=True, timeout=5).strip()
        require(re.fullmatch(r'[1-9][0-9]*', value) is not None, 'ui:mate-service-owner')
        pid = int(value)
        require(Path('/proc/' + value).stat().st_uid == os.getuid(), 'ui:mate-service-owner')
        return pid

    def mate_prompt(self, pid, *, observation=None, challenge=None, filled=False,
                    binding=None):
        """MATE-only semantic adapter; never reads password contents or types.

        English PAM recipient label and displayed policy message are public
        meaning checks inside the sole service-owned authentication dialog.
        Missing context refuses; the form/broker cannot supply it instead.
        """
        require(binding is None or binding in MULTIPLE_MATE_BINDINGS, 'ui:mate-binding')
        child, approver = MULTIPLE_MATE_BINDINGS[binding] if binding else (CHILD, PARENT)
        if observation is None:
            self.invalidate_observation()
            observation = self.read_snapshot(protect_text=True)
        nodes, snapshot, _identities, facts = observation
        kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
        require(kind in (None, 'mate-polkit'), 'ui:mate-wrong-agent')
        if kind is None:
            require(challenge is None, 'ui:mate-replacement')
            return None
        owners = [node for node in nodes if facts[node]['role'] == 'application'
                  and self._prompt_application_kind(facts[node]['name']) == 'mate-polkit']
        require(len(owners) == 1 and owners[0].get_process_id() == pid, 'ui:mate-owner')
        owner = owners[0]
        scoped = self.snapshot_scope(nodes, snapshot, owner)
        dialogs = [node for node in scoped if facts[node]['showing']
                   and facts[node]['role'] in ('dialog', 'alert')]
        require(len(dialogs) == 1, 'ui:mate-dialog')
        dialog = dialogs[0]
        controls = self.snapshot_scope(nodes, snapshot, dialog)
        require(all(not self.has_state(node, self.api.StateType.DEFUNCT)
                    and node.get_process_id() == pid for node in (owner, *controls)),
                'ui:mate-owner')
        fields = [node for node in controls if facts[node]['role'] == 'password text']
        require(len(fields) == 1, 'ui:mate-field-ambiguous')
        field = fields[0]
        proof = self.mate_field_proof(field, facts)
        if filled:
            require(type(proof['length']) is int and 1 <= proof['length'] <= 256,
                    'ui:mate-field-empty')
            proof = {**proof, 'length': 0}
        self.validate_mate_field(proof)
        labels = [facts[node]['name'] for node in controls
                  if facts[node]['role'] == 'label' and facts[node]['showing']]
        require(labels.count('Password for ' + APPROVER_ACCOUNTS[approver] + ':') == 1,
                'ui:mate-recipient-context-missing')
        message = (f'Grant {child} 30 minutes?' if binding else
                   f'Grant {CHILD} 1 minute, 15 seconds and allow soft blocked apps?')
        require(labels.count(message) == 1, 'ui:mate-request-context-missing')
        buttons = [node for node in controls if facts[node]['role'] in ('push button', 'button')
                   and facts[node]['showing'] and facts[node]['name'] == 'Cancel']
        require(len(buttons) == 1 and self.has_state(buttons[0], self.api.StateType.SENSITIVE),
                'ui:mate-cancel')
        current = (owner, dialog, field, buttons[0])
        require(challenge is None or current == challenge, 'ui:mate-replacement')
        return current

    def mate_challenge_identity(self, pid, challenge):
        """Opaque public object identity, bound to this boot, session and process."""
        import hashlib
        payload = [Path('/proc/sys/kernel/random/boot_id').read_text(), os.getuid(), pid,
                   Path('/proc/' + str(pid) + '/stat').read_text().rsplit(')', 1)[1].split()[19],
                   [(node.bus, node.path) for node in challenge]]
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()

    def kiosk_approval_success(self, *, immediate=False):
        """REQUEST11: explicit owned success, never prompt disappearance alone."""
        def success():
            self.invalidate_observation()
            window = self.snapshot_owned_target('kiosk-request-window', check_prompt=False)
            if window is None:
                return False
            title = self.find_id('kiosk-result-title', root=window)
            page = self.find_id('kiosk-result-page', root=window)
            if title is None or page is None or not self.showing(title) or not self.showing(page):
                return False
            require(title.get_name() == 'Request approved', 'ui:kiosk-approval-result')
            require(self.system_prompt_kind() is None, 'ui:kiosk-approval-prompt')
            if immediate:
                action = self.find_id('kiosk-result-action', root=page)
                require(action is not None and self.has_state(action, self.api.StateType.VISIBLE)
                        and self.has_state(action, self.api.StateType.SENSITIVE),
                        'ui:kiosk-immediate-action')
                return action
            return True
        action = self.wait(success, 'kiosk-approval-success', prompt_in_predicate=True)
        if immediate:
            self._invoke_target(action)
        return {'approved': True, 'form_success': True, **({'immediate_exit': True} if immediate else {})}

    def kiosk_mate_approval(self, operation):
        require(not self.input_uncertain, 'ui:uncertain-input')
        pid = self.mate_agent_pid()
        opening = operation in ('kiosk-mate-open', 'kiosk-mate-rejection-open')
        submitting = operation in ('kiosk-mate-submit-success', 'kiosk-mate-submit-rejection',
                                   'kiosk-mate-submit-immediate')
        try:
            if opening:
                self.kiosk_valid_choice('kiosk-valid-fraction-soft-read')
                require(self.mate_prompt(pid) is None, 'ui:mate-already-open')
                self._invoke_target(self.kiosk_valid_target('kiosk-request-submit'))
                challenge = self.wait(lambda: self.mate_prompt(pid), 'mate-prompt',
                                      prompt_in_predicate=True)
            else:
                challenge = self.mate_prompt(pid, filled=submitting)
                require(challenge is not None, 'ui:mate-missing')
            identity = self.mate_challenge_identity(pid, challenge)
            if not opening:
                require(identity == self.expected_mate_challenge, 'ui:mate-replacement')
            if submitting:
                # Resolve the provider button from the same fresh scoped tree;
                # submit once, then read the brief product result in this process.
                nodes, snapshot, _, facts = self.read_snapshot(protect_text=True)
                current = self.mate_prompt(pid, observation=(nodes, snapshot, _, facts),
                                           challenge=challenge, filled=True)
                buttons = [node for node in self.snapshot_scope(nodes, snapshot, current[1])
                           if facts[node]['role'] in ('button', 'push button')
                           and facts[node]['name'] == 'Authenticate' and facts[node]['showing']]
                require(len(buttons) == 1 and self.has_state(buttons[0], self.api.StateType.SENSITIVE),
                        'ui:mate-submit')
                self._invoke_target(buttons[0])
                if operation == 'kiosk-mate-submit-rejection':
                    result = self.kiosk_mate_rejected(pid, challenge)
                    self.input_uncertain = True
                    return result
                result = self.kiosk_approval_success(immediate=operation == 'kiosk-mate-submit-immediate')
                self.input_uncertain = True  # This one submission is consumed even on success.
                return result
            return {'challenge_id': identity}
        except BaseException:
            self.input_uncertain = True
            raise

    def kiosk_mate_rejected(self, pid, challenge):
        """Observe explicit provider rejection, then Cancel once; never resubmit.

        MATE's public info label is scoped to the original service-owned dialog.
        A disappearing prompt, success page or timeout cannot establish rejection.
        """
        def rejected():
            self.invalidate_observation()
            observation = self.read_snapshot(protect_text=True)
            nodes, snapshot, _, facts = observation
            require(self.system_prompt_kind(observation=(nodes, snapshot, facts)) == 'mate-polkit',
                    'ui:mate-rejection-prompt-missing')
            owner, dialog, field, cancel = challenge
            require(owner in nodes and dialog in nodes and owner.get_process_id() == pid,
                    'ui:mate-replacement')
            labels = [facts[node]['name'] for node in self.snapshot_scope(nodes, snapshot, dialog)
                      if facts[node]['role'] == 'label' and facts[node]['showing']]
            message = 'Your authentication attempt was unsuccessful. Please try again.'
            if message not in labels:
                return False
            require(labels.count(message) == 1, 'ui:mate-rejection-ambiguous')
            # The retry field must be empty, focused and on the same challenge.
            # MATE 1.26 hides the password grid after submission and publishes
            # rejection before starting the next PAM prompt (including an
            # event-dispatching error animation). The label alone therefore
            # does not mean the retry field is ready. Retry only observation,
            # within wait's original deadline; never submit again or accept
            # rejection until the complete unchanged prompt proof succeeds.
            try:
                return self.mate_prompt(pid, observation=observation, challenge=challenge)
            except UiError as error:
                if str(error) != 'ui:mate-field-state':
                    raise
                return False
        current = self.wait(rejected, 'mate-rejection', prompt_in_predicate=True)
        require(self.mate_agent_pid() == pid, 'ui:mate-owner')
        current = self.mate_prompt(pid, challenge=current)
        self._invoke_target(current[3])
        def absent():
            self.invalidate_observation()
            observation = self.read_snapshot(protect_text=True)
            nodes, snapshot, _, facts = observation
            if self.system_prompt_kind(observation=(nodes, snapshot, facts)) is None:
                return True
            self.mate_prompt(pid, observation=observation, challenge=challenge)
            return False
        self.wait(absent, 'mate-dismissed', prompt_in_predicate=True)
        self.kiosk_valid_choice('kiosk-valid-fraction-soft-read')
        return {'rejected': True, 'cancelled': True, 'no_error': True}

    def mate_field_proof(self, field, facts):
        """Read public field state and length only, never password contents."""
        interface = field.get_text_iface()
        return {'showing': facts[field]['showing'],
                'sensitive': self.has_state(field, self.api.StateType.SENSITIVE),
                'focused': self.has_state(field, self.api.StateType.FOCUSED),
                'stale': self.has_state(field, self.api.StateType.DEFUNCT),
                'length': None if interface is None else self.api.Text.get_character_count(interface)}

    @staticmethod
    def validate_mate_field(proof):
        require(not proof['stale'], 'ui:mate-owner')
        require(all(proof[key] for key in ('showing', 'sensitive', 'focused')),
                'ui:mate-field-state')
        require(type(proof['length']) is int and proof['length'] == 0,
                'ui:mate-field-not-empty')

    def mate_provider_metadata(self, pid):
        from gi.repository import Gio
        environment = dict(item.split(b'=', 1) for item in
                           Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                           if b'=' in item)
        locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
                  or environment.get(b'LANG') or b'C').decode('ascii')
        version = subprocess.check_output(
            ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', 'mate-polkit'],
            text=True, timeout=5).strip()
        sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
        # GNOME Kiosk uses locale1 when the account has no configured sources.
        # https://github.com/GNOME/gnome-kiosk#keyboard-layout-switching
        # Keep the tuple nonempty and validated; do not invent a default layout.
        if sources == []:
            sources = greeter_keyboard_sources()
        return validate_shell_metadata({'version': version, 'locale': locale,
                                        'keyboard': [list(source) for source in sources]})

    def mate_prompt_refusals(self, pid, challenge):
        """Exercise refusal on projections of a fresh real tree; no test input."""
        self.invalidate_observation()
        observation = self.read_snapshot(protect_text=True)
        self.mate_prompt(pid, observation=observation, challenge=challenge)
        nodes, snapshot, identities, facts = observation
        owner, dialog, field, cancel = challenge
        variants = []
        wrong_agent = {node: dict(value) for node, value in facts.items()}
        wrong_agent[owner]['name'] = 'gnome-shell'
        variants.append((pid, (nodes, snapshot, identities, wrong_agent), challenge,
                         'ui:mate-wrong-agent'))
        variants.append((pid + 1, observation, challenge, 'ui:mate-owner'))
        labels = [node for node in self.snapshot_scope(nodes, snapshot, dialog)
                  if facts[node]['role'] == 'label' and facts[node]['showing']]
        recipient = next(node for node in labels
                         if facts[node]['name'] == 'Password for ' + APPROVER_ACCOUNTS[PARENT] + ':')
        message = next(node for node in labels if facts[node]['name'].startswith('Grant '))
        for node, value, code in (
                (recipient, 'Password for wrong-parent:', 'ui:mate-recipient-context-missing'),
                (message, 'Grant wrong-child 1 minute, 15 seconds and allow soft blocked apps?',
                 'ui:mate-request-context-missing'),
                (message, f'Grant {CHILD} 5 minutes and allow soft blocked apps?',
                 'ui:mate-request-context-missing'),
                (message, f'Grant {CHILD} 1 minute, 15 seconds?',
                 'ui:mate-request-context-missing')):
            projected = {key: dict(value) for key, value in facts.items()}
            projected[node]['name'] = value
            variants.append((pid, (nodes, snapshot, identities, projected), challenge, code))
        ambiguous = {node: dict(value) for node, value in facts.items()}
        ambiguous[cancel]['role'] = 'password text'
        variants.append((pid, (nodes, snapshot, identities, ambiguous), challenge,
                         'ui:mate-field-ambiguous'))
        variants.append((pid, observation, (owner, dialog, cancel, field), 'ui:mate-replacement'))
        for expected_pid, tree, expected_challenge, code in variants:
            try:
                self.mate_prompt(expected_pid, observation=tree, challenge=expected_challenge)
            except UiError as error:
                require(str(error) == code, 'ui:mate-refusal-mismatch')
            else:
                raise UiError('ui:mate-refusal-accepted')
        proof = self.mate_field_proof(field, facts)
        for key, value, code in (
                ('showing', False, 'ui:mate-field-state'),
                ('sensitive', False, 'ui:mate-field-state'),
                ('focused', False, 'ui:mate-field-state'),
                ('length', 1, 'ui:mate-field-not-empty'),
                ('stale', True, 'ui:mate-owner')):
            try:
                self.validate_mate_field({**proof, key: value})
            except UiError as error:
                require(str(error) == code, 'ui:mate-refusal-mismatch')
            else:
                raise UiError('ui:mate-refusal-accepted')
        return list(MATE_REFUSALS)

    def kiosk_mate_cancel(self, *, refusals=False, binding=None):
        """One owned Request, guarded Cancel, complete absence and form readback."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(binding is None or binding in MULTIPLE_MATE_BINDINGS and not refusals,
                'ui:mate-binding')
        child, approver = MULTIPLE_MATE_BINDINGS[binding] if binding else (CHILD, PARENT)

        def form():
            if binding is None:
                return self.kiosk_valid_choice('kiosk-valid-fraction-soft-read')['request']
            value = self.kiosk_request_form(enabled=True,
                expected_selection=('child', CHILD_IDENTITIES[child]))
            require(value['approver'] == APPROVER_IDENTITIES[approver]
                    and value['allow_soft'] is False, 'ui:mate-form-binding')
            status = self.snapshot_owned_target('kiosk-request-status', check_prompt=True)
            require(status is not None and ' '.join(status.get_name().split()).startswith(
                'Estimated time remaining if approved: '), 'ui:mate-form-estimate')
            return value

        def prompt(**kwargs):
            return self.mate_prompt(pid, **kwargs, **({'binding': binding} if binding else {}))

        before = form()
        pid = self.mate_agent_pid()
        require(prompt() is None, 'ui:mate-already-open')
        challenge_id = os.urandom(32).hex()
        try:
            self._invoke_target(self.kiosk_valid_target('kiosk-request-submit', child=child, approver=approver))
            self.invalidate_observation()
            challenge = self.wait(lambda: prompt(), 'mate-prompt',
                                  prompt_in_predicate=True)
            provider = self.mate_provider_metadata(pid)
            rejected = self.mate_prompt_refusals(pid, challenge) if refusals else []
            require(self.mate_agent_pid() == pid, 'ui:mate-owner')
            current = prompt(challenge=challenge)
            self._invoke_target(current[3])
            self.invalidate_observation()
            def absent():
                self.invalidate_observation()
                observation = self.read_snapshot(protect_text=True)
                nodes, snapshot, _identities, facts = observation
                kind = self.system_prompt_kind(observation=(nodes, snapshot, facts))
                if kind is None:
                    return True
                prompt(observation=observation, challenge=challenge)
                return False
            self.wait(absent, 'mate-dismissed', prompt_in_predicate=True)
            after = form()
            require(after == before, 'ui:mate-form-changed')
            return {'provider': provider, 'child': CHILD_IDENTITIES[child],
                    'approver': APPROVER_IDENTITIES[approver],
                    'duration_seconds': 1800 if binding else 75,
                    'allow_soft': binding is None, 'cancelled': True,
                    'unchanged_form': True, 'no_error': True, 'refusals': refusals,
                    'rejected_proofs': rejected, 'challenge_id': challenge_id,
                    'same_challenge_rechecked': True}
        except BaseException:
            self.input_uncertain = True
            raise

    def kiosk_invalid_choice(self, operation):
        """Submit one finite invalid value; never authenticate or replay input."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(operation in INVALID_REQUEST_OPERATIONS, 'ui:kiosk-invalid-binding')
        binding, action = INVALID_REQUEST_OPERATIONS[operation]
        overlay = operation in OVERLAY_INVALID_OPERATIONS

        def read_form():
            self.kiosk_valid_target('kiosk-custom-duration', overlay=overlay)
            request = self.kiosk_request_form(
                enabled=True, expected_selection=('approver', 'fixture-parent') if overlay
                    else ('child', 'fixture-child'),
                duration_seconds=None, custom_text=KIOSK_INVALID_VALUES[binding], overlay=overlay)
            require(request['approver'] == 'fixture-parent' and not request['allow_soft']
                    and request['child_selector_enabled'] is (not overlay)
                    and all(request[key] for key in (
                        'approver_selector_enabled', 'duration_enabled',
                        'soft_choice_enabled', 'request_enabled', 'cancel_enabled')),
                    'ui:kiosk-invalid-form')
            return request

        try:
            before = read_form()
            if action == 'submit':
                self._invoke_target(self.kiosk_valid_target('kiosk-request-submit', overlay=overlay))
                self.invalidate_observation()
            if action != 'ready':
                def validation():
                    root = self.snapshot_owned_target('kiosk-request-form', check_prompt=True)
                    require(root is not None, 'ui:kiosk-invalid-form')
                    status = self.snapshot_owned_target('kiosk-request-status', root=root,
                                                        check_prompt=True)
                    require(status is not None, 'ui:kiosk-validation-missing')
                    return status.get_name() == 'Enter a number from 0.1 to 1440 minutes.'
                self.wait(validation, 'kiosk-invalid-validation')
                require(read_form() == before, 'ui:kiosk-invalid-preserved')
            return {'request': before, 'validation': action != 'ready', 'no_authentication': True}
        except BaseException:
            self.input_uncertain = True
            raise

    def kiosk_approver_baseline(self):
        """Prove at least one parent is listed, without using a disabled selector.

        GTK omits collapsed options from AT-SPI. The showing selected parent
        proves the nonempty starting state; OS fixture setup discovers all
        eligible accounts before locking. Its UID binds that setup to this form.
        """
        def observe():
            selector, _form, observation = self.kiosk_account_snapshot(
                'approver', require_enabled=False)
            nodes, snapshot, identities, _facts = observation
            selected = [node for node in self.snapshot_scope(nodes, snapshot, selector)
                        if identities[node].startswith('kiosk-approver-selected-')]
            require(len(selected) == 1, 'ui:kiosk-approver-selection')
            if identities[selected[0]] == 'kiosk-approver-selected-none':
                return None
            match = re.fullmatch(r'kiosk-approver-selected-([1-9][0-9]*)',
                                 identities[selected[0]])
            require(self.showing(selected[0]) and match is not None,
                    'ui:kiosk-approver-selection')
            uid = int(match[1])
            require(1000 <= uid <= (1 << 32) - 1, 'ui:kiosk-approver-identity')
            return [uid]

        return self.wait(observe, 'kiosk-approver-baseline', prompt_in_predicate=True)

    def kiosk_account_snapshot(self, field, *, require_enabled=True, overlay=False):
        """One complete owned snapshot for a station account input boundary."""
        require(field in ('child', 'approver'), 'ui:kiosk-account-field')
        require(not overlay or field == 'approver', 'ui:overlay-child-selection')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(strict=True, snapshot=snapshot, facts=facts))
        identities = {node: facts[node]['identity'] for node in nodes}
        require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in nodes), 'ui:stale-request-form')
        observation = (nodes, snapshot, identities, facts)
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        try:
            window = self.request_surface(observation, overlay=overlay)
        except UiError as error:
            if str(error) == 'ui:kiosk-valid-entry':
                raise UiError('ui:kiosk-account-surface') from error
            raise
        form = self.snapshot_owned_target(
            'kiosk-request-form', root=window, observation=observation)
        require(form is not None, 'ui:kiosk-account-surface')
        selector = self.snapshot_owned_target(
            f'kiosk-{field}-selector', root=form, showing=False, observation=observation)
        require(selector is not None and self.has_state(selector, self.api.StateType.VISIBLE)
                and (not require_enabled or self.has_state(selector, self.api.StateType.SENSITIVE)),
                'ui:kiosk-account-unavailable')
        return selector, form, observation

    def select_kiosk_account(self, field, name, *, expected, enabled=True, inspect_only=False,
                             duration_seconds=1800, custom_text=None, overlay=False):
        """UI15: inspect the exact offered set, optionally select and read back."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(type(enabled) is bool, 'ui:kiosk-enabled-binding')
        require(type(inspect_only) is bool, 'ui:kiosk-inspection-binding')
        require(field in ('child', 'approver'), 'ui:kiosk-account-field')
        accounts = CHILD_ACCOUNTS if field == 'child' else APPROVER_ACCOUNTS
        require(type(expected) is tuple and len(expected) == len(set(expected))
                and set(expected) <= set(accounts) and name in expected,
                'ui:kiosk-account-choice')
        bindings = {}
        for label in expected:
            uid = (self.fixture_uids.get(label) if self.fixture_uids is not None
                   else pwd.getpwnam(accounts[label]).pw_uid)
            require(type(uid) is int and uid >= 1000, 'ui:fixture-account-uid')
            identity = f'kiosk-{field}-choice-{uid}'
            require(identity not in bindings, 'ui:duplicate-choice-identity')
            bindings[identity] = label
        selector, form, observation = self.kiosk_account_snapshot(field, overlay=overlay)
        if inspect_only:
            require(self.snapshot_owned_target(
                f'kiosk-{field}-choices', root=form, observation=observation) is None,
                'ui:kiosk-choices-already-open')
        self._invoke_target(selector)
        if inspect_only:
            self.input_uncertain = True
        self.invalidate_observation()

        def offered():
            _selector, form, observation = self.kiosk_account_snapshot(field, overlay=overlay)
            nodes, snapshot, identities, _facts = observation
            choices = self.snapshot_owned_target(
                f'kiosk-{field}-choices', root=form, observation=observation)
            if choices is None:
                return None
            scope = self.snapshot_scope(nodes, snapshot, choices)
            found = {}
            for node in scope:
                identity = identities[node]
                if not identity.startswith(f'kiosk-{field}-choice-'):
                    continue
                require(identity in bindings and identity not in found,
                        'ui:kiosk-eligible-set')
                require(self.has_state(node, self.api.StateType.VISIBLE)
                        and self.has_state(node, self.api.StateType.SENSITIVE),
                        'ui:kiosk-account-unavailable')
                label = 'Child account' if field == 'child' else 'Approving parent'
                require(' '.join(node.get_name().split()) == f'{label}: {bindings[identity]}',
                        'ui:kiosk-choice-label')
                found[identity] = node
            require(set(found) == set(bindings), 'ui:kiosk-eligible-set')
            if inspect_only:
                return True
            return next(found[identity] for identity in found if bindings[identity] == name)

        target = self.wait(offered, 'kiosk-offered-accounts', prompt_in_predicate=True)
        if inspect_only:
            self.input_uncertain = False
            return None
        self._invoke_target(target)
        self.input_uncertain = True
        self.invalidate_observation()
        canonical = CHILD_IDENTITIES if field == 'child' else APPROVER_IDENTITIES
        result = self.kiosk_request_form(enabled=enabled, expected_selection=(field, canonical[name]),
                                         duration_seconds=duration_seconds, custom_text=custom_text,
                                         overlay=overlay)
        self.input_uncertain = False
        return result

    def collapse_kiosk_child_choices(self, field='child', *, enabled=False):
        """Collapse the inline list once and independently read the whole form."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        # GatewayDropDown is an inline list, not a popup. Its public trigger
        # collapses it; Escape is the whole form's Cancel action.
        require(field in ('child', 'approver'), 'ui:kiosk-account-field')
        selector, form, observation = self.kiosk_account_snapshot(field)
        require(self.snapshot_owned_target(
            f'kiosk-{field}-choices', root=form, observation=observation) is not None,
            'ui:kiosk-choices-not-open')
        self._invoke_target(selector)
        self.input_uncertain = True
        self.invalidate_observation()

        def closed():
            _selector, form, observation = self.kiosk_account_snapshot(field)
            return self.snapshot_owned_target(
                f'kiosk-{field}-choices', root=form, observation=observation) is None

        self.wait(closed, 'kiosk-choices-closed', prompt_in_predicate=True)
        result = self.kiosk_request_form(enabled=enabled)
        self.input_uncertain = False
        return result

    def kiosk_exit_target(self, *, with_window=False, overlay=False):
        """Resolve the fresh owned Cancel control inside one showing form."""
        snapshot = {}
        facts = {}
        nodes = list(self.nodes(strict=True, snapshot=snapshot, facts=facts))
        require(nodes and not self.has_state(nodes[0], self.api.StateType.DEFUNCT),
                'ui:stale-request-form')
        identities = {node: facts[node]['identity'] for node in nodes}
        self.handle_system_prompt(observation=(nodes, snapshot, facts))

        def lookup(identity, scope, *, showing=True):
            matches = [node for node in scope if identities[node] == identity]
            require(len(matches) <= 1, 'ui:ambiguous-automation-id')
            if not matches or (showing and not self.showing(matches[0])):
                return None
            return matches[0]

        # Resolve this observation from its complete scoped snapshot. Generic
        # find_id re-traverses ownership trees even when supplied these nodes.
        if overlay:
            self.require_child_overlay_session()
        application_id = CHILD_APPLICATION if overlay else KIOSK_APPLICATION
        application = lookup(application_id, nodes, showing=False)
        require(application is not None, 'ui:kiosk-application')
        requested = (self.application_ids() if callable(self.application_ids)
                     else self.application_ids)
        if requested is not None:
            require(application_id in requested, 'ui:wrong-application-owner')
        if self.owner_pids is not None:
            require(application.get_process_id() in self.owner_pids(), 'ui:wrong-owner')
        if self.application_owners is not None:
            owners = self.application_owners()
            require(application.get_process_id() in owners.get(application_id, ()),
                    'ui:wrong-application-owner')
        application_nodes = self.snapshot_scope(nodes, snapshot, application)
        # A readable stale object in another desktop application is not this
        # request form. Keep the complete desktop prompt check above, and
        # refuse stale objects anywhere in the verified owning application.
        require(not any(self.has_state(node, self.api.StateType.DEFUNCT)
                        for node in application_nodes), 'ui:stale-request-form')
        window = lookup('kiosk-request-window', application_nodes)
        require(window is not None, 'ui:kiosk-request-window')
        self.validate_owned_surface(
            window, application, nodes=nodes, snapshot=snapshot, identities=identities,
        )
        window_nodes = self.snapshot_scope(nodes, snapshot, window)
        form = lookup('kiosk-request-form', window_nodes)
        require(form is not None, 'ui:kiosk-request-form')
        form_nodes = self.snapshot_scope(nodes, snapshot, form)
        target = lookup('kiosk-request-cancel', form_nodes)
        require(target is not None and self.has_state(target, self.api.StateType.SENSITIVE),
                'ui:kiosk-request-cancel')
        return (window, target) if with_window else target

    def cancel_kiosk_request(self, *, overlay=False):
        """UI04: activate Cancel once after refusing any system prompt."""
        # The station's scoped public action is explicitly authorized even
        # when its Cancel control is clipped by the scroll viewport.
        target = self.kiosk_exit_target(overlay=overlay)
        self._invoke_target(target)

    def kiosk_restrictions(self, *, stable_seconds=2, prepared=False):
        """Complete public station-tree exclusion, anchored by owned form IDs.

        No provider targets or names are inferred: any showing content outside
        the station application refuses, including a Shell search or terminal.
        Inspect offered control IDs within the recognized product window; do
        not type a query or open supporting applications to test their absence.
        """
        require(type(stable_seconds) in (int, float) and 0 <= stable_seconds <= 2,
                'ui:restriction-interval')
        require(type(prepared) is bool, 'ui:restriction-form-binding')
        started = None

        def inspect():
            nonlocal started
            observation = self.read_snapshot()
            nodes, edges, identities, facts = observation
            require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                      for node in nodes), 'ui:restriction-stale-tree')
            window = self.snapshot_owned_target('kiosk-request-window',
                                                observation=observation, check_prompt=True)
            require(window is not None, 'ui:restriction-window')
            self.snapshot_matches('kiosk-request-form', nodes, identities=identities)
            form = self.snapshot_owned_target('kiosk-request-form', root=window,
                                              observation=observation)
            require(form is not None, 'ui:restriction-form')
            application = self.snapshot_matches(KIOSK_APPLICATION, nodes, identities=identities)
            scope = set(self.snapshot_scope(nodes, edges, application))
            # Registry/application roots do not themselves constitute a window.
            # Every descendant outside the owned app must be non-showing.
            roots = {nodes[0], *edges[nodes[0]]} if nodes[0] != application else {application}
            require(not any(facts[node]['showing'] for node in nodes
                            if node not in scope and node not in roots),
                    'ui:station-forbidden-surface')
            allowed = {
                'kiosk-child-selector', 'kiosk-approver-selector',
                'kiosk-soft-apps-row', 'kiosk-soft-apps-toggle',
                'kiosk-request-submit', 'kiosk-request-cancel', 'kiosk-menu-button',
                'kiosk-menu-item-about', 'kiosk-custom-duration',
                'kiosk-request-scrollbar',
                *('kiosk-duration-' + str(value) for value in
                  (300, 900, 1800, 3600, 7200, 14400, 0, 'custom')),
            }
            controls = {'push button', 'button', 'toggle button', 'check box',
                        'radio button', 'combo box', 'entry', 'text', 'menu item'}
            # GtkMenuButton exposes an anonymous implementation toggle below
            # its public ID (also recognized by the owned-control audit). It
            # is part of this allowed menu, not another offered product action.
            # Never target it, accept a named unknown control, or exempt the
            # whole menu subtree from the restriction check.
            menu = self.snapshot_owned_target('kiosk-menu-button', root=window,
                                              observation=observation)
            menu_toggles = set() if menu is None else {
                node for node in edges[menu]
                if not identities[node] and facts[node]['role'] == 'toggle button'
            }
            require(len(menu_toggles) <= 1, 'ui:station-forbidden-control')
            for node in self.snapshot_scope(nodes, edges, window):
                if facts[node]['showing'] and facts[node]['role'] in controls:
                    require(identities[node] in allowed or node in menu_toggles,
                            'ui:station-forbidden-control')
            if started is None:
                started = time.monotonic()
            return time.monotonic() - started >= stable_seconds

        def stable():
            nonlocal started
            try:
                return inspect()
            except self.query_errors:
                started = None
                raise

        self.wait(stable, 'station-restrictions', prompt_in_predicate=True)
        # One final independent form read keeps diagnostic output bounded.
        # The caller declares initial versus FLOW04-prepared state. Never
        # infer an expectation from whichever duration the UI currently shows.
        self.invalidate_observation()
        if prepared:
            self.kiosk_valid_choice('kiosk-valid-fraction-soft-read')
        else:
            self.kiosk_request_form()
        return True

    def focus_kiosk_escape_recipient(self, *, overlay=False):
        """UI05: focus and freshly recheck the owned recipient before Escape."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        window, target = self.kiosk_exit_target(with_window=True, overlay=overlay)
        identity = public_automation_id(target)
        require(self.has_state(window, self.api.StateType.SENSITIVE), 'ui:unusable-target')
        action = window.get_action_iface()
        require(action is not None, 'ui:missing-action')
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',
                message=r'^Atspi\.Action\.get_action_name is deprecated$',
                category=DeprecationWarning)
            matches = [index for index in range(self.api.Action.get_n_actions(action))
                       if self.api.Action.get_action_name(action, index) == 'focus.' + identity]
        require(len(matches) == 1, 'ui:missing-or-ambiguous-action')
        self.input_uncertain = True
        require(self.api.Action.do_action(action, matches[0]), 'ui:action-refused')

        def focused():
            current = self.kiosk_exit_target(overlay=overlay)
            require(current == target, 'ui:kiosk-exit-stale-focus')
            return self.has_state(current, self.api.StateType.FOCUSED)

        # kiosk_exit_target checks prompts in every fresh predicate snapshot.
        self.wait(focused, 'kiosk-exit-focus', prompt_in_predicate=True)
        self.input_uncertain = False

    def password_recipient(self, name):
        """Read only public identity, masked role, focus and empty length.

        Never read password text or children. A false/stale observation cannot
        authorize typing. The caller also requires a separate fresh recheck.
        """
        require(name in GREETER_IDENTITIES, 'ui:gdm-account-binding')
        if not self.gdm_nonsecret_has_id_route():
            require(name in (PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD),
                    'ui:gdm-nonsecret-binding')
            recipient, field = self.gdm_semantic_prompt()
            if recipient != name:
                return False
            interface = field.get_text_iface()
            return (interface is not None
                    and self.api.Text.get_character_count(interface) == 0)
        surface, registered = self.provider_surface(
            'gdm', 'greeter', GDM_PROVIDER_CONTROLS)
        if surface is None:
            return False
        recipient = self.find_id(registered['selected-recipient'], root=surface)
        field = self.find_id(registered['password'], root=surface)
        account_list = self.find_id(registered['account-list'], root=surface, showing=False)
        if (recipient is None or ' '.join(recipient.get_name().split()) != name
                or field is None or field.get_role_name() != 'password text'
                or not self.has_state(field, self.api.StateType.SENSITIVE)
                or not self.has_state(field, self.api.StateType.FOCUSED)
                or (account_list is not None and self.showing(account_list))):
            return False
        interface = field.get_text_iface()
        return interface is not None and self.api.Text.get_character_count(interface) == 0

    def search_query(self, expected):
        """Read only the overview's public search field; never arbitrary text."""
        require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal', NATIVE_PRODUCT), 'ui:search-binding')
        if not self.provider_contracts['gnome-shell']['application_id']:
            field = self.shell_search_field()
            if field is None:
                return False
            return self.shell_query_matches(field, expected)
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid', ('search',))
        self.search_status = 'surface-missing'
        if surface is None:
            return False
        field = self.find_id(registered['search'], root=surface)
        self.search_status = 'field-missing'
        if field is None:
            return False
        if (field.get_role_name() not in ('text', 'entry')
                or not self.has_state(field, self.api.StateType.SENSITIVE)
                or not self.has_state(field, self.api.StateType.EDITABLE)):
            self.search_status = 'field-unusable'
            return False
        return self.read_label(field, 'search-query', expected=expected, maximum=80)

    def shell_query_matches(self, field, expected):
        """Read the field from the caller's fresh scoped Shell observation."""
        require(expected in ('', PRODUCT[:1], PRODUCT, 'Terminal', NATIVE_PRODUCT), 'ui:search-binding')
        text = field.get_text_iface()
        require(text is not None, 'ui:search-text-unavailable')
        count = self.api.Text.get_character_count(text)
        require(0 <= count <= 80, 'ui:search-text-bound')
        matches = (count == len(expected)
                   and self.api.Text.get_text(text, 0, count) == expected)
        self.search_status = ('query-matched' if matches else
                              'query-mismatch-length=' + str(count))
        return matches

    def shell_search_snapshot(self):
        """Shell 50 Overview adapter; semantics stay inside this provider scope.

        Shell exposes no usable public IDs on the pinned image. A complete fresh
        tree binds the one direct desktop application owner before inspecting its
        search controls. Names never select an application outside that owner.
        """
        root = self.api.get_desktop(0)
        require(root is not None, 'ui:incomplete-tree')
        snapshot, facts = {}, {}
        nodes = list(self.nodes(root, strict=True, protect_text=True,
                                snapshot=snapshot, facts=facts))
        require(nodes and not any(self.has_state(node, self.api.StateType.DEFUNCT)
                                  for node in nodes), 'ui:incomplete-tree')
        self.handle_system_prompt(observation=(nodes, snapshot, facts))
        owners = [node for node in snapshot[root]
                  if facts[node]['role'] == 'application'
                  and facts[node]['name'].casefold() in GDM_SEMANTIC_APPLICATION_NAMES]
        require(len(owners) <= 1, 'ui:shell-provider-owner')
        return (owners[0] if owners else None), nodes, snapshot, facts

    def shell_search_field(self):
        owner, nodes, snapshot, facts = self.shell_search_snapshot()
        self.search_status = 'shell-owner-missing'
        if owner is None:
            return None
        fields = [node for node in self.snapshot_scope(nodes, snapshot, owner)
                  if facts[node]['role'] in ('text', 'entry')
                  and facts[node]['showing']
                  and self.has_state(node, self.api.StateType.SENSITIVE)
                  and self.has_state(node, self.api.StateType.EDITABLE)]
        require(len(fields) <= 1, 'ui:shell-search-ambiguous')
        self.search_status = 'shell-field-missing' if not fields else 'shell-field-identified'
        return fields[0] if fields else None

    def search_ready(self, surface, *, focused=False):
        """SEARCH01/UI21: read the empty field, optionally its independent focus."""
        require(surface == 'overview' and type(focused) is bool, 'ui:search-binding')
        def ready():
            if not self.search_query(''):
                return False
            if not self.provider_contracts['gnome-shell']['application_id']:
                field = self.shell_search_field()
            else:
                surface, registered = self.provider_surface(
                    'gnome-shell', 'app-grid', ('search',))
                field = (self.find_id(registered['search'], root=surface)
                         if surface is not None else None)
            return field if field is not None and (not focused or self.has_state(
                field, self.api.StateType.FOCUSED)) else False
        return self.wait_search(ready, 'standard-search-focus' if focused else 'standard-search-ready')

    def focus_search_field(self):
        """Focus the scoped provider search field without pointer geometry."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        if not self.provider_contracts['gnome-shell']['application_id']:
            field = self.wait(self.shell_search_field, 'search-field', prompt_in_predicate=True)
        else:
            field = self.wait(
                lambda: self.snapshot_provider_target(
                    'gnome-shell', 'app-grid', 'search', check_prompt=True),
                'search-field', prompt_in_predicate=True,
            )
        require(field is not None and self.has_state(field, self.api.StateType.SENSITIVE),
                'ui:search-field')
        component = field.get_component_iface()
        require(component is not None, 'ui:search-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:search-focus-refused')
        def focused():
            current = (self.shell_search_field()
                       if not self.provider_contracts['gnome-shell']['application_id'] else
                       self.find_provider_control('gnome-shell', 'app-grid', 'search'))
            return current is not None and self.has_state(
                current, self.api.StateType.FOCUSED)
        self.wait(focused, 'standard-search-focus')
        self.input_uncertain = False

    def focus_search_result(self, product=PRODUCT):
        """Qualify the exact launcher recipient before the worker sends Enter."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(product in (PRODUCT, NATIVE_PRODUCT), 'ui:search-binding')
        self.wait(lambda: self.search_query(product), 'parent-search-query')
        target = self.wait(lambda: self.launchable_result(product), 'parent-search-result')
        target = (self.launchable_result(product)
                  if not self.provider_contracts['gnome-shell']['application_id'] else
                  self.fresh_owned_target(target))
        require(target is not None, 'ui:search-result-stale')
        component = target.get_component_iface()
        require(component is not None, 'ui:search-focus-unavailable')
        self.input_uncertain = True
        require(component.grab_focus(), 'ui:search-focus-refused')
        def focused():
            current = self.launchable_result(product)
            return current is not None and self.has_state(current, self.api.StateType.FOCUSED)
        self.wait(focused, 'parent-result-focus')
        self.input_uncertain = False

    def native_launch_command(self, instance='primary', *, child=EXISTING_CHILD):
        """APP01: one fixed native command in Jordan's active desktop session.

        FIX06 verifies the baseline inputs before this operation. Submission is
        never window acceptance; APP02 independently reads the public result.
        """
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(instance == 'primary', 'ui:native-binding')
        require(child in (CHILD, EXISTING_CHILD), 'ui:native-child-binding')
        require_active_launch_session()
        if child == CHILD:
            self.require_child_overlay_session()
        self.desktop_result(child, 'success')
        require(self.native_app_closed(), 'ui:native-window-exists')
        self.handle_system_prompt()
        self.input_uncertain = True
        subprocess.run([
            '/usr/bin/systemd-run', '--user', '--quiet', '--collect',
            '--service-type=exec',
            '/opt/onpc-test-fixtures/Applications/Exact Fixture.AppImage',
        ], stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15)

    def native_app_snapshot(self, submitted, *, pending=False, with_window=False):
        """APP02/03: public owned window and finite independent activity projection."""
        require(submitted in ('No submitted draft', 'ONPC fixture draft'), 'ui:native-projection')
        scope = 'onpc-fixture-native-primary'
        root = self.snapshot_owned_target(scope, check_prompt=True)
        if pending and (root is None or not self.has_state(root, self.api.StateType.ACTIVE)):
            return None
        require(root is not None and self.has_state(root, self.api.StateType.ACTIVE),
                'ui:native-entry')
        try:
            from fixture_ui import FixtureUI
        except ModuleNotFoundError as error:
            if error.name != 'fixture_ui':
                raise
            from tests.e2e.fixture_ui import FixtureUI
        fixture = FixtureUI(self, 'native', require=require)
        require(fixture.text('status') == 'Ready', 'ui:native-status')
        value = fixture.snapshot()
        expected = {'draft': 'ONPC fixture draft', 'submitted': submitted,
                    'score': 'Moves: 0; token: 0'}
        if pending and value != expected:
            return None
        require(value == expected, 'ui:native-activity')
        if with_window:
            # Public accessible identity distinguishes replacement windows even
            # when they expose identical fixture text and the same public ID.
            pid, bus, path = root.get_process_id(), root.bus, root.path
            require(type(pid) is int and pid > 0 and type(bus) is str
                    and bus.startswith(':') and type(path) is str and path.startswith('/'),
                    'ui:native-endpoint')
            return {'binding': 'native-primary', 'pid': pid,
                    'endpoint': [bus, path], 'state': value}
        return value

    def native_app_submit(self, instance='primary', *, submitted='No submitted draft'):
        """One normal public action; no replay after uncertain delivery."""
        require(not self.input_uncertain, 'ui:uncertain-input')
        require(instance == 'primary', 'ui:native-binding')
        self.native_app_snapshot(submitted)
        self.activate_id('onpc-fixture-native-primary-submit')

    def native_app_closed(self):
        """Complete owned absence with the independently recognized Shell desktop."""
        self.standard_shell_desktop(no_prompt=True)
        node = self.snapshot_owned_target('onpc-fixture-native-primary', showing=False,
                                          check_prompt=True)
        return node is None or not self.showing(node)

    def native_app_operation(self, operation, *, child=EXISTING_CHILD):
        require(operation in NATIVE_APP_OPERATIONS, 'ui:native-operation')
        if operation in ('native-desktop', 'native-closed'):
            self.wait(self.native_app_closed, 'native-closed')
        elif operation == 'native-command-launch':
            self.native_launch_command(child=child)
        elif operation == 'native-command-refusals':
            require(self.native_app_closed(), 'ui:native-wrong-entry')
            for instance, uncertain, expected in (
                    ('secondary', False, 'ui:native-binding'),
                    ('primary', True, 'ui:uncertain-input')):
                self.input_uncertain = uncertain
                try:
                    self.native_launch_command(instance)
                except UiError as error:
                    require(str(error) == expected, 'ui:native-wrong-refusal')
                else:
                    raise UiError('ui:native-refusal-missing')
                finally:
                    self.input_uncertain = False
            require(self.native_app_closed(), 'ui:native-refusal-changed')
        elif operation == 'native-search-ready':
            self.search_ready('overview')
        elif operation == 'native-search-focused':
            self.focus_search_field()
            self.search_ready('overview', focused=True)
        elif operation == 'native-search-entered':
            self.wait_search(lambda: self.search_query(NATIVE_PRODUCT), 'native-search-query')
        elif operation in ('native-grid', 'native-grid-refusals'):
            self.focus_search_result(NATIVE_PRODUCT)
            if operation == 'native-grid-refusals':
                for instance, uncertain, expected in (
                        ('secondary', False, 'ui:native-binding'),
                        ('primary', True, 'ui:uncertain-input')):
                    self.input_uncertain = uncertain
                    try:
                        self.native_app_submit(instance)
                    except UiError as error:
                        require(str(error) == expected, 'ui:native-wrong-refusal')
                    else:
                        raise UiError('ui:native-refusal-missing')
                    finally:
                        self.input_uncertain = False
                # Neither refusal may change the independently supplied grid entry.
                require(self.search_query(NATIVE_PRODUCT), 'ui:native-refusal-query')
                node = self.launchable_result(NATIVE_PRODUCT)
                require(node is not None and self.has_state(node, self.api.StateType.FOCUSED),
                        'ui:native-refusal-focus')
        elif operation == 'native-wrong-entry':
            require(self.native_app_closed(), 'ui:native-wrong-entry')
            try:
                self.native_app_submit()
            except UiError as error:
                require(str(error) == 'ui:native-entry', 'ui:native-wrong-refusal')
            else:
                raise UiError('ui:native-refusal-missing')
        elif operation == 'native-opened':
            return self.wait(lambda: self.native_app_snapshot('No submitted draft', pending=True),
                             'native-opened')
        elif operation == 'native-submit':
            self.native_app_submit()
        elif operation == 'native-resubmit':
            # A deliberate new invocation after activity retention, not a
            # retry of uncertain input or the initial unsubmitted-state guard.
            self.native_app_submit(submitted='ONPC fixture draft')
        elif operation == 'native-submitted':
            return self.wait(lambda: self.native_app_snapshot('ONPC fixture draft', pending=True),
                             'native-submitted')
        elif operation == 'native-activity':
            return self.native_app_snapshot('ONPC fixture draft', with_window=True)
        elif operation == 'native-activity-wrong-entry':
            require(self.native_app_closed(), 'ui:native-wrong-entry')
            try:
                self.native_app_snapshot('ONPC fixture draft', with_window=True)
            except UiError as error:
                require(str(error) == 'ui:native-entry', 'ui:native-wrong-refusal')
            else:
                raise UiError('ui:native-refusal-missing')
        elif operation == 'native-close':
            self.native_app_snapshot('ONPC fixture draft')
            self.activate_id('onpc-fixture-native-primary-close')

    def search_absence(self, product, *, stable_seconds):
        """Positive query/result witnesses plus fresh, complete absence reads.

        A missing tree, unfinished query, stale subtree or failed read cannot
        prove that the launcher is unavailable. Require a stable observation
        interval; repeat reads only, with no replay of customer input.
        """
        stable_since = None
        semantic_shell = not self.provider_contracts['gnome-shell']['application_id']
        if not semantic_shell:
            self.require_provider_contract(
                'gnome-shell', 'app-grid',
                ('search', 'result::parent', 'web-suggestion::parent'))
        def observed():
            nonlocal stable_since
            try:
                # Keep prompt/traversal failures inside the interval guard.
                # wait() retries these reads; none may bridge a stable interval.
                self.handle_system_prompt()
                if semantic_shell:
                    owner, nodes, snapshot, facts = self.shell_search_snapshot()
                    self.search_status = 'shell-owner-missing'
                    if owner is None:
                        stable_since = None
                        return False
                    scoped = self.snapshot_scope(nodes, snapshot, owner)
                    fields = [node for node in scoped
                              if facts[node]['role'] in ('text', 'entry')
                              and facts[node]['showing']
                              and self.has_state(node, self.api.StateType.SENSITIVE)
                              and self.has_state(node, self.api.StateType.EDITABLE)]
                    require(len(fields) <= 1, 'ui:shell-search-ambiguous')
                    self.search_status = 'shell-field-missing'
                    if not fields or not self.shell_query_matches(fields[0], product):
                        stable_since = None
                        return False
                    description = 'Search "' + product + '" on the web'
                    buttons = [node for node in scoped
                               if facts[node]['role'] in ('button', 'push button')
                               and facts[node]['showing']]
                    suggestions = [node for node in buttons
                                   if self.has_state(node, self.api.StateType.SENSITIVE)
                                   and (facts[node]['name'] == description or any(
                                       facts[child]['role'] == 'label'
                                       and facts[child]['showing']
                                       and facts[child]['name'] == description
                                       for child in self.snapshot_scope(nodes, snapshot, node)))]
                    require(len(suggestions) <= 1, 'ui:shell-suggestion-ambiguous')
                    self.search_status = 'suggestion-missing'
                    if not suggestions:
                        stable_since = None
                        return False
                    launchers = [node for node in buttons
                                 if facts[node]['name'] == product or any(
                                     facts[child]['role'] == 'label'
                                     and facts[child]['showing']
                                     and facts[child]['name'] == product
                                     for child in self.snapshot_scope(nodes, snapshot, node))]
                    management = {'parent-window', 'parent-access-denied-window',
                                  'kiosk-request-window', 'startup-error-window'}
                    ready = not launchers and not any(
                        facts[node]['showing'] and facts[node]['identity'] in management
                        for node in nodes)
                    self.search_status = ('description-matched' if ready else
                                          'parent-available')
                    if not ready:
                        stable_since = None
                        return False
                    now = time.monotonic()
                    if stable_since is None:
                        stable_since = now
                    return now - stable_since >= stable_seconds
                self.search_status = 'surface-missing'
                surface, registered = self.provider_surface(
                    'gnome-shell', 'app-grid',
                    ('search', 'result::parent', 'web-suggestion::parent'))
                ready = surface is not None and self.search_query(product)
                if ready:
                    suggestion = self.find_id(
                        registered['web-suggestion::parent'], root=surface)
                    ready = (suggestion is not None and self.has_state(
                        suggestion, self.api.StateType.SENSITIVE))
                    self.search_status = 'suggestion-matched' if ready else 'suggestion-missing'
                if ready:
                    ready = self.read_label(suggestion, 'web-suggestion', expected=product, maximum=80)
                    self.search_status = 'description-matched' if ready else 'description-missing'
                root = self.api.get_desktop(0)
                nodes = list(self.nodes(root, strict=True)) if root is not None else []
                for node in nodes:
                    if self.has_state(node, self.api.StateType.DEFUNCT):
                        ready = False
                        self.search_status = 'incomplete-read'
                    if (self.showing(node) and public_automation_id(node)
                            == registered['result::parent']):
                        ready = False
                        self.search_status = 'parent-available'
                    if (self.showing(node) and public_automation_id(node) in (
                            'parent-window', 'parent-access-denied-window',
                            'kiosk-request-window', 'startup-error-window')):
                        ready = False
                        self.search_status = 'parent-window-available'
                if not ready:
                    stable_since = None
                    return False
                now = time.monotonic()
                if stable_since is None:
                    stable_since = now
                return now - stable_since >= stable_seconds
            except (UiError, *self.query_errors):
                stable_since = None
                self.search_status = 'incomplete-read'
                raise
        return self.wait_search(observed, 'standard-parent-unavailable',
                                prompt_in_predicate=True)

    def wait_search(self, predicate, code, *, prompt_in_predicate=False):
        self.search_status = 'observation-pending'
        try:
            return self.wait(predicate, code, prompt_in_predicate=prompt_in_predicate)
        except UiError as error:
            if str(error) == 'ui:timeout:' + code:
                raise UiError(str(error) + ':' + self.search_status) from None
            raise

    def search_diagnostic(self):
        """Fixed ID-presence diagnostic; it never becomes target identity."""
        surface, registered = self.provider_surface(
            'gnome-shell', 'app-grid',
            ('search', 'result::parent', 'web-suggestion::parent'), showing=False)
        if surface is None:
            return {'provider_surface': 'absent', 'identified_controls': []}
        identified = [logical for logical, identity in registered.items()
                      if self.find_id(identity, root=surface, showing=False) is not None]
        return {'provider_surface': 'identified', 'identified_controls': sorted(identified)}

    def system_prompt_control(self, *, qualify=True):
        """Resolve Cancel only through the qualified keyring provider contract."""
        prompt_controls = ('recipient', 'secret', 'confirm', 'cancel')
        # Validate every authentication provider before the first tree read, so
        # a qualified keyring mapping cannot conceal an unqualified Polkit path
        # (or vice versa) during unrelated waits.
        self.require_provider_contract('gnome-shell-polkit-agent', 'polkit', prompt_controls)
        self.require_provider_contract('gcr-keyring-prompter', 'keyring', prompt_controls)
        polkit, _polkit_registered = self.provider_surface(
            'gnome-shell-polkit-agent', 'polkit', prompt_controls)
        require(polkit is None, 'ui:unsupported-system-prompt')
        surface, registered = self.provider_surface(
            'gcr-keyring-prompter', 'keyring',
            prompt_controls)
        if surface is None:
            return None
        if not qualify:
            return surface
        recipient = self.find_id(registered['recipient'], root=surface)
        field = self.find_id(registered['secret'], root=surface)
        confirm = self.find_id(registered['confirm'], root=surface)
        cancel = self.find_id(registered['cancel'], root=surface)
        require(recipient is not None, 'ui:system-prompt-recipient')
        require(field is not None and field.get_role_name() == 'password text'
                and self.has_state(field, self.api.StateType.SENSITIVE)
                and self.has_state(field, self.api.StateType.FOCUSED),
                'ui:system-prompt-focus')
        interface = field.get_text_iface()
        require(interface is not None and self.api.Text.get_character_count(interface) == 0,
                'ui:system-prompt-secret-state')
        require(confirm is not None and cancel is not None
                and self.has_state(cancel, self.api.StateType.SENSITIVE),
                'ui:system-prompt-control')
        return cancel

    def system_prompt_absent(self, dialog=None):
        # Absence is a fresh read of the qualified provider surface. A stale or
        # incomplete tree cannot establish dismissal.
        prompt_controls = ('recipient', 'secret', 'confirm', 'cancel')
        self.require_provider_contract('gnome-shell-polkit-agent', 'polkit', prompt_controls)
        self.require_provider_contract('gcr-keyring-prompter', 'keyring', prompt_controls)
        polkit, _polkit_registered = self.provider_surface(
            'gnome-shell-polkit-agent', 'polkit', prompt_controls, showing=False)
        require(polkit is None or not self.showing(polkit), 'ui:unsupported-system-prompt')
        surface, _registered = self.provider_surface(
            'gcr-keyring-prompter', 'keyring',
            prompt_controls, showing=False)
        if surface is None or not self.showing(surface):
            return True
        return dialog is not None and surface is not dialog

    @staticmethod
    def _prompt_application_kind(name):
        """Classify only the fixed provider application names for this image."""
        normalized = ' '.join(name.casefold().replace('_', ' ').replace('-', ' ').split())
        if normalized in (
                'policykit authentication agent',
                'mate polkit',
                'mate polkit authentication agent',
                'polkit mate authentication agent 1'):
            return 'mate-polkit'
        if normalized in ('gnome shell', 'gnome shell polkit agent'):
            return 'shell-polkit'
        if normalized in ('gcr prompter', 'gcr prompter 3', 'gcr prompter 4',
                          'system prompter'):
            return 'keyring'
        return None

    @staticmethod
    def _prompt_title(name):
        normalized = ' '.join(name.casefold().split())
        return normalized in (
            'authenticate', 'authentication required', 'password required',
            'unlock keyring', 'unlock login keyring',
        )

    def _provider_kind_from_ids(self, application, surface, identities=None):
        """Use provider IDs when both available, without requiring control IDs."""
        application_id = (public_automation_id(application) if identities is None
                          else identities[application])
        surface_id = (public_automation_id(surface) if identities is None
                      else identities[surface])
        bindings = []
        for provider, kind in (
                ('mate-polkit-agent', 'mate-polkit'),
                ('gnome-shell-polkit-agent', 'shell-polkit'),
                ('gcr-keyring-prompter', 'keyring')):
            contract = self.provider_contracts.get(provider, {})
            expected_application = contract.get('application_id')
            expected_surface = contract.get('surfaces', {}).get(
                'keyring' if kind == 'keyring' else 'polkit', (None, {}))[0]
            if (expected_application and expected_surface
                    and application_id == expected_application and surface_id == expected_surface):
                bindings.append(kind)
        require(len(bindings) <= 1, 'ui:ambiguous-system-prompt')
        return bindings[0] if bindings else None

    def system_prompt_kind(self, *, observation=None, nonsecret_surface=None):
        """Read one complete tree and classify a visible authentication modal.

        This is the provider-specific G02 adapter.  It recognizes only the
        fixed English provider semantics used by the prepared Ubuntu image, or
        a provider's application/surface IDs when both are available.  It does
        not resolve an input control and cannot authorize an action.
        """
        if observation is None:
            desktop = self.root()
            require(desktop is not None, 'ui:incomplete-tree')
            nodes, snapshot, identities, facts = self.read_snapshot(desktop)
            require(nodes, 'ui:incomplete-tree')
        else:
            nodes, snapshot, facts = observation
        require(nonsecret_surface is None or nonsecret_surface in nodes,
                'ui:wrong-prompt-scope')
        identities = {node: facts[node]['identity'] for node in nodes}
        provider_application_ids = {
            contract.get('application_id')
            for provider, contract in self.provider_contracts.items()
            if provider in ('mate-polkit-agent', 'gnome-shell-polkit-agent',
                            'gcr-keyring-prompter') and contract.get('application_id')
        }
        applications = [node for node in nodes
                        if facts[node]['role'] == 'application'
                        or identities[node] in provider_application_ids]
        candidates = []
        for application in applications:
            application_nodes = self.snapshot_scope(nodes, snapshot, application)
            application_kind = self._prompt_application_kind(facts[application]['name'])
            owned = bool(identities[application] in (
                PARENT_APPLICATION, KIOSK_APPLICATION, CHILD_APPLICATION,
                *self.owned_applications('watch-window')))
            for surface in application_nodes:
                if surface is application or not facts[surface]['showing']:
                    continue
                id_kind = self._provider_kind_from_ids(
                    application, surface, identities)
                modal = (facts[surface]['role'] in ('alert', 'dialog')
                         or facts[surface]['modal']
                         or id_kind is not None)
                if not modal:
                    continue
                # Descendant lookup is needed only for candidate dialogs.
                # Doing it for every label/control makes this shared check
                # quadratic in large Shell and application trees.
                descendants = self.snapshot_scope(nodes, snapshot, surface)
                password = any(facts[node]['role'] == 'password text'
                               for node in descendants)
                prompt_title = self._prompt_title(facts[surface]['name'])
                kind = id_kind or application_kind
                if surface == nonsecret_surface and not (password or prompt_title or kind):
                    continue
                # Shell's logout confirmation is also modal. Known provider
                # applications need authentication meaning; an unregistered
                # external modal is itself an unknown surface and must block.
                if kind is not None and not (password or prompt_title):
                    continue
                if not owned:
                    candidates.append(kind or 'unknown')
        require(len(candidates) <= 1, 'ui:ambiguous-system-prompt')
        return candidates[0] if candidates else None

    def pointer_target(self, node):
        raise UiError('ui:pointer-route-refused')

    def pointer_glyph(self, node):
        raise UiError('ui:pointer-route-refused')

    def stable_pointer(self, locate, *, stable_seconds=0.4):
        raise UiError('ui:pointer-route-refused')

    def handle_system_prompt(self, *, observation=None, nonsecret_surface=None):
        """Recognize and refuse session prompts without delivering input."""
        if not self.prompt_enabled or self.handling_prompt:
            return
        self.handling_prompt = True
        try:
            kind = (self.system_prompt_kind(nonsecret_surface=nonsecret_surface)
                    if observation is None else self.system_prompt_kind(
                        observation=observation, nonsecret_surface=nonsecret_surface))
            if kind is not None:
                require(self.prompt_session in ('station', 'desktop'),
                        'ui:system-prompt-session')
                raise UiError('ui:system-prompt-refused:' + self.prompt_session + ':' + kind)
        except self.query_errors as error:
            refusal = UiError('ui:system-prompt-observation-failed')
            for note in getattr(error, '__notes__', ()):
                if note.startswith('public-atspi-query:'):
                    refusal.add_note(note)
            raise refusal from None
        finally:
            self.handling_prompt = False

    def run(self, operation, version, *, child=None):
        """One registered operation, with generic read reuse between inputs."""
        require(child is None or (child in NAMED_CUSTOM_CHILDREN
                and operation in NAMED_CHILD_OPERATIONS), 'ui:custom-child-binding')
        if self.timing is not None:
            require(operation in OPERATIONS, 'ui:operation')
            self._timing = {'started': time.monotonic(), 'tree_reads': 0,
                            'nodes_read': 0, 'reader_ms': 0.0, 'input_ms': []}
        try:
            with self.observation():
                return self._run(operation, version, child=NAMED_CUSTOM_CHILDREN[child] if child else CHILD)
        finally:
            if self._timing is not None:
                timing, self._timing = self._timing, None
                started = timing.pop('started')
                elapsed = (time.monotonic() - started) * 1000
                timing['reader_ms'] = round(timing['reader_ms'], 3)
                self.timing({'event': 'ui-operation-timing', 'operation': operation,
                             'started_monotonic_ms': round(started * 1000, 3),
                             'elapsed_ms': round(elapsed, 3), **timing})

    def _run(self, operation, version, *, child=CHILD):
        require(operation in OPERATIONS, 'ui:operation')
        self.text_overlay = operation.startswith('text-overlay-')
        if self.text_overlay:
            self.require_child_overlay_session()
        self.prompt_enabled = operation not in GREETER_OPERATIONS and operation not in STATION_BRANCH_OPERATIONS
        self.prompt_session = ('station' if operation in KIOSK_SESSION_OPERATIONS
                               or operation == 'station-default-entry' else
                               None if operation in GREETER_OPERATIONS else 'desktop')
        result = {'operation': operation, 'outcome': 'passed', 'interface': 'AT-SPI'}
        if operation in NATIVE_APP_OPERATIONS or operation in OVERLAY_NATIVE_OPERATIONS:
            overlay_native = operation in OVERLAY_NATIVE_OPERATIONS
            if overlay_native:
                self.require_child_overlay_session()
            value = self.native_app_operation(operation.removeprefix('overlay-'),
                                             child=CHILD if overlay_native else EXISTING_CHILD)
            if value is not None:
                result['activity'] = value
            if operation in ('native-grid', 'native-grid-refusals'):
                owner, _nodes, _snapshot, _facts = self.shell_search_snapshot()
                require(owner is not None, 'ui:shell-provider-owner')
                result['provider'] = self._shell_provider_metadata(owner)
        elif operation == 'station-entry-branch':
            result['branch'] = self.station_entry_branch(self.branch_owner)
        elif operation == 'station-default-entry':
            result['entry'] = self.station_default_entry(self.branch_owner)
        elif operation in GREETER_OPERATIONS:
            if operation in ('gdm-child-time-denied', 'gdm-child-denied-return-ready'):
                result['denial'] = self.gdm_child_time_denied()
            elif operation == 'gdm-child-denied-returned':
                self.gdm_nonsecret_account(CHILD)
            elif operation == 'gdm-installed-accounts':
                self.gdm_semantic_rows((PARENT, OTHER_PARENT, EXISTING_CHILD, CHILD, KIOSK))
            elif operation == 'gdm-product-free-provider':
                result['provider'] = self.gdm_provider_metadata()
            elif operation in ('gdm-no-child-refused', 'gdm-no-approver-refused'):
                self.gdm_nonsecret_account(KIOSK)
                try:
                    self.kiosk_account_snapshot(
                        'child' if operation == 'gdm-no-child-refused' else 'approver')
                except UiError as error:
                    require(str(error) == 'ui:kiosk-account-surface', 'ui:kiosk-wrong-refusal')
                else:
                    raise UiError('ui:kiosk-wrong-entry-accepted')
            elif operation in ('gdm-wrong-recipient-refused', 'gdm-standard-wrong-recipient-refused',
                               'gdm-child-wrong-recipient-refused'):
                self.wait(lambda: self.password_recipient(OTHER_PARENT), 'gdm-other-recipient')
                name = EXISTING_CHILD if operation == 'gdm-standard-wrong-recipient-refused' else PARENT
                if operation == 'gdm-child-wrong-recipient-refused':
                    name = CHILD
                require(not self.password_recipient(name), 'ui:gdm-wrong-recipient-accepted')
            elif operation in ('gdm-parent-recipient', 'gdm-parent-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(PARENT), 'gdm-parent-recipient')
            elif operation in ('gdm-standard-recipient', 'gdm-standard-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(EXISTING_CHILD), 'gdm-standard-recipient')
            elif operation in ('gdm-child-recipient', 'gdm-child-recipient-rechecked'):
                self.wait(lambda: self.password_recipient(CHILD), 'gdm-child-recipient')
            elif operation == 'gdm-select-parent':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-product-free-select-parent':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-product-free-returned':
                self.gdm_product_free_account()
            elif operation in ('gdm-navigation-returned', 'gdm-dismissed', 'gdm-returned'):
                self.gdm_nonsecret_account(PARENT)
            elif operation == 'gdm-station-wrong-entry-refused':
                self.gdm_nonsecret_prompt()
            elif operation == 'gdm-station-returned':
                self.kiosk_gdm_returned()
            elif operation in ('gdm-focused', 'gdm-other-focused', 'gdm-standard-focused',
                              'gdm-station-focused', 'gdm-product-free-focused', 'gdm-child-focused'):
                name = OTHER_PARENT if operation == 'gdm-other-focused' else PARENT
                if operation == 'gdm-standard-focused':
                    name = EXISTING_CHILD
                if operation == 'gdm-child-focused':
                    name = CHILD
                if operation == 'gdm-station-focused':
                    name = KIOSK
                account = (self.gdm_product_free_account
                           if operation == 'gdm-product-free-focused'
                           else (lambda: self.gdm_nonsecret_account(name))
                           if operation in GDM_NONSECRET_OPERATIONS
                           else (lambda: self.greeter_list(name)))
                self.wait(lambda: self.has_state(account(), self.api.StateType.FOCUSED),
                          'gdm-account-focus')
            elif operation in GREETER_NAVIGATION:
                name = OTHER_PARENT if operation == 'gdm-other-list' else PARENT
                if operation == 'gdm-standard-list':
                    name = EXISTING_CHILD
                if operation == 'gdm-child-list':
                    name = CHILD
                if operation == 'gdm-station-list':
                    name = KIOSK
                if operation == 'gdm-product-free-list':
                    result['focused'] = self.gdm_product_free_navigation()
                else:
                    navigation = (self.gdm_nonsecret_navigation
                                  if operation in GDM_NONSECRET_OPERATIONS
                                  else self.greeter_navigation)
                    result['focused'] = navigation(name)
                if operation == 'gdm-child-list':
                    result['provider'] = self.gdm_provider_metadata(installed_child=True)
            else:
                self.greeter_list()
        elif operation in COUNTDOWN_OPERATIONS:
            result['countdown'] = self.child_countdown(operation == 'child-countdown-present')
        elif operation == 'child-countdown-wrong-account-refused':
            try:
                self.child_countdown(True)
            except UiError as error:
                require(str(error) == 'ui:countdown-account', 'ui:countdown-refusal')
            else:
                raise UiError('ui:countdown-wrong-account-accepted')
            result['refused'] = True
        elif operation in ('fresh-parent-desktop', 'fresh-standard-desktop', 'fresh-child-desktop'):
            self.standard_shell_desktop(no_prompt=True)
            if operation == 'fresh-child-desktop':
                result['provider'] = self.shell_provider_metadata()
        elif operation == 'parent-desktop-provider':
            self.standard_shell_desktop(no_prompt=True)
            result['provider'] = self.shell_provider_metadata()
        elif operation == 'keyring-cancel-standard':
            self.cancel_keyring_prompt()
        elif operation in ('desktop', 'standard-desktop'):
            self.desktop_result(PARENT if operation == 'desktop' else EXISTING_CHILD, 'success')
        elif operation == 'help-desktop-clear':
            self.help_desktop_clear()
        elif operation == 'standard-system-prompt':
            self.desktop_result(EXISTING_CHILD, 'success')
        elif operation in ('parent-command-launch', 'standard-parent-command-launch'):
            self.launch_parent_command(standard=operation == 'standard-parent-command-launch')
        elif operation == 'child-command-launch':
            self.require_child_overlay_session()
            self.launch_child_command(child=CHILD)
        elif operation == 'overlay-panel-ready':
            self.overlay_panel_target()
        elif operation == 'overlay-panel-launch':
            self.overlay_panel_launch()
        elif operation == 'overlay-panel-reveal-ready':
            self.require_child_overlay_session()
            self.kiosk_request_form(enabled=True, overlay=True)
            require(self.shell_search_field() is None, 'ui:overlay-overview-already-open')
        elif operation == 'overlay-panel-overview':
            self.require_child_overlay_session()
            self.search_ready('overview')
        elif operation == 'overlay-request-form':
            result['request'] = self.kiosk_request_form(enabled=True, overlay=True)
        elif operation == 'overlay-qualification-cancel':
            self.require_child_overlay_session()
            nodes, edges, identities, facts = self.read_snapshot(protect_text=True)
            application = self.snapshot_matches(CHILD_APPLICATION, nodes, showing=False,
                                                identities=identities)
            require(application is not None, 'ui:overlay-application')
            target = self.snapshot_owned_target('kiosk-request-cancel', root=application,
                showing=False, check_prompt=True, observation=(nodes, edges, identities, facts))
            require(target is not None, 'ui:overlay-cancel')
            self._invoke_target(target)
        elif operation == 'overlay-desktop':
            self.overlay_desktop()
        elif operation == 'overlay-wrong-account-refused':
            try:
                self.require_child_overlay_session()
            except UiError as error:
                require(str(error) == 'ui:overlay-account', 'ui:overlay-wrong-refusal')
            else:
                raise UiError('ui:overlay-wrong-account-accepted')
            result['refused'] = True
        elif operation == 'standard-parent-closed':
            self.wait(self.parent_denial_closed, 'denial-closed')
        elif operation == 'standard-management-denied':
            self.management_denied()
        elif operation == 'standard-app-grid':
            self.search_ready('overview')
        elif operation == 'standard-search-focused':
            self.focus_search_field()
        elif operation == 'standard-search-started':
            # GNOME's public overview supports type-to-search without manually
            # focusing the entry. Observe the first character before continuing.
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'standard-search-started')
        elif operation == 'standard-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'standard-search-entered')
        elif operation == 'standard-parent-unavailable':
            self.search_result(PRODUCT, 'unavailable', stable_seconds=2)
        elif operation == 'standard-search-qualified':
            self.search_result(PRODUCT, 'unavailable', stable_seconds=2)
            result['provider'] = self.shell_provider_metadata()
        elif operation == 'parent-search-ready':
            self.search_ready('overview')
        elif operation == 'parent-search-focused':
            self.focus_search_field()
            self.search_ready('overview', focused=True)
        elif operation == 'parent-search-entered':
            self.wait_search(lambda: self.search_query(PRODUCT), 'parent-search-entered')
        elif operation == 'shell-search-started':
            self.wait_search(lambda: self.search_query(PRODUCT[:1]), 'shell-search-started')
        elif operation == 'shell-search-wrong-result-refused':
            require(self.search_query(PRODUCT), 'ui:search-query')
            try:
                self.launchable_result('Terminal')
            except UiError as error:
                require(str(error) == 'ui:search-binding', 'ui:wrong-search-refusal')
            else:
                raise UiError('ui:wrong-search-accepted')
        elif operation == 'shell-search-cleared':
            self.search_ready('overview')
        elif operation == 'shell-search-dismissed':
            self.standard_shell_desktop(no_prompt=True)
            require(self.shell_search_field() is None, 'ui:search-not-dismissed')
        elif operation == 'app-grid':
            self.focus_search_result()
        elif operation == 'parent-search-close-ready':
            self.complete_parent_language_setup()
            result['provider'] = self.shell_provider_metadata()
            self.wait(lambda: self.has_state(self.parent(), self.api.StateType.ACTIVE),
                      'parent-search-close-ready')
        elif operation == 'parent-search-closed':
            self.wait(self.parent_search_closed, 'parent-search-closed')
        elif operation == 'parent-window':
            self.complete_parent_language_setup()
            self.parent()
        elif operation == 'parent-window-count':
            result['count'] = self.parent_window_count()
        elif operation == 'parent-restart-ready':
            self.parent_restart_entry('parent', 'management')
        elif operation == 'parent-restart-closed-refused':
            self.new_parent_window_entry()
            try:
                self.parent_restart_entry('parent', 'management')
            except UiError as error:
                require(str(error) == 'ui:restart-window', 'ui:restart-refusal')
            else:
                raise UiError('ui:restart-refusal-missing')
            self.new_parent_window_entry()
        elif operation == 'parent-restart-wrong-refused':
            self.parent_restart_entry('parent', 'management')
            try:
                self.parent_restart_entry('about', 'management')
            except UiError as error:
                require(str(error) == 'ui:restart-binding', 'ui:restart-refusal')
            else:
                raise UiError('ui:restart-refusal-missing')
            self.parent_restart_entry('parent', 'management')
        elif operation == 'parent-initial-selection':
            result['selection'] = self.parent_initial_selection()
        elif operation == 'parent-new-window-absent':
            self.new_parent_window_entry()
        elif operation == 'parent-new-window-refused':
            self.parent()
            try:
                self.new_parent_window_entry()
            except UiError as error:
                require(str(error) == 'ui:parent-window-exists', 'ui:window-refusal')
            else:
                raise UiError('ui:window-refusal-missing')
        elif operation == 'parent-empty':
            self.complete_parent_language_setup()
            self.parent_empty()
        elif operation == 'named-custom-setup':
            self.configure_time_controls(child, initial_enabled=False, minutes=0, final_enabled=True)
        elif operation == 'named-custom-wrong-child-refused':
            self.allowance_entry(child)
            other = EXISTING_CHILD if child == CHILD else CHILD
            for check, category in (
                    (lambda: self.focus_text('parent-custom-daily-limit', child=other), 'ui:wrong-child'),
                    (lambda: self.parent_save_trace_source(True, other), 'ui:selected-child')):
                try:
                    check()
                except UiError as error:
                    require(str(error) == category, 'ui:trace-refusal')
                else:
                    raise UiError('ui:trace-wrong-entry-accepted')
        elif operation in ACCESSIBILITY_TRACE_OPERATIONS:
            if operation.startswith('feedback-collection-'):
                result['trace'] = self.feedback_collection_events(operation)
            elif operation == 'parent-custom-trace-focus':
                result['trace'] = self.custom_trace_focus(child)
            elif operation == 'parent-custom-trace-disabled-refused':
                self.parent_save_snapshot(child, False)
                try:
                    self.custom_allowance(child, 6, action='open')
                except UiError as error:
                    require(str(error) == 'ui:unusable-target', 'ui:trace-refusal')
                    result['trace'] = {'refusal': 'disabled'}
                else:
                    raise UiError('ui:trace-wrong-entry-accepted')
            else:
                result['trace'] = (self.parent_save_events(operation == 'parent-custom-events', child)
                    if operation in ('parent-save-events', 'parent-custom-events')
                    else self.parent_checked_events(operation))
        elif operation in TOGGLE_OPERATIONS:
            result['toggle'] = self.parent_toggle_operation(operation)
        elif operation in FILTER_OPERATIONS:
            kind, mask, action = FILTER_OPERATIONS[operation]
            result['filter'] = self.catalogue_filter(child, kind, mask, action)
        elif operation in APP_ROW_OPERATIONS:
            result['apps'] = self.app_row_operation(operation)
        elif operation in LEGEND_OPERATIONS:
            result['legend'] = self.policy_legend_operation(operation)
        elif operation in MATCH_OPERATIONS:
            result['match'] = self.match_operation(operation, child=child)
        elif operation in PARENT_REPORT_OPERATIONS:
            value = self.parent_report_operation(operation)
            result['report' if operation == 'parent-report-refused' else 'feedback'] = value
        elif operation in ACCESS_OPERATIONS:
            result['access'] = self.access_operation(operation, child=child)
        elif operation in PARENT_SAVE_OPERATIONS:
            result['save'] = self.parent_save_operation(operation)
        elif operation in PICKER_OPERATIONS:
            result['focused'] = self.open_child_picker(PICKER_OPERATIONS[operation])
        elif operation in HIGHLIGHT_OPERATIONS:
            self.child_highlighted(HIGHLIGHT_OPERATIONS[operation])
        elif operation == 'parent-page-wrong-child-refused':
            # A real selected child is a required entry condition. Refuse the
            # different child's page before any page input, then reread entry.
            self.selected_child(CHILD)
            try:
                self.parent_page(EXISTING_CHILD, 'App Limits')
            except UiError as error:
                require(str(error) == 'ui:selected-child', 'ui:page-wrong-refusal')
            else:
                raise UiError('ui:page-wrong-entry-accepted')
            self.selected_child(CHILD)
        elif operation == 'parent-apps-page':
            self.parent_page(CHILD, 'App Limits')
        elif operation in ('existing-apps', 'new-child-apps'):
            child = EXISTING_CHILD if operation == 'existing-apps' else NEW_CHILD
            self.parent_page(child, 'App Limits')
        elif operation in SETTINGS_OPERATIONS and operation != 'parent-returned':
            child = SETTINGS_OPERATIONS[operation]
            if operation in ('discovery-ready', 'new-child-screen', 'parent-screen-page'):
                result['settings'] = self.parent_page(child, 'Screen Limits')
            else:
                result['settings'] = self.selected_child(child)
        elif operation == 'parent-kiosk-about-refused':
            require(self.snapshot_owned_target('parent-window', check_prompt=True) is not None,
                    'ui:kiosk-about-parent-entry')
            try:
                self.open_kiosk_about()
            except UiError as error:
                require(str(error) == 'ui:kiosk-about-entry', 'ui:kiosk-about-refusal')
            else:
                raise UiError('ui:kiosk-about-refusal-missing')
        elif operation == 'kiosk-about-open':
            self.open_kiosk_about()
        elif operation == 'kiosk-about-read':
            self.read_kiosk_about(version)
        elif operation == 'kiosk-about-close-ready':
            self.kiosk_about_snapshot()
        elif operation == 'kiosk-about-closed':
            self.window_closed('about', 'kiosk')
        elif operation == 'about':
            self.open_about(version)
        elif operation == 'parent-help-clickable':
            self.check_parent_help()
        elif operation == 'parent-information-about':
            self.open_about(version, menu_open=True)
        elif operation == 'parent-information-clickable':
            self.check_parent_information()
        elif operation == 'about-interval-read':
            result['about_interval'] = self.read_about_interval(version)
        elif operation == 'about-interval-refused':
            self.parent()
            self.wait(lambda: self.absent_id('about-dialog', within='parent-window'),
                      'about-interval-wrong-entry')
            try:
                self.read_about_interval(version)
            except UiError as error:
                require(str(error) == 'ui:about-interval-entry', 'ui:about-interval-refusal')
            else:
                raise UiError('ui:about-interval-wrong-entry-accepted')
        elif operation in ALLOWANCE_OPERATIONS:
            result['allowance'] = self.allowance_operation(operation)
        elif operation in TIME_EXPLANATION_OPERATIONS:
            result['time_explanation'] = self.time_explanation_operation(operation, child=child)
        elif operation in REVOKE_DISABLED_OPERATIONS:
            result['revoke'] = self.revoke_disabled(CHILD, REVOKE_DISABLED_OPERATIONS[operation])
        elif operation in INVALID_ALLOWANCE_OPERATIONS:
            result['allowance_validation'] = self.invalid_allowance(
                INVALID_ALLOWANCE_OPERATIONS[operation])
        elif operation in CUSTOM_ALLOWANCE_OPERATIONS:
            result['custom_allowance'] = self.custom_allowance_operation(operation, child=child)
        elif operation in TEXT_OPERATIONS or operation in ('text-wrong-entry', 'text-disabled'):
            text = self.text_operation(operation, child=child)
            if text is not None:
                result['text'] = text
        elif operation in DUPLICATE_OPERATIONS:
            text = self.duplicate_text_operation(operation)
            if text is not None:
                result['text'] = text
        elif operation in SCALAR_OPERATIONS:
            text = self.scalar_text_operation(operation)
            if text is not None:
                result['text'] = text
        elif operation in SUFFIX_OPERATIONS:
            text = self.suffix_text_operation(operation)
            if text is not None:
                result['text'] = text
        elif operation in LENGTH_OPERATIONS:
            feedback = self.length_operation(operation)
            if feedback is not None:
                result['feedback_state'] = feedback
        elif operation in DRAFT_OPERATIONS:
            result.update(self.feedback_draft_operation(operation))
        elif operation in FILE_REVIEW_OPERATIONS:
            result.update(self.attachment_review_operation(operation))
        elif operation in WINDOW_SWITCH_OPERATIONS:
            result['window'] = self.window_switch_operation(operation)
            if operation == 'switch-viewer-launch':
                result['provider'] = self.wait(self.license_provider_metadata,
                    'switch-viewer-provider', prompt_in_predicate=True)
        elif operation in feedback_formats.OPERATIONS:
            formats = feedback_formats.operate(self, operation, require, UiError)
            if formats is not None:
                result['formats'] = formats
        elif operation in block_semantics.OPERATIONS:
            blocks = self.block_operation(operation)
            if blocks is not None:
                result['blocks'] = blocks
        elif operation in FORMAT_OPERATIONS:
            formatting = self.format_operation(operation)
            if formatting is not None:
                result['formatting'] = formatting
        elif operation in REJECTION_OPERATIONS:
            feedback = self.rejection_operation(operation)
            if feedback is not None:
                result['feedback_state'] = feedback
        elif operation == 'feedback-collection-ready':
            result['collection'] = self.wait_feedback_collection()
        elif operation in FEEDBACK_STATE_OPERATIONS:
            feedback = self.feedback_state_operation(operation)
            if feedback is not None:
                result['feedback_state'] = feedback
        elif operation in FEEDBACK_PRIVACY_OPERATIONS:
            feedback = self.feedback_privacy_operation(operation)
            if feedback is not None:
                result['feedback'] = feedback
        elif operation in CHOOSER_OPERATIONS:
            result['chooser'] = self.chooser_operation(operation)
        elif operation in SAVE_OPERATIONS:
            result['chooser'] = self.save_chooser_operation(operation)
        elif operation in ATTACHMENT_OPERATIONS:
            result['attachment'] = self.attachment_operation(operation)
        elif operation in BOUNDARY_OPERATIONS:
            result['boundary'] = self.boundary_operation(operation)
        elif operation in FEEDBACK_READ_OPERATIONS:
            feedback = self.feedback_read_operation(operation)
            if feedback is not None:
                result['feedback'] = feedback
        elif operation == 'about-rechecked':
            root = self.about()
            self.read_label(root, 'about-product', maximum=80)
            self.read_label(root, 'about-version', maximum=80, expected=version)
            self.id_target('about-license-value', root=root)
        elif operation == 'license':
            self.open_license()
        elif operation == 'license-provider-refusals':
            self.open_license()
        elif operation == 'website-clickable':
            self.clickable_link('about-website-value', root=self.about())
        elif operation == 'privacy-clickable':
            self.clickable_link('about-privacy-value', root=self.about())
        elif operation == 'support-clickable':
            self.clickable_link('about-support-value', root=self.about())
        elif operation == 'license-closed':
            self.about()
        elif operation == 'about-returned':
            self.about_footer()
            self.window_ready_to_close('about')
        elif operation == 'parent-returned':
            self.window_closed('about', 'parent')
            result['settings'] = self.settings()
        elif operation in KIOSK_DISABLED_REQUESTS:
            if operation == 'kiosk-disabled-child-select':
                result['request'] = self.select_kiosk_account(
                    'child', CHILD, expected=(CHILD, EXISTING_CHILD), enabled=False)
            else:
                result['request'] = self.kiosk_request_form(
                    enabled=False, expected_selection=('child', CHILD_IDENTITIES[CHILD]))
        elif operation in ('multiple-child-open', 'multiple-approver-open'):
            field = operation.split('-')[1]
            self.select_kiosk_account(field, EXISTING_CHILD if field == 'child' else OTHER_PARENT,
                expected=(CHILD, EXISTING_CHILD) if field == 'child' else (PARENT, OTHER_PARENT),
                inspect_only=True)
        elif operation in KIOSK_ACCOUNT_REQUESTS:
            if operation in ('multiple-child-closed', 'multiple-approver-closed'):
                result['request'] = self.collapse_kiosk_child_choices(
                    operation.split('-')[1], enabled=True)
            elif operation == 'multiple-preserved':
                result['request'] = self.kiosk_request_form(enabled=True,
                    expected_selection=('approver', 'fixture-parent'))
            elif operation.startswith('multiple-'):
                child, approver = KIOSK_ACCOUNT_REQUESTS[operation]
                field = 'child' if operation.endswith('-child') else 'approver'
                identities = CHILD_IDENTITIES if field == 'child' else APPROVER_IDENTITIES
                name = next(name for name, canonical in identities.items()
                            if canonical == (child if field == 'child' else approver))
                result['request'] = self.select_kiosk_account(field, name,
                    expected=(CHILD, EXISTING_CHILD) if field == 'child' else (PARENT, OTHER_PARENT))
            elif operation == 'kiosk-child-select':
                result['request'] = self.select_kiosk_account(
                    'child', CHILD, expected=(CHILD, EXISTING_CHILD))
            elif operation == 'kiosk-approver-select':
                result['request'] = self.select_kiosk_account(
                    'approver', PARENT, expected=(PARENT, OTHER_PARENT))
            else:
                result['request'] = self.kiosk_request_form(enabled=True)
        elif operation in KIOSK_ACCOUNT_REFUSALS:
            if operation == 'parent-kiosk-refused':
                self.parent()
                try:
                    self.kiosk_account_snapshot('child')
                except UiError as error:
                    require(str(error) == 'ui:kiosk-account-surface', 'ui:kiosk-wrong-refusal')
                else:
                    raise UiError('ui:kiosk-wrong-entry-accepted')
            else:
                for field, name, expected in (
                        ('child', PARENT, (CHILD, EXISTING_CHILD)),
                        ('approver', NEW_CHILD, (PARENT, OTHER_PARENT))):
                    try:
                        self.select_kiosk_account(field, name, expected=expected)
                    except UiError as error:
                        require(str(error) == 'ui:kiosk-account-choice', 'ui:kiosk-wrong-refusal')
                    else:
                        raise UiError('ui:kiosk-wrong-choice-accepted')
        elif operation == 'kiosk-child-choices-open':
            self.select_kiosk_account('child', CHILD, expected=(CHILD, EXISTING_CHILD),
                                      enabled=False, inspect_only=True)
        elif operation == 'kiosk-child-choices-closed':
            result['request'] = self.collapse_kiosk_child_choices()
        elif operation == 'parent-mate-refused':
            require(self.snapshot_owned_target('parent-window', check_prompt=True) is not None,
                    'ui:mate-parent-entry')
            try:
                self.kiosk_valid_target('kiosk-request-submit')
            except UiError as error:
                require(str(error) == 'ui:kiosk-valid-entry', 'ui:mate-wrong-entry-refusal')
            else:
                raise UiError('ui:mate-wrong-entry-accepted')
        elif operation in MATE_APPROVAL_OPERATIONS:
            result['approval'] = self.kiosk_mate_approval(operation)
        elif operation in MATE_OPERATIONS:
            result['mate'] = self.kiosk_mate_cancel(refusals=operation == 'kiosk-mate-refusals-cancel',
                binding=operation if operation in MULTIPLE_MATE_BINDINGS else None)
        elif operation in ('parent-kiosk-valid-refused', 'parent-kiosk-invalid-refused'):
            try:
                self.kiosk_valid_target('kiosk-request-submit' if operation ==
                                        'parent-kiosk-invalid-refused' else 'kiosk-duration-300')
            except UiError as error:
                require(str(error) == 'ui:kiosk-valid-entry', 'ui:kiosk-valid-refusal')
            else:
                raise UiError('ui:kiosk-valid-refusal-missing')
        elif operation in INVALID_REQUEST_OPERATIONS:
            result['invalid_choice'] = self.kiosk_invalid_choice(operation)
        elif operation in KIOSK_VALID_OPERATIONS:
            value = self.kiosk_valid_choice(operation)
            if value is not None:
                result['valid_choice'] = value
        elif operation in OVERLAY_VALID_REQUESTS or operation == 'overlay-valid-custom-open':
            self.require_child_overlay_session()
            value = self.kiosk_valid_choice(operation)
            if value is not None:
                result['valid_choice'] = value
        elif operation == 'overlay-valid-refusals':
            self.require_child_overlay_session()
            for call, expected in (
                (lambda: self.select_kiosk_account('child', CHILD, expected=(CHILD,), overlay=True),
                 'ui:overlay-child-selection'),
                (lambda: self.kiosk_valid_target('kiosk-duration-300'), 'ui:kiosk-valid-entry')):
                try:
                    call()
                except UiError as error:
                    require(str(error) == expected, 'ui:overlay-valid-refusal')
                else:
                    raise UiError('ui:overlay-valid-refusal-missing')
        elif operation == 'overlay-request-cancel':
            self.require_child_overlay_session()
            self.cancel_kiosk_request(overlay=True)
        elif operation == 'overlay-request-escape-ready':
            self.focus_kiosk_escape_recipient(overlay=True)
        elif operation in KIOSK_RESTRICTION_OPERATIONS:
            prepared = operation.startswith('kiosk-restriction-prepared-')
            if operation.endswith('-ready'):
                self.kiosk_restrictions(stable_seconds=0, prepared=prepared)
                self.focus_kiosk_escape_recipient()
            else:
                self.kiosk_restrictions(prepared=prepared)
        elif operation == 'kiosk-request-form':
            result['request'] = self.kiosk_request_form()
        elif operation == 'kiosk-no-child-form':
            result['request'] = self.kiosk_request_form(no_child=True)
        elif operation == 'kiosk-no-approver-form':
            result['request'] = self.kiosk_request_form(no_approver=True)
        elif operation == 'kiosk-approver-baseline':
            result['approver_uids'] = self.kiosk_approver_baseline()
        elif operation == 'kiosk-request-cancel':
            self.cancel_kiosk_request()
        elif operation == 'kiosk-request-escape-ready':
            self.focus_kiosk_escape_recipient()
        return result


def greeter_keyboard_sources():
    """Read GDM Shell's system input-source configuration through locale1."""
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    reply = bus.call_sync(
        'org.freedesktop.locale1', '/org/freedesktop/locale1',
        'org.freedesktop.DBus.Properties', 'GetAll',
        GLib.Variant('(s)', ('org.freedesktop.locale1',)),
        GLib.VariantType.new('(a{sv})'), Gio.DBusCallFlags.NONE, 5000, None)
    properties = reply.unpack()[0]
    layouts = properties.get('X11Layout')
    variants = properties.get('X11Variant')
    require(type(layouts) is str and 0 < len(layouts) <= 1024
            and type(variants) is str and len(variants) <= 1024,
            'ui:greeter-keyboard-metadata')
    layouts, variants = layouts.split(','), variants.split(',')
    require(0 < len(layouts) <= 8 and len(variants) <= len(layouts)
            and all(re.fullmatch(r'[A-Za-z0-9_-]{1,64}', item) for item in layouts)
            and all(re.fullmatch(r'[A-Za-z0-9_-]{0,64}', item) for item in variants),
            'ui:greeter-keyboard-metadata')
    return [['xkb', layout + ('+' + variants[index] if
                             index < len(variants) and variants[index] else '')]
            for index, layout in enumerate(layouts)]


def validate_gdm_metadata(value):
    require(type(value) is dict and set(value) == {'shell', 'gdm_version'}
            and type(value['gdm_version']) is str
            and re.fullmatch(r'[A-Za-z0-9_.+:@()/-]{1,128}', value['gdm_version']),
            'ui:gdm-metadata')
    validate_shell_metadata(value['shell'])
    return value


def validate_shell_metadata(value):
    """Bound the nonsecret tuple on both sides of the observation transport."""
    require(type(value) is dict and set(value) == {'version', 'locale', 'keyboard'},
            'ui:shell-metadata')
    require(type(value['keyboard']) is list and 0 < len(value['keyboard']) <= 8,
            'ui:shell-metadata')
    words = [value['version'], value['locale']]
    for source in value['keyboard']:
        require(type(source) is list and len(source) == 2 and source[0] in ('xkb', 'ibus'),
                'ui:shell-metadata')
        words.extend(source)
    require(all(type(word) is str and re.fullmatch(r'[A-Za-z0-9_.+:@()/-]{1,128}', word)
                for word in words), 'ui:shell-metadata')
    return value


def greeter_account(*, station_branch=False, station_required=False):
    """Resolve the sole active local greeter via public logind session metadata.

    Modern GDM can use a dynamic account instead of the legacy gdm UID. This
    selects only the public UI connection identity; it proves no product result.
    """
    # Installed boots gate GDM on enforcement readiness. Snapshot consumers
    # enter here directly after SSH, without the former setup boot-complete
    # wait. Observe the public greeter within its own finite boot budget.
    require(not station_required or station_branch, 'ui:station-account-binding')
    deadline = time.monotonic() + (90 if station_branch else 300)
    def call(*args):
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'ui:timeout:greeter-identity')
        try:
            return subprocess.run(['/usr/bin/loginctl', *args], capture_output=True,
                                  text=True, check=True, timeout=min(5, remaining)).stdout
        except subprocess.SubprocessError:
            # Fixed operation only; logind errors can contain account details.
            print('ui:greeter-read-failed:' + args[0], file=sys.stderr, flush=True)
            raise

    def sessions():
        rows = call('list-sessions', '--no-legend', '--no-pager').splitlines()
        require(len(rows) <= 32, 'ui:session-bound')
        identities = [row.split()[0] if row.split() else '' for row in rows]
        require(all(re.fullmatch(r'[a-zA-Z0-9]+', session) for session in identities),
                'ui:session-id')
        require(len(identities) == len(set(identities)), 'ui:session-id')
        return identities

    while True:
        found = []
        for session in sessions():
            try:
                raw = call('show-session', session, '-p', 'Class', '-p', 'Active',
                           '-p', 'Remote', '-p', 'Type', '-p', 'Seat', '-p', 'User')
            except subprocess.CalledProcessError:
                # A session can disappear between list and show during logout.
                # Confirm absence through a fresh successful inventory, then
                # discard the incomplete scan. A still-listed session, failed
                # inventory or timeout remains fatal; no input is retried.
                if session in sessions():
                    raise
                print('ui:greeter-session-disappeared', file=sys.stderr, flush=True)
                found = []
                break
            props = dict(line.split('=', 1) for line in raw.splitlines())
            if ((station_branch or props.get('Class') == 'greeter') and props.get('Active') == 'yes'
                    and props.get('Remote') == 'no' and props.get('Seat') == 'seat0'
                    and props.get('Type') in ('wayland', 'x11')):
                require(props.get('User', '').isdecimal() and int(props['User']) > 0,
                        'ui:greeter-user')
                uid = int(props['User'])
                if station_branch:
                    owner = 'greeter' if props.get('Class') == 'greeter' else 'station'
                    require(owner == 'greeter' or (props.get('Class') == 'user'
                            and uid == pwd.getpwnam(KIOSK_USERNAME).pw_uid),
                            'ui:station-branch-owner')
                    found.append((uid, owner))
                else:
                    found.append(uid)
        require(len(found) <= 1, 'ui:greeter-identity')
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'ui:timeout:greeter-identity')
        if found and not (station_required and found[0][1] != 'station'):
            if station_branch:
                return pwd.getpwuid(found[0][0]), found[0][1]
            return pwd.getpwuid(found[0])
        # SSH can become ready before GDM after an installed snapshot boots.
        # Repeat only confirmed absence, never ambiguity or an unresolved read.
        time.sleep(min(.2, remaining))


def countdown_seconds(text):
    """Public horizontal countdown formatting gives a closed seconds interval."""
    require(type(text) is str and len(text) <= 5, 'ui:countdown-text')
    match = re.fullmatch(r'([0-9]{2}):([0-5][0-9])', text)
    if match:
        seconds = int(match[1]) * 3600 + int(match[2]) * 60
        require(60 <= seconds < 86400, 'ui:countdown-text')
        return max(61, seconds), seconds + 59
    require(re.fullmatch(r'(?:[1-5]?[0-9]|60)', text) is not None,
            'ui:countdown-text')
    return int(text), int(text)


def validate_countdown(value, present):
    require(type(value) is dict and set(value) == {
        'child', 'surface', 'present', 'text', 'observed_monotonic_ns', 'stable_ms'}
        and value['child'] == 'fixture-child' and value['surface'] == 'desktop'
        and type(value['present']) is bool and value['present'] is present
        and type(value['observed_monotonic_ns']) is int and value['observed_monotonic_ns'] > 0
        and type(value['stable_ms']) is int, 'ui:countdown-response')
    if present:
        countdown_seconds(value['text'])
        require(value['stable_ms'] == 0, 'ui:countdown-response')
    else:
        require(value['text'] is None and 2000 <= value['stable_ms'] <= 45000,
                'ui:countdown-response')
    return dict(value)


def require_active_launch_session():
    """Bind direct execution to one active local graphical session of this UID."""
    uid = os.getuid()
    require(uid >= 1000 and os.geteuid() == uid, 'ui:launch-identity')

    def call(*args):
        return subprocess.run(['/usr/bin/loginctl', *args], capture_output=True,
                              text=True, check=True, timeout=10).stdout

    rows = call('list-sessions', '--no-legend', '--no-pager').splitlines()
    require(len(rows) <= 32, 'ui:session-bound')
    active = []
    for row in rows:
        fields = row.split()
        require(len(fields) >= 2, 'ui:session-row')
        if fields[1] != str(uid):
            continue
        session = fields[0]
        require(re.fullmatch(r'[a-zA-Z0-9]+', session), 'ui:session-id')
        props = dict(line.split('=', 1) for line in call(
            'show-session', session, '--no-pager', '-p', 'User', '-p', 'Active',
            '-p', 'Remote', '-p', 'Class', '-p', 'Type', '-p', 'Seat').splitlines())
        if props.get('User') == str(uid) and props.get('Active') == 'yes':
            if props.get('Class') in ('user', 'user-early') and props.get('Type') in ('wayland', 'x11'):
                require(props.get('Remote') == 'no' and props.get('Seat') == 'seat0',
                        'ui:launch-session')
                active.append(session)
    require(len(active) == 1, 'ui:launch-session')


def runtime_failure_diagnostic(account, pending, elapsed_ms):
    """Failure-only service/session evidence on private command stderr.

    This reads public OS state, never starts a session or retries UI input.
    Diagnostic errors must not replace the original binding failure.
    """
    document = {'event': 'ui-runtime-timeout', 'object': pending,
                'elapsed_ms': elapsed_ms, 'sessions': [], 'units': {}}

    def read(argv):
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, check=True, timeout=2).stdout

    try:
        sessions = read(['/usr/bin/loginctl', 'show-user', str(account.pw_uid),
                         '--no-pager', '-p', 'Sessions', '--value']).split()
        for session in sessions[:8]:
            if not re.fullmatch(r'[a-zA-Z0-9]+', session):
                continue
            props = read(['/usr/bin/loginctl', 'show-session', session, '--no-pager',
                          '-p', 'Class', '-p', 'Type', '-p', 'Active', '-p', 'Seat'])
            document['sessions'].append(dict(line.split('=', 1) for line in
                                              props.splitlines() if '=' in line))
    except (OSError, subprocess.SubprocessError):
        document['sessions_unavailable'] = True
    for unit in ('display-manager.service', 'fapolicyd.service',
                 'oh-no-parent-control-execution-policy-ready.service'):
        try:
            props = read(['/usr/bin/systemctl', 'show', unit, '--no-pager',
                          '-p', 'ActiveState', '-p', 'SubState', '-p', 'Result'])
            document['units'][unit] = dict(line.split('=', 1) for line in
                                           props.splitlines() if '=' in line)
        except (OSError, subprocess.SubprocessError):
            document['units'][unit] = {'unavailable': True}
    print(json.dumps(document, sort_keys=True), file=sys.stderr, flush=True)


def session_environment(account, *, runtime_root=Path('/run/user'), timeout=20):
    """Wait for the selected account's owned public session-bus socket."""
    runtime = runtime_root / str(account.pw_uid)
    started = time.monotonic()
    deadline = started + timeout

    def checked(info, *, kind, label):
        valid_type = (stat.S_ISDIR(info.st_mode) if kind == 'directory'
                      else stat.S_ISSOCK(info.st_mode))
        valid_owner = info.st_uid == account.pw_uid
        if not (valid_type and valid_owner):
            print(json.dumps({'event': 'ui-runtime-binding-refused',
                              'object': label, 'type': stat.S_IFMT(info.st_mode),
                              'owner': ('expected' if valid_owner else
                                        'root' if info.st_uid == 0 else 'other'),
                              'elapsed_ms': max(0, int((time.monotonic() - started) * 1000))},
                             sort_keys=True), file=sys.stderr, flush=True)
        require(valid_type and valid_owner,
                'ui:runtime-owner' if kind == 'directory' else 'ui:session-bus')

    while True:
        pending = 'runtime'
        try:
            info = runtime.lstat()
            checked(info, kind='directory', label='runtime')
            path = runtime / 'bus'
            pending = 'session-bus'
            info = path.lstat()
            checked(info, kind='socket', label='session-bus')
            return {'XDG_RUNTIME_DIR': str(runtime),
                    'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(path)}
        except FileNotFoundError:
            now = time.monotonic()
            if now >= deadline:
                try:
                    runtime_failure_diagnostic(account, pending,
                                               max(0, int((now - started) * 1000)))
                except Exception:
                    pass  # Private diagnostics cannot replace the original error.
                require(False, 'ui:timeout:' + pending)
            time.sleep(.2)


def observation_environment(account, operation):
    if operation in KIOSK_SESSION_OPERATIONS or operation == 'station-default-entry':
        runtime = '/run/user/' + str(account.pw_uid)
        return {'XDG_RUNTIME_DIR': runtime,
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + runtime + '/bus'}
    return session_environment(account)


def allowance_failure_diagnostic():
    """Distinguish desktop idle blanking from a missing preset, without UI text."""
    active = None
    try:
        result = subprocess.run(
            ['/usr/bin/gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
             '--object-path', '/org/gnome/ScreenSaver',
             '--method', 'org.gnome.ScreenSaver.GetActive'],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=10)
        active = {'(true,)': True, '(false,)': False}.get(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {'event': 'allowance-failure-diagnostic', 'screensaver_active': active}


def main():
    require(len(sys.argv) in (3, 4, 5, 6) and sys.argv[1] in OPERATIONS, 'ui:arguments')
    child = sys.argv[5] if len(sys.argv) == 6 else None
    require(child is None or (child in NAMED_CUSTOM_CHILDREN and
            sys.argv[1] in NAMED_CHILD_OPERATIONS), 'ui:custom-child-binding')
    boot = None
    if len(sys.argv) >= 4:
        # This is transport continuity, not a product/UI assertion. Check it
        # before account lookup, accessibility connection or any public input.
        import hashlib
        expected = sys.argv[3]
        require(expected == '' or re.fullmatch(r'[0-9a-f]{64}', expected), 'ui:boot-binding')
        raw = Path('/proc/sys/kernel/random/boot_id').read_bytes()
        require(re.fullmatch(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\n', raw),
                'ui:boot-identity')
        boot = hashlib.sha256(raw).hexdigest()
        require(not expected or expected == boot, 'ui:boot-changed')
    greeter = sys.argv[1] in GREETER_OPERATIONS
    kiosk = sys.argv[1] in KIOSK_SESSION_OPERATIONS or sys.argv[1] == 'station-default-entry'
    require(os.geteuid() == 0, 'ui:fixture-identity')
    branch_owner = None
    if sys.argv[1] in STATION_BRANCH_OPERATIONS:
        account, branch_owner = greeter_account(
            station_branch=True,
            station_required=sys.argv[1] == 'station-default-entry')
        greeter, kiosk = branch_owner == 'greeter', branch_owner == 'station'
    else:
        account = greeter_account() if greeter else pwd.getpwnam(
            'oh-no-parent-control' if kiosk else
            (CHILD_ACCOUNTS[CHILD] if sys.argv[1] in CHILD_DESKTOP_OPERATIONS else
             'onpc-child-jordan' if sys.argv[1] in STANDARD_OPERATIONS else 'onpc-parent-jamie'))
    require(account.pw_uid > 0 and (greeter or account.pw_uid >= 1000), 'ui:fixture-identity')
    # Station entry is qualified by its public form. Bind the observation
    # client to the account without polling session services or treating their
    # readiness as a customer result.
    environment = observation_environment(account, sys.argv[1])
    os.initgroups(account.pw_name, account.pw_gid)
    os.setgid(account.pw_gid)
    os.setuid(account.pw_uid)
    os.environ.clear()
    os.environ.update(HOME=account.pw_dir, USER=account.pw_name,
                      **environment,
                      LANG='C.UTF-8', NO_AT_BRIDGE='0')
    if sys.argv[1] == 'keyring-cancel-standard' or sys.argv[1] in MATE_APPROVAL_OPERATIONS:
        require_active_launch_session()
    import gi
    gi.require_version('Atspi', '2.0')
    from gi.repository import Atspi, GLib
    Atspi.set_timeout(2000, 5000)

    def reset_atspi_client():
        # Reconnect this observer's client after a graphical-session handoff.
        # This only resets the local AT-SPI client; it does not start, wait for,
        # or inspect an accessibility service.
        Atspi.exit()
        Atspi.init()
        ui.api.reset()

    ui = AccessibleUI(Atspi, timeout=90 if kiosk else 45, query_errors=(GLib.Error,),
        reset_observer=reset_atspi_client if kiosk else None,
        timing=lambda value: print(json.dumps(value, sort_keys=True), file=sys.stderr, flush=True),
        dispatch=lambda: GLib.MainContext.default().iteration(False))
    ui.branch_owner = branch_owner
    trace_argument = (sys.argv[1] in ACCESSIBILITY_TRACE_OPERATIONS or
                      sys.argv[1] == 'parent-toggle-enabled')
    ui.trace_request = sys.argv[4] if len(sys.argv) >= 5 and trace_argument else None
    ui.trace_boot = boot
    ui.expected_trace_source = (ui.trace_request if sys.argv[1] == 'parent-toggle-enabled' else None)
    ui.expected_mate_challenge = sys.argv[4] if len(sys.argv) == 5 and not trace_argument else None
    require(ui.expected_mate_challenge is None or (
        sys.argv[1] in MATE_APPROVAL_OPERATIONS and
        re.fullmatch(r'[0-9a-f]{64}', ui.expected_mate_challenge)), 'ui:mate-binding')
    try:
        result = ui.run(sys.argv[1], sys.argv[2], child=child)
    except UiError:
        if sys.argv[1] in ALLOWANCE_OPERATIONS:
            print(json.dumps(allowance_failure_diagnostic(), sort_keys=True),
                  file=sys.stderr, flush=True)
        if sys.argv[1] in STANDARD_OPERATIONS:
            try:
                print(json.dumps(ui.search_diagnostic(), sort_keys=True), file=sys.stderr, flush=True)
            except Exception:
                print('ui:search-diagnostic-unavailable', file=sys.stderr, flush=True)
        raise
    if boot is not None:
        result['boot_sha256'] = boot
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # No raw UI tree, account names, document contents or D-Bus errors.
        print(str(error) if isinstance(error, UiError) else 'ui:adapter-failed:' + type(error).__name__,
              file=sys.stderr, flush=True)
        raise SystemExit(1)
