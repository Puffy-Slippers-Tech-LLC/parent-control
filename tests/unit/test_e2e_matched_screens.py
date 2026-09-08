"""Completed public module evidence must prove the later graphical return."""

import copy
import json

import pytest

from test_graphical_smoke import png
from test_e2e_controller_qualification_cleanup_safety import qualification, EvidenceError


@pytest.fixture
def completed(tmp_path):
    account, prompt = 'onpc-gdm-parent-account', 'onpc-gdm-parent-masked-password'
    details = []
    for number, needle in enumerate((account, account, account, prompt, account, account), 1):
        if number == 6:
            details.append({'title': 'serial-logout', 'result': 'ok'})
        name = f'smoke-{number}.png'
        # Deliberately identical initial/return images: serial leaves GDM alone.
        png(tmp_path, name=name, suffix=b'private-canary')
        details.append({'needle': needle, 'screenshot': name, 'result': 'ok',
                        'area': [{'result': 'ok', 'similarity': 100}]})
    details.append({'title': 'gdm-return', 'result': 'ok'})
    document = {'result': 'ok', 'dents': 0, 'details': details}
    return tmp_path, document


def collect(completed):
    directory, document = completed
    (directory / 'testresults/result-smoke.json').write_text(json.dumps(document))
    return qualification.matched_screens(directory)


def test_ordered_matches_retain_only_screen_metadata(completed):
    result = collect(completed)
    assert [r['stage'] for r in result] == ['initial', 'select-ready', 'click', 'prompt', 'dismissed', 'returned']
    assert result[0]['sha256'] == result[-1]['sha256']
    assert all(set(r) == {'stage', 'detail_index', 'needle', 'width', 'height', 'sha256'} for r in result)
    assert 'private-canary' not in json.dumps(result)


@pytest.mark.parametrize('mutation', ['missing-return', 'old-screen', 'wrong-needle',
    'extra-match', 'missing-logout', 'duplicate-logout', 'early-return', 'low-match',
    'failed-area', 'missing-area', 'missing-screen', 'path', 'symlink', 'module-fail'])
def test_incomplete_or_misordered_screen_proof_refused(completed, mutation):
    directory, document = completed
    details = document['details']
    final = details[-2]
    if mutation == 'missing-return':
        details.pop(-2)
    elif mutation == 'old-screen':
        details[-3], details[-2] = details[-2], details[-3]
    elif mutation == 'wrong-needle':
        final['needle'] = 'private-canary'
    elif mutation == 'extra-match':
        details.append(copy.deepcopy(final))
    elif mutation == 'missing-logout':
        details.pop(-3)
    elif mutation == 'duplicate-logout':
        details.append(copy.deepcopy(details[-3]))
    elif mutation == 'early-return':
        details.insert(0, details.pop())
    elif mutation == 'low-match':
        final['area'][0]['similarity'] = 99
    elif mutation == 'failed-area':
        final['area'][0]['result'] = 'fail'
    elif mutation == 'missing-area':
        final['area'] = []
    elif mutation == 'missing-screen':
        (directory / 'testresults' / final['screenshot']).unlink()
    elif mutation == 'path':
        final['screenshot'] = '../private-canary'
    elif mutation == 'symlink':
        path = directory / 'testresults' / final['screenshot']
        path.unlink()
        path.symlink_to(directory / 'testresults/smoke-1.png')
    else:
        document['result'] = 'fail'
    with pytest.raises((EvidenceError, RuntimeError, OSError)):
        collect(completed)
