# Linux on the HP Googlebook (Snapdragon X Elite)

Mainline Linux and Gentoo on the HP Googlebook, the Chrome-OS-style laptop
Google calls **Quartz** (Bluey baseboard, Snapdragon X Elite X1E80100). It
boots like an Android phone: coreboot + depthcharge load Android boot images
from A/B partitions. This project puts a mainline kernel with a new device
tree on slot B and leaves slot A (stock) alone, so the stock system stays one
`fastboot set_active a` away.

Everything here was brought up on Linux 7.2.11 and a Gentoo arm64 stage3, but
the kernel patches are generic and should help any distribution.

## Status

| Hardware | Status | Notes |
|---|---|---|
| Boot (slot B, EL2, no hypervisor) | ✅ | Android boot image v4; DTB in `dtbo_b` |
| Display (2880×1800 120 Hz OLED) | ✅ | `msm` on eDP; brightness over DPCD AUX |
| GPU (Adreno X1-85) | ✅ | Firmware from linux-firmware; no zap shader at EL2 |
| Keyboard, power button | ✅ | Chrome EC over SPI; needs our spi-geni fix |
| Touchpad (Synaptics, haptic) | ✅ | HID over I²C |
| Touchscreen (ELAN) | ✅ | HID over I²C, pen collections present |
| NVMe SSD | ✅ | PCIe 6A, Gen4 ×4 |
| Wi-Fi (WCN7850, Wi-Fi 7) | ✅ | 6 GHz / 160 MHz tested; needs a board file, see docs |
| Bluetooth | ✅ | Same WCN7850 |
| USB-C (both ports) | ⚠️ USB 2.0 only | USB 3 / DP alt mode need the ADSP |
| **Charging** | ❌ | The battery does not charge under Linux (0 mA). The adapter powers the system, and heavy load drains the battery. Needs the ADSP |
| Battery status | ❌ | The EC only mirrors the ADSP, so its values are stale. `tools/ecbatt.py` shows the live charger status |
| Audio | ❌ | Needs the ADSP |
| Suspend, webcam, fingerprint | ❓ | Not tried yet |

> **Warning: charging.** Until the ADSP (audio DSP) runs under Linux, the
> battery does **not charge**: both chargers report status 7 and 0 mA. The
> adapter still powers the system, but a full-load job such as a 12-core
> kernel build draws more than it supplies, and the battery makes up the
> difference. One flattened the battery during bring-up, even on a 60 W
> charger. Charge with the laptop **powered off**: the firmware then charges
> normally. The Chrome EC's battery numbers are stale under Linux. The EC has
> no fuel gauge of its own and only mirrors what the ADSP reports.

## Layout

* `gentoo/`: files to install on the laptop. These are the kernel patches as
  Portage user patches, the kernel config fragment, a `kernel-install` hook
  that flashes new kernels to slot B, and NetworkManager settings. See
  [gentoo/README.md](gentoo/README.md).
* `tools/`: host-side tools. They build the boot images, flash slot B, extract
  stock firmware and partitions, and handle kexec testing.
* `initramfs/`: the busybox rescue initramfs. It switches to the root
  filesystem, or gives a rescue shell (optionally over the network).
* `config/`: kernel config fragments for a host-built kernel.
* `docs/`: [installation](docs/INSTALL.md), [firmware](docs/FIRMWARE.md) and
  [hardware notes and pitfalls](docs/HARDWARE.md).

Not in this repository, because they are device-specific or not
redistributable:
* your laptop's partition dumps
* HP's signed DSP firmware
* the stock vbmeta image
* any built binaries

The docs explain how to produce each from your own laptop.

## Kernel patches

In `gentoo/etc/portage/patches/sys-kernel/gentoo-kernel/`, against Linux 7.2.11:

1. `spi: geni-qcom`: release a chip select left asserted. This is a generic
   fix: without it, the Chrome EC rejects every command after the first.
2. The board device tree, `qcom/x1e80100-google-quartz.dtb`, and its later
   additions: USB 2.0, NVMe, touch, Wi-Fi, Bluetooth, display and GPU.
3. `phy: qcom: eusb2-repeater`: reset the repeater on init. This is a generic
   fix for a USB-C port that stays dead when a device was plugged in at boot.
4. `drm/panel-edp`: leave the enable GPIO alone when the panel is already
   powered. This is a generic fix: Samsung OLEDs otherwise stay black after the
   firmware-to-Linux handover.

The generic fixes are meant to go upstream.

## Safety

You need an **unlocked bootloader**, which wipes the device. Flashing goes to
slot B only, and slot A keeps the stock system. Have HP's recovery image
handy before you start.

The rescue initramfs can run a **root telnet shell with no password**
(`gbnet.telnet=1` on the kernel command line, or `GBNET_TELNET=1` for
`tools/build-images.sh`). It is off by default. Only use it on a network you
trust.

## License

The tools and scripts are GPL-3.0 (see `LICENSE`). The kernel patches are
GPL-2.0, as part of Linux. The device tree is BSD-3-Clause, matching the other
Qualcomm device trees.
