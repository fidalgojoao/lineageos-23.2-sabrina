# Known issues

## Open

- **Wi-Fi drops:** the connection has been reported dropping, sometimes needing the password again. Auto-join works at boot but can take about a minute. The cause hasn't been found, and no drop has been captured in a log yet.
- **Blank tab in the launcher:** an unlabelled tab appears after "Library" and opens the search page. It's a `guide_page_tab_title` with empty text inside Google's launcher. It's harmless, and may change with launcher updates.
- **SELinux:** the tested build is permissive. An enforcing build still has to be tested, and earlier logs show `vendor_init` property denials to review.
- **Cast:** logs show `cast_ClientAuthCredsFactoryProvisioned: Cannot get device credentials`. Cast is untested and may not work.
- **Certification:** this build reports its own LineageOS fingerprint and isn't Google-certified. Apps that check Play Integrity or certification may refuse to run or limit quality.

## Untested

- 4K output. Only a 1080p monitor has been used so far, and stock offered the same modes on it.
- HDR, Dolby Vision and Dolby Atmos.
- Widevine L1 playback in Netflix and similar apps.
- The Assistant, beyond a user report that voice search works.
- SELinux enforcing, the factory-reset guard and the recovery-install guard on a running device.
- A clean full build from this device tree. See [BUILDING.md](BUILDING.md).
- Any device other than the one used here.

## Log noise to ignore

- `init: Unable to read config file ... init.boringssl.zygote32.rc`
- `Failed to mount optional controller schedtune`
- `Failed to generate rollback-resistant key`, which is expected on this hardware

Please include logs with any bug report, and remove serial numbers, MAC addresses, network names and account details first.
