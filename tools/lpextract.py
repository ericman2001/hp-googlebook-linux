#!/usr/bin/env python3
"""List or extract logical partitions from an Android "super" partition (liblp).

usage: lpextract.py <super device/image>                 list partitions
       lpextract.py <super> <outdir> <name> [<name>...]  extract partitions

Reads the primary metadata of slot 0. Linear extents are copied, zero
extents are written as zeros.
"""
import os
import struct
import sys

SECTOR = 512
GEOMETRY_OFFSET = 4096          # LP_PARTITION_RESERVED_BYTES
GEOMETRY_SIZE = 4096            # LP_METADATA_GEOMETRY_SIZE (x2: primary + backup)
GEOMETRY_MAGIC = 0x616C4467
HEADER_MAGIC = 0x414C5030


def read_metadata(f):
    f.seek(GEOMETRY_OFFSET)
    g = f.read(GEOMETRY_SIZE)
    magic, _size = struct.unpack_from('<II', g)
    if magic != GEOMETRY_MAGIC:
        sys.exit('no liblp geometry found')
    max_size, slots, lbs = struct.unpack_from('<III', g, 40)

    f.seek(GEOMETRY_OFFSET + 2 * GEOMETRY_SIZE)
    m = f.read(max_size)
    magic, major, minor, header_size = struct.unpack_from('<IHHI', m)
    if magic != HEADER_MAGIC:
        sys.exit('no liblp metadata header found')
    off = 12 + 32 + 4 + 32     # past magic/versions/size, checksum, tables_size, checksum
    tables = [struct.unpack_from('<III', m, off + 12 * i) for i in range(4)]
    base = header_size

    def entries(i):
        o, n, sz = tables[i]
        return [m[base + o + k * sz: base + o + (k + 1) * sz] for k in range(n)]

    extents = [struct.unpack_from('<QIQI', e) for e in entries(1)]
    parts = []
    for e in entries(0):
        name = e[:36].split(b'\0')[0].decode()
        attrs, first, count, group = struct.unpack_from('<IIII', e, 36)
        ext = extents[first:first + count]
        parts.append((name, attrs, ext))
    return f'{major}.{minor}', slots, lbs, parts


def main():
    with open(sys.argv[1], 'rb') as f:
        version, slots, lbs, parts = read_metadata(f)
        if len(sys.argv) == 2:
            print(f'liblp {version}, {slots} metadata slots, block size {lbs}')
            for name, attrs, ext in parts:
                size = sum(n for n, *_ in ext) * SECTOR
                print(f'  {name:24s} {size / 2**20:9.1f} MiB  {len(ext)} extent(s)')
            return
        outdir, wanted = sys.argv[2], sys.argv[3:]
        os.makedirs(outdir, exist_ok=True)
        for name, attrs, ext in parts:
            if name not in wanted:
                continue
            with open(os.path.join(outdir, name + '.img'), 'wb') as out:
                for nsec, ttype, data, _src in ext:
                    if ttype == 0:          # linear
                        f.seek(data * SECTOR)
                        left = nsec * SECTOR
                        while left:
                            chunk = f.read(min(left, 1 << 20))
                            out.write(chunk)
                            left -= len(chunk)
                    else:                   # zero fill
                        out.write(b'\0' * (nsec * SECTOR))
            print('extracted', name)


if __name__ == '__main__':
    main()
