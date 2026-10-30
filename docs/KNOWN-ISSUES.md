# Known issues

## Open

- **Wi-Fi after reboot:** reconnecting can be slow. On the test device, the saved network is hidden and on a DFS channel (5560 MHz). Full scans repeatedly missed it, with one boot taking 142 seconds, while a Wi-Fi toggle's single-channel scan connected in about 2 seconds. Stock's Wi-Fi settings are now applied, and three timed boots linked in 35 to 62 seconds, but that isn't enough to call it fixed. Broadcasting the network name or using a non-DFS channel may help. See [ROOT-CAUSES.md](ROOT-CAUSES.md).
- **CEC Volume Control switch:** once remote buttons are set up with IR, the remote sends volume straight to the TV, so this switch has no effect until the remote's volume control is turned off.
- **Blank tab in the launcher:** an unlabelled tab appears after "Library" and opens the search page. It's a `guide_page_tab_title` with empty text inside Google's launcher. It's harmless, and may change with launcher updates.
- **SELinux:** the tested build is permissive. An enforcing build still has to be tested, and earlier logs show `vendor_init` property denials to review.
- **Cast:** logs show `Cannot get device credentials` and, every 5 seconds, `Could not sign message in SSLPrivateKeyCastInternal::Sign`. The `castkey` DRM HAL is registered, and the cause hasn't been found. Cast is untested and may not work, and Google services that rely on device authentication may fail. The screensaver settings request to `clients3.google.com/cast/chromecast/home/settings/device` returned 404 before the privileged-app fix.
- **Certification:** this build reports the device as `sabrina`, which YouTube needs for quality above 360p, but its fingerprint is still its own and it isn't Google-certified. Apps that check Play Integrity or certification may refuse to run or limit quality.
- **Recovery RAM boot:** a later RAM boot of the release-signed recovery ended in the bootloader, and the cause isn't known yet. The device was not harmed, and a reboot returned it to Android.

## Untested

- **Release-signed images.** They have been built and checked offline, but not yet booted.
- **Play updates built into the image.** The tested image has the 11 Play-updated Google apps built in, with a generated permission allowlist and extracted native libraries. The device installed them without a wipe and kept using its identical `/data/app` copies, so **the built-in copies themselves haven't run**. A wrong allowlist could stop a wiped device from booting.
- **Factory reset through the new recovery.** Google's wipe plugin is gone, but no real reset has proved `env` survives. Use `fastboot -w` until it has.
- **A real OTA package reaching recovery.** Only a harmless unsigned zip has been refused so far.
- HDR, Dolby Vision and Dolby Atmos.
- Widevine L1 playback in Netflix and similar apps.
- The Assistant, beyond a user report that voice search works.
- SELinux enforcing, and the factory-reset and recovery-install guards on a running device.
- A clean full build from this device tree. See [BUILDING.md](BUILDING.md).
- Any device other than the one used here.

## Log noise to ignore

- `init: Unable to read config file ... init.boringssl.zygote32.rc`
- `Failed to mount optional controller schedtune`
- `Failed to generate rollback-resistant key`, which is expected on this hardware

Please include logs with any bug report, and remove serial numbers, MAC addresses, network names and account details first.
