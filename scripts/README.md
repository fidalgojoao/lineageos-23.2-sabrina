# Scripts

## Scripts to run

| Script | What it does |
|---|---|
| `apply-patches.sh` | Applies `patches/` to your source tree |
| `extract-proprietary.sh` | Copies the launcher, screensaver and Gboard from your own stock `product` image |

## `pipeline/`: for reference only

These are the scripts used during development, with personal details replaced by placeholders. **They aren't a one-click build.** They expect paths such as `/opt/sabrina/android16`, read each other's JSON status files, and include checks tied to exact hashes from one device. Use them as a record of what was done, and adapt them.

Before running one:

- Replace `YOUR_DEVICE_SERIAL` and `/path/to/project` with your own values.
- Set `SABRINA_SERIAL`, and `SABRINA_KEY_BACKUP` for signing.
- Read the whole script, especially anything that flashes.

| Scripts | What they're for |
|---|---|
| `prepare_kernel_*`, `start_kernel_*`, `fetch_kernel_reference.py` | Kernel sources and build |
| `apply_ota_guard.py`, `apply_privacy_policy.py`, `generate_*_overrides.py`, `check_*.py` | OTA and privacy changes, and their checks |
| `apply_hdmi_cec_fixes.py`, `apply_home_long_press.py` | HDMI, audio and remote-button fixes |
| `prepare_development_images.py`, `prepare_cgroup_fixed_images.py` | Boot, vendor and vbmeta assembly |
| `assemble_development_super.py`, `prepare_sparse_transfer.py`, `check_sparse_chunk_transfer.py` | Super image and transfer checks |
| `prepare_watchdog_images.py` | The post-build edits that produced the tested image |
| `build_target_files.py`, `sign_target_files_release.py`, `apply_release_signing.py` | Release signing |
| `build_recovery_*.py`, `prepare_recovery_menu.py`, `apply_recovery_install_anyway.py`, `flash_recovery_image.py` | Lineage-style recovery |
| `apply_tv_features.py`, `apply_updater_tv_picker.py`, `apply_accessory_battery.py` | Advanced restart, the local Updater and remote battery |
| `apply_remote_wake.py`, `apply_input_button.py` | Remote buttons that wake the TV, and the Input button switch |
| `update_release_set.py`, `make_local_update.py` | Update a signed image set, and build a zip for the Updater |
| `watchdog_trial.py`, `capture_failed_diagnostic_boot.py`, `make_debug_boot.py` | Flashing, restoring and capturing logs |
