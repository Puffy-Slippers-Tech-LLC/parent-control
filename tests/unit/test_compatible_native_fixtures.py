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
