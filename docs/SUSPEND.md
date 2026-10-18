# Suspend: status and notes

**Status: not working.** The SoC resets when it wakes from s2idle, and the
EC then powers the laptop off. Suspend is disabled on the reference install
so that closing the lid or idling can't lose a session:

    systemctl mask sleep.target suspend.target hibernate.target \
        hybrid-sleep.target suspend-then-hibernate.target
    # undo: systemctl unmask <same targets>

What does work: the system-wide PSCI idle state (patch 0016). With it the
SoC spends most of its *idle* time in system sleep, which helps battery life
even without suspend.

## What the firmware offers

* `/sys/power/mem_sleep` is `s2idle [deep]`, so PSCI `SYSTEM_SUSPEND` is
  advertised.
* **deep** is not usable. coreboot for bluey has no resume path, so a
  `SYSTEM_SUSPEND` wake is a cold boot. The EC stays up, but the session is
  lost.
* **s2idle** is the target. The stock system is Android, and the stock DT
  has the idle states for it.

## Tests (2026-10-18)

All 20 s sleeps were woken by the EC RTC (`rtcwake -m freeze`), unless
noted. "Reset" means the SoC reset while waking.

| # | Setup | Result |
|---|---|---|
| — | `pm_test=devices` (no real sleep) | Clean: devices suspended in 0.09 s, resumed in 2 s |
| 1 | s2idle | Reset at wake. Then everything lost power, the EC included. PMIC `FAULT_REASON1` = 0x40 (UVLO) |
| 2 | deep | Cold boot at wake (no resume path) |
| 3 | s2idle + system idle state (`0x200c354`) | Reset at wake; the EC forced G3 |
| 4 | same, woken by a key press | Reset at the key press |
| 5 | s2idle, `cros_ec_spi` unbound, power-key wake | Never woke (it stayed asleep, or hung) |
| 6 | s2idle, `cros_ec_spi` without the sleep event | Reset, then a full power loss, EC included |
| 7 | s2idle with the ADSP stopped | Reset at wake; the EC forced G3 |

The EC side of tests 3, 4 and 7 is always the same:

    power state 4 = S0, in 0x0004        <- at suspend entry (normally 0x0006)
    ... wake event ...
    power state 4 = S0, in 0x0005 / 0x0004 / 0x0006   <- the same pattern as a power-on reset
    AP_RST_L transitions not expected: 1
    chipset_force_shutdown(32778)

So the SoC's reset line toggles at the moment of waking, regardless of:
* the system idle state
* the EC sleep event (S0ix is sent: the dist kernel has `CONFIG_ACPI=y`)
* the ADSP
* the wake source

When the ADSP is running, the shutdown sometimes becomes a full brownout
(the EC resets with `reset-pin`, and the PMIC logs UVLO).

## Tools

* `tools/ec-uptime.py` (`ec-uptime` on the laptop) shows the EC uptime,
  its reset flags and recent AP resets.
* `googlebook-ec-log.service` saves the EC console log early at every boot
  to `/var/log/ec/boot-*.log`. The EC side of a failed suspend survives
  there.
* `/sys/kernel/debug/cros_ec/console_log` is a stream: always read it with
  `timeout 3 cat`.
* The PMIC power-off and fault reasons are in
  `/sys/kernel/debug/regmap/0-00/registers`, `0x08c0`-`0x08cf`.

## Ideas for next time

1. Find out who pulls `AP_RST_L` on wake: the PMIC (read its warm-reset
   reason after a test that the EC doesn't escalate to G3), or the
   firmware's PSCI wake path.
2. Retest s2idle with only cluster states, with CPU idle limited (for
   example `cpuidle.off=1`, which makes s2idle spin), to separate the PSCI
   wake path from everything else.
3. Look for Google's own Linux support for bluey suspend (ChromeOS kernel or
   Android GKI vendor patches) and the EC's Zephyr board code (`AP_RST_L`
   handling, `chipset_force_shutdown` reason 32778).
4. Fallback: hibernate (suspend to disk). Clean power-off and boot both
   work, so it only needs swap, `resume=`, and the rescue initramfs writing
   the swap device to `/sys/power/resume` before mounting root.
