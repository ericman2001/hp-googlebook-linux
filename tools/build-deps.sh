#!/bin/sh
# Build what tools/build-images.sh needs for the rescue initramfs, under src/:
# an arm64 sysroot taken from a Gentoo stage3, a static busybox and a static
# kexec. Cross-compiles with clang/lld, so no aarch64 gcc is needed.
#
# usage: build-deps.sh <stage3-arm64-*.tar.xz>
set -eu

[ $# -eq 1 ] || { echo "usage: $0 <stage3-arm64-*.tar.xz>" >&2; exit 1; }
top=$(cd "$(dirname "$0")/.." && pwd)
src=$top/src
dl=$top/downloads
sysroot=$src/sysroot
mkdir -p "$src" "$dl" "$sysroot"

fetch() {	# <url> <sha256>
	f=$dl/$(basename "$1")
	[ -f "$f" ] || curl -fL -o "$f" "$1"
	echo "$2  $f" | sha256sum -c - > /dev/null
}

# Headers and libraries to link the static helpers against
tar -C "$sysroot" -xpf "$1" ./lib ./lib64 ./usr/include ./usr/lib/gcc ./usr/lib64

cc="clang --target=aarch64-unknown-linux-gnu --sysroot=$sysroot -fuse-ld=lld"

fetch https://busybox.net/downloads/busybox-1.38.0.tar.bz2 \
	34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2
rm -rf "$src/busybox-1.38.0"
tar -C "$src" -xjf "$dl/busybox-1.38.0.tar.bz2"
(
	cd "$src/busybox-1.38.0"
	make -s HOSTCC=clang "CC=$cc" defconfig > /dev/null
	# Static, and without tc (it doesn't build against current kernel headers)
	sed -i -e 's/^# CONFIG_STATIC is not set/CONFIG_STATIC=y/' \
		-e 's/^CONFIG_TC=y/# CONFIG_TC is not set/' .config
	make -s HOSTCC=clang "CC=$cc" oldconfig < /dev/null > /dev/null
	make -s HOSTCC=clang "CC=$cc" STRIP=llvm-strip -j"$(nproc)" busybox
)

fetch https://www.kernel.org/pub/linux/utils/kernel/kexec/kexec-tools-2.0.32.tar.xz \
	8f81422a5fd2362cf6cb001b511e535565ed0f32c2f4451fb5eb68fed6710a5d
rm -rf "$src/kexec-tools-2.0.32"
tar -C "$src" -xJf "$dl/kexec-tools-2.0.32.tar.xz"
(
	cd "$src/kexec-tools-2.0.32"
	./configure -q --host=aarch64-unknown-linux-gnu --without-xen --without-lzma \
		--without-zlib CC="$cc" LD=ld.lld AR=llvm-ar RANLIB=llvm-ranlib \
		OBJCOPY=llvm-objcopy STRIP=llvm-strip LDFLAGS=-static BUILD_CC=clang
	make -s -j"$(nproc)"
)

echo "built $src/busybox-1.38.0/busybox and $src/kexec-tools-2.0.32/build/sbin/kexec"
