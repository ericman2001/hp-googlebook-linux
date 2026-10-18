#!/bin/sh
# Test the current kernel + DTB + rescue initramfs on the Googlebook without
# flashing: stage them, graft depthcharge's runtime DT nodes onto the new
# DTB, download everything to the laptop and kexec into it.
#
# usage: kexec-test.sh [extra kernel parameters]
# The new DTB is passed through /sys/kernel/debug/kexec_dtb, which the
# running kernel needs (DEBUG patch on the quartz-dev branch): kexec-tools'
# kexec_load path (-c, --dtb) hangs on this machine.
# Needs the laptop's rescue shell on the network (telnet) and run from the
# project directory. Serves out/kexec/ over HTTP on this machine meanwhile.
set -eu

top=$(cd "$(dirname "$0")/.." && pwd)
build=$top/src/build-arm64
k=$top/out/kexec
host=${GBHOST:-10.0.0.194}
me=${GBSERVER:-10.0.0.132}
gbsh="python3 -I $top/tools/gbsh.py -H $host"

mkdir -p "$k"
cp "$build/arch/arm64/boot/Image" "$k/Image"
cat "$top/out/vendor.cpio" "$top/out/rescue.cpio" > "$k/initrd.cpio"
cp "$top/initramfs/gbkexec" "$k/gbkexec"

# Graft onto the DT the laptop booted with (as left by depthcharge)
$gbsh -t 60 'base64 /sys/firmware/fdt' | base64 -d > "$k/running.dtb"
python3 -I "$top/tools/dtgraft.py" "$k/running.dtb" \
	"$build/arch/arm64/boot/dts/qcom/x1e80100-google-quartz.dtb" "$k/quartz.dtb"

python3 -I -m http.server 8000 --bind "$me" --directory "$k" > /dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
sleep 1

$gbsh -t 300 "cd /tmp && for f in gbkexec Image initrd.cpio quartz.dtb; do wget -q -O \$f http://$me:8000/\$f || exit 1; done && chmod +x gbkexec &&
	{ mountpoint -q /sys/kernel/debug || mount -t debugfs none /sys/kernel/debug; } &&
	cat quartz.dtb > /sys/kernel/debug/kexec_dtb && echo staged"
$gbsh -t 10 "setsid sh -c \"sleep 1; /tmp/gbkexec /tmp/Image /tmp/initrd.cpio '\$(sed 's/ bootconfig\$//' /proc/cmdline) $*'\" < /dev/null > /dev/null 2>&1 & echo kexec started" || true

python3 -I - "$host" <<'EOF'
import socket, sys, time
host, t0 = sys.argv[1], time.time()
while time.time() - t0 < 30:
    try:
        socket.create_connection((host, 23), timeout=1).close(); time.sleep(1)
    except OSError:
        break
for _ in range(180):
    try:
        socket.create_connection((host, 23), timeout=2).close()
        print(f'back on the network after {time.time() - t0:.0f}s'); sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit('not back after 3 minutes')
EOF
