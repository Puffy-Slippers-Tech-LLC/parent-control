"""Exercise real pytest JUnit and export with synthetic authentication outcomes."""

import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/integration'))
from owned_commands import Commands
import system_guest as guest
import system_runner as runner
sys.path.pop(0)


def collect_local(monkeypatch, tmp_path, payload):
    """Exercise real collection while substituting all OS reads."""
    monkeypatch.setattr(guest, 'PAYLOAD', payload)
    monkeypatch.setattr(guest, 'Path', lambda value: (
        tmp_path / 'absent-product-logs' if value == '/var/log/oh-no-parent-control'
        else Path(value)))
    monkeypatch.setattr(guest, 'Commands', lambda: Mock(run=Mock(return_value=b'')))
    import pwd
    monkeypatch.setattr(pwd, 'getpwall', lambda: [SimpleNamespace(
        pw_uid=1001, pw_name='private-user', pw_gecos='Private <Test> & User',
        pw_dir='/home/private-user')])
    guest.collect({'run': 'a' * 32, 'package_sha256': 'b' * 64,
                   'baseline_sha256': 'c' * 64, 'selected_inputs_sha256': 'd' * 64}, 'failed')


def test_junit_redaction_handles_escaped_values_without_breaking_xml(monkeypatch, tmp_path):
    results = tmp_path / 'results'
    results.mkdir()
    root = ET.Element('testsuite', hostname='ubuntu26.04')
    case = ET.SubElement(root, 'testcase', name='test_example')
    failure = ET.SubElement(case, 'failure', message='password=credential<&"')
    failure.text = 'Private <Test> & User /home/private-user password=credential<&"'
    failure.tail = 'private-user token=' + 'a' * 32
    ET.ElementTree(root).write(results / 'authorization.xml', encoding='utf-8')
    collect_local(monkeypatch, tmp_path, tmp_path)
    exported = ET.parse(results / 'authorization.xml').getroot()
    assert exported.get('hostname') == '[Test VM]'
    failure = exported.find('testcase/failure')
    assert failure.get('message') == 'password=<redacted>'
    assert failure.text == '[Test user] [Test user] password=<redacted>'
    assert failure.tail == '[Test user] token=<redacted>'


def test_deleted_identity_is_redacted_from_text_and_junit(monkeypatch, tmp_path):
    import pwd
    account = SimpleNamespace(pw_uid=1234, pw_name='deleted-fixture',
                              pw_gecos='Deleted <Person>', pw_dir='/home/deleted-fixture')
    monkeypatch.setattr(guest, 'PAYLOAD', tmp_path)
    monkeypatch.setattr(guest, 'guard', lambda: {})
    monkeypatch.setattr(pwd, 'getpwuid', lambda uid: account)
    guest.retain_identity_for_redaction(account.pw_uid)
    saved = list((tmp_path / 'private/redaction-identities').glob('*.json'))
    assert len(saved) == 1 and saved[0].stat().st_mode & 0o777 == 0o600
    # The collector runs later in another process, after NSS no longer has it.
    diagnostics = tmp_path / 'private/stage-sample'
    diagnostics.mkdir()
    contents = 'deleted-fixture Deleted <Person> /home/deleted-fixture'
    (diagnostics / 'stderr.txt').write_text(contents)
    results = tmp_path / 'results'
    results.mkdir()
    root = ET.Element('testsuite')
    case = ET.SubElement(root, 'testcase', name='test_deleted_account')
    ET.SubElement(case, 'failure', message=contents).text = contents
    ET.ElementTree(root).write(results / 'authorization.xml', encoding='utf-8')
    collect_local(monkeypatch, tmp_path, tmp_path)
    assert (results / 'stage-sample-stderr.txt').read_text() == '[Test user] ' * 2 + '[Test user]'
    failure = ET.parse(results / 'authorization.xml').find('testcase/failure')
    assert failure.text == failure.get('message') == '[Test user] ' * 2 + '[Test user]'
    assert {path.name for path in results.iterdir()} == {
        'authorization.xml', 'stage-sample-stderr.txt', 'service-journal.txt',
        'authentication-journal.txt', 'result.json',
    }


def test_authentication_attempts_survive_failed_pytest_and_public_export(monkeypatch, tmp_path):
    payload = tmp_path / 'payload'
    results = payload / 'results'
    results.mkdir(parents=True)
    sample = payload / 'test_authorization.py'
    shutil.copyfile(ROOT / 'tests/fixtures/authentication_evidence_sample.py', sample)
    commands = Commands()
    raw = commands.run([
        'env', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD=1', 'PYTHONDONTWRITEBYTECODE=1',
        f'PYTHONPATH={ROOT / "tests/integration"}',
        f'ONPC_AUTHORIZATION_SOURCE={ROOT / "tests/system/test_authorization.py"}',
        '/usr/bin/python3', '-B', '-m', 'pytest',
        '-c', str(ROOT / 'tests/system/pytest.ini'), '--noconftest',
        '--rootdir', str(payload), '--junitxml', str(results / 'authorization.xml'),
        '-q', str(sample),
    ], check=False, timeout=60)
    assert commands.last_returncode == 1  # Deliberate sample failure is preserved.
    assert b'1 failed, 1 passed' in raw
    assert b'fixture-credential-do-not-export' in raw  # The private transport sees it.

    # Use the real guest redaction/collection and host public export. Substitute
    # only OS reads; no host logs, accounts, services, or VM are accessed.
    collect_local(monkeypatch, tmp_path, payload)
    shutil.copytree(results, tmp_path / 'guest-results')
    selection = runner.resolve_selection('authorization', inventories={
        'package': ('test_installed_package', 'test_reboot_applies_installation'),
        'authorization': tuple(f'test_real_selected_parent_authentication[{surface}]'
                               for surface in ('child1', 'kiosk')),
    })
    ledger = runner.RunLedger()
    ledger.fail_outcome('product', 'pytest:failed:authorization')
    ledger.pass_outcome('collection')
    manifest = {'artifacts': {'package': {'sha256': 'b' * 64},
                              'fixtures': {'sha256': 'e' * 64}}, 'source': {}}
    lease = SimpleNamespace(state={'baseline_sha256': 'c' * 64, 'phase': 'complete'})
    assert runner.evidence(tmp_path, manifest, lease, False, 'pytest:failed:authorization',
                           selection, 'd' * 64, ledger) == (False, 'pytest:failed:authorization')

    public = tmp_path / 'evidence'
    xml = ET.parse(public / 'guest/authorization.xml').getroot()
    records = [json.loads(prop.get('value')) for prop in xml.iter('property')
               if prop.get('name') == 'onpc.authentication']
    assert records == [
        {'case_id': f'test_real_selected_parent_authentication[{surface}]',
         'attempt': attempt, 'expected': expected, 'outcome': outcome,
         'helper_category': category}
        for surface, attempt, expected, outcome, category in (
            ('child1', 1, 'denied', 'denied', 'pam-authenticate'),
            ('child1', 2, 'accepted', 'denied', 'authority-response-no-session'),
            ('kiosk', 1, 'denied', 'denied', 'pam-authenticate'),
            ('kiosk', 2, 'accepted', 'accepted', None),
        )
    ]
    cases = list(xml.iter('testcase'))
    assert [case.get('name') for case in cases] == [
        f'test_real_selected_parent_authentication[{surface}]' for surface in ('child1', 'kiosk')]
    assert cases[0].find('failure') is not None
    assert 'agent:unexpected-denied' in cases[0].find('failure').get('message')
    assert cases[1].find('failure') is None
    aggregate = json.loads((public / 'result.json').read_text())
    assert aggregate['category'] == 'pytest:failed:authorization'
    assert aggregate['outcomes']['collection']['outcome'] == 'passed'
    for path in public.rglob('*'):
        if path.is_file():
            contents = path.read_bytes()
            for secret in (b'fixture-credential-do-not-export', b'private-user',
                           b'/home/private-user', b'private@example.invalid'):
                assert secret not in contents, path.relative_to(public)
