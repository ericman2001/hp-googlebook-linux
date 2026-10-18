#!/usr/bin/env python3
"""Show the Chrome EC uptime, its reset cause and recent AP resets (EC_CMD_GET_UPTIME_INFO)."""
import fcntl, os, struct
IOC = 0xc014ec00
fd = os.open('/dev/cros_ec', os.O_RDWR)
def cmd(c, ver, data, insize):
    buf = bytearray(struct.pack('<IIIII', ver, c, len(data), insize, 0)) + data + bytes(max(insize - len(data), 0))
    fcntl.ioctl(fd, IOC, buf)
    r = struct.unpack_from('<I', buf, 16)[0]
    if r: raise OSError(f'EC command {c:#x}: result {r}')
    return bytes(buf[20:20 + insize])
# EC_CMD_GET_UPTIME_INFO: time_since_ec_boot_ms, ap_resets_since_ec_boot, ec_reset_flags, 4x {reset_cause u16, reset_time_ms u32 packed}
d = cmd(0x0121, 0, b"", 120)
boot_ms, ap_resets, flags = struct.unpack_from('<III', d)
names = ['other', 'reset-pin', 'brownout', 'power-on', 'watchdog', 'soft', 'hibernate', 'rtc-alarm', 'wake-pin', 'low-battery', 'sysjump', 'hard', 'ap-off', 'preserved', 'usb-resume', 'rdd', 'rbox', 'security', 'ap-watchdog', 'stay-in-ro', 'efs', 'ap-idle', 'initial-pwr']
print(f'EC up {boot_ms / 1000:.0f} s, AP resets since EC boot: {ap_resets}')
print('EC reset flags:', ', '.join(n for i, n in enumerate(names) if flags & (1 << i)) or hex(flags))
causes = {0: 'unknown', 1: 'reset-board', 2: 'reset-ap', 0x8000: 'shutdown-power-fail', 0x8001: 'shutdown-reset-board', 0x8002: 'shutdown-thermal',
          0x8003: 'shutdown-battery-inhibit', 0x8004: 'shutdown-wake', 0x8005: 'shutdown-g3', 0x8006: 'shutdown-bad-battery', 0x8007: 'shutdown-battery-cutoff',
          0x8008: 'shutdown-console-cmd', 0x8009: 'shutdown-g3-ap-off', 0x800a: 'shutdown-ap-watchdog', 0x800b: 'shutdown-ap-reset'}
for i in range(4):
    cause, t = struct.unpack_from('<HI', d, 12 + i * 6)
    if cause or t:
        print(f'  recent AP reset: {causes.get(cause, hex(cause))} at {t / 1000:.1f} s')
