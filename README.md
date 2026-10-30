# LineageOS 23 for Chromecast with Google TV 4K (sabrina)

An experimental Android 16 (LineageOS 23.2) port for the Chromecast with Google TV 4K, running on the device's Android 14 bootloader, stock-derived vendor partition and a repaired 5.15 kernel.

> **Read [docs/RISKS.md](docs/RISKS.md) before doing anything.** A factory reset or an OTA update can relock the bootloader, and an OTA can stop you from ever unlocking it again.

## This would not be possible without sabrina-unlock-v2

This project depends entirely on **[oddsolutions/sabrina-unlock-v2](https://github.com/oddsolutions/sabrina-unlock-v2)**, by Nolen Johnson (npjohnson), Jan Altensen (Stricted) and Ray Volpe (Functioner). It's the exploit chain that unlocks the bootloader, and nothing here works without it. It uses [k-o-n-t-o-r/ghostlock-sabrina](https://github.com/k-o-n-t-o-r/ghostlock-sabrina) for temporary root.

Follow that project's instructions to unlock your device. See [CREDITS.md](CREDITS.md) for everyone else.

## Status

Tested on **one device**, stock build `UTTC.250917.004`, on a 1080p monitor and 4K LGTV. This is a test build, not a daily-driver release.

| Feature | Status |
|---|---|
| Boots to Google TV | Works |
| Google first-boot setup | Works |
| Gboard | Works |
| Google TV screensaver as a system app | Works |
| Remote stays paired after reboot | Works |
| Google sign-in, Play Store, voice search | Reported working |
| OTA update services | Disabled, confirmed on the running device |
| Android recovery-install block | In the build, not tested live |
| Factory-reset block | In the build, not tested live |
| SELinux enforcing | **Not yet tested.** The tested build is permissive |
| Wi-Fi reconnect after reboot | **Open.** Can still be slow, especially with a hidden network on a DFS channel |
| YouTube above 360p | Works, confirmed on a 1080p monitor and a 4K LG TV |
| Holding Home opens Quick Settings | Works |
| TV volume through the remote | Works after IR setup, on one LG TV |
| Set up remote buttons in Settings | Works, through Remotes & Accessories |
| Lineage-style recovery menu | Works with the device's button. Unsigned packages were refused |
| Release-key signing | Works: wiped and booted to setup with the builder's own keys, on one device. No keys are included here |
| HDR, DRM video, Cast, audio formats | **Not tested** |
| Play Integrity or Google certification | **Not expected to pass** |

Full list: [docs/KNOWN-ISSUES.md](docs/KNOWN-ISSUES.md).

## What's in this repository

| Path | Contents |
|---|---|
| [`device/google/sabrina16/`](device/google/sabrina16) | Device tree and product definition |
| [`patches/`](patches) | Patches to AOSP, LineageOS and the kernel |
| [`manifests/`](manifests) | Pinned source manifests |
| [`scripts/`](scripts) | The scripts used to assemble the tested images, as reference |
| [`docs/`](docs) | Risks, building, signing, installing, root causes |

**No ROM image is published, and no Google files are included.** This repository has no Google apps, vendor blobs or firmware, because they aren't ours to redistribute. You extract what's needed from your own copy of the stock OTA, and build with your own keys.

## Guides

1. [Risks and how to prevent them](docs/RISKS.md): read this first
2. [Building](docs/BUILDING.md)
3. [Signing with your own keys](docs/SIGNING.md)
4. [Installing and rolling back](docs/INSTALL.md)
5. [What was broken and why](docs/ROOT-CAUSES.md)
6. [Known issues](docs/KNOWN-ISSUES.md)

## Disclaimer

You're responsible for any damage to your device. This work is unofficial and isn't affiliated with Google or the LineageOS project, and it may void your warranty. The fixes have only been tested on one device.

## License

Our own files are under [Apache-2.0](LICENSE). Kernel patches are under GPL-2.0, matching the kernel. See [NOTICE](NOTICE).
