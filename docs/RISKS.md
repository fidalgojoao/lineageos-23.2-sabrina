# Risks and how to prevent them

Two ordinary actions can undo your unlock: **a factory reset** and **an OTA update**. Please read this before installing anything.

## Factory reset

**What happens:** Factory Data Reset in stock recovery also resets the `env` partition, where the unlock state is stored. The bootloader relocks, and your custom button mapping is lost. The [unlock whitepaper](https://oddsolutions.github.io/Chromecast-with-Google-TV-4K-Secure-Boot-Bypass-v2/) describes this behaviour, and we saw a relock with both `env` copies reverted after stock recovery appeared during testing. The exact code that writes `env` hasn't been traced.

**You can land in that menu by accident.** After a failed boot, or when stock Android can't read its userdata, Rescue Party can reboot to a recovery screen saying "Can't load Android system" and offering Factory data reset.

**How to prevent it:**

- **Wipe only with `fastboot -w`.** It erases userdata, cache and metadata and leaves `env` alone.
- **Never choose Factory data reset** in recovery, however the device got there.
- **If recovery appears**, don't pick anything. Leave with `adb reboot fastboot` then `fastboot reboot bootloader`, or use the button-to-fastboot path set up by the unlock.
- **Don't use "Factory reset" in Settings.** This ROM's `FirmwareOtaPolicy` patch blocks `--wipe_data` and `--prompt_and_wipe_data`, so it should fail safely, but that guard hasn't been tested live and it can't protect the recovery menu itself.
- **Always wipe when switching between stock and this ROM.** Data from one can trigger the recovery prompt on the other.

## OTA updates

**What happens:** per the [unlock project](https://github.com/oddsolutions/sabrina-unlock-v2), each OTA relocks the bootloader on install, and can brick a modified device. Newer updates also set a password on Amlogic burn mode, which **stops the exploit from being run again**. So one OTA can make the relock permanent.

**How this ROM blocks them:**

| Layer | Status |
|---|---|
| 12 Play services update components disabled | Confirmed on a running device |
| SetupWraith's update service disabled | Confirmed on a running device |
| `ota_disable_automatic_update=1` | **Set by hand after each wipe** (`adb shell settings put global ota_disable_automatic_update 1`) |
| Android refuses `--update_package` recovery commands | In the build, not tested live |

**These blocks aren't a guarantee.** Part of Play services' `SystemUpdate` code still runs through a separate route that disabling these components doesn't stop. Google may also change how updates work.

**How to prevent it:**

- **Decline any system update prompt**, including during first-boot setup.
- **Block Google's OTA servers on your router**, as the unlock project suggests. It's the only layer that doesn't depend on the device's software.
- **Don't sideload an OTA** through stock recovery.
- **Don't change the device identity to match stock** without thinking it through. Reporting as a certified `sabrina` may make the update servers more likely to offer an OTA. This build deliberately doesn't.
- **Stock Android has fewer protections.** Its OTA blocks live in userdata, so `fastboot -w` removes them. Keep stock offline after any rollback until they're reapplied.

## Other ways to brick or lock yourself out

- **Don't flash LineageOS 22.2 or older `sabrina` builds on an unlocked device.** Per the unlock project, they flash an older bootloader, and anti-rollback will brick the device.
- **Don't flash `bootloader`, `env` or `recovery`** while following this guide. Only `super`, `boot` and `vbmeta` are written.
- **Don't run `fastboot flashing lock`** or otherwise relock while modified.
- **Back up `env` and `bootloader`** with the unlock tool first, and keep them private, since they contain your device's identifiers.
- **Use a USB-C to USB-C data cable.** USB-A to C may not provide enough power. If Windows reports `Device Descriptor Request Failed`, try flipping the connector.

## Security

- The **tested build uses SELinux permissive** and includes diagnostic code. Don't treat it as secure until an enforcing build is proven. Consider a secondary Google account.
- An unlocked bootloader means anyone with physical access can modify the device.
- Never publish your signing keys, `env` backups, bugreports or logs. They can contain keys, serial numbers, MAC addresses and network names.

## OEM unlocking toggle

"OEM unlocking" showing as disabled in Developer options is normal here. It doesn't report the actual state. To check that:

```bash
adb shell getprop ro.boot.flash.locked
```

`0` means unlocked. In fastboot, use:

```bash
fastboot getvar unlocked
```
