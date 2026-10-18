#!/usr/bin/env python3
"""Show what can be read about the battery without the ADSP.

* The Chrome EC's battery data (EC_CMD_BATTERY_GET_DYNAMIC). On this laptop
  the EC has no fuel gauge of its own: it only mirrors what the ADSP reports.
  Under Linux, with no ADSP running, this is a STALE snapshot from the
  firmware's charging applet at boot.
* The live charge status and charge current of the two SMB2360 chargers
  (SPMI SIDs 7 and 0xa), read like coreboot does. This needs debugfs
  (/sys/kernel/debug/regmap/1-07 and 1-0a).
"""
import fcntl
import os
import struct

EC_CMD_BATTERY_GET_DYNAMIC = 0x0601
CROS_EC_DEV_IOCXCMD = 0xc014ec00  # _IOWR(0xec, 0, struct cros_ec_command)
SCHG_CHGR_STATUS_REG = 0x2606     # bits 2:0, 3 = fast charge
SCHG_CHGR_CHARGING_FCC = 0x260a   # charge current, 50 mA steps


def ec_cmd(fd, cmd, version, data, insize):
    buf = bytearray(struct.pack('<IIIII', version, cmd, len(data), insize, 0))
    buf += data + bytes(max(insize - len(data), 0))
    fcntl.ioctl(fd, CROS_EC_DEV_IOCXCMD, buf)
    result = struct.unpack_from('<I', buf, 16)[0]
    if result:
        raise OSError(f'EC command {cmd:#x} failed with result {result}')
    return bytes(buf[20:20 + insize])


def smb_regs(sid):
    regs = {}
    with open(f'/sys/kernel/debug/regmap/1-{sid:02x}/registers') as f:
        for line in f:
            addr, _, val = line.partition(':')
            a = int(addr, 16)
            if a in (SCHG_CHGR_STATUS_REG, SCHG_CHGR_CHARGING_FCC):
                regs[a] = int(val, 16)
            if a > SCHG_CHGR_CHARGING_FCC:
                break
    return regs


fd = os.open('/dev/cros_ec', os.O_RDWR)
d = ec_cmd(fd, EC_CMD_BATTERY_GET_DYNAMIC, 0, bytes([0]), 14)
volt, cur, rem, full, flags, _, _ = struct.unpack('<hhhhhhh', d)
pct = 100 * rem / full if full > 0 else 0
print(f'EC snapshot (stale without the ADSP): {pct:.0f}% ({rem}/{full} mAh), '
      f'{volt} mV, {cur:+d} mA, flags {flags:#x}')

for name, sid in (('SMB1', 0x07), ('SMB2', 0x0a)):
    try:
        r = smb_regs(sid)
    except OSError as e:
        print(f'{name}: cannot read charger registers ({e.strerror}; mount debugfs?)')
        continue
    st = r[SCHG_CHGR_STATUS_REG] & 7
    ma = r[SCHG_CHGR_CHARGING_FCC] * 50
    print(f'{name} (live): status {st}{" (fast charge)" if st == 3 else " (not charging)" if ma == 0 else ""}, '
          f'charge current {ma} mA')
