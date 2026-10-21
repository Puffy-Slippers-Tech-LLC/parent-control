"""Real native payload/renderer applicability; no installed enforcement claim.

Only pytest-private disk files and synchronous, waited compiler children are
used. No display, bus, VM, policy activation or shared mutable cache is owned.
"""
import hashlib
import pytest

from oh_no_parent_control.execution_policy import ExecutionPolicyError, FapolicydPolicy
from tests.fixtures import build_test_applications as builder
from tests.fixtures import native_assets as assets


@pytest.fixture(scope='module')
def payload(tmp_path_factory):
    root = tmp_path_factory.mktemp('compatible-native')
    native = builder._compile_native(root)
    builder._build_native_layout(root, native)
    return root


def target(root, role):
    return root / ('image-root' + assets.executable_path(role))


@pytest.mark.parametrize('early', [False, True])
@pytest.mark.parametrize('soft_blocked', [True, False])
def test_complete_payload_preserves_allowed_hard_and_versioned_intent(payload, early, soft_blocked):
    """Render actual compiled files, including every legacy whitespace nonmatch."""
    allowed, hard, soft = (target(payload, role) for role in ('A', 'H', 'S'))
    assert ' ' in allowed.name and ' ' in hard.name
    assert soft.parent != allowed.parent == hard.parent
    assert len({path.read_bytes() for path in (allowed, hard, soft)}) == 3
    # Neither hiding A nor replacing the wildcard with a precise S rule is valid.
    pattern = str(payload / ('image-root' + assets.version_pattern()))
    assert pattern == str(soft.with_name('Lunar Client-*.AppImage'))
    issues = []
    blocked = (str(hard), str(soft)) if soft_blocked else (str(hard),)
    layers = FapolicydPolicy._render_layers(
        {1001: blocked}, {1001: (pattern,)} if soft_blocked else {},
        issues=issues, early_pattern_guards=early)
    assert issues == []
    for rules in layers:
        assert 'allow perm=execute uid=1001 : sha256hash=' not in rules
        assert 'allow perm=open uid=1001 : sha256hash=' not in rules
        assert hashlib.sha256(allowed.read_bytes()).hexdigest() not in rules
        assert f'deny_syslog perm=execute uid=1001 : dir={allowed.parent}/\n' not in rules
        for permission in ('execute', 'open'):
            assert (f'deny_syslog perm={permission} uid=1001 : sha256hash='
                    + hashlib.sha256(hard.read_bytes()).hexdigest()) in rules
    guarded = layers[0] if early else layers[1]
    for permission in ('execute', 'open'):
        assert (f'deny_syslog perm={permission} uid=1001 : dir={soft.parent}/'
                in guarded) is soft_blocked
    if not soft_blocked:
        assert hashlib.sha256(soft.read_bytes()).hexdigest() not in ''.join(layers)


def test_legacy_shared_directory_is_still_refused_without_hash_allowances(payload):
    """The old layout must retain its deliberate warning and whole-group omission."""
    hard = target(payload, 'H')
    legacy = target(payload, 'A').with_name('Lunar Client-3.7.17.AppImage')
    assert legacy.read_bytes() == target(payload, 'S').read_bytes()
    pattern = str(legacy.with_name('Lunar Client-*.AppImage'))
    filters, patterns = {1001: (str(hard), str(legacy))}, {1001: (pattern,)}
    with pytest.raises(ExecutionPolicyError, match='nonmatching executable'):
        FapolicydPolicy.render(filters, patterns)
    issues = []
    rules = FapolicydPolicy.render(filters, patterns, issues=issues)
    assert issues == [(1001, 'pattern', pattern)]
    assert 'dir=' not in rules
    assert 'allow ' not in rules
    assert hashlib.sha256(hard.read_bytes()).hexdigest() in rules
    assert hashlib.sha256(legacy.read_bytes()).hexdigest() in rules


def source_hashes(root):
    return {source: hashlib.sha256((root / source.removeprefix('fixtures/')).read_bytes()).hexdigest()
            for source in assets.runtime_sources()}


@pytest.mark.parametrize('fault', ['source-key', 'digest', 'duplicate-native', 'runtime-copy',
    'duplicate-runtime', 'runtime-native', 'uid-root', 'uid-duplicate', 'uid-bool', 'uid-text'])
def test_baseline_admission_renderer_is_closed(payload, fault):
    expected = source_hashes(payload)
    uids = (1000, 1001)
    if fault == 'source-key': expected['foreign'] = 'a' * 64
    if fault == 'digest': expected[assets.executable_sources()[0]] = 'G' * 64
    if fault == 'duplicate-native': expected[assets.executable_sources()[0]] = expected[assets.executable_sources()[1]]
    if fault == 'runtime-copy': expected[assets.gui_sources()[2]] = 'a' * 64
    if fault == 'duplicate-runtime':
        for source in assets.gui_sources(): expected[source] = 'a' * 64
    if fault == 'runtime-native':
        for source in (assets.gui_sources()[0], assets.gui_sources()[2]):
            expected[source] = expected[assets.executable_sources()[0]]
    if fault == 'uid-root': uids = (0, 1001)
    if fault == 'uid-duplicate': uids = (1000, 1000)
    if fault == 'uid-bool': uids = (True, 1001)
    if fault == 'uid-text': uids = ('1000,0', 1001)
    with pytest.raises(ValueError, match='native:baseline-policy-inputs'):
        assets.native_policy_files(expected, uids)


@pytest.mark.parametrize('soft_blocked', [False, True])
def test_stock_first_match_keeps_product_hard_and_wildcard_denials_before_admission(payload, soft_blocked):
    expected = source_hashes(payload)
    admissions = assets.native_policy_files(expected, (1002, 1001))
    hard, soft = target(payload, 'H'), target(payload, 'S')
    early, late = FapolicydPolicy._render_layers(
        {1001: (str(hard),)}, {1001: (str(soft.with_name('Lunar Client-*.AppImage')),)}
        if soft_blocked else {})
    rules = {'01-oh-no-parent-control-deny.rules': early,
        '42-trusted-elf.rules': 'allow perm=execute all : trust=1\n',
        '70-trusted-lang.rules': 'deny_audit perm=open all : ftype=text/x-python trust=0\n',
        '89-oh-no-parent-control.rules': late,
        '90-deny-execute.rules': 'deny_audit perm=execute all : all\n'}
    rules.update({path.rsplit('/', 1)[-1]: data.decode() for path, data in admissions.items()})
    names = sorted(rules)
    assert names.index('01-oh-no-parent-control-deny.rules') < names.index('69-onpc-baseline-runtime.rules')
    assert names.index('69-onpc-baseline-runtime.rules') < names.index('70-trusted-lang.rules')
    assert names.index('89-oh-no-parent-control.rules') < names.index('89-onpc-baseline-fixtures.rules') < names.index('90-deny-execute.rules')
    def decision(path, permission, *, uid=1001, trusted=False):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in names:
            for line in rules[name].splitlines():
                if line.startswith('#') or not line:
                    continue
                subject, obj = line.split(' : ')
                if f'perm={permission}' not in subject:
                    continue
                uids = next((part[4:].split(',') for part in subject.split() if part.startswith('uid=')), None)
                if uids is not None and str(uid) not in uids:
                    continue
                clauses = obj.split()
                if any(part == 'trust=1' and not trusted or part == 'trust=0' and trusted
                       or part.startswith('sha256hash=') and part[11:] != digest
                       or part.startswith('dir=') and not str(path).startswith(part[4:])
                       or part.startswith('path=') and str(path) != part[5:]
                       or part.startswith('ftype=') and path.suffix != '.py' for part in clauses):
                    continue
                return subject.split()[0], name
        return None
    assert decision(target(payload, 'A'), 'execute') == ('allow', '89-onpc-baseline-fixtures.rules')
    assert decision(hard, 'execute')[0] == 'deny_syslog'
    assert decision(soft, 'execute')[0] == ('deny_syslog' if soft_blocked else 'allow')
    gui = payload / ('image-root' + assets.PREFIX + '/onpc-test-gui.py')
    assert decision(gui, 'open') == ('allow', '69-onpc-baseline-runtime.rules')
    assert decision(target(payload, 'A'), 'execute', uid=1003)[0] == 'deny_audit'
    for data in admissions.values():
        assert b'uid=1001,1002 :' in data and b'trust=0\n' in data
        assert b'dir=' not in data and b'path=' not in data and b'perm=any' not in data
