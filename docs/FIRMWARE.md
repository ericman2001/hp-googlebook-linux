# Firmware

Most firmware comes from `sys-kernel/linux-firmware`:
* GPU: `qcom/gen70500_sqe.fw` and `gen70500_gmu.bin`
* Wi-Fi: `ath12k/WCN7850/hw2.0/*`
* Bluetooth: `qca/hmtbtfw20.tlv` and `qca/hmtnv20.b112`

The rest is device-specific or signed for this laptop, and is not included
here. Copy it from your own stock partitions.

## Device-signed firmware

The kernel looks for these in `/lib/firmware/qcom/x1e80100/google/quartz/`:

| Files | Source partition | Path inside |
|---|---|---|
| `adsp*`, `cdsp*` (with `.bNN` segments), `*.jsn` | `modem_a` (FAT) | `image/` |
| `kiwi/` (WCN785x firmware and `bdwlan` board files) | `modem_a` | `image/kiwi/` |
| `gen70500_zap.mbn` | `vendor_a` (EROFS, in `super`) | `firmware/` |
| `wlan_pci_subsys_bdf_map.ini` | `vendor_a` | `firmware/` |

    mount -o loop,ro modem_a.img /mnt/modem
    mount -t erofs -o loop,ro vendor_a.img /mnt/vendor   # vendor_a: tools/lpextract.py super.img
    F=/lib/firmware/qcom/x1e80100/google/quartz
    mkdir -p $F
    cp /mnt/modem/image/adsp* /mnt/modem/image/cdsp* /mnt/modem/image/*.jsn $F/
    cp -r /mnt/modem/image/kiwi $F/
    cp /mnt/vendor/firmware/gen70500_zap.mbn /mnt/vendor/firmware/wlan_pci_subsys_bdf_map.ini $F/

The ADSP and CDSP images are not used yet. The zap shader is not needed when
Linux runs at EL2, which is how this laptop boots.

## Wi-Fi board file

The HP/AzureWave card (PCI subsystem `103c:8e64`) has no entry in
linux-firmware's `board-2.bin`, and its OTP board ID is unset (`0xff`).
HP's `wlan_pci_subsys_bdf_map.ini` maps it to board 0x112, the NCM825A
module. Every other 0x112 card in `board-2.bin` (`17aa:e0e9`, `105b:e0ee`,
`105b:e0ef`, `17aa:930a`) uses the same calibration. Use that one:

    D=/lib/firmware/updates/ath12k/WCN7850/hw2.0
    mkdir -p $D
    python3 gentoo/usr/local/lib/googlebook/ath12k-board2.py \
        /lib/firmware/ath12k/WCN7850/hw2.0/board-2.bin \
        "bus=pci,vendor=17cb,device=1107,subsystem-vendor=17aa,subsystem-device=e0e9,qmi-chip-id=2,qmi-board-id=255" \
        $D/board.bin

HP's own Android `bdwlan.e12` does not work: the chip times out loading it
with the upstream firmware. `/lib/firmware/updates` keeps the file safe
from linux-firmware updates. Bluetooth independently picks
`hmtnv20.b112`, which confirms the board ID.
