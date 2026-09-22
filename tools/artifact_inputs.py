"""Build-only identities, independent of cleanup and live VM qualification."""

from email.parser import Parser
from importlib.util import cache_from_source
from pathlib import Path
import os
import re
import shutil
import stat
import subprocess
import sys
import sysconfig


SCHEMA = 1
FIXTURE_SOURCES = (
    'tests/__init__.py', 'tests/fixtures/__init__.py',
    'tests/fixtures/build_test_applications.py', 'tests/fixtures/gui_runtime.py',
    'tests/fixtures/gui_application.py', 'tests/fixtures/onpc_test_application.c',
    'common/oh_no_parent_control_ui/gtk_automation.py',
)
FIXTURE_IMPORTS = ('tests/__init__.py', 'tests/fixtures/__init__.py',
                   'tests/fixtures/gui_runtime.py')
PACKAGE_TOOLS = ('make', 'cc', 'dpkg-buildpackage', 'dpkg-deb', 'dpkg-architecture',
                 'glib-compile-schemas', 'git')
FIXTURE_TOOLS = ('cc', 'flatpak', 'snap', 'mksquashfs', 'ldd')


def dependency_names(value):
    # Include every installed alternative/provider. Architecture/profile clauses
    # may overselect, but must never hide an applicable build dependency.
    return {match.group(1) for part in re.split(r'[,|]', value)
            if (match := re.match(r'\s*([a-z0-9][a-z0-9+.-]*)', part))}


def package_records(status, roots, *, essential=False):
    records = [Parser().parsestr(part) for part in status.split('\n\n') if part.strip()]
    installed = {p['Package'] + ':' + p['Architecture']: p for p in records
                 if p.get('Status') == 'install ok installed'}
    providers = {}
    for key, record in installed.items():
        for name in {record['Package']} | dependency_names(record.get('Provides', '')):
            providers.setdefault(name, set()).add(key)
    pending = set(roots)
    if essential:
        pending.update(p['Package'] for p in installed.values() if p.get('Essential') == 'yes')
    selected = {}
    while pending:
        name = pending.pop()
        for key in providers.get(name, ()):
            if key in selected:
                continue
            record = installed[key]
            # Description and dpkg selection state cannot affect build output.
            selected[key] = {field: record.get(field, '') for field in (
                'Version', 'Architecture', 'Depends', 'Pre-Depends', 'Provides', 'Conffiles')}
            pending.update(dependency_names(record.get('Depends', '')) |
                           dependency_names(record.get('Pre-Depends', '')))
    # Missing dependencies are part of the identity too; fresh builds still
    # enforce their ordinary prerequisites rather than installing anything.
    return selected


def source_files(root, sources, *, imports=()):
    from e2e_startup_cache import files_digest
    paths = {Path(p) for p in sources}
    # Only bytecode for an actual imported module, never every sibling cache.
    for name in imports:
        path = Path(name)
        compiled = Path(cache_from_source(str(root / path), optimization=''))
        if compiled.exists():
            paths.add(compiled.relative_to(root))
    return files_digest(root, paths)


def tool_packages(paths):
    """Include the actual tool providers, including a different cc alternative."""
    paths = sorted({str(Path(path).resolve()) for path in paths if path})
    if not paths:
        return set()
    result = subprocess.run(['dpkg-query', '--search', *paths], check=True,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    packages = set()
    for line in result.stdout.splitlines():
        owners, separator, path = line.partition(': ')
        if separator and path in paths:
            packages.update(owner.split(':')[0] for owner in owners.split(', '))
    return packages


def runtime_inputs(root):
    """Capture managed build dependencies and executable Python/tool bytes.

    Builders run without site initialization. Neither pytest/GTK test imports,
    the user's desktop, host boot, nor installed ONPC helpers are build inputs.
    Dependency closure uses installed Debian records, including virtual providers.
    """
    from e2e_startup_cache import digest, file_digest
    control = Parser().parsestr((root / 'debian/control').read_text().split('\n\n')[0])
    package_roots = {'build-essential', 'python3', 'git'}
    for field in ('Build-Depends', 'Build-Depends-Arch', 'Build-Depends-Indep'):
        package_roots.update(dependency_names(control.get(field, '')))
    fixture_roots = {'build-essential', 'python3', 'python3-gi', 'python3-cairo',
                     'gir1.2-gtk-4.0', 'libgirepository-2.0-0', 'flatpak', 'snapd',
                     'squashfs-tools', 'fonts-dejavu-core', 'xkb-data', 'libc-bin'}
    status = Path('/var/lib/dpkg/status').read_text()
    # An in-progress package transaction cannot certify a stable toolchain.
    if any(Path('/var/lib/dpkg/updates').iterdir()):
        raise ValueError('startup cache: package update in progress')
    python = {}
    stdlib = Path(sysconfig.get_path('stdlib'))
    for path in sorted(stdlib.rglob('*')):
        if ('dist-packages' not in path.parts and 'site-packages' not in path.parts
                and path.is_file() and path.suffix in ('.py', '.pyc', '.so')):
            python[str(path)] = file_digest(path.resolve())
    common = {'python': digest(python), 'interpreter': file_digest(Path(sys.executable).resolve()),
              'architecture': os.uname().machine, 'schema': SCHEMA}
    result = {}
    for name, roots, commands in (('package', package_roots, PACKAGE_TOOLS),
                                   ('fixtures', fixture_roots, FIXTURE_TOOLS)):
        commands = {command: shutil.which(command) for command in commands}
        binaries = {name: [path, file_digest(Path(path).resolve())] if path else None
                    for name, path in commands.items()}
        result[name] = dict(common, packages=digest(package_records(
            status, roots | tool_packages(commands.values()), essential=name == 'package')),
                            tools=digest(binaries))
    # These non-Python resources and extension modules are copied into fixtures.
    # Hash them as well as managed dependency records, so local payload edits count.
    from tests.fixtures.gui_runtime import runtime_sources
    result['fixtures']['payload'] = digest({name: [str(path.resolve()),
        ['directory', stat.S_IMODE(path.stat().st_mode)] if path.is_dir()
        else file_digest(path.resolve())] for name, path in runtime_sources().items()})
    return result


def capture(builder):
    from e2e_startup_cache import digest
    root = builder.REPOSITORY
    paths = builder.package_inputs.paths(root)
    metadata = builder._metadata(paths, builder.package_inputs.digest(root, paths))
    runtime = runtime_inputs(root)
    shared = source_files(root, ('tools/build_test_artifacts.py', 'tools/artifact_inputs.py'),
                          imports=('tools/artifact_inputs.py',))
    inputs = {
        'package': {'source': digest(metadata['source']), 'build': digest(metadata['build_inputs']),
                    'builder': source_files(root, ('tools/package_inputs.py',),
                                            imports=('tools/package_inputs.py',)),
                    'shared': shared, **runtime['package']},
        'fixtures': {'source': source_files(root, FIXTURE_SOURCES, imports=FIXTURE_IMPORTS),
                     'shared': shared, **runtime['fixtures']},
    }
    return inputs, metadata
