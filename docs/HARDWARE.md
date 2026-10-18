# Hardware notes

The HP Googlebook is Google's **Quartz** model, on the **Bluey** baseboard
with a Snapdragon X Elite **X1E80100**. coreboot's `src/mainboard/google/bluey`
and depthcharge are the best references for the board wiring, alongside the
stock device tree in `dtbo_a`.

## Boot chain

* coreboot loads depthcharge, which boots **Android boot image v4**:
  * `boot` (kernel, LZ4)
  * `init_boot` (ramdisk)
  * `vendor_boot` (command line and vendor ramdisk)
  * `dtbo` (the DTB), and `vbmeta`
  * Slots A and B. Slot B is ours.
* The DTB comes from `dtbo_x`: a DT table v1 with LZ4 entries, a base DTB
  plus an overlay. Depthcharge picks entries by the custom fields
  `3, 0, 0xffffffff, 0` (id 0, rev 0xffff0000).
* At runtime depthcharge adds:
  * `/memory`
  * `/firmware/coreboot` and `/firmware/chromeos`
  * ramoops
  * pKVM and coreboot reserved regions
  * the LPDDR channels
* **Linux is entered at EL2 and there is no Gunyah**, so the device tree
  takes the `x1-el2.dtso` adjustments:
  * the SBSA watchdog off, the APSS watchdog on
  * the PCIe SMMU on, with `iommu-map` set
  * no zap shader
* Fastboot runs over a USB Ethernet adapter. Unlocking is the usual
  `fastboot flashing unlock`.

## Pitfalls (each cost real time)

* **GPIOs 34–35 and 44–47 belong to the secure world.** Touching them
  causes a NoC error, then a TrustZone fatal error and a reset. They must be
  in `gpio-reserved-ranges`.
* **The GIC ITS must stay disabled**, as in the stock DT, or the kernel hangs
  early. PCIe therefore uses the DesignWare controller's own MSI receiver
  (`msi-map` deleted).
* **simple-framebuffer:** the `reg` size must be exactly 2880×1800×4, and the
  splash region must be `no-map`. A short size oopses simpledrm, which looks
  like a silent hang.
* **Chrome EC on SPI (QUP SE13):** `spi-geni-qcom` has no `set_cs`, so CS
  stays asserted after the zero-length end-of-message transfer, and the EC
  rejects everything after the first command. Patch 0001 fixes this.
* **eUSB2 repeaters** (in the SMB2360 PMICs, SPMI SIDs 7 and 0xa): a port
  with a device attached at handoff stays dead unless the repeater is reset
  (`EN_CTL1` 0 → 0x80, as coreboot does). Patch 0004 does this.
* **Touchpad:** it needs the 1.8 V `L1B` rail, which the stock DT lists as
  `pm_humu_l1`. Its 3.3 V switch (GPIO 36) must stay on, or i2c-hid probes
  it before it's ready.
* **Display handover:** the eDP panel is a Samsung OLED (`SDC 0x4215`).
  panel-edp used to drop the panel enable line at probe while the panel
  stayed powered. The panel then stays black, even though the link trains and
  the stream is in sync, until it is power cycled. Patch 0009 fixes this.
* **`msm` with no outputs in the DT** oopses in `msm_drv_probe`, because
  there are no components to match.
* **Charging is done by the ADSP.** coreboot runs a charging applet on the
  ADSP and then resets it before booting the OS, which is expected to load
  the full ADSP firmware. Without it there is no PD negotiation, so the
  laptop discharges on the charger.

## Board map

| Function | Wiring |
|---|---|
| Chrome EC (Zephyr, NPCX9) | QUP SE13 SPI, GPIOs 52–55; interrupt GPIO 66 |
| Touchpad (Synaptics 06CB:96E7) | I²C QUP0 SE0 @ 0x2c; interrupt GPIO 3; 3.3 V GPIO 36; 1.8 V L1B |
| Touchscreen (ELAN 04F3:4832) | I²C QUP1 SE0 @ 0x15; interrupt GPIO 51; reset GPIO 48; 3.3 V GPIO 88 |
| NVMe (WD SN5000S) | PCIe 6A ×4; PERST GPIO 152, CLKREQ 153, WAKE 154; 3.3 V GPIO 18 |
| Wi-Fi/BT (WCN7850, HP/AzureWave 103c:8e64) | PCIe 4; 3.3 V GPIO 214; WLAN_EN 117, BT_EN 116; BT on QUP1 SE6 (`uart14`) |
| eDP panel | DP3; power GPIO 70; HPD GPIO 119; enable (EL_ON3) PMC8380 #3 GPIO 4; brightness over DPCD |
| USB-C | Right port `usb_1_ss1`, left port `usb_1_ss0`; eUSB2 repeaters in the SMB2360s |
| Display rails | eDP PHY on L2J (1.2 V) and L3J (0.88 V), shared with the USB QMP PHYs |

## Development tricks

* **kexec:** `kexec_file_load` ignores `--dtb`, and kexec-tools' `-c` path
  hangs. The DEBUG patch on our development branch (not in the patch set)
  adds `/sys/kernel/debug/kexec_dtb`. See `tools/kexec-test.sh` and
  `initramfs/gbkexec.c`.
* **Crash logs:** pstore/ramoops survives a warm reset. `fastboot oem logs`
  shows the previous boot's firmware log after a warm reset, but not after a
  long power-button press.
* **QEMU** (`-M virt,virtualization=on`) with a copy of the framebuffer node
  reproduced the simpledrm bug.
* **Display test pattern without a desktop:**
  `tools/drmtest/drmstripes.c` does a full modeset with stripes.
