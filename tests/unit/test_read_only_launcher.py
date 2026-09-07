"""Read-only aliases do not forward tool options that execute or write."""
import runpy
from pathlib import Path

import pytest

reader = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'tools/read-only'))


@pytest.mark.parametrize('args', [
    ['search', '--pre=/tmp/evil', 'needle'], ['sort', '-o', '/tmp/output'],
    ['unique', '--output=/tmp/file'], ['gzip', '--force', 'file'],
    ['slice', '1', '0'], ['slice', '1e', '10'], ['slice', '1', '10', '--expression=e'],
    ['fetch', 'file:///etc/shadow'], ['fetch', 'https://user:password@example.com'],
    ['fetch', 'https://example.com', '--output=/tmp/file'], ['fetch', 'https://example.com', '-XPOST'],
])
def test_mutating_options_refused(args):
    with pytest.raises(ValueError):
        reader['command'](args)


def test_fetch_is_fixed_get_with_no_config_credentials_redirect_protocol_or_output_override():
    command = reader['command'](['fetch', 'https://example.com/?query=x&y=z'])
    assert command[:4] == ['/usr/bin/curl', '--disable', '--globoff', '-fsSL']
    assert command[-2:] == ['--', 'https://example.com/?query=x&y=z']
    assert '--proto-redir' in command


def test_preprocessor_text_is_only_a_search_pattern():
    command = reader['command'](['search', '--', '--pre=/tmp/evil', '.'])
    assert command[-3:] == ['--', '--pre=/tmp/evil', '.']


def test_filter_paths_cannot_be_output_options():
    assert reader['command'](['sort', '--', '-o', 'file'])[-3:] == ['--', '-o', 'file']
    assert reader['command'](['slice', '2', '9', 'file']) == [
        '/usr/bin/sed', '-n', '2,9p', '--', 'file']
