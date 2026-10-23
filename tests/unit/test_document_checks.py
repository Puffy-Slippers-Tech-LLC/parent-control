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
        (tmp_path / name).write_text('# Heading\n')
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
# Heading
''')
    assert checks.check_links([source]) == 0
    assert capsys.readouterr().out == 'links: documents=1 checked=7 missing=0\n'


@pytest.mark.parametrize('source, raw, destination, kind', [
    ('[label](guide.md#part).', 'guide.md#part', 'guide.md#part', 'inline'),
    ('![label](<with space.md> "title")', 'with space.md', 'with space.md', 'image'),
    ('[nested [label]](a(b(c)).md)', 'a(b(c)).md', 'a(b(c)).md', 'inline'),
    (r'[label](a\(b\).md)', r'a\(b\).md', 'a(b).md', 'inline'),
    ('[label](name%23part%3F.md#caf%C3%A9)', 'name%23part%3F.md#caf%C3%A9',
     'name%23part%3F.md#caf%C3%A9', 'inline'),
    ('[label](result,.md)', 'result,.md', 'result,.md', 'inline'),
    ('[label](name&amp;.md)', 'name&amp;.md', 'name&.md', 'inline'),
    (r'\![label](guide.md)', 'guide.md', 'guide.md', 'inline'),
    ('[Use][KEY]\n\n[key]: <with space.md#part> "title"\n', 'with space.md#part',
     'with space.md#part', 'reference'),
    ('![Key][]\n\n[key]: image.png\n', 'image.png', 'image.png', 'reference'),
    ('[Key]\n\n[key]: guide.md\n[key]: ignored.md\n', 'guide.md', 'guide.md', 'reference'),
])
def test_shared_reference_syntax_preserves_exact_source_spans(source, raw, destination, kind):
    link, = checks.references(source)
    assert source[link.destination_start:link.destination_end] == raw
    assert source[link.start:link.end].startswith(('![', '['))
    assert link.destination == destination
    assert link.kind == kind
    assert link.line == 1
    with pytest.raises(AttributeError):
        link.destination = 'changed'


def test_reference_lines_and_examples_are_not_reinterpreted_as_prose():
    source = '''before `result.txt` [claim][id]
[id]: first.txt
[unused]: unused.txt
````markdown
[example](missing.md)
```
````
    [indented](missing.md)
<!-- [comment](missing.md) -->
`[code](missing.md)`
[valid](second.txt)
'''
    links = list(checks.references(source))
    assert [(link.destination, link.line) for link in links] == [('first.txt', 1), ('second.txt', 11)]
    prose = checks.evidence_prose(source)
    assert len(prose) == len(source)
    assert prose.count('\n') == source.count('\n')
    assert '`result.txt`' in prose and '`[code](missing.md)`' in prose
    assert 'first.txt' not in prose and 'unused.txt' not in prose and 'claim' not in prose


@pytest.mark.parametrize('source', [
    r'\[escaped](absent.md)', '[unclosed](<absent.md)', '[unbalanced](a(b.md)',
    '[title](absent.md "unfinished)', '[space](unwrapped space.md)', r'[space](bad\ space.md)',
    '[unresolved][id]', '[id]: <unfinished\n', '[not a link] text )(',
    '`[code](absent.md)`', '~~~\n[fence](absent.md)\n~~~',
])
def test_malformed_or_literal_syntax_does_not_invent_links(source):
    assert list(checks.references(source)) == []


def test_local_destination_separates_before_decoding_and_preserves_structured_fragments():
    target = checks.local_destination('name%23part%3F.md?view=1#caf%C3%A9')
    assert (target.path, target.fragment) == ('name#part?.md', 'café')
    assert checks.local_destination('file%2520.txt').path == 'file%20.txt'
    fragment = 'onpc-evidence-v1;record=case%20one;sha256=abc'
    target = checks.local_destination('report.json#' + fragment)
    assert target.fragment == 'onpc-evidence-v1;record=case one;sha256=abc'
    assert checks.local_destination('#same-document').path == ''
    for destination in ('https://[malformed', '//host/file', 'mailto:person@example.com'):
        assert checks.local_destination(destination) is None


def test_heading_and_explicit_anchor_compatibility_and_fixed_fragment_diagnostics(tmp_path, capsys):
    target = tmp_path / 'target.md'
    target.write_text('''# Café & punctuation! (yes)
# Café & punctuation! (yes)
# Café & punctuation! (yes)-1
Setext title
============
# Escaped \\(parentheses\\) and `code`
# [Inline](with(parentheses).md)
# [Reference][key]
[key]: ignored.md
# `<foo>` and <em>HTML</em>
# `_literal_` and _`emphasized`_
<a id="named-anchor"></a><a name='old-anchor'></a>
<a data-id="invented" data-name="also-invented" title=" id='quoted'"></a>
```
# Hidden
<a id="hidden"></a>
```
''')
    assert checks.heading_anchors(checks.read_text(target)) == {
        'café--punctuation-yes', 'café--punctuation-yes-1', 'café--punctuation-yes-1-1',
        'setext-title', 'escaped-parentheses-and-code', 'named-anchor', 'old-anchor',
        'inline', 'reference', 'foo-and-html',
        '_literal_-and-emphasized',
    }
    report = tmp_path / 'report.json'
    report.write_text('{}')
    source = tmp_path / 'source.md'
    source.write_text('''# Same document
[unicode](target.md#caf%C3%A9--punctuation-yes)
[duplicate](target.md#caf%C3%A9--punctuation-yes-1)
[setext](target.md#setext-title)
[named](target.md#named-anchor)
[same](#same-document)
[record](report.json#onpc-evidence-v1;record=private)
[private prose](target.md#private-missing)
''')
    assert checks.check_links([source]) == 1
    assert capsys.readouterr().out == ('links: document=1 line=8 missing local fragment\n'
                                      'links: documents=1 checked=7 missing=1\n')


def test_queue_repair_grammar_stays_narrower_than_shared_markdown_parser():
    source = '''[simple](a.md)
![image](a.md)
[angle](<with space.md>)
[balanced](a(b).md)
[title](a.md "title")
[ref][id]
[id]: a.md
`[code](a.md)`
\\[escaped](a.md)
[pipe](a|b.md)
'''
    assert len(list(checks.references(source))) == 7
    links = list(checks.simple_inline_references(source))
    assert [(link.destination, link.line) for link in links] == [('a.md', 1)]
    # Preserve the former conservative mask even where general Markdown now
    # recognizes a link between escaped backticks or an invalid opening fence.
    for unsupported in (r'\`[claim](old.md)\`', '```invalid`info\n[claim](old.md)\n```',
                        '<!-- ` -->[claim](old.md)`'):
        assert list(checks.references(unsupported))
        assert list(checks.simple_inline_references(unsupported)) == []


def test_parser_limits_bound_direct_input_and_unsupported_destinations(monkeypatch):
    monkeypatch.setattr(checks, 'MAX_BYTES', 32)
    with pytest.raises(ValueError, match='at most 8 MiB'):
        list(checks.references('é' * 17))
    monkeypatch.setattr(checks, 'MAX_BYTES', 8 * 1024 * 1024)
    assert list(checks.references('[long](' + 'a' * (checks.MAX_DESTINATION_CHARS + 1) + ')')) == []
    assert list(checks.references('[deep](' + '(' * (checks.MAX_NESTING + 1) + 'x' +
                                  ')' * (checks.MAX_NESTING + 2))) == []
    assert list(checks.references('[' * (checks.MAX_NESTING + 1) + 'x' +
                                  ']' * (checks.MAX_NESTING + 1) + '(target.md)')) == []
    assert checks.reference_definition_spans('[' + r'\!' * 500 + ']: target.md\n') == ()
    # Many unmatched delimiter sizes previously required repeated suffix scans.
    text = '\n'.join('`' * size for size in range(1, 200))
    assert len(checks.without_code(text)) == len(text)


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


def test_routine_links_skip_disposable_reports_without_reading_them(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'checkout'
    (root / 'docs').mkdir(parents=True)
    source = root / 'docs/guide.md'
    reports = ('[expired](../output/test-runs/expired/report.md#lost-heading)\n'
               '[protected](../output/test-runs/private/report.md#unreadable-heading)\n')
    source.write_text(reports)
    monkeypatch.setattr(checks, 'ROOT', root)
    original_stat, original_read = checks.Path.stat, checks.read_text
    inspected_reports = []

    def outside_reports(path, *args, **kwargs):
        if checks.Path(os.path.abspath(path)).is_relative_to(root / 'output/test-runs'):
            inspected_reports.append(path)
            if 'private' in path.parts:
                raise PermissionError(errno.EACCES, 'private report')
        return original_stat(path, *args, **kwargs)

    def source_only(path):
        assert path == source
        return original_read(path)

    monkeypatch.setattr(checks.Path, 'stat', outside_reports)
    monkeypatch.setattr(checks, 'read_text', source_only)
    monkeypatch.setattr(checks.subprocess, 'run', lambda *_args, **_kwargs:
                        pytest.fail('routine document check invoked a privileged reader'))
    assert checks.check_links([source]) == 0
    assert capsys.readouterr().out == 'links: documents=1 checked=0 missing=0 skipped_reports=2\n'
    source.write_text(reports + '[missing source](absent.md)\n')
    assert checks.check_links([source]) == 1
    assert capsys.readouterr().out == ('links: document=1 line=3 missing local target\n'
                                      'links: documents=1 checked=1 missing=1 skipped_reports=2\n')
    assert inspected_reports == []


def test_explicit_report_document_keeps_target_and_fragment_checks(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'checkout'
    reports = root / 'output/test-runs/report'
    reports.mkdir(parents=True)
    source = reports / 'report.md'
    source.write_text('[missing](absent.md)\n[fragment](target.md#absent)\n')
    (reports / 'target.md').write_text('# Present\n')
    monkeypatch.setattr(checks, 'ROOT', root)
    assert checks.check_links([source]) == 1
    assert capsys.readouterr().out == ('links: document=1 line=1 missing local target\n'
                                      'links: document=1 line=2 missing local fragment\n'
                                      'links: documents=1 checked=2 missing=2\n')


@pytest.mark.parametrize('outcome', ['verified', 'refused', 'malformed', 'timeout', 'unavailable'])
def test_explicit_protected_link_inspection_uses_only_the_guarded_metadata_reader(
        tmp_path, monkeypatch, outcome):
    from evidence_policy import Condition
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
    text = source.read_text()
    link = next(checks.references(text))
    assert checks.link_condition(source, text, link) == (None if outcome == 'verified' else Condition.DENIED)
    assert len(calls) == 1


def test_parent_steps_through_symlinks_cannot_verify_an_unrelated_artifact(
        tmp_path, monkeypatch):
    from evidence_policy import Condition
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
    text = source.read_text()
    assert checks.link_condition(source, text, next(checks.references(text))) == Condition.DENIED


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
