# Suspend: status and notes

**Status: s2idle works.** The laptop suspends to idle and resumes into the
running session, with Wi-Fi and NVMe working afterwards. It needs:

* kernel patches 0021 and 0022 (PCIe GDSCs in retention, see below)
* `gentoo/etc/systemd/sleep.conf.d/googlebook.conf`, which makes systemd use
  s2idle and turns off hibernation
* `mem_sleep_default=s2idle` on the kernel command line
  (`gentoo/etc/googlebook/cmdline`), so `echo mem > /sys/power/state` also
  means s2idle

If you masked the sleep targets while suspend was broken, unmask them:

    systemctl unmask sleep.target suspend.target

Still open:

* **Sleep depth.** While suspended, only the CPU subsystem (`apss` in
  `/sys/kernel/debug/qcom_stats/`) enters its sleep state; `cxsd`, `aosd` and
  `ddr` stay at 0. So standby power is closer to idle than to a phone's
  standby. Something still holds a vote that keeps CX and DDR up.
* **deep** (PSCI `SYSTEM_SUSPEND`) is not usable: coreboot for bluey has no
  resume path, so waking from it is a cold boot.
* Hibernation is not set up (no swap or resume path).

## What was wrong

Resuming from s2idle reset the SoC. The cause was in the kernel, not the
firmware: genpd turned the PCIe GDSCs (power domains) off at
`suspend_noirq`, as `PWRSTS_OFF_ON` allows.

1. The PCIe controller GDSC (`gcc_pcie_4_gdsc`, Wi-Fi) didn't come back on
   at resume: `gcc_pcie_4_gdsc status stuck at 'off'`. Patch 0021, an
   upstream patch from January 2026 not yet in 7.2, switches the controller
   GDSCs to `PWRSTS_RET_ON`.
2. The PCIe PHYs don't use runtime PM, so genpd counts them as suspended and
   turns their GDSCs off too. The PHY then loses its state while the
   controller still has the link up, and the controller's first register
   read after waking faults. Patch 0022 switches the PHY GDSCs to
   `PWRSTS_RET_ON`, as SM8550 and SM8650 already do.

Any bad access like this is a NoC error. TrustZone turns it into a fatal
error (`qteed_err_fatal`) and a warm reset.

## Debugging tips

* **The firmware log survives a warm reset.** coreboot's console is in
  `/sys/firmware/log`. TrustZone writes its fatal errors there, after the
  previous boot's `jumping to kernel` line, for example:

      ERROR:   NOC_NAME: GEM_NOC POC:9, ... ERRLOGADDR_LOW = 0x7c000034 ...
      ERROR:   qteed_err_fatal: err = 12, err_ctx = ...

  The address names the block that was accessed (here PCIe 4's DBI).
* **The kernel's last messages** are in pstore,
  `/var/lib/systemd/pstore/console-ramoops-0`. Set
  `/sys/module/printk/parameters/console_suspend` to `N` and
  `/sys/power/pm_debug_messages` to 1 first, so the suspend and resume
  messages are kept.
* **Wake with a key, not the RTC, while debugging.** After a reset with an
  RTC event pending, coreboot boots in `LB_BOOT_MODE_RTC_WAKE` (the
  off-mode charging heartbeat) and powers the laptop off through
  `EC_CMD_AP_SHUTDOWN`. That loses the logs above. The EC log then shows
  `chipset_force_shutdown(32778)`, which is `CHIPSET_SHUTDOWN_HOST_CMD`.
* **The EC's view.** The EC runs `power/qcom_exp.c` from the ChromeOS EC
  tree (program `bluey/quartz`). Its input bits are 0 `AP_RST_ASSERTED`,
  1 `PS_HOLD`, 2 `POWER_GOOD` and 3 `AP_SUSPEND`. The sequence
  `in 0x0004 → 0x0005 → 0x0004 → 0x0006` followed by
  `AP_RST_L transitions not expected: 1` is an ordinary warm reset; every
  reboot shows it.
* `tools/ec-uptime.py` (`ec-uptime` on the laptop) shows the EC uptime, its
  reset flags and recent AP resets. `googlebook-ec-log.service` saves the EC
  console log at every boot to `/var/log/ec/boot-*.log`.
  `/sys/kernel/debug/cros_ec/console_log` is a stream: read it with
  `timeout 3 cat`.
* The PMIC power-off and fault reasons are in
  `/sys/kernel/debug/regmap/0-00/registers`, `0x08c0`-`0x08cf`.
