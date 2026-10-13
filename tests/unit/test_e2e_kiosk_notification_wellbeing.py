"""Public UI/command doubles and private files; no live user manager/settings."""
import json
import shlex
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from accessible_ui import KIOSK_APPLICATION, TEXT_VALUES, UiError
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from tests.support.modules import load_module
from tests.support.paths import ROOT
from ui_observations import UiObservations


def reminder_ui():
    draft = Node(identity='reminder-list', value=[{'id': 'original', 'value': 1, 'unit': 'minute'}])
    text = Node(identity='reminder-text', states=('showing', 'visible', 'sensitive', 'editable'))
    seconds = Node(identity='reminder-value', states=('showing', 'visible', 'sensitive', 'editable'))
    preview, cancel, save = (Node(identity='reminder-editor-' + action)
                             for action in ('preview', 'cancel', 'save'))
    editor = Node(identity='reminder-editor-dialog', children=[text, seconds,
        Node(identity='reminder-unit', value='minute'), preview, cancel, save])
    preferences = Node(identity='language-dialog', children=[draft,
        Node(identity='preferences-tabs', value='language'), Node(identity='reminder-add'),
        Node(identity='language-cancel')])
    window = Node(identity='kiosk-request-window', children=[preferences, editor,
        Node(identity='kiosk-menu-button'), Node(identity='kiosk-menu-item-preferences')])
    window.bus, window.path = ':1.42', '/public/window'
    for dialog, owner in ((preferences, window), (editor, preferences)):
        dialog.relations = [SimpleNamespace(get_relation_type=lambda: 'controlled-by',
            get_n_targets=lambda: 1, get_target=lambda _, owner=owner: owner)]
    message = Node(identity='kiosk-system-notification-message', value='critical')
    message.getText = Mock(return_value=TEXT_VALUES['installed-reminder-text'][1])
    countdown = Node(identity='kiosk-system-notification-countdown', value='14s')
    banner = Node(identity='kiosk-system-notification', children=[message, countdown], states=())
    notifications = Node(identity='com.puffyslippers.OhNoParentControl.KioskNotifications', children=[banner])
    root = Node(children=[Node(identity=KIOSK_APPLICATION, children=[window]), notifications])
    def show(_):
        banner.states.update(('visible', 'showing', 'sensitive'))
        return True
    preview.action.do_action.side_effect = show
    def discard(_):
        window.children.remove(editor)
        notifications.children.remove(banner)
        return True
    cancel.action.do_action.side_effect = discard
    preferences.children[-1].action.do_action.side_effect = lambda _: window.children.remove(preferences) or True
    return ui_for(root), window, draft, text, seconds, preview, cancel, save, message, countdown


def test_public_preview_observes_literal_critical_banner_then_discards_unsaved_draft():
    ui, window, draft, text, seconds, preview, cancel, save, message, countdown = reminder_ui()
    result = ui.run('kiosk-reminder-preview', '')['reminder']
    assert result == {'source': result['source'], 'banner_surface': True, 'literal': True,
                      'critical': True, 'countdown': True}
    assert ui.run('kiosk-reminder-preview-cancel', '')['reminder'] == {
        'source': result['source'], 'banner_closed': True, 'unsaved_draft_discarded': True}
    text.setText.assert_called_once_with(TEXT_VALUES['installed-reminder-text'][1])
    seconds.setText.assert_called_once_with('15')
    assert preview.action.do_action.call_count == cancel.action.do_action.call_count == 1
    save.action.do_action.assert_not_called()


@pytest.mark.parametrize('mismatch', ['literal', 'urgency', 'countdown', 'owner', 'draft'])
def test_preview_requires_rendered_content_and_refuses_replaced_draft_owner(mismatch):
    ui, window, draft, text, seconds, preview, cancel, save, message, countdown = reminder_ui()
    if mismatch == 'literal':
        message.getText.return_value = 'wrong rendered text'
    elif mismatch == 'urgency':
        message.value = 'normal'
    elif mismatch == 'countdown':
        countdown.value = '60s'
    if mismatch in ('owner', 'draft'):
        ui.run('kiosk-reminder-preview', '')
        if mismatch == 'owner':
            window.bus = ':1.99'
        else:
            draft.value = []
        with pytest.raises(UiError, match='ui:kiosk-reminder-owner'):
            ui.run('kiosk-reminder-preview-cancel', '')
        cancel.action.do_action.assert_not_called()
    else:
        with pytest.raises(UiError, match='ui:kiosk-reminder-(content|countdown)'):
            ui.run('kiosk-reminder-preview', '')
        assert preview.action.do_action.call_count == 1
    save.action.do_action.assert_not_called()


def test_transport_binds_cancellation_to_rendered_banner_owner_and_rejects_process_only_reply():
    transport = SimpleNamespace(call=Mock(), commands=SimpleNamespace(progress=None))
    def stream(argv, *, on_output, **kwargs):
        on_output(transport.call.return_value + b'\n')
        return transport.call.return_value
    transport.call.side_effect = stream
    observations = UiObservations(transport)
    observations.boot_guard = 'b' * 64
    def reply(operation, **fields):
        transport.call.return_value = json.dumps({'operation': operation, 'outcome': 'passed',
            'interface': 'ApplicationUI+external-provider', 'boot_sha256': 'b' * 64,
            'reminder': {'source': 'a' * 64, **fields}}).encode()
        return observations.observe(operation)
    with pytest.raises(EvidenceError, match='ui:kiosk-reminder-order'):
        reply('kiosk-reminder-preview-cancel', banner_closed=True, unsaved_draft_discarded=True)
    with pytest.raises(EvidenceError, match='ui:kiosk-reminder-response'):
        reply('kiosk-reminder-preview', service_running=True)
    reply('kiosk-reminder-preview', banner_surface=True, literal=True, critical=True, countdown=True)
    reply('kiosk-reminder-preview-cancel', banner_closed=True, unsaved_draft_discarded=True)
    assert transport.call.call_args.args[0][-2:] == ['b' * 64, 'a' * 64]


def test_owned_notification_controls_require_application_ui_route():
    ui, window, draft, text, seconds, preview, cancel, save, message, countdown = reminder_ui()
    ui.application_ui = SimpleNamespace()
    with pytest.raises(UiError, match='ui:product-api-required'):
        ui.require_product_route(message)


@pytest.fixture
def ordinary(tmp_path, monkeypatch):
    helper = load_module('private_installed_wellbeing', ROOT / 'tests/integration/system_wellbeing_qualification.py')
    account = SimpleNamespace(pw_uid=1002, pw_gid=1002, pw_dir='/private/home', pw_name=helper.ACCOUNT)
    monkeypatch.setattr(helper.pwd, 'getpwnam', lambda name: account if name == helper.ACCOUNT else
                        SimpleNamespace(pw_uid=999))
    monkeypatch.setattr(helper.guest, 'guard', Mock())
    monkeypatch.setattr(helper.guest, 'PAYLOAD', tmp_path)
    (tmp_path / 'wellbeing_probe.py').write_bytes(b'private-public-client')
    process = tmp_path / 'proc/200'
    process.mkdir(parents=True)
    settings = {'environment': {'DCONF_PROFILE': 'private-profile', 'XDG_CONFIG_HOME': '/private/config'},
                'process_environment': None,
                'service': {'ActiveState': 'active', 'InvocationID': 'b' * 32, 'MainPID': '200'}}
    class Proc:
        def __truediv__(self, name):
            return Proc() if str(name) == '200' else process / name
        def stat(self):
            return SimpleNamespace(st_uid=account.pw_uid)
    real_path = helper.Path
    monkeypatch.setattr(helper, 'Path', lambda value: Proc() if value == '/proc' else real_path(value))
    state = {'ActiveState': 'inactive', 'InvocationID': '0' * 32, 'MainPID': '0'}
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        assert argv[0] == 'systemctl' and argv[-1] == 'user@1002.service'
        if argv[1] == 'start':
            state.update(ActiveState='active', InvocationID='a' * 32, MainPID='100')
        elif argv[1] == 'stop':
            state.update(ActiveState='inactive', InvocationID='0' * 32, MainPID='0')
        else:
            assert argv[1] == 'show'
        return '\n'.join(key + '=' + value for key, value in state.items())
    monkeypatch.setattr(helper.guest, 'run', run)
    def user(argv, **kwargs):
        calls.append(argv)
        assert argv[:7] == ['/usr/bin/setpriv', '--reuid', '1002', '--regid', '1002', '--init-groups', '/usr/bin/env']
        command = argv[next(index for index, value in enumerate(argv)
                            if value in ('systemctl', '/usr/bin/python3')):]
        if command == ['systemctl', '--user', 'show-environment']:
            return '\n'.join(key + '=' + shlex.quote(value)
                             for key, value in settings['environment'].items()).encode()
        if command[:3] == ['systemctl', '--user', 'set-environment']:
            settings['environment'].update(assignment.split('=', 1) for assignment in command[3:])
            return b''
        if command == ['/usr/bin/python3', '-I', '-']:
            assert kwargs['input'] == b'private-public-client'
            assert all(key + '=' + value in argv for key, value in settings['environment'].items())
            return json.dumps({'original': 'default', 'backup_recorded': True,
                               'suppressed': True, 'restored': True}).encode()
        assert command[:2] == ['systemctl', '--user'] and command[-1] == helper.SERVICE
        service = settings['service']
        if command[2] == 'stop':
            service.update(ActiveState='inactive', MainPID='0')
            return b''
        if command[2] == 'start':
            if service['ActiveState'] == 'inactive':
                service.update(ActiveState='active', InvocationID='c' * 32, MainPID='200')
            actual = settings['process_environment']
            if actual is None:
                actual = settings['environment']
            (process / 'environ').write_bytes(b'\0'.join(
                (key + '=' + value).encode() for key, value in actual.items()) + b'\0')
            return b''
        assert command[2] == 'show'
        return '\n'.join(key + '=' + value for key, value in service.items()).encode()
    monkeypatch.setattr(helper.guest.commands, 'run', user)
    return helper, state, calls, process, settings


def test_ordinary_manager_uses_public_client_and_preserves_settings_environment(ordinary):
    helper, state, calls, process, settings = ordinary
    assert helper.qualify() == {'original': 'default', 'backup_recorded': True, 'suppressed': True,
        'restored': True, 'ordinary_settings_environment_retained': True, 'owned_manager_stopped': True}
    assert [call[1] for call in calls if call[0] == 'systemctl' and call[1] != 'show'] == ['start', 'stop']
    assert settings['environment'] == {'DCONF_PROFILE': 'private-profile',
        'XDG_CONFIG_HOME': '/private/config', 'GSETTINGS_BACKEND': 'dconf'}
    operations = [call[call.index('systemctl') + 2] for call in calls
                  if call[0] == '/usr/bin/setpriv' and 'systemctl' in call and call[-1] != 'show-environment']
    assert [operation for operation in operations if operation != 'show'] == [
        'start', 'stop', 'set-environment', 'start']


def test_absent_settings_overrides_get_populated_defaults_without_a_dconf_profile(ordinary):
    helper, state, calls, process, settings = ordinary
    settings['environment'] = {}
    assert helper.qualify()['ordinary_settings_environment_retained'] is True
    assert settings['environment'] == {'XDG_CONFIG_HOME': '/private/home/.config',
                                       'GSETTINGS_BACKEND': 'dconf'}
    assert all(not any(argument.startswith('DCONF_PROFILE=') for argument in call) for call in calls)


def test_existing_settings_overrides_are_never_replaced_with_defaults(ordinary):
    helper, state, calls, process, settings = ordinary
    settings['environment'] = {'DCONF_PROFILE': 'profile with spaces',
        'XDG_CONFIG_HOME': '/private/custom config', 'GSETTINGS_BACKEND': 'keyfile'}
    original = dict(settings['environment'])
    assert helper.qualify()['ordinary_settings_environment_retained'] is True
    assert settings['environment'] == original


def test_ordinary_environment_mismatch_fails_and_stops_only_owned_manager(ordinary):
    helper, state, calls, process, settings = ordinary
    settings['process_environment'] = {'DCONF_PROFILE': 'wrong-target'}
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:settings-target-mismatch'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'


def test_active_ordinary_manager_is_never_adopted_or_stopped(ordinary):
    helper, state, calls, process, settings = ordinary
    state['ActiveState'] = 'active'
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-already-active'):
        helper.qualify()
    assert [call[1] for call in calls] == ['show']


def test_replaced_ordinary_manager_is_never_stopped(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run
    def replacement(argv, **options):
        result = run(argv, **options)
        if argv[-3:] == ['/usr/bin/python3', '-I', '-']:
            state['InvocationID'] = 'c' * 32
        return result
    monkeypatch.setattr(helper.guest.commands, 'run', replacement)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-replaced'):
        helper.qualify()
    assert not any(call[:2] == ['systemctl', 'stop'] for call in calls)


@pytest.mark.parametrize('started', [False, True])
def test_failed_manager_start_cleans_only_a_new_recorded_invocation(ordinary, monkeypatch, started):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.run

    def failed_start(argv, **options):
        if argv[:2] == ['systemctl', 'start']:
            if started:
                run(argv, **options)
            raise helper.guest.GuestError('wellbeing-test:start-failed')
        return run(argv, **options)

    monkeypatch.setattr(helper.guest, 'run', failed_start)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-test:start-failed'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls) is started


@pytest.mark.parametrize('field,value,owned', [
    ('MainPID', '0', True), ('MainPID', 'invalid', True),
    ('InvocationID', 'invalid', False), ('InvocationID', '0' * 32, False),
])
def test_invalid_manager_readiness_stops_only_a_valid_new_invocation(ordinary, monkeypatch, field, value, owned):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.run

    def invalid_start(argv, **options):
        result = run(argv, **options)
        if argv[:2] == ['systemctl', 'start']:
            state[field] = value
        return result

    monkeypatch.setattr(helper.guest, 'run', invalid_start)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:manager-identity'):
        helper.qualify()
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls) is owned


def test_owned_manager_state_change_during_failure_does_not_prevent_cleanup(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run

    def failed_probe(argv, **options):
        result = run(argv, **options)
        if argv[-3:] == ['/usr/bin/python3', '-I', '-']:
            state.update(ActiveState='failed', MainPID='0')
            raise helper.guest.GuestError('wellbeing-test:probe-failed')
        return result

    monkeypatch.setattr(helper.guest.commands, 'run', failed_probe)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-test:probe-failed'):
        helper.qualify()
    assert state['ActiveState'] == 'inactive'
    assert any(call[:2] == ['systemctl', 'stop'] for call in calls)


def test_replaced_service_is_never_stopped_or_given_new_environment(ordinary, monkeypatch):
    helper, state, calls, process, settings = ordinary
    run = helper.guest.commands.run
    shown = 0

    def replacement(argv, **options):
        nonlocal shown
        if argv[-3:] == ['show', '--property=ActiveState,InvocationID,MainPID', helper.SERVICE]:
            shown += 1
            if shown == 2:
                settings['service']['InvocationID'] = 'd' * 32
        return run(argv, **options)

    monkeypatch.setattr(helper.guest.commands, 'run', replacement)
    with pytest.raises(helper.guest.GuestError, match='wellbeing-installed:service-replaced'):
        helper.qualify()
    assert not any('stop' in call and call[-1] == helper.SERVICE for call in calls)
    assert not any('set-environment' in call for call in calls)
    assert state['ActiveState'] == 'inactive'


def test_installed_journey_records_real_ordinary_service_proof_and_stages_invoked_helpers(tmp_path):
    import installed_setup
    from kiosk_notification_wellbeing import KioskNotificationWellbeingJourney, PLAN
    from kiosk_eligible_choices import PLAN as original
    context = SimpleNamespace(directory=tmp_path, lease=SimpleNamespace(
        guard=Mock(), state={'run': 'a' * 32}))
    journey = KioskNotificationWellbeingJourney(context, Mock())
    result = {'original': 'default', 'backup_recorded': True, 'suppressed': True, 'restored': True,
              'ordinary_settings_environment_retained': True, 'owned_manager_stopped': True}
    journey.transport = SimpleNamespace(call=Mock(return_value=json.dumps(result)))
    observed = {}
    journey.check_request('selections-read', observed)
    assert observed == {'engineering_ordinary_wellbeing': result}
    assert journey.transport.call.call_args.args[0][-1] == 'ordinary'
    context.lease.guard.assert_called_once()
    assert PLAN.worker_mode == 'kiosk_notification_wellbeing'
    assert PLAN.screen_tags.keys() >= original.screen_tags.keys()
    bundle = installed_setup.inputs(ROOT)
    assert {'system_kiosk_feedback.py', 'system_wellbeing_qualification.py', 'wellbeing_probe.py'} <= bundle.files.keys()


@pytest.mark.parametrize('refused', ['', 'kiosk-reminder-preview'])
def test_worker_observes_banner_before_cancel_and_never_uses_native_input(monkeypatch, refused):
    from kiosk_notification_wellbeing import EXTRA, PLAN
    from tests.support.e2e_kiosk import WORKER
    from tests.support.perl import run_perl
    ending = '    });\n    1;'
    assert WORKER.count(ending) == 1
    program = WORKER.replace(ending, '    }, 2);\n    1;')
    if refused:
        monkeypatch.setenv('ONPC_TEST_REFUSE_STAGE', refused)
    result = json.loads(run_perl(program).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    if refused:
        assert not result['ok'] and stages[-1] == refused
        assert EXTRA[1] not in stages
    else:
        assert result['ok'] and stages[-2:] == list(EXTRA)
        assert [stage for stage in PLAN.screen_tags if stage in stages] == stages
    boundary = result['events'].index(['stage', 'selections-read'])
    assert not any(event[0] in ('key', 'secret') for event in result['events'][boundary + 1:])
