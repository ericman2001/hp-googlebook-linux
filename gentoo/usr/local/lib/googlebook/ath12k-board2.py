# List (and optionally extract) entries of an ath12k board-2.bin
import struct, sys, hashlib
d = open(sys.argv[1], 'rb').read()
magic = b'QCA-ATH12K-BOARD\0'
assert d.startswith(magic)
off = (len(magic) + 3) & ~3
while off + 8 <= len(d):
    ie, ln = struct.unpack_from('<II', d, off); off += 8
    body = d[off:off + ln]; off += (ln + 3) & ~3
    if ie != 0: continue
    o, names, data = 0, [], None
    while o + 8 <= len(body):
        sid, sl = struct.unpack_from('<II', body, o); o += 8
        v = body[o:o + sl]; o += (sl + 3) & ~3
        if sid == 0: names.append(v.decode())
        elif sid == 1: data = v
    for n in names:
        if len(sys.argv) < 3 or sys.argv[2] in n:
            print(n, len(data), hashlib.md5(data).hexdigest()[:8])
    if len(sys.argv) > 3 and any(sys.argv[2] == n for n in names):
        open(sys.argv[3], 'wb').write(data)
