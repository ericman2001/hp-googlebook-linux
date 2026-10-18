#!/bin/sh
# Build the boot, init_boot, vendor_boot and dtbo images for the Googlebook
# from the kernel build in src/build-arm64. Output goes to out/.
#
# KSRC, KBUILD and OUT override the kernel source, kernel build and output
# directories; VBMETA the stock vbmeta image (default stock/vbmeta_a.img).
# ROOT sets the root filesystem (default LABEL=gentoo); CRYPT=<partition
# name> makes the rescue initramfs unlock that LUKS partition first (with
# ROOT=/dev/mapper/root). The rescue initramfs includes cryptsetup if
# tools/build-cryptsetup.sh has built it.
set -eu

top=$(cd "$(dirname "$0")/.." && pwd)
src=${KSRC:-$top/src/linux-7.2.11}
build=${KBUILD:-$top/src/build-arm64}
out=${OUT:-$top/out}
vbmeta=${VBMETA:-$top/stock/vbmeta_a.img}
dtb=$build/arch/arm64/boot/dts/qcom/x1e80100-google-quartz.dtb

# root=LABEL=gentoo: the rescue init switch_roots into the installed system
# (any key within 3 s, or gbrescue, keeps the rescue shell).
# mem_sleep_default=s2idle: deep sleep has no resume path in this firmware.
cmdline="console=tty0 fbcon=font:TER16x32 clk_ignore_unused pd_ignore_unused ${LOGLEVEL:-loglevel=7} rdinit=/init mem_sleep_default=s2idle"
[ -n "${CRYPT:-}" ] && cmdline="$cmdline gbcrypt=$CRYPT"
cmdline="$cmdline root=${ROOT:-LABEL=gentoo}"
# GBNET_TELNET=1 adds gbnet.telnet=1: the rescue shell also listens on telnet
# with NO password. Only for bring-up on a trusted, firewalled network.
[ "${GBNET_TELNET:-0}" = 1 ] && cmdline="$cmdline gbnet.telnet=1"
# Extra kernel parameters, e.g. EXTRA_CMDLINE='dyndbg="file cros_ec_spi.c +p"'
cmdline="$cmdline ${EXTRA_CMDLINE:-}"

mkdir -p "$out"

# Built with __symbols__ (DTC_FLAGS_x1e80100-google-quartz in the qcom Makefile)
make -s -C "$src" O="$build" ARCH=arm64 LLVM=1 qcom/x1e80100-google-quartz.dtb
dtc -q -@ -I dts -O dtb -o "$out/placeholder.dtbo" "$top/config/placeholder.dtso"

# Initramfs: INITRAMFS=rescue (busybox shell, default) or smoke (test init)
initramfs=${INITRAMFS:-rescue}
if [ "$initramfs" = smoke ]; then
	clang --target=aarch64-linux-gnu -O2 -static -nostdlib -ffreestanding \
		-fno-stack-protector -fuse-ld=lld -Wall -Wextra \
		-o "$top/initramfs/init" "$top/initramfs/smoke-init.c"
fi
if [ "$initramfs" = rescue ]; then
	clang --target=aarch64-unknown-linux-gnu --sysroot="$top/src/sysroot" -fuse-ld=lld \
		-static -O2 -Wall -Wextra -o "$top/initramfs/ecprobe" "$top/initramfs/ecprobe.c"
	clang --target=aarch64-unknown-linux-gnu --sysroot="$top/src/sysroot" -fuse-ld=lld \
		-static -O2 -Wall -Wextra -o "$top/initramfs/ecspi" "$top/initramfs/ecspi.c"
	clang --target=aarch64-unknown-linux-gnu --sysroot="$top/src/sysroot" -fuse-ld=lld \
		-static -O2 -Wall -Wextra -o "$top/initramfs/gbkexec" "$top/initramfs/gbkexec.c"
fi
list=$initramfs.list
if [ "$initramfs" = rescue ] && [ -x "$top/src/cryptsetup/cryptsetup" ]; then
	list=$out/rescue-crypt.list
	{ cat "$top/initramfs/rescue.list"; echo "file /bin/cryptsetup ../src/cryptsetup/cryptsetup 0755 0 0"; } > "$list"
fi
(cd "$top/initramfs" && "$build/usr/gen_init_cpio" "$list") > "$out/$initramfs.cpio"
# Stock vendor_boot always carries a vendor ramdisk; keep one, nearly empty
echo 'dir /dev 0755 0 0' | "$build/usr/gen_init_cpio" - > "$out/vendor.cpio"

py="python3 -I $top/tools/mkimages.py"
$py boot --kernel "$build/arch/arm64/boot/Image.lz4" -o "$out/boot.img"
$py init_boot --ramdisk "$out/$initramfs.cpio" -o "$out/init_boot.img"
$py vendor_boot --cmdline "$cmdline" --ramdisk "$out/vendor.cpio" -o "$out/vendor_boot.img"
$py dtbo --base "$dtb" --overlay "$out/placeholder.dtbo" -o "$out/dtbo.img"

# Stock vbmeta with the HASHTREE_DISABLED | VERIFICATION_DISABLED flags set,
# i.e. what fastboot --disable-verity --disable-verification would flash
python3 -I - "$vbmeta" "$out/vbmeta.img" <<'EOF'
import struct, sys
d = open(sys.argv[1], 'rb').read()
assert d[:4] == b'AVB0', 'not a vbmeta image'
auth, aux = struct.unpack_from('>QQ', d, 12)
img = bytearray(d[:256 + auth + aux])
struct.pack_into('>I', img, 120, 3)
open(sys.argv[2], 'wb').write(img)
print(f'{sys.argv[2]}: {len(img)} bytes')
EOF
