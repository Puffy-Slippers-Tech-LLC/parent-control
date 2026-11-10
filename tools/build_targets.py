"""Explicit package targets shared by setup, local builds and VM consumers."""
from dataclasses import dataclass
import json
from pathlib import Path
import platform


@dataclass(frozen=True)
class Target:
    name: str
    distribution: str
    version: str
    package_format: str
    architecture: str = 'x86_64'

    @property
    def package_architecture(self):
        return 'amd64' if self.package_format == 'deb' else self.architecture

    @property
    def dist(self):
        return '.fc' + self.version

    def native(self):
        release = platform.freedesktop_os_release()
        return (release.get('ID') == self.distribution
                and release.get('VERSION_ID') == self.version
                and platform.machine() == self.architecture)

    def output(self, root):
        return root / 'output' / self.package_format / self.name / self.architecture


TARGETS = {(target.name, target.architecture): target for target in (
    Target('ubuntu26.04', 'ubuntu', '26.04', 'deb'),
    Target('fedora44', 'fedora', '44', 'rpm'),
    Target('fedora45', 'fedora', '45', 'rpm'),
)}


def get(name, architecture='x86_64', package_format=None):
    if not isinstance(name, str) or not any(target.name == name for target in TARGETS.values()):
        raise ValueError('unsupported build_target: ' + str(name))
    if not isinstance(architecture, str) or (name, architecture) not in TARGETS:
        raise ValueError('unsupported architecture: ' + str(architecture))
    target = TARGETS[(name, architecture)]
    if package_format is not None and package_format != target.package_format:
        raise ValueError('build_target does not match package_format')
    return target


def from_family(family, package_format=None):
    if not isinstance(family, str) or '-' not in family:
        raise ValueError('family must be BUILD_TARGET-ARCHITECTURE, for example fedora45-x86_64')
    name, architecture = family.rsplit('-', 1)
    return get(name, architecture, package_format)


def configured(root: Path):
    """Build each declared combination once, independently of VM availability."""
    document = json.loads((root / 'config/environment.json').read_text())
    targets = {}
    for family in document['families']:
        target = from_family(family['family'], family['package_format'])
        targets[(target.name, target.architecture)] = target
    if not targets:
        raise ValueError('no package build targets configured')
    return tuple(targets.values())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-output', required=True, choices=('deb', 'rpm'))
    args = parser.parse_args()
    matches = [target for target in configured(Path(__file__).resolve().parents[1])
               if target.package_format == args.native_output and target.native()]
    if len(matches) != 1:
        parser.exit(1, 'No unique configured target for this host; set INSTALL_PACKAGE explicitly\n')
    print(matches[0].output(Path(__file__).resolve().parents[1]))
