# What was broken and why

Each problem here was diagnosed from device logs or source. These notes may help with other ports to older Android TV devices.

**Contents:** [Booting](#booting) · [Setup](#setup) · [Remote](#remote-and-buttons) · [Wi-Fi](#wi-fi) · [Video and audio](#video-and-audio) · [Apps](#apps) · [Keeping the unlock](#keeping-the-unlock) · [Debugging notes](#debugging-notes)

## Booting

### Reboots about 18 seconds in

- **Cause:** the device launched on API 29, so Android 16 picks an old cgroup description where `schedtune` is mandatory. Kernel 5.15 doesn't have it, so cgroup setup aborts, `ueventd` and `apexd-bootstrap` can't start, and init reboots.
- **Fix:** [`vendor-config/cgroups.json`](../device/google/sabrina16/vendor-config/cgroups.json) makes that one controller optional.

### Stuck on the logo forever

- **Cause:** the GPU driver never loaded. `ro.board.platform=sabrina` makes Android 16 look for `libGLES_sabrina.so`. When that fails, a flag **skips its wildcard search**, so `libGLES_mali.so` is never found. SurfaceFlinger aborts with `couldn't find an OpenGL ES implementation`, and it and zygote restart forever.
- **Fix:** `ro.hardware.egl=mali`.

### Storage needs a kernel feature

- **Cause:** Android 16's storage needs `CONFIG_DM_DEFAULT_KEY`, which the stock kernel lacks. Simply enabling it shifts the kernel ABI that stock vendor modules depend on.
- **Fix:** [`kernel-dm-default-key-kabi.patch`](../patches/kernel/kernel-dm-default-key-kabi.patch) moves the new field into a reserved slot, so the modules keep loading.

## Setup

### Google sign-in returned to the home screen

- **Symptom:** "Set up Google TV" bounced back home.
- **Cause:** `TvProvision` and `LineageSetupWizard` were present alongside Google's `SetupWraith`. Android logs `There should probably be exactly one setup wizard; found 2` and recognises none, so `SetupWraith` doesn't get the setup-only `NETWORK_SETUP_WIZARD` permission. It then crashes in `WifiServiceImpl.getCurrentNetwork`.
- **Fix:** remove both extra setup apps.

### First-boot setup was skipped

- **Cause:** `ro.setupwizard.mode=DISABLED`, inherited from `atv_emulator_vendor.mk`.
- **Fix:** remove it. The patch also sets `PRODUCT_CHARACTERISTICS` to stock's `tv,nosdcard`, where the same file had set `emulator`.

## Remote and buttons

### Remote needed the two-button press after every reboot

- **Symptom:** the pairing survived, but the remote only reconnected after holding its two pairing buttons.
- **Likely cause:** stock's `bluetooth.core.le.privacy.apply_identity_addr_after_paired=true` doesn't exist in Android 16's Bluetooth source. The Chromecast keeps a rotating private address, so the remote's normal wake-up signal appears to get ignored. Pairing mode broadcasts to everyone, so that still worked.
- **Fix:** `bluetooth.core.gap.le.privacy.enabled=false`, which uses the public address. The cost is that its Bluetooth address no longer rotates. The Bluetooth device class was also restored to stock's `44,4,32`.

### TV volume and Input didn't work

- **Cause:** stock's `TVAxel` (Android TV Infrared Service) was missing, so the remote couldn't be set up to send IR. CEC volume went to the soundbar, which acknowledged it and ignored it.
- **Fix:** include `TVAxel`, its overlay and stock's permission entries, then run the setup. Stock links the menu from `ChromecastServiceAml`, so `SabrinaTvSettingsOverlay` fills TV Settings' own `bluetooth_ir_entry_slice_uri` slot instead.

### Holding Home opened the assistant

- **Cause:** LineageOS's key handler uses its own action list, where `3` means search. Separately, `TvFrameworkOverlay` sets a `large` value that wins on TVs, and `ATVOverlay` points the panel at the wrong package.
- **Fix:** `patches/frameworks_base/0002` honours stock's panel setting, and `SabrinaFrameworkOverlay` sets both values. Build it with `aapt2 --no-resource-deduping`, or the `large` copy is dropped.

## Wi-Fi

### Wi-Fi asking for the password again

- **Symptom:** Wi-Fi took minutes to come back, or didn't return until the password was entered again.
- **Likely cause:** stock's `SabrinaWifiOverlayGoogle` targets `com.google.android.wifi.resources`, but this build's package is `com.android.wifi.resources`, so its values were missing. Android's defaults disable a network indefinitely after a password failure or a permanent no-internet result, and allow temporary disables of up to 18 hours. Stock uses 60 seconds and 5 minutes.
- **Fix:** [`rro/SabrinaWifiOverlay`](../device/google/sabrina16/rro/SabrinaWifiOverlay) applies stock's values to the right package. It also matches stock's `config_wifi_background_scan_support` (true), `config_wifiSaeUpgradeEnabled` (false) and `config_wifiVerboseLoggingAlwaysOnLevel` (0).

### Wi-Fi slow to reconnect on a hidden network

- **Symptom:** after a reboot, Wi-Fi could take over 2 minutes to connect, with no toggling involved. Turning Wi-Fi off and on connected in about 2 seconds.
- **Cause:** the test network is hidden and on DFS channel 5560. Full scans can see the router with a blank name, logged as `invalid SSID`, and skip it. A scan of only its known channel finds it. After a reboot, Android was using full scans, and it had no channel history until a connection event loaded it.
- **Fix, in `packages/modules/Wifi`:**
  - `WifiScoreCard` now loads the stored channels whenever they're asked for.
  - While disconnected with a hidden network saved, `WifiConnectivityManager` now alternates full scans with known-channel scans.
- **Result:**

| Build | Wi-Fi start to link |
|---|---|
| Before stock's Wi-Fi values | 142 s and 11 s |
| With stock's Wi-Fi values | 35, 35 and 62 s |
| With both fixes above | 29, 29, 29, 28, 14 and 29 s |

The known-channel scan connects when it runs. The remaining wait is mostly the 20 seconds before its turn. This was measured on one router, with no toggling.

**Not explained:** stock's compiled code doesn't have these fixes either, so they don't show why stock felt seamless.

## Video and audio

### YouTube limited to 360p

- **Cause:** the build reported a generic device.
- **Fix:** `ro.product.product.device=sabrina` and `ro.product.product.model=Chromecast`. Confirmed on a monitor and a TV.

### No audio over HDMI

- **Fix:** audio only reached HDMI after `patches/frameworks_base/0002` reported Amlogic's extcon state.

## Apps

### Old keyboard

- **Cause:** only Leanback was included, while stock ships `LatinIMEGoogleTvPrebuilt` (Gboard for TV).
- **Fix:** add Gboard from your stock image, and remove Leanback.

### Screensaver settings said "Unable to load content"

- **Symptom:** Google TV's screensaver settings showed an error, and Google Photos wasn't used.
- **Cause:** the build shipped an older `Backdrop` app and no `TVDreamXPrebuilt`. Google TV's screensaver (`dreamx`) was installed from Play as a normal app, without stock's privileged permissions, and Android still ran the old one.
- **Fix:** ship `dreamx` from your stock image as a privileged app, with its stock permission list, and remove `Backdrop`.
- **Then update it from the Play Store.** Stock's version 3.2 logs `Binding to mediashell failed` and `JWT token not available` against the newer Cast app.
- **To select it by hand**, which a wipe clears, because the build doesn't make it the default yet:

```bash
adb shell settings put secure screensaver_components com.google.android.apps.tv.dreamx/.service.Backdrop
```

This was tested over existing data, without a wipe.

## Keeping the unlock

### Factory reset relocks the device

- **Cause:** `ChromecastDevice::PostWipeData()` in stock recovery's `librecovery_ui_ext.so` wipes every partition in `ro.odm.fdr.extra_wipe_partitions=cri_data,env,param,tee`. The unlock lives in `env`.
- **Fix:** the Lineage-style recovery uses Lineage's default plugin, which has no such wipe, and the property is removed.
- **Evidence:** from reading the code only. No real reset has been run.

## Debugging notes

A silent hang leaves no logs, so diagnosis needed a way to capture them. `patches/diagnostic/` adds a thread in `init` that logs each boot stage, copies logcat into the kernel log, and warm-reboots to the bootloader. The kept logs can then be read from a RAM-booted stock debug image.

**Don't ship those patches.** Remove them before building anything for daily use.

Each of these caused a misleading failure while building it:

- Init has to be single-threaded at `Service::CreateSigchldFd()`, so start any thread after `InstallSignalFdHandler`.
- A thread sharing init's mount namespace makes `setns()` fail in `enter_default_mount_ns`, which breaks APEX library loading in confusing ways. Call `unshare(CLONE_NEWNS)` first, as bootchart does.
- The bootloader injects `androidboot.selinux=enforcing`, and the first value wins. Use a separate key to test permissive.
- `/dev/kmsg` rejects large writes, so forward logcat line by line.
- `fastboot -w` also clears saved ADB keys, so use an open debug image for capture.
