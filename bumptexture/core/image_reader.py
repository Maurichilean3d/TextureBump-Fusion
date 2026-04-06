"""
image_reader.py
Reads a grayscale displacement map from a PNG/JPEG file using only Python stdlib
(struct + zlib for PNG, or a simple JPEG luminance decoder).
Returns normalized float values in [0.0, 1.0] and supports bilinear interpolation.
Uses Pillow if available (from Fusion's bundled Python), otherwise falls back to
a pure-stdlib PNG decoder.
"""

import os
import math
from typing import List


# ---------------------------------------------------------------------------
# Pillow / PIL import with stdlib fallback
# ---------------------------------------------------------------------------

try:
    from PIL import Image as _PIL_Image  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GrayscaleMap:
    """Holds a 2-D array of float values [0,1] with bilinear sampling."""

    def __init__(self, pixels: List[List[float]], width: int, height: int):
        self.pixels = pixels   # [row][col] in [0,1]
        self.width = width
        self.height = height

    def sample(self, u: float, v: float) -> float:
        """
        Sample the map at normalized coordinates (u,v) in [0,1] x [0,1].
        v=0 is the top of the image.  Uses bilinear interpolation.
        """
        # Wrap coordinates (tile)
        u = u % 1.0
        v = v % 1.0

        px = u * (self.width - 1)
        py = v * (self.height - 1)

        x0 = int(px)
        y0 = int(py)
        x1 = min(x0 + 1, self.width - 1)
        y1 = min(y0 + 1, self.height - 1)

        tx = px - x0
        ty = py - y0

        c00 = self.pixels[y0][x0]
        c10 = self.pixels[y0][x1]
        c01 = self.pixels[y1][x0]
        c11 = self.pixels[y1][x1]

        return (
            c00 * (1 - tx) * (1 - ty) +
            c10 * tx       * (1 - ty) +
            c01 * (1 - tx) * ty +
            c11 * tx       * ty
        )

    def gaussian_blur(self, sigma: float = 1.0) -> 'GrayscaleMap':
        """
        Apply a simple Gaussian blur for smoothing.
        Returns a new GrayscaleMap.
        """
        if sigma <= 0:
            return self

        radius = max(1, int(math.ceil(2 * sigma)))
        size = 2 * radius + 1
        kernel = [math.exp(-((i - radius) ** 2) / (2 * sigma * sigma)) for i in range(size)]
        k_sum = sum(kernel)
        kernel = [k / k_sum for k in kernel]

        # Horizontal pass
        temp = [[0.0] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                val = 0.0
                for ki, kv in enumerate(kernel):
                    xi = max(0, min(self.width - 1, x + ki - radius))
                    val += self.pixels[y][xi] * kv
                temp[y][x] = val

        # Vertical pass
        blurred = [[0.0] * self.width for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                val = 0.0
                for ki, kv in enumerate(kernel):
                    yi = max(0, min(self.height - 1, y + ki - radius))
                    val += temp[yi][x] * kv
                blurred[y][x] = val

        return GrayscaleMap(blurred, self.width, self.height)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_image(path: str, blur_sigma: float = 0.0) -> GrayscaleMap:
    """
    Load a grayscale displacement map from a PNG or JPEG file.

    Args:
        path:       Absolute path to the image file.
        blur_sigma: If > 0, apply Gaussian blur with this sigma.

    Returns:
        GrayscaleMap instance.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Displacement map not found: {path}')

    ext = os.path.splitext(path)[1].lower()

    if _PIL_AVAILABLE:
        gmap = _load_with_pillow(path)
    elif ext == '.png':
        gmap = _load_png_stdlib(path)
    else:
        raise RuntimeError(
            'Pillow (PIL) is not available and only PNG is supported without it. '
            'Please use a PNG file or install Pillow.'
        )

    if blur_sigma > 0:
        gmap = gmap.gaussian_blur(blur_sigma)

    return gmap


def load_image_from_bytes(data: bytes, blur_sigma: float = 0.0) -> GrayscaleMap:
    """Load from raw bytes (base64-decoded from palette). Falls back to stdlib PNG decoder."""
    import io
    if _PIL_AVAILABLE:
        img = _PIL_Image.open(io.BytesIO(data)).convert('L')
        w, h = img.size
        raw = list(img.getdata())
        pixels = [[raw[y * w + x] / 255.0 for x in range(w)] for y in range(h)]
        gmap = GrayscaleMap(pixels, w, h)
    else:
        gmap = _load_png_stdlib_bytes(data)

    if blur_sigma > 0:
        gmap = gmap.gaussian_blur(blur_sigma)
    return gmap


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------

def _load_with_pillow(path: str) -> GrayscaleMap:
    img = _PIL_Image.open(path).convert('L')
    w, h = img.size
    raw = list(img.getdata())
    pixels = [[raw[y * w + x] / 255.0 for x in range(w)] for y in range(h)]
    return GrayscaleMap(pixels, w, h)


def _load_png_stdlib(path: str) -> GrayscaleMap:
    """
    Minimal PNG loader using only stdlib (struct + zlib).
    Supports 8-bit grayscale and RGB images; converts RGB to luminance.
    """
    import struct
    import zlib

    with open(path, 'rb') as f:
        data = f.read()

    # Validate PNG signature
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG file')

    offset = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []

    while offset < len(data):
        length = struct.unpack_from('>I', data, offset)[0]
        chunk_type = data[offset + 4: offset + 8].decode('ascii', errors='replace')
        chunk_data = data[offset + 8: offset + 8 + length]
        offset += 12 + length

        if chunk_type == 'IHDR':
            width, height = struct.unpack_from('>II', chunk_data)
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        elif chunk_type == 'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == 'IEND':
            break

    if bit_depth != 8:
        raise ValueError(f'Unsupported PNG bit depth: {bit_depth}. Only 8-bit PNG supported.')

    raw = zlib.decompress(b''.join(idat_chunks))

    # color_type: 0=grayscale, 2=RGB, 3=indexed, 4=grayscale+alpha, 6=RGBA
    if color_type == 0:
        channels = 1
    elif color_type == 2:
        channels = 3
    elif color_type == 4:
        channels = 2
    elif color_type == 6:
        channels = 4
    else:
        raise ValueError(f'Unsupported PNG color type: {color_type}')

    stride = width * channels + 1  # +1 for filter byte per row
    pixels = []
    prev_row = bytes(stride - 1)

    for y in range(height):
        row_start = y * stride
        filter_byte = raw[row_start]
        row = bytearray(raw[row_start + 1: row_start + stride])

        # Apply PNG filter
        if filter_byte == 1:  # Sub
            for i in range(channels, len(row)):
                row[i] = (row[i] + row[i - channels]) & 0xFF
        elif filter_byte == 2:  # Up
            for i in range(len(row)):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_byte == 3:  # Average
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                row[i] = (row[i] + (a + b) // 2) & 0xFF
        elif filter_byte == 4:  # Paeth
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i - channels] if i >= channels else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF

        prev_row = bytes(row)
        row_pixels = []
        for x in range(width):
            idx = x * channels
            if color_type == 0:
                row_pixels.append(row[idx] / 255.0)
            elif color_type == 2:
                r, g, b = row[idx], row[idx + 1], row[idx + 2]
                row_pixels.append((0.299 * r + 0.587 * g + 0.114 * b) / 255.0)
            elif color_type == 4:
                row_pixels.append(row[idx] / 255.0)
            elif color_type == 6:
                r, g, b = row[idx], row[idx + 1], row[idx + 2]
                row_pixels.append((0.299 * r + 0.587 * g + 0.114 * b) / 255.0)
        pixels.append(row_pixels)

    return GrayscaleMap(pixels, width, height)


def _load_png_stdlib_bytes(data: bytes) -> GrayscaleMap:
    """
    Minimal PNG loader from raw bytes using only stdlib (struct + zlib).
    Mirrors _load_png_stdlib but accepts bytes instead of a file path.
    """
    import struct
    import zlib

    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Not a PNG file (invalid signature in bytes data)')

    offset = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []

    while offset < len(data):
        length = struct.unpack_from('>I', data, offset)[0]
        chunk_type = data[offset + 4: offset + 8].decode('ascii', errors='replace')
        chunk_data = data[offset + 8: offset + 8 + length]
        offset += 12 + length

        if chunk_type == 'IHDR':
            width, height = struct.unpack_from('>II', chunk_data)
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        elif chunk_type == 'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == 'IEND':
            break

    if bit_depth != 8:
        raise ValueError(f'Unsupported PNG bit depth: {bit_depth}. Only 8-bit PNG supported.')

    raw = zlib.decompress(b''.join(idat_chunks))

    if color_type == 0:
        channels = 1
    elif color_type == 2:
        channels = 3
    elif color_type == 4:
        channels = 2
    elif color_type == 6:
        channels = 4
    else:
        raise ValueError(f'Unsupported PNG color type: {color_type}')

    stride = width * channels + 1
    pixels = []
    prev_row = bytes(stride - 1)

    for y in range(height):
        row_start = y * stride
        filter_byte = raw[row_start]
        row = bytearray(raw[row_start + 1: row_start + stride])

        if filter_byte == 1:
            for i in range(channels, len(row)):
                row[i] = (row[i] + row[i - channels]) & 0xFF
        elif filter_byte == 2:
            for i in range(len(row)):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_byte == 3:
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                row[i] = (row[i] + (a + b) // 2) & 0xFF
        elif filter_byte == 4:
            for i in range(len(row)):
                a = row[i - channels] if i >= channels else 0
                b = prev_row[i]
                c = prev_row[i - channels] if i >= channels else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF

        prev_row = bytes(row)
        row_pixels = []
        for x in range(width):
            idx = x * channels
            if color_type == 0:
                row_pixels.append(row[idx] / 255.0)
            elif color_type == 2:
                r, g, b = row[idx], row[idx + 1], row[idx + 2]
                row_pixels.append((0.299 * r + 0.587 * g + 0.114 * b) / 255.0)
            elif color_type == 4:
                row_pixels.append(row[idx] / 255.0)
            elif color_type == 6:
                r, g, b = row[idx], row[idx + 1], row[idx + 2]
                row_pixels.append((0.299 * r + 0.587 * g + 0.114 * b) / 255.0)
        pixels.append(row_pixels)

    return GrayscaleMap(pixels, width, height)


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    elif pb <= pc:
        return b
    return c
