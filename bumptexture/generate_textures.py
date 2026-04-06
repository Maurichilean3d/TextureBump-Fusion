"""
generate_textures.py
Run this script once to generate the built-in grayscale PNG displacement maps
in resources/textures/ using only Python stdlib (no Pillow required).
Run from the add-in directory: python generate_textures.py
"""

import os
import math
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(__file__), 'resources', 'textures')
SIZE = 256  # pixels per texture


def write_png(path: str, pixels: list, width: int, height: int):
    """Write a grayscale 8-bit PNG using stdlib."""
    def pack_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)

    raw = b''
    for row in pixels:
        raw += b'\x00' + bytes([max(0, min(255, int(v))) for v in row])

    compressed = zlib.compress(raw, 9)

    signature = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)
    ihdr = pack_chunk(b'IHDR', ihdr_data)
    idat = pack_chunk(b'IDAT', compressed)
    iend = pack_chunk(b'IEND', b'')

    with open(path, 'wb') as f:
        f.write(signature + ihdr + idat + iend)


def make_crystal(w, h):
    import random
    random.seed(42)
    N = 30
    pts = [(random.uniform(0, w), random.uniform(0, h)) for _ in range(N)]
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            d1, d2 = float('inf'), float('inf')
            for px, py in pts:
                d = math.hypot(x - px, y - py)
                if d < d1:
                    d2, d1 = d1, d
                elif d < d2:
                    d2 = d
            v = min(255, int((d2 - d1) * 10))
            row.append(v)
        pixels.append(row)
    return pixels


def make_hexagonal(w, h):
    size = 16
    sq3 = math.sqrt(3)
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            col = int(x / (size * 1.5))
            row_i = int(y / (size * sq3 / 2))
            cx = col * size * 1.5
            cy = row_i * size * sq3 / 2
            if col % 2 == 1:
                cy += size * sq3 / 4
            dx, dy = x - cx, y - cy
            # dist to hex center
            d = math.hypot(dx * 0.5, dy * (1 / sq3))
            v = max(0, min(255, int((1 - d / size) * 255)))
            row.append(v)
        pixels.append(row)
    return pixels


def make_waves(w, h):
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            v = (math.sin((x + y) * 0.12) * 0.5 +
                 math.sin(x * 0.08) * 0.3 +
                 math.sin(y * 0.15) * 0.2 + 1.0) * 0.5
            row.append(int(v * 255))
        pixels.append(row)
    return pixels


def make_dots(w, h):
    step = 16
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            cx = round(x / step) * step
            cy = round(y / step) * step
            d = math.hypot(x - cx, y - cy)
            v = 255 if d < step * 0.38 else 0
            row.append(v)
        pixels.append(row)
    return pixels


def make_pyramids(w, h):
    step = 24
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            lx = ((x % step) + step) % step
            ly = ((y % step) + step) % step
            v = max(0, 1 - max(abs(lx - step / 2), abs(ly - step / 2)) / (step / 2))
            row.append(int(v * 255))
        pixels.append(row)
    return pixels


def make_scales(w, h):
    r = 18
    row_h = int(r * 0.9)
    col_w = int(r * 1.8)
    canvas = [[0] * w for _ in range(h)]
    for row in range(h // row_h + 2):
        for col in range(w // col_w + 2):
            ox = 0 if row % 2 == 0 else col_w // 2
            cx = col * col_w + ox
            cy = row * row_h
            for dy in range(-r - 2, r + 2):
                for dx in range(-r - 2, r + 2):
                    px, py = cx + dx, cy + dy
                    if 0 <= px < w and 0 <= py < h:
                        d = math.hypot(dx, dy)
                        if d <= r:
                            v = int((1 - d / r) * 255)
                            canvas[py][px] = max(canvas[py][px], v)
    return canvas


def make_knurl(w, h):
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            a = math.sin((x - y) * 0.28) * 0.5 + 0.5
            b = math.sin((x + y) * 0.28) * 0.5 + 0.5
            v = int(min(a, b) * 255)
            row.append(v)
        pixels.append(row)
    return pixels


def make_wood(w, h):
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            warp = math.sin(x * 0.05 + y * 0.01) * 8
            ring = math.sin(math.hypot(x - w / 2, y - h / 2 + warp) * 0.3) * 0.5 + 0.5
            row.append(int(ring * 255))
        pixels.append(row)
    return pixels


def make_leather(w, h):
    def noise(x, y):
        return (math.sin(x * 1.5 + math.cos(y * 2.3)) * 0.5 +
                math.sin(y * 1.1 + math.cos(x * 3.7)) * 0.3 +
                math.sin((x + y) * 0.7) * 0.2) * 0.5 + 0.5

    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            n = noise(x * 0.07, y * 0.07) * 0.6 + noise(x * 0.18, y * 0.18) * 0.4
            row.append(int(n * 255))
        pixels.append(row)
    return pixels


def make_diamond(w, h):
    step = 20
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            lx = ((x % step) + step) % step - step / 2
            ly = ((y % step) + step) % step - step / 2
            d = (abs(lx) + abs(ly)) / step
            v = max(0, int((1 - min(1.0, d * 2)) * 255))
            row.append(v)
        pixels.append(row)
    return pixels


GENERATORS = {
    'crystal.png':    make_crystal,
    'hexagonal.png':  make_hexagonal,
    'waves.png':      make_waves,
    'dots.png':       make_dots,
    'pyramids.png':   make_pyramids,
    'scales.png':     make_scales,
    'knurl.png':      make_knurl,
    'wood.png':       make_wood,
    'leather.png':    make_leather,
    'diamond.png':    make_diamond,
}

if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    for filename, fn in GENERATORS.items():
        path = os.path.join(OUT_DIR, filename)
        print(f'Generating {filename}...')
        pixels = fn(SIZE, SIZE)
        write_png(path, pixels, SIZE, SIZE)
        print(f'  -> {path}')
    print('Done! All textures generated.')
