# Installing Gentoo on the HP Googlebook

## The installer

> **New:** each phase has been tested on its own, including a container boot of
> the root filesystem it builds on the laptop. A complete run on a freshly
> unlocked laptop has not been done yet. Reports welcome.

`tools/googlebook-installer` installs Gentoo on a Googlebook from another
Linux PC (x86-64 or arm64), as automatically as the hardware allows:

    git clone https://github.com/ericman2001/hp-googlebook-linux
    cd hp-googlebook-linux
    tools/googlebook-installer

You need:
* A Linux PC with `fastboot` and `img2simg` (android-tools), clang/lld/llvm,
  `make`, `flex`, `bison`, `bc`, `perl`, `dtc`, `lz4`, `curl`, `xz`,
  `patch`, e2fsprogs, kmod, `openssl` and `sudo`. The installer checks and
  names anything missing. About 30 GiB of free space.
* A USB Ethernet adapter (or a USB-C hub with Ethernet) for the laptop, on
  the same wired network as the PC, with DHCP. The laptop's fastboot only
  works over the network.

It walks you through unlocking the bootloader (hold Esc + F2 and press
Power, then Advanced options → Unlock bootloader, which **erases the
laptop**) and starting fastboot (Advanced options → Bootloader fastboot).
Then, without anything to download by hand, it:
1. Optionally takes the stock `vbmeta_a` and the device-signed DSP firmware
   (`modem_a`) from HP's recovery USB drive or an image of it. Without one it
   makes its own vbmeta with verification disabled (an unlocked laptop boots
   it the same way it boots a modified stock one), and the laptop copies its
   DSP firmware from its own `modem_a` partition on first boot. This
   firmware's fastboot can't read partitions, so nothing is read from the
   laptop before Gentoo runs on it.
2. Downloads the latest Gentoo stage3 (arm64 desktop systemd, checked with
   Gentoo's signature), Linux 7.2.11 and the needed linux-firmware files, all
   checked against known checksums. Pass it a stage3 you already have to skip
   that download.
3. Builds the patched kernel and the boot images on the PC.
4. Builds an ext4 root filesystem: the stage3, the kernel modules, the
   firmware, the files from `gentoo/`, your user, passwords, time zone and
   locale, wired networking and SSH. This step uses `sudo`.
5. Asks you to type ERASE, then flashes the boot images to slot B and the
   root filesystem to `userdata`, and boots it. Slot A keeps stock Android.

On first boot the laptop grows the root filesystem to the whole disk and
backs up its unique partitions (`persist`, `keymaster`, `modem_a`, …) to
`/var/lib/googlebook/stock/` (root only). Copy them somewhere safe: `persist`
holds the laptop's calibration data and MAC addresses.

On the laptop, finish the setup as root:

    googlebook-postinstall          # Portage tree, sudo, NetworkManager,
                                    # linux-firmware, the Gentoo kernel
    googlebook-postinstall --gnome  # the same, plus the GNOME desktop

The installer keeps its progress in `work/`, so running it again continues
where it stopped; `--from PHASE` redoes a phase. `tools/googlebook-installer
--help` lists the phases.

## By hand

This is the path we took during the bring-up, condensed. It assumes an
x86-64 or arm64 Linux host with `clang`, `lld`, `llvm`, `dtc`, `lz4`,
`python3`, `fastboot` and a USB Ethernet adapter for the laptop. A USB-C
hub with Ethernet works, and fastboot over Ethernet is how depthcharge talks
to the host.

Commands run from a checkout of this repository. The tools expect this
layout:

    src/linux-7.2.11/     kernel git tree (patches applied, see below)
    src/build-arm64/      kernel build directory
    src/sysroot, src/busybox-*, src/kexec-tools-*   from tools/build-deps.sh
    stock/                your partition dumps
    out/                  built images

### 1. Unlock the bootloader and dump the stock partitions

Unlocking wipes the laptop. Afterward, boot the stock system or HP's
recovery USB and back up at least these partitions from the internal NVMe:
* `modem_a`
* `vendor_a` (inside `super`; `tools/lpextract.py` extracts it)
* `vbmeta_a`
* `dtbo_a`
* `persist`, `keymaster_a`, `frp_persist` and `desktop_security_persist`

Keep them private. `persist` holds unique calibration data and MAC addresses.

The stock device tree is in `dtbo_a`, a DT table of LZ4-compressed entries.
It is the reference for any hardware not yet supported.

### 2. Build the kernel

    git clone --depth 1 --branch v7.2.11 \
        https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git src/linux-7.2.11
    git -C src/linux-7.2.11 am ../../gentoo/etc/portage/patches/sys-kernel/gentoo-kernel/*.patch
    cd src/linux-7.2.11
    ARCH=arm64 LLVM=1 scripts/kconfig/merge_config.sh -O ../build-arm64 -m \
        arch/arm64/configs/defconfig ../../config/quartz.config
    make O=../build-arm64 ARCH=arm64 LLVM=1 olddefconfig
    make O=../build-arm64 ARCH=arm64 LLVM=1 -j$(nproc) Image.lz4 modules qcom/x1e80100-google-quartz.dtb

### 3. Build the boot images

    sh tools/build-deps.sh stage3-arm64-desktop-systemd-*.tar.xz   # sysroot, busybox, kexec
    sh tools/build-images.sh

This writes the following to `out/`:
* `boot.img`, `init_boot.img` (the rescue initramfs), `vendor_boot.img`
  (kernel command line), `dtbo.img` (the DTB) and `vbmeta.img`
* `rescue.cpio`, `vendor.cpio` and `placeholder.dtbo`, which step 5 needs

`vbmeta.img` is your stock `vbmeta_a` with verification disabled, so
`stock/vbmeta_a.img` must exist.

### 4. Boot it

In the depthcharge fastboot menu, with the Ethernet adapter connected:

    sh tools/flash-slot-b.sh <laptop-ip>   # flashes the *_b partitions, sets slot B active, reboots

With no root filesystem yet, you land in the rescue shell on the screen. Go
back to stock any time with `fastboot set_active a`.

### 5. Install Gentoo

From the rescue shell, or from any Linux running on the laptop:
1. Partition the NVMe. We reused the stock `userdata` partition: `mkfs.ext4 -L gentoo`.
2. Unpack the stage3 onto it with `tar xpf ... --numeric-owner`.
3. Install the kernel modules from step 2 into `/lib/modules`.
4. Set a root password.

The rescue init boots `root=LABEL=gentoo`. Press any key within 3 seconds,
or add `gbrescue` to the command line, to stay in the rescue shell.

Then, on the running Gentoo system:
1. Install the files from `gentoo/` (see [gentoo/README.md](../gentoo/README.md)).
2. Copy `out/rescue.cpio`, `out/vendor.cpio`, `out/placeholder.dtbo` and
   `out/vbmeta.img` to `/usr/local/share/googlebook/`.
3. Install the device firmware ([FIRMWARE.md](FIRMWARE.md)).
4. `emerge sys-kernel/gentoo-kernel`. The patches apply automatically, and
   the install hook flashes slot B. `googlebook-install-kernel --rollback`
   undoes the last flash.

Keep the laptop **powered off while charging** until the ADSP works (see the
README).
