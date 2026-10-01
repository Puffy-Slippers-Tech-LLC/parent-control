"""Shared request controls remain usable at supported display scales."""

import pytest

from tests.support.request_form import calls, launch_request


pytestmark = pytest.mark.ui


def test_child_preview_language_survives_overlay_cancel_and_reopen(
        launch_ui, automation, wait_for_accessible_state, tmp_path):
    from tests.support.localization_review import switch_language
    ui, wait = automation, wait_for_accessible_state
    language_file = tmp_path / 'language'
    environment = {'OH_NO_PARENT_CONTROL_PREVIEW_LANGUAGE_FILE': str(language_file)}
    process, _log = launch_ui('child_overlay_preview', environment_overrides=environment)
    switch_language(ui, wait, 'kiosk', 'de')
    assert language_file.read_text(encoding='utf-8') == 'de'
    ui.activate('kiosk-request-cancel')
    process.wait(timeout=10)
    assert language_file.read_text(encoding='utf-8') == 'de'
    launch_ui('child_overlay_preview', environment_overrides=environment)
    wait(lambda: ui.text('kiosk-request-submit') == 'ANFRAGEN',
         'reopened overlay reads the shared preview language')


@pytest.mark.parametrize('overlay,dpi_scale', [(False, 1), (True, 1.25)])
@pytest.mark.parametrize('language', ['de', 'fr', 'ru', 'pl', 'ja', 'zh-Hans'])
def test_translated_request_preserves_choices_and_custom_draft(
        launch_ui, automation, request_display_scale, wait_for_accessible_state,
        tmp_path, overlay, dpi_scale, language):
    from tests.support.keyboard import key_combo, type_text
    from tests.support.localization_review import switch_language, review_frame
    ui, wait = automation, wait_for_accessible_state
    _process, path = launch_request(launch_ui, tmp_path, overlay=overlay,
                                   scenario='remembered', wait_for_application=False)
    wait(lambda: ui.state('kiosk-request-submit', ui.api.StateType.SENSITIVE), 'ready')
    ui.focus('kiosk-custom-duration')
    key_combo(ui, 'kiosk-custom-duration', '<Control>a', state=ui.api.StateType.FOCUSED)
    type_text(ui, 'kiosk-custom-duration', '2.75')
    wait(lambda: ui.content('kiosk-custom-duration') == '2.75', 'custom draft typed')
    switch_language(ui, wait, 'kiosk', language)
    assert ui.content('kiosk-custom-duration') == '2.75'
    assert ui.showing('kiosk-approver-selected-1010')
    assert ui.showing('kiosk-child-selected-1001')
    assert ui.state('kiosk-soft-apps-toggle', ui.api.StateType.CHECKED)
    visible = {'de': 'ANFRAGEN', 'fr': 'DEMANDER', 'ru': 'ЗАПРОСИТЬ',
               'pl': 'POPROŚ', 'ja': 'リクエスト', 'zh-Hans': '提交请求'}
    assert ui.text('kiosk-request-submit') == visible[language]
    review_frame('request-' + language + ('-overlay' if overlay else '-kiosk'))
    soft_label = ui.text('kiosk-soft-apps-label')
    ui.activate('kiosk-request-submit')
    method = 'RequestOwnAccess' if overlay else 'RequestAccess'
    wait(lambda: bool(calls(path, method)), 'translated request submits')
    assert calls(path, method)[0]['values'] == (
        [1010, 165, True] if overlay else [1001, 1010, 165, True])
    soft = {'de': 'Vorübergehend freigebbare Apps erlauben',
            'fr': 'Autoriser les applications pouvant être débloquées temporairement',
            'ru': 'Разрешить приложения с временным доступом',
            'pl': 'Zezwól na aplikacje z blokadą tymczasową',
            'ja': '一時的に許可できるアプリを許可', 'zh-Hans': '允许使用需授权的应用'}
    assert soft_label == soft[language]


@pytest.mark.parametrize("overlay,dpi_scale", (
    (False, 1), (True, 1), (False, 1.25), (True, 1.25),
), ids=("kiosk", "child-overlay", "kiosk-fractional", "child-fractional"))
def test_request_layout_keeps_all_choices_and_submission_reachable(
        launch_ui, automation, request_display_scale, wait_for_accessible_state,
        tmp_path, overlay, dpi_scale):
    """Exercise the full form through public IDs after actual display scaling."""
    _process, path = launch_request(
        launch_ui, tmp_path, overlay=overlay, wait_for_application=False,
    )
    ui = automation
    wait_for_accessible_state(lambda: ui.find("kiosk-request-submit") is not None,
                              "scaled form publishes request control")
    wait_for_accessible_state(
        lambda: ui.state("kiosk-request-submit", ui.api.StateType.SENSITIVE),
        "scaled form is ready",
    )
    ui.activate("kiosk-approver-selector")
    wait_for_accessible_state(lambda: ui.find("kiosk-approver-choice-1010") is not None,
                              "expanded choices are published")
    ui.activate("kiosk-approver-choice-1010")
    ui.activate("kiosk-duration-300")
    ui.reveal("kiosk-request-status")
    ui.activate("kiosk-request-submit")
    method = "RequestOwnAccess" if overlay else "RequestAccess"
    wait_for_accessible_state(lambda: bool(calls(path, method)),
                              "scaled form submits selected values")
    assert calls(path, method)[0]["values"] == (
        [1010, 300, False] if overlay else [1001, 1010, 300, False]
    )
