#!/bin/sh
# Flash our images to the Googlebook's (unused) slot B over fastboot TCP and
# boot it. Slot A keeps stock Android; go back with: fastboot set_active a
#
# usage: flash-slot-b.sh <googlebook-ip>
set -eu

[ $# -eq 1 ] || { echo "usage: $0 <googlebook-ip>" >&2; exit 1; }
top=$(cd "$(dirname "$0")/.." && pwd)
fb="fastboot -s tcp:$1"

$fb flash boot_b "$top/out/boot.img"
$fb flash init_boot_b "$top/out/init_boot.img"
$fb flash vendor_boot_b "$top/out/vendor_boot.img"
$fb flash dtbo_b "$top/out/dtbo.img"
# Stock vbmeta with verification turned off (built by build-images.sh)
$fb flash vbmeta_b "$top/out/vbmeta.img"
$fb set_active b
$fb reboot
