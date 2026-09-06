"""Preserve site policy and reject ambiguous edits before kernel activation."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('graphical_policy', ROOT / 'tools/install_graphical_test_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def test_managed_policy_preserves_site_rules_and_is_idempotent():
    site = '# unrelated site policy\n/specific/path r,\n'
    added = policy.updated_local(site, 'first-rule,')
    assert added.startswith(site)
    assert policy.updated_local(added, 'first-rule,') == added
    replaced = policy.updated_local(added + '# suffix\n', 'new-rule,')
    assert replaced.startswith(site) and replaced.endswith('# suffix\n')
    assert 'first-rule' not in replaced and replaced.count('new-rule') == 1


@pytest.mark.parametrize('bad', [policy.BEGIN, policy.END, policy.BEGIN * 2 + policy.END,
                                policy.END + policy.BEGIN])
def test_ambiguous_block_is_refused(bad):
    with pytest.raises(ValueError):
        policy.updated_local(bad, 'rule,')


def test_compile_failure_leaves_system_file_untouched(tmp_path):
    local, profile = tmp_path / 'local', tmp_path / 'profile'
    local.write_text('# site rules\n')
    profile.write_text('profile libvirtd {\n' + policy.INCLUDE + '\n}\n')
    with patch.object(policy, 'LOCAL', local), patch.object(policy, 'PROFILE', profile), \
            patch.object(policy, 'trusted_file', side_effect=lambda p: p.read_text()), \
            patch.object(policy.subprocess, 'run', side_effect=RuntimeError('syntax failure')) as run:
        with pytest.raises(RuntimeError, match='syntax failure'):
            policy.install()
    assert local.read_text() == '# site rules\n'
    assert '--skip-kernel-load' in run.call_args.args[0]
    assert run.call_count == 1
