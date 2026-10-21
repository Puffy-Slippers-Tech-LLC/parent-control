"""Finite native fixture identities shared by builder and guarded preparation.

A/H/S/N are later policy roles. Preparation leaves all four Allowed.
"""
import hashlib
import re
import stat

PREFIX = '/opt/onpc-test-fixtures/Applications'
NATIVE_POLICY_PATHS = ('/etc/fapolicyd/rules.d/69-onpc-baseline-runtime.rules',
                       '/etc/fapolicyd/rules.d/89-onpc-baseline-fixtures.rules')
NATIVE_RULE_MANIFEST = '[%{FILENAMES}\t%{FILEDIGESTS}\t%{FILEMODES}\t%{FILEUSERNAME}\t%{FILEGROUPNAME}\t%{FILEFLAGS}\n]'
NATIVE_STOCK_RULE_NAMES = (
    '10-languages.rules', '20-dracut.rules', '21-updaters.rules', '30-patterns.rules',
    '40-bad-elf.rules', '41-shared-obj.rules', '42-trusted-elf.rules',
    '70-trusted-lang.rules', '72-shell.rules', '90-deny-execute.rules', '95-allow-open.rules')
ASSETS = (
    ('A', 'Exact Fixture.AppImage', 'ONPC Allowed Fixture', 'Exact native catalogue fixture', 'precise'),
    ('H', 'Path With Spaces.AppImage', 'ONPC Hard Fixture', 'Whitespace native catalogue fixture', 'precise'),
    ('S', 'Versioned/Lunar Client-3.7.17.AppImage', 'ONPC Soft Fixture', 'Versioned native catalogue fixture', 'pattern'),
    ('N', 'PrismLauncher.AppImage', 'ONPC Nonmatching Fixture', 'Unrelated native catalogue fixture', 'precise'),
)
GUI_FILES = ('onpc-test-gui.py', 'gtk_automation.py')
# Keep the earlier generated/baseline S file as an untrusted compatibility
# control. The active launcher and policy pattern use only Versioned.
LEGACY_S = 'Lunar Client-3.7.17.AppImage'
TRUSTED_NATIVE = {
    'trusted-hard': ('/opt/onpc-test-fixtures-trusted-hard/native-fixture', 'TrustedHard'),
    'trusted-soft': ('/opt/onpc-test-fixtures-trusted-soft/native-fixture', 'TrustedSoft'),
}
ACTIVITY_PREFIX = '/opt/onpc-test-fixtures-activity'
ACTIVITY_EXECUTABLE = ACTIVITY_PREFIX + '/native-fixture'


def trusted_file_modes():
    """Exact root-owned admitted inputs; existing policy controls stay untrusted."""
    return {path: 0o755 for path, _ in TRUSTED_NATIVE.values()} | {
        ACTIVITY_EXECUTABLE: 0o755,
        **{ACTIVITY_PREFIX + '/' + name: 0o644 for name in GUI_FILES}}


def activity_sources():
    return ('fixtures/native/identity-trusted-activity',
            'fixtures/native/onpc-test-gui.py', 'fixtures/native/gtk_automation.py')


def desktop_id(role):
    assert role in ('A', 'H', 'S', 'N')
    return 'com.puffyslippers.ONPCTest.' + role + '.desktop'


def desktop_entry(asset):
    role, filename, name, description, match = asset
    return ('[Desktop Entry]\nType=Application\n' + f'Name={name}\nComment={description}\n'
            'Icon=applications-system\n' + f'Exec="{PREFIX}/{filename}"\nTerminal=false\n')


def executable_path(role, *, prefix=None):
    """Active absolute executable, independent of catalogue/order indexing."""
    filename, = (asset[1] for asset in ASSETS if asset[0] == role)
    return (PREFIX if prefix is None else prefix) + '/' + filename


def version_pattern(*, prefix=None):
    return (PREFIX if prefix is None else prefix) + '/Versioned/Lunar Client-*.AppImage'


def legacy_executable_paths(*, prefix=None):
    return ((PREFIX if prefix is None else prefix) + '/' + LEGACY_S,)


def executable_sources():
    return tuple('fixtures/image-root' + executable_path(asset[0]) for asset in ASSETS)


def gui_sources():
    """Both adjacent runtimes are exact source keys, including duplicate bytes."""
    return tuple('fixtures/image-root' + PREFIX + '/' + directory + filename
                 for directory in ('', 'Versioned/') for filename in GUI_FILES)


def launcher_sources():
    return tuple('fixtures/native-launchers/' + desktop_id(asset[0]) for asset in ASSETS)


def runtime_sources():
    return executable_sources() + gui_sources()


def sources():
    """Active source keys relative to verified artifact root; never image-root/home."""
    return runtime_sources() + launcher_sources()


def source_destinations(home, *, prefix=None):
    """Exact source-key -> (guest path, mode), preserving nested runtime paths."""
    prefix = PREFIX if prefix is None else prefix
    image_prefix = 'fixtures/image-root' + PREFIX + '/'
    return {source: (prefix + '/' + source.removeprefix(image_prefix),
                     0o755 if source in executable_sources() else 0o644)
            for source in runtime_sources()} | {
        source: (home + '/.local/share/applications/' + source.rsplit('/', 1)[1], 0o644)
        for source in launcher_sources()}


def riley_grid_sources():
    """Same shared executables/GUI and only Riley's declared A launcher."""
    return (*runtime_sources(), launcher_sources()[0])


def native_policy_files(expected, child_uids):
    """Closed Fedora baseline admissions; product denials precede these rules.

    Only the two prepared children may open the two shared Python runtimes or
    execute the four active native payloads. These inputs remain untrusted.
    Source keys bind both copies of each runtime to identical expected bytes.
    """
    required = runtime_sources()
    if (type(expected) is not dict or set(expected) not in
            (set(required), set(sources()), set(riley_grid_sources()))
            or any(type(expected[key]) is not str or len(expected[key]) != 64
                   or any(c not in '0123456789abcdef' for c in expected[key])
                   for key in required)
            or type(child_uids) is not tuple or len(child_uids) != 2
            or any(type(uid) is not int or not 1000 <= uid < 2 ** 32 for uid in child_uids)
            or len(set(child_uids)) != 2):
        raise ValueError('native:baseline-policy-inputs')
    executables = [expected[key] for key in executable_sources()]
    gui = [expected[key] for key in gui_sources()]
    if (len(set(executables)) != 4 or gui[:2] != gui[2:]
            or len(set(gui)) != 2 or set(gui) & set(executables)):
        raise ValueError('native:baseline-policy-inputs')
    subject = ','.join(str(uid) for uid in sorted(child_uids))
    def rules(permission, hashes):
        return ('# Finite reusable fixture admission; inputs remain untrusted.\n' + ''.join(
            f'allow perm={permission} uid={subject} : sha256hash={digest} trust=0\n'
            for digest in hashes)).encode('ascii')
    return dict(zip(NATIVE_POLICY_PATHS, (rules('open', gui[:2]),
                                         rules('execute', executables))))


def native_stock_rules(manifest, read):
    """Recognize RPM-owned known-libs sources before admitting any fixtures.

    ``read`` pins a regular root-owned file with the supplied native mode and
    group. SHA256 matches the package algorithm already required by preparation.
    Never infer stock policy from mutable rules.d files or their existing bytes.
    """
    if type(manifest) is not str or not 0 < len(manifest.encode()) <= 2 * 1024 * 1024:
        raise ValueError('native:stock-policy-manifest')
    samples = {}
    for row in manifest.splitlines():
        fields = row.split('\t')
        if len(fields) != 6:
            raise ValueError('native:stock-policy-manifest')
        path, digest, mode, owner, group, flags = fields
        if not path.startswith('/usr/share/fapolicyd/') or int(flags) & 64:
            continue
        if path in samples:
            raise ValueError('native:stock-policy-manifest')
        samples[path] = (digest, int(mode), owner, group)
    def shipped(path):
        digest, mode, owner, group = samples[path]
        if (owner != 'root' or group not in ('root', 'fapolicyd')
                or not stat.S_ISREG(mode) or mode & 0o022
                or re.fullmatch('[0-9a-f]{64}', digest) is None):
            raise ValueError('native:stock-policy-source')
        data = read(path, stat.S_IMODE(mode), group)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('native:stock-policy-source')
        return data
    names = shipped('/usr/share/fapolicyd/default-ruleset.known-libs').decode('ascii').splitlines()
    # Pin the qualified Fedora 44 stock inventory, including the concrete
    # language and execute-denial boundaries. Do not silently extend fixture
    # admission across newly introduced native policy. These fixed names also
    # have identical lexical and native sort -V ordering around our layers.
    if tuple(names) != NATIVE_STOCK_RULE_NAMES:
        raise ValueError('native:stock-policy-inventory')
    return {'/etc/fapolicyd/rules.d/' + name:
            (shipped('/usr/share/fapolicyd/sample-rules/' + name),
             stat.S_IMODE(samples['/usr/share/fapolicyd/sample-rules/' + name][1]))
            for name in names}
