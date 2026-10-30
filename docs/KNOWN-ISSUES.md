# Known issues

## Open problems

### Wi-Fi is slow after a reboot

**What you'll see:** Wi-Fi reconnects by itself, but it can take up to about 30 seconds after Wi-Fi starts. It's been measured on a hidden network on a DFS channel (5560 MHz), and other networks may behave differently.

**Why:** a full scan can miss a hidden network, because its name isn't broadcast. A scan of the channel it was last seen on finds it straight away. See [ROOT-CAUSES.md](ROOT-CAUSES.md#wi-fi-slow-to-reconnect-on-a-hidden-network).

**What may help:** broadcasting the network name, or using a non-DFS channel.

### Cast may not work

Logs show `Cannot get device credentials` and, every 5 seconds, `Could not sign message in SSLPrivateKeyCastInternal::Sign`. The cause hasn't been found. Cast is untested, and Google services that rely on device authentication may fail too.

### The device isn't Google-certified

It reports itself as `sabrina`, which YouTube needs for quality above 360p, but it has its own fingerprint. Apps that check Play Integrity or certification may refuse to run or limit quality.

### SELinux is permissive

An enforcing build still has to be tested, and earlier logs show `vendor_init` property denials to review. See [the SELinux review](SELINUX-API-MIGRATION-REVIEW.md).

## Small problems

- **OTA setting after a wipe:** `ota_disable_automatic_update` has to be set again. See [INSTALL.md](INSTALL.md#4-finish-setup).
- **Remote buttons after a wipe:** set them up again in Remotes & Accessories.
- **CEC Volume Control switch:** once remote buttons are set up with IR, the remote sends volume straight to the TV. The switch does nothing until the remote's volume control is turned off.
- **Blank launcher tab:** an unlabelled tab after "Library" opens the search page. It comes from Google's launcher, it's harmless, and it may change with launcher updates.

## Seen once, not repeated

- **Recovery RAM boot:** one RAM boot of the release-signed recovery ended in the bootloader. A retry worked, and a reboot returned to Android.
- **Bluetooth crash during setup:** setup's `SetupWraith` app crashed once on Bluetooth during first-boot setup.

## Working as intended

- **Rooted debugging is greyed out.** Release (`user`) builds don't allow it.
- **"OEM unlocking" shows as disabled.** It doesn't report the real state. See [how to check](RISKS.md#checking-the-lock-state).
- **Choosing No at "Install anyway?"** ends with `error 21`, `status 2` and `Installation aborted`.

## Not tested yet

**Safety features.** Don't rely on these:

- A factory reset through the new recovery. No real reset has proved `env` survives, so use `fastboot -w`
- A real OTA reaching the recovery. Only a harmless unsigned zip has been tried
- A hidden automatic OTA being refused by Android
- The factory-reset guard on a running device

**Features:**

- HDR, Dolby Vision and Dolby Atmos
- Widevine L1 playback in Netflix and similar apps
- The Assistant, beyond a user report that voice search works

**Coverage:**

- A clean full build from this device tree. See [BUILDING.md](BUILDING.md)
- Any other device, or any TV other than one LG

## Log messages you can ignore

- `init: Unable to read config file ... init.boringssl.zygote32.rc`
- `Failed to mount optional controller schedtune`
- `Failed to generate rollback-resistant key`, which is expected on this hardware
- `Failed to set DFS flag`, which also appears on stock

## Reporting a bug

Please include logs, and first remove serial numbers, MAC addresses, network names and account details.
