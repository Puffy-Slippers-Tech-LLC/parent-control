"""Exact pre-secret VT6 screen gate; no files, captures, input or retries.

The caller must supply provenance-bound reference bytes and a fresh private
capture bracketed by boot/recipient observations. Pixels alone cannot establish
freshness, password recipient identity, or absence of invisible typed input.
"""

import hashlib
import struct

from owned_commands import require


REFERENCE_SHA256 = '63f310dff9a066270e8888af30ade4c65fc5e02af2604dc3bba53defff243f47'
SIZE = (1024, 768)
CURSOR = (60, 64, 6, 16)


def _pixels(raw):
    # Bound the decoder before it allocates pixel storage. GdkPixbuf is part of
    # the existing GTK/GI host prerequisites; decoding needs no graphical session.
    require(type(raw) is bytes and 24 <= len(raw) <= 8 * 1024 * 1024
            and raw[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            and struct.unpack('!II', raw[16:24]) == SIZE, 'vt6-pixels:image')
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf

    loader = GdkPixbuf.PixbufLoader.new_with_type('png')
    try:
        loader.write(raw)
    finally:
        loader.close()
    pixbuf = loader.get_pixbuf()
    require(pixbuf is not None and (pixbuf.get_width(), pixbuf.get_height()) == SIZE
            and pixbuf.get_bits_per_sample() == 8 and pixbuf.get_n_channels() == 3
            and not pixbuf.get_has_alpha(), 'vt6-pixels:format')
    data, stride = pixbuf.get_pixels(), pixbuf.get_rowstride()
    return b''.join(data[row * stride:row * stride + SIZE[0] * 3] for row in range(SIZE[1]))


def verify_prompt_pixels(screen_png, reference_png):
    """Return only a fixed proof; never export decoded pixels or decoder errors."""
    try:
        require(type(reference_png) is bytes
                and hashlib.sha256(reference_png).hexdigest() == REFERENCE_SHA256,
                'vt6-pixels:reference')
        actual, expected = _pixels(screen_png), _pixels(reference_png)
        x, y, width, height = CURSOR
        for row in range(SIZE[1]):
            start, end = row * SIZE[0] * 3, (row + 1) * SIZE[0] * 3
            if y <= row < y + height:
                left, right = start + x * 3, start + (x + width) * 3
                require(actual[start:left] == expected[start:left]
                        and actual[right:end] == expected[right:end], 'vt6-pixels:mismatch')
            else:
                require(actual[start:end] == expected[start:end], 'vt6-pixels:mismatch')
    except Exception:
        raise RuntimeError('vt6-pixels:refused') from None
    return {'vt6_prompt_pixels_verified': True}
