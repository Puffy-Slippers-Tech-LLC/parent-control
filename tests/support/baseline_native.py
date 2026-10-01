"""Caller-owned host trees representing already prepared baseline files."""
import os
from pathlib import Path
from types import SimpleNamespace

import system_enforcement as enforcement


def install(declaration, source, *, root, monkeypatch, identities=None):
    identities = identities or {}
    for filename, (content, mode, role) in declaration.items():
        path = Path(filename)
        assert path.is_relative_to(root)
        for directory in reversed((path.parent, *path.parent.parents)):
            if directory.is_relative_to(root) and not directory.exists():
                directory.mkdir(mode=0o755)
                directory.chmod(0o755)
        with path.open('xb') as stream:
            stream.write(content if isinstance(content, bytes) else source.read_bytes())
        path.chmod(mode)
    actual = enforcement.verify_fixture_files
    # Patch only the installed-root identity boundary, leaving content, mode,
    # link, ancestry and target checks real in caller-owned private files.
    if hasattr(actual, '_original'):
        actual = actual._original
    def verify(files, accounts):
        expected = {}
        for filename, (_, _, role) in files.items():
            user = accounts.get(role)
            expected[Path(filename)] = (user.pw_uid, user.pw_gid) if user else (0, 0)
        def metadata(path):
            info = path.lstat()
            uid, gid = expected.get(path, (0, 0))
            return SimpleNamespace(**{key: getattr(info, key) for key in
                                      ('st_mode', 'st_nlink')}, st_uid=uid, st_gid=gid)
        with monkeypatch.context() as scoped:
            scoped.setattr(enforcement, 'fixture_metadata', metadata)
            return actual(files, accounts, root=root)
    verify._original = actual
    monkeypatch.setattr(enforcement, 'verify_fixture_files', verify)


def native(target, desktop, source, *, root, monkeypatch, unrelated=False):
    declaration = {str(target): ('mechanical', 0o755, 'system'),
                   str(desktop): (('[Desktop Entry]\nType=Application\nName=ONPC Native Fixture\n'
                                  f'Exec="{target}"\nTerminal=false\n').encode(), 0o644, 'system')}
    if unrelated:
        declaration[str(target.with_name('Unrelated.AppImage'))] = ('mechanical', 0o755, 'system')
    install(declaration, source, root=root, monkeypatch=monkeypatch)
