"""Latest-only source synchronization and read-only translation transport.

Private pytest PO/TOML/output trees and bounded waited gettext children only;
Codex, workflow ownership and model discovery use process-local doubles.
"""

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.support.paths import ROOT
from tools import whats_new_catalogs as catalogs
from tools import sync_whatsnew as sync
from common.oh_no_parent_control_ui.whats_new import (
    load_whats_new_translations, release_domain, translate_content,
)


def source(root, records):
    content, history = 'version = 1\n', ''
    for version, audience, markdown in records:
        if 'Child' in audience:
            content += ('\n[[records]]\nProductVersion = ' + json.dumps(version) +
                        '\nContent = ' + json.dumps(markdown, ensure_ascii=False) + '\n')
        if 'Parent' in audience:
            history += '## v' + version + ' -\n' + markdown + ('' if markdown.endswith('\n') else '\n')
    if content == 'version = 1\n':
        content += 'records = []\n'
    (root / 'data/whats-new-child.toml').write_text(content, encoding='utf-8')
    (root / 'docs').mkdir(exist_ok=True)
    (root / 'docs/VersionHistory.md').write_text(history, encoding='utf-8')


@pytest.fixture
def repository(tmp_path):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'po').mkdir()
    common = tmp_path / 'common/oh_no_parent_control_ui'
    common.mkdir(parents=True)
    (common / 'languages.json').write_text(json.dumps([
        {'id': language, 'name': language, 'english_name': language} for language in ('en', 'fr', 'de')]))
    for locale in ('fr', 'de'):
        shutil.copyfile(ROOT / 'po' / (locale + '.po'), tmp_path / 'po' / (locale + '.po'))
    source(tmp_path, [('1.9', 'Parent', 'Old notes'),
                      ('1.10', 'Parent, Child', '## New features\n\n- **Search:** Find a language.\n')])
    return tmp_path


def response(work):
    return dict(status='translated', summary='Translated and reviewed', translations=[
        dict(language=language, records=[dict(record_id=record['record_id'],
             content=record['Content'].replace('New features', 'Nouveautés').replace(
                 'Find a language.', 'Trouvez une langue.')) for record in records])
        for language, records in work.items()])


def originals(root, release, work):
    return {language: catalogs.fingerprint(catalogs.catalog_path(root, release, language))
            for language in work}


def finish(root):
    release = catalogs.prepare(root)
    work = catalogs.pending(root, release)
    sync.apply_response(root, release, work, response(work), originals(root, release, work))
    return release


def test_numeric_latest_includes_all_audiences_ignores_installed_version_and_preserves_history(repository):
    source(repository, [('1.10.0', 'Parent', 'Parent notes'), ('1.9', 'Parent,Child', 'Old notes'),
                        ('1.10', 'Child', 'Child notes')])
    (repository / 'data/app.json').write_text('{"version":"1.9"}')
    history = repository / 'po/whats-new/1.9/fr.po'
    history.parent.mkdir(parents=True)
    history.write_text('Historical translation left exactly intact')
    release = catalogs.prepare(repository)
    assert release.version == '1.10'
    assert {record['record_id'] for record in release.records} == {'1.10:Parent', '1.10:Child'}
    assert all('ShowIn' not in record for record in release.records)
    assert history.read_text() == 'Historical translation left exactly intact'
    assert all(record['ProductVersion'] == '1.10' for rows in catalogs.pending(repository).values() for record in rows)


def test_prepare_is_idempotent_and_unchanged_translations_are_preserved(repository):
    english = (repository / 'data/whats-new-child.toml').read_bytes()
    parent_english = (repository / 'docs/VersionHistory.md').read_bytes()
    ui = (repository / 'po/fr.po').read_bytes()
    release = finish(repository)
    paths = list((repository / 'po/whats-new/1.10').iterdir())
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
    catalogs.prepare(repository)
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths} == before
    assert catalogs.pending(repository) == {}
    assert catalogs.check(repository) == release
    assert (repository / 'data/whats-new-child.toml').read_bytes() == english
    assert (repository / 'docs/VersionHistory.md').read_bytes() == parent_english
    assert (repository / 'po/fr.po').read_bytes() == ui


def test_edited_source_requires_review_again_but_retains_previous_translation(repository, tmp_path):
    release = finish(repository)
    source(repository, [('1.9', 'Parent', 'Older English changed; do not translate it'),
                        ('1.10', 'Parent,Child', '## New features\n\n- **Search:** Find a language faster.\n')])
    release = catalogs.prepare(repository)
    work = catalogs.pending(repository, release)
    assert set(work) == {'fr', 'de'}
    assert all(rows[0]['reason'] == 'unreviewed' for rows in work.values())
    assert all('Trouvez une langue.' in rows[0]['previous_translation'] for rows in work.values())
    assert all('Find a language.\n' in rows[0]['previous_source'] for rows in work.values())
    catalogs.prepare(repository)  # Review flags must survive another preparation.
    assert catalogs.pending(repository, release) == work
    with pytest.raises(ValueError, match='pending translations'):
        catalogs.check(repository)
    catalogs.compile_catalogs(repository, tmp_path / 'locale')
    context = load_whats_new_translations('1.10', 'fr', localedir=tmp_path / 'locale')
    assert translate_content(release.records[0], context) == release.records[0]['Content']


def test_new_and_removed_latest_records_do_not_affect_completed_audience(repository):
    source(repository, [('1.10', 'Parent', 'Parent notes')])
    finish(repository)
    source(repository, [('1.10', 'Parent', 'Parent notes'), ('1.10', 'Child', 'Child notes')])
    release = catalogs.prepare(repository)
    assert all([r['record_id'] for r in rows] == ['1.10:Child'] for rows in catalogs.pending(repository).values())
    source(repository, [('1.10', 'Parent', 'Parent notes')])
    catalogs.prepare(repository)
    assert not catalogs.pending(repository)
    assert all(entry.get('msgctxt') != 'whats-new:1.10:Child' for entry in catalogs.read_catalog(
        catalogs.catalog_path(repository, release, 'fr')))


def test_latest_parent_release_needs_no_child_entry_and_ignores_other_child_versions(repository):
    source(repository, [('1.10', 'Parent', 'Current parent notes\n'),
                        ('1.9', 'Child', 'Old child notes'), ('2.0', 'Child', 'Future child notes')])
    release = finish(repository)
    assert release.version == '1.10'
    assert [record['record_id'] for record in release.records] == ['1.10:Parent']
    assert catalogs.check(repository) == release
    source(repository, [('1.10', 'Parent', 'Current parent notes\n')])
    assert not catalogs.pending(repository)


@pytest.mark.parametrize('mutate', [
    lambda value: value['translations'].pop(),
    lambda value: value['translations'][0].update(language='../old'),
    lambda value: value['translations'][0]['records'][0].update(record_id='1.9:Parent'),
    lambda value: value['translations'][0]['records'][0].update(content='Translation without structure'),
    lambda value: value.update(status='blocked'),
])
def test_bad_agent_output_refuses_before_any_catalogue_write(repository, mutate):
    release = catalogs.prepare(repository)
    work = catalogs.pending(repository)
    before = originals(repository, release, work)
    result = response(work)
    mutate(result)
    with pytest.raises(ValueError):
        sync.apply_response(repository, release, work, result, before)
    assert originals(repository, release, work) == before


@pytest.mark.parametrize('operand,replacement', [
    ('https://example.com/releases/1.10', 'https://elsewhere.invalid'),
    ('`example --flag`', '`changed`'), ('%(name)s', '%(other)s'),
    ('Oh No! Parent Control', 'Translated Brand'), ('v1.10', 'v1.11'),
    ('## ', '# '), ('**bold**', 'bold'),
])
def test_protected_markdown_operands_and_structure(operand, replacement):
    source_text = '## Release v1.10\n\n- **bold** Oh No! Parent Control %(name)s `example --flag` https://example.com/releases/1.10\n'
    with pytest.raises(ValueError, match='structure or protected literals'):
        catalogs.validate_content(source_text, source_text.replace(operand, replacement))


def test_concurrent_source_or_translation_edit_is_preserved(repository):
    release = catalogs.prepare(repository)
    work = catalogs.pending(repository)
    before = originals(repository, release, work)
    path = catalogs.catalog_path(repository, release, 'fr')
    path.write_text(path.read_text() + '\n# Developer work\n')
    edited = path.read_bytes()
    with pytest.raises(ValueError, match='changed during translation'):
        sync.apply_response(repository, release, work, response(work), before)
    assert path.read_bytes() == edited
    before = originals(repository, release, work)
    source(repository, [('1.11', 'Parent', 'New release created while translating')])
    with pytest.raises(ValueError, match='source or supported languages changed'):
        sync.apply_response(repository, release, work, response(work), before)
    assert originals(repository, release, work) == before


def test_compiled_catalogues_use_personal_language_and_exact_english_source(repository, tmp_path):
    release = finish(repository)
    catalogs.compile_catalogs(repository, tmp_path / 'locale')
    translated = load_whats_new_translations('1.10', '', ['fr_CA.UTF-8'], localedir=tmp_path / 'locale')
    assert 'Nouveautés' in translate_content(release.records[0], translated)
    assert 'Find a language.' in translate_content(release.records[0], load_whats_new_translations(
        '1.10', 'unsupported', ['fr'], localedir=tmp_path / 'locale'))
    edited = dict(release.records[0], Content=release.records[0]['Content'] + '\nNew text')
    assert translate_content(edited, translated) == edited['Content']
    assert (tmp_path / 'locale/fr/LC_MESSAGES' / (release_domain('1.10.0') + '.mo')).exists()
    with pytest.raises(ValueError):
        release_domain('../../fr')


def test_symlink_catalogues_are_refused(repository, tmp_path):
    target = tmp_path / 'unrelated'
    target.write_text('Preserve me')
    release = catalogs.latest(repository)
    path = catalogs.catalog_path(repository, release, 'fr')
    path.parent.mkdir(parents=True)
    path.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        catalogs.prepare(repository)
    assert target.read_text() == 'Preserve me'


def test_transport_is_read_only_and_helpers_are_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(sync.launcher.shutil, 'which', lambda _name: '/installed/codex')
    command = sync.agent_command(ROOT, tmp_path, 'gpt-6.1-sol', 'high', 2)
    assert command.count('--sandbox') == 1
    assert command[command.index('--sandbox') + 1] == 'read-only'
    assert '--ephemeral' in command and '--json' in command
    assert command[command.index('--ask-for-approval') + 1] == 'never'
    assert 'agents.max_depth=1' in command
    assert 'agents.max_concurrent_threads_per_session=2' in command
    assert 'features.fast_mode=false' in command
    config = sync.TRANSLATOR.read_text()
    assert 'sandbox_mode = "read-only"' in config
    assert 'enabled = false' in config


def test_ephemeral_helpers_receive_self_contained_translation_and_review_tasks(repository):
    release = catalogs.prepare(repository)
    work = catalogs.pending(repository, release)
    instructions, manifest = sync.prompt(release, work, 2).split('\n\n', 1)
    assert 'On every spawn_agent call, explicitly set fork_turns="none"' in instructions
    assert 'fork_context' not in instructions
    assert 'self-contained' in instructions
    assert 'read-only/scope/data instructions' in instructions
    assert 'review assignments must also include the candidate translations' in instructions
    assert 'separate bounded review assignment' in instructions
    assert 'Wait for every helper to finish' in instructions
    assert json.loads(manifest) == work
    serial, manifest = sync.prompt(release, work, 0).split('\n\n', 1)
    assert 'do not spawn subagents' in serial
    assert 'fork_context' not in serial
    assert 'fork_turns' not in serial
    assert json.loads(manifest) == work


def test_worker_batches_pending_languages_only_and_noop_needs_no_agent(repository, tmp_path, monkeypatch):
    run = tmp_path / 'run'
    run.mkdir()
    calls = []

    def execute(root, run, owner, model, effort, helpers):
        manifest = json.loads((run / 'prompt.txt').read_text().split('\n\n', 1)[1])
        calls.append(manifest)
        result = response(manifest)
        (run / 'agent-result.json').write_text(json.dumps(result))
        return result

    monkeypatch.setattr(sync, 'execute', execute)
    owner = os.open(run / 'owner', os.O_CREAT | os.O_RDWR, 0o600)
    assert sync.worker(repository, run, owner, 'gpt-6.1-sol', 'high', 2, 1) == 0
    assert [list(batch) for batch in calls] == [['fr'], ['de']]
    assert all(r['ProductVersion'] == '1.10' for batch in calls for rows in batch.values() for r in rows)
    calls.clear()
    owner = os.open(run / 'owner', os.O_RDWR)
    assert sync.worker(repository, run, owner, 'gpt-6.1-sol', 'high', 2, 1) == 0
    assert not calls


def test_guarded_internal_does_not_release_the_inherited_owner_lock(repository, tmp_path, monkeypatch):
    directory = tmp_path / 'workflow'
    directory.mkdir()
    run = directory / ('a' * 32)
    run.mkdir(mode=0o700)
    monkeypatch.setattr(sync, 'ROOT', repository)
    monkeypatch.setattr(sync, 'storage_directory', lambda *args, **kwargs: directory)
    sync.launcher.atomic(directory / 'current.json', {'run': run.name})
    with sync.launcher.lock(directory / 'owner') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        sync.guarded_internal(repository, run, owner)
        with sync.launcher.lock(directory / 'owner') as probe:
            assert sync.launcher.busy(probe)


def test_translation_sources_and_compiler_join_the_package_manifest():
    result = subprocess.run(['make', '--no-print-directory', 'package-source-files'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30, check=True)
    assert 'tools/whats_new_catalogs.py' in result.stdout.splitlines()
    assert 'common/oh_no_parent_control_ui/whats_new.py' in result.stdout.splitlines()
    assert 'docs/VersionHistory.md' in result.stdout.splitlines()
    assert 'data/whats-new-child.toml' in result.stdout.splitlines()
    assert 'data/whats-new.toml' not in result.stdout.splitlines()
    assert 'tools/sync_whatsnew.py' not in result.stdout.splitlines()
    assert 'WHATS_NEW_POFILES := $(wildcard po/whats-new/*/*.po)' in (ROOT / 'Makefile').read_text()


def test_real_launcher_transport_with_private_codex_double(repository):
    # Execute the actual detached worker/supervisor/renderer, never a live model.
    files = [
        'tools/sync-whatsnew', 'tools/sync_whatsnew.py', 'tools/whats_new_catalogs.py',
        'tools/sync_whatsnew_response.schema.json', 'tools/sync_whatsnew_translator.toml',
        'tools/detached_launcher.py', 'tools/test_storage.py', 'tools/test_retention.py',
        'tools/launcher_render.py', 'tools/launcher_progress.py', 'tools/watch_output.py',
        'tools/e2e_watch_protocol.py', 'tools/launcher_question.py',
        'common/oh_no_parent_control_ui/languages.py',
        'common/oh_no_parent_control_ui/localization.py',
        'common/oh_no_parent_control_ui/whats_new.py',
        'broker/oh_no_parent_control/whats_new.py',
    ]
    for name in files:
        destination = repository / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    binaries = repository / 'fake-bin'
    binaries.mkdir()
    codex = binaries / 'codex'
    codex.write_text('''#!/usr/bin/python3
import json, pathlib, sys
if sys.argv[1:] == ['debug', 'models']:
    print(json.dumps({'models': [{'slug': 'gpt-6.1-sol', 'visibility': 'list',
        'supported_reasoning_levels': [{'effort': 'high'}]}]}))
else:
    assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'
    assert sys.argv[sys.argv.index('--ask-for-approval') + 1] == 'never'
    work = json.loads(sys.stdin.read().split('\\n\\n', 1)[1])
    value = {'status': 'translated', 'summary': 'Fixture translation', 'translations': [
        {'language': language, 'records': [{'record_id': r['record_id'],
            'content': r['Content'].replace('New features', 'Nouveautés')}
            for r in rows]} for language, rows in work.items()]}
    pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps(value))
    print(json.dumps({'type': 'item.completed', 'item': {'id': 'fixture',
        'type': 'agent_message', 'text': 'Translated fixture batch'}}))
''')
    codex.chmod(0o755)
    environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'])
    result = subprocess.run([str(repository / 'tools/sync-whatsnew'), '--batch-size', '1', '--subagents', '0'],
                            cwd=repository, env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'all 2 non-English languages complete' in result.stdout
    assert catalogs.pending(repository) == {}
    # A complete rerun works even after the fake CLI disappears.
    codex.unlink()
    result = subprocess.run([str(repository / 'tools/sync-whatsnew')], cwd=repository,
                            env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
