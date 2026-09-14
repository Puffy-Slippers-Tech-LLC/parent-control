"""Select and freeze the product/build inputs declared by the packaging map."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess


def paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ['make', '--no-print-directory', 'package-source-files'], cwd=root,
        check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selected = sorted({Path(name) for name in result.stdout.splitlines()})
    if not selected or any(p.is_absolute() or '..' in p.parts for p in selected):
        raise ValueError('invalid package source manifest')
    return selected


def digest(root: Path, selected: list[Path]) -> str:
    value = hashlib.sha256()
    for relative in selected:
        path = root / relative
        if path.is_symlink() or path.resolve() != root.resolve() / relative or not path.is_file():
            raise ValueError(f'package input must be a regular file: {relative}')
        value.update(relative.as_posix().encode() + b'\0')
        value.update(f'{path.stat().st_mode & 0o7777:o}'.encode() + b'\0')
        value.update(path.read_bytes())
    return value.hexdigest()


def copy(root: Path, destination: Path) -> list[Path]:
    selected = paths(root)
    before = digest(root, selected)
    for relative in selected:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    if (paths(root) != selected or digest(root, selected) != before
            or digest(destination, selected) != before):
        raise ValueError('package source inputs changed while copying')
    return selected
