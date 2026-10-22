"""Read-only handoff checks have bounded inputs and never evaluate source text."""
from tests.support.modules import load_module
import errno
import os
import subprocess
from types import SimpleNamespace

import pytest


from tests.support.paths import ROOT
checks = load_module('onpc_test_document_checks', ROOT / 'tools/document_checks.py')


def test_local_inline_links_handle_destinations_and_ignore_code_and_urls(tmp_path, capsys):
    for name in ('ordinary.md', 'with space.md', 'with(parentheses).md', 'image.png'):
        (tmp_path / name).touch()
    source = tmp_path / 'source.md'
    source.write_text('''[simple](ordinary.md#heading)
[encoded](with%20space.md?view=1#heading)
[angle](<with space.md> "optional title")
[balanced](with(parentheses).md)
[escaped](with\\(parentheses\\).md 'title')
![image](image.png)
[external](https://example.com/missing)
[malformed external](https://[bad-host)
[external](//example.com/missing)
[mail](mailto:example@example.com)
[anchor](#heading)
`[example](missing.md)` and ``[example](other-missing.md)``
```md
[fenced](missing.md)
```
~~~
[fenced](missing.md)
~~~
[reference][not-an-inline-link]
''')
    assert checks.check_links([source]) == 0
    assert capsys.readouterr().out == 'links: documents=1 checked=6 missing=0\n'


def test_missing_targets_report_document_number_and_line_without_input_values(tmp_path, capsys):
    first = tmp_path / 'sensitive-document.md'
    second = tmp_path / 'another-document.md'
    first.write_text('intro\n[private prose](private-target.md)\n')
    second.write_text('[also private](other-target.md)\n')
    assert checks.check_links([first, second]) == 1
    output = capsys.readouterr().out
    assert output == ('links: document=1 line=2 missing local target\n'
                      'links: document=2 line=1 missing local target\n'
                      'links: documents=2 checked=2 missing=2\n')


def test_inaccessible_targets_are_read_failures_not_missing_or_success(tmp_path, monkeypatch, capsys):
    source = tmp_path / 'sensitive-document.md'
    target = tmp_path / 'private-target.json'
    target.touch()
    source.write_text('[private prose](private-target.json)\n[missing](absent.md)\n'
                      '[present](sensitive-document.md)\n')
    monkeypatch.setattr(checks, 'ROOT', tmp_path)
    original = type(target).stat

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError(errno.EACCES, 'private access details', str(target))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(type(target), 'stat', denied)
    monkeypatch.setattr(checks.os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(checks.subprocess, 'run', lambda *args, **kwargs:
                        pytest.fail('non-evidence paths must not reach the artifact reader'))
    assert checks.main(['links', str(source)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ('links: document=1 line=1 inaccessible local target\n'
                            'links: document=1 line=2 missing local target\n'
                            'links: documents=1 checked=3 missing=1 inaccessible=1\n')
    assert not captured.err


@pytest.mark.parametrize('outcome', ['verified', 'refused', 'malformed', 'timeout', 'unavailable'])
def test_protected_evidence_links_use_only_the_guarded_metadata_reader(
        tmp_path, monkeypatch, capsys, outcome):
    root = tmp_path / 'checkout'
    (root / 'docs').mkdir(parents=True)
    source = root / 'docs/guide.md'
    source.write_text('[private prose](../output/test-runs/private-result.json)\n')
    target = root / 'output/test-runs/private-result.json'
    original = type(target).stat
    calls = []

    def denied(path, *args, **kwargs):
        if checks.Path(os.path.abspath(path)) == target:
            raise PermissionError(errno.EACCES, 'private access details', str(target))
        return original(path, *args, **kwargs)

    def metadata_reader(argv, **kwargs):
        calls.append(argv)
        assert argv == ['/usr/bin/pkexec', '--keep-cwd',
                        '/usr/local/libexec/onpc-test-artifacts', 'stat', str(target)]
        assert kwargs == dict(cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, check=False, timeout=15)
        if outcome == 'timeout':
            raise subprocess.TimeoutExpired(argv, 15)
        if outcome == 'unavailable':
            raise FileNotFoundError('private helper details')
        return SimpleNamespace(returncode=2 if outcome == 'refused' else 0,
                               stdout='{"kind":"file"}' if outcome != 'malformed' else 'true')

    monkeypatch.setattr(checks, 'ROOT', root)
    monkeypatch.setattr(type(target), 'stat', denied)
    monkeypatch.setattr(checks.subprocess, 'run', metadata_reader)
    assert checks.check_links([source]) == (0 if outcome == 'verified' else 2)
    assert len(calls) == 1
    captured = capsys.readouterr()
    expected = 'links: documents=1 checked=1 missing=0\n' if outcome == 'verified' else (
        'links: document=1 line=1 inaccessible local target\n'
        'links: documents=1 checked=1 missing=0 inaccessible=1\n')
    assert captured.out == expected
    assert not captured.err


def test_parent_steps_through_symlinks_cannot_verify_an_unrelated_artifact(
        tmp_path, monkeypatch, capsys):
    root = tmp_path / 'checkout'
    evidence = root / 'output/test-runs'
    evidence.mkdir(parents=True)
    (evidence / 'result.json').touch()
    private = tmp_path / 'elsewhere/private'
    private.mkdir(parents=True)
    (evidence / 'jump').symlink_to(private, target_is_directory=True)
    source = root / 'guide.md'
    source.write_text('[private prose](output/test-runs/jump/../result.json)\n')
    target = evidence / 'jump/../result.json'
    original = type(target).stat

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError(errno.EACCES, 'private access details', str(target))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(checks, 'ROOT', root)
    monkeypatch.setattr(type(target), 'stat', denied)
    monkeypatch.setattr(checks.subprocess, 'run', lambda *args, **kwargs:
                        pytest.fail('a different normalized target must not reach the reader'))
    assert checks.check_links([source]) == 2
    assert capsys.readouterr().out == (
        'links: document=1 line=1 inaccessible local target\n'
        'links: documents=1 checked=1 missing=0 inaccessible=1\n')


def test_link_existence_is_relative_to_each_document(tmp_path, capsys):
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs/target.md').touch()
    nested = tmp_path / 'docs/readme.md'
    nested.write_text('[target](target.md)')
    outer = tmp_path / 'readme.md'
    outer.write_text('[target](target.md)')
    assert checks.check_links([nested, outer]) == 1
    assert 'document=2 line=1' in capsys.readouterr().out


def test_word_count_matches_source_split_and_exact_handoff_selection(tmp_path):
    path = tmp_path / 'guide.md'
    marker = '### Current section'
    source = 'prior handoff\n' + marker + '\n**Solid progress:** first result.\n### Next\nend\n'
    path.write_text(source)
    assert checks.count_words(path) == len(source.split())
    assert checks.count_words(path, after=marker) == len(source.split(marker)[1].split())
    assert checks.count_words(path, after=marker, before='### Next') == 4
    assert checks.count_words(path, before=marker) == 2


@pytest.mark.parametrize('source, options', [
    ('heading appears twice heading', {'after': 'heading'}),
    ('ordinary text', {'after': 'absent'}), ('ordinary text', {'before': 'absent'}),
    ('ordinary text', {'after': ''}), ('end before start', {'after': 'start', 'before': 'end'}),
])
def test_missing_or_ambiguous_markers_fail_instead_of_counting_other_text(tmp_path, source, options):
    path = tmp_path / 'source.md'
    path.write_text(source)
    with pytest.raises(ValueError, match='marker must occur exactly once'):
        checks.count_words(path, **options)


@pytest.mark.parametrize('kind', ['symlink', 'fifo', 'directory', 'large', 'binary'])
def test_non_document_sources_are_refused(tmp_path, monkeypatch, kind):
    path = tmp_path / 'source.md'
    if kind == 'symlink':
        target = tmp_path / 'real.md'
        target.write_text('text')
        path.symlink_to(target)
    elif kind == 'fifo':
        os.mkfifo(path)
    elif kind == 'directory':
        path.mkdir()
    elif kind == 'large':
        monkeypatch.setattr(checks, 'MAX_BYTES', 8)
        path.write_text('too large')
    else:
        path.write_bytes(b'\xff')
    with pytest.raises((ValueError, OSError)):
        checks.read_text(path)


def test_read_failure_does_not_echo_paths_or_markers(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(checks.os, 'geteuid', lambda: 1000)
    assert checks.main(['words', '--after', 'private-marker', str(tmp_path / 'private-name')]) == 2
    captured = capsys.readouterr()
    assert 'document read or metadata check failed' in captured.err
    assert 'private-' not in captured.err
    assert not captured.out


def test_document_commands_use_existing_executable_reader_without_shell_or_input_execution(tmp_path):
    path = tmp_path / '$(touch sentinel).md'
    target = tmp_path / '$(touch another).txt'
    target.touch()
    marker = '### $(touch sentinel)'
    path.write_text(marker + '\n[link](<$(touch another).txt>)\nend\n')
    before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}
    reader = ROOT / 'tools/read-only'
    for args, expected in (
        (['links', str(path)], 'links: documents=1 checked=1 missing=0\n'),
        (['words', '--after', marker, str(path)], 'words: 3\n'),
    ):
        result = subprocess.run([str(reader), *args], cwd=tmp_path,
                                input="raise RuntimeError('stdin-code')\n", capture_output=True,
                                text=True, check=True, timeout=10)
        assert result.stdout == expected
        assert not result.stderr
    assert {item.name: item.read_bytes() for item in tmp_path.iterdir()} == before
