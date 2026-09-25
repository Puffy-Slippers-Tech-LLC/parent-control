"""Small, private Debian archives for content-identity regressions."""

import gzip
import io
import lzma
import tarfile


def tar_bytes(entries, *, mtime=0, reverse=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for entry in reversed(entries) if reverse else entries:
            values = dict(entry)
            data = values.pop('data', b'')
            info = tarfile.TarInfo(values.pop('name'))
            info.mtime = mtime
            info.mode = 0o644
            info.size = len(data)
            for key, value in values.items():
                setattr(info, key, value)
            archive.addfile(info, io.BytesIO(data) if info.isfile() else None)
    return output.getvalue()


def write_package(path, *, mtime=0, compression='gz', reverse=False,
                  payload=b'product', control=None, data=None):
    control = control if control is not None else [
        {'name': './control', 'data': b'Package: example\nVersion: 1.1\nArchitecture: all\n'
         b'Maintainer: Test <test@example.invalid>\nDescription: test\nDepends: libc6\n'},
        {'name': './postinst', 'data': b'#!/bin/sh\nexit 0\n', 'mode': 0o755},
        {'name': './conffiles', 'data': b'/etc/example.conf\n'},
        {'name': './triggers', 'data': b'interest example\n'},
        {'name': './md5sums', 'data': b'fixture-only\n'},
    ]
    data = data if data is not None else [
        {'name': '.', 'type': tarfile.DIRTYPE, 'mode': 0o755},
        {'name': './usr', 'type': tarfile.DIRTYPE, 'mode': 0o755},
        {'name': './usr/bin', 'type': tarfile.DIRTYPE, 'mode': 0o755},
        {'name': './usr/bin/example', 'data': payload, 'mode': 0o755},
        {'name': './usr/bin/alias', 'type': tarfile.SYMTYPE, 'linkname': 'example'},
    ]
    members = [('debian-binary', b'2.0\n')]
    for name, entries in (('control', control), ('data', data)):
        raw = tar_bytes(entries, mtime=mtime, reverse=reverse)
        raw = gzip.compress(raw, mtime=mtime) if compression == 'gz' else lzma.compress(raw)
        members.append((name + '.tar.' + compression, raw))
    with path.open('wb') as stream:
        stream.write(b'!<arch>\n')
        for name, raw in members:
            header = f'{name + "/":<16}{mtime:<12}{0:<6}{0:<6}{"100644":<8}{len(raw):<10}`\n'
            assert len(header) == 60
            stream.write(header.encode() + raw + (b'\n' if len(raw) % 2 else b''))
    return path
