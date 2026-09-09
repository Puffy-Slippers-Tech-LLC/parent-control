"""Synthetic PNG headers for collector validation, not visual acceptance."""

import struct

def png(directory, name='smoke-1.png', width=1024, height=768, suffix=b'fixture'):
    results = directory / 'testresults'
    results.mkdir(exist_ok=True)
    path = results / name
    path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' + struct.pack('!II', width, height) + suffix)
    return path
