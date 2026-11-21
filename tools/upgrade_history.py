"""Select genuine VM upgrade sources from the current branch's release history."""

from calendar import monthrange
from datetime import date
import json
import re
import subprocess


VERSION_PATTERN = r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)'
FROM_OPTION = '--upgrade-from='


def version_key(version):
    if not isinstance(version, str) or not re.fullmatch(VERSION_PATTERN, version):
        raise ValueError('invalid product release version')
    return tuple(map(int, version.split('.')))


def main_revision(root, *, optional=False):
    """Use the main checkout directly, or its Git ref from another checkout."""
    git = ['git', '-c', f'safe.directory={root}']
    branch = subprocess.run([*git, 'symbolic-ref', '--quiet', '--short', 'HEAD'], cwd=root,
                            capture_output=True, text=True, check=False)
    if branch.stdout.strip() == 'main':
        return None
    for ref in ('refs/remotes/origin/main', 'refs/heads/main'):
        result = subprocess.run([*git, 'rev-parse', '--verify', ref + '^{commit}'], cwd=root,
                                capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    if not optional:
        raise ValueError('upgrade matrix needs the main checkout or a local Git ref for main')
    return None


def main_input(root, path, revision):
    if revision is None:
        return (root / path).read_text()
    return subprocess.run(['git', '-c', f'safe.directory={root}', 'show', revision + ':' + path],
                          cwd=root, capture_output=True, text=True, check=True).stdout


def release_history(root, *, revision=None):
    """Return the build version and dated predecessors in descending order."""
    current = json.loads(main_input(root, 'data/app.json', revision))['version']
    current_key = version_key(current)
    text = main_input(root, 'docs/VersionHistory.md', revision)
    rows = re.findall(r'^## (.+)$', text, re.MULTILINE)
    previous = []
    last = None
    for index, row in enumerate(rows):
        heading = re.fullmatch(rf'v({VERSION_PATTERN}) (?:—|-) (\d{{4}}-\d{{2}}-\d{{2}})', row.strip())
        draft = re.fullmatch(rf'v({VERSION_PATTERN})(?: (?:—|-))?', row.strip()) if index == 0 else None
        if heading is None and draft is None:
            raise ValueError('invalid release heading in docs/VersionHistory.md: ' + row)
        version = (heading or draft)[1]
        released = date.fromisoformat(heading[2]) if heading else None
        key = version_key(version)
        if (last is not None and key >= last) or key > current_key:
            raise ValueError('docs/VersionHistory.md versions must be newest first and at most the build version')
        if released is None and key != current_key:
            raise ValueError('undated VersionHistory.md entry must match data/app.json')
        if released is not None and key < current_key:
            previous.append((version, released))
        last = key
    if not rows:
        raise ValueError('docs/VersionHistory.md contains no release headings')
    return current, previous


def supported_releases(root, package_format, *, revision=None):
    current, previous = release_history(root, revision=revision)
    return current, [(version, released) for version, released in previous
                     if package_format != 'rpm' or version_key(version) >= (1, 5)]


def upgrade_matrix(root, package_format, *, today=None, revision=None):
    current, previous = supported_releases(root, package_format, revision=revision)
    today = date.today() if today is None else today
    year, month = divmod(today.year * 12 + today.month - 3, 12)
    month += 1
    cutoff = date(year, month, min(today.day, monthrange(year, month)[1]))
    eligible = [(version, released) for version, released in previous if released <= today]
    if not eligible:
        raise ValueError(f'no eligible earlier {package_format.upper()} release in docs/VersionHistory.md for v{current}')
    recent = [version for version, released in reversed(eligible) if released >= cutoff]
    return current, recent or [eligible[0][0]]


def upgrade_from(options):
    releases = [value.removeprefix(FROM_OPTION) for value in options if value.startswith(FROM_OPTION)]
    if not releases:
        return None
    if len(releases) != 1 or not releases[0].startswith('v'):
        raise ValueError('use one --upgrade-from=vX.Y')
    version_key(releases[0][1:])
    return releases[0]


def transfer_release_tags(option_groups):
    """Select Git tags for prepared work, or for an explicit older bundle."""
    tags = set()
    for options in option_groups:
        if any(value.partition('=')[0] == '--previous-artifacts' for value in options):
            # A retained bundle can live on the VM host and predate the window.
            return None
        source = upgrade_from(options)
        if source:
            tags.add(source)
    return tags
