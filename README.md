# LineageOS 23.2 for Chromecast with Google TV 4K (sabrina)

An experimental Android 16 (LineageOS 23.2) port for the Chromecast with Google TV 4K. It runs on the device's Android 14 bootloader, a stock-based vendor partition and a repaired 5.15 kernel.

This is a test build, not a daily-driver release. It has been tested on **one device**, stock build `UTTC.250917.004`, with a 1080p monitor and a 4K LG TV.

> **Read [docs/RISKS.md](docs/RISKS.md) before doing anything.** A factory reset or an OTA update can relock the bootloader, and an OTA can stop you from ever unlocking it again.

## This depends on sabrina-unlock-v2

**[oddsolutions/sabrina-unlock-v2](https://github.com/oddsolutions/sabrina-unlock-v2)**, by Nolen Johnson (npjohnson), Jan Altensen (Stricted) and Ray Volpe (Functioner), is the exploit chain that unlocks the bootloader. Nothing here works without it. It uses [k-o-n-t-o-r/ghostlock-sabrina](https://github.com/k-o-n-t-o-r/ghostlock-sabrina) for temporary root.

Follow that project's instructions to unlock your device. See [CREDITS.md](CREDITS.md) for everyone else.

## What works

**Working on the test device:**

- Booting to Google TV, first-boot setup, and Gboard
- Google sign-in and the Play Store
- YouTube above 360p
- The remote staying paired after a reboot
- TV volume and Input through the remote, after setting up remote buttons (one LG TV)
- Holding Home to open Quick Settings
- Google TV screensaver
- Lineage-style recovery menu with the device's button
- Signing with your own release keys
- OTA update services disabled
- Remote battery level in Remotes & Accessories
- Rooted debugging, which you can turn on in Developer options

**In the build, not fully tested:**

- Advanced restart, which adds Recovery and Bootloader to the power menu
- A local-only Updater, including its remote-friendly list of zips and its recovery switch. **No update has been installed through it yet**

**Works, with problems:**

- Wi-Fi reconnects by itself after a reboot, but it can be slow on a hidden network. See [known issues](docs/KNOWN-ISSUES.md#wi-fi-is-slow-after-a-reboot)

**Not tested:**

- HDR, DRM video, Cast and audio formats
- SELinux enforcing. The tested build is permissive
- A factory reset through the new recovery, and a real OTA reaching it. **Don't try these on a device you care about**

**Not expected to work:**

- Play Integrity and Google certification
- Miracast. Neither AOSP nor the Lineage device tree has a receiver

Full list: [docs/KNOWN-ISSUES.md](docs/KNOWN-ISSUES.md).

## Guides

1. [Risks and how to avoid them](docs/RISKS.md): read this first
2. [Building](docs/BUILDING.md)
3. [Signing with your own keys](docs/SIGNING.md)
4. [Installing and rolling back](docs/INSTALL.md)
5. [Known issues](docs/KNOWN-ISSUES.md)
6. [What was broken and why](docs/ROOT-CAUSES.md)
7. [SELinux policy review](docs/SELINUX-API-MIGRATION-REVIEW.md): for developers

## What's in this repository

| Path | Contents |
|---|---|
| [`device/google/sabrina16/`](device/google/sabrina16) | Device tree and product definition |
| [`patches/`](patches) | Patches to AOSP, LineageOS and the kernel |
| [`manifests/`](manifests) | Pinned source manifests |
| [`scripts/`](scripts) | The scripts used to assemble the tested images, for reference |
| [`docs/`](docs) | The guides above |

**There's no ROM image, and there are no Google files or signing keys here.** Google's apps, vendor files and firmware aren't ours to redistribute. You extract what's needed from your own copy of the stock OTA, and build with your own keys.

## Disclaimer

You're responsible for any damage to your device. This work is unofficial, isn't affiliated with Google or the LineageOS project, and may void your warranty.

## License

Our own files are under [Apache-2.0](LICENSE). Kernel patches are under GPL-2.0, matching the kernel. See [NOTICE](NOTICE).
