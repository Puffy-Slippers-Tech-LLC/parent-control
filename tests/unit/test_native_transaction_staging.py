"""Attempt-private native input applicability; no VM or package database."""

import hashlib
import json
import shutil
from unittest.mock import Mock

import pytest
import system_runner
from tools import native_transaction_inputs as native


@pytest.fixture
def staged(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    manifest = {'schema_version': 1, 'package_format': 'deb',
                'pair_id': 'ubuntu26.04-bubblewrap'}
    (source / native.MANIFEST_NAME).write_text(json.dumps(manifest))
    (source / 'old.deb').write_bytes(b'authenticated old input')
    destination = tmp_path / 'input'
    destination.mkdir()
    selected = destination / 'selected-inputs.json'
    selected.write_text('{"files":{"history.py":{"sha256":"frozen"}}}')
    def verify(path, *, package_format):
        assert package_format == 'deb'
        assert (path / 'old.deb').read_bytes() == b'authenticated old input'
        return json.loads((path / native.MANIFEST_NAME).read_bytes())
    def stage(src, dst, *, package_format):
        value = verify(src, package_format=package_format)
        if (dst / native.MANIFEST_NAME).exists():
            assert verify(dst, package_format=package_format) == value
        else:
            shutil.copytree(src, dst, dirs_exist_ok=True)
        return value
    monkeypatch.setattr(native, 'stage', Mock(side_effect=stage))
    monkeypatch.setattr(native, 'verify', Mock(side_effect=verify))
    options = {'package_format': 'deb', 'baseline_provenance_sha256': 'b' * 64,
               'selected_inputs_sha256': hashlib.sha256(selected.read_bytes()).hexdigest()}
    return source, destination, options


def test_stage_binds_manifest_selection_and_baseline_and_repeat_is_read_only(staged):
    source, destination, options = staged
    binding = system_runner.stage_native_assets(source, destination, **options)
    assert binding['native_manifest_sha256'] == hashlib.sha256(
        (source / native.MANIFEST_NAME).read_bytes()).hexdigest()
    assert binding['baseline_provenance_sha256'] == options['baseline_provenance_sha256']
    assert binding['selected_inputs_sha256'] == options['selected_inputs_sha256']
    def snapshot():
        return {str(path): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in destination.rglob('*') if path.is_file()}
    before = snapshot()
    assert system_runner.stage_native_assets(source, destination, **options) == binding
    assert system_runner.verify_native_assets(destination, **options) == binding
    assert snapshot() == before


@pytest.mark.parametrize('fault', ['baseline', 'selection', 'manifest', 'binding', 'bytes', 'link'])
def test_retained_inputs_cannot_be_rebound_or_substituted(staged, fault):
    source, destination, options = staged
    system_runner.stage_native_assets(source, destination, **options)
    if fault == 'baseline':
        options['baseline_provenance_sha256'] = 'c' * 64
    elif fault == 'selection':
        (destination / 'selected-inputs.json').write_text('different selected helper')
    elif fault == 'manifest':
        path = destination / 'native-transaction' / native.MANIFEST_NAME
        path.write_text(path.read_text() + '\n')
    elif fault == 'binding':
        path = destination / 'native-transaction-binding.json'
        value = json.loads(path.read_bytes())
        value['native_manifest_sha256'] = 'f' * 64
        path.write_text(json.dumps(value))
    elif fault == 'bytes':
        (destination / 'native-transaction/old.deb').write_bytes(b'tampered')
    else:
        path = destination / 'native-transaction-binding.json'
        path.unlink()
        path.symlink_to(source / native.MANIFEST_NAME)
    with pytest.raises((system_runner.Error, ValueError, AssertionError)):
        system_runner.verify_native_assets(destination, **options)


@pytest.mark.parametrize('field', ['baseline_provenance_sha256', 'selected_inputs_sha256'])
def test_missing_applicability_refuses_before_staging(staged, field):
    source, destination, options = staged
    options[field] = ''
    with pytest.raises(system_runner.Error, match='native-provenance-required'):
        system_runner.stage_native_assets(source, destination, **options)
    native.stage.assert_not_called()
    assert not (destination / 'native-transaction').exists()


def test_interrupted_binding_publication_retries_owned_frozen_inputs(staged, monkeypatch):
    source, destination, options = staged
    publish = native.publish_record
    def interrupted(path, value):
        if path.name == 'native-transaction-binding.json':
            raise OSError('interrupted')
        return publish(path, value)
    monkeypatch.setattr(native, 'publish_record', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        system_runner.stage_native_assets(source, destination, **options)
    assert (destination / 'native-transaction').is_dir()
    assert not (destination / 'native-transaction-binding.json').exists()
    monkeypatch.setattr(native, 'publish_record', publish)
    binding = system_runner.stage_native_assets(source, destination, **options)
    assert system_runner.verify_native_assets(destination, **options) == binding


@pytest.mark.parametrize('changed', ['baseline', 'selection', 'source'])
def test_interrupted_staging_cannot_adopt_different_applicability(staged, monkeypatch, changed):
    source, destination, options = staged
    actual = native.stage
    monkeypatch.setattr(native, 'stage', Mock(side_effect=OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        system_runner.stage_native_assets(source, destination, **options)
    if changed == 'baseline':
        options['baseline_provenance_sha256'] = 'd' * 64
    elif changed == 'selection':
        path = destination / 'selected-inputs.json'
        path.write_text('different helper selection')
        options['selected_inputs_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        path = source / native.MANIFEST_NAME
        path.write_text(path.read_text() + '\n')
    monkeypatch.setattr(native, 'stage', actual)
    with pytest.raises(system_runner.Error, match='native-intent-mismatch'):
        system_runner.stage_native_assets(source, destination, **options)
    actual.assert_not_called()


def test_published_repeat_rechecks_the_requested_source(staged):
    source, destination, options = staged
    system_runner.stage_native_assets(source, destination, **options)
    (source / 'old.deb').write_bytes(b'substituted source')
    with pytest.raises(AssertionError):
        system_runner.stage_native_assets(source, destination, **options)
