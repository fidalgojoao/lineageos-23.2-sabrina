# What was broken and why

Each entry here was diagnosed from device logs or source, and fixed. These notes may help with other ports to old-launch Android TV devices.

## Bootloop: mandatory `schedtune` cgroup

- **Symptom:** repeated reboots about 18 seconds in.
- **Cause:** the device launched at API 29, so Android 16 picks an old cgroup description where `schedtune` is mandatory. Kernel 5.15 doesn't have it. Cgroup setup aborts, `ueventd` and `apexd-bootstrap` can't start, and init reboots.
- **Fix:** [`vendor-config/cgroups.json`](../device/google/sabrina16/vendor-config/cgroups.json) makes that one controller optional.

## Static logo: GPU driver never loaded

- **Symptom:** the bootloader logo stays on forever.
- **Cause:** `ro.board.platform=sabrina` makes Android 16's EGL loader try `libGLES_sabrina.so`. When that fails, it sets a flag that **skips its wildcard search**, so `libGLES_mali.so` is never found. SurfaceFlinger aborts with `couldn't find an OpenGL ES implementation`, and it and zygote restart forever.
- **Fix:** `ro.hardware.egl=mali`.

## Google sign-in returning to the home screen

- **Symptom:** "Set up Google TV" bounces back home.
- **Cause:** `TvProvision` and `LineageSetupWizard` were present alongside Google's `SetupWraith`. Android logs `There should probably be exactly one setup wizard; found 2` and recognises none, so `SetupWraith` isn't granted the setup-only `NETWORK_SETUP_WIZARD` permission. It then crashes in `WifiServiceImpl.getCurrentNetwork`.
- **Fix:** remove both extra setup apps.

## First-boot setup skipped

- **Cause:** `ro.setupwizard.mode=DISABLED`, inherited from `atv_emulator_vendor.mk`.
- **Fix:** remove it. This patch also sets `PRODUCT_CHARACTERISTICS` to stock's `tv,nosdcard`, where the same file had set `emulator`.

## Remote needing the two-button press after every reboot

- **Symptom:** the pairing survives, but the remote only reconnects after holding its two pairing buttons.
- **Cause (best supported by testing):** stock sets `bluetooth.core.le.privacy.apply_identity_addr_after_paired=true`, but that property doesn't exist in Android 16's Bluetooth source. The Chromecast keeps a rotating private address, so the remote's normal wake-up signal appears to get ignored. Pairing mode broadcasts to everyone, so that still worked.
- **Fix:** `bluetooth.core.gap.le.privacy.enabled=false`, which uses the public address. The remote then survived reboots. The cost is that its Bluetooth address no longer rotates.
- **Related:** the Bluetooth device class was also restored to stock's `44,4,32`.

## Old keyboard

- **Cause:** only Leanback was included. Stock ships `LatinIMEGoogleTvPrebuilt` (Gboard for TV).
- **Fix:** add Gboard from your stock image, and remove Leanback.

## Wi-Fi slow to reconnect, or asking for the password again

- **Symptom:** after a reboot, Wi-Fi took minutes to come back, or didn't return until the password was entered again.
- **Cause (best supported by testing):** stock's `SabrinaWifiOverlayGoogle` targets `com.google.android.wifi.resources`, but this build's package is `com.android.wifi.resources`, so its values were missing. Android's defaults disable a network indefinitely after a password failure or a permanent no-internet result, and allow temporary disables of up to 18 hours. Stock uses 60 seconds and 5 minutes.
- **Fix:** [`rro/SabrinaWifiOverlay`](../device/google/sabrina16/rro/SabrinaWifiOverlay) applies stock's values to the right package.
- **Result:** on the reboot measured after the fix, the first scan to connection took about 7 seconds, compared with 94 before. That's one reboot, on one router, so more testing is welcome.
- **Red herring:** `Failed to set DFS flag` also appears on stock, so it isn't the cause.

## Screensaver settings: "Unable to load content"

- **Symptom:** Google TV's screensaver settings show an error, and Google Photos isn't used.
- **Cause:** the build shipped an older `Backdrop` app and no `TVDreamXPrebuilt`. Google TV's screensaver (`dreamx`) was installed from Play as a normal app, without stock's privileged permissions, and Android still ran the old one.
- **Fix:** ship `dreamx` from your stock image as a privileged app, with its stock permission list, and remove `Backdrop`.
- **To set it by hand:** `adb shell settings put secure screensaver_components com.google.android.apps.tv.dreamx/.service.Backdrop`. A wipe clears this, and the build doesn't yet make it the default.
- **Then update it:** the screensaver only worked after updating it from the Play Store. Stock's version 3.2 logs `Binding to mediashell failed` and `JWT token not available` against the newer Cast app.
- **Note:** this was installed over existing data without a wipe.

## Kernel storage feature

- **Cause:** the Android 16 storage path needs `CONFIG_DM_DEFAULT_KEY`, which the stock kernel lacks, and enabling it naively shifts the kernel ABI that stock vendor modules depend on.
- **Fix:** [`patches/kernel/kernel-dm-default-key-kabi.patch`](../patches/kernel/kernel-dm-default-key-kabi.patch) moves the new field into a reserved slot, preserving the module ABI.

## Factory reset relocking the device

- **Cause:** `ChromecastDevice::PostWipeData()` in stock recovery's `librecovery_ui_ext.so` wipes every partition listed in `ro.odm.fdr.extra_wipe_partitions=cri_data,env,param,tee`. The unlock lives in `env`.
- **Fix:** the Lineage-style recovery uses Lineage's default plugin, which has no such wipe, and the property is removed. Static evidence only: no real reset has been run.

## YouTube limited to 360p

- **Cause:** the build reported a generic device.
- **Fix:** `ro.product.product.device=sabrina` and `ro.product.product.model=Chromecast`. Confirmed by the user on a monitor and a TV.

## TV volume and Input through the remote

- **Cause:** stock's `TVAxel` (Android TV Infrared Service) was missing, so the remote couldn't be set up to send IR. CEC volume went to the soundbar, which acknowledged it and ignored it.
- **Fix:** include `TVAxel`, its overlay and stock's permission entries, then run the setup. Stock links the menu from `ChromecastServiceAml`, so `SabrinaTvSettingsOverlay` fills TV Settings' own `bluetooth_ir_entry_slice_uri` slot instead.
- **Also:** audio only reached HDMI after `patches/frameworks_base/0002` reported Amlogic's extcon state.

## Holding Home opened the assistant

- **Cause:** LineageOS's own key handler uses its action list, where `3` means search. Separately, `TvFrameworkOverlay` sets a `large` value that wins on TVs, and `ATVOverlay` points the panel at the wrong package.
- **Fix:** `patches/frameworks_base/0002` honours stock's panel setting, and `SabrinaFrameworkOverlay` sets both values. Build it with `aapt2 --no-resource-deduping`, or the `large` copy is dropped.

## Wi-Fi settings that differ from stock

Stock's `com.google.android.wifi` sets `config_wifi_background_scan_support` true, `config_wifiSaeUpgradeEnabled` false and `config_wifiVerboseLoggingAlwaysOnLevel` 0. `SabrinaWifiOverlay` now matches. This hasn't been shown to solve slow reconnects.

## Debugging notes

A silent hang leaves no logs, so diagnosis needed a way to capture them. `patches/diagnostic/` adds a thread in `init` that logs each boot stage, dumps logcat into the kernel log, and warm-reboots to the bootloader. Retained logs can then be read from a RAM-booted stock debug image.

Lessons from building it, each of which caused a misleading failure:

- Init requires being single-threaded at `Service::CreateSigchldFd()`, so start any thread after `InstallSignalFdHandler`.
- A thread sharing init's mount namespace makes `setns()` fail in `enter_default_mount_ns`, which breaks APEX library loading in confusing ways. Call `unshare(CLONE_NEWNS)` first, as bootchart does.
- The bootloader injects `androidboot.selinux=enforcing`, and the first value wins. Use a separate key to test permissive.
- `/dev/kmsg` rejects large writes, so forward logcat line by line.
- `fastboot -w` also clears saved ADB keys, so use an open debug image for capture.

Don't ship those patches. Remove them before building anything for daily use.
