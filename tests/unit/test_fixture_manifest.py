"""Inert codec inputs, confined to pytest-private disk; no runtime execution."""
import copy
import hashlib
import json
import struct
import tarfile

import pytest

from tests.fixtures import baseline_assets, native_assets
from tools import fixture_manifest as codec
from tests.support.fixture_bundles import compiler_record, environment_record


def elf(identity=b'test', *, library='libc.so.6', version='GLIBC_2.43'):
    """A bounded ELF container for parser tests, intentionally never executed."""
    data = bytearray(640)
    base = 0x400000
    ident = b'\x7fELF\x02\x01\x01' + bytes(9)
    struct.pack_into('<16sHHIQQQIHHHHHH', data, 0, ident, 2, 62, 1,
                     base + 600, 64, 0, 0, 64, 56, 3, 0, 0, 0)
    interpreter = codec.DEPENDENCIES['elf']['interpreter'].encode() + b'\0'
    struct.pack_into('<IIQQQQQQ', data, 64, 1, 5, 0, base, base, len(data), len(data), 4096)
    struct.pack_into('<IIQQQQQQ', data, 120, 3, 4, 232, base + 232, base + 232,
                     len(interpreter), len(interpreter), 1)
    struct.pack_into('<IIQQQQQQ', data, 176, 2, 4, 288, base + 288, base + 288, 96, 96, 8)
    data[232:232 + len(interpreter)] = interpreter
    strings = library.encode() + b'\0' + version.encode() + b'\0'
    data[416:416 + len(strings)] = strings
    dynamic = ((5, base + 416), (10, len(strings)), (1, 0),
               (0x6ffffffe, base + 512), (0x6fffffff, 1), (0, 0))
    for index, (tag, value) in enumerate(dynamic):
        struct.pack_into('<qQ', data, 288 + index * 16, tag, value)
    struct.pack_into('<HHIII', data, 512, 1, 1, 0, 16, 0)
    struct.pack_into('<IHHII', data, 528, 0, 0, 2, len(library) + 1, 0)
    data[600:600 + len(identity)] = identity
    return bytes(data)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def inputs(os_id='ubuntu'):
    from tools.artifact_inputs import NATIVE_RUNTIME_SOURCES
    source = {name: {'sha256': 'a' * 64, 'mode': 420, 'length': 12}
              for name in NATIVE_RUNTIME_SOURCES}
    for key, path in (('onpc-test-gui.py', 'tests/fixtures/gui_application.py'),
                      ('gtk_automation.py', 'common/oh_no_parent_control_ui/gtk_automation.py')):
        data = ('# inert ' + key + '\n').encode()
        source[path] = {'sha256': hashlib.sha256(data).hexdigest(), 'length': len(data), 'mode': 420}
    return {'source': source,
            'toolchain': {'compiler': compiler_record(os_id),
                          'environment': environment_record(os_id)},
            'target': {'os': os_id, 'release': '26.04' if os_id == 'ubuntu' else '44',
                       'architecture': 'x86_64'},
            'dependencies': copy.deepcopy(codec.DEPENDENCIES)}


def payloads():
    result = {}
    for key, declaration in codec.declarations().items():
        source = declaration['source']
        result[key] = (source if type(source) is bytes else
                       elf(source.encode()) if declaration['mode'] == 0o755 else
                       ('# inert ' + source + '\n').encode())
    return result


@pytest.fixture
def bundle(tmp_path):
    codec.write(tmp_path, inputs(), payloads())
    return tmp_path


def reseal(root):
    content = (root / 'fixture-manifest.json').read_bytes() + (root / 'payload.tar').read_bytes()
    (root / 'complete.json').write_bytes(canonical({'schema': 1, 'content_identity':
                                                  hashlib.sha256(content).hexdigest()}))


def test_declaration_inventory_preserves_exact_movable_maps():
    from types import SimpleNamespace
    accounts = {role: SimpleNamespace(pw_dir='@' + role + '@')
                for role in ('child', 'other', 'parent')}
    original = baseline_assets.native_files(accounts) | baseline_assets.catalogue_files(accounts)
    declared = codec.declarations()
    assert len(declared) == 67
    assert {item['destination']: (item['source'], item['mode'], item['owner'])
            for item in declared.values()} == original
    assert set(codec.select(['legacy'])) == set(declared)
    assert all(key == hashlib.sha256(item['destination'].encode()).hexdigest()
               for key, item in declared.items())
    assert all('/.config/' not in item['destination'] for item in declared.values())


def test_subsets_are_minimal_unions_with_exact_trust_and_absence():
    native, grid = codec.select(['native']), codec.select(['riley-grid'])
    assert len(native) == len(native_assets.sources()) == 12
    assert len(grid) == len(native_assets.riley_grid_sources()) == 9
    assert {item['destination'] for item in native.values()} == {
        destination for destination, _ in native_assets.source_destinations('@other@').values()}
    assert {item['destination'] for item in grid.values() if item['destination'].startswith('@')} == {
        '@child@/.local/share/applications/' + native_assets.desktop_id('A')}
    assert len(codec.select(['activity'])) == 3
    assert len(codec.select(['catalogue'])) == 33
    assert len(codec.select(['trusted-hard'])) == len(codec.select(['trusted-soft'])) == 1
    assert len(codec.select(['trusted-hard-launcher'])) == len(codec.select(['trusted-soft-launcher'])) == 1
    assert len(codec.select(['command'])) == len(codec.select(['whitespace'])) == len(codec.select(['retention'])) == 2
    assert len(codec.select(['pattern'])) == 3
    assert {item['destination'] for item in codec.select(['compatibility']).values()} == {
        *native_assets.legacy_executable_paths(),
        *(native_assets.PREFIX + '/' + name for name in native_assets.GUI_FILES)}
    assert len(codec.select(['mechanical'])) == 1
    assert set(codec.select(['native', 'activity'])) == set(native) | set(codec.select(['activity']))
    assert {item['destination'] for item in codec.declarations().values()
            if item['native_action'] == 'trust'} == set(native_assets.trusted_file_modes())
    assert {item['destination'] for item in native.values()
            if item['native_action'] == 'native-execute'} == {
        native_assets.executable_path(asset[0]) for asset in native_assets.ASSETS}
    assert codec.ABSENCES == [{'destination': '/usr/local/bin/onpc-test-catalog-fallback',
                               'subsets': ['catalogue', 'legacy']}]
    assert codec.select([]) == {}


@pytest.mark.parametrize('selection', [['future'], ['native', 'native'], 'native', [True]])
def test_unknown_or_malformed_subset_refused(selection):
    with pytest.raises(ValueError, match='fixture:subsets'):
        codec.select(selection)


@pytest.mark.parametrize('os_id', ['ubuntu', 'fedora'])
def test_write_independently_verifies_complete_target_bundle(tmp_path, os_id):
    manifest = codec.write(tmp_path, inputs(os_id), payloads())
    assert codec.verify(tmp_path, os_id) == manifest
    assert len(manifest['members']) == 67
    assert set(child.name for child in tmp_path.iterdir()) == {
        'fixture-manifest.json', 'payload.tar', 'complete.json'}
    assert all(child.stat().st_mode & 0o777 == 0o600 for child in tmp_path.iterdir())
    with pytest.raises(ValueError, match='fixture:target-mismatch'):
        codec.verify(tmp_path, 'fedora' if os_id == 'ubuntu' else 'ubuntu')


def test_identity_separates_recorded_inputs_from_output_bytes(tmp_path):
    first, second, third = [tmp_path / name for name in ('first', 'second', 'third')]
    for root in (first, second, third):
        root.mkdir(mode=0o700)
    first_manifest = codec.write(first, inputs(), payloads())
    changed_inputs = inputs()
    changed_inputs['toolchain']['compiler']['compiler_version'] = 'other-target-gcc'
    second_manifest = codec.write(second, changed_inputs, payloads())
    changed_bytes = payloads()
    for key, descriptor in codec.declarations().items():
        if descriptor['source'] == 'mechanical':
            changed_bytes[key] = elf(b'changed-mechanical')
    third_manifest = codec.write(third, inputs(), changed_bytes)
    assert first_manifest['build_identity'] != second_manifest['build_identity']
    assert first_manifest['build_identity'] == third_manifest['build_identity']
    identities = [json.loads((root / 'complete.json').read_bytes())['content_identity']
                  for root in (first, second, third)]
    assert len(set(identities)) == 3


@pytest.mark.parametrize('fault', ['missing', 'extra', 'literal', 'alias', 'identity', 'oversized'])
def test_writer_refuses_incomplete_or_inconsistent_payload_before_writes(tmp_path, fault):
    data, declarations = payloads(), codec.declarations()
    if fault == 'missing':
        data.pop(next(iter(data)))
    elif fault == 'extra':
        data['f' * 64] = b'foreign'
    elif fault == 'literal':
        key = next(key for key, item in declarations.items() if type(item['source']) is bytes)
        data[key] = b'[Desktop Entry]\nExec=foreign\n'
    elif fault == 'alias':
        key = next(key for key, item in declarations.items() if item['source'] == 'mechanical')
        data[key] = elf(b'changed-alias')
    elif fault == 'identity':
        for key, item in declarations.items():
            if item['source'] == 'A':
                data[key] = elf(b'H')
    elif fault == 'oversized':
        data[next(iter(data))] = bytes(codec.MAX_MEMBER + 1)
    with pytest.raises(ValueError, match='fixture:'):
        codec.write(tmp_path, inputs(), data)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('fault', ['schema', 'mode-bool', 'owner', 'destination', 'action',
                                  'length-bool', 'length-negative', 'extra-field', 'absence',
                                  'missing-member', 'dependency', 'identity'])
def test_verifier_refuses_modified_manifest_even_with_resealed_content(bundle, fault):
    manifest = json.loads((bundle / 'fixture-manifest.json').read_bytes())
    member = manifest['members'][next(iter(manifest['members']))]
    if fault == 'schema': manifest['schema'] = 2
    if fault == 'mode-bool': member['mode'] = True
    if fault == 'owner': member['owner'] = 'root'
    if fault == 'destination': member['destination'] = '/etc/passwd'
    if fault == 'action': member['native_action'] = 'foreign'
    if fault == 'length-bool': member['length'] = True
    if fault == 'length-negative': member['length'] = -1
    if fault == 'extra-field': member['command'] = 'foreign'
    if fault == 'absence': manifest['absences'] = []
    if fault == 'missing-member': manifest['members'].pop(next(iter(manifest['members'])))
    if fault == 'dependency': manifest['inputs']['dependencies']['elf']['needed'] = ['libevil.so']
    if fault == 'identity': manifest['build_identity'] = '0' * 64
    (bundle / 'fixture-manifest.json').write_bytes(canonical(manifest))
    reseal(bundle)
    with pytest.raises(ValueError, match='fixture:'):
        codec.verify(bundle)


@pytest.mark.parametrize('raw', [b'{"schema":1,"schema":1}\n', b'{"value":NaN}\n',
                              b'{"value":Infinity}\n', b'{}', b'\xff', b'[]\n'])
def test_verifier_refuses_duplicate_noncanonical_and_malformed_json(bundle, raw):
    (bundle / 'fixture-manifest.json').write_bytes(raw)
    with pytest.raises(ValueError, match='fixture:'):
        codec.verify(bundle)


@pytest.mark.parametrize('fault', ['traversal', 'absolute', 'symlink', 'hardlink', 'device',
                                  'directory', 'pax', 'duplicate', 'extra', 'truncated',
                                  'padding', 'checksum', 'trailer'])
def test_unsafe_or_inconsistent_archive_refused_without_extraction(bundle, fault):
    archive = bytearray((bundle / 'payload.tar').read_bytes())
    first = next(iter(codec.declarations()))
    if fault in ('traversal', 'absolute', 'symlink', 'hardlink', 'device', 'directory', 'pax'):
        item = tarfile.TarInfo('../escape' if fault == 'traversal' else
                               '/etc/escape' if fault == 'absolute' else first)
        item.type = {'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE,
                     'device': tarfile.CHRTYPE, 'directory': tarfile.DIRTYPE,
                     'pax': tarfile.XHDTYPE}.get(fault, tarfile.REGTYPE)
        item.linkname = 'foreign' if fault in ('symlink', 'hardlink') else ''
        archive[:512] = item.tobuf(format=tarfile.USTAR_FORMAT)
    elif fault == 'duplicate': archive[512:512] = archive[:512]
    elif fault == 'extra': archive.extend(b'foreign')
    elif fault == 'truncated': archive = archive[:600]
    elif fault == 'padding':
        manifest = json.loads((bundle / 'fixture-manifest.json').read_bytes())
        end = 512 + manifest['members'][first]['length']
        assert end % 512
        archive[end] = 1
    elif fault == 'checksum': archive[512] ^= 1
    elif fault == 'trailer': archive[-1] = 1
    (bundle / 'payload.tar').write_bytes(archive)
    reseal(bundle)
    with pytest.raises(ValueError, match='fixture:'):
        codec.verify(bundle)
    assert set(child.name for child in bundle.iterdir()) == {
        'fixture-manifest.json', 'payload.tar', 'complete.json'}


@pytest.mark.parametrize('fault', ['marker', 'missing-marker', 'extra-file', 'symlink', 'hardlink'])
def test_bundle_completion_and_regular_single_link_files_required(bundle, fault):
    if fault == 'marker': (bundle / 'complete.json').write_bytes(canonical({'schema': 1, 'content_identity': '0' * 64}))
    if fault == 'missing-marker': (bundle / 'complete.json').unlink()
    if fault == 'extra-file': (bundle / 'foreign').write_bytes(b'foreign')
    if fault == 'symlink':
        original = bundle / 'payload.tar'
        saved = bundle.parent / (bundle.name + '-payload')
        original.rename(saved)
        original.symlink_to(saved)
    if fault == 'hardlink':
        (bundle.parent / (bundle.name + '-alias')).hardlink_to(bundle / 'payload.tar')
    with pytest.raises(ValueError, match='fixture:'):
        codec.verify(bundle)


@pytest.mark.parametrize('fault', ['machine', 'class', 'loader', 'library', 'future-glibc',
                                  'namespace', 'segment', 'dynamic', 'version-cycle'])
def test_independent_elf_abi_checks_reject_incompatible_payload(fault):
    data = bytearray(elf())
    if fault == 'machine': struct.pack_into('<H', data, 18, 183)
    if fault == 'class': data[4] = 1
    if fault == 'loader': data[233] = ord('x')
    if fault == 'library': data = bytearray(elf(library='libevil.so'))
    if fault == 'future-glibc': data = bytearray(elf(version='GLIBC_2.44'))
    if fault == 'namespace': data = bytearray(elf(version='GLIBC_PRIVATE'))
    if fault == 'segment': struct.pack_into('<Q', data, 64 + 32, 2 ** 63)
    if fault == 'dynamic': struct.pack_into('<q', data, 288 + 80, 15)
    if fault == 'version-cycle': struct.pack_into('<I', data, 540, 16)
    with pytest.raises(ValueError, match='fixture:elf'):
        codec.verify_elf(bytes(data))


def test_elf_abi_parser_accepts_bounded_target_runtime():
    assert codec.verify_elf(elf())['glibc_versions'] == ['GLIBC_2.43']


@pytest.mark.parametrize('fault', ['missing-source', 'extra-source', 'source-mode',
                                  'source-digest', 'source-length', 'gui-binding'])
def test_frozen_source_inventory_and_gui_byte_binding_are_independent(tmp_path, fault):
    recorded = inputs()
    first = next(iter(recorded['source']))
    if fault == 'missing-source': recorded['source'].pop(first)
    if fault == 'extra-source': recorded['source']['product.py'] = recorded['source'][first]
    if fault == 'source-mode': recorded['source'][first]['mode'] = 0o666
    if fault == 'source-digest': recorded['source'][first]['sha256'] = 'G' * 64
    if fault == 'source-length': recorded['source'][first]['length'] = True
    if fault == 'gui-binding': recorded['source']['tests/fixtures/gui_application.py']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='fixture:'):
        codec.write(tmp_path, recorded, payloads())
    assert list(tmp_path.iterdir()) == []


def test_source_permissions_are_recorded_separately_from_guest_modes(tmp_path):
    recorded = inputs()
    recorded['source']['tests/fixtures/onpc_test_application.c']['mode'] = 0o640
    codec.write(tmp_path, recorded, payloads())
    assert codec.verify(tmp_path)['inputs']['source']['tests/fixtures/onpc_test_application.c']['mode'] == 0o640


def test_manifest_total_limit_is_checked_before_reading_archive(bundle, monkeypatch):
    monkeypatch.setattr(codec, 'MAX_TOTAL', 1)
    with pytest.raises(ValueError, match='fixture:total-length'):
        codec.verify(bundle)


def test_writer_never_marks_a_bundle_that_failed_independent_verification(tmp_path, monkeypatch):
    def refuse(*args):
        raise ValueError('independent refusal')
    monkeypatch.setattr(codec, '_verify', refuse)
    with pytest.raises(ValueError, match='independent refusal'):
        codec.write(tmp_path, inputs(), payloads())
    assert not (tmp_path / 'complete.json').exists()


def test_directory_ancestor_symlink_refused(tmp_path):
    original, alias = tmp_path / 'original', tmp_path / 'alias'
    original.mkdir()
    alias.symlink_to(original, target_is_directory=True)
    with pytest.raises(ValueError, match='fixture:directory-symlink'):
        codec.write(alias, inputs(), payloads())


@pytest.mark.parametrize('fault', ['missing-compiler', 'extra-field', 'target', 'fingerprint',
                                  'file-digest', 'header-path', 'image', 'abi'])
def test_resealed_bundle_refuses_incomplete_build_provenance_or_output_proof(bundle, fault):
    manifest = json.loads((bundle / 'fixture-manifest.json').read_bytes())
    compiler = manifest['inputs']['toolchain']['compiler']
    if fault == 'missing-compiler': manifest['inputs']['toolchain']['compiler'] = {'compiler': 'anything'}
    if fault == 'extra-field': compiler['arbitrary'] = 'ignored'
    if fault == 'target': compiler['target']['release'] = '44'
    if fault == 'fingerprint': compiler['dependency_sha256'] = '0' * 64
    if fault == 'file-digest': compiler['inputs']['cc']['sha256'] = 'G' * 64
    if fault == 'header-path': next(iter(compiler['headers'].values()))['path'] = '/etc/passwd'
    if fault == 'image': compiler['image_identity'] = 'mutable-name'
    if fault == 'abi': manifest['abi']['A']['sha256'] = '0' * 64
    manifest['build_identity'] = hashlib.sha256(canonical(manifest['inputs'])).hexdigest()
    (bundle / 'fixture-manifest.json').write_bytes(canonical(manifest))
    reseal(bundle)
    with pytest.raises(ValueError, match='fixture:'):
        codec.verify(bundle)


def test_empty_regular_toolchain_input_keeps_exact_length_and_hash(tmp_path):
    from tools.fixture_provenance import dependency_digest
    recorded = inputs()
    compiler = recorded['toolchain']['compiler']
    item = next(iter(compiler['python_runtime'].values()))
    item.update(size=0, sha256=hashlib.sha256(b'').hexdigest())
    compiler['dependency_sha256'] = dependency_digest(compiler)
    codec.write(tmp_path, recorded, payloads())
    assert codec.verify(tmp_path)['inputs'] == recorded
