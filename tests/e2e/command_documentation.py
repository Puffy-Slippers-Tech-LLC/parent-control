"""Read installed command documentation from guarded SSH stdout."""

import re

from private_artifacts import require
from watch_activity import operation


BINDINGS = {
    'parent-help': ('oh-no-parent-control-parent', 'help',
                    'Administrator-facing GTK 4/libadwaita parent-control application.'),
    'station-help': ('oh-no-parent-control', 'help',
                     'Libadwaita application for the GNOME Kiosk request station.'),
    'parent-manual': ('oh-no-parent-control-parent', 'manual',
                      'configure controls for managed users'),
    'station-manual': ('oh-no-parent-control', 'manual',
                       'run the parent-control request interface'),
}


def command(binding):
    require(binding in BINDINGS, 'help:binding')
    name, kind, _ = BINDINGS[binding]
    executable = ['/usr/bin/' + name, '--help'] if kind == 'help' else [
        '/usr/bin/man', '-P', 'cat', name]
    return ['/usr/sbin/runuser', '--user', 'onpc-parent-jamie', '--',
            '/usr/bin/env', '-i', 'LANG=C.UTF-8', 'PATH=/usr/bin:/bin',
            'MANWIDTH=1000', 'GROFF_NO_SGR=1', *executable]


def validate(binding, raw):
    """Check the command's own bounded stdout, independent of GUI layout."""
    require(binding in BINDINGS and type(raw) is bytes and 0 < len(raw) <= 65536,
            'help:output-bound')
    try:
        value = raw.decode('utf-8')
    except UnicodeDecodeError:
        require(False, 'help:output-encoding')
    require('\x00' not in value and '\x1b' not in value, 'help:output-format')
    # man can use overstrikes for bold text when stdout is a pipe.
    value = re.sub(r'.\x08', '', value)
    name, kind, identity = BINDINGS[binding]
    normalized = ' '.join(re.sub(r'[\u00ad\u2010]\s+', '', value).split())
    if kind == 'help':
        require(bool(re.search(r'(?im)^usage:\s+' + re.escape(name) + r'\b', value))
                and identity in normalized and '--help' in value
                and 'show this help message and exit' in normalized,
                'help:content-' + binding)
    else:
        require(name.upper() + '(1)' in normalized and identity in normalized
                and all(re.search(r'(?m)^\s*' + section + r'\s*$', value)
                        for section in ('NAME', 'SYNOPSIS', 'DESCRIPTION')),
                'help:content-' + binding)
    return {'operation': binding, 'outcome': 'passed', 'interface': 'SSH stdout'}


def observe(transport, binding):
    require(binding in BINDINGS, 'help:binding')
    with operation('Reading installed ' + binding.replace('-', ' ')):
        received = 0

        def bound(chunk):
            nonlocal received
            received += len(chunk)
            require(received <= 65536, 'help:output-bound')

        raw = transport.call(command(binding), timeout=45, on_output=bound)
        return validate(binding, raw)
