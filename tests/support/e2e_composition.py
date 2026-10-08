"""Shared source-composition review for ready E2E recipes.

Only checkout source reads and private Python values; no live test resources.
"""

import ast
import json
from pathlib import Path

from tests.support.paths import ROOT


INVENTORY = json.loads((ROOT / 'tests/e2e/scenarios.json').read_text())
READY = [(scenario, variant) for scenario in INVENTORY['scenarios']
         for variant in scenario['variants'] if variant['status'] == 'ready']
CASE_MODULES = {Path(variant['executable']['path']).stem for _, variant in READY}
# Reviewed composition APIs, not a list of cases. Adding a ready inventory row
# is sufficient to exercise it. New mechanics belong behind a shared API.
APIS = {
    'countdown': {'CountdownObservation', 'check_countdown_balance'},
    'access_choices': {'AccessChoiceJourney'},
    'policy_edits': {'policy_edit'},
    'match_rules': {'MatchRuleJourney', 'MATCH_RULES', 'match_edit'},
    'parent_reports': {'ParentReportJourney', 'report_review', 'report_close'},
    'account_fixture': {'DynamicAccountFixture', 'EmptyAccountFixture', 'station_fixture_actions'},
    'installed_journey': {'JourneyPlan', 'InstalledJourney', 'matched_screens', 'record_installed_journey'},
    'journey_blocks': {'fresh_desktop', 'parent_management', 'parent_reopen', 'parent_search', 'observed_text', 'language_selection',
                       'product_free_desktop', 'package_installation', 'restart_reentry', 'reboot_desktop', 'station_entry',
                       'custom_child_selection', 'custom_save_entry', 'ordinary_custom_save', 'allowance_selection',
                       'filter_screens', 'rejected_gdm_return', 'native_usable_app', 'native_activity_entry', 'overlay_entry',
                       'overlay_license_read', 'prefixed_stages', 'custom_allowance'},
    'native_fixtures': {'fixture_actions', 'check_catalogue', 'expected_rows', 'search_rows', 'catalogue_rows',
                        'CataloguePolicyJourney'},
    'journey_checks': {'allowed_app_rows', 'installed_accounts', 'access_choice', 'AllowanceJourney',
                       'policy_projection', 'request_choices', 'checked_language',
                       'approval_estimate', 'public_checks', 'restart_instructions'},
    'real_interval': {'interval_action'},
    'request_flow': {'prepared_request', 'daily_station_entry', 'overlay_authentication', 'CHOICES', 'chinese_request'},
    'kiosk_approved_flow': {'approved_request', 'obtain_time', 'chinese_approval'},
    'chinese_current_install': {'current_actions'},
    'chinese_journey': {'chinese_journey'},
    'language_composition': {'language_journey', 'public_language_value', 'language_policy', 'offline_language_actions'},
    'approval_flow': {'rejected_request'},
    'request_composition': {'KioskRequestJourney'},
    'package_install': {'check_install_result', 'observe_current_install', 'submit_install'},
    'restart_notice': {'RestartNoticeJourney'},
    'chinese_kiosk_lifecycle': {'ChinesePresentationMixin', 'renewed_desktop',
                              'renewed_language_entry', 'set_desktop_language'},
    'package_journey': {'record_package_journey'},
    'package_lifecycle': {'record_lifecycle_journey'},
    'package_command': {'BINDING', 'REMOVE', 'REINSTALL', 'PURGE', 'FRESH_INSTALL'},
    'accessible_ui': {'MATCH_APP'},
    'ui_observations': {'SettingsObservation', 'AppRowsObservation',
                        'AppActivityObservation', 'compare_app_activity'},
    'feedback_composition': {'FeedbackValidationJourney', 'FeedbackDraftJourney', 'text_fragment',
                             'privacy_review'},
    'window_switch': {'window_switch_entry'},
    'feedback_formats': {'all_formats', 'format_stages'},
    'feedback_length': {'length_boundary'},
    'feedback_states': {'edit_states'},
    'feedback_rejection': {'STAGES'},
    'allowance_boundaries': {'BOUNDARY_SCREENS', 'boundary_screens'},
    'allowance_values': {'REPRESENTATIVE_PRESETS'},
    'file_chooser': {'stage_files', 'cleanup_files'},
    'synthetic_files': {'fixture_actions', 'read_declared_text', 'read_declared_zip',
                        'change_attachment_source', 'save_destination_actions', 'diagnostic_export_actions'},
    'attachment_composition': {'file_handoff', 'boundary_batch', 'AttachmentJourney',
                               'chooser_preservation', 'attachment_removal',
                               'save_handoff', 'save_cancellation', 'diagnostic_export',
                               'DiagnosticExportJourney'},
    'serial_harness': {'PLAN', 'SERIAL_STAGES', 'matched_screens', 'record_serial_journey',
                       'validate_completion', 'validate_stages'},
}


def composition_errors(source, case_modules, apis=APIS):
    """Review all definitions, including renamed callbacks and hidden helpers."""
    tree = ast.parse(source)
    allowed = {'dict', 'tuple', 'zip', 'super'}
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                errors.append('unreviewed module import')
            modules = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                       else [item.name for item in node.names])
            if (any(set(module.split('.')) & case_modules for module in modules)
                    or isinstance(node, ast.ImportFrom)
                    and any(item.name in case_modules for item in node.names)):
                errors.append('case dependency')
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if not node.level and item.name in apis.get(node.module, set()):
                        allowed.add(item.asname or item.name)
                    else:
                        errors.append('unreviewed import: ' + item.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(not isinstance(statement, (ast.Expr, ast.Assign, ast.Return))
                   for statement in node.body):
                errors.append('runtime mechanics in ' + node.name)
            for call in (item for item in ast.walk(node) if isinstance(item, ast.Call)):
                if isinstance(call.func, ast.Attribute) and not (
                        call.func.attr == '__init__' and isinstance(call.func.value, ast.Call)
                        and isinstance(call.func.value.func, ast.Name)
                        and call.func.value.func.id == 'super'):
                    errors.append('runtime method call in ' + node.name)
        if isinstance(node, (ast.With, ast.AsyncWith, ast.Try, ast.While, ast.Lambda)):
            errors.append('case-owned runtime boundary')
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Name):
            if call.func.id not in allowed:
                errors.append('unreviewed call: ' + call.func.id)
        elif isinstance(call.func, ast.Attribute):
            if call.func.attr not in ('items', 'update', '__init__'):
                errors.append('unreviewed method: ' + call.func.attr)
        else:
            errors.append('indirect call')
    return errors
