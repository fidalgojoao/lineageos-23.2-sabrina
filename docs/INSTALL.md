# Installing and rolling back

Read [RISKS.md](RISKS.md) first. You'll need your own images, built by following [BUILDING.md](BUILDING.md).

## Before you start

1. Unlock using [sabrina-unlock-v2](https://github.com/oddsolutions/sabrina-unlock-v2). It requires stock build `UTTC.250917.004`.
2. Keep your `env` and `bootloader` backups somewhere safe and private.
3. Prepare your rollback files: stock `super`, `boot` and `vbmeta` from the same stock build. Check that they're correct first.
4. Use a USB-C to USB-C data cable.
5. On WSL2, forward USB with [usbipd-win](https://github.com/dorssel/usbipd-win). The tested setup used a source-built Linux `fastboot`, because Windows fastboot behaved unreliably.

## Enter fastboot

From Android:

```bash
adb reboot bootloader
```

Otherwise, hold the button during power-on, as set up by the unlock project.

Check that it's the right device and still unlocked. **Stop if this doesn't say `yes`:**

```bash
fastboot getvar product
```

```bash
fastboot getvar unlocked
```

```bash
fastboot getvar is-userspace
```

Expect `sabrina`, `yes` and `no`.

## Flash

Only these three partitions get written. **Don't flash `bootloader`, `env` or `recovery`.**

```bash
fastboot -S 96M flash super super.sparse.img
```

```bash
fastboot -S 96M flash boot boot.img
```

```bash
fastboot -S 96M flash vbmeta vbmeta.img
```

Confirm it's still unlocked, then wipe and reboot:

```bash
fastboot getvar unlocked
```

```bash
fastboot -w
```

```bash
fastboot reboot
```

The first boot takes 2–3 minutes. The bootloader's logo stays on screen until Android's graphics start, so that's normal.

## After first boot

1. Pair the remote and complete setup. **Decline any system update.**
2. Turn on USB debugging: Settings → About → press "Android TV OS build" 7 times, then Developer options.
3. Set the OTA block, which every wipe clears:

```bash
adb shell settings put global ota_disable_automatic_update 1
```

4. Check the lock state:

```bash
adb shell getprop ro.boot.flash.locked
```

`0` means unlocked.

## Rolling back to stock

**Don't use the stock recovery's full OTA as your normal rollback.** It can change bootloader state and relock the device.

From fastboot, flash your stock images:

```bash
fastboot -S 96M flash super stock-super.sparse.img
```

```bash
fastboot -S 96M flash boot stock-boot.img
```

```bash
fastboot -S 96M flash vbmeta stock-vbmeta.img
```

Then check, wipe and reboot:

```bash
fastboot getvar unlocked
```

```bash
fastboot -w
```

```bash
fastboot reboot
```

**Stock is now unprotected against OTAs**, because its blocks live in userdata. Keep it offline until you've reapplied them.

## If something goes wrong

- **Stuck on the logo:** hold the button to enter fastboot, then restore stock.
- **Recovery screen appears:** **don't choose Factory data reset.** Leave through fastboot, then wipe with `fastboot -w`.
- **USB device not recognised:** flip the USB-C connector, and try another port.
- **`fastboot getvar unlocked` says `no`:** stop flashing. Re-unlock using the unlock project, if the exploit is still possible on your device.
