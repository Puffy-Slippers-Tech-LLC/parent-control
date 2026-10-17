"""Build and read the fixed lava treatments without a runtime pixel scan.

The build reader deliberately supports only our noninterlaced, 8-bit RGB/RGBA
PNG artwork. It needs only Python's standard library on both package builders.
"""

import hashlib
from pathlib import Path
import struct
import zlib

PORTAL_BOUNDS = (480 / 1672, 36 / 941, 1090 / 1672, 906 / 941)
MAGIC = b'ONPCLAVA\x01'
HEADER = struct.Struct('>9s32sIII')
MAX_PIXELS = 4096 * 4096


def crop(width, height):
    return tuple(round(fraction * dimension) for fraction, dimension
                 in zip(PORTAL_BOUNDS, (width, height) * 2))


def treatments(width, height, pixels, stride):
    left, top, right, bottom = crop(width, height)
    crop_width, crop_height = right - left, bottom - top
    cool = bytearray(crop_width * crop_height * 4)
    hot = bytearray(len(cool))
    selected = 0
    for y in range(top, bottom):
        for x in range(left, right):
            source = y * stride + x * 4
            red, green, blue, alpha = pixels[source:source + 4]
            warmth = min(1.0, max(0.0, (red - blue - 45) / 100))
            warmth *= min(1.0, max(0.0, (green - blue - 8) / 60))
            warmth *= min(1.0, max(0.0, (red - 110) / 100))
            opacity = round(alpha * warmth)
            if not opacity:
                continue
            target = ((y - top) * crop_width + x - left) * 4
            cool[target:target + 4] = bytes((
                round(red * 0.85), round(green * 0.55), round(blue * 0.5), opacity,
            ))
            hot[target:target + 4] = bytes((
                min(255, round(red * 1.08 + 12)),
                min(255, round(green * 1.4 + 28)),
                min(255, round(blue * 0.8 + 5)), opacity,
            ))
            selected += 1
    return bytes(cool), bytes(hot), selected


def inflate(data, size):
    decoder = zlib.decompressobj()
    result = decoder.decompress(data, size + 1)
    if (len(result) != size or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail):
        raise ValueError('invalid artwork payload length')
    return result


def read_png(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('invalid artwork PNG')
    offset, compressed, header, ended = 8, bytearray(), None, False
    while offset < len(data):
        if len(data) - offset < 12:
            raise ValueError('truncated PNG chunk')
        length, kind = struct.unpack_from('>I4s', data, offset)
        end = offset + 12 + length
        if end > len(data):
            raise ValueError('truncated PNG chunk')
        payload = data[offset + 8:end - 4]
        checksum, = struct.unpack_from('>I', data, end - 4)
        if zlib.crc32(kind + payload) != checksum:
            raise ValueError('invalid PNG checksum')
        if kind == b'IHDR':
            if header is not None or offset != 8 or length != 13:
                raise ValueError('invalid PNG header')
            header = struct.unpack('>IIBBBBB', payload)
        elif kind == b'IDAT':
            compressed.extend(payload)
        elif kind == b'IEND':
            if length or end != len(data):
                raise ValueError('invalid PNG end')
            ended = True
        elif kind in (b'iCCP', b'gAMA', b'cHRM', b'cICP', b'tRNS'):
            # GDK can color-convert these. Refuse rather than silently generate
            # treatments from a different color space than TextureDownloader.
            raise ValueError('unsupported artwork color profile')
        elif kind == b'sRGB':
            if payload != b'\x00':
                raise ValueError('unsupported artwork rendering intent')
        elif not kind[0] & 32:
            raise ValueError('unsupported critical PNG chunk')
        offset = end
    if header is None or not ended:
        raise ValueError('incomplete artwork PNG')
    width, height, depth, color, compression, filtering, interlace = header
    if (not 0 < width * height <= MAX_PIXELS or depth != 8 or color not in (2, 6)
            or (compression, filtering, interlace) != (0, 0, 0)):
        raise ValueError('unsupported artwork PNG format')
    channels = 3 if color == 2 else 4
    stride = width * channels
    raw = inflate(compressed, (stride + 1) * height)
    pixels, previous = bytearray(), bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        if method not in range(5):
            raise ValueError('unsupported PNG row filter')
        for x in range(stride):
            a = row[x - channels] if x >= channels else 0
            b = previous[x]
            c = previous[x - channels] if x >= channels else 0
            if method == 4:
                p = a + b - c
                distances = (abs(p - a), abs(p - b), abs(p - c))
                predictor = (a, b, c)[distances.index(min(distances))]
            else:
                predictor = (0, a, b, (a + b) // 2)[method]
            row[x] = (row[x] + predictor) & 255
        if channels == 4:
            pixels.extend(row)
        else:
            for x in range(0, stride, 3):
                pixels.extend(row[x:x + 3])
                pixels.append(255)
        previous = row
    return width, height, bytes(pixels)


def build(source, destination):
    data = Path(source).read_bytes()
    width, height, pixels = read_png(data)
    cool, hot, selected = treatments(width, height, pixels, width * 4)
    if not selected:
        raise ValueError('artwork has no lava pixels')
    Path(destination).write_bytes(HEADER.pack(
        MAGIC, hashlib.sha256(data).digest(), width, height, selected,
    ) + zlib.compress(cool + hot, 9))


def load(path, source, width, height):
    data = Path(path).read_bytes()
    magic, digest, cached_width, cached_height, selected = HEADER.unpack_from(data)
    if (magic != MAGIC or (cached_width, cached_height) != (width, height)
            or not 0 < width * height <= MAX_PIXELS
            or digest != hashlib.sha256(Path(source).read_bytes()).digest()):
        raise ValueError('stale lava artwork')
    left, top, right, bottom = crop(width, height)
    size = (right - left) * (bottom - top) * 4
    if not 0 < selected <= size // 4:
        raise ValueError('invalid lava pixel count')
    pixels = inflate(data[HEADER.size:], size * 2)
    return pixels[:size], pixels[size:], selected


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    build(arguments.source, arguments.output)
