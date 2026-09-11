"""Signing never executes .envrc or passes secrets through argv/environment/logs."""
import os
import subprocess
from types import SimpleNamespace

import pytest

from tools.publishing import signing
from tests.support.paths import ROOT


def test_signer_uses_original_checkout_and_is_directly_executable():
    assert signing.ROOT == ROOT
    assert os.access(ROOT / 'tools/publishing/signing.py', os.X_OK)


@pytest.mark.parametrize('assignment,expected', [
    ("export APT_PACKAGE_PRIVATE_KEY_PASSPHRASE='literal $ and ` characters'", b'literal $ and ` characters'),
    ('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE="spaces and punctuation !" # comment', b'spaces and punctuation !'),
    ('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE=plain-literal', b'plain-literal'),
])
def test_reads_literal_assignments_without_a_shell(tmp_path, assignment, expected):
    (tmp_path / '.envrc').write_text(assignment + '\n')
    assert signing.read_passphrase(tmp_path) == expected


@pytest.mark.parametrize('value', ['', "''", '$(touch /tmp/should-never-exist)', '"$HOME"',
                                  '`id`', 'one; id', 'placeholder', '"unterminated'])
def test_invalid_values_fail_without_echoing_them(tmp_path, value):
    (tmp_path / '.envrc').write_text('APT_PACKAGE_PRIVATE_KEY_PASSPHRASE=' + value + '\n')
    with pytest.raises(ValueError):
        signing.read_passphrase(tmp_path)


def test_duplicate_assignment_and_symlinks_are_refused(tmp_path):
    path = tmp_path / '.envrc'
    path.write_text("APT_PACKAGE_PRIVATE_KEY_PASSPHRASE='one'\n" * 2)
    with pytest.raises(ValueError):
        signing.read_passphrase(tmp_path)
    path.unlink()
    path.symlink_to(tmp_path / 'missing')
    with pytest.raises(OSError):
        signing.read_passphrase(tmp_path)


@pytest.mark.parametrize('returncode', [0, 2])
def test_secret_only_reaches_gpg_pipe_and_diagnostics_are_redacted(monkeypatch, capsys, returncode):
    secret = b'private-test-passphrase'
    monkeypatch.setattr(signing, 'read_passphrase', lambda: secret)
    monkeypatch.setenv(signing.VARIABLE, secret.decode())

    def run(argv, **kwargs):
        assert '--batch' in argv and '--no-tty' in argv
        assert argv[argv.index('--pinentry-mode') + 1] == 'loopback'
        assert secret.decode() not in repr(argv)
        assert signing.VARIABLE not in kwargs['env']
        fd = int(argv[argv.index('--passphrase-fd') + 1])
        assert kwargs['pass_fds'] == (fd,)
        assert os.read(fd, 4096) == secret + b'\n'
        assert kwargs['stderr'] == subprocess.PIPE
        return SimpleNamespace(returncode=returncode, stderr=b'diagnostic ' + secret)

    monkeypatch.setattr(signing.subprocess, 'run', run)
    assert signing.main(['--detach-sign']) == (0 if returncode == 0 else 1)
    output = capsys.readouterr()
    assert secret.decode() not in output.out + output.err


def test_git_receives_only_machine_readable_signature_status(monkeypatch, capsys):
    monkeypatch.setattr(signing, 'read_passphrase', lambda: b'passphrase')
    status = b'[GNUPG:] SIG_CREATED D 1 10 00 1 FINGERPRINT'
    monkeypatch.setattr(signing.subprocess, 'run', lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stderr=b'private identity\n' + status + b'\n'))
    assert signing.main(['--detach-sign']) == 0
    assert capsys.readouterr().err == status.decode() + '\n'
