"""Private API/session/transport doubles, pytest files and waited Perl children.

No live accounts, bus, VM, desktop, shared cache or expensive work. Compatible
in both unit and cleanup inventories. The inherited VM envelope owns cleanup.
"""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import account_language as control
import account_language_guest as guest
import desktop_language_qualification as qualification
import check_e2e_desktop_language as selector
import check_graphical_smoke as smoke
from owned_commands import CommandError
from parent_setup_qualification import DesktopLanguageQualification, ProductFreeEntryQualification
from private_artifacts import EvidenceError
from tests.support.desktop_session import props, RUN_PROBE
from tests.support.perl import run_perl


def receipt():
    return {'accounts': {'1000': {'name': guest.sessions.ACCOUNTS['parent'], 'language': 'en_US.UTF-8'},
                         '1001': {'name': guest.sessions.ACCOUNTS['standard'], 'language': 'en_US.UTF-8'},
                         '900': {'name': 'station', 'language': 'en_US.UTF-8'}},
            'target_uid': '1001', 'sessions': {'7': props()},
            'system_locale': ['LANG=en_US.UTF-8'], 'observer_locale': {'LANG': 'C.UTF-8'},
            'product_free': True}


def controller(responses):
    transport = SimpleNamespace(config={'run': 'owned', 'domain_uuid': 'fixture'},
        guard=Mock(), call=Mock(side_effect=[
            (json.dumps(value, sort_keys=True) + '\n').encode() for value in responses]))
    verified = SimpleNamespace(recheck=Mock())
    return control.AccountLanguage(transport, verified)


@pytest.fixture
def guest_rig(monkeypatch):
    parent = SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_name=guest.sessions.ACCOUNTS['parent'])
    child = SimpleNamespace(pw_uid=1001, pw_gid=1001, pw_name=guest.sessions.ACCOUNTS['standard'])
    users = {parent.pw_name: parent, child.pw_name: child}
    monkeypatch.setattr(guest.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(guest.pwd, 'getpwnam', users.__getitem__)
    monkeypatch.setattr(guest.pwd, 'getpwall', lambda: list(users.values()))
    monkeypatch.setattr(guest.grp, 'getgrnam', lambda _: SimpleNamespace(gr_gid=27))
    monkeypatch.setattr(guest.os, 'getgrouplist', lambda *_: [27])
    current = {'7': props()}
    monkeypatch.setattr(guest.sessions, 'sessions', lambda: copy.deepcopy(current))
    monkeypatch.setattr(guest.sessions, 'call', Mock(return_value='C\nzh_CN.utf8\n'))
    api = Mock(resolve=Mock(return_value=(guest.ROOT + '/User1001', 'en_US.UTF-8')))
    return api, current, users


@pytest.mark.parametrize('language', ['zh_CN.UTF-8', 'zh_CN'])
def test_supported_setter_is_single_input_and_independent_confirmation_is_two_reads(language):
    before = receipt()
    after = copy.deepcopy(before)
    after['accounts']['1001']['language'] = language
    owner = controller([{'accepted': True}, after, after])
    owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
    result = owner.confirm(before)
    assert result['confirmed_language'] == language
    assert result['requested_locale'] == guest.LOCALE
    assert result['session_renewal_required'] is True
    assert result['independent_readback'] and result['other_accounts_unchanged']
    assert before == receipt()
    assert [call.args[0][3] for call in owner.transport.call.call_args_list] == ['set', 'read', 'read']
    assert owner.transport.guard.call_count == owner.verified.recheck.call_count == 6
    compile(control.guest_source(), '<account-language-guest>', 'exec')
    with pytest.raises(EvidenceError, match='replay'):
        owner.submit(guest.ROLE, guest.LOCALE, owner.identity)


@pytest.mark.parametrize('fault', ['target', 'locale', 'attempt', 'config', 'lost-owner', 'provenance',
                                  'uncertain', 'reply', 'large'])
def test_refusal_and_uncertain_submission_never_retry(fault):
    owner = controller([{'accepted': True}])
    role, language, identity = guest.ROLE, guest.LOCALE, copy.deepcopy(owner.identity)
    if fault == 'target': role = 'parent'
    if fault == 'locale': language = 'zz_ZZ.UTF-8'
    if fault == 'attempt': identity['run'] = 'foreign'
    if fault == 'config': owner.transport.config['domain_uuid'] = 'foreign'
    if fault == 'lost-owner': owner.transport.guard.side_effect = EvidenceError('lost-owner')
    if fault == 'provenance': owner.verified.recheck.side_effect = EvidenceError('changed-source')
    if fault == 'uncertain': owner.transport.call.side_effect = OSError('unknown effect')
    if fault == 'reply': owner.transport.call.side_effect = [b'{"accepted": false}\n']
    if fault == 'large': owner.transport.call.side_effect = [b'x' * 65537]
    with pytest.raises((EvidenceError, OSError)): owner.submit(role, language, identity)
    count = owner.transport.call.call_count
    if fault in ('uncertain', 'reply', 'large', 'lost-owner', 'provenance', 'config'):
        with pytest.raises(EvidenceError): owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
        assert owner.transport.call.call_count == count
    assert count == (1 if fault in ('uncertain', 'reply', 'large') else 0)


@pytest.mark.parametrize('fault', ['target', 'other-account', 'system', 'observer', 'session',
                                  'product', 'second', 'wrong-identity'])
def test_confirmation_rejects_changed_preservation_or_missing_result(fault):
    before = receipt()
    after = copy.deepcopy(before)
    after['accounts']['1001']['language'] = guest.LOCALE
    if fault == 'target': after['accounts']['1001']['language'] = 'en_US.UTF-8'
    if fault == 'other-account': after['accounts']['900']['language'] = guest.LOCALE
    if fault == 'system': after['system_locale'] = ['LANG=zh_CN.UTF-8']
    if fault == 'observer': after['observer_locale'] = {'LANG': guest.LOCALE}
    if fault == 'session': after['sessions']['7']['LockedHint'] = 'yes'
    if fault == 'product': after['product_free'] = False
    if fault == 'wrong-identity': after['accounts']['1001']['name'] = 'foreign'
    second = copy.deepcopy(after)
    if fault == 'second': second['accounts']['1001']['language'] = 'en_US.UTF-8'
    owner = controller([{'accepted': True}, after, second])
    owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
    with pytest.raises(EvidenceError): owner.confirm(before)
    with pytest.raises(EvidenceError): owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
    assert owner.transport.call.call_count <= 3


@pytest.mark.parametrize('language', ['', 'en', 'zh', 'zh_TW', 'zh_HK', 'zh_cn',
                                      'zh_CN.ISO-8859-1', 'zh_CN:en', 'zh_CN@foreign'])
def test_confirmation_refuses_every_undeclared_language_representation(language):
    before = receipt()
    after = copy.deepcopy(before)
    after['accounts']['1001']['language'] = language
    owner = controller([{'accepted': True}, after, after])
    owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
    with pytest.raises(EvidenceError, match='confirmed-language'):
        owner.confirm(before)
    with pytest.raises(EvidenceError, match='unconfirmed-submission'):
        owner.confirm(before)
    with pytest.raises(EvidenceError, match='replay'):
        owner.submit(guest.ROLE, guest.LOCALE, owner.identity)
    assert [call.args[0][3] for call in owner.transport.call.call_args_list] == ['set', 'read', 'read']


@pytest.mark.parametrize('fault', ['greeter', 'locked', 'nonadmin', 'missing-locale',
                                  'unsupported', 'identity', 'session-change', 'api-error'])
def test_guest_refuses_before_mutation_or_never_retries_uncertain_api(guest_rig, monkeypatch, fault):
    api, current, users = guest_rig
    if fault == 'greeter': current['7'] = props('120', kind='greeter')
    if fault == 'locked': current['7']['LockedHint'] = 'yes'
    if fault == 'nonadmin': monkeypatch.setattr(guest.os, 'getgrouplist', lambda *_: [])
    if fault == 'missing-locale': guest.sessions.call.return_value = 'C\nen_US.utf8\n'
    if fault == 'unsupported': api.supported.side_effect = guest.LanguageError('api-unsupported')
    if fault == 'identity': api.resolve.side_effect = [(guest.ROOT + '/User1001', 'en_US.UTF-8'),
                                                    (guest.ROOT + '/User1002', 'en_US.UTF-8')]
    if fault == 'session-change':
        monkeypatch.setattr(guest.sessions, 'sessions', Mock(side_effect=[current, {'8': props()}]))
    if fault == 'api-error': api.set_language.side_effect = guest.LanguageError('submission-uncertain')
    with pytest.raises((guest.LanguageError, guest.sessions.SessionError)):
        guest.execute('set', guest.ROLE, guest.LOCALE, api)
    assert api.set_language.call_count == int(fault == 'api-error')


def test_guest_valid_api_input_and_invalid_declared_bindings(guest_rig):
    api, _, _ = guest_rig
    assert guest.execute('reject-inputs', guest.ROLE, guest.LOCALE, api) == {
        'wrong_account_refused': True, 'undeclared_locale_refused': True}
    api.set_language.assert_not_called()
    assert guest.execute('set', guest.ROLE, guest.LOCALE, api) == {'accepted': True}
    api.set_language.assert_called_once_with(guest.ROOT + '/User1001', guest.LOCALE)
    assert api.resolve.call_count == 2


def test_greeter_refusal_is_real_authority_check_without_setter(guest_rig):
    api, current, _ = guest_rig
    current['7'] = props('120', kind='greeter')
    assert guest.execute('refuse', guest.ROLE, guest.LOCALE, api) == {'wrong_entry_refused': True}
    api.resolve.assert_not_called()
    api.set_language.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'path', 'uid', 'name', 'language'])
def test_actual_api_resolution_binds_nss_identity_and_language(fault):
    api = object.__new__(guest.AccountsAPI)
    account = SimpleNamespace(pw_uid=1001, pw_name=guest.sessions.ACCOUNTS['standard'])
    path = guest.ROOT + '/User' + ('1002' if fault == 'path' else '1001')
    values = {'Uid': 1002 if fault == 'uid' else 1001,
              'UserName': 'foreign' if fault == 'name' else account.pw_name,
              'Language': None if fault == 'language' else guest.LOCALE}
    api.call = Mock(side_effect=[(path,), (values,)])
    if fault:
        with pytest.raises(guest.LanguageError): api.resolve(account)
    else:
        assert api.resolve(account) == (path, guest.LOCALE)
        assert api.call.call_args_list[-1].args[2] == 'GetAll'


@pytest.mark.parametrize('fault', ['', 'missing', 'duplicate', 'signature', 'property'])
def test_supported_api_preflight_has_no_fallback(fault):
    api = object.__new__(guest.AccountsAPI)
    method = '<method name="SetLanguage"><arg type="s" direction="in"/></method>'
    prop = '<property name="Language" type="s" access="read"/>'
    if fault == 'missing': method = ''
    if fault == 'duplicate': method *= 2
    if fault == 'signature': method = method.replace('type="s"', 'type="i"')
    if fault == 'property': prop = prop.replace('type="s"', 'type="i"')
    api.call = Mock(return_value=(f'<node><interface name="{guest.USER}">{method}{prop}</interface></node>',))
    if fault:
        with pytest.raises(guest.LanguageError): api.supported('path')
    else: api.supported('path')
    api.call.assert_called_once()


@pytest.mark.parametrize('method,code', [('GetAll', 'read-failed'), ('SetLanguage', 'submission-uncertain')])
def test_dbus_failure_is_explicit_bounded_and_never_repeated(method, code):
    api = object.__new__(guest.AccountsAPI)
    api.GLib = SimpleNamespace(Variant=Mock(), VariantType=SimpleNamespace(new=Mock()))
    api.Gio = SimpleNamespace(DBusCallFlags=SimpleNamespace(NONE=0))
    api.bus = Mock(call_sync=Mock(side_effect=RuntimeError('private error')))
    with pytest.raises(guest.LanguageError, match=code):
        api.call('path', guest.USER, method, '(s)', ('value',), '()')
    api.bus.call_sync.assert_called_once()
    assert api.bus.call_sync.call_args.args[-2] == 5000


def test_snapshot_reads_all_nss_accounts_and_never_writes_state(guest_rig, monkeypatch):
    api, current, users = guest_rig
    current['ssh-1'] = props('0', remote='yes', seat='')
    station = SimpleNamespace(pw_uid=900, pw_gid=900, pw_name='station')
    users['station'] = station
    api.resolve.side_effect = lambda user: (guest.ROOT + '/User' + str(user.pw_uid), 'en_US.UTF-8')
    monkeypatch.setattr(guest, 'system_locale', lambda: ['LANG=en_US.UTF-8'])
    monkeypatch.setattr(guest.os.path, 'lexists', lambda _: False)
    monkeypatch.setattr(guest.os, 'environ', {'LANG': 'C.UTF-8'})
    guest.sessions.call.return_value = 'unrelated-package\n'
    first = guest.snapshot(api)
    current['ssh-2'] = current.pop('ssh-1')
    assert guest.snapshot(api) == first
    assert set(first['sessions']) == {'7'}
    assert set(first['accounts']) == {'900', '1000', '1001'}
    assert first['observer_locale'] == {'LANG': 'C.UTF-8'}
    api.set_language.assert_not_called()
    guest.sessions.call.assert_called_with(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\n'])


def test_selector_and_real_recorder_constructor_reuse_owned_cleanup_envelope(monkeypatch):
    entry = Mock(return_value=0)
    monkeypatch.setattr(selector, 'smoke', entry)
    monkeypatch.setattr(selector, 'named_input', lambda: 'verified-input')
    assert selector.main() == 0
    entry.assert_called_once_with(assets='verified-input', provision_credentials=True, desktop_language=True)
    assert DesktopLanguageQualification.__bases__ == (ProductFreeEntryQualification,)
    assert DesktopLanguageQualification.observation_only
    journey = DesktopLanguageQualification.journey(SimpleNamespace(product_free=True, asset_transfer=Mock()), Mock())
    assert journey.plan is qualification.PLAN and journey.plan.worker_mode == 'product_free_entry'
    assert set(journey.actions) == set(journey.plan.stage_actions.values())
    with pytest.raises(CommandError, match='desktop-language-prerequisites'):
        smoke.main(desktop_language=True, chinese_language_assets=True,
                   assets='inputs', provision_credentials=True)


@pytest.mark.parametrize('fault', ['', 'normalized', 'greeter-exit', 'api', 'readback', 'provider', 'storage'])
def test_complete_desktop_action_through_real_recorder_requires_preservation_before_reply(
        tmp_path, monkeypatch, fault):
    before = receipt()
    after = copy.deepcopy(before)
    after['accounts']['1001']['language'] = guest.LOCALE
    if fault == 'normalized': after['accounts']['1001']['language'] = 'zh_CN'
    owner = controller([before, {'wrong_account_refused': True, 'undeclared_locale_refused': True},
                        before, {'accepted': True}, after, after])
    if fault == 'api':
        owner.transport.call.side_effect = [
            (json.dumps(value, sort_keys=True) + '\n').encode() for value in
            (before, {'wrong_account_refused': True, 'undeclared_locale_refused': True}, before)] + [OSError()]
    if fault == 'readback':
        after['accounts']['900']['language'] = guest.LOCALE
        owner = controller([before, {'wrong_account_refused': True, 'undeclared_locale_refused': True},
                            before, {'accepted': True}, after, after])
    native = Mock(return_value={'independent_readback': True})
    monkeypatch.setattr(qualification, 'fixture_actions', lambda **kwargs: {'native-verify': native})
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(),
                              verified=SimpleNamespace(recheck=Mock()))
    journey = qualification.journey(context, Mock())
    journey.account_language, journey.language_entry = owner, copy.deepcopy(before)
    if fault == 'greeter-exit':
        journey.language_entry['accounts']['60578'] = {'name': 'gdm-greeter', 'language': 'en'}
        journey.language_entry['sessions'] = {'c1': props('60578', kind='greeter')}
    journey.steps = [{'stage': name} for name in journey.plan.stages[:journey.plan.stages.index('desktop')]]
    provider = {'locale': 'en_US.UTF-8', 'version': '50.1', 'keyboard': [['xkb', 'us']]}
    changed = {**provider, 'locale': guest.LOCALE} if fault == 'provider' else provider
    journey.ui = SimpleNamespace(boot_proof='a' * 64, observe=Mock(side_effect=[
        {'outcome': 'passed'}, {'provider': provider}, {'provider': provider}, {'provider': changed}]))
    journey.transport = owner.transport
    monkeypatch.setattr(guest.sessions, 'observe', Mock(return_value={'outcome': 'passed'}))
    if fault == 'storage': journey.progress.side_effect = OSError('storage failed')
    (tmp_path / 'desktop.request.json').write_text(json.dumps({'stage': 'desktop', 'screenshot': None}))
    if fault and fault not in ('greeter-exit', 'normalized'):
        with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
        assert not (tmp_path / 'desktop.reply.json').exists()
        with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
    else:
        journey.step(Mock())
        observed = journey.progress.call_args.args[1]
        assert observed['ui']['outcome'] == 'passed' and observed['provider'] == provider
        assert observed['fixture']['confirmed_language'] == after['accounts']['1001']['language']
        assert observed['fixture']['requested_locale'] == guest.LOCALE
        assert json.loads((tmp_path / 'desktop.reply.json').read_text()) == {'observed': 'desktop'}
        native.assert_called_once()
    assert [call.args[0][3] for call in owner.transport.call.call_args_list].count('set') == 1


def test_real_decoder_accepts_bounded_all_account_snapshot():
    value = receipt()
    value['accounts'].update({str(uid): {'name': 'synthetic-account-' + str(uid),
                                        'language': 'en_US.UTF-8'} for uid in range(2000, 2125)})
    assert len(value['accounts']) == 128
    owner = controller([value])
    assert owner.read() == value


@pytest.mark.parametrize('fault', ['', 'persistent', 'unbound', 'remote', 'still-present',
                                  'reused-session', 'new-account', 'language', 'locale'])
def test_entry_only_allows_departed_session_bound_temporary_greeter(fault):
    after = receipt()
    before = copy.deepcopy(after)
    before['accounts']['60578'] = {'name': 'gdm-greeter', 'language': 'en'}
    before['sessions'] = {'c1': props('60578', kind='greeter')}
    if fault == 'persistent': before['accounts']['60578']['name'] = 'unrelated-account'
    if fault == 'unbound': before['sessions']['c1']['User'] = '120'
    if fault == 'remote': before['sessions']['c1']['Remote'] = 'yes'
    if fault == 'still-present': after['sessions']['c1'] = before['sessions']['c1']
    if fault == 'reused-session': after['sessions']['c1'] = props()
    if fault == 'new-account': after['accounts']['2000'] = {'name': 'unrelated-account', 'language': 'en'}
    if fault == 'language': after['accounts']['900']['language'] = guest.LOCALE
    if fault == 'locale': after['observer_locale']['LANG'] = guest.LOCALE
    unchanged = copy.deepcopy(before)
    if fault:
        with pytest.raises(EvidenceError, match='entry-preservation'):
            control.compare_desktop_entry(before, after)
    else:
        control.compare_desktop_entry(before, after)
    assert before == unchanged


@pytest.mark.parametrize('fault', ['', 'wrong-entry', 'desktop'])
def test_actual_shared_worker_order_stops_before_later_input_and_shutdown(fault):
    source = RUN_PROBE.replace('require onpc_desktop_session;', 'require onpc_product_free_entry;')
    source = source.replace('onpc_desktop_session::run', 'onpc_product_free_entry::run')
    source = source.replace('}, $action);', '});')
    source = source.replace("push @events, ['stage', $_[0]];",
        "push @events, ['stage', $_[0]]; die 'fixed refusal' if $_[0] eq $action;")
    result = json.loads(run_perl(source, fault).stdout)
    stages = [event[1] for event in result['events'] if event[0] == 'stage']
    expected = list(qualification.PLAN.screen_tags)
    assert stages == (expected[:expected.index(fault) + 1] if fault else expected)
    assert bool(result['ok']) == (not fault)
    if not fault: assert result['events'][-1] == ['power', 'off']
    else: assert ['power', 'off'] not in result['events']


@pytest.mark.parametrize('fault', ['guard', 'setter', 'readback', 'storage'])
def test_real_recorder_refuses_reply_and_reentry_on_language_failure(tmp_path, monkeypatch, fault):
    context = SimpleNamespace(directory=tmp_path, product_free=True, asset_transfer=Mock(),
                              verified=SimpleNamespace(recheck=Mock()))
    journey = qualification.journey(context, Mock())
    journey.steps = [{'stage': stage} for stage in journey.plan.stages[:2]]
    stage = 'wrong-entry'
    before = receipt()
    owner = controller([before, {'wrong_entry_refused': True}, before])
    if fault == 'guard': owner.transport.guard.side_effect = EvidenceError('lost-owner')
    if fault == 'setter': owner.transport.call.side_effect = OSError('uncertain')
    if fault == 'readback':
        changed = copy.deepcopy(before)
        changed['accounts']['1001']['language'] = guest.LOCALE
        owner = controller([before, {'wrong_entry_refused': True}, changed])
    monkeypatch.setattr(qualification, 'AccountLanguage', lambda *args: owner)
    journey.transport = owner.transport
    journey.ui = SimpleNamespace(observe=Mock(return_value={'outcome': 'passed'}), boot_proof='a' * 64)
    if fault == 'storage': journey.progress.side_effect = OSError('storage failed')
    (tmp_path / (stage + '.request.json')).write_text(json.dumps({'stage': stage, 'screenshot': None}))
    with pytest.raises((EvidenceError, OSError)): journey.step(Mock())
    assert not (tmp_path / (stage + '.reply.json')).exists()
    with pytest.raises(EvidenceError, match='previous-failure'): journey.step(Mock())
