"""Guarded controller for public UI operations, with sanitized evidence."""

import json
import sys
import time
import secrets
from dataclasses import dataclass

import accessible_ui
import watch_activity
from private_artifacts import require
import system_runner as system


# Collection replies need room for their full bounded semantic projection.
# App rows still validate at most 256 fixed-format ID/access/match triples.
RESPONSE_BYTE_LIMITS = {
    'revoke-saved-balances': 327680,
    'revoke-cleared-balances': 327680,
    **{operation: 8192 for operation in accessible_ui.CHINESE_MATE_ORDER},
    **{operation: 8192 for operation in accessible_ui.CHINESE_LANGUAGE_OPERATIONS},
    **{operation: 8192 for operation in accessible_ui.INITIAL_KIOSK_OPERATIONS},
    **{operation: 32768 for operation in accessible_ui.CATALOGUE_ROW_OPERATIONS},
    'feedback-collection-events': 8192,
    'parent-checked-events': 8192,
    'parent-save-events': 8192,
    'parent-custom-events': 8192,
    'kiosk-approver-baseline': 65536,
    'parent-app-rows': 32768,
    'parent-app-rows-reopened': 32768,
    'existing-parent-app-rows': 32768,
    'existing-parent-app-rows-reopened': 32768,
}


# Fixed public descriptions only; never forward account labels, query text or
# credentials from the observed desktop. New operations must declare prose here.
OPERATION_LABELS = {
    **{operation: 'Observing the bound desktop shortcut and its public result'
       for operation in accessible_ui.SHORTCUT_OPERATIONS},
    'gdm-standard-session-open': 'Opening the ordinary account desktop chooser',
    'gdm-standard-session-select-full': 'Choosing the offered ordinary full desktop',
    'gdm-standard-session-chosen': 'Observing the ordinary desktop chooser after selection',
    'gdm-standard-session-cancel': 'Cancelling the ordinary account sign-in choice',
    'gdm-station-session-open': 'Checking whether normal station entry offers a desktop choice',
    'gdm-station-session-select-full': 'Choosing a publicly offered station desktop',
    'gdm-station-session-chosen': 'Observing station entry after the public desktop choice',
    'gdm-station-full-desktop': 'Checking the station full desktop public controls',
    'child-natural-expiry-observe': 'Observing the active child app or its naturally owned lock',
    'child-natural-expiry-wrong-account-refused': 'Refusing natural-expiry work on the Parent account',
    'child-natural-expiry-activity': 'Using the owned child app while usable time remains',
    'child-natural-expiry-lock-ready': 'Checking the naturally locked input recipient',
    'child-natural-expiry-lock-result': 'Reading the owned lock after harmless normal input',
    'kiosk-diagnostic-error': 'Observing a real kiosk request failure under the owned engineering fault',
    'kiosk-diagnostic-exit': 'Leaving the unavailable request safely without submission or replay',
    'kiosk-diagnostic-report': 'Opening the kiosk error report through its public dismissal action',
    'kiosk-diagnostic-editor': 'Editing the real kiosk report and waiting for diagnostics without Send',
    'kiosk-diagnostic-privacy': 'Reading confined in-app privacy and preserving the unsent kiosk report',
    'kiosk-reminder-preview': 'Observing the installed kiosk reminder banner and literal countdown',
    'kiosk-reminder-preview-cancel': 'Discarding the preview draft and observing banner closure',
    **{operation: 'Checking the bound Parent lock surface: ' + operation.removeprefix('parent-lock-')
       for operation in accessible_ui.LOCK_SURFACE_OPERATIONS},
    **{operation: 'Checking the installed restart notice: ' + surface + ' / ' + action
       for operation, (surface, action) in accessible_ui.RESTART_OPERATIONS.items()},
    'parent-about-information': 'Reading installed product, version and legal information',
    'overlay-about-summary': 'Reading overlay product, version and legal information',
    **{operation: 'Setting or reading the owned daily allowance through its API: ' + phase
       for operation, (_value, phase) in accessible_ui.ALLOWANCE_KEYBOARD_OPERATIONS.items()},
    'parent-child-picker-ready': 'Checking the owned Parent child selector is available',
    **{operation: 'Selecting the declared child through its canonical UID'
       for operation in accessible_ui.PRESENTED_PICKER_OPERATIONS},
    **{operation: 'Observing the initial request station without automatic language setup: ' +
       operation.removeprefix('kiosk-initial-') for operation in accessible_ui.INITIAL_KIOSK_OPERATIONS},
    'station-initial-entry': 'Observing fresh station entry before any first-run handler',
    'chinese-standard-desktop': 'Observing the renewed Chinese child desktop',
    'overlay-shell-cancel-ready': 'Qualifying the real Shell request and fresh Cancel recipient',
    'overlay-shell-dismissed': 'Independently requiring Shell challenge disappearance',
    'overlay-shell-open': 'Opening and qualifying the declared Shell approval challenge',
    'overlay-shell-qualified': 'Freshly qualifying the Shell password recipient',
    'overlay-shell-rechecked': 'Rechecking the same empty Shell password recipient',
    'overlay-shell-submit-ready': 'Guarding one submission to the filled Shell challenge',
    'overlay-approval-success': 'Reading explicit approval before automatic overlay exit',
    'overlay-approval-immediate': 'Reading explicit approval and taking the owned immediate exit',
    **{operation: 'Qualifying the wrong-password Shell challenge: ' +
       operation.removeprefix('overlay-shell-rejection-')
       for operation in accessible_ui.SHELL_REJECTION_ORDER},
    **{operation: 'Checking the intended child graphical login recipient'
       for operation in accessible_ui.CHILD_GREETER_OPERATIONS},
    'fresh-child-desktop': 'Independently observing the usable intended child desktop',
    'child-retained-unlock-diagnostic': 'Diagnosing the retained child desktop without input',
    'child-countdown-present': 'Reading the child desktop countdown',
    'child-countdown-absent': 'Requiring stable countdown absence on the child desktop',
    **{'child-countdown-session-' + state: label for state, label in (
        ('pin', 'Binding the countdown observer to the child desktop'),
        ('locked', 'Checking countdown unavailability while the child is locked'),
        ('greeter', 'Checking the retained child countdown at sign-in'),
        ('restored', 'Checking the same child countdown after sign-in'))},
    'child-countdown-wrong-account-refused': 'Refusing countdown observation on another account',
    'child-countdown-animation-read': 'Reading the child countdown animation preference',
    'child-countdown-animation-on': 'Enabling the child countdown animation preference',
    'child-countdown-animation-off': 'Disabling the child countdown animation preference',
    'child-countdown-animation-wrong-account-refused': 'Refusing countdown preference input on another account',
    'gdm-child-time-denied': 'Observing the intended child’s specific time-limit rejection',
    'gdm-child-denied-return-ready': 'Reobserving the rejected child prompt before normal return',
    'gdm-child-denied-return-state': 'Checking the account list or a fresh empty child prompt after Cancel',
    'gdm-child-denied-returned': 'Observing the usable account list after rejection',
    **{operation: 'Reviewing the automatic Parent error report without sending it'
       for operation in accessible_ui.PARENT_REPORT_OPERATIONS},
    **{operation: 'Checking the owned app match editor and its independent public result'
       for operation in accessible_ui.MATCH_OPERATIONS},
    **{operation: 'Saving one app access choice and independently reading its public row'
       for operation in accessible_ui.ACCESS_OPERATIONS},
    **{operation: 'Reading the complete public app access and matching legend'
       for operation in accessible_ui.LEGEND_OPERATIONS},
    **{operation: 'Setting and independently reading a declared catalogue filter'
       for operation in accessible_ui.FILTER_OPERATIONS},
    **{operation: 'Checking the complete declared catalogue search result'
       for operation in accessible_ui.CATALOGUE_ROW_OPERATIONS},
    'catalogue-incomplete-refused': 'Refusing an incomplete catalogue result expectation',
    'catalogue-filter-wrong-child': 'Refusing catalogue filtering for a different child',
    'catalogue-filter-wrong-page': 'Refusing catalogue filtering outside App Limits',
    **{'existing-' + operation: 'Checking public App Limits rows for [Existing child]'
       for operation in accessible_ui.APP_ROW_OPERATIONS
       if operation.startswith('parent-app-rows')},
    'about-interval-read': 'Reading the already open About window and its public identity',
    'about-interval-refused': 'Refusing About read entry while only management is open',
    **{operation: 'Saving diagnostic output through the owned chooser: ' + operation
       for operation in accessible_ui.SAVE_OPERATIONS},
    'named-custom-setup': 'Setting the named child allowance to enabled zero',
    'named-custom-wrong-child-refused': 'Refusing custom input and trace for the wrong child',
    **{operation: 'Preparing or independently reading the owned Parent action'
       for operation in accessible_ui.ACCESSIBILITY_TRACE_OPERATIONS},
    'feedback-trace-sample': 'Observing the caller-owned synthetic feedback transition',
    **{operation: 'Comparing the file-bearing feedback draft across public review and return'
       for operation in accessible_ui.FILE_REVIEW_OPERATIONS},
    **{operation: 'Checking public attachment metadata and the declared attachment operation'
       for operation in accessible_ui.ATTACHMENT_OPERATIONS},
    **{operation: 'Checking declared attachment count and size boundaries: ' + operation
       for operation in accessible_ui.BOUNDARY_OPERATIONS},
    **{operation: 'Qualifying feedback file selection: ' + operation.removeprefix('chooser-')
       for operation in accessible_ui.CHOOSER_OPERATIONS},
    'parent-kiosk-about-refused': 'Refusing station About entry from Parent management',
    'kiosk-about-open': 'Opening About from the request station',
    'kiosk-about-read': 'Reading station product and legal information without external actions',
    'kiosk-preferences-confinement': 'Checking confined station Preferences pages and nested editors',
    'kiosk-about-close-ready': 'Rechecking the active station About dialog before closing',
    'kiosk-about-closed': 'Observing About closed and the request station returned',
    'parent-overlay-about-refused': 'Refusing overlay About entry from Parent management',
    'overlay-about-open': 'Opening the child overlay About window',
    'overlay-license-read': 'Reading overlay product/version and clickable license without activation',
    'overlay-website-read': 'Checking the owned overlay website link without activation',
    'overlay-privacy-read': 'Checking the owned overlay privacy link without activation',
    'overlay-support-read': 'Checking the owned overlay support link without activation',
    'overlay-legal-notices-read': 'Checking the owned overlay legal link without activation',
    'overlay-help-read': 'Checking the child-owned Help action without activation',
    'overlay-information-about': 'Opening overlay About from its owned Help menu',
    'overlay-about-close-ready': 'Rechecking the active child-owned About before closing',
    'overlay-about-closed': 'Observing About absent and the unchanged child form returned',
    'overlay-about-refused': 'Refusing license reading while overlay About is absent',
    'multiple-other-enable': 'Enabling screen limits for the second declared child',
    'multiple-other-saved': 'Reading saved screen limits for the second declared child',
    'multiple-isolation-child': 'Selecting the unavailable child while retaining the approving parent',
    **{operation: 'Checking the exact offered account set and declared selection'
       for operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS if operation.startswith('multiple-')},
    'parent-mate-refused': 'Refusing kiosk authentication entry from Parent management',
    **{operation: 'Qualifying MATE request context, guarded Cancel and unchanged form return'
       for operation in accessible_ui.MATE_OPERATIONS},
    'parent-kiosk-valid-refused': 'Refusing kiosk duration input from Parent management',
    'parent-kiosk-invalid-refused': 'Refusing kiosk Request input from Parent management',
    **{operation: 'Checking invalid kiosk duration: ' + binding + ' / ' + action
       for operation, (binding, action) in accessible_ui.KIOSK_INVALID_OPERATIONS.items()},
    **{operation: 'Choosing and independently reading valid kiosk duration and app access'
       for operation in accessible_ui.KIOSK_VALID_OPERATIONS},
    **{operation: 'Choosing and independently reading valid fixed-child overlay values'
       for operation in accessible_ui.OVERLAY_VALID_OPERATIONS},
    **{operation: 'Checking invalid overlay text, preserved form and absence of authentication'
       for operation in accessible_ui.OVERLAY_INVALID_OPERATIONS},
    **{operation: 'Observing usable child app activity around the request overlay'
       for operation in accessible_ui.OVERLAY_NATIVE_OPERATIONS},
    **{operation: 'Reading idle Revoke availability and zero remaining balances'
       for operation in accessible_ui.REVOKE_DISABLED_OPERATIONS},
    **{operation: 'Reading and cancelling the owned revocation warning without changing time'
       for operation in accessible_ui.REVOKE_CANCEL_OPERATIONS},
    **{operation: 'Confirming revocation and independently reading saved policy and time'
       for operation in accessible_ui.REVOKE_CONFIRM_OPERATIONS},
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
    'gdm-product-free-standard-list': 'Reading the product-free standard-account greeter list',
    'gdm-product-free-standard-focused': 'Checking the product-free standard account is focused',
    'gdm-product-free-child-list': 'Reading the child greeter list after product removal',
    'gdm-product-free-child-focused': 'Checking the child account is focused after product removal',
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
    'shell-search-wrong-result-refused': 'Refusing an unrelated search result binding',
    'shell-search-dismissed': 'Checking search closed and the desktop returned',
    'app-grid': 'Finding the launchable Parent result in public app search',
    'parent-window': 'Waiting for the Parent window',
    'parent-window-count': 'Counting the owned Parent management windows',
    'parent-new-window-absent': 'Checking a new Parent window can be opened',
    'parent-new-window-refused': 'Refusing new-window entry while Parent remains open',
    'parent-restart-ready': 'Checking the active Parent window for normal closure',
    'parent-restart-closed-refused': 'Refusing restart when Parent is already closed',
    'parent-restart-wrong-refused': 'Refusing a different named window for Parent restart',
    'parent-initial-selection': 'Reading the reopened Parent initial child selection',
    'parent-command-launch': 'Invoking the Parent command as [Parent user]',
    'standard-parent-command-launch': 'Invoking the Parent command as [Standard user]',
    'child-command-launch': 'Invoking the child overlay command as [Child user]',
    'overlay-panel-ready': 'Checking the child panel request control',
    'overlay-panel-launch': 'Activating the child request action through its API',
    'overlay-panel-reveal-ready': 'Checking the open overlay before revealing its panel',
    'overlay-panel-overview': 'Checking Overview before returning to the open overlay',
    'overlay-request-form': 'Reading one overlay with the fixed child account',
    'overlay-qualification-cancel': 'Closing the qualification overlay with Cancel',
    'overlay-desktop': 'Checking the overlay closed and child desktop returned',
    'overlay-wrong-account-refused': 'Refusing overlay entry from another account',
    'standard-parent-closed': 'Checking denial dismissal returns to the standard desktop',
    'parent-empty': 'Checking the explanation for no eligible children',
    'child-picker-opened': 'Selecting [Child user] through the Parent API',
    'child-choice-highlighted': 'Reading the selected [Child user] identity',
    'parent-selected': 'Checking the selected child and displayed settings',
    'parent-screen-page': 'Returning to Screen Limits and reading settings',
    'parent-apps-page': 'Opening App Limits and checking its controls',
    'parent-page-wrong-child-refused': 'Refusing page input for a different child',
    'about': 'Opening About and reading product information',
    'about-rechecked': 'Rechecking owned About information',
    'license': 'Checking the license link is clickable without following it',
    'license-provider-refusals': 'Rechecking the clickable license link',
    'website-clickable': 'Checking the website link is clickable without following it',
    'privacy-clickable': 'Checking the privacy link is clickable without following it',
    'support-clickable': 'Checking the support link is clickable without following it',
    'parent-help-clickable': 'Checking Help is clickable without following it',
    'parent-information-about': 'Opening About from the owned Help menu',
    'parent-information-clickable': 'Checking all offered About links without following them',
    'license-closed': 'Checking About remains open after link inspection',
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
    'new-child-picker-opened': 'Selecting [New child] through the Parent API',
    'new-child-choice-highlighted': 'Reading the selected [New child] identity',
    'new-child-selected': 'Checking the selected new child and displayed settings',
    'existing-child-picker-opened': 'Selecting [Existing child] through the Parent API',
    'existing-child-choice-highlighted': 'Reading the selected [Existing child] identity',
    'existing-returned': 'Checking the returned existing child and displayed settings',
    'existing-apps': 'Reading App Limits for [Existing child]',
    'new-child-apps': 'Reading App Limits for [New child]',
    'new-child-screen': 'Reading screen-time settings for [New child]',
    'discovery-child-picker-opened': 'Selecting [Existing child] through the Parent API',
    'discovery-child-choice-highlighted': 'Reading the selected [Existing child] identity',
    'discovery-selected': 'Checking existing-child settings and remaining time',
    'standard-desktop': 'Waiting for the standard-account desktop',
    'standard-system-prompt': 'Checking for a login-keyring prompt',
    'standard-app-grid': 'Opening public app search',
    'standard-search-focused': 'Checking the app search field is focused',
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
    'gdm-station-refused': 'Reading sign-in after the request station was refused',
    'kiosk-request-form': 'Reading the request-station form and unavailable controls',
    'kiosk-lifecycle-defaults': 'Reading the request-station defaults after the lifecycle transition',
    'kiosk-restriction-ready': 'Checking and focusing the request station before an ordinary shortcut',
    'kiosk-restriction-read': 'Verifying the station remains request-only after an ordinary shortcut',
    'kiosk-restriction-prepared-ready': 'Checking and focusing the prepared request before an ordinary shortcut',
    'kiosk-restriction-prepared-read': 'Verifying station restrictions and preserved request choices after an ordinary shortcut',
    'kiosk-disabled-child-select': 'Selecting the disabled child in the request station',
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
    'feedback-collection-ready': 'Waiting for finished diagnostics and available Download',
    'feedback-close': 'Closing the owned feedback dialog',
    'feedback-wrong-entry': 'Refusing a feedback read outside its dialog',
    'feedback-reopen': 'Independently opening Parent feedback again',
    'feedback-reread': 'Comparing the independently observed synthetic draft',
    'feedback-finished': 'Closing feedback after read qualification',
})


OPERATION_LABELS.update({operation: 'Replacing and reading a declared nonsecret field value'
                         for operation in accessible_ui.TEXT_OPERATIONS})
OPERATION_LABELS.update({operation: 'Checking native app launch and ordinary draft submission: ' + operation
                         for operation in accessible_ui.NATIVE_APP_OPERATIONS})
OPERATION_LABELS.update({operation: 'Checking declared baseline native access and usable results'
                         for operation in accessible_ui.BASELINE_NATIVE_BINDINGS})
OPERATION_LABELS.update({operation: 'Using and independently reading the Parent native activity'
                         for operation in accessible_ui.PARENT_NATIVE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Setting and reading doubled synthetic editor text'
                         for operation in accessible_ui.DUPLICATE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Applying and independently reading synthetic range formatting'
                         for operation in accessible_ui.FORMAT_OPERATIONS})
OPERATION_LABELS.update({operation: 'Reading feedback block meaning and associated synthetic text'
                         for operation in accessible_ui.block_semantics.OPERATIONS})
OPERATION_LABELS.update({operation: 'Applying and reading all feedback formats, links and removal'
                         for operation in accessible_ui.feedback_formats.OPERATIONS})
OPERATION_LABELS.update({operation: 'Comparing the formatted draft, reply address and selected file'
                         for operation in accessible_ui.DRAFT_OPERATIONS})
OPERATION_LABELS.update({operation: 'Qualifying invalid-only feedback input and public rejection'
                         for operation in accessible_ui.REJECTION_OPERATIONS})
OPERATION_LABELS.update({operation: 'Qualifying exact UTF-16 boundary drafts without valid submission'
                         for operation in accessible_ui.LENGTH_OPERATIONS})
OPERATION_LABELS.update({operation: 'Appending and reading one declared Unicode scalar'
                         for operation in accessible_ui.SCALAR_OPERATIONS})
OPERATION_LABELS.update({operation: 'Finishing and reading a declared synthetic fixture'
                         for operation in accessible_ui.SUFFIX_OPERATIONS})
OPERATION_LABELS.update({operation: 'Returning to an existing window and reading its retained public state'
                         for operation in accessible_ui.WINDOW_SWITCH_OPERATIONS})
OPERATION_LABELS.update({operation: 'Reading the existing Parent window, child, page and saved settings'
                         for operation in accessible_ui.RETAINED_PARENT_OPERATIONS})
OPERATION_LABELS.update({operation: 'Qualifying kiosk approval and its explicit public result'
                         for operation in accessible_ui.MATE_APPROVAL_OPERATIONS})
OPERATION_LABELS.update({operation: 'Preparing and independently reading the Chinese Jordan request'
                         for operation in accessible_ui.CHINESE_VALID_BINDINGS})
OPERATION_LABELS.update({operation: 'Preparing and independently reading the Jordan request'
                         for operation in accessible_ui.JORDAN_VALID_BINDINGS})
OPERATION_LABELS.update({operation: 'Saving or independently observing the persisted Chinese kiosk language'
                         for operation in accessible_ui.CHINESE_LANGUAGE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Reading or changing the owned Parent language through public controls'
                         for operation in accessible_ui.PARENT_LANGUAGE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Reading inherited Parent dialog text and retained synthetic draft'
                         for operation in accessible_ui.PARENT_DIALOG_BINDINGS})
RESPONSE_BYTE_LIMITS.update({operation: 32768
                            for operation in accessible_ui.PARENT_LANGUAGE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Reading or changing the owned kiosk language through public controls'
                         for operation in accessible_ui.KIOSK_LANGUAGE_OPERATIONS})
OPERATION_LABELS['kiosk-language-policy'] = 'Comparing Jordan policy and balances in Parent'
OPERATION_LABELS['kiosk-language-policy-restored'] = 'Restoring and independently reading Jordan policy in Parent'
OPERATION_LABELS['kiosk-riley-language-policy'] = 'Comparing Riley policy and balances in Parent'
OPERATION_LABELS['kiosk-language-account-refusals'] = 'Refusing wrong-child and mismatched language input'
OPERATION_LABELS.update({operation: 'Selecting the declared kiosk account with independent language readback'
                         for operation in accessible_ui.KIOSK_LANGUAGE_ACCOUNTS})
RESPONSE_BYTE_LIMITS.update({operation: 32768 for operation in
                           accessible_ui.KIOSK_LANGUAGE_OPERATIONS | set(accessible_ui.KIOSK_LANGUAGE_POLICIES)})
OPERATION_LABELS.update({operation: 'Reading or changing Riley overlay language through public controls'
                         for operation in accessible_ui.OVERLAY_LANGUAGE_OPERATIONS})
OPERATION_LABELS.update({operation: 'Preserving the declared multilingual request through public controls'
                         for operation in accessible_ui.LANGUAGE_HISTORY_REQUESTS})
RESPONSE_BYTE_LIMITS.update({operation: 32768 for operation in accessible_ui.LANGUAGE_HISTORY_REQUESTS})
OPERATION_LABELS['overlay-language-policy'] = 'Comparing Riley saved policy in Parent'
OPERATION_LABELS.update({operation: 'Editing or reading Riley reminders through public Preferences'
                        for operation in accessible_ui.OVERLAY_REMINDER_OPERATIONS})
RESPONSE_BYTE_LIMITS.update({operation: 32768
                            for operation in accessible_ui.OVERLAY_REMINDER_OPERATIONS})
OPERATION_LABELS.update({operation: 'Preserving selected-child reminders across request surfaces'
                        for operation in (set(accessible_ui.BINDING_REMINDER_OPERATIONS) |
                                          set(accessible_ui.BINDING_REMINDER_SELECTIONS))})
RESPONSE_BYTE_LIMITS.update({operation: 32768
                            for operation in accessible_ui.BINDING_REMINDER_OPERATIONS})
OPERATION_LABELS.update({operation: 'Transferring child choices between the overlay and request station: ' + operation
                        for operation in accessible_ui.TRANSFER_OPERATIONS})
RESPONSE_BYTE_LIMITS.update({operation: 32768 for operation in
                           accessible_ui.OVERLAY_LANGUAGE_OPERATIONS | {'overlay-language-policy'}})
OPERATION_LABELS.update({
    'text-wrong-entry': 'Refusing text input outside feedback',
    'text-disabled': 'Refusing text input to a disabled control',
})

OPERATION_LABELS.update({operation: 'Reading privacy and comparing the synthetic feedback draft'
                         for operation in accessible_ui.FEEDBACK_PRIVACY_OPERATIONS})
OPERATION_LABELS.update({
    **{operation: 'Reading validation and Send availability after declared feedback edits'
       for operation in accessible_ui.FEEDBACK_STATE_PROJECTIONS},
    'feedback-state-close': 'Closing the synthetic feedback dialog before independent entry',
    'feedback-state-wrong-entry': 'Refusing a validation snapshot outside feedback',
    'feedback-state-reopen': 'Reopening feedback and independently reading validation and Send',
})


@dataclass(frozen=True)
class FeedbackStateObservation:
    draft: str
    validation: str
    send_enabled: bool

    @classmethod
    def from_value(cls, value):
        require(type(value) is dict and set(value) == {
            'draft', 'attachments', 'collection', 'validation', 'controls', 'send_enabled'}
            and value['draft'] in accessible_ui.FEEDBACK_PROJECTIONS
            and value['attachments'] == ['diagnostic-logs.zip']
            and value['collection'] == 'ready' and value['controls'] == 'ready'
            and value['validation'] in accessible_ui.FEEDBACK_VALIDATION.values()
            and type(value['send_enabled']) is bool, 'ui:feedback-state-response')
        return cls(value['draft'], value['validation'], value['send_enabled'])


@dataclass(frozen=True)
class FeedbackObservation:
    draft: str
    attachments: tuple
    collection: str
    validation: str
    controls: str

    @classmethod
    def from_value(cls, value):
        require(type(value) is dict and type(value.get('draft')) is str
                and value['draft'] in accessible_ui.FEEDBACK_PROJECTIONS and value == {
            'draft': value['draft'], 'attachments': ['diagnostic-logs.zip'],
            'collection': 'ready', 'validation': 'none', 'controls': 'ready'},
            'ui:feedback-response')
        return cls(value['draft'], ('diagnostic-logs.zip',), 'ready', 'none', 'ready')


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
class AppActivityObservation:
    """APP04 immutable public window identity and recognizable native activity."""

    binding: str
    pid: int
    endpoint: tuple
    state: tuple

    @classmethod
    def from_value(cls, value):
        require(type(value) is dict and set(value) == {'binding', 'pid', 'endpoint', 'state'}
                and value['binding'] == 'native-primary'
                and type(value['pid']) is int and value['pid'] > 0
                and type(value['endpoint']) is list and len(value['endpoint']) == 2
                and all(type(part) is str and 0 < len(part) <= 256 for part in value['endpoint'])
                and value['endpoint'][0].startswith(':') and value['endpoint'][1].startswith('/')
                and type(value['state']) is dict and value['state'] == {
                    'draft': 'ONPC fixture draft', 'submitted': 'ONPC fixture draft',
                    'score': 'Moves: 0; token: 0'}, 'ui:app-activity')
        return cls(value['binding'], value['pid'], tuple(value['endpoint']),
                   tuple(value['state'][key] for key in ('draft', 'submitted', 'score')))


def compare_app_activity(observed, expected, *, result='same'):
    """UI12: compare explicit observations; replacement never proves retention."""
    require(type(observed) is AppActivityObservation and type(expected) is AppActivityObservation
            and result in ('same', 'replaced'), 'ui:app-comparison-binding')
    same_window = (observed.binding, observed.pid, observed.endpoint) == (
        expected.binding, expected.pid, expected.endpoint)
    require(same_window if result == 'same' else not same_window, 'ui:app-window-changed')
    require(observed.state == expected.state, 'ui:app-activity-changed')
    return {'same_window': same_window, 'activity_unchanged': True, 'outcome': 'passed'}


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
        invalid = accessible_ui.INVALID_REQUEST_OPERATIONS.get(operation)
        require(type(observation.surface) is str and type(observation.form_count) is int
                and type(observation.child) is str and type(observation.approver) is str
                and (type(observation.duration_seconds) is int or (
                    invalid is not None and observation.duration_seconds is None))
                and (observation.custom_text is None or observation.custom_text == '1.25'
                     or operation in ('kiosk-long-included-duration-select',
                         'overlay-long-approver-select', 'overlay-long-request-read')
                     and observation.custom_text == '10'
                     or operation in accessible_ui.KIOSK_VALID_REQUESTS
                     and operation.startswith('kiosk-long-request-') and observation.custom_text == '10'
                     or operation in accessible_ui.PROFILE_REQUESTS
                     and observation.custom_text == accessible_ui.PROFILE_REQUESTS[operation][1]
                     or operation in accessible_ui.TRANSFER_REQUESTS and observation.custom_text == '2.5'
                     or invalid is not None and observation.custom_text ==
                     accessible_ui.KIOSK_INVALID_VALUES[invalid[0]])
                and all(type(getattr(observation, field)) is bool for field in (
                    'allow_soft', 'child_selector_enabled', 'approver_selector_enabled',
                    'duration_enabled', 'soft_choice_enabled', 'request_enabled',
                    'cancel_enabled'))
                and type(observation.message) is str and observation.mute is None,
                'ui:request')
        if operation in accessible_ui.TRANSFER_REQUESTS:
            overlay, child, _action = accessible_ui.TRANSFER_OPERATIONS[operation]
            seconds, custom, soft, approver = accessible_ui.TRANSFER_REQUESTS[operation]
            require(observation == cls(
                surface='child-overlay' if overlay else 'kiosk', form_count=1,
                child=accessible_ui.CHILD_IDENTITIES[child],
                approver=accessible_ui.APPROVER_IDENTITIES[approver], duration_seconds=seconds,
                custom_text=custom, allow_soft=soft, child_selector_enabled=not overlay,
                approver_selector_enabled=True, duration_enabled=True, soft_choice_enabled=True,
                request_enabled=True, cancel_enabled=True, message='', mute=None), 'ui:request')
            return observation
        overlay_valid = (operation in accessible_ui.OVERLAY_VALID_REQUESTS
                         or operation in accessible_ui.OVERLAY_INVALID_OPERATIONS)
        valid = {**accessible_ui.KIOSK_VALID_REQUESTS,
                 **accessible_ui.JORDAN_VALID_REQUESTS,
                 **accessible_ui.CHINESE_VALID_REQUESTS,
                 **accessible_ui.OVERLAY_VALID_REQUESTS}.get(operation)
        if operation == 'kiosk-lifecycle-defaults':
            require(observation.child in accessible_ui.CHILD_IDENTITIES.values()
                    and observation.approver in accessible_ui.APPROVER_IDENTITIES.values(), 'ui:request')
            require(observation == cls(surface='kiosk', form_count=1,
                child=observation.child, approver=observation.approver, duration_seconds=1800,
                custom_text=None, allow_soft=False, child_selector_enabled=True,
                approver_selector_enabled=False, duration_enabled=False, soft_choice_enabled=False,
                request_enabled=False, cancel_enabled=True, message='screen-limit-disabled', mute=None),
                'ui:request')
            return observation
        if operation == 'overlay-request-form':
            require(observation == cls(
                surface='child-overlay', form_count=1, child='fixture-child',
                approver='other-fixture-parent', duration_seconds=1800, custom_text=None,
                allow_soft=False, child_selector_enabled=False,
                approver_selector_enabled=True, duration_enabled=True,
                soft_choice_enabled=True, request_enabled=True, cancel_enabled=True,
                message='', mute=None), 'ui:request')
            return observation
        if operation in accessible_ui.LANGUAGE_HISTORY_REQUESTS:
            overlay, child, _language, approver, action = accessible_ui.LANGUAGE_HISTORY_REQUESTS[operation]
            if action in ('riley', 'jordan'):
                child = accessible_ui.CHILD if action == 'riley' else accessible_ui.EXISTING_CHILD
            require(action in ('form', 'approver', 'riley', 'jordan') and observation == cls(
                surface='child-overlay' if overlay else 'kiosk', form_count=1,
                child=accessible_ui.CHILD_IDENTITIES[child],
                approver=accessible_ui.APPROVER_IDENTITIES[approver], duration_seconds=75,
                custom_text='1.25', allow_soft=True, child_selector_enabled=not overlay,
                approver_selector_enabled=True, duration_enabled=True, soft_choice_enabled=True,
                request_enabled=True, cancel_enabled=True, message='', mute=None), 'ui:request')
            return observation
        if operation in accessible_ui.BINDING_REMINDER_SELECTIONS:
            field, target, child = accessible_ui.BINDING_REMINDER_SELECTIONS[operation]
            child = target if field == 'child' else child
            require(observation.approver in accessible_ui.APPROVER_IDENTITIES.values()
                    and (field != 'approver' or observation.approver ==
                         accessible_ui.APPROVER_IDENTITIES[target]), 'ui:request')
            require(observation == cls(surface='kiosk', form_count=1,
                child=accessible_ui.CHILD_IDENTITIES[child], approver=observation.approver,
                duration_seconds=1800, custom_text=None, allow_soft=False,
                child_selector_enabled=True, approver_selector_enabled=True,
                duration_enabled=True, soft_choice_enabled=True, request_enabled=True,
                cancel_enabled=True, message='', mute=None), 'ui:request')
            return observation
        enabled = operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS or valid is not None or invalid is not None
        require(enabled or operation in accessible_ui.KIOSK_OPERATIONS
                or operation in accessible_ui.KIOSK_DISABLED_REQUESTS, 'ui:request-operation')
        child, approver = {**accessible_ui.KIOSK_ACCOUNT_REQUESTS,
                           **accessible_ui.KIOSK_DISABLED_REQUESTS}.get(
            operation, ('existing-fixture-child', 'other-fixture-parent'))
        no_child = operation == 'kiosk-no-child-form'
        if valid is not None or invalid is not None:
            child, approver = 'fixture-child', 'fixture-parent'
            if operation in accessible_ui.CHINESE_VALID_REQUESTS or operation in accessible_ui.JORDAN_VALID_REQUESTS:
                child = 'existing-fixture-child'
        no_approver = operation == 'kiosk-no-approver-form'
        if no_child:
            child = 'none'
        if no_approver:
            approver = 'none'
        require(observation == cls(
            surface='child-overlay' if overlay_valid else 'kiosk', form_count=1, child=child,
            approver=approver, duration_seconds=None if invalid else valid[0] if valid else 1800,
            custom_text=accessible_ui.KIOSK_INVALID_VALUES[invalid[0]] if invalid else valid[1] if valid else None,
            allow_soft=valid[2] if valid else False, child_selector_enabled=not overlay_valid,
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
        self.trace = None
        self.trace_failed = False
        self._trace_clock = time.monotonic
        self.trace_sink = lambda token, index, sample: None
        self.accessibility_trace = None

    def observe_accessibility_input(self, operation, terminal, mode='checked', *, worker_input=None, child=None):
        """Prepare the owned input once, then independently observe its result.

        Save acceptance reads the settled API value. Collection diagnostics
        retain independent bounded reads of their public controls.
        """
        custom = mode == 'custom-save'
        collection = mode == 'collection'
        require(child is None or (custom and child in accessible_ui.NAMED_CUSTOM_CHILDREN),
                'ui:custom-child-binding')
        require((collection and operation == 'feedback-collection-open' and terminal is True
                 and worker_input is None) or
                (custom and operation == 'parent-custom-trace-focus' and terminal == 6
                 and worker_input is None) or
                (operation == 'parent-toggle-enabled' and terminal is True and
                 mode in ('checked', 'save') and worker_input is None),
                'ui:trace-input-binding')
        require(not self.trace_failed and self.trace is None and
                self.accessibility_trace is None, 'ui:trace-previous-failure')
        token = secrets.token_hex(16)
        trace = {'token': token, 'ready': False, 'input': False,
                 'started': self._trace_clock(), 'operation': operation, 'mode': mode,
                 'worker_input': worker_input, 'child': child}
        self.accessibility_trace = trace
        try:
            with watch_activity.operation('Preparing one declared Parent input and reading its result'):
                result = self._observe('feedback-collection-events' if collection else
                                       'parent-custom-events' if custom else 'parent-save-events' if mode == 'save'
                                       else 'parent-checked-events', **({'child': child} if child else {}))
            require(trace['ready'] and trace['input'] and
                    self._trace_clock() - trace['started'] < 60, 'ui:trace-incomplete')
            value = result['trace']
            require(value['token'] == token and value['source'] == trace['source'],
                    'ui:trace-token')
            if mode in ('save', 'custom-save'):
                saved = self._observe('parent-custom-saved-result' if custom else 'parent-saved-result',
                                      **({'child': child} if child else {}))['trace']
                self.trace_sink(token, 1, saved)
                return {'operation': 'parent-custom-save-trace' if custom else 'parent-save-trace',
                        'outcome': 'passed', 'interface': 'ApplicationUI', 'token': token,
                        'terminal': terminal, 'saved': saved}
            for index, sample in enumerate(value['samples'], 1):
                self.trace_sink(token, index, sample)
            return {'operation': ('feedback-collection-trace' if collection else
                                  'parent-custom-save-trace' if custom else 'parent-save-trace' if mode == 'save'
                                  else 'accessibility-input-trace'), 'outcome': 'passed',
                    'interface': 'ApplicationUI', 'token': token, 'terminal': terminal,
                    'samples': value['samples']}
        except BaseException:
            self.trace_failed = True
            raise
        finally:
            self.accessibility_trace = None

    def accessibility_ready(self, value):
        import re
        trace = self.accessibility_trace
        require(trace is not None and not trace['ready'] and
                type(value) is dict and set(value) == {
                    'event', 'token', 'source', 'boot_sha256', 'checked'} and
                value['event'] == 'accessibility-trace-ready' and
                value['token'] == trace['token'] and
                value['checked'] is (trace['mode'] == 'custom-save') and
                type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source']) and
                value['boot_sha256'] == self.boot_guard and bool(self.boot_guard) and
                self._trace_clock() - trace['started'] < 60, 'ui:trace-readiness')
        trace['ready'] = True
        trace['source'] = value['source']
        # Durable readiness is a prerequisite of input, not a later report.
        self.trace_sink(trace['token'], 0, dict(value))
        require(self._trace_clock() - trace['started'] < 60, 'ui:trace-deadline')
        trace['input'] = True  # Consume before the fallible action; never replay.
        self._observe(trace['operation'], **({'child': trace['child']} if trace.get('child') else {}))

    def _trace_sample(self):
        with watch_activity.operation('Reading one unchanged public feedback trace sample'):
            return self._observe('feedback-state-empty')

    def start_trace(self, binding=None):
        """UI25: bind empty feedback and a finite terminal before caller input."""
        require(not self.trace_failed, 'ui:trace-previous-failure')
        try:
            require(self.trace is None, 'ui:trace-duplicate')
            require(binding in (None, 'body-first', 'body-clear'), 'ui:trace-binding')
            started = self._trace_clock()
            value = (self._observe('feedback-state-no-reply') if binding == 'body-clear'
                     else self._trace_sample())
            state = FeedbackStateObservation.from_value(value['feedback_state'])
            require(state == FeedbackStateObservation(
                'states-no-reply' if binding == 'body-clear' else 'initial-empty', 'none', True),
                    'ui:trace-entry')
            now = self._trace_clock()
            require(now < started + 60, 'ui:trace-deadline')
            token = secrets.token_hex(16)
            self.trace = {'token': token, 'started': started, 'deadline': started + 60,
                          'binding': binding, 'input_index': 0,
                          'boot': self.boot_proof, 'state': state,
                          'samples': [{'elapsed_ms': int((now - started) * 1000),
                                       'state': value['feedback_state']}]}
            self.trace_sink(token, 0, self.trace['samples'][0])
            return {'operation': 'feedback-trace-start', 'outcome': 'passed',
                    'interface': 'ApplicationUI+external-provider', 'token': token, 'ready': True}
        except BaseException:
            self.trace_failed = True
            self.trace = None
            raise

    def poll_trace(self):
        """Read-only pump in the worker rendezvous, including while it types.

        Sampling never authorizes or performs input. Only observed states are
        retained; no transient is inferred between these bounded reads.
        """
        require(not self.trace_failed, 'ui:trace-previous-failure')
        trace = self.trace
        if trace is None or trace['binding'] is None:
            return
        try:
            require(self._trace_clock() < trace['deadline'], 'ui:trace-deadline')
            value = self._observe('feedback-trace-sample')
            now = self._trace_clock()
            require(now < trace['deadline'], 'ui:trace-deadline')
            require(self.boot_proof == trace['boot'], 'ui:trace-boot')
            state = FeedbackStateObservation.from_value(value['feedback_state'])
            require(state.validation == 'none' and state.send_enabled,
                    'ui:trace-controls')
            elapsed = int((now - trace['started']) * 1000)
            require(elapsed >= trace['samples'][-1]['elapsed_ms'], 'ui:trace-order')
            require(len(trace['samples']) < 256, 'ui:trace-sample-limit')
            trace['samples'].append({'elapsed_ms': elapsed, 'state': value['feedback_state'],
                                    'input_index': trace['input_index']})
            self.trace_sink(trace['token'], len(trace['samples']) - 1, trace['samples'][-1])
        except BaseException:
            self.trace_failed = True
            self.trace = None
            raise

    def finish_trace(self, token, terminal=None):
        """UI26: consume exactly the caller's live token, never infer one."""
        require(not self.trace_failed, 'ui:trace-previous-failure')
        try:
            trace = self.trace
            require(trace is not None and type(token) is str and token == trace['token'],
                    'ui:trace-token')
            expected = FeedbackStateObservation(
                'initial-empty' if trace['binding'] == 'body-clear' else 'states-no-reply',
                'none', True)
            require(terminal == expected if trace['binding'] == 'body-clear' else
                    terminal is None or terminal == expected, 'ui:trace-predicate')
            if trace['binding'] is not None:
                self.poll_trace()
                require(trace['input_index'] == 3 and any(
                    sample.get('input_index') == 2 for sample in trace['samples']),
                    'ui:trace-input-unobserved')
                state = FeedbackStateObservation.from_value(trace['samples'][-1]['state'])
                require(state == expected,
                        'ui:trace-terminal')
                self.trace = None
                return {'operation': 'feedback-trace-finish', 'outcome': 'passed',
                        'interface': 'ApplicationUI+external-provider', 'token': token,
                        'terminal': trace['binding'] + '-ready', 'samples': trace['samples']}
            self.trace = None  # Consume before any fallible read; never replay.
            for _ in range(2):
                require(self._trace_clock() < trace['deadline'], 'ui:trace-deadline')
                value = self._trace_sample()
                now = self._trace_clock()
                require(now < trace['deadline'], 'ui:trace-deadline')
                require(self.boot_proof == trace['boot'], 'ui:trace-boot')
                require(FeedbackStateObservation.from_value(value['feedback_state']) == trace['state'],
                        'ui:trace-changed')
                elapsed = int((now - trace['started']) * 1000)
                require(elapsed >= trace['samples'][-1]['elapsed_ms'], 'ui:trace-order')
                trace['samples'].append({'elapsed_ms': elapsed, 'state': value['feedback_state']})
            return {'operation': 'feedback-trace-finish', 'outcome': 'passed',
                    'interface': 'ApplicationUI+external-provider', 'token': token,
                    'terminal': 'three-unchanged-samples', 'samples': trace['samples']}
        except BaseException:
            self.trace_failed = True
            self.trace = None
            raise

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

    def observe_shell_success(self, worker_input, *, operation='overlay-approval-success'):
        """Keep the owned observer live while releasing one guarded Enter."""
        require(operation in accessible_ui.SHELL_SUCCESS_OPERATIONS
                and callable(worker_input) and not getattr(self, 'shell_success_input', None),
                'ui:shell-input-binding')
        self.shell_success_input = worker_input
        self.shell_success_ready = False
        try:
            result = self.observe(operation)
            require(self.shell_success_ready, 'ui:shell-input-missing')
            return result
        except BaseException:
            self.challenge_failed = True
            raise
        finally:
            self.shell_success_input = None

    def shell_success_readiness(self, value):
        import time
        require(not self.challenge_failed and callable(getattr(self, 'shell_success_input', None))
                and not self.shell_success_ready
                and value == {'event': 'overlay-approval-ready',
                              'challenge_id': self.shell_approval_identity,
                              'boot_sha256': self.boot_guard}
                and bool(self.boot_guard)
                and time.monotonic() - self.shell_approval_checked < 30,
                'ui:shell-input-readiness')
        self.shell_success_ready = True  # Consume before durable publication.
        token = self.shell_approval_identity[:32]
        self.trace_sink(token, 0, value)
        require(time.monotonic() - self.shell_approval_checked < 30, 'ui:shell-stale-proof')
        self.shell_success_input(token, self.shell_approval_identity)

    def call(self, argv, operation, *, input=None):
        if operation in accessible_ui.RESTART_OPERATIONS and operation.endswith('-reboot'):
            return self.restart_call(argv, operation, input=input), []
        # Overlay readback uses the same form reader and diagnostic stream as
        # the station, while retaining its separate child-session binding.
        form_diagnostics = (operation in accessible_ui.KIOSK_SESSION_OPERATIONS
                            or operation in accessible_ui.SHELL_PROMPT_OPERATIONS
                            or operation in accessible_ui.SHELL_APPROVAL_OPERATIONS
                            or operation in accessible_ui.OVERLAY_VALID_OPERATIONS
                            or operation in accessible_ui.OVERLAY_INVALID_OPERATIONS
                            or operation in accessible_ui.OVERLAY_LANGUAGE_OPERATIONS
                            or operation in accessible_ui.OVERLAY_REMINDER_OPERATIONS
                            or operation in accessible_ui.BINDING_REMINDER_OPERATIONS
                            or operation in accessible_ui.LANGUAGE_HISTORY_REQUESTS
                            or operation in accessible_ui.TRANSFER_OPERATIONS
                            or operation in ('overlay-request-form', 'overlay-panel-reveal-ready'))
        # Greeter startup: 300s identity + 20s bus + 45s UI, with transport
        # margin; still inside the worker's 420s checkpoint deadline.
        # Kiosk waits only for the public form, with transport margin.
        timeout = (120 if operation in accessible_ui.GDM_SESSION_OPERATIONS
                   or operation == 'gdm-station-full-desktop' else
                   390 if operation in accessible_ui.GREETER_OPERATIONS
                   or operation in accessible_ui.STATION_BRANCH_OPERATIONS else
                   120 if form_diagnostics else 90)
        event_trace = operation in ('parent-checked-events', 'parent-save-events', 'parent-custom-events',
                                    'feedback-collection-events')
        if (self.system_prompt is None and not form_diagnostics and not event_trace
                and self.accessibility_trace is None):
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
            limit = 131072 if form_diagnostics else 16384 if event_trace else 8192
            if operation in accessible_ui.APP_ROW_OPERATIONS:
                limit = max(limit, RESPONSE_BYTE_LIMITS.get(operation, 2048))
            require(received <= limit, 'ui:response-size')
            pending.extend(data)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                if type(value) is dict and value.get('event') == 'overlay-approval-ready':
                    require(operation in accessible_ui.SHELL_SUCCESS_OPERATIONS and not results,
                            'ui:shell-input-readiness')
                    self.shell_success_readiness(value)
                elif type(value) is dict and value.get('event') == 'accessibility-trace-ready':
                    require(event_trace and not results, 'ui:trace-readiness')
                    self.accessibility_ready(value)
                elif type(value) is dict and value.get('event') == 'kiosk-form-observation':
                    diagnostic_count += 1
                    require(form_diagnostics and not results and diagnostic_count <= 128,
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

    def submit_restart(self, surface):
        require(surface in ('parent', 'overlay', 'kiosk') and
                not getattr(self, 'restart_consumed', False) and
                self.boot_proof == self.boot_guard and bool(self.boot_guard), 'ui:restart-submission')
        self.restart_consumed = True
        with watch_activity.operation('Requesting one normal reboot through the installed notice'):
            return self._observe('restart-' + surface + '-reboot')

    def restart_call(self, argv, operation, *, input):
        """Only a qualified terminal mutation may survive an SSH disconnect."""
        surface = accessible_ui.RESTART_OPERATIONS[operation][0]
        qualified = {'event': 'restart-input-qualified', 'surface': surface,
                     'boot_sha256': self.boot_guard}
        acknowledged = {'surface': surface, 'status': 'acknowledged',
                        'boot_sha256': self.boot_guard}
        pending, records = bytearray(), []
        received = 0
        def output(data):
            nonlocal received
            received += len(data)
            require(received <= 4096, 'ui:restart-response-size')
            pending.extend(data)
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                require(len(records) < 2 and value == (qualified if not records else acknowledged),
                        'ui:restart-response')
                records.append(value)
        self.transport.call(argv, input=input, timeout=120, check=False, on_output=output)
        status = self.transport.commands.last_returncode
        # Preserve strict refusal, interrupt and ownership errors. A missing or
        # partial readiness record never authorizes accepting a lost receipt.
        require(not pending and records and status in (0, 255), 'ui:restart-submission-failed')
        require(len(records) == 2 or status == 255, 'ui:restart-receipt-missing')
        return json.dumps({'surface': surface,
            'status': 'acknowledged' if len(records) == 2 else 'uncertain',
            'boot_sha256': self.boot_guard}).encode()

    def observe_gdm_chooser(self, operation, lease):
        """Consume a fresh GDM focus proof once and independently read the result."""
        require(operation in accessible_ui.GDM_SESSION_OPERATIONS
                and not operation.endswith('-chosen'), 'ui:chooser-operation')
        checked = time.monotonic()
        result = UiObservations.observe(self, operation)
        choice = result['session_choice']
        disposition = choice['disposition']
        if disposition not in ('chooser-focused', 'choice-focused', 'cancel-focused'):
            return result
        with watch_activity.operation('Activating the freshly focused public sign-in control'):
            lease.guard()
            require(time.monotonic() - checked < 30, 'ui:chooser-stale-focus')
            try:
                lease.source.domain.sendKey(lease.source.api.VIR_KEYCODE_SET_LINUX,
                                            100, [28], 1, 0)
            finally:
                # An uncertain key is never replayed.
                lease.guard()
        if disposition == 'chooser-focused':
            result = UiObservations.observe(self, operation)
            require(result['session_choice']['disposition'] == 'chooser-opened',
                    'ui:chooser-not-opened')
        elif disposition == 'choice-focused':
            after = UiObservations.observe(self, operation.removesuffix('select-full') + 'chosen')
            require(after['session_choice']['disposition'] in (
                'choice-activated', 'no-public-chooser'), 'ui:chooser-choice-not-applied')
            result['session_choice'] = {**choice, 'disposition': 'choice-activated',
                'selected': after['session_choice']['selected'],
                'destination': after['session_choice']['destination']}
        else:
            UiObservations.observe(self, 'gdm-returned')
            result['session_choice'] = {**choice, 'disposition': 'cancelled',
                                        'destination': 'account-list'}
        return result

    def observe(self, operation, *, child=None):
        require(not getattr(self, 'language_failed', False), 'ui:language-previous-failure')
        import time
        trace = self.trace
        if trace is not None and trace['binding'] is not None and not self.trace_failed:
            order = tuple('text-' + trace['binding'] + '-' + suffix
                          for suffix in ('focus', 'selected', 'read'))
            index = trace['input_index']
            if index < len(order) and operation == order[index]:
                try:
                    value = self._observe(operation)
                    require(self.boot_proof == trace['boot'], 'ui:trace-boot')
                    require(self._trace_clock() < trace['deadline'], 'ui:trace-deadline')
                    trace['input_index'] += 1
                    return value
                except BaseException:
                    self.trace_failed = True
                    self.trace = None
                    raise
        if trace is not None or self.trace_failed:
            self.trace_failed = True
            self.trace = None
            require(False, 'ui:trace-intervening-operation')
        previous_operation = getattr(self, 'last_mate_operation', None)
        self.last_mate_operation = None
        self.pending_challenge = None
        self.approver_uids = None
        require(operation in accessible_ui.OPERATIONS, 'ui:operation')
        with watch_activity.operation(OPERATION_LABELS[operation]):
            try:
                if operation in accessible_ui.LOCK_RECIPIENT_OPERATIONS:
                    require(not getattr(self, 'lock_recipient_failed', False),
                            'ui:lock-recipient-previous-failure')
                    role = operation.split('-', 1)[0]
                    first = operation.endswith('-qualified')
                    require(self.last_operation == (role + '-lock-challenge' if first else
                            role + '-lock-recipient-qualified'), 'ui:lock-recipient-order')
                    if not first:
                        require(time.monotonic() - self.lock_recipient_checked < 30,
                                'ui:lock-recipient-stale-proof')
                    if first:
                        self.lock_recipient_checked = time.monotonic()
                shell_index = getattr(self, 'shell_approval_index', 0)
                if operation == 'overlay-shell-open' and getattr(self, 'shell_cancel_active', False):
                    require(getattr(self, 'shell_dismissed', False)
                            and previous_operation in ('overlay-valid-fraction-soft-read',
                                                       'overlay-fraction-estimate-refresh'),
                            'ui:shell-retry-entry')
                    self.shell_cancel_active = False
                if (operation == 'overlay-shell-open'
                        and getattr(self, 'shell_dismissed', False)
                        and previous_operation in ('overlay-valid-fraction-soft-read',
                                                   'overlay-fraction-estimate-refresh')
                        and (shell_index == 0 or getattr(self, 'shell_rejection', False)
                             and shell_index == len(accessible_ui.SHELL_REJECTION_ORDER))):
                    # A deliberate retry starts only after independently proved
                    # dismissal and preserved usable form. Challenge IDs remain
                    # globally single-use; no earlier recipient authority survives.
                    shell_index = 0
                    self.shell_dismissed = False
                if 0 < shell_index < len(accessible_ui.SHELL_APPROVAL_ORDER):
                    require(operation in accessible_ui.SHELL_APPROVAL_OPERATIONS,
                            'ui:shell-intervening-operation')
                if operation in accessible_ui.SHELL_APPROVAL_OPERATIONS:
                    require(not self.challenge_failed, 'ui:challenge-previous-failure')
                    if shell_index == 0:
                        self.shell_rejection = operation == accessible_ui.SHELL_REJECTION_ORDER[0]
                    order = (accessible_ui.SHELL_REJECTION_ORDER if getattr(self, 'shell_rejection', False) else
                             accessible_ui.SHELL_APPROVAL_ORDER)
                    if not getattr(self, 'shell_rejection', False) and operation == 'overlay-approval-immediate':
                        order = (*order[:-1], operation)
                    require(shell_index < len(order) and operation == order[shell_index],
                            'ui:shell-order')
                    if shell_index:
                        require(time.monotonic() - self.shell_approval_checked < 30,
                                'ui:shell-stale-proof')
                    self.shell_approval_index = shell_index + 1
                    self.shell_approval_checked = time.monotonic()
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
                    if (index == 4 and (
                            operation == 'kiosk-mate-open'
                            and previous_operation == 'kiosk-valid-fraction-soft-read'
                            or operation == 'kiosk-long-mate-open'
                            and previous_operation == 'kiosk-long-request-soft-read'
                            or operation in accessible_ui.PROFILE_MATE_REQUESTS
                            and operation.endswith('-mate-open')
                            and previous_operation == operation.removesuffix('-mate-open') + '-soft-read'
                            or operation == 'jordan-mate-open'
                            and previous_operation in ('jordan-fraction-soft-read',
                                                       'jordan-fraction-estimate-refresh'))):
                        index = 0
                    if index == 0:
                        self.mate_rejection = operation == accessible_ui.MATE_REJECTION_ORDER[0]
                        self.mate_chinese = operation == accessible_ui.CHINESE_MATE_ORDER[0]
                        self.mate_long_request = operation == accessible_ui.LONG_MATE_ORDER[0]
                        self.mate_jordan = operation == accessible_ui.JORDAN_MATE_ORDER[0]
                        self.mate_paused = operation == accessible_ui.PAUSE_MATE_ORDER[0]
                        self.mate_profile = accessible_ui.PROFILE_MATE_REQUESTS.get(operation)
                    if getattr(self, 'mate_chinese', False):
                        order = accessible_ui.CHINESE_MATE_ORDER
                    if getattr(self, 'mate_long_request', False):
                        order = accessible_ui.LONG_MATE_ORDER
                    if getattr(self, 'mate_profile', None):
                        order = accessible_ui.PROFILE_MATE_ORDERS[self.mate_profile['duration_seconds']]
                    if getattr(self, 'mate_jordan', False):
                        order = accessible_ui.JORDAN_MATE_ORDER
                    if getattr(self, 'mate_paused', False):
                        order = accessible_ui.PAUSE_MATE_ORDER
                    if self.mate_rejection:
                        order = accessible_ui.MATE_REJECTION_ORDER
                    elif operation == 'kiosk-mate-submit-immediate':
                        order = (*order[:3], operation)
                    require(index < len(order) and operation == order[index], 'ui:mate-order')
                    if index:
                        elapsed = time.monotonic() - self.mate_approval_checked
                        # The opening observation retains identity only. Its
                        # authority expires during TIME03; two newly observed
                        # recipient proofs are still required before input.
                        if getattr(self, 'mate_paused', False) and index == 1:
                            require(45 <= elapsed < 135, 'ui:mate-pause-bound')
                        else:
                            require(elapsed < 30, 'ui:mate-stale-proof')
                    self.mate_approval_index = index + 1
                    self.mate_approval_checked = time.monotonic()
                if operation in accessible_ui.MATE_OPERATIONS | accessible_ui.SHELL_PROMPT_OPERATIONS:
                    require(not self.challenge_failed, 'ui:challenge-previous-failure')
                read_started = time.monotonic_ns()
                result = self._observe(operation, **({'child': child} if child else {}))
                self.read_bounds = (read_started, time.monotonic_ns())
                if operation == accessible_ui.PAUSE_MATE_ORDER[0]:
                    self.mate_approval_checked = time.monotonic()
                if operation in ('revoke-balances', 'revoke-saved-balances', 'revoke-cleared-balances'):
                    result['revoke_cancel']['read_bounds'] = [read_started, time.monotonic_ns()]
                if operation in accessible_ui.COUNTDOWN_OPERATIONS:
                    result['countdown_read_bounds'] = list(self.read_bounds)
                if operation in accessible_ui.LOCK_RECIPIENT_OPERATIONS:
                    require(time.monotonic() - self.lock_recipient_checked < 30,
                            'ui:lock-recipient-stale-proof')
                    challenge_id = result['lock']['challenge_id']
                    if first:
                        self.lock_recipient_id = challenge_id
                    else:
                        require(challenge_id == self.lock_recipient_id, 'ui:lock-recipient-replaced')
                if operation == 'chinese-mate-open':
                    self.mate_approval_checked = time.monotonic()
                    self.chinese_returned = False
                if operation == 'gdm-station-returned' and getattr(self, 'mate_chinese', False):
                    require(self.mate_approval_index == 4, 'ui:mate-return-order')
                    self.chinese_returned = True
                if operation == 'chinese-persisted-form':
                    require(getattr(self, 'mate_chinese', False) and self.mate_approval_index == 4
                            and self.chinese_returned, 'ui:mate-fresh-session-order')
                    self.mate_approval_index = 0
                    self.chinese_returned = False
                if operation in ('overlay-shell-open', accessible_ui.SHELL_REJECTION_ORDER[0]):
                    # Opening includes request submission, prompt discovery and
                    # refusal qualification. It grants no password authority;
                    # age the forthcoming recipient proofs from this completed
                    # boundary, retaining their own acquisition-start clocks.
                    self.shell_approval_checked = time.monotonic()
                    self.shell_dismissed = False
                if operation == 'overlay-shell-dismissed':
                    self.shell_dismissed = True
                if operation == 'overlay-shell-cancel-ready':
                    self.shell_cancel_active = True
                    self.shell_dismissed = False
                self.last_mate_operation = operation
                return result
            except BaseException:
                if operation in accessible_ui.LOCK_RECIPIENT_OPERATIONS:
                    self.lock_recipient_failed = True
                if operation in (accessible_ui.PARENT_LANGUAGE_OPERATIONS |
                                 set(accessible_ui.PARENT_DIALOG_BINDINGS) |
                                 accessible_ui.KIOSK_LANGUAGE_OPERATIONS |
                                 accessible_ui.OVERLAY_LANGUAGE_OPERATIONS |
                                 accessible_ui.OVERLAY_REMINDER_OPERATIONS |
                                 set(accessible_ui.BINDING_REMINDER_OPERATIONS) |
                                 set(accessible_ui.BINDING_REMINDER_SELECTIONS) |
                                 set(accessible_ui.KIOSK_LANGUAGE_POLICIES) | {'overlay-language-policy'} |
                                 set(accessible_ui.KIOSK_LANGUAGE_ACCOUNTS) |
                                 set(accessible_ui.LANGUAGE_HISTORY_REQUESTS) | {'kiosk-language-account-refusals'}):
                    self.language_failed = True
                if operation in (accessible_ui.MATE_OPERATIONS | accessible_ui.MATE_APPROVAL_OPERATIONS
                                 | accessible_ui.SHELL_PROMPT_OPERATIONS | accessible_ui.SHELL_APPROVAL_OPERATIONS
                                 ) or 0 < getattr(self, 'shell_approval_index', 0) < len(accessible_ui.SHELL_APPROVAL_ORDER):
                    self.challenge_failed = True
                raise

    def observe_challenge(self, operation, challenge):
        """Two fresh same-challenge checks; no intervening operation or replay."""
        require(not self.challenge_failed, 'ui:challenge-previous-failure')
        try:
            require(type(challenge) is dict and set(challenge) == {
                'id', 'role', 'surface', 'check'} and challenge['surface'] == 'gdm'
                and challenge['role'] in ('parent', 'other-child', 'child')
                and challenge['check'] in ('qualified', 'rechecked')
                and type(challenge['id']) is str and bool(challenge['id']), 'ui:challenge')
            identity = (challenge['id'], challenge['role'], challenge['surface'])
            first = challenge['check'] == 'qualified'
            recipient = ('gdm-parent-recipient' if challenge['role'] == 'parent'
                         else 'gdm-child-recipient' if challenge['role'] == 'child'
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

    def _observe(self, operation, *, child=None):
        if operation in accessible_ui.RESTART_OPERATIONS and operation.endswith('-reboot'):
            require(getattr(self, 'restart_consumed', False), 'ui:restart-submission')
        initial_inputs = {'kiosk-initial-notice-close': 'kiosk-initial-notice',
                          'kiosk-initial-notice-return': 'kiosk-initial-notice-close',
                          'kiosk-initial-language-cancel': 'kiosk-initial-language'}
        if operation in initial_inputs:
            require(self.last_operation == initial_inputs[operation], 'ui:initial-input-order')
        if operation == 'chinese-persisted-form':
            require(getattr(self, 'mate_chinese', False) and self.mate_approval_index == 4
                    and getattr(self, 'chinese_returned', False), 'ui:mate-fresh-session-order')
        require(child is None or (child in accessible_ui.NAMED_CUSTOM_CHILDREN and
                operation in accessible_ui.NAMED_CHILD_OPERATIONS), 'ui:custom-child-binding')
        import re
        # Qualifications lack a scenario recorder, but use the same existing
        # spectator command pane as customer cases. Keep private program/stdin
        # and raw UI replies hidden; expose the fixed operation and its result.
        watch_activity.event('SSH UI: ' + OPERATION_LABELS[operation])
        if self.progress is not None:
            self.progress.operation(OPERATION_LABELS[operation])
        program = (system.ROOT / 'tests/e2e/accessible_ui.py').read_text()
        modules = 'import sys, types\n'
        # The public client is test-side code. Carry the same facade used by
        # previews even for product-free GDM observations before installation.
        # Every product value still comes from the live Application UI service.
        for package in ('common', 'common.oh_no_parent_control_ui'):
            modules += (f'module = types.ModuleType({package!r})\n'
                        f'module.__path__ = []\n'
                        f'sys.modules[{package!r}] = module\n')
        sources = {
            'common.oh_no_parent_control_ui.application_ui':
                'common/oh_no_parent_control_ui/application_ui.py',
            'common.oh_no_parent_control_ui.application_ui_client':
                'common/oh_no_parent_control_ui/application_ui_client.py',
            'application_ui_support': 'tests/support/application_ui.py',
            **{name: f'tests/e2e/{name}.py' for name in (
                'application_ui', 'session_control', 'public_atspi', 'block_semantics',
                'feedback_formats', 'download_destination', 'fixture_ui')},
        }
        for name, path in sources.items():
            source = (system.ROOT / path).read_text()
            modules += (f'module = types.ModuleType({name!r})\n'
                        f'module.__package__ = {name.rpartition(".")[0]!r}\n'
                        f'sys.modules[{name!r}] = module\n'
                        f'exec(compile({source!r}, {name + ".py"!r}, "exec"), module.__dict__)\n')
        program = modules + program
        version = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
        self.boot_proof = None
        binding = []
        if self.boot_guard is not None:
            import re
            require(type(self.boot_guard) is str and (self.boot_guard == '' or
                    re.fullmatch(r'[0-9a-f]{64}', self.boot_guard)), 'ui:boot-binding')
            binding = [self.boot_guard]
        if operation in accessible_ui.MATE_APPROVAL_OPERATIONS and operation not in (
                'kiosk-mate-open', 'kiosk-mate-rejection-open', 'chinese-mate-open', 'kiosk-long-mate-open',
                'kiosk-pause-mate-open', 'jordan-mate-open') and not (
                    operation in accessible_ui.PROFILE_MATE_REQUESTS and operation.endswith('-mate-open')):
            binding = [self.boot_guard or '', self.mate_approval_identity]
        if operation in accessible_ui.SHELL_APPROVAL_OPERATIONS and operation not in (
                'overlay-shell-open', accessible_ui.SHELL_REJECTION_ORDER[0]):
            binding = [self.boot_guard or '', self.shell_approval_identity]
        if operation == 'kiosk-reminder-preview-cancel':
            require(self.last_operation == 'kiosk-reminder-preview' and
                    hasattr(self, 'kiosk_reminder_source'), 'ui:kiosk-reminder-order')
            binding = [self.boot_guard or '', self.kiosk_reminder_source]
        if operation in accessible_ui.OVERLAY_REMINDER_MUTATIONS:
            source = getattr(self, 'overlay_reminder_source', None)
            require(type(source) is str and re.fullmatch(r'[0-9a-f]{64}', source),
                    'ui:reminder-source-required')
            binding = [self.boot_guard or '', source]
        if operation in accessible_ui.BINDING_REMINDER_MUTATIONS:
            source = getattr(self, 'binding_reminder_source', None)
            require(type(source) is str and re.fullmatch(r'[0-9a-f]{64}', source),
                    'ui:reminder-source-required')
            binding = [self.boot_guard or '', source]
        if operation == 'child-natural-expiry-activity':
            source = getattr(self, 'natural_expiry_source', None)
            require(type(source) is str and re.fullmatch(r'[0-9a-f]{64}', source),
                    'ui:natural-expiry-source')
            binding = [self.boot_guard or '', source]
        if operation in accessible_ui.COUNTDOWN_SESSION_OPERATIONS - {'child-countdown-session-pin'}:
            source = getattr(self, 'countdown_session_source', None)
            require(type(source) is str and re.fullmatch(r'[0-9a-f]{64}', source),
                    'ui:countdown-session-source')
            binding = [self.boot_guard or '', source]
        if operation.endswith(('natural-expiry-lock-ready', 'natural-expiry-lock-result')):
            require(hasattr(self, 'natural_expiry_lock') and (
                operation != 'child-natural-expiry-lock-result'
                or self.last_operation == 'child-natural-expiry-lock-ready'),
                'ui:natural-expiry-lock-order')
        if operation in accessible_ui.KIOSK_DIAGNOSTIC_OPERATIONS - {'kiosk-diagnostic-error'}:
            previous = {'kiosk-diagnostic-report': 'kiosk-diagnostic-error',
                        'kiosk-diagnostic-exit': 'kiosk-diagnostic-error',
                        'kiosk-diagnostic-editor': 'kiosk-diagnostic-report',
                        'kiosk-diagnostic-privacy': 'kiosk-diagnostic-editor'}
            require(self.last_operation == previous[operation] and
                    hasattr(self, 'kiosk_diagnostic_source'), 'ui:kiosk-diagnostic-order')
            binding = [self.boot_guard or '', self.kiosk_diagnostic_source]
        if self.accessibility_trace is not None:
            trace = self.accessibility_trace
            require(operation in ('parent-checked-events', 'parent-save-events', 'parent-custom-events',
                                  'parent-saved-result', 'parent-custom-saved-result',
                                  'feedback-collection-events',
                                  trace['operation']),
                    'ui:trace-intervening-operation')
            binding = [self.boot_guard or '', trace['token'] if operation ==
                       ('feedback-collection-events' if trace['mode'] == 'collection' else
                        'parent-custom-events' if trace['mode'] == 'custom-save' else
                        'parent-save-events' if trace['mode'] == 'save'
                        else 'parent-checked-events') else
                       ('save:' if trace['mode'] == 'save' else '') + trace['source']]
        if child is not None:
            if not binding:
                binding = [self.boot_guard or '']
            if len(binding) == 1:
                binding.append('')
            binding.append(child)
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
        if operation in accessible_ui.RESTART_OPERATIONS and operation.endswith('-reboot'):
            surface = accessible_ui.RESTART_OPERATIONS[operation][0]
            require(type(result) is dict and set(result) == {'surface', 'status', 'boot_sha256'}
                    and result['surface'] == surface and result['status'] in ('acknowledged', 'uncertain')
                    and result['boot_sha256'] == self.boot_guard, 'ui:restart-response')
            self.boot_proof = result['boot_sha256']
            return {'surface': surface, 'status': result['status']}
        if binding:
            proof = result.pop('boot_sha256', None) if type(result) is dict else None
            require(type(proof) is str and re.fullmatch(r'[0-9a-f]{64}', proof)
                    and (not self.boot_guard or proof == self.boot_guard), 'ui:boot-changed')
            self.boot_proof = proof
        expected = {'operation': operation, 'outcome': 'passed', 'interface': 'ApplicationUI+external-provider'}
        if operation in accessible_ui.SHORTCUT_OPERATIONS:
            account, route, phase = {**accessible_ui.SHORTCUT_BINDINGS,
                                      **accessible_ui.SHORTCUT_RESTRICTIONS}[operation]
            value = result.get('shortcut')
            require(type(value) is dict and set(value) == {
                'route', 'outcome', 'usable_request', 'source', 'provider', 'terminal_binding'}
                and value['route'] == route and value['outcome'] in (
                    'desktop-ready', 'overview', 'app-grid', 'run', 'terminal', 'no-result',
                    'request-only', 'desktop-exposed', 'closed')
                and type(value['usable_request']) is bool
                and value['usable_request'] is (account == 'kiosk')
                and (value['source'] is None or type(value['source']) is str
                     and re.fullmatch(r'[0-9a-f]{64}', value['source']))
                and (type(value['terminal_binding']) is bool if account == 'standard'
                     and route == 'terminal' else value['terminal_binding'] is None),
                'ui:shortcut-response')
            if value['provider'] is not None:
                accessible_ui.validate_shell_metadata(value['provider'])
            if account == 'standard':
                base = 'standard-shortcut-' + route
                if phase == 'read':
                    require(self.last_operation == base + '-ready', 'ui:shortcut-order')
                    self.shortcut_result = dict(value)
                elif phase == 'close-ready':
                    previous = getattr(self, 'shortcut_result', None)
                    require(self.last_operation == base + '-read'
                            and previous is not None and value == previous,
                            'ui:shortcut-close-recipient')
                elif phase == 'closed':
                    require(self.last_operation == base + '-close-ready'
                            and value['outcome'] == 'closed', 'ui:shortcut-order')
            elif phase == 'read':
                require(self.last_operation == operation.removesuffix('-read') + '-ready',
                        'ui:shortcut-order')
            expected['shortcut'] = value
        if operation in accessible_ui.GDM_SESSION_OPERATIONS:
            choice = result.get('session_choice')
            values = {'station', 'ubuntu', 'ubuntu-xorg', 'gnome', 'gnome-xorg'}
            require(type(choice) is dict and set(choice) == {
                'recipient', 'disposition', 'choice', 'offered', 'selected', 'destination'}
                and choice['recipient'] == ('station' if operation.startswith('gdm-station-')
                                             else 'other-child')
                and choice['disposition'] in ('chooser-opened', 'chooser-focused',
                                              'choice-focused', 'choice-activated',
                                              'cancel-focused', 'cancelled', 'no-public-chooser')
                and choice['choice'] in values | {None}
                and choice['selected'] in values | {None}
                and type(choice['offered']) is list and len(choice['offered']) <= len(values)
                and all(type(item) is str and item in values for item in choice['offered'])
                and len(set(choice['offered'])) == len(choice['offered'])
                and choice['destination'] in ('greeter-controls', 'request-window', 'full-desktop',
                                              'account-list'),
                'ui:session-choice-response')
            expected['session_choice'] = choice
        if operation == 'gdm-station-refused':
            require(result.get('fallback') in ('account-list', 'station-prompt'), 'ui:gdm-refusal-result')
            expected['fallback'] = result['fallback']
        if operation == 'child-natural-expiry-wrong-account-refused':
            require(result.get('natural_expiry_refused') is True, 'ui:natural-expiry-refusal')
            expected['natural_expiry_refused'] = True
        if operation in accessible_ui.NATURAL_EXPIRY_OPERATIONS:
            value = result.get('natural_expiry')
            require(type(value) is dict and set(value) == {
                'state', 'session_sha256', 'source', 'activity', 'seconds', 'lock', 'acted'}
                and value['state'] in ('desktop', 'locked')
                and type(value['session_sha256']) is str
                and re.fullmatch(r'[0-9a-f]{64}', value['session_sha256'])
                and type(value['acted']) is bool
                and (operation == 'child-natural-expiry-activity' or not value['acted']),
                'ui:natural-expiry-response')
            previous_session = getattr(self, 'natural_expiry_session', value['session_sha256'])
            require(value['session_sha256'] == previous_session, 'ui:natural-expiry-session-changed')
            if value['state'] == 'desktop':
                require(not operation.endswith(('lock-ready', 'lock-result'))
                    and not hasattr(self, 'natural_expiry_lock')
                    and value['lock'] is None and type(value['seconds']) is int
                    and 0 <= value['seconds'] < 86400 and type(value['source']) is str
                    and re.fullmatch(r'[0-9a-f]{64}', value['source']), 'ui:natural-expiry-response')
                AppActivityObservation.from_value(value['activity'])
                require(value['source'] == getattr(self, 'natural_expiry_source', value['source']),
                        'ui:natural-expiry-stale-activity')
                self.natural_expiry_source = value['source']
            else:
                lock = value['lock']
                require(value['activity'] is value['seconds'] is value['source'] is None
                    and type(lock) is dict and lock.get('entry') in ('curtain', 'restriction')
                    and set(lock) == {'entry', 'owner', 'locked', 'desktop_input_available',
                        'recipient', 'surface_id', 'provider'} | (
                        {'reason', 'authentication_blocked'} if lock['entry'] == 'restriction' else set())
                    and lock['owner'] == 'fixture-child' and lock['locked'] is True
                    and lock['desktop_input_available'] is False and lock['recipient'] is None
                    and type(lock['surface_id']) is str
                    and re.fullmatch(r'[0-9a-f]{64}', lock['surface_id']), 'ui:natural-expiry-lock')
                accessible_ui.validate_shell_metadata(lock['provider'])
                if lock['entry'] == 'restriction':
                    require(lock['reason'] == 'time-limit' and lock['authentication_blocked'] is True,
                            'ui:natural-expiry-lock')
                require(lock['surface_id'] == getattr(self, 'natural_expiry_lock', lock['surface_id']),
                        'ui:natural-expiry-lock-changed')
                self.natural_expiry_lock = lock['surface_id']
            self.natural_expiry_session = value['session_sha256']
            expected['natural_expiry'] = value
        if operation in accessible_ui.LOCK_SURFACE_OPERATIONS:
            value = result.get('lock')
            lock_operation = operation.replace('child-', 'parent-', 1)
            identity = 'fixture-' + operation.split('-', 1)[0]
            if lock_operation in ('parent-lock-unlocked-refused', 'parent-lock-refusals',
                             'parent-lock-recipient-refusals'):
                require(value == {'refused': ['unlocked-session'] if operation.endswith('unlocked-refused')
                    else list(accessible_ui.LOCK_RECIPIENT_REFUSALS) if lock_operation == 'parent-lock-recipient-refusals'
                    else ['session', 'surface-ambiguous', 'field-ambiguous', 'recipient']},
                    'ui:lock-refusal-response')
            else:
                recipient = operation in accessible_ui.LOCK_RECIPIENT_OPERATIONS
                denial = lock_operation == 'parent-lock-time-denied'
                entry = ('restriction' if denial else
                         'challenge' if lock_operation == 'parent-lock-challenge' or recipient else 'curtain')
                require(type(value) is dict and set(value) == {
                    'entry', 'owner', 'locked', 'desktop_input_available', 'recipient', 'surface_id', 'provider'}
                    | ({'empty', 'masked', 'focused', 'challenge_id'} if recipient else set())
                    | ({'reason', 'authentication_blocked'} if denial else set())
                    and value['entry'] == entry and value['owner'] == identity
                    and value['locked'] is True and value['desktop_input_available'] is False
                    and value['recipient'] == (identity if entry == 'challenge' else None)
                    and type(value['surface_id']) is str and re.fullmatch(r'[0-9a-f]{64}', value['surface_id']),
                    'ui:lock-response')
                if recipient:
                    require(all(value[key] is True for key in ('empty', 'masked', 'focused'))
                            and type(value['challenge_id']) is str
                            and re.fullmatch(r'[0-9a-f]{64}', value['challenge_id']),
                            'ui:lock-recipient-response')
                accessible_ui.validate_shell_metadata(value['provider'])
                if denial:
                    require(value['reason'] == 'time-limit'
                            and value['authentication_blocked'] is True
                            and self.last_operation == 'child-lock-reveal-ready', 'ui:lock-denial')
                if lock_operation == 'parent-lock-curtain' or (
                        lock_operation == 'parent-lock-challenge' and not hasattr(self, 'lock_surface_id')):
                    self.lock_surface_id = value['surface_id']
                else:
                    require(value['surface_id'] == getattr(self, 'lock_surface_id', None),
                            'ui:lock-surface-changed')
            expected['lock'] = value
        if operation in accessible_ui.RESTART_OPERATIONS:
            surface, action = accessible_ui.RESTART_OPERATIONS[operation]
            if action == 'read':
                value = result.get('restart')
                require(type(value) is dict and set(value) == {'surface', 'texts', 'modal', 'policy_blocked'}
                        and value['surface'] == surface and value['modal'] is True
                        and value['policy_blocked'] is True and type(value['texts']) is dict
                        and set(value['texts']) == {'update-required-message', 'update-required-close',
                                                   'update-required-reboot'}
                        and all(type(text) is str and 0 < len(text) <= 512
                                for text in value['texts'].values()), 'ui:restart-response')
                expected['restart'] = value
        if operation in accessible_ui.LANGUAGE_HISTORY_REQUESTS:
            action = accessible_ui.LANGUAGE_HISTORY_REQUESTS[operation][4]
            if action == 'form':
                value = result.get('language_form')
                ids = {'kiosk-child-account-caption', 'kiosk-approver-account-caption',
                       'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel'}
                require(type(value) is dict and set(value) == {'request', 'texts', 'labels', 'chooser_absent'}
                    and value['chooser_absent'] is True and type(value['texts']) is dict
                    and set(value['texts']) == ids and type(value['labels']) is dict
                    and set(value['labels']) == {'kiosk-request-submit', 'kiosk-request-cancel'}
                    and all(type(text) is str and 0 < len(text) <= 512 for text in
                            (*value['texts'].values(), *value['labels'].values())), 'ui:language-form')
                RequestObservation.from_request(value['request'], operation=operation)
                expected['language_form'] = value
            elif action in ('approver', 'riley', 'jordan'):
                RequestObservation.from_request(result.get('request'), operation=operation)
                expected['request'] = result['request']
        if operation == 'kiosk-language-account-refusals':
            require(result == {**expected, 'refused': True}, 'ui:language-refusal')
            expected['refused'] = True
        if operation in (*accessible_ui.KIOSK_LANGUAGE_POLICIES, 'overlay-language-policy'):
            value = result.get('language_policy')
            require(type(value) is dict and set(value) == {'settings', 'rows', 'balances'},
                    'ui:language-policy')
            SettingsObservation.from_settings(value['settings'])
            AppRowsObservation.from_rows(value['rows'])
            require(type(value['balances']) is dict and set(value['balances']) == {'daily', 'one_time', 'total'}
                    and all(type(seconds) is int and seconds >= 0 for seconds in value['balances'].values()),
                    'ui:language-balances')
            expected['language_policy'] = value
        if ((operation in accessible_ui.OVERLAY_REMINDER_OPERATIONS and operation not in (
                'overlay-reminder-save', 'overlay-reminder-cancel')) or
                (operation in accessible_ui.BINDING_REMINDER_OPERATIONS and
                 accessible_ui.BINDING_REMINDER_OPERATIONS[operation][2] not in ('save', 'cancel'))):
            value = result.get('reminders')
            require(type(value) is dict and set(value) == {
                'records', 'show_in_fullscreen', 'fullscreen_enabled', 'language', 'source'}
                and type(value['records']) is list and len(value['records']) <= 64
                and type(value['show_in_fullscreen']) is bool
                and type(value['fullscreen_enabled']) is bool
                and value['language'] in accessible_ui.PARENT_LANGUAGE_CHOICES
                and type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source']),
                'ui:reminder-response')
            identifiers = set()
            for row in value['records']:
                require(type(row) is dict and set(row) == {'id', 'value', 'unit', 'text'}
                    and type(row['id']) is str and len(row['id']) <= 64
                    and re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', row['id'])
                    and row['id'] not in identifiers and row['unit'] in ('minute', 'second')
                    and type(row['value']) is int and 0 < row['value'] <= (
                        4294967295 // 60 if row['unit'] == 'minute' else 4294967295)
                    and type(row['text']) is str and len(row['text']) <= 4096
                    and '\x00' not in row['text']
                    and not any(0xD800 <= ord(character) <= 0xDFFF for character in row['text']),
                    'ui:reminder-record')
                identifiers.add(row['id'])
            expected['reminders'] = value
        if operation in accessible_ui.PARENT_DIALOG_BINDINGS:
            surface, language, action = accessible_ui.PARENT_DIALOG_BINDINGS[operation]
            if action == 'refused':
                expected['refused'] = True
            elif action not in ('closed', 'close-ready'):
                value = {'surface': surface, 'language': language,
                         'labels': {key: value for key, value in accessible_ui.PARENT_DIALOG_TEXT[language].items()
                                    if key.startswith(surface + '-')}}
                require(result.get('dialog_presentation') == value, 'ui:dialog-presentation')
                expected['dialog_presentation'] = value
                if surface == 'feedback':
                    FeedbackObservation.from_value(result.get('feedback'))
                    require(result['feedback']['draft'] == ('initial-empty' if action == 'empty'
                                                            else 'synthetic-rtl'), 'ui:dialog-draft')
                    expected['feedback'] = result['feedback']
        if operation in (accessible_ui.PARENT_LANGUAGE_OPERATIONS | accessible_ui.KIOSK_LANGUAGE_OPERATIONS |
                         accessible_ui.OVERLAY_LANGUAGE_OPERATIONS):
            language_operation, language_child = accessible_ui.KIOSK_LANGUAGE_BINDINGS.get(
                operation, (operation, None))
            if language_operation == 'kiosk-language-initial-identity':
                language_operation = 'kiosk-language-initial'
            surface = operation.split('-', 1)[0]
            if operation.endswith('-wrong-entry'):
                require(result == {**expected, 'refused': True}, 'ui:language-refusal')
                expected['refused'] = True
            elif operation in accessible_ui.PARENT_LANGUAGE_ALLOWANCES:
                require(result.get('allowance') == {'minutes': 60, 'saved': True},
                        'ui:language-allowance-response')
                expected['allowance'] = result['allowance']
            elif operation in accessible_ui.PARENT_LANGUAGE_SELECTIONS:
                account = accessible_ui.NAMED_CUSTOM_CHILDREN[
                    accessible_ui.PARENT_LANGUAGE_SELECTIONS[operation]]
                require(result.get('child_selection') == {
                    'child': accessible_ui.CHILD_IDENTITIES[account]}, 'ui:language-selected-child')
                expected['child_selection'] = result['child_selection']
            elif operation == 'parent-language-state' or operation in accessible_ui.PARENT_LANGUAGE_STATES:
                value = result.get('language_state')
                binding = accessible_ui.PARENT_LANGUAGE_STATES.get(operation)
                keys = {
                    'child', 'limit_enabled', 'allowance_minutes', 'rows', 'management',
                    'management_labels', 'chooser_absent'}
                if binding:
                    keys |= {'account_name', 'app_names', 'balances'}
                require(type(value) is dict and set(value) == keys
                    and value['child'] in accessible_ui.CHILD_IDENTITIES.values()
                    and value['limit_enabled'] is bool(binding)
                    and value['allowance_minutes'] == (60 if binding else 0)
                    and type(value['allowance_minutes']) is int and value['chooser_absent'] is True
                    and type(value['management_labels']) is list
                    and 0 < len(value['management_labels']) <= 64
                    and all(type(text) is str and len(text) <= 512
                            for text in value['management_labels'])
                    and type(value['management']) is str and 0 < len(value['management']) <= 512,
                    'ui:language-state')
                AppRowsObservation.from_rows(value['rows'])
                if binding:
                    child, language = binding
                    account = accessible_ui.NAMED_CUSTOM_CHILDREN[child]
                    require(value['child'] == accessible_ui.CHILD_IDENTITIES[account]
                            and value['account_name'] == account
                            and type(value['app_names']) is list
                            and len(value['app_names']) == len(value['rows'])
                            and all(type(row) is list and len(row) == 2
                                    and row[0] == policy[0] and type(row[1]) is str
                                    and 0 < len(row[1]) <= 512
                                    for row, policy in zip(value['app_names'], value['rows'])),
                            'ui:language-account-or-app-names')
                    balances = value['balances']
                    require(type(balances) is dict and set(balances) == {
                        'child', 'expanded', 'daily', 'one_time', 'total', 'observed_monotonic_ns'}
                        and balances['child'] == value['child'] and balances['expanded'] is True
                        and type(balances['observed_monotonic_ns']) is int
                        and 0 < balances['observed_monotonic_ns'] < 10**20,
                        'ui:language-balances')
                    for key in ('daily', 'one_time', 'total'):
                        item = balances[key]
                        require(type(item) is dict and set(item) == {'text', 'seconds', 'precision_seconds'}
                                and type(item['seconds']) is int and type(item['precision_seconds']) is int,
                                'ui:language-balances')
                        try:
                            parsed = accessible_ui.duration_projection(item['text'], language=language)
                        except accessible_ui.UiError:
                            require(False, 'ui:language-balances')
                        require(item == parsed, 'ui:language-balances')
                expected['language_state'] = value
            elif language_operation.startswith(('kiosk-language-form-', 'overlay-language-form-')):
                value = result.get('language_form')
                ids = {'kiosk-child-account-caption', 'kiosk-approver-account-caption',
                       'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel'}
                require(type(value) is dict and set(value) == {'request', 'texts', 'labels', 'chooser_absent'}
                        and value['chooser_absent'] is True and type(value['texts']) is dict
                        and set(value['texts']) == ids and type(value['labels']) is dict
                        and set(value['labels']) == {'kiosk-request-submit', 'kiosk-request-cancel'}
                        and all(type(text) is str and 0 < len(text) <= 512 for text in
                                (*value['texts'].values(), *value['labels'].values())), 'ui:language-form')
                RequestObservation.from_request(value['request'], operation=(
                    'overlay-request-form' if surface == 'overlay' else 'multiple-first-parent'
                    if language_child == accessible_ui.CHILD and operation not in accessible_ui.KIOSK_LANGUAGE_CASEY_FORMS
                    else 'multiple-other-parent' if language_child == accessible_ui.CHILD
                    else 'multiple-other-child' if operation in accessible_ui.KIOSK_LANGUAGE_CASEY_FORMS
                    else 'multiple-other-first-parent'))
                expected['language_form'] = value
            elif language_operation not in (surface + '-language-save', surface + '-language-cancel'):
                value = result.get('language')
                identity_keys = {'identity'} if type(value) is dict and 'identity' in value else set()
                require(operation != 'kiosk-language-initial-identity' or identity_keys,
                        'ui:language-identity')
                require(type(value) is dict and set(value) == {
                    'initial', 'checked', 'choices', 'heading', 'save', 'save_label', 'save_description'} | identity_keys
                    and value['initial'] is (language_operation == surface + '-language-initial')
                    and value['checked'] in tuple(language.lower() for language in
                                                  accessible_ui.PARENT_LANGUAGE_CHOICES)
                    and type(value['choices']) is dict
                    and set(value['choices']) == set(accessible_ui.PARENT_LANGUAGE_CHOICES)
                    and all(type(text) is str and 0 < len(text) <= 512 for text in
                            (*value['choices'].values(), value['heading'], value['save'], value['save_label'],
                             value['save_description'])), 'ui:language-response')
                if identity_keys:
                    identity = value['identity']
                    require(operation == 'kiosk-language-initial-identity' and type(identity) is dict
                            and set(identity) == {'chooser', 'session'}
                            and type(identity['chooser']) is str
                            and re.fullmatch(r'[0-9a-f]{32}', identity['chooser'])
                            and type(identity['session']) is str
                            and re.fullmatch(r'[0-9a-f]{64}', identity['session']),
                            'ui:language-identity')
                expected['language'] = value
        if (operation in accessible_ui.INITIAL_KIOSK_OPERATIONS and operation != 'kiosk-initial-notice-return'
                or operation in accessible_ui.CHINESE_LANGUAGE_OPERATIONS):
            require(type(result) is dict and set(result) == {*expected, 'initial'}, 'ui:initial-response')
            value = result['initial']
            kind = ('form' if operation in accessible_ui.CHINESE_LANGUAGE_OPERATIONS else
                    'notice' if 'notice' in operation else 'language' if 'language' in operation else 'form')
            ids = ({'update-required-message', 'update-required-close', 'update-required-reboot'}
                   if kind == 'notice' else {'kiosk-child-account-caption', 'kiosk-approver-account-caption',
                       'kiosk-duration-label-1800', 'kiosk-request-submit', 'kiosk-request-cancel'} |
                       ({'language-title', 'language-continue', 'language-cancel'} if kind == 'language' else set()))
            require(type(value) is dict and set(value) == {'kind', 'child', 'texts', 'default_chinese', 'input_free'}
                    and value['kind'] == kind and value['child'] == 'other-fixture-child'
                    and value['input_free'] is True and type(value['texts']) is dict
                    and set(value['texts']) == ids and all(type(text) is str and 0 < len(text) <= 512
                        for text in value['texts'].values()) and
                    (type(value['default_chinese']) is bool if kind == 'language' else value['default_chinese'] is None),
                    'ui:initial-response')
            expected['initial'] = value
        if operation == 'chinese-standard-desktop':
            require(type(result) is dict and set(result) == {*expected, 'provider'}, 'ui:response')
            expected['provider'] = accessible_ui.validate_shell_metadata(result['provider'])
        if operation == 'station-initial-entry':
            require(type(result) is dict and set(result) == {*expected, 'entry'} and
                    result['entry'] == {'destination': 'initial-request-window'}, 'ui:initial-entry-response')
            expected['entry'] = result['entry']
        if operation in ('native-opened', 'native-submitted', 'overlay-native-opened',
                         'overlay-native-submitted', 'parent-native-opened', 'parent-native-submitted'):
            expected['activity'] = {'draft': 'ONPC fixture draft',
                'submitted': 'No submitted draft' if operation.endswith('native-opened') else 'ONPC fixture draft',
                'score': 'Moves: 0; token: 0'}
        if operation in accessible_ui.BASELINE_NATIVE_BINDINGS:
            _role, action = accessible_ui.BASELINE_NATIVE_BINDINGS[operation]
            if action in ('opened', 'submitted'):
                expected['activity'] = {'draft': 'ONPC fixture draft',
                    'submitted': 'No submitted draft' if action == 'opened' else 'ONPC fixture draft',
                    'score': 'Moves: 0; token: 0'}
        if operation in ('native-activity', 'overlay-native-activity', 'parent-native-activity'):
            require(type(result) is dict and set(result) == {*expected, 'activity'}, 'ui:response')
            AppActivityObservation.from_value(result['activity'])
            expected['activity'] = result['activity']
        if operation.removeprefix('overlay-') in ('native-grid', 'native-grid-refusals'):
            expected['provider'] = accessible_ui.validate_shell_metadata(result.get('provider'))
        if operation in accessible_ui.COUNTDOWN_SESSION_OPERATIONS:
            state = operation.removeprefix('child-countdown-session-')
            value = result.get('session_countdown')
            require(type(value) is dict and set(value) == {
                'state', 'source', 'available', 'input_refused', 'preference_unchanged'}
                and value['state'] == state and type(value['source']) is str
                and re.fullmatch(r'[0-9a-f]{64}', value['source'])
                and value['available'] is (state in ('pin', 'restored'))
                and value['input_refused'] is (state in ('locked', 'greeter'))
                and value['preference_unchanged'] is True, 'ui:countdown-session-response')
            if state == 'pin':
                require(not hasattr(self, 'countdown_session_source'), 'ui:countdown-session-replay')
                self.countdown_session_source = value['source']
            else:
                require(value['source'] == self.countdown_session_source,
                        'ui:countdown-session-replaced')
            expected['session_countdown'] = value
        if operation in accessible_ui.COUNTDOWN_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'countdown'}, 'ui:response')
            expected['countdown'] = accessible_ui.validate_countdown(
                result['countdown'], operation == 'child-countdown-present')
        if operation in accessible_ui.PANEL_ANIMATION_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'panel_animation'}, 'ui:response')
            value = accessible_ui.validate_panel_animation(result['panel_animation'])
            require(operation.endswith('-read') or value['animation'] is operation.endswith('-on'),
                    'ui:panel-animation-result')
            expected['panel_animation'] = value
        if operation in ('child-countdown-wrong-account-refused', 'overlay-wrong-account-refused',
                         'child-countdown-animation-wrong-account-refused'):
            require(type(result) is dict and set(result) == {*expected, 'refused'}
                    and result['refused'] is True, 'ui:countdown-refusal')
            expected['refused'] = True
        if operation == 'feedback-collection-ready':
            value = result.get('collection')
            require(type(value) is dict and set(value) == {'collecting', 'download'}
                    and value['collecting'] is False and value['download'] is True,
                    'ui:collection-not-ready')
            expected['collection'] = value
        if operation == 'kiosk-preferences-confinement':
            value = result.get('preferences_confinement')
            require(type(value) is dict and value == {
                'pages': ['language', 'reminders', 'presets'],
                'editors': ['reminder-add', 'reminder-edit', 'preset-add', 'preset-edit'],
                'actions_confined': True, 'drafts_discarded': True}
                and value['actions_confined'] is True and value['drafts_discarded'] is True,
                'ui:preferences-confinement-response')
            expected['preferences_confinement'] = value
        if operation in accessible_ui.KIOSK_REMINDER_OPERATIONS:
            fields = ({'banner_surface': True, 'literal': True, 'critical': True, 'countdown': True}
                      if operation == 'kiosk-reminder-preview' else
                      {'banner_closed': True, 'unsaved_draft_discarded': True})
            value = result.get('reminder')
            require(type(value) is dict and set(value) == {'source', *fields} and
                    type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source']) and
                    all(value[key] is expected_value for key, expected_value in fields.items()),
                    'ui:kiosk-reminder-response')
            if operation == 'kiosk-reminder-preview':
                require(not hasattr(self, 'kiosk_reminder_source'), 'ui:kiosk-reminder-replay')
                self.kiosk_reminder_source = value['source']
            else:
                require(self.last_operation == 'kiosk-reminder-preview' and value['source'] ==
                        getattr(self, 'kiosk_reminder_source', None), 'ui:kiosk-reminder-order')
            expected['reminder'] = value
        if operation in accessible_ui.KIOSK_DIAGNOSTIC_OPERATIONS:
            fields = {'kiosk-diagnostic-error': {'error_shown': True, 'report_default': True},
                      'kiosk-diagnostic-exit': {'exit_initiated': True, 'reported': False},
                      'kiosk-diagnostic-report': {'report_open': True},
                      'kiosk-diagnostic-editor': {'editor_usable': True,
                                                  'diagnostics_ready': True, 'sent': False},
                      'kiosk-diagnostic-privacy': {'privacy_read': True, 'actions_confined': True,
                                                  'draft_preserved': True, 'sent': False}}
            value = result.get('diagnostic')
            require(type(value) is dict and set(value) == {'source', *fields[operation]} and
                    type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source']) and
                    all(value[key] is expected_value for key, expected_value in fields[operation].items()),
                    'ui:kiosk-diagnostic-response')
            if operation == 'kiosk-diagnostic-error':
                require(not hasattr(self, 'kiosk_diagnostic_source'), 'ui:kiosk-diagnostic-replay')
                self.kiosk_diagnostic_source = value['source']
            else:
                previous = {'kiosk-diagnostic-report': 'kiosk-diagnostic-error',
                            'kiosk-diagnostic-exit': 'kiosk-diagnostic-error',
                            'kiosk-diagnostic-editor': 'kiosk-diagnostic-report',
                            'kiosk-diagnostic-privacy': 'kiosk-diagnostic-editor'}
                require(self.last_operation == previous[operation] and
                        value['source'] == getattr(self, 'kiosk_diagnostic_source', None),
                        'ui:kiosk-diagnostic-order')
            expected['diagnostic'] = value
        if operation == 'parent-window-count':
            require(type(result) is dict and set(result) == {*expected, 'count'}
                    and type(result['count']) is int and result['count'] == 1,
                    'ui:parent-window-count')
            expected['count'] = 1
        if operation == 'about-interval-read':
            value = result.get('about_interval')
            require(type(result) is dict and set(result) == {*expected, 'about_interval'}
                    and type(value) is dict and set(value) == {'pid', 'endpoint', 'product', 'version'}
                    and type(value['pid']) is int and value['pid'] > 0
                    and type(value['endpoint']) is list and len(value['endpoint']) == 2
                    and all(type(part) is str and 0 < len(part) <= 256 for part in value['endpoint'])
                    and value['endpoint'][0].startswith(':') and value['endpoint'][1].startswith('/')
                    and value['product'] == accessible_ui.PRODUCT and value['version'] == version,
                    'ui:about-interval-response')
            expected['about_interval'] = value
        if operation in accessible_ui.ACCESSIBILITY_TRACE_OPERATIONS:
            value = result.get('trace')
            if operation in ('parent-save-events', 'parent-custom-events'):
                require(type(value) is dict and set(value) == {'token', 'source', 'prepared'}
                        and type(value['token']) is str and re.fullmatch(r'[0-9a-f]{32}', value['token'])
                        and type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source'])
                        and value['prepared'] is True, 'ui:trace-response')
            elif operation in ('parent-saved-result', 'parent-custom-saved-result'):
                custom = operation == 'parent-custom-saved-result'
                require(type(value) is dict and set(value) == {'saved', 'minutes' if custom else 'enabled'}
                        and value['saved'] is True and
                        (type(value['minutes']) is int and value['minutes'] == 6 if custom
                         else value['enabled'] is True), 'ui:save-result')
            elif operation in ('parent-checked-events',
                             'feedback-collection-events'):
                require(type(value) is dict and set(value) == {
                    'token', 'source', 'terminal', 'samples'} and
                    type(value['token']) is str and re.fullmatch(r'[0-9a-f]{32}', value['token']) and
                    type(value['source']) is str and re.fullmatch(r'[0-9a-f]{64}', value['source']) and
                    value['terminal'] is True and type(value['samples']) is list and
                    1 <= len(value['samples']) <= 32, 'ui:trace-response')
                previous = 0
                for sample in value['samples']:
                    require(type(sample) is dict and type(sample.get('elapsed_ms')) is int and
                            previous <= sample['elapsed_ms'] < 60000, 'ui:trace-sample')
                    if operation == 'feedback-collection-events':
                        require(set(sample) == {'elapsed_ms', 'collecting', 'download'} and
                                type(sample['collecting']) is bool and type(sample['download']) is bool,
                                'ui:trace-sample')
                    elif operation == 'parent-checked-events':
                        require(set(sample) == {'elapsed_ms', 'checked', 'source'} and
                                type(sample['checked']) is bool and sample['source'] == 'application-ui',
                                'ui:trace-sample')
                    previous = sample['elapsed_ms']
                if operation == 'feedback-collection-events':
                    require(value['samples'][-1]['collecting'] is False
                            and value['samples'][-1]['download'] is True,
                            'ui:collection-not-ready')
                elif operation == 'parent-checked-events':
                    require(value['samples'][-1]['checked'] is True, 'ui:trace-terminal')
            elif operation == 'feedback-collection-open':
                require(value == {'opened': True}, 'ui:collection-open')
            elif operation == 'parent-custom-trace-focus':
                require(value == {'applied': True}, 'ui:trace-input')
            elif operation == 'parent-custom-trace-disabled-refused':
                require(value == {'refusal': 'disabled'}, 'ui:trace-refusal')
            else:
                require(value == {'refusal': 'wrong-child' if operation ==
                    'parent-trace-wrong-child-refused' else 'wrong-surface'}, 'ui:trace-refusal')
            expected['trace'] = value
        if operation in accessible_ui.FILE_REVIEW_OPERATIONS and not operation.startswith('files-switch-'):
            from attachment_composition import compare_file_draft
            if operation != 'files-feedback-privacy-open':
                expected['file_draft'] = compare_file_draft(result.get('file_draft'))
        if operation in accessible_ui.DRAFT_OPERATIONS and not operation.startswith('draft-switch-'):
            from attachment_composition import compare_formatted_draft
            base = operation.removeprefix('draft-')
            if base.startswith('chooser-'):
                projection = {'checked': base}
                if base == 'chooser-open':
                    provider = result.get('chooser', {}).get('provider')
                    require(type(provider) is dict and set(provider) == {'route', 'version', 'locale', 'keyboard'}
                            and provider['route'] in ('gtk-native', 'nautilus-portal'), 'ui:chooser-provider')
                    accessible_ui.validate_shell_metadata({key: value for key, value in provider.items() if key != 'route'})
                    projection['provider'] = provider
                expected['chooser'] = projection
            elif base != 'feedback-privacy-open':
                expected['draft_state'] = compare_formatted_draft(result.get('draft_state'),
                    reset=base in ('feedback-reopen', 'feedback-reread'))
        if operation in accessible_ui.MATE_APPROVAL_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'approval'}, 'ui:mate-response')
            value = result['approval']
            if operation == 'kiosk-mate-submit-rejection':
                require(value == {'rejected': True, 'cancelled': True, 'no_error': True}
                        and all(type(item) is bool for item in value.values()), 'ui:mate-result')
            elif operation in ('kiosk-mate-submit-success', 'kiosk-mate-submit-immediate',
                               'chinese-mate-submit-success', 'kiosk-long-mate-submit-success',
                               'jordan-mate-submit-success',
                               'kiosk-pause-mate-submit-success') or (
                                   operation in accessible_ui.PROFILE_MATE_REQUESTS
                                   and operation.endswith('-submit-success')):
                require(value == {'approved': True, 'form_success': True,
                                  **({'immediate_exit': True} if operation.endswith('immediate') else {})}
                        and all(type(item) is bool for item in value.values()), 'ui:mate-result')
            else:
                chinese = operation in accessible_ui.CHINESE_MATE_ORDER
                long_request = operation in accessible_ui.LONG_MATE_ORDER
                profile_request = accessible_ui.PROFILE_MATE_REQUESTS.get(operation)
                jordan = operation in accessible_ui.JORDAN_MATE_ORDER
                paused = operation in accessible_ui.PAUSE_MATE_ORDER
                fields = {'challenge_id'} | ({'provider', 'texts', 'child', 'approver', 'agent_id',
                    'duration_seconds', 'allow_soft', 'rejected_proofs'} if chinese else set()) | (
                    {'request'} if long_request or jordan or profile_request else set()) | ({'provider'} if paused else set())
                require(type(value) is dict and set(value) == fields and
                        type(value['challenge_id']) is str and
                        re.fullmatch(r'[0-9a-f]{64}', value['challenge_id']), 'ui:mate-identity')
                if paused:
                    accessible_ui.validate_shell_metadata(value['provider'])
                    if operation == accessible_ui.PAUSE_MATE_ORDER[0]:
                        self.mate_pause_provider = dict(value['provider'])
                    else:
                        require(value['provider'] == self.mate_pause_provider, 'ui:mate-provider-changed')
                if long_request or jordan or profile_request:
                    request = value['request']
                    require(type(request) is dict and request == (
                            profile_request or (accessible_ui.JORDAN_MATE_REQUEST if jordan else accessible_ui.LONG_MATE_REQUEST))
                            and type(request.get('duration_seconds')) is int
                            and request.get('allow_soft') is True, 'ui:mate-request-binding')
                if chinese:
                    accessible_ui.validate_shell_metadata(value['provider'])
                    require(value['provider']['locale'] in ('zh_CN.UTF-8', 'zh_CN.utf8', 'zh_CN')
                            and type(value['agent_id']) is str and re.fullmatch(r'[0-9a-f]{64}', value['agent_id'])
                            and value['texts'] == accessible_ui.chinese_mate_texts(value['provider']['version'])
                            and value['child'] == 'existing-fixture-child' and value['approver'] == 'fixture-parent'
                            and type(value['duration_seconds']) is int and value['duration_seconds'] == 75
                            and value['allow_soft'] is True and value['rejected_proofs'] == (
                                list(accessible_ui.CHINESE_MATE_REFUSALS) if operation == 'chinese-mate-open' else []),
                            'ui:mate-native-response')
                if operation in ('kiosk-mate-open', 'kiosk-mate-rejection-open', 'chinese-mate-open',
                                 'kiosk-long-mate-open', 'kiosk-pause-mate-open', 'jordan-mate-open') or (
                                     profile_request and operation.endswith('-mate-open')):
                    require(value['challenge_id'] not in self.challenges, 'ui:challenge-replay')
                    self.challenges.add(value['challenge_id'])
                    self.mate_approval_identity = value['challenge_id']
                else:
                    require(value['challenge_id'] == self.mate_approval_identity, 'ui:mate-replacement')
            expected['approval'] = value
        if operation in accessible_ui.SHELL_APPROVAL_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'approval'}, 'ui:shell-response')
            value = result['approval']
            if operation in accessible_ui.SHELL_SUCCESS_OPERATIONS:
                require(value == {'approved': True, 'form_success': True,
                                  **({'immediate_exit': True} if operation == 'overlay-approval-immediate' else {})}
                        and all(type(item) is bool for item in value.values()), 'ui:shell-result')
            elif operation == accessible_ui.SHELL_REJECTION_ORDER[-1]:
                require(value == {'challenge_id': self.shell_approval_identity,
                                  'rejected': True, 'cancel_ready': True,
                                  'same_challenge_rechecked': True}
                        and all(type(value[key]) is bool for key in (
                            'rejected', 'cancel_ready', 'same_challenge_rechecked')),
                        'ui:shell-rejection-result')
            else:
                opening = operation in ('overlay-shell-open', accessible_ui.SHELL_REJECTION_ORDER[0])
                require(type(value) is dict and set(value) == (
                    {'challenge_id', 'provider', 'rejected_proofs'} if opening else {'challenge_id'}),
                    'ui:shell-response')
                identity = value['challenge_id']
                require(type(identity) is str and re.fullmatch(r'[0-9a-f]{64}', identity), 'ui:shell-identity')
                if opening:
                    accessible_ui.validate_shell_metadata(value['provider'])
                    require(value['rejected_proofs'] == list(accessible_ui.SHELL_PROMPT_REFUSALS),
                            'ui:shell-refusals')
                    require(identity not in self.challenges, 'ui:challenge-replay')
                    self.challenges.add(identity)
                    self.shell_approval_identity = identity
                else:
                    require(identity == self.shell_approval_identity, 'ui:shell-replacement')
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
                         'parent-desktop-provider', 'fresh-child-desktop',
                         'child-retained-unlock-diagnostic'):
            require(type(result) is dict and set(result) == {*expected, 'provider'}, 'ui:response')
            expected['provider'] = accessible_ui.validate_shell_metadata(result['provider'])
        if operation == 'gdm-product-free-provider':
            require(type(result) is dict and set(result) == {*expected, 'provider'}, 'ui:response')
            expected['provider'] = accessible_ui.validate_gdm_metadata(result['provider'])
        if operation == 'gdm-child-list':
            require(type(result) is dict and set(result) == {*expected, 'provider', 'focused'}, 'ui:response')
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
        if (operation in accessible_ui.PICKER_OPERATIONS
                or operation in accessible_ui.PRESENTED_PICKER_OPERATIONS
                or operation == 'parent-child-picker-ready'):
            require(type(result) is dict and set(result) == {*expected, 'selection_ready'}
                    and result['selection_ready'] is True, 'ui:response')
            expected['selection_ready'] = True
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
        if operation in accessible_ui.BOUNDARY_OPERATIONS:
            projection = accessible_ui.boundary_expected(operation)
            if operation.endswith('-open'):
                provider = result.get('boundary', {}).get('provider')
                require(type(provider) is dict and set(provider) == {'route', 'version', 'locale', 'keyboard'}
                        and provider['route'] in ('gtk-native', 'nautilus-portal'), 'ui:chooser-provider')
                accessible_ui.validate_shell_metadata({key: value for key, value in provider.items() if key != 'route'})
                projection['provider'] = provider
            require(type(result) is dict and set(result) == {*expected, 'boundary'}
                    and result['boundary'] == projection, 'ui:boundary-response')
            expected['boundary'] = result['boundary']
        if operation in accessible_ui.ATTACHMENT_OPERATIONS:
            projection = {'checked': operation}
            if operation != 'attachment-wrong-entry':
                projection['items'] = [[name, f'{len(data)} bytes']
                    for name, data in accessible_ui.ATTACHMENT_INPUTS
                    if operation in ('attachment-details', 'attachment-preview', 'attachment-preview-return')
                    or name == 'Synthetic note.txt']
            if operation == 'attachment-preview':
                projection['preview'] = 'not-offered'
            require(type(result) is dict and set(result) == {*expected, 'attachment'}
                    and result['attachment'] == projection, 'ui:attachment-response')
            expected['attachment'] = result['attachment']
        if operation in accessible_ui.SAVE_OPERATIONS:
            projection = {'checked': operation}
            if operation.removeprefix('denied-').removeprefix('export-') in ('save-chooser-open', 'save-chooser-reopen'):
                provider = result.get('chooser', {}).get('provider')
                require(type(provider) is dict and set(provider) == {
                    'route', 'version', 'locale', 'keyboard', 'mode', 'caller'}
                    and provider['route'] == 'nautilus-portal' and provider['mode'] == 'save'
                    and provider['caller'] == 'parent-feedback', 'ui:save-provider')
                accessible_ui.validate_shell_metadata({key: provider[key]
                    for key in ('version', 'locale', 'keyboard')})
                projection['provider'] = provider
            require(type(result) is dict and set(result) == {*expected, 'chooser'}
                    and result['chooser'] == projection, 'ui:save-response')
            expected['chooser'] = result['chooser']
        if operation in accessible_ui.CHOOSER_OPERATIONS:
            projection = {'checked': operation}
            if operation in ('chooser-open', 'chooser-reopen'):
                provider = result.get('chooser', {}).get('provider')
                require(type(provider) is dict and set(provider) == {'route', 'version', 'locale', 'keyboard'}
                        and provider['route'] in ('gtk-native', 'nautilus-portal'), 'ui:chooser-provider')
                accessible_ui.validate_shell_metadata({key: value for key, value in provider.items() if key != 'route'})
                projection['provider'] = provider
            if operation in ('chooser-attachments', 'chooser-preserved'):
                projection['attachments'] = ['diagnostic-logs.zip', *accessible_ui.CHOOSER_FILES]
            require(type(result) is dict and set(result) == {*expected, 'chooser'}
                    and result['chooser'] == projection, 'ui:chooser-response')
            expected['chooser'] = result['chooser']
        if operation in accessible_ui.TOGGLE_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'toggle'}
                    and result['toggle'] == accessible_ui.TOGGLE_OPERATIONS[operation],
                    'ui:toggle-response')
            expected['toggle'] = accessible_ui.TOGGLE_OPERATIONS[operation]
        if operation in accessible_ui.FILTER_OPERATIONS:
            kind, mask, action = accessible_ui.FILTER_OPERATIONS[operation]
            value = result.get('filter')
            if action == 'open':
                projection = {'ready': kind}
                require(value == projection, 'ui:filter-response')
            else:
                desired = bool(mask & (1 << accessible_ui.FILTER_OPTIONS[kind].index(action)))
                require(type(value) is dict and set(value) == {'state', 'activated'}
                        and value['state'] is desired and type(value['activated']) is bool,
                        'ui:filter-response')
            require(set(result) == {*expected, 'filter'}, 'ui:filter-response')
            expected['filter'] = value
        if operation in accessible_ui.APP_ROW_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'apps'}, 'ui:response')
            apps = result['apps']
            if operation == 'catalogue-incomplete-refused':
                require(apps == {'refusal': 'incomplete-result'}, 'ui:app-row-refusal')
            elif operation.endswith(('wrong-child', 'wrong-page')):
                require(apps == {'refusal': 'wrong-child' if operation.endswith('wrong-child')
                                  else 'wrong-page'}, 'ui:app-row-refusal')
            else:
                require(type(apps) is dict and set(apps) == {'rows'}, 'ui:app-rows')
                AppRowsObservation.from_rows(apps['rows'])
            expected['apps'] = apps
        if operation in accessible_ui.LEGEND_OPERATIONS:
            projection = ({'refusal': operation.removeprefix('policy-legend-')}
                if operation.endswith(('wrong-child', 'wrong-page')) else
                {'headings': list(accessible_ui.LEGEND_HEADINGS),
                 'rules': [list(rule) for rule in accessible_ui.LEGEND_RULES]})
            if operation == 'policy-legend-expand':
                activated = result.get('legend', {}).get('activated')
                require(type(activated) is bool, 'ui:legend-response')
                projection['activated'] = activated
            require(type(result) is dict and set(result) == {*expected, 'legend'}
                    and result['legend'] == projection, 'ui:legend-response')
            expected['legend'] = result['legend']
        if operation in accessible_ui.MATCH_OPERATIONS:
            value = result.get('match')
            app, action = accessible_ui.BASELINE_MATCH_OPERATIONS.get(operation,
                (accessible_ui.MATCH_APP, operation.removeprefix('match-')))
            if action in ('save', 'cancel', 'reset', 'rejected'):
                require(value == {'closed': action}, 'ui:match-response')
            elif action.startswith('invalid-'):
                key = action.removeprefix('invalid-')
                require(value == {'invalid': key, 'message': accessible_ui.MATCH_INVALID[key]},
                        'ui:match-response')
            elif action in ('wrong-app', 'ambiguous'):
                require(value == {'refusal': action}, 'ui:match-response')
            else:
                require(type(value) is dict and set(value) == {'app', 'rule'}
                        and value['app'] == app
                        and value['rule'] in accessible_ui.MATCH_RULES, 'ui:match-response')
            require(set(result) == {*expected, 'match'}, 'ui:match-response')
            expected['match'] = value
        if operation in accessible_ui.PARENT_REPORT_OPERATIONS:
            if operation == 'parent-report-refused':
                require(result.get('report') == {'refusal': 'absent'}
                        and set(result) == {*expected, 'report'}, 'ui:parent-report-response')
                expected['report'] = result['report']
            else:
                require(set(result) == {*expected, 'feedback'}, 'ui:parent-report-response')
                FeedbackObservation.from_value(result['feedback'])
                require(result['feedback']['draft'] == ('parent-rule-error'
                    if operation == 'parent-report-read' else 'synthetic-first'),
                    'ui:parent-report-response')
                expected['feedback'] = result['feedback']
        if operation in accessible_ui.ACCESS_OPERATIONS:
            value = result.get('access')
            app, action = accessible_ui.BASELINE_ACCESS_OPERATIONS.get(operation,
                (accessible_ui.MATCH_APP, operation.removeprefix('access-')))
            if action in accessible_ui.ACCESS_CHOICES:
                require(value == {'chosen': action}, 'ui:access-response')
            elif action == 'screen':
                require(value == {'page': 'screen'}, 'ui:access-response')
            elif action in ('wrong-row', 'disabled'):
                require(value == {'refusal': action}, 'ui:access-response')
            else:
                require(type(value) is dict and set(value) == {'app', 'choice'}
                        and value['app'] == app
                        and value['choice'] in accessible_ui.ACCESS_CHOICES, 'ui:access-response')
            require(set(result) == {*expected, 'access'}, 'ui:access-response')
            expected['access'] = value
        if operation in ('feedback-open', 'feedback-read', 'feedback-reopen', 'feedback-reread',
                         'feedback-draft', 'feedback-draft-reopen', 'feedback-draft-reread',
                         'feedback-privacy-returned'):
            require(type(result) is dict and set(result) == {*expected, 'feedback'},
                    'ui:feedback-response')
            FeedbackObservation.from_value(result['feedback'])
            require(result['feedback']['draft'] == (
                'synthetic-first' if operation in accessible_ui.FEEDBACK_PRIVACY_OPERATIONS
                else 'initial-empty'), 'ui:feedback-response')
            expected['feedback'] = result['feedback']
        if operation in accessible_ui.RETAINED_PARENT_OPERATIONS:
            if operation == 'retained-parent-absent-refused':
                require(result == {**expected, 'refused': True}, 'ui:retained-parent-response')
                expected['refused'] = True
            elif operation != 'retained-parent-close':
                value = result.get('retained_parent')
                require(type(value) is dict and set(value) == {'window', 'page', 'settings'}
                        and value['page'] in ('screen-limits', 'app-limits'),
                        'ui:retained-parent-response')
                SettingsObservation.from_settings(value['settings'])
                window = value['window']
                require(type(window) is dict and set(window) == {'binding', 'pid', 'endpoint', 'available'}
                        and window['binding'] == 'parent' and window['available'] is True
                        and type(window['pid']) is int and window['pid'] > 0
                        and type(window['endpoint']) is list and len(window['endpoint']) == 2
                        and all(type(part) is str and 0 < len(part) <= 256 for part in window['endpoint'])
                        and window['endpoint'][0].startswith(':') and window['endpoint'][1].startswith('/'),
                        'ui:retained-parent-response')
                require(set(result) == {*expected, 'retained_parent'}, 'ui:retained-parent-response')
                expected['retained_parent'] = value
        if operation in accessible_ui.WINDOW_SWITCH_OPERATIONS or operation.startswith(('draft-switch-', 'files-switch-')):
            if operation == 'switch-viewer-launch':
                expected['provider'] = accessible_ui.validate_shell_metadata(result.get('provider'))
            require(type(result) is dict and set(result) == {*expected, 'window'},
                    'ui:switch-response')
            value = result['window']
            ready = operation.endswith('-ready')
            stage = (operation[:-6] if ready else operation).removeprefix('draft-').removeprefix('files-')
            binding = ('parent' if stage in ('switch-parent-before', 'switch-parent') else
                       'viewer' if stage in ('switch-viewer-launch', 'switch-viewer',
                           'switch-viewer-again', 'switch-viewer-close') else 'feedback')
            require(type(value) is dict and set(value) == {
                    'binding', 'pid', 'endpoint', 'available', *(['feedback'] if binding == 'feedback' and not ready else [])}
                and value['binding'] == binding and value['available'] is True
                and type(value['pid']) is int and value['pid'] > 0
                and type(value['endpoint']) is list and len(value['endpoint']) == 2
                and all(type(part) is str and 0 < len(part) <= 256 for part in value['endpoint'])
                and value['endpoint'][0].startswith(':') and value['endpoint'][1].startswith('/'),
                'ui:switch-response')
            if binding == 'feedback' and not ready:
                if operation.startswith('draft-'):
                    from attachment_composition import compare_formatted_draft
                    compare_formatted_draft(value['feedback'])
                elif operation.startswith('files-'):
                    from attachment_composition import compare_file_draft
                    compare_file_draft(value['feedback'])
                else:
                    FeedbackObservation.from_value(value['feedback'])
                    require(value['feedback']['draft'] == 'synthetic-first', 'ui:switch-response')
            expected['window'] = value
        if operation in accessible_ui.feedback_formats.OPERATIONS and (
                operation.endswith(('-read', '-reopen')) or operation in ('formats-before', 'linked-before')):
            projection = accessible_ui.feedback_formats.expected(operation)
            require(type(result) is dict and set(result) == {*expected, 'formats'}
                    and result['formats'] == projection, 'ui:formats-response')
            expected['formats'] = projection
        if operation in accessible_ui.block_semantics.OPERATIONS and (
                operation in ('block-before', 'block-reopen') or operation.endswith('-read')):
            projection = accessible_ui.block_semantics.expected(operation)
            require(type(result) is dict and set(result) == {*expected, 'blocks'}
                    and result['blocks'] == projection, 'ui:block-response')
            expected['blocks'] = projection
        if operation in ('format-before', 'format-read', 'format-reopen'):
            projection = [
                {'start': 0, 'end': 9, 'weight': 'normal' if operation == 'format-before' else 'bold'},
                {'start': 9, 'end': 23, 'weight': 'normal'},
            ]
            require(type(result) is dict and set(result) == {*expected, 'formatting'}
                    and result['formatting'] == projection, 'ui:format-response')
            expected['formatting'] = projection
        rejection_case = next((case for case in accessible_ui.REJECTION_CASES
                               if operation == f'rejection-{case}-read'), None)
        if rejection_case is not None or operation == 'rejection-reopen':
            require(type(result) is dict and set(result) == {*expected, 'feedback_state'},
                    'ui:rejection-response')
            state = FeedbackStateObservation.from_value(result['feedback_state'])
            projection, explanation = accessible_ui.REJECTION_CASES[rejection_case or 'complex']
            if operation == 'rejection-reopen':
                explanation = 'none'
            require(state.draft == projection and state.validation == explanation
                    and state.send_enabled, 'ui:rejection-response')
            expected['feedback_state'] = result['feedback_state']
        if operation in accessible_ui.FEEDBACK_STATE_PROJECTIONS:
            require(type(result) is dict and set(result) == {*expected, 'feedback_state'},
                    'ui:feedback-state-response')
            state = FeedbackStateObservation.from_value(result['feedback_state'])
            require((state.draft in ('initial-empty', 'trace-prefix', 'states-no-reply'))
                    if operation == 'feedback-trace-sample' else
                    state.draft == accessible_ui.FEEDBACK_STATE_PROJECTIONS[operation],
                    'ui:feedback-state-response')
            expected['feedback_state'] = result['feedback_state']
        if operation in accessible_ui.LENGTH_OBSERVATIONS:
            require(type(result) is dict and set(result) == {*expected, 'feedback_state'},
                    'ui:length-response')
            state = FeedbackStateObservation.from_value(result['feedback_state'])
            projection, validation = accessible_ui.LENGTH_OBSERVATIONS[operation]
            require((state.draft, state.validation, state.send_enabled)
                    == (projection, validation, True), 'ui:length-response')
            expected['feedback_state'] = result['feedback_state']
        text_operations = {**accessible_ui.TEXT_OPERATIONS, **accessible_ui.DUPLICATE_OPERATIONS,
                           **accessible_ui.SCALAR_OPERATIONS, **accessible_ui.SUFFIX_OPERATIONS}
        if operation in text_operations and operation.endswith('-read'):
            binding, _ = text_operations[operation]
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
        if operation in accessible_ui.ALLOWANCE_KEYBOARD_OPERATIONS:
            value, phase = accessible_ui.ALLOWANCE_KEYBOARD_OPERATIONS[operation]
            projection = {'value': value, 'phase': phase}
            require(type(result) is dict and set(result) == {*expected, 'allowance_keyboard'}
                    and result['allowance_keyboard'] == projection
                    and type(result['allowance_keyboard']['value']) is type(value),
                    'ui:allowance-keyboard-response')
            expected['allowance_keyboard'] = projection
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
                    and value['child'] == accessible_ui.CHILD_IDENTITIES[
                        accessible_ui.NAMED_CUSTOM_CHILDREN[child or 'child']]
                    and value['expanded'] is True
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
        if operation in accessible_ui.REVOKE_CANCEL_OPERATIONS | accessible_ui.REVOKE_CONFIRM_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'revoke_cancel'},
                    'ui:revoke-response')
            value = result['revoke_cancel']
            if operation in ('revoke-balances', 'revoke-saved-balances', 'revoke-cleared-balances'):
                fields = {'settings', 'balances'}
                if operation != 'revoke-balances':
                    fields |= {'apps', 'rules'}
                require(type(value) is dict and set(value) == fields,
                        'ui:revoke-response')
                SettingsObservation.from_settings(value['settings'])
                if operation != 'revoke-balances':
                    rows = AppRowsObservation.from_rows(value['apps']).rows
                    rules = value['rules']
                    require(type(rules) is list and len(rules) == len(rows)
                            and all(type(rule) is list and len(rule) == 2
                                    and rule[0] == row[0] and type(rule[1]) is str
                                    and 0 < len(rule[1]) <= 1024
                                    for row, rule in zip(rows, rules)), 'ui:revoke-saved-rule')
                balances = value['balances']
                require(type(balances) is dict and set(balances) == {
                    'child', 'expanded', 'daily', 'one_time', 'total', 'observed_monotonic_ns'}
                    and balances['child'] == value['settings']['child'] == 'fixture-child'
                    and balances['expanded'] is True
                    and type(balances['observed_monotonic_ns']) is int
                    and 0 < balances['observed_monotonic_ns'] < 10**20, 'ui:revoke-response')
                for key in ('daily', 'one_time', 'total'):
                    item = balances[key]
                    require(type(item) is dict and set(item) == {'text', 'seconds', 'precision_seconds'}
                            and type(item['seconds']) is int and type(item['precision_seconds']) is int
                            and item == accessible_ui.duration_projection(item['text']),
                            'ui:revoke-response')
            else:
                projection = ({'refusal': operation.removeprefix('revoke-')}
                              if operation.startswith('revoke-wrong-') or operation in (
                                  'revoke-confirm-wrong-child', 'revoke-confirm-refused') else
                              {'child': 'fixture-child', 'cancelled': True}
                              if operation == 'revoke-cancel' else
                              {'child': 'fixture-child', 'confirmed': True}
                              if operation == 'revoke-confirm' else
                              {'child': 'fixture-child', 'warning': 'time-apps-daily-preserved'})
                require(value == projection, 'ui:revoke-response')
            expected['revoke_cancel'] = value
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
        if operation in accessible_ui.SHELL_PROMPT_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'shell_prompt'}, 'ui:shell-response')
            value = result['shell_prompt']
            projection = {'child': 'fixture-child', 'approver': 'fixture-parent',
                          'duration_seconds': 75, 'allow_soft': True, 'cancel_ready': True,
                          'same_challenge_rechecked': True,
                          'rejected_proofs': list(accessible_ui.SHELL_PROMPT_REFUSALS)}
            require(type(value) is dict and set(value) == {*projection, 'provider', 'challenge_id'}
                    and all(value[key] == item and type(value[key]) is type(item)
                            for key, item in projection.items()), 'ui:shell-response')
            accessible_ui.validate_shell_metadata(value['provider'])
            identity = value['challenge_id']
            require(type(identity) is str and re.fullmatch(r'[0-9a-f]{64}', identity), 'ui:challenge')
            require(not self.challenge_failed and identity not in self.challenges, 'ui:challenge-replay')
            self.challenges.add(identity)
            expected['shell_prompt'] = value
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
            if operation in accessible_ui.MULTIPLE_MATE_BINDINGS:
                child, approver = accessible_ui.MULTIPLE_MATE_BINDINGS[operation]
                projection.update(child=accessible_ui.CHILD_IDENTITIES[child],
                                  approver=accessible_ui.APPROVER_IDENTITIES[approver],
                                  duration_seconds=1800, allow_soft=False)
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
        if operation in accessible_ui.INVALID_REQUEST_OPERATIONS:
            require(type(result) is dict and set(result) == {*expected, 'invalid_choice'}, 'ui:response')
            value = result['invalid_choice']
            require(type(value) is dict and set(value) == {'request', 'validation', 'no_authentication'}
                    and value['no_authentication'] is True
                    and value['validation'] is (accessible_ui.INVALID_REQUEST_OPERATIONS[operation][1] != 'ready'),
                    'ui:kiosk-invalid-response')
            RequestObservation.from_request(value['request'], operation=operation)
            expected['invalid_choice'] = value
        valid_requests = {**accessible_ui.KIOSK_VALID_REQUESTS, **accessible_ui.OVERLAY_VALID_REQUESTS,
                          **accessible_ui.JORDAN_VALID_REQUESTS,
                          **accessible_ui.CHINESE_VALID_REQUESTS}
        if operation in valid_requests:
            require(type(result) is dict and set(result) == {*expected, 'valid_choice'}, 'ui:response')
            value = result['valid_choice']
            fresh = operation in ('overlay-fraction-estimate-refresh', 'jordan-fraction-estimate-refresh')
            require(type(value) is dict and set(value) == {
                    'request', 'estimate', 'observed_monotonic_ns',
                    *({'estimate_read_bounds'} if fresh else set())}
                    and type(value['observed_monotonic_ns']) is int
                    and value['observed_monotonic_ns'] > 0, 'ui:kiosk-valid-response')
            if fresh:
                bounds = value['estimate_read_bounds']
                require(type(bounds) is list and len(bounds) == 2
                        and all(type(endpoint) is int for endpoint in bounds)
                        and 0 < bounds[0] <= bounds[1] == value['observed_monotonic_ns']
                        and bounds[1] - bounds[0] <= 45_000_000_000,
                        'ui:overlay-refresh-bounds')
            RequestObservation.from_request(value['request'], operation=operation)
            estimate = value['estimate']
            if valid_requests[operation][0] == 0:
                require(estimate == {'kind': 'midnight'}, 'ui:kiosk-valid-response')
            else:
                require(type(estimate) is dict and set(estimate) == {
                    'kind', 'text', 'seconds', 'precision_seconds'} and estimate['kind'] == 'fixed',
                    'ui:kiosk-valid-response')
                require(estimate == {'kind': 'fixed', **accessible_ui.duration_projection(estimate['text'],
                    **({'language': 'zh-Hans'} if operation in accessible_ui.CHINESE_VALID_REQUESTS else {}))},
                        'ui:kiosk-valid-response')
                if fresh:
                    require(estimate['precision_seconds'] == 1, 'ui:overlay-refresh-precision')
            expected['valid_choice'] = value
        if (operation in accessible_ui.KIOSK_OPERATIONS
                or operation in accessible_ui.KIOSK_ACCOUNT_REQUESTS
                or operation in accessible_ui.BINDING_REMINDER_SELECTIONS
                or operation in accessible_ui.KIOSK_DISABLED_REQUESTS
                or operation in accessible_ui.TRANSFER_REQUESTS
                or operation == 'overlay-request-form'):
            require(type(result) is dict and set(result) == {*expected, 'request'}, 'ui:response')
            RequestObservation.from_request(result['request'], operation=operation)
            expected['request'] = result['request']
        if operation in ('gdm-child-time-denied', 'gdm-child-denied-return-ready'):
            require(type(result) is dict and set(result) == {*expected, 'denial'}
                    and type(result['denial']) is dict
                    and result['denial'] == {'recipient': 'fixture-child',
                        'reason': 'time-limit', 'desktop_access': False}
                    and result['denial']['desktop_access'] is False, 'ui:time-denial')
            expected['denial'] = result['denial']
            require(self.last_operation == ('gdm-child-recipient-rechecked'
                    if operation == 'gdm-child-time-denied' else 'gdm-child-time-denied'),
                    'ui:denial-order')
        if operation == 'gdm-child-denied-return-state':
            require(self.last_operation == 'gdm-child-denied-return-ready', 'ui:denial-order')
            require(result.get('return_state') in ('account-list', 'child-prompt'), 'ui:denial-return-state')
            expected['return_state'] = result['return_state']
        if operation == 'gdm-child-denied-returned':
            require(self.last_operation == 'gdm-child-denied-return-state', 'ui:denial-order')
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
            require(self.last_operation in ('gdm-standard-focused', 'gdm-product-free-standard-focused',
                                            'gdm-standard-session-select-full',
                                            'gdm-standard-session-chosen'),
                    'ui:recipient-order')
        elif operation == 'gdm-standard-recipient-rechecked':
            require(self.last_operation == 'gdm-standard-recipient', 'ui:recipient-order')
        elif operation == 'gdm-child-wrong-recipient-refused':
            require(self.last_operation == 'gdm-other-focused', 'ui:recipient-order')
        elif operation == 'gdm-child-recipient':
            require(self.last_operation in ('gdm-child-focused', 'gdm-product-free-child-focused'),
                    'ui:recipient-order')
        elif operation == 'gdm-child-recipient-rechecked':
            require(self.last_operation == 'gdm-child-recipient', 'ui:recipient-order')
        if operation in accessible_ui.OVERLAY_REMINDER_OPERATIONS:
            self.overlay_reminder_source = (None if operation in (
                'overlay-reminder-save', 'overlay-reminder-cancel') else result['reminders']['source'])
        if operation in accessible_ui.BINDING_REMINDER_OPERATIONS:
            self.binding_reminder_source = (None if
                accessible_ui.BINDING_REMINDER_OPERATIONS[operation][2] in ('save', 'cancel')
                else result['reminders']['source'])
        elif operation in accessible_ui.BINDING_REMINDER_SELECTIONS:
            self.binding_reminder_source = None
        self.last_operation = operation
        if operation == 'kiosk-approver-baseline':
            self.approver_uids = tuple(result.pop('approver_uids'))
            result['approver_present'] = True
        watch_activity.event('SSH UI observation passed: ' + operation)
        if prompts:
            result['system_prompts'] = prompts
        return result
