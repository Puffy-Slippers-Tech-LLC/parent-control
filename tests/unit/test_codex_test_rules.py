"""Routine commands stay approved; scoped restrictions dominate saved allows."""
import ast
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess

import pytest

from tests.support.paths import ROOT
BASELINE_PATTERN = '^(def|class) |environment|provenance|accepted'
BASELINE_SEARCH = [
    'rg', '-n', BASELINE_PATTERN,
    '--glob', '/tools/*baseline*', '--glob', '/tools/*baseline*/**',
    '--glob', '/tests/integration/baseline*', '--glob', '/tests/integration/baseline*/**',
    '.',
]
SETUP_PATTERN = 'codex_slices|codex-slices|apply_patch|execpolicy|codex-rules'
SETUP_PATHS = [
    'setup.sh', 'docs/TestAutomation/Unattended-Sessions.md',
    'docs/TestAutomation/Unattended-Prompt.md', 'tests/unit/test_codex_slices.py',
]
SETUP_SEARCH = [
    'tools/read-only', 'search', '--path-glob', 'tools/setup*',
    SETUP_PATTERN, *SETUP_PATHS,
]


def entries(name='codex-tests.rules'):
    tree = ast.parse((ROOT / 'config' / name).read_text())
    result = []
    for statement in tree.body:
        assert isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
        assert statement.value.func.id == 'prefix_rule'
        result.append({key.arg: ast.literal_eval(key.value) for key in statement.value.keywords})
    return result


def matches(pattern, argv):
    return len(argv) >= len(pattern) and all(value in token if isinstance(token, list)
                                            else value == token for token, value in zip(pattern, argv))


@pytest.mark.parametrize('entrypoint', [
    'tools/codex_slices.py', './tools/codex_slices.py', '@CHECKOUT@/tools/codex_slices.py',
])
@pytest.mark.parametrize('action', ['--help', '-h', 'status'])
def test_slice_inspection_has_only_allow_matches(entrypoint, action):
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], [entrypoint, action])} == {'allow'}


@pytest.mark.parametrize('command', [
    'python3 tools/codex_slices.py --help', 'python3 -',
    'python3 -c arbitrary', '/usr/bin/python3 tools/codex_slices.py status',
    'tools/codex_slices.py start --max-slices 1', 'tools/codex_slices.py run',
    './tools/codex_slices.py stop', 'tools/codex_slices.py --reconciled start',
])
def test_inspection_allowance_does_not_cancel_interpreter_or_worker_prompts(command):
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], shlex.split(command))} == {'prompt'}


@pytest.mark.parametrize('command', [
    'tools/random.py --help', 'tools/codex_slices.py --max-slices=1 start',
    'tools/codex_slices.py --command arbitrary', 'tools/codex_slices.py',
    'pkexec tools/codex_slices.py status', 'apply_patch arbitrary',
])
def test_inspection_does_not_grant_other_programs_or_unrecognized_argument_forms(command):
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert not any(rule['decision'] == 'allow' and matches(rule['pattern'], shlex.split(command))
                   for rule in rules)


@pytest.mark.parametrize('script', [
    f'rg -n {shlex.quote(SETUP_PATTERN)} setup.sh tools/setup* '
    + shlex.join(SETUP_PATHS[1:]),
    "python3 - <<'PY'\nfrom pathlib import Path\n"
    "p = Path('docs/TestAutomation/Task-19.md')\np.write_text('updated')\nPY",
])
def test_reported_opaque_scripts_keep_shell_prompt(script):
    # Evaluate the unsplit argv from the actual approval report. Do not claim
    # that shlex splitting a script tests Codex's command-tool shell parser.
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], ['/bin/bash', '-lc', script])} == {'prompt'}


def test_reported_setup_search_uses_existing_generic_reader_allowance():
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], SETUP_SEARCH)} == {'allow'}


@pytest.mark.parametrize('unsafe', ['missing', 'not-executable', 'symlink'])
def test_renderer_requires_inspection_launcher_and_preserves_quoted_checkout_paths(tmp_path, unsafe):
    root = tmp_path / 'checkout with "quotes"'
    (root / 'tools').mkdir(parents=True)
    (root / 'config').mkdir()
    (root / 'config/codex-tests.rules').write_bytes((ROOT / 'config/codex-tests.rules').read_bytes())
    for name in ('run-unit-tests', 'run-ui-tests', 'run-tests', 'diagnose', 'test-vm',
                 'cleanup-screenshots', 'read-only'):
        (root / 'tools' / name).touch(mode=0o755)
    launcher = root / 'tools/codex_slices.py'
    if unsafe == 'not-executable':
        launcher.touch(mode=0o644)
    elif unsafe == 'symlink':
        launcher.symlink_to(root / 'tools/read-only')
    installer = runpy.run_path(str(ROOT / 'tools/install_codex_rules.py'))
    with pytest.raises(ValueError, match='missing or nonexecutable launcher'):
        installer['render'](root)
    launcher.unlink(missing_ok=True)
    launcher.touch(mode=0o755)
    rendered = installer['render'](root)
    assert installer['render'](root) == rendered
    rules = []
    for statement in ast.parse(rendered).body:
        rules.append({key.arg: ast.literal_eval(key.value) for key in statement.value.keywords})
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], [str(launcher), '--help'])} == {'allow'}


@pytest.mark.parametrize('command', [
    "tools/run-tests component 'tests/component/test_*.py' -q",
    "tools/run-tests child-node 'tests/child/**/*.test.js'", 'tools/run-tests static',
    'tools/run-tests artifacts build', 'tools/run-tests fast --type contract',
    'tools/run-tests all', 'tools/run-tests e2e --list',
    "tools/read-only search --path-glob 'tests/integration/fixture*' 'password|credential|parent2|child2' tests/fixtures",
    'tools/read-only links docs/TestAutomation/Continuation.md docs/TestAutomation/Task-19.md tests/e2e/README.md',
    "tools/read-only words --after '### Task 19B continuation — 2026-09-08' docs/TestAutomation/Task-19.md",
    "tools/read-only words --after '### Future task' --before '### Next task' docs/future.md",
    "tools/run-ui-tests --timeout 360s 'tests/ui/test_*.py'",
    'tools/diagnose journal --lines 900', 'tools/test-vm reboot',
    'pkexec /usr/local/libexec/onpc-test-runner vm stop',
    'pkexec /usr/local/libexec/onpc-test-runner e2e --list',
    'pkexec /usr/local/libexec/onpc-diagnostics systemctl show sshd.service',
])
def test_validated_routes_only_match_allow_rules(command):
    decisions = [rule['decision'] for rule in entries() if matches(rule['pattern'], shlex.split(command))]
    assert decisions and set(decisions) == {'allow'}


@pytest.mark.parametrize('command', [
    'virsh --connect qemu:///system destroy other-vm',
    'virsh --connect qemu:///system start other-vm',
    '/usr/bin/python3 -B -m pytest /tmp/arbitrary.py',
    '.venv/onpc-ui-tests/bin/python -c arbitrary',
    'make check-system SHELL=/tmp/arbitrary', 'make installdeb', 'make prep-host',
    'journalctl --vacuum-time=1s', 'systemctl restart sshd',
    'pkexec /usr/bin/head /etc/shadow', 'gdbus call --address unix:path=/tmp/bus',
    'rg --pre /tmp/arbitrary needle', 'sort input -o /tmp/output',
    'wget -qO- https://example.com --post-data=example', 'env -u GDK_BACKEND /tmp/arbitrary',
])
def test_legacy_global_allow_cannot_override_project_prompt(command):
    decisions = [rule['decision'] for rule in entries() if matches(rule['pattern'], shlex.split(command))]
    assert 'prompt' in decisions


@pytest.mark.parametrize('url', [
    'https://example.com/path',
    'https://example.com/~project/path?key=value&other=value',
    'https://gitlab.freedesktop.org/pwithnall/malcontent/-/raw/0.14.0/meson.build',
])
def test_saved_curl_public_fetch_allow_is_not_overridden_or_duplicated(url):
    # Model the user's existing global rule without reading personal policy or
    # adding a second maintained allowance. The reported command was already
    # correctly quoted; a project prompt caused the conflict after parsing.
    saved_rule = {'pattern': ['curl', '-fsSL'], 'decision': 'allow'}
    argv = shlex.split(f'curl -fsSL {shlex.quote(url)}')
    maintained_rules = [*entries('codex-read-only.rules'), *entries()]
    assert not any(matches(rule['pattern'], argv) for rule in maintained_rules)
    decisions = {rule['decision'] for rule in [saved_rule, *maintained_rules]
                 if matches(rule['pattern'], argv)}
    assert decisions == {'allow'}


@pytest.mark.parametrize('command', [
    'curl', 'curl -X POST https://example.com',
    'curl --data example https://example.com',
    'curl -T /tmp/input https://example.com',
    'curl -o /tmp/output https://example.com',
    "bash -lc 'curl -fsSL https://example.com'",
    'env curl -fsSL https://example.com',
])
def test_restoring_saved_curl_prefix_does_not_add_other_allowances(command):
    saved_rule = {'pattern': ['curl', '-fsSL'], 'decision': 'allow'}
    rules = [saved_rule, *entries('codex-read-only.rules'), *entries()]
    assert not any(rule['decision'] == 'allow' and matches(rule['pattern'], shlex.split(command))
                   for rule in rules)


def test_saved_curl_prefix_does_not_validate_trailing_arguments():
    # This is a policy-language boundary, never a network request. The direct
    # saved prefix is for trusted public reads; the validated fetch helper is
    # required when arguments are untrusted or must be confined by code.
    saved_rule = {'pattern': ['curl', '-fsSL'], 'decision': 'allow'}
    rules = [saved_rule, *entries('codex-read-only.rules'), *entries()]
    argv = ['curl', '-fsSL', 'https://example.com', '-X', 'POST']
    assert {rule['decision'] for rule in rules if matches(rule['pattern'], argv)} == {'allow'}


@pytest.mark.parametrize('executable', ['make', '/usr/bin/make'])
@pytest.mark.parametrize('target', [
    'build', 'check', 'check-release-version', 'check-unit', 'check-component',
    'check-test-fixtures', 'check-child-node', 'check-child-gjs',
    'check-child-shell', 'check-shell', 'check-gjs', 'check-static',
])
def test_routine_make_targets_are_allowed_without_saved_user_rules(executable, target):
    # Evaluate every maintained rule: any broad prompt recreates the reported
    # failure even when a target-specific allow also matches.
    rules = [*entries('codex-read-only.rules'), *entries()]
    decisions = {rule['decision'] for rule in rules
                 if matches(rule['pattern'], [executable, target])}
    assert decisions == {'allow'}


@pytest.mark.parametrize('command', [
    'make', 'make arbitrary-target', 'make check-other',
    'make -f /tmp/Makefile check', 'make -C /tmp check',
    'make installdeb', 'make uninstalldeb', 'make prep-host', 'make prep-vm',
    'make check-system', 'pkexec make check', 'pkexec /usr/bin/make check',
    "bash -lc 'make check'", "/bin/bash -lc 'make check'",
    "bash -lc 'make check && arbitrary-command'", 'env make check',
])
def test_make_target_grants_do_not_allow_other_commands_or_whole_shells(command):
    # Codex splits simple shell invocations before matching. We must not grant
    # the wrapper itself: unsplit scripts still require independent approval.
    assert not any(rule['decision'] == 'allow' and matches(rule['pattern'], shlex.split(command))
                   for rule in entries())


def test_make_prefix_grant_does_not_claim_to_validate_trailing_arguments():
    # Document the supported rule language's boundary rather than treating
    # match/not_match examples as runtime argument validators.
    command = ['make', 'check', '-f', '/tmp/Makefile']
    decisions = {rule['decision'] for rule in entries() if matches(rule['pattern'], command)}
    assert decisions == {'allow'}


def test_inline_examples_and_no_generic_script_allow():
    for rule in [*entries(), *entries('codex-read-only.rules')]:
        for example in rule.get('match', []):
            assert matches(rule['pattern'], shlex.split(example)), example
        for example in rule.get('not_match', []):
            assert not matches(rule['pattern'], shlex.split(example)), example
        if rule['decision'] == 'allow':
            assert not matches(rule['pattern'], ['tools/random.py'])
            assert not matches(rule['pattern'], ['pkexec', '/usr/bin/python3'])


@pytest.mark.parametrize('command', [
    'pwd', '/bin/pwd -L', '/usr/bin/pwd -P', 'git status --short',
    'git status --porcelain=v2 --untracked-files=all -- arbitrary/file',
    '/usr/bin/git status --short -- another/path',
    "rg -n 'evidence|redact|secret|collector|outcomes|first_failure' tests/integration/graphical_worker.py tests/integration/check_graphical_smoke.py docs/TestAutomation/E2E-Coverage.md tests/README.md",
    "rg -n --glob '*evidence*' 'evidence|redact|secret|collector|outcomes|first_failure' tests/integration",
    "rg -n 'perl|subprocess.run|Test::More' --glob '/tests/unit/test_graphical*' --glob '/tests/unit/test_e2e*' .",
    'rg -n needle /etc /var/log /tmp', '/usr/bin/rg -n pattern arbitrary/repo',
    "sed -n '1,95p' tests/integration/check_graphical_smoke.py",
    "/usr/bin/sed -n '20,80p' /var/log/example.log",
])
def test_machine_reads_are_path_independent_without_project_prompt(command):
    rules = [*entries('codex-read-only.rules'), *entries()]
    decisions = {rule['decision'] for rule in rules if matches(rule['pattern'], shlex.split(command))}
    assert decisions == {'allow'}


@pytest.mark.parametrize('command', [
    'git reset --hard', 'git clean -fd', 'git config --global alias.x arbitrary',
    'git -C /tmp/repo clean -fd', 'bash -c pwd', 'pkexec /usr/bin/git status',
])
def test_machine_reads_do_not_grant_writes_or_generic_wrappers(command):
    assert not any(matches(rule['pattern'], shlex.split(command))
                   for rule in entries('codex-read-only.rules'))


@pytest.mark.parametrize('executable', ['rg', '/usr/bin/rg'])
def test_baseline_search_with_quoted_filters_has_only_allow_matches(executable):
    # Check the argv Codex can extract from a simple literal command. shlex is
    # NOT Codex's shell parser; splitting the original unquoted wildcard search
    # here would falsely suggest that the command tool can approve it.
    argv = [executable, *BASELINE_SEARCH[1:]]
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules if matches(rule['pattern'], argv)} == {'allow'}


@pytest.mark.parametrize('shell', ['bash', '/bin/bash', '/usr/bin/bash'])
def test_opaque_baseline_search_still_matches_shell_prompt(shell):
    # This is the argv from the reported approval request, after Codex declined
    # to split the script containing filename expansion. Do not execute it.
    script = f'rg -n {shlex.quote(BASELINE_PATTERN)} tools/*baseline* tests/integration/baseline*'
    rules = [*entries('codex-read-only.rules'), *entries()]
    assert {rule['decision'] for rule in rules
            if matches(rule['pattern'], [shell, '-lc', script])} == {'prompt'}


def test_baseline_glob_filters_preserve_path_scope(tmp_path):
    rg = shutil.which('rg')
    if rg is None:
        pytest.skip('ripgrep is a development prerequisite; run ./setup.sh --dependencies-only')
    selected = [
        'tools/host_baseline.py', 'tools/baseline data.txt',
        'tools/baseline-dir/child.py', 'tools/baseline-dir/nested/child.py',
        'tests/integration/baseline.py', 'tests/integration/baseline-dir/child.py',
    ]
    excluded = [
        'tools/unrelated.py', 'tools/other/baseline.py',
        'tests/integration/check_baseline.py', 'tests/integration/other/baseline.py',
        'other/baseline.py', 'other/tools/host_baseline.py',
    ]
    for name in [*selected, *excluded]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('no match\naccepted\n')
    result = subprocess.run(
        [rg, *BASELINE_SEARCH[1:]], cwd=tmp_path,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
        text=True, capture_output=True, timeout=10, check=True,
    )
    assert set(result.stdout.splitlines()) == {f'./{name}:2:accepted' for name in selected}
    assert not result.stderr
