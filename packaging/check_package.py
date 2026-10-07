"""Check product source formats in an unpacked package, without developer tools."""
import ast
import json
from pathlib import Path
import subprocess
import tomllib
import xml.etree.ElementTree as ET

from render_lifecycle import PHASES, render


def check_lifecycle(root: Path) -> None:
    # Templates and adapters are not standalone shell files. Check the actual
    # expanded scripts for both formats, including source-only build checks.
    for distribution in ('ubuntu', 'fedora'):
        for phase in PHASES:
            result = subprocess.run(
                ['/bin/sh', '-n'], input=render(root, distribution, phase),
                text=True, capture_output=True, check=False)
            if result.returncode:
                raise ValueError(f'{distribution} {phase}: {result.stderr.strip()}')


def main():
    root = Path(__file__).resolve().parents[1]
    selected = subprocess.check_output(
        ['make', '--no-print-directory', 'package-source-files'], cwd=root, text=True).splitlines()
    for name in selected:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'missing regular package input: {name}')
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=name)
        elif path.suffix == '.json':
            json.loads(path.read_text())
        elif path.suffix == '.toml':
            tomllib.loads(path.read_text(encoding='utf-8'))
        elif path.suffix == '.xml' or name.endswith(('.policy.in', '.conf.in')):
            ET.parse(path)
        elif path.suffix in ('.js', '.mjs'):
            subprocess.run(['node', '--check', str(path)], check=True)
    check_lifecycle(root)
    subprocess.run(['make', '--no-print-directory', 'check-release-version'], cwd=root, check=True)
    print(f'package-check: passed ({len(selected)} product/build inputs)')


if __name__ == '__main__':
    main()
