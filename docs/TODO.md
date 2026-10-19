# To do

Open items, roughly in order of value.

## Power

* **Deeper sleep while suspended.** s2idle works, but only the CPU
  subsystem reaches its sleep state: in `/sys/kernel/debug/qcom_stats/`,
  `apss` counts up while `cxsd` (CX shutdown), `aosd` (always-on subsystem
  sleep) and `ddr` stay at 0. Something still votes CX and DDR up during
  suspend, so standby drain is close to idle drain. Start by measuring
  overnight drain, then find the votes (interconnect and RPMh votes of the
  PCIe, USB and display drivers are the usual suspects).
* **Wi-Fi wake (WoWLAN).** ath12k supports it on the WCN7850. With it the
  card stays associated during suspend and wakes the laptop for matching
  packets, instead of being powered off.

## Polish

* **Battery time estimates** are about 8× too short. The battery firmware
  reports mAh labelled as mWh (`energy_full` 8796000 is 8796 mAh, a ~68 Wh
  pack). The percentage is right. Fix with a voltage-scaling quirk in
  `qcom_battmgr`.
* **Panel quirk table.** Add the Samsung OLED (`SDC 0x4215`) to
  `panel-edp`'s table, so it gets the right timings without the generic
  fallback warning at boot.
* **DMIC1 clicks.** One of the two internal mics clicks now and then (see
  [HARDWARE.md](HARDWARE.md)).

## Upkeep

* **Kernel version.** The patches target 7.2.11, and the installer and
  `package.accept_keywords/kernel` pin it. When Gentoo drops 7.2.11 from the
  tree, port the patches to a newer kernel and move the pins
  (`googlebook-postinstall` stops with a message until then).
* **The built-in fragment.** `tools/kfrag.py` builds
  `50-googlebook-quartz.config` from the drivers bound at boot, so it misses
  drivers that were already built in on the system it ran on but are modules
  in Gentoo's config. That's how `CROS_EC_SPI` (the internal keyboard at the
  passphrase prompt) and USB HID were missed. Next time the fragment is
  regenerated, compare it with the installer kernel's `modules.builtin`.

## Installer

* **Keymap at the passphrase prompt.** It's always US; load the chosen
  keymap in the rescue initramfs (busybox `loadkmap`).
* Not yet tried: installing with HP's recovery USB drive as the source of
  `vbmeta_a` and `modem_a`, and an install on a laptop that Android
  updates have moved to slot B.

## Untested

* Headset mic (no test hardware).
* DisplayPort audio.

## Upstreaming

* Generic kernel fixes: the spi-geni-qcom CS fix, the eusb2-repeater reset,
  panel-edp GPIO, the ADSP identity mapping, `cros_ec_usb`, gpio-cros-ec,
  and the PCIe PHY GDSC retention patch (0022).
* The board device tree.
* The crfpmoc fixes, offered to libfprint MR !512.
