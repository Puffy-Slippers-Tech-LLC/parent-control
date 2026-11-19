"""Explicit package targets shared by setup, local builds and VM consumers."""
from dataclasses import dataclass
import json
from pathlib import Path
import platform
import re


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

    def debian_version(self, version):
        """Keep the source/product revision and set its Ubuntu build series."""
        version, count = re.subn(r'~ubuntu[0-9]+\.[0-9]{2}(?=\.[0-9]+(?:~activation[0-9]+)?$)',
                                 '~ubuntu' + self.version, version)
        if count != 1:
            raise ValueError('DEB version lacks an Ubuntu release suffix')
        return version

    def matches_package_version(self, version):
        if self.package_format == 'rpm':
            return version.endswith(self.dist)
        try:
            return version == self.debian_version(version)
        except ValueError:
            return False


TARGET_PATTERNS = {
    'ubuntu': (re.compile(r'ubuntu([1-9][0-9]*\.[0-9]{2})'), 'deb'),
    'fedora': (re.compile(r'fedora([1-9][0-9]*)'), 'rpm'),
}


def get(name, architecture='x86_64', package_format=None):
    if architecture != 'x86_64':
        raise ValueError('unsupported architecture: ' + str(architecture))
    if isinstance(name, str):
        for distribution, (pattern, expected_format) in TARGET_PATTERNS.items():
            if match := pattern.fullmatch(name):
                if package_format is not None and package_format != expected_format:
                    raise ValueError('build_target does not match package_format')
                return Target(name, distribution, match[1], expected_format, architecture)
    raise ValueError('unsupported build_target: ' + str(name))


def from_family(family, package_format=None):
    if isinstance(family, str):
        name, separator, architecture = family.partition('-')
        if not separator:
            name, separator, architecture = family.partition('_')
        if separator:
            return get(name, architecture, package_format)
    raise ValueError('family must be BUILD_TARGET-ARCHITECTURE or BUILD_TARGET_ARCHITECTURE')


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
    parser.add_argument('--debian-version', help='print this source version for the native Ubuntu release')
    args = parser.parse_args()
    matches = [target for target in configured(Path(__file__).resolve().parents[1])
               if target.package_format == args.native_output and target.native()]
    if len(matches) != 1:
        parser.exit(1, 'No unique configured target for this host; set INSTALL_PACKAGE explicitly\n')
    target = matches[0]
    if args.debian_version is None:
        print(target.output(Path(__file__).resolve().parents[1]))
    elif target.package_format != 'deb':
        parser.error('--debian-version requires --native-output deb')
    else:
        print(target.debian_version(args.debian_version))
