#!/usr/bin/env python3
"""Talk to the Googlebook's fingerprint MCU (Google 18d1:5405) from userspace.

The FPMCU is a Chrome EC that takes host commands (protocol v3) over a
vendor USB interface: bulk OUT 0x01 for requests, bulk IN 0x83 for
responses, interrupt IN 0x82 for events. This uses usbfs directly, so it
needs no kernel driver and no pyusb.

usage: fpmcu.py [version|info|reset|raw <cmd> [<ver> [<hex data>]]]
"""
import fcntl, glob, os, struct, sys, ctypes

VID, PID = 0x18d1, 0x5405
EP_OUT, EP_IN = 0x01, 0x83

# usbfs ioctls (64-bit layout)
USBDEVFS_BULK = 0xc0185502
USBDEVFS_CLAIMINTERFACE = 0x8004550f
USBDEVFS_RELEASEINTERFACE = 0x80045510
USBDEVFS_RESET = 0x5514


def find_dev():
	for d in glob.glob('/sys/bus/usb/devices/*'):
		try:
			v = int(open(d + '/idVendor').read(), 16)
			p = int(open(d + '/idProduct').read(), 16)
		except OSError:
			continue
		if (v, p) == (VID, PID):
			bus = int(open(d + '/busnum').read())
			dev = int(open(d + '/devnum').read())
			return '/dev/bus/usb/%03d/%03d' % (bus, dev)
	sys.exit('fpmcu: no 18d1:5405 device')


def bulk(fd, ep, data_or_len, timeout=1000):
	if isinstance(data_or_len, int):
		buf = ctypes.create_string_buffer(data_or_len)
		n = data_or_len
	else:
		buf = ctypes.create_string_buffer(bytes(data_or_len), len(data_or_len))
		n = len(data_or_len)
	arg = struct.pack('IIIxxxxQ', ep, n, timeout, ctypes.addressof(buf))
	r = fcntl.ioctl(fd, USBDEVFS_BULK, bytearray(arg))
	return buf.raw[:r] if isinstance(data_or_len, int) else r


def command(fd, cmd, ver=0, data=b'', insize=512):
	hdr = struct.pack('<BBHBBH', 3, 0, cmd, ver, 0, len(data))
	csum = (-sum(hdr + data)) & 0xff
	pkt = hdr[:1] + bytes([csum]) + hdr[2:] + data
	bulk(fd, EP_OUT, pkt)
	resp = b''
	while True:
		chunk = bulk(fd, EP_IN, 64)
		resp += chunk
		if len(resp) >= 8:
			ver_, _, result, dlen, _ = struct.unpack('<BBHHH', resp[:8])
			if len(resp) >= 8 + dlen or len(chunk) < 64:
				break
		elif len(chunk) < 64:
			break
	if len(resp) < 8:
		raise RuntimeError('short response: %s' % resp.hex())
	ver_, _, result, dlen, _ = struct.unpack('<BBHHH', resp[:8])
	if sum(resp[:8 + dlen]) & 0xff:
		print('fpmcu: warning: bad response checksum', file=sys.stderr)
	return result, resp[8:8 + dlen]


def cstr(b):
	return b.split(b'\0', 1)[0].decode(errors='replace')


def main():
	path = find_dev()
	fd = os.open(path, os.O_RDWR)
	fcntl.ioctl(fd, USBDEVFS_CLAIMINTERFACE, struct.pack('I', 0))
	try:
		what = sys.argv[1] if len(sys.argv) > 1 else 'version'
		if what == 'version':
			r, d = command(fd, 0x0002)
			print('result', r)
			if r == 0:
				print('RO:', cstr(d[0:32]))
				print('RW:', cstr(d[32:64]))
				print('image:', {1: 'RO', 2: 'RW'}.get(struct.unpack('<I', d[96:100])[0], '?'))
			r, d = command(fd, 0x000b)	# EC_CMD_GET_PROTOCOL_INFO
			if r == 0:
				vers, maxreq, maxresp, flags = struct.unpack('<IHHI', d[:12])
				print('protocols 0x%x, max request %d, max response %d' % (vers, maxreq, maxresp))
			r, d = command(fd, 0x0004)	# EC_CMD_GET_BUILD_INFO
			if r == 0:
				print('build:', cstr(d))
		elif what == 'info':
			r, d = command(fd, 0x0403, 1)	# EC_CMD_FP_INFO v1
			print('result', r, d.hex())
			if r == 0:
				vid, pid, model, ver, size, mode, fw = struct.unpack('<IIIIIII', d[:28])
				w, h, bpp = struct.unpack('<HHH', d[28:34])
				print('sensor vendor 0x%x product 0x%x model 0x%x version %d' % (vid, pid, model, ver))
				print('image %dx%d %d bpp; errors 0x%x' % (w, h, bpp, struct.unpack('<H', d[34:36])[0]))
				print('templates: %s' % (struct.unpack('<IHHII', d[36:52]),))
		elif what == 'reset':
			fcntl.ioctl(fd, USBDEVFS_RESET)
		elif what == 'raw':
			cmd = int(sys.argv[2], 0)
			ver = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
			data = bytes.fromhex(sys.argv[4]) if len(sys.argv) > 4 else b''
			r, d = command(fd, cmd, ver, data)
			print('result', r, d.hex())
		else:
			sys.exit(__doc__)
	finally:
		try:
			fcntl.ioctl(fd, USBDEVFS_RELEASEINTERFACE, struct.pack('I', 0))
		except OSError:
			pass	# released by a reset
		os.close(fd)


main()
