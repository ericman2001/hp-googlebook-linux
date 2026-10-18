#!/usr/bin/env python3
"""Write the raw arm64 Image contained in an installed kernel image.

usage: unpack-kernel.py <vmlinuz> <Image out>

Accepts a raw Image, a gzip-compressed Image, or an EFI zboot image
(CONFIG_EFI_ZBOOT: "MZ" PE stub with a "zimg" payload, gzip/zstd/lzma/xz).
"""
import gzip
import lzma
import struct
import subprocess
import sys

ARM64_MAGIC = b'ARM\x64'


def decompress(data, kind):
    if kind == 'gzip':
        return gzip.decompress(data)
    if kind in ('lzma', 'xz'):
        return lzma.decompress(data)
    if kind == 'zstd' or kind == 'zstd22':
        return subprocess.run(['zstd', '-dc'], input=data, capture_output=True, check=True).stdout
    sys.exit(f'unsupported zboot compression {kind!r}')


def main():
    data = open(sys.argv[1], 'rb').read()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    elif data[:2] == b'MZ' and data[4:8] == b'zimg':
        off, size = struct.unpack_from('<II', data, 8)
        kind = data[24:56].split(b'\0')[0].decode()
        data = decompress(data[off:off + size], kind)
    if data[56:60] != ARM64_MAGIC:
        sys.exit(f'{sys.argv[1]}: not an arm64 Image')
    open(sys.argv[2], 'wb').write(data)


if __name__ == '__main__':
    main()
