# Installing and rolling back

Read [RISKS.md](RISKS.md) first. You'll need your own images, built by following [BUILDING.md](BUILDING.md).

**Steps:**

1. [Get ready](#1-get-ready)
2. [Enter fastboot and check the device](#2-enter-fastboot-and-check-the-device)
3. [Flash the ROM](#3-flash-the-rom)
4. [Finish setup](#4-finish-setup)

Also: [updating without a wipe](#updating-without-a-wipe), [the optional recovery](#optional-lineage-style-recovery), [rolling back](#rolling-back-to-stock) and [troubleshooting](#if-something-goes-wrong).

## 1. Get ready

- **Unlock the device** with [sabrina-unlock-v2](https://github.com/oddsolutions/sabrina-unlock-v2). It requires stock build `UTTC.250917.004`.
- **Keep your `env` and `bootloader` backups** somewhere safe and private.
- **Prepare your rollback files:** stock `super`, `boot` and `vbmeta` from that same build. Check that they're correct before you need them.
- **Use a USB-C to USB-C data cable.**
- **On WSL2,** forward USB with [usbipd-win](https://github.com/dorssel/usbipd-win). The tested setup used a Linux `fastboot` built from source, because Windows fastboot was unreliable.

## 2. Enter fastboot and check the device

From Android:

```bash
adb reboot bootloader
```

Otherwise, hold the button during power-on, as set up by the unlock project.

Run these three checks:

```bash
fastboot getvar product
```

```bash
fastboot getvar unlocked
```

```bash
fastboot getvar is-userspace
```

You should see `sabrina`, `yes` and `no`. **If `unlocked` isn't `yes`, stop here.**

## 3. Flash the ROM

This writes three partitions. **Don't flash `bootloader` or `env`.**

```bash
fastboot -S 96M flash super super.sparse.img
```

```bash
fastboot -S 96M flash boot boot.img
```

```bash
fastboot -S 96M flash vbmeta vbmeta.img
```

Confirm it's still unlocked:

```bash
fastboot getvar unlocked
```

Then wipe and reboot:

```bash
fastboot -w
```

```bash
fastboot reboot
```

The first boot takes 2–3 minutes. The logo stays on screen until Android's graphics start, which is normal.

## 4. Finish setup

1. Pair the remote and complete setup. **Decline any system update.**
2. Turn on USB debugging: go to Settings → About, press "Android TV OS build" 7 times, then open Developer options.
3. Set the OTA block, which every wipe clears:

   ```bash
   adb shell settings put global ota_disable_automatic_update 1
   ```

4. Check the lock state. `0` means unlocked:

   ```bash
   adb shell getprop ro.boot.flash.locked
   ```

5. To control the TV's volume and Input, go to Settings → Remotes & Accessories → Set up remote buttons. This needs internet, and has to be run on the TV you'll use.

## Updating without a wipe

If your new build uses **the same keys** as the one on the device, you can flash `super`, `boot` and `vbmeta` as above and skip `fastboot -w`. Your account and apps stay in place. Switching keys, or switching from stock, needs a wipe.

## Optional: Lineage-style recovery

The ROM doesn't need this, but it replaces the stock recovery that has the dangerous reset. Build it with `scripts/pipeline/prepare_recovery_menu.py`, using your own keys.

**Test it from RAM first.** This changes nothing on the device:

```bash
fastboot boot recovery.img
```

If the menu and the device's button both work, flash it:

```bash
fastboot flash recovery recovery.img
```

Move through the menu with the button on the device, because the Bluetooth remote doesn't work in recovery. See [the "Install anyway?" warning](RISKS.md#install-anyway-in-recovery).

## Rolling back to stock

**Don't use the stock recovery's full OTA for this.** It can change bootloader state and relock the device.

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

Check that it's still unlocked:

```bash
fastboot getvar unlocked
```

Then wipe and reboot:

```bash
fastboot -w
```

```bash
fastboot reboot
```

**Stock now has no OTA protection**, because its blocks live in userdata. Keep it offline until you've reapplied them.

## If something goes wrong

| Problem | What to do |
|---|---|
| Stuck on the logo | Hold the button to enter fastboot, then restore stock |
| A recovery screen appears | **Don't choose Factory data reset.** Leave through fastboot, then wipe with `fastboot -w` |
| USB device not recognised | Flip the USB-C connector, or try another port |
| `fastboot getvar unlocked` says `no` | Stop flashing. Re-unlock with the unlock project, if the exploit is still possible on your device |
