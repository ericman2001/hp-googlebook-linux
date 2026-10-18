#!/usr/bin/env python3
"""Graft depthcharge's boot-time DT additions onto a freshly built DTB.

usage: dtgraft.py <running.dtb> <new.dtb> <out.dtb>

<running.dtb> is /sys/firmware/fdt from a kernel booted by depthcharge
(or kexec'd from one). Copied from it into <new.dtb>:
  /memory, /lpddr-channel*, /firmware/coreboot, /firmware/chromeos, and
  every /reserved-memory child that <new.dtb> doesn't have (ramoops,
  coreboot regions, pKVM buffers...).
The result is suitable for kexec --dtb.
"""
import struct
import sys

FDT_MAGIC = 0xd00dfeed
BEGIN_NODE, END_NODE, PROP, NOP, END = 1, 2, 3, 4, 9


class Node:
    def __init__(self, name):
        self.name = name
        self.props = []      # [(name, bytes)], order preserved
        self.children = []   # [Node]

    def child(self, name):
        return next((c for c in self.children if c.name == name), None)

    def find(self, path):
        node = self
        for part in [p for p in path.split('/') if p]:
            node = node.child(part)
            if node is None:
                return None
        return node


def load(path):
    d = open(path, 'rb').read()
    (magic, _total, off_struct, off_strings, off_rsv, _ver, _last, boot_cpu,
     size_strings, size_struct) = struct.unpack_from('>10I', d)
    assert magic == FDT_MAGIC, f'{path}: not a DTB'
    rsv = []
    o = off_rsv
    while True:
        addr, size = struct.unpack_from('>QQ', d, o)
        o += 16
        if addr == 0 and size == 0:
            break
        rsv.append((addr, size))
    strings = d[off_strings:off_strings + size_strings]
    o = off_struct
    stack, root = [], None
    while True:
        tok, = struct.unpack_from('>I', d, o)
        o += 4
        if tok == BEGIN_NODE:
            end = d.index(b'\0', o)
            node = Node(d[o:end].decode())
            o = (end + 1 + 3) & ~3
            if stack:
                stack[-1].children.append(node)
            else:
                root = node
            stack.append(node)
        elif tok == END_NODE:
            stack.pop()
        elif tok == PROP:
            ln, nameoff = struct.unpack_from('>II', d, o)
            o += 8
            name = strings[nameoff:strings.index(b'\0', nameoff)].decode()
            stack[-1].props.append((name, d[o:o + ln]))
            o = (o + ln + 3) & ~3
        elif tok == NOP:
            continue
        elif tok == END:
            break
        else:
            sys.exit(f'{path}: bad token {tok:#x}')
    return root, rsv, boot_cpu


def save(path, root, rsv, boot_cpu):
    strings, offsets, st = bytearray(), {}, bytearray()

    def stroff(name):
        if name not in offsets:
            offsets[name] = len(strings)
            strings.extend(name.encode() + b'\0')
        return offsets[name]

    def emit(node):
        st.extend(struct.pack('>I', BEGIN_NODE))
        st.extend(node.name.encode() + b'\0')
        st.extend(b'\0' * (-len(st) % 4))
        for name, val in node.props:
            st.extend(struct.pack('>III', PROP, len(val), stroff(name)))
            st.extend(val)
            st.extend(b'\0' * (-len(st) % 4))
        for c in node.children:
            emit(c)
        st.extend(struct.pack('>I', END_NODE))

    emit(root)
    st.extend(struct.pack('>I', END))
    rsvmap = b''.join(struct.pack('>QQ', a, s) for a, s in rsv) + b'\0' * 16
    off_rsv = 40
    off_struct = off_rsv + len(rsvmap)
    off_strings = off_struct + len(st)
    total = off_strings + len(strings)
    hdr = struct.pack('>10I', FDT_MAGIC, total, off_struct, off_strings, off_rsv,
                      17, 16, boot_cpu, len(strings), len(st))
    open(path, 'wb').write(hdr + rsvmap + bytes(st) + bytes(strings))


def strip_phandles(node):
    node.props = [p for p in node.props if p[0] not in ('phandle', 'linux,phandle')]
    for c in node.children:
        strip_phandles(c)


def graft(src_parent, dst_parent, name):
    src = src_parent.child(name)
    if src is None:
        return False
    dst_parent.children = [c for c in dst_parent.children if c.name != name]
    strip_phandles(src)
    dst_parent.children.append(src)
    return True


def main():
    run, _, _ = load(sys.argv[1])
    new, rsv, boot_cpu = load(sys.argv[2])
    done = []

    for c in list(run.children):
        if c.name == 'memory' or c.name.startswith('lpddr-channel'):
            graft(run, new, c.name) and done.append('/' + c.name)
    # depthcharge replaces the DTB's memory@... placeholder with /memory
    if run.child('memory'):
        new.children = [c for c in new.children if not c.name.startswith('memory@')]

    for name in ('coreboot', 'chromeos'):
        if new.find('/firmware') and graft(run.find('/firmware'), new.find('/firmware'), name):
            done.append('/firmware/' + name)

    rr, nr = run.find('/reserved-memory'), new.find('/reserved-memory')
    for c in list(rr.children):
        if nr.child(c.name) is None:
            graft(rr, nr, c.name)
            done.append('/reserved-memory/' + c.name)

    save(sys.argv[3], new, rsv, boot_cpu)
    print('grafted:', ' '.join(done))


if __name__ == '__main__':
    main()
