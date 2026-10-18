#!/usr/bin/env python3
"""Print the battery state from the Chrome EC (via /dev/cros_ec).

Linux has no battery driver on this laptop yet (that needs the ADSP), but the
EC runs the fuel gauge, so this shows charge, current and charger state.
"""
import fcntl
import os
import struct

EC_CMD_BATTERY_GET_STATIC = 0x0600
EC_CMD_BATTERY_GET_DYNAMIC = 0x0601
CROS_EC_DEV_IOCXCMD = 0xc014ec00  # _IOWR(0xec, 0, struct cros_ec_command)


def ec_cmd(fd, cmd, version, data, insize):
    buf = bytearray(struct.pack('<IIIII', version, cmd, len(data), insize, 0))
    buf += data + bytes(max(insize - len(data), 0))
    fcntl.ioctl(fd, CROS_EC_DEV_IOCXCMD, buf)
    result = struct.unpack_from('<I', buf, 16)[0]
    if result:
        raise OSError(f'EC command {cmd:#x} failed with result {result}')
    return bytes(buf[20:20 + insize])


fd = os.open('/dev/cros_ec', os.O_RDWR)
d = ec_cmd(fd, EC_CMD_BATTERY_GET_DYNAMIC, 0, bytes([0]), 14)
volt, cur, rem, full, flags, dvolt, dcur = struct.unpack('<hhhhhhh', d)
pct = 100 * rem / full if full > 0 else 0
state = []
if flags & 1: state.append('AC present')
if flags & 2: state.append('battery present')
if flags & 4: state.append('discharging')
if flags & 8: state.append('charging')
if flags & 16: state.append('level critical')
print(f'battery {pct:.0f}% ({rem}/{full} mAh), {volt} mV, {cur:+d} mA'
      f' (charger asks for {dvolt} mV / {dcur} mA): {", ".join(state)}')
