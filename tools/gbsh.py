#!/usr/bin/env python3
"""Run a shell command on the Googlebook's rescue shell (busybox telnetd).

usage: gbsh.py [-H host] [-t timeout] 'command'

Refuses every telnet option, sends the command followed by an end marker,
and prints the output up to the marker. Exit status is the command's.
"""
import argparse
import re
import socket
import sys
import time

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def strip_telnet(sock, data):
    """Remove telnet negotiation from data, refusing every option."""
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b != IAC or i + 1 >= len(data):
            out.append(b)
            i += 1
            continue
        cmd = data[i + 1]
        if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
            opt = data[i + 2]
            if cmd == DO:
                sock.sendall(bytes([IAC, WONT, opt]))
            elif cmd == WILL:
                sock.sendall(bytes([IAC, DONT, opt]))
            i += 3
        elif cmd == SB:
            end = data.find(bytes([IAC, SE]), i)
            i = len(data) if end < 0 else end + 2
        elif cmd == IAC:
            out.append(IAC)
            i += 2
        else:
            i += 2
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-H', '--host', default='10.0.0.194')
    ap.add_argument('-t', '--timeout', type=float, default=60)
    ap.add_argument('command')
    a = ap.parse_args()

    marker = f'__GBSH_DONE_{time.time_ns()}__'
    sock = socket.create_connection((a.host, 23), timeout=10)
    sock.settimeout(1)
    # Turn echo off first, so our own input stays out of the output
    sock.sendall(b"stty -echo 2>/dev/null; PS1=''\n")
    time.sleep(0.5)
    try:
        while sock.recv(65536):
            pass
    except socket.timeout:
        pass
    # Marker on its own line, so multi-line commands work too
    sock.sendall(f'{a.command}\necho "{marker} $?"\n'.encode())

    buf = b''
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        try:
            chunk = sock.recv(65536)
        except socket.timeout:
            continue
        if not chunk:
            break
        buf += strip_telnet(sock, chunk)
        m = re.search(rf'{marker} (\d+)'.encode(), buf)
        if m:
            text = buf[:m.start()].decode(errors='replace').replace('\r', '')
            # drop the echoed command line (sent before stty -echo took effect)
            if marker in text:
                text = text.split(marker, 1)[1].partition('\n')[2]
            sys.stdout.write(text)
            sock.sendall(b'exit\n')
            sys.exit(int(m.group(1)))
    sys.stdout.write(buf.decode(errors='replace'))
    sys.exit('gbsh: timed out')


if __name__ == '__main__':
    main()
