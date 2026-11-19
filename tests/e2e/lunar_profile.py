"""FIX05: guarded preparation and independent verification of supplied launchers."""
from pathlib import Path

from native_fixtures import PackagedFixtures
from private_artifacts import require
from watch_activity import operation


def guest_source():
    root = Path(__file__).parent
    source = 'import sys, types\n'
    for name in ('guest_files', 'session_control', 'flatpak_launcher'):
        source += (f'm = types.ModuleType({name!r}); sys.modules[{name!r}] = m\n'
                   f'exec({(root / (name + ".py")).read_text()!r}, m.__dict__)\n')
    return source.encode() + (root / 'lunar_profile_guest.py').read_bytes()


class LunarProfile(PackagedFixtures):
    kind = 'lunar-profile'
    guest_source = staticmethod(guest_source)

    def verify(self, *, prepare=False):
        require(not self.used, 'lunar-profile:replay')
        self.used = True
        with operation("Checking the supplied launchers and autostart settings for [Child user]"):
            first = self.read('prepare' if prepare else 'read')
            require((first.get('profile'), first.get('autostart')) in (
                ('lunar-flatpak', 'flatpak-login'), ('lunar-manual', 'desktop-login')),
                'lunar-profile:receipt')
            require(self.read('read') == first, 'lunar-profile:independent-readback')
            return {**first, 'independent_readback': True}
