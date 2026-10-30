# Risks and how to avoid them

Read this before installing anything.

## The short version

| Do | Don't |
|---|---|
| Wipe only with `fastboot -w` | Use Factory data reset, in Settings or in recovery |
| Decline every system update | Install or sideload a stock OTA |
| Block Google's OTA servers on your router | Flash LineageOS 22.2 or older `sabrina` builds |
| Back up `env` and `bootloader` first | Flash `bootloader` or `env`, or run `fastboot flashing lock` |
| Check you're still unlocked before wiping | Publish your keys, backups or logs |

## Factory reset can relock the device

**What happens:** stock recovery's Factory data reset also erases the `env` partition, where the unlock is stored. The bootloader relocks, and your button mapping is lost.

**How we know:**

- The [unlock whitepaper](https://oddsolutions.github.io/Chromecast-with-Google-TV-4K-Secure-Boot-Bypass-v2/) describes it.
- We saw a relock during testing, with both `env` copies reverted, after stock recovery appeared.
- Stock recovery's code does it, in `PostWipeData()`. See [ROOT-CAUSES.md](ROOT-CAUSES.md).

The Lineage-style recovery removes that code, but **no real reset has proved `env` survives**, so treat every reset as dangerous.

**You can reach the reset menu by accident.** After a failed boot, or when stock Android can't read its data, Android can reboot to a screen saying "Can't load Android system" and offering Factory data reset.

**How to stay safe:**

- **Wipe only with `fastboot -w`.** It erases userdata, cache and metadata, and leaves `env` alone.
- **Never choose Factory data reset**, however you got there.
- **If recovery appears, don't pick anything.** Leave with `adb reboot fastboot`, then `fastboot reboot bootloader`, or use the button-to-fastboot path from the unlock.
- **Don't use Factory reset in Settings.** The ROM should refuse it, but that guard hasn't been tested on a running device, and it can't protect the recovery menu itself.
- **Always wipe when switching between stock and this ROM.** Data from one can trigger the recovery prompt on the other.

## OTA updates can make the relock permanent

**What happens:** according to the [unlock project](https://github.com/oddsolutions/sabrina-unlock-v2), each OTA relocks the bootloader and can brick a modified device. Newer updates also put a password on Amlogic burn mode, which **stops the exploit from being run again**.

**How this ROM blocks them:**

| Block | Status |
|---|---|
| 12 Play services update components disabled | Confirmed on a running device |
| SetupWraith's update service disabled | Confirmed on a running device |
| `ota_disable_automatic_update=1` | **Set it by hand after every wipe** |
| Android refuses `--update_package` recovery commands | In the build, not tested live |

To set the third block:

```bash
adb shell settings put global ota_disable_automatic_update 1
```

**These blocks aren't a guarantee.** Part of Play services' `SystemUpdate` code still runs through a route they don't stop, and Google can change how updates work.

**How to stay safe:**

- **Decline any system update prompt**, including during first-boot setup.
- **Block Google's OTA servers on your router**, as the unlock project suggests. It's the only block that doesn't depend on the device's software.
- **Don't change the device identity to look like a certified stock device** without thinking it through, because update servers may be more likely to offer it an OTA. This build reports `sabrina` for YouTube, but keeps its own fingerprint.
- **Keep stock offline after a rollback** until you've reapplied its OTA blocks. They live in userdata, so `fastboot -w` removes them.

## "Install anyway?" in recovery

The Lineage-style recovery offers **Install anyway?** for a zip it can't verify. This is deliberate, so that you can install ROM zips, but a zip can write anything:

- A real stock OTA could relock the device.
- A LineageOS 22.2 zip's older bootloader could brick it through anti-rollback.

**Only choose Yes for a zip you know doesn't touch the bootloader.** Choosing No stops the install, with `error 21`, `status 2` and `Installation aborted`. That's the expected result.

## Other ways to brick or lock yourself out

- **Older LineageOS builds:** per the unlock project, 22.2 and older `sabrina` builds flash an older bootloader, and anti-rollback will brick the device.
- **Wrong partitions:** the ROM only writes `super`, `boot` and `vbmeta`. The optional recovery also writes `recovery`. Nothing here needs `bootloader` or `env`.
- **Relocking:** don't run `fastboot flashing lock` while modified.
- **Backups:** back up `env` and `bootloader` with the unlock tool first. Keep them private, because they contain your device's identifiers.
- **Cable:** use a USB-C to USB-C data cable, because USB-A to C may not give enough power. If Windows reports `Device Descriptor Request Failed`, flip the connector or change port.

## Security

- **The tested build isn't hardened.** SELinux is permissive and it contains diagnostic code. Consider using a secondary Google account.
- **Physical access:** with an unlocked bootloader, anyone holding the device can modify it.
- **Private files:** never publish signing keys, `env` backups, bugreports or logs. They can contain keys, serial numbers, MAC addresses and network names.

## Checking the lock state

"OEM unlocking" showing as disabled in Developer options is normal here, and doesn't tell you the real state.

From Android, `0` means unlocked:

```bash
adb shell getprop ro.boot.flash.locked
```

From fastboot, `yes` means unlocked:

```bash
fastboot getvar unlocked
```
