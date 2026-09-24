"""Build a local package without cleaning or traversing the working checkout."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

import package_inputs
from test_storage import scratch_directory, scratch_descriptors


def build(root: Path, architecture: str) -> None:
    with tempfile.TemporaryDirectory(prefix='onpc-package-', dir=scratch_directory()) as temporary:
        source = Path(temporary) / 'source'
        source.mkdir()
        package_inputs.copy(root, source)
        subprocess.run(
            ['make', '--no-print-directory', '_build-package',
             f'DEB_HOST_ARCH={architecture}'], cwd=source, check=True,
            pass_fds=scratch_descriptors())
        output = root / 'output'
        output.mkdir(exist_ok=True)
        for artifact in (source / 'output').iterdir():
            shutil.move(str(artifact), output / artifact.name)
    print(f'SUCCESS: build artifacts are in {output}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--architecture', required=True)
    arguments = parser.parse_args()
    try:
        build(Path(__file__).resolve().parents[1], arguments.architecture)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'FAIL: build: {error}\n')
