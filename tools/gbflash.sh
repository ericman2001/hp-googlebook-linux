#!/bin/sh
# Flash our boot images to the Googlebook's slot B from its running Linux
# (rescue shell over telnet), instead of fastboot.
#
# usage: gbflash.sh [image dir]     (default: out/)
#
# Only the slot B boot partitions are ever written: boot_b, init_boot_b,
# vendor_boot_b, dtbo_b, vbmeta_b. Each is found by its exact GPT name,
# checked against the image size, written, and read back to verify.
set -eu

top=$(cd "$(dirname "$0")/.." && pwd)
dir=$(cd "${1:-$top/out}" && pwd)
host=${GBHOST:-10.0.0.194}
me=${GBSERVER:-10.0.0.132}
gbsh="python3 -I $top/tools/gbsh.py -H $host"

for p in boot init_boot vendor_boot dtbo vbmeta; do
	[ -f "$dir/$p.img" ] || { echo "missing $dir/$p.img" >&2; exit 1; }
done

python3 -I -m http.server 8001 --bind "$me" --directory "$dir" > /dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
sleep 1

for p in boot init_boot vendor_boot dtbo vbmeta; do
	sum=$(md5sum < "$dir/$p.img" | cut -d' ' -f1)
	size=$(stat -c %s "$dir/$p.img")
	$gbsh -t 300 "
		set -e
		devs=\$(grep -lx 'PARTNAME=${p}_b' /sys/class/block/nvme0n1p*/uevent | xargs -n1 dirname)
		[ \$(echo \"\$devs\" | wc -w) -eq 1 ] || { echo '${p}_b: expected exactly one partition'; exit 1; }
		dev=/dev/\$(basename \$devs)
		[ \$(( \$(cat \$devs/size) * 512 )) -ge $size ] || { echo '${p}_b: image too big'; exit 1; }
		wget -q -O /tmp/$p.img http://$me:8001/$p.img
		dd if=/tmp/$p.img of=\$dev bs=1M conv=fsync 2>/dev/null
		got=\$(head -c $size \$dev | md5sum | cut -d' ' -f1)
		rm -f /tmp/$p.img
		[ \"\$got\" = $sum ] && echo \"${p}_b (\$dev): written and verified\" || { echo \"${p}_b: VERIFY FAILED\"; exit 1; }
	"
done
