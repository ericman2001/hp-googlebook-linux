#!/bin/sh
# Build a static aarch64 cryptsetup for the rescue initramfs, so it can
# unlock an encrypted root filesystem. Cross-compiles with clang/lld against
# the sysroot from tools/build-deps.sh, with its own static libuuid, popt,
# json-c and libdevmapper, and the kernel's crypto API as the crypto backend
# (no OpenSSL).
#
# usage: build-cryptsetup.sh      (after tools/build-deps.sh)
# Result: src/cryptsetup/cryptsetup
set -eu

top=$(cd "$(dirname "$0")/.." && pwd)
src=$top/src
dl=$top/downloads
sysroot=$src/sysroot
work=$src/cryptsetup-build
prefix=$work/prefix
[ -d "$sysroot/usr/include" ] || { echo "run tools/build-deps.sh first" >&2; exit 1; }
rm -rf "$work"
mkdir -p "$dl" "$work" "$prefix"

fetch() {	# <url> <sha256>
	f=$dl/$(basename "$1")
	[ -f "$f" ] || curl -fL -o "$f" "$1"
	echo "$2  $f" | sha256sum -c - > /dev/null
	tar -C "$work" -xf "$f"
}

host=aarch64-unknown-linux-gnu
export CC="clang --target=$host --sysroot=$sysroot -fuse-ld=lld"
export AR=llvm-ar RANLIB=llvm-ranlib STRIP=llvm-strip NM=llvm-nm
export CFLAGS="-O2" LDFLAGS="-static -L$prefix/lib"
export PKG_CONFIG_LIBDIR=$prefix/lib/pkgconfig PKG_CONFIG_SYSROOT_DIR=
export CPPFLAGS="-I$prefix/include"
ac() {	# configure options common to the autotools packages
	./configure -q --host=$host --prefix="$prefix" --libdir="$prefix/lib" \
		--disable-shared --enable-static "$@"
}
jobs=$(nproc)

fetch https://www.kernel.org/pub/linux/utils/util-linux/v2.42/util-linux-2.42.4.tar.xz \
	fbd62a100ab7bb8746ba0661255c3c48185b1e9021507c624da01fbc696330ec
(
	cd "$work/util-linux-2.42.4"
	ac --disable-all-programs --enable-libuuid --disable-nls --without-systemd \
		--without-python --without-tinfo --without-ncurses --disable-bash-completion
	make -s -j"$jobs" libuuid.la
	make -s install-uuidincHEADERS install-usrlib_execLTLIBRARIES install-pkgconfigDATA
)

fetch https://ftp.osuosl.org/pub/rpm/popt/releases/popt-1.x/popt-1.19.tar.gz \
	c25a4838fc8e4c1c8aacb8bd620edb3084a3d63bf8987fdad3ca2758c63240f9
(
	cd "$work/popt-1.19"
	ac --disable-nls
	make -s -j"$jobs" -C src install
	make -s install-pkgconfigDATA
)

fetch https://s3.amazonaws.com/json-c_releases/releases/json-c-0.18.tar.gz \
	876ab046479166b869afc6896d288183bbc0e5843f141200c677b3e8dfb11724
(
	mkdir "$work/json-c-build"
	cd "$work/json-c-build"
	cmake -S "$work/json-c-0.18" -B . -G Ninja -DCMAKE_BUILD_TYPE=Release \
		-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 \
		-DCMAKE_C_COMPILER=clang -DCMAKE_C_COMPILER_TARGET=$host \
		-DCMAKE_SYSROOT="$sysroot" -DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld \
		-DCMAKE_AR="$(command -v llvm-ar)" -DCMAKE_RANLIB="$(command -v llvm-ranlib)" \
		-DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
		-DBUILD_SHARED_LIBS=OFF -DBUILD_STATIC_LIBS=ON -DBUILD_TESTING=OFF \
		-DBUILD_APPS=OFF -DDISABLE_WERROR=ON > /dev/null
	ninja -j"$jobs" install > /dev/null
)

fetch https://sourceware.org/pub/lvm2/LVM2.2.03.43.tgz \
	d87ec0dac9061f1fa58ebced5c6b1360c87d4c5cd7b455dc0ebe1d3f036920d7
(
	cd "$work/LVM2.2.03.43"
	./configure -q --host=$host --prefix="$prefix" --libdir="$prefix/lib" \
		--enable-static_link --disable-selinux --disable-udev_sync \
		--disable-blkid_wiping \
		--disable-readline --with-thin=none --with-cache=none \
		--with-vdo=none --with-writecache=none --with-integrity=none
	make -s -j"$jobs" -C libdm ioctl/libdevmapper.a
	install -D -m644 libdm/ioctl/libdevmapper.a "$prefix/lib/libdevmapper.a"
	install -D -m644 libdm/libdevmapper.h "$prefix/include/libdevmapper.h"
	dmver=$(cut -d' ' -f1 VERSION_DM)
	cat > "$prefix/lib/pkgconfig/devmapper.pc" <<-EOF
		prefix=$prefix
		libdir=\${prefix}/lib
		includedir=\${prefix}/include
		Name: devmapper
		Description: device-mapper library
		Version: $dmver
		Cflags: -I\${includedir}
		Libs: -L\${libdir} -ldevmapper
		Libs.private: -lm -lpthread
	EOF
)

fetch https://www.kernel.org/pub/linux/utils/cryptsetup/v2.8/cryptsetup-2.8.8.tar.xz \
	3acfa685f2dd7fcc832e0b77bc7093aa7da554a51ce8dafbb4138eaa854eee35
(
	cd "$work/cryptsetup-2.8.8"
	ac --enable-static-cryptsetup --with-crypto_backend=kernel --disable-blkid \
		--disable-udev --disable-selinux --disable-ssh-token --disable-external-tokens \
		--disable-asciidoc --disable-nls --disable-veritysetup --disable-integritysetup \
		--disable-hw-opal --disable-libargon2 --disable-keyring --disable-fips
	make -s -j"$jobs" cryptsetup.static
	mkdir -p "$src/cryptsetup"
	$STRIP -o "$src/cryptsetup/cryptsetup" cryptsetup.static
)

file "$src/cryptsetup/cryptsetup" 2> /dev/null || ls -l "$src/cryptsetup/cryptsetup"
echo "built $src/cryptsetup/cryptsetup"
