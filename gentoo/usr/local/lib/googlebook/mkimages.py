#!/usr/bin/env python3
"""Pack Android boot images the way the Googlebook's depthcharge expects them.

Formats follow AOSP mkbootimg (boot/init_boot header v4, vendor_boot v4)
and the DT table format used by the stock dtbo partition.

  mkimages.py boot        --kernel Image.lz4 -o boot.img
  mkimages.py init_boot   --ramdisk ramdisk.cpio -o init_boot.img
  mkimages.py vendor_boot --cmdline '...' [--ramdisk r.cpio] [--bootconfig f] -o vendor_boot.img
  mkimages.py dtbo        --base base.dtb [--overlay o.dtbo ...] -o dtbo.img

Header fields that are not ours to choose (load addresses, os_version,
DT table entry ids) are copied from the stock images.
"""
import argparse
import struct
import subprocess
import sys

BOOT_PAGE = 4096
VENDOR_PAGE = 2048
DTBO_PAGE = 2048

# Stock values, from stock/boot_a.img, init_boot_a.img and vendor_boot_a.img
INIT_BOOT_OS_VERSION = 0x220001A9
VENDOR_KERNEL_ADDR = 0x10008000
VENDOR_RAMDISK_ADDR = 0x11000000
VENDOR_TAGS_ADDR = 0x10000100
VENDOR_DTB_ADDR = 0x11F00000

# Stock DT table entry fields after dt_size/dt_offset: id, rev, custom[4]
DTBO_ENTRY_FIELDS = (0x0, 0xFFFF0000, 0x3, 0x0, 0xFFFFFFFF, 0x0)

VENDOR_RAMDISK_TYPE_PLATFORM = 1


def pad(data, page):
    return data + b'\0' * (-len(data) % page)


def read(path):
    with open(path, 'rb') as f:
        return f.read()


def boot_image(kernel=b'', ramdisk=b'', os_version=0):
    cmdline = b''
    header = struct.pack('<8sIIII4II1536sI', b'ANDROID!', len(kernel), len(ramdisk),
                         os_version, 1584, 0, 0, 0, 0, 4, cmdline, 0)
    return pad(header, BOOT_PAGE) + pad(kernel, BOOT_PAGE) + pad(ramdisk, BOOT_PAGE)


def vendor_boot_image(cmdline, ramdisk, bootconfig):
    cmdline = cmdline.encode()
    if len(cmdline) >= 2048:
        sys.exit('vendor_boot cmdline too long')
    table = b''
    if ramdisk:
        table = struct.pack('<III32s16I', len(ramdisk), 0, VENDOR_RAMDISK_TYPE_PLATFORM,
                            b'', *([0] * 16))
    header = struct.pack('<8sIIIII2048sI16sIIQIIII', b'VNDRBOOT', 4, VENDOR_PAGE,
                         VENDOR_KERNEL_ADDR, VENDOR_RAMDISK_ADDR, len(ramdisk), cmdline,
                         VENDOR_TAGS_ADDR, b'', 2128, 0, VENDOR_DTB_ADDR,
                         len(table), 1 if ramdisk else 0, 108, len(bootconfig))
    return (pad(header, VENDOR_PAGE) + pad(ramdisk, VENDOR_PAGE) +
            pad(table, VENDOR_PAGE) + pad(bootconfig, VENDOR_PAGE))


def lz4_frame(data):
    # Same frame options as the stock entries: content checksum, no content size
    return subprocess.run(['lz4', '-9', '-c'], input=data,
                          capture_output=True, check=True).stdout


def dtbo_image(blobs):
    blobs = [lz4_frame(b) for b in blobs]
    offset = 32 + 32 * len(blobs)
    entries = b''
    for b in blobs:
        entries += struct.pack('>II6I', len(b), offset, *DTBO_ENTRY_FIELDS)
        offset += len(b)
    header = struct.pack('>8I', 0xD7B7AB1E, offset, 32, 32, len(blobs), 32, DTBO_PAGE, 1)
    return header + entries + b''.join(blobs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('kind', choices=['boot', 'init_boot', 'vendor_boot', 'dtbo'])
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--kernel')
    ap.add_argument('--ramdisk')
    ap.add_argument('--cmdline', default='')
    ap.add_argument('--bootconfig')
    ap.add_argument('--base')
    ap.add_argument('--overlay', action='append', default=[])
    a = ap.parse_args()

    if a.kind == 'boot':
        img = boot_image(kernel=read(a.kernel))
    elif a.kind == 'init_boot':
        img = boot_image(ramdisk=read(a.ramdisk), os_version=INIT_BOOT_OS_VERSION)
    elif a.kind == 'vendor_boot':
        img = vendor_boot_image(a.cmdline, read(a.ramdisk) if a.ramdisk else b'',
                                read(a.bootconfig) if a.bootconfig else b'')
    else:
        img = dtbo_image([read(a.base)] + [read(o) for o in a.overlay])

    with open(a.output, 'wb') as f:
        f.write(img)
    print(f'{a.output}: {len(img)} bytes')


if __name__ == '__main__':
    main()
