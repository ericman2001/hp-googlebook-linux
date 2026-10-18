#!/usr/bin/env python3
"""Extract a file from a coreboot CBFS region of an AP firmware image.

usage: cbfs_extract.py <ap.bin> <fmap-region> <cbfs-name> <out>
Payloads are written as <out>/segN.bin (decompressed); other files to <out>.
"""
import lzma, os, struct, subprocess, sys

ap, region, want, out = sys.argv[1:5]
d = open(ap, 'rb').read()
i = d.find(b'__FMAP__\x01\x01')
nareas = struct.unpack_from('<H', d, i + 54)[0]
for k in range(nareas):
    off, sz, nm, _ = struct.unpack_from('<II32sH', d, i + 56 + k * 42)
    if nm.split(b'\0')[0].decode() == region:
        break
else:
    sys.exit(f'no FMAP region {region}')


def decompress(raw, comp, size):
    if comp == 1:
        return lzma.decompress(raw, format=lzma.FORMAT_ALONE)
    if comp == 2:
        return subprocess.run(['lz4', '-d', '-c'], input=raw, capture_output=True).stdout
    return raw


p, end = off, off + sz
while p < end - 24:
    if d[p:p + 8] != b'LARCHIVE':
        p += 64
        continue
    ln, ty, attr, hoff = struct.unpack_from('>IIII', d, p + 8)
    name = d[p + 24:p + hoff].split(b'\0')[0].decode(errors='replace')
    if name == want:
        body = d[p + hoff:p + hoff + ln]
        if ty == 0x20:  # payload: list of segments ending with ENTRY
            os.makedirs(out, exist_ok=True)
            q = j = 0
            while True:
                t, c, o, la, l, ml = struct.unpack_from('>IIIQII', body, q)
                q += 28
                if t == 0x454E5452:  # 'ENTR'
                    break
                seg = decompress(body[o:o + l], c, ml)
                open(f'{out}/seg{j}.bin', 'wb').write(seg)
                print(f'seg{j}: load {la:#x} {len(seg)} bytes')
                j += 1
        else:
            comp = 0
            a = p + attr if attr else p + hoff
            while a < p + hoff:
                tag, alen = struct.unpack_from('>II', d, a)
                if tag == 0x42435A4C:  # compression attribute
                    comp = struct.unpack_from('>I', d, a + 8)[0]
                if not alen:
                    break
                a += alen
            open(out, 'wb').write(decompress(body, comp, 0))
            print(f'wrote {out}')
        break
    p = (p + hoff + ln + 63) & ~63
else:
    sys.exit(f'{want} not found in {region}')
