#!/usr/bin/env python3
from __future__ import annotations

import binascii
import struct
import sys
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Input is not a PNG file")

    chunks = []
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        crc_end = end + 4
        if crc_end > len(data):
            raise ValueError("Truncated PNG chunk data")
        chunks.append((chunk_type, data[start:end]))
        offset = crc_end
        if chunk_type == b"IEND":
            break
    return chunks


def write_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = binascii.crc32(chunk_type)
    crc = binascii.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def paeth(left: int, up: int, upper_left: int) -> int:
    p = left + up - upper_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - upper_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return upper_left


def unfilter_scanline(filter_type: int, current: bytes, previous: bytes, bytes_per_pixel: int) -> bytearray:
    out = bytearray(current)
    for index, value in enumerate(out):
        left = out[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        up = previous[index] if previous else 0
        upper_left = previous[index - bytes_per_pixel] if previous and index >= bytes_per_pixel else 0
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = paeth(left, up, upper_left)
        else:
            raise ValueError(f"Unsupported PNG filter: {filter_type}")
        out[index] = (value + predictor) & 0xFF
    return out


def strip_alpha(input_path: Path, output_path: Path) -> None:
    chunks = read_chunks(input_path.read_bytes())
    ihdr = next(payload for chunk_type, payload in chunks if chunk_type == b"IHDR")
    width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", ihdr)
    if bit_depth != 8 or compression != 0 or filter_method != 0 or interlace != 0:
        raise ValueError("Only 8-bit non-interlaced PNG files are supported")

    idat = b"".join(payload for chunk_type, payload in chunks if chunk_type == b"IDAT")
    raw = zlib.decompress(idat)

    if color_type == 2:
        output_path.write_bytes(input_path.read_bytes())
        return
    if color_type != 6:
        raise ValueError(f"Unsupported PNG color type: {color_type}")

    input_channels = 4
    input_stride = width * input_channels
    output_rows = []
    offset = 0
    previous = bytearray(input_stride)
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        filtered = raw[offset : offset + input_stride]
        offset += input_stride
        scanline = unfilter_scanline(filter_type, filtered, previous, input_channels)
        previous = scanline
        rgb = bytearray()
        for pixel in range(0, len(scanline), 4):
            rgb.extend(scanline[pixel : pixel + 3])
        output_rows.append(b"\x00" + bytes(rgb))

    rgb_ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressed = zlib.compress(b"".join(output_rows), level=9)
    output = (
        PNG_SIGNATURE
        + write_chunk(b"IHDR", rgb_ihdr)
        + write_chunk(b"IDAT", compressed)
        + write_chunk(b"IEND", b"")
    )
    output_path.write_bytes(output)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: strip_png_alpha.py input.png output.png", file=sys.stderr)
        return 2
    strip_alpha(Path(sys.argv[1]), Path(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
