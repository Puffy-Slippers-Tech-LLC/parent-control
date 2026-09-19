"""Offline GUI runtime payload from the maintained host's installed public ABI.

Copies only the Python/GTK runtime and its resolved ELF dependencies, fonts and
typelibs. No package install, service activation, host home or host policy files.
The enclosing builder hashes every delivered byte and normalizes timestamps.
"""

from pathlib import Path
import re
import shutil
import subprocess
import sysconfig


TYPELIBS = (
    'Gtk-4.0', 'Gdk-4.0', 'Gsk-4.0', 'GdkPixbuf-2.0', 'Gio-2.0',
    'GLib-2.0', 'GLibUnix-2.0', 'GioUnix-2.0', 'GObject-2.0', 'Pango-1.0', 'PangoCairo-1.0', 'Graphene-1.0',
    'HarfBuzz-0.0', 'cairo-1.0', 'freetype2-2.0', 'GModule-2.0',
)


def build_runtime(destination):
    """Fill a new runtime /usr tree; return its architecture and ELF loader."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    triplet = sysconfig.get_config_var('MULTIARCH')
    if not triplet or re.fullmatch(r'[a-z0-9_-]+', triplet) is None:
        raise RuntimeError('GUI fixture requires a supported Debian multiarch runtime')
    interpreter = Path('/usr/bin/python3').resolve(strict=True)
    stdlib = Path('/usr/lib') / interpreter.name
    roots = [interpreter]

    def copy_file(source, relative):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        target.chmod(source.stat().st_mode & 0o777)
        return target

    def copy_tree(source, relative):
        if not source.is_dir():
            raise RuntimeError('GUI fixture runtime prerequisite missing: ' + str(source))
        target = destination / relative
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        roots.extend(path for path in source.rglob('*.so') if path.is_file())

    copy_file(interpreter, Path('bin/python3'))
    copy_tree(stdlib, Path('lib') / interpreter.name)
    for package in ('gi', 'cairo'):
        relative = Path('lib/python3/dist-packages') / package
        copy_tree(Path('/usr') / relative, relative)
    for name in TYPELIBS:
        relative = Path('lib') / triplet / 'girepository-1.0' / (name + '.typelib')
        copy_file(Path('/usr') / relative, relative)
    library_root = Path('/usr/lib') / triplet
    entry_libraries = {library_root / name for name in (
        'libgtk-4.so.1', 'libgirepository-2.0.so.0', 'libpangocairo-1.0.so.0',
    )}
    roots.extend(sorted(entry_libraries))
    libraries = set()
    loader = None
    # ldd is used only on these trusted installed ELF objects. A missing SONAME
    # is a build failure, never a dependency-install or host-filesystem fallback.
    for source in roots:
        result = subprocess.run(['/usr/bin/ldd', str(source)], check=True,
                                text=True, capture_output=True, env={'LC_ALL': 'C', 'PATH': '/usr/bin:/bin'})
        if 'not found' in result.stdout:
            raise RuntimeError('GUI fixture has unresolved ELF dependencies')
        for line in result.stdout.splitlines():
            match = re.search(r'(?:=>\s*)?(/\S+)\s+\(', line)
            if match:
                library = Path(match.group(1))
                libraries.add(library)
                if library.name.startswith('ld-linux'):
                    loader = library
    for source in sorted(libraries | entry_libraries):
        relative = source.relative_to('/usr') if source.is_relative_to('/usr') else source.relative_to('/')
        copy_file(source, relative)
    if loader is None:
        raise RuntimeError('GUI fixture ELF loader is missing')
    copy_tree(Path('/usr/share/fonts/truetype/dejavu'), Path('share/fonts/truetype/dejavu'))
    copy_tree(Path('/usr/share/X11/xkb'), Path('share/X11/xkb'))
    copy_tree(Path('/usr/lib/locale/C.utf8'), Path('lib/locale/C.utf8'))
    config = destination / 'etc/fonts/fonts.conf'
    config.parent.mkdir(parents=True)
    config.write_text('<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n'
        '<fontconfig><dir prefix="relative">../../share/fonts</dir>'
        '<cachedir prefix="xdg">fontconfig</cachedir></fontconfig>\n', encoding='utf-8')
    return triplet, loader.relative_to('/usr') if loader.is_relative_to('/usr') else loader.relative_to('/')
