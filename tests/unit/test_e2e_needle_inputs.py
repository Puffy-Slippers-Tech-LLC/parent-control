"""Needle input/provenance contract; synthetic pixels never qualify a prompt."""

import hashlib
import json
from pathlib import Path
import struct

import pytest

import e2e_worker as worker


@pytest.fixture
def distribution(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    dist = root / 'tests/integration/graphical_smoke'
    (dist / 'tests').mkdir(parents=True)
    (dist / 'needles').mkdir()
    (dist / 'main.pm').write_text('1;')
    (dist / 'tests/smoke.pm').write_text('1;')
    base = dist / 'needles/onpc-gdm-parent-masked-password'
    base.with_suffix('.png').write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + struct.pack('!II', 1024, 768))
    base.with_suffix('.json').write_text(json.dumps({'tags': [base.name], 'area': [
        {'xpos': 400, 'ypos': 400, 'width': 200, 'height': 40, 'type': 'match', 'match': 100}]}))
    monkeypatch.setattr(worker, 'ROOT', root)
    monkeypatch.setattr(worker, 'DISTRIBUTION', dist)
    return dist, base


def test_needle_bytes_are_frozen_and_part_of_distribution_digest(tmp_path, distribution):
    dist, _ = distribution
    files = worker.distribution_inputs()
    prefix = dist.relative_to(worker.ROOT).as_posix() + '/'
    expected = {prefix + name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    out = tmp_path / 'work'
    out.mkdir(mode=0o700)
    digest = worker.stage_distribution(out, expected)
    assert len(digest) == 64
    for name, value in files.items():
        assert (out / 'distribution' / name).read_bytes() == value
    (dist / 'needles/onpc-gdm-parent-masked-password.png').write_bytes(files['needles/onpc-gdm-parent-masked-password.png'] + b'changed')
    with pytest.raises(RuntimeError, match='inputs-changed'):
        worker.stage_distribution(tmp_path, expected)
    assert not (tmp_path / 'distribution').exists()


@pytest.mark.parametrize('fault', ['missing-png', 'missing-json', 'symlink', 'unknown',
    'bad-json', 'tag', 'property', 'exclude', 'threshold', 'offscreen', 'bool', 'empty', 'png', 'dimensions'])
def test_invalid_or_unsafe_needle_refuses_before_staging(distribution, fault):
    dist, base = distribution
    path = base.with_suffix('.json')
    doc = json.loads(path.read_bytes())
    if fault.startswith('missing-'):
        base.with_suffix('.' + fault[8:]).unlink()
    elif fault == 'symlink':
        (dist / 'needles/linked.png').symlink_to(base.with_suffix('.png'))
    elif fault == 'unknown': (dist / 'needles/unknown.json').write_text('{}')
    elif fault == 'bad-json': path.write_bytes(b'not-json')
    elif fault == 'png': base.with_suffix('.png').write_bytes(b'not-png')
    elif fault == 'dimensions':
        raw = base.with_suffix('.png').read_bytes()
        base.with_suffix('.png').write_bytes(raw[:16] + struct.pack('!II', 0, 768))
    else:
        if fault == 'tag': doc['tags'] = ['onpc-polkit-masked-password']
        elif fault == 'property': doc['properties'] = ['workaround']
        elif fault == 'exclude': doc['area'][0]['type'] = 'exclude'
        elif fault == 'threshold': doc['area'][0]['match'] = 50
        elif fault == 'offscreen': doc['area'][0]['width'] = 1024
        elif fault == 'bool': doc['area'][0]['match'] = True
        elif fault == 'empty': doc['area'] = []
        path.write_text(json.dumps(doc))
    with pytest.raises(RuntimeError, match='e2e:'):
        worker.distribution_inputs()


def test_generic_password_prompt_cannot_authorize_a_fixture_role(distribution):
    dist, base = distribution
    for suffix in ('.json', '.png'):
        base.with_suffix(suffix).rename(dist / ('needles/onpc-gdm-masked-password' + suffix))
    with pytest.raises(RuntimeError, match='needle-name'):
        worker.distribution_inputs()


@pytest.mark.parametrize('point', [None, {}, 'center', {'xpos': True, 'ypos': 10},
    {'xpos': 0, 'ypos': 10}, {'xpos': 200, 'ypos': 10}, {'xpos': 10, 'ypos': 40},
    {'xpos': 10, 'ypos': 10, 'id': 'unexpected'}, {'xpos': 10, 'ypos': 10}])
def test_account_click_point_must_stay_inside_matched_region(distribution, point):
    dist, base = distribution
    account = base.with_name('onpc-gdm-parent-account')
    doc = json.loads(base.with_suffix('.json').read_bytes())
    doc['tags'] = [account.name]
    doc['area'][0]['click_point'] = point
    base.with_suffix('.png').rename(account.with_suffix('.png'))
    base.with_suffix('.json').unlink()
    account.with_suffix('.json').write_text(json.dumps(doc))
    if point == {'xpos': 10, 'ypos': 10}:
        worker.distribution_inputs()
    else:
        with pytest.raises(RuntimeError, match='needle-click-point'):
            worker.distribution_inputs()


def test_password_prompt_cannot_add_a_click_point(distribution):
    _, base = distribution
    path = base.with_suffix('.json')
    doc = json.loads(path.read_bytes())
    doc['area'][0]['click_point'] = {'xpos': 10, 'ypos': 10}
    path.write_text(json.dumps(doc))
    with pytest.raises(RuntimeError, match='needle-click-point'):
        worker.distribution_inputs()


@pytest.mark.parametrize('fault', [None, 'cursor', 'threshold', 'bool', 'click',
                                  'missing', 'extra', 'dimensions'])
def test_vt6_needle_permits_only_reviewed_full_frame_and_cursor(distribution, fault):
    dist, _ = distribution
    needles = Path(worker.__file__).resolve().parents[1] / 'integration/graphical_smoke/needles'
    base = dist / 'needles/onpc-vt6-parent-password'
    png = (needles / (base.name + '.png')).read_bytes()
    doc = json.loads((needles / (base.name + '.json')).read_bytes())
    if fault == 'cursor': doc['area'][-1]['width'] += 1
    elif fault == 'threshold': doc['area'][0]['match'] = 99
    elif fault == 'bool': doc['area'][0]['xpos'] = False
    elif fault == 'click': doc['area'][0]['click_point'] = {'xpos': 1, 'ypos': 1}
    elif fault == 'missing': doc['area'].pop(1)
    elif fault == 'extra': doc['area'].append(dict(doc['area'][0]))
    elif fault == 'dimensions': png = png[:16] + struct.pack('!II', 1280, 800) + png[24:]
    base.with_suffix('.png').write_bytes(png)
    base.with_suffix('.json').write_text(json.dumps(doc))
    if fault:
        with pytest.raises(RuntimeError, match='vt6-needle-layout'):
            worker.distribution_inputs()
    else:
        worker.distribution_inputs()


@pytest.mark.parametrize('variant', ['onpc-gdm-parent-installed-account',
    'onpc-gdm-child-installed-account', 'onpc-gdm-parent-installed-masked-password',
    'onpc-polkit-parent-installed-account'])
def test_installed_greeter_variant_is_fixed_and_readiness_only(distribution, variant):
    dist, base = distribution
    installed = base.with_name(variant)
    doc = json.loads(base.with_suffix('.json').read_bytes())
    doc['tags'] = [variant]
    base.with_suffix('.png').rename(installed.with_suffix('.png'))
    base.with_suffix('.json').unlink()
    installed.with_suffix('.json').write_text(json.dumps(doc))
    if variant != 'onpc-gdm-parent-installed-account':
        with pytest.raises(RuntimeError, match='needle-name'):
            worker.distribution_inputs()
        return
    worker.distribution_inputs()
    doc['area'][0]['click_point'] = {'xpos': 10, 'ypos': 10}
    installed.with_suffix('.json').write_text(json.dumps(doc))
    with pytest.raises(RuntimeError, match='needle-click-point'):
        worker.distribution_inputs()
