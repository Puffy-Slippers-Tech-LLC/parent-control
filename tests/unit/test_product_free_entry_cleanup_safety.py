"""005a setup, command identity, evidence and worker refusal regressions."""

import json
import io
import hashlib
import stat
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import accessible_ui
import check_e2e_product_free_entry as check
import check_graphical_smoke as smoke
import installed_journey as shared
import installed_setup
import session_control as control
from owned_commands import CommandError
from parent_setup_qualification import ProductFreeEntryQualification, ParentJourneyQualification
from private_artifacts import EvidenceError
from product_free_entry import PLAN, ProductFreeEntryJourney
from tests.support.desktop_session import RUN_PROBE, props
from tests.support.perl import run_perl
from tests.support.accessible_ui import Node, ui_for
from ui_observations import UiObservations


def test_fixed_selector_and_preparation_reuse_transfer(monkeypatch):
    calls = []
    monkeypatch.setattr(check, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert check.main() == 0
    assert calls == [dict(assets=check.ASSETS, provision_credentials=True, product_free_entry=True)]
    assert ProductFreeEntryQualification.__bases__ == (ParentJourneyQualification,)
    assert ProductFreeEntryQualification.observation_only
    qualification = object.__new__(ProductFreeEntryQualification)
    qualification.verified, qualification.guestfs, qualification.result = Mock(), Mock(), {}
    transfer = Mock()
    monkeypatch.setattr(smoke, 'AssetTransfer', Mock(return_value=transfer))
    context = SimpleNamespace(lease=Mock())
    qualification.prepare_context(context)
    transfer.provision.assert_called_once_with(context.lease, qualification.guestfs)
    assert context.product_free is True and context.asset_transfer is transfer
    assert qualification.journey(context, Mock()).plan is PLAN


@pytest.mark.parametrize('extra', [{}, {'install': True}, {'gdm_product_free': True},
                                   {'challenges': True}, {'fresh_desktop': 'parent'}])
def test_selector_refuses_missing_assets_or_other_modes(extra):
    kwargs = dict(assets=check.ASSETS, provision_credentials=True, **extra) if extra else {}
    with pytest.raises(CommandError, match='product-free-entry-prerequisites'):
        smoke.main(product_free_entry=True, **kwargs)


@pytest.mark.parametrize('fault', ['', 'install', 'snapshot', 'type', 'transfer'])
def test_product_free_setup_never_installs_and_requires_verified_transfer(tmp_path, monkeypatch, fault):
    transfer = Mock()
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=transfer,
        host_key='fixture-key', commands=Mock(), lease=SimpleNamespace(
            source=SimpleNamespace(uuid='fixture'), view=SimpleNamespace(domain_id=7),
            state={'run': 'a' * 32}, guard=Mock()))
    if fault == 'install': context.install_current_package = True
    if fault == 'snapshot': context.installed_snapshot = 'onpc-v1.1'
    if fault == 'type': context.install_current_package = 1
    if fault == 'transfer': transfer.observe.side_effect = EvidenceError('transfer:booted-assets-mismatch')
    setup = Mock(side_effect=AssertionError('must not install or provision'))
    transport = Mock()
    monkeypatch.setattr(installed_setup, 'InstalledSetup', setup)
    monkeypatch.setattr(shared, 'Transport', Mock(return_value=transport))
    monkeypatch.setattr(shared.system, 'address', Mock(return_value='fixture-host'))
    monkeypatch.setattr(shared, 'ReadOnlyObservations', Mock())
    progress = Mock()
    journey = ProductFreeEntryJourney(context, progress)
    journey.steps = [{'stage': 'ready'}]
    (tmp_path / 'setup-detached.request.json').write_text(json.dumps(
        {'stage': 'setup-detached', 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / 'setup-detached.reply.json').exists()
        progress.assert_not_called()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        transfer.observe.assert_called_once_with(journey.vm)
        assert progress.call_args.args[1]['setup']['product_free_baseline'] is True
    setup.assert_not_called()
    if fault in ('install', 'snapshot', 'type'): transport.probe_ready.assert_not_called()


@pytest.mark.parametrize('prior', ['gdm-product-free-focused', 'gdm-product-free-list',
                                  'gdm-standard-focused', None])
def test_recipient_needs_fresh_correct_focus_and_two_proofs(prior):
    transport = SimpleNamespace(call=Mock())
    ui = UiObservations(transport)
    ui.last_operation = prior
    for operation in ('gdm-parent-recipient', 'gdm-parent-recipient-rechecked'):
        transport.call.return_value = json.dumps(dict(
            operation=operation, outcome='passed', interface='AT-SPI')).encode()
        if prior != 'gdm-product-free-focused':
            with pytest.raises(EvidenceError, match='recipient-order'): ui.observe(operation)
            break
        assert ui.observe(operation)['outcome'] == 'passed'


@pytest.mark.parametrize('fault', ['', 'digest', 'provenance', 'durability'])
def test_package_context_cannot_acknowledge_mismatched_or_unrecorded_input(tmp_path, monkeypatch, fault):
    verified = SimpleNamespace(inputs={'package_sha256': 'a' * 64}, recheck=Mock())
    if fault == 'provenance': verified.recheck.side_effect = EvidenceError('changed-input')
    progress = Mock(side_effect=OSError('storage failed') if fault == 'durability' else None)
    journey = ProductFreeEntryJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock(), verified=verified), progress)
    journey.steps = [{'stage': stage} for stage in PLAN.stages[:-1]]
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    journey.transport = Mock()
    monkeypatch.setattr(control, 'observe', Mock(return_value={
        'operation': 'parent-command-context', 'outcome': 'passed',
        'package_sha256': ('c' if fault == 'digest' else 'a') * 64}))
    (tmp_path / 'command-context.request.json').write_text(json.dumps(
        {'stage': 'command-context', 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'command-context.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert (tmp_path / 'command-context.reply.json').exists()
        assert progress.call_args.args[1]['assertion']['id'] == 'administrator-package-context'


@pytest.mark.parametrize('current', [dict(g=props('120', kind='greeter')),
                                   dict(p=props()), {}, dict(p=props('1001'))])
def test_wrong_entry_qualification_requires_actual_greeter_and_refusal(monkeypatch, current):
    monkeypatch.setattr(control.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: SimpleNamespace(pw_uid=1000))
    monkeypatch.setattr(control, 'sessions', lambda: current)
    drop = Mock(side_effect=AssertionError('wrong entry must not bind user'))
    monkeypatch.setattr(control.os, 'setuid', drop)
    if 'g' in current:
        assert control.execute('parent-command-refused')['wrong_entry_refused'] is True
    else:
        with pytest.raises(control.SessionError): control.execute('parent-command-refused')
    drop.assert_not_called()


@pytest.mark.parametrize('fault', ['owner', 'locked', 'changed', 'authority'])
def test_admin_context_refuses_before_package_access(monkeypatch, fault):
    monkeypatch.setattr(control.os, 'geteuid', Mock(side_effect=[0, 1000]))
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control.os, 'environ', {})
    for name in ('initgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(control.os, name, Mock())
    monkeypatch.setattr(control.os, 'getgroups', lambda: [] if fault == 'authority' else [27])
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props('1001' if fault == 'owner' else '1000',
                    locked='yes' if fault == 'locked' else 'no')},
        {'8' if fault == 'changed' else '7': props()}]))
    opening = Mock(side_effect=AssertionError('must refuse before file access'))
    monkeypatch.setattr(control.os, 'open', opening)
    with pytest.raises(control.SessionError): control.execute('parent-command-context')
    opening.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'recipient-qualified', 'recipient-rechecked', 'command-context'])
def test_worker_uses_shared_login_and_stops_on_uncertain_result(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_product_free_entry;')
    source = source.replace('onpc_desktop_session::run', 'onpc_product_free_entry::run')
    source = source.replace('}, $action);', '});')
    source = source.replace("push @events, ['stage', $_[0]];",
                            "push @events, ['stage', $_[0]]; die 'fixed failure' if $_[0] eq $action;")
    result = json.loads(run_perl(source, fault).stdout)
    assert bool(result['ok']) == (not fault)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    assert result['events'].count(['secret']) == (0 if fault.startswith('recipient-') else 1)
    if not fault: assert result['events'][-1] == ['power', 'off']


@pytest.mark.parametrize('fault', ['', 'owner', 'writable', 'hardlink', 'special',
                                   'replaced', 'parent', 'changed-session'])
def test_admin_package_read_binds_identity_and_digest_without_install(monkeypatch, fault):
    account = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name='fixture')
    monkeypatch.setattr(control.os, 'geteuid', Mock(side_effect=[0, 1000]))
    monkeypatch.setattr(control.pwd, 'getpwnam', lambda _: account)
    monkeypatch.setattr(control.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(control, 'environment', lambda _: {})
    monkeypatch.setattr(control.os, 'environ', {})
    for name in ('initgroups', 'setgid', 'setuid'):
        monkeypatch.setattr(control.os, name, Mock())
    monkeypatch.setattr(control.os, 'getgroups', lambda: [27])
    monkeypatch.setattr(control, 'sessions', Mock(side_effect=[
        {'7': props()}, {'7': props()},
        {'8' if fault == 'changed-session' else '7': props()}]))
    info = SimpleNamespace(st_uid=1 if fault == 'owner' else 0, st_gid=0,
        st_mode=(stat.S_IFIFO if fault == 'special' else stat.S_IFREG) |
                (0o666 if fault == 'writable' else 0o644),
        st_nlink=2 if fault == 'hardlink' else 1, st_dev=1, st_ino=2,
        st_size=7, st_mtime_ns=0, st_ctime_ns=0)
    parent = Mock()
    parent.resolve.return_value = parent
    parent.stat.return_value = SimpleNamespace(st_uid=1 if fault == 'parent' else 0, st_mode=0o755)
    path = SimpleNamespace(parent=parent, lstat=Mock(return_value=SimpleNamespace(
        **{**vars(info), 'st_ino': 3 if fault == 'replaced' else 2})))
    monkeypatch.setattr(control, 'Path', lambda _: path)
    stream = io.BytesIO(b'package')
    stream.fileno = lambda: 123
    monkeypatch.setattr(control.os, 'open', Mock(return_value=123))
    monkeypatch.setattr(control.os, 'fdopen', lambda *_: stream)
    monkeypatch.setattr(control.os, 'fstat', lambda _: info)
    submit = Mock(side_effect=AssertionError('no system mutation'))
    monkeypatch.setattr(control, 'submit', submit)
    if fault:
        with pytest.raises(control.SessionError): control.execute('parent-command-context')
    else:
        result = control.execute('parent-command-context')
        assert result['administrator'] is True
        assert result['package_sha256'] == hashlib.sha256(b'package').hexdigest()
    submit.assert_not_called()


def test_wrong_entry_action_is_recorded_only_after_refusal(tmp_path, monkeypatch):
    from product_free_entry import refuse_command
    context = SimpleNamespace(transport=Mock())
    observe = Mock(return_value={'wrong_entry_refused': True})
    monkeypatch.setattr(control, 'observe', observe)
    guard = Mock()
    assert refuse_command(context, guard) == {'wrong_entry_refused': True}
    observe.assert_called_once_with(context.transport, 'parent-command-refused')
    assert guard.call_count == 2
    observe.side_effect = control.SessionError('unexpected entry')
    with pytest.raises(control.SessionError): refuse_command(context, guard)


@pytest.mark.parametrize('operation', ['gdm-product-free-provider', 'parent-desktop-provider'])
@pytest.mark.parametrize('fault', ['', 'missing', 'locale', 'keyboard', 'version', 'extra'])
def test_provider_transport_requires_complete_bounded_tuple(operation, fault):
    shell = {'version': '50.1-0ubuntu1.2', 'locale': 'en_US.UTF-8',
             'keyboard': [['xkb', 'us']]}
    if fault == 'locale': shell['locale'] = 'unbounded arbitrary text'
    if fault == 'keyboard': shell['keyboard'] = []
    if fault == 'version': shell['version'] = ''
    provider = ({'shell': shell, 'gdm_version': '50.0-1ubuntu1'}
                if operation.startswith('gdm-') else shell)
    if fault == 'extra': provider['unregistered'] = True
    result = {'operation': operation, 'interface': 'AT-SPI', 'outcome': 'passed'}
    if fault != 'missing': result['provider'] = provider
    ui = UiObservations(SimpleNamespace(call=Mock(return_value=json.dumps(result).encode())))
    if fault:
        with pytest.raises((EvidenceError, accessible_ui.UiError)):
            ui.observe(operation)
    else:
        assert ui.observe(operation)['provider'] == provider


@pytest.mark.parametrize('greeter', [False, True])
def test_provider_metadata_reads_selected_owner_environment(monkeypatch, greeter):
    ui = ui_for(Node())
    owner = SimpleNamespace(get_process_id=lambda: 4321)
    ui.gdm_semantic_rows = Mock(return_value=(owner, {}))
    ui.shell_search_snapshot = Mock(return_value=(owner, [], {}, {}))
    paths = []
    def path(value):
        paths.append(value)
        return SimpleNamespace(read_bytes=lambda:
            b'LANG=de_DE.UTF-8\0LC_MESSAGES=en_GB.UTF-8\0LC_ALL=en_US.UTF-8\0')
    monkeypatch.setattr(accessible_ui, 'Path', path)
    monkeypatch.setenv('LC_ALL', 'fr_FR.UTF-8')
    sources = SimpleNamespace(unpack=lambda: [('xkb', 'us')])
    settings = SimpleNamespace(get_value=lambda key: sources if key == 'sources' else None)
    gio = SimpleNamespace(Settings=SimpleNamespace(new=lambda schema: settings))
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gio=gio))
    system_sources = Mock(return_value=[['xkb', 'de+nodeadkeys']])
    monkeypatch.setattr(accessible_ui, 'greeter_keyboard_sources', system_sources)
    query = Mock(side_effect=lambda argv, **kw:
                 '50.0-1ubuntu1' if argv[-1] == 'gdm3' else '50.1-0ubuntu1.2')
    monkeypatch.setattr(accessible_ui.subprocess, 'check_output', query)
    result = ui.gdm_provider_metadata() if greeter else ui.shell_provider_metadata()
    shell = result['shell'] if greeter else result
    assert shell == {'version': '50.1-0ubuntu1.2', 'locale': 'en_US.UTF-8',
                     'keyboard': [['xkb', 'de+nodeadkeys']] if greeter else [['xkb', 'us']]}
    assert paths == ['/proc/4321/environ']
    if greeter:
        ui.gdm_semantic_rows.assert_called_once_with(
            (accessible_ui.PARENT,), excluded=(accessible_ui.KIOSK,))
        assert result['gdm_version'] == '50.0-1ubuntu1'
        system_sources.assert_called_once_with()
    else:
        ui.shell_search_snapshot.assert_called_once_with()
        system_sources.assert_not_called()


@pytest.mark.parametrize(('properties', 'expected'), [
    ({'X11Layout': 'us', 'X11Variant': ''}, [['xkb', 'us']]),
    ({'X11Layout': 'us,de', 'X11Variant': ',nodeadkeys'},
     [['xkb', 'us'], ['xkb', 'de+nodeadkeys']]),
    ({'X11Layout': 'us,de', 'X11Variant': ''}, [['xkb', 'us'], ['xkb', 'de']]),
    ({'X11Layout': '', 'X11Variant': ''}, None),
    ({'X11Layout': 'us'}, None),
    ({'X11Layout': ['us'], 'X11Variant': ''}, None),
    ({'X11Layout': 'us', 'X11Variant': None}, None),
    ({'X11Layout': 'us,', 'X11Variant': ''}, None),
    ({'X11Layout': 'us', 'X11Variant': ',extra'}, None),
    ({'X11Layout': ','.join(['us'] * 9), 'X11Variant': ''}, None),
    ({'X11Layout': 'us', 'X11Variant': 'arbitrary text'}, None),
    ({'X11Layout': 'u' * 1025, 'X11Variant': ''}, None),
])
def test_greeter_keyboard_uses_bounded_locale1_configuration(monkeypatch, properties, expected):
    bus = Mock()
    bus.call_sync.return_value.unpack.return_value = (properties,)
    gio = SimpleNamespace(bus_get_sync=Mock(return_value=bus),
        BusType=SimpleNamespace(SYSTEM='system'), DBusCallFlags=SimpleNamespace(NONE=0),
        Settings=Mock(side_effect=AssertionError('greeter must not read desktop settings')))
    glib = SimpleNamespace(Variant=lambda signature, value: (signature, value),
                           VariantType=SimpleNamespace(new=lambda signature: signature))
    monkeypatch.setitem(sys.modules, 'gi.repository', SimpleNamespace(Gio=gio, GLib=glib))
    if expected is None:
        with pytest.raises(accessible_ui.UiError, match='greeter-keyboard-metadata'):
            accessible_ui.greeter_keyboard_sources()
    else:
        assert accessible_ui.greeter_keyboard_sources() == expected
    gio.bus_get_sync.assert_called_once_with('system', None)
    bus.call_sync.assert_called_once_with(
        'org.freedesktop.locale1', '/org/freedesktop/locale1',
        'org.freedesktop.DBus.Properties', 'GetAll',
        ('(s)', ('org.freedesktop.locale1',)), '(a{sv})', 0, 5000, None)
    # Failure must propagate without synthesizing a default layout or falling
    # back to the greeter account's unrelated desktop configuration.
    bus.call_sync.side_effect = RuntimeError('locale1 unavailable')
    with pytest.raises(RuntimeError, match='locale1 unavailable'):
        accessible_ui.greeter_keyboard_sources()


@pytest.mark.parametrize('stage', ['installed-greeter', 'desktop'])
@pytest.mark.parametrize('fault', ['', 'provider', 'durability'])
def test_entry_never_acknowledges_missing_provider_evidence(tmp_path, monkeypatch, stage, fault):
    monkeypatch.setattr(control, 'observe', Mock(return_value={
        'operation': 'parent-continuous-activity', 'outcome': 'passed',
        'interface': 'system session', 'idle_delay_seconds': 0,
        'previous_idle_delay_seconds': 300}))
    progress = Mock(side_effect=OSError('storage failed') if fault == 'durability' else None)
    journey = ProductFreeEntryJourney(SimpleNamespace(directory=tmp_path,
        product_free=True, asset_transfer=Mock()), progress)
    journey.steps = [{'stage': item} for item in PLAN.stages[:PLAN.stages.index(stage)]]
    journey.vm = SimpleNamespace(read=Mock(return_value={'boot_sha256': 'b' * 64}))
    provider = {'version': '50.1', 'locale': 'en_US.UTF-8', 'keyboard': [['xkb', 'us']]}
    journey.ui = SimpleNamespace(boot_proof='b' * 64, observe=Mock(side_effect=[
        {'outcome': 'passed'}, EvidenceError('provider missing') if fault == 'provider'
        else {'provider': provider}]))
    (tmp_path / (stage + '.request.json')).write_text(json.dumps(
        {'stage': stage, 'screenshot': None}))
    if fault:
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / (stage + '.reply.json')).exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        assert progress.call_args.args[1]['provider'] == provider
        assert (tmp_path / (stage + '.reply.json')).exists()


@pytest.mark.parametrize('greeter', [False, True])
def test_provider_route_requires_owned_public_surface_before_metadata(greeter):
    ui = ui_for(Node())
    operation = 'gdm-product-free-provider' if greeter else 'parent-desktop-provider'
    reader = Mock(side_effect=AssertionError('must not read unowned metadata'))
    ui._shell_provider_metadata = reader
    if greeter:
        ui.gdm_semantic_rows = Mock(side_effect=accessible_ui.UiError('wrong-owner'))
    else:
        ui.standard_shell_desktop = Mock(side_effect=accessible_ui.UiError('wrong-owner'))
    with pytest.raises(accessible_ui.UiError, match='wrong-owner'):
        ui.run(operation, '')
    reader.assert_not_called()
