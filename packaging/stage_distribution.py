"""Stage the small OS-specific integration differences over the shared payload."""
import argparse
from pathlib import Path


def pam_profile(root: Path, name: str) -> list[str]:
    """Translate a shared pam-auth-update profile without copying its policy."""
    profile = (root / 'data/pam-configs' / name).read_text()
    stack = []
    kind = None
    for line in profile.splitlines():
        if line == 'Auth:':
            kind = 'auth'
        elif line == 'Account:':
            kind = 'account'
        elif not line.startswith((' ', '\t')):
            kind = None
        elif kind:
            stack.append(f'{kind} {line.strip().replace("ingroup sudo", "ingroup wheel")}')
    if not stack:
        raise ValueError(f'empty managed PAM profile: {name}')
    return stack


def pam_stack(root: Path) -> str:
    # The kiosk gate must run before the session profile's account skip rules.
    stack = pam_profile(root, 'oh-no-parent-control-kiosk-only')
    stack += pam_profile(root, 'oh-no-parent-control-session-limits')
    return '\n'.join(stack) + '\n'


def stage(source: Path, destination: Path, distribution: str):
    if distribution == 'ubuntu':
        return
    if distribution != 'fedora':
        raise ValueError('unsupported packaging distribution')
    system = destination / 'usr/lib/systemd/system/oh-no-parent-control-broker.service'
    system.write_text(system.read_text().replace('Group=sudo', 'Group=wheel'))
    agent = destination / 'usr/lib/systemd/user/oh-no-parent-control-polkit-agent.service'
    contents = agent.read_text()
    start = contents.index('# The public mate-polkit launcher')
    end = contents.index('Restart=on-failure', start)
    contents = (contents[:start] + 'Type=simple\n'
                'ExecStart=/usr/libexec/polkit-mate-authentication-agent-1\n' + contents[end:])
    agent.write_text(contents)
    pam = destination / 'usr/share/oh-no-parent-control/pam'
    pam.mkdir(parents=True, exist_ok=True)
    (pam / 'managed-stack').write_text(pam_stack(source))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', choices=('ubuntu', 'fedora'), required=True)
    parser.add_argument('--root', type=Path, required=True)
    arguments = parser.parse_args()
    stage(Path(__file__).resolve().parents[1], arguments.root, arguments.distribution)
