#!/usr/bin/env python3
"""List /reserved-memory children (name, base, size) from a DTB via fdtget."""
import subprocess, sys

dtb = sys.argv[1]
run = lambda *a: subprocess.run(['fdtget', *a], capture_output=True, text=True).stdout.split()
for n in run('-l', dtb, '/reserved-memory'):
    path = f'/reserved-memory/{n}'
    reg = run('-t', 'x', dtb, path, 'reg')
    if len(reg) >= 4:
        for i in range(0, len(reg) - 3, 4):
            base = int(reg[i], 16) << 32 | int(reg[i + 1], 16)
            size = int(reg[i + 2], 16) << 32 | int(reg[i + 3], 16)
            print(f'{base:#012x} {base + size:#012x} {size >> 10:8d}K {n}')
    else:
        print(f'{"dynamic":>12} {"":12} {"":9} {n}')
