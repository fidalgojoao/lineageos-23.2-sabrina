# Scripts

## Use these

| Script | Purpose |
|---|---|
| `apply-patches.sh` | Applies `patches/` to your source tree |
| `extract-proprietary.sh` | Copies the launcher and Gboard from your own stock `product` image |

## `pipeline/`: reference only

These are the scripts used during development, with personal details replaced by placeholders. **They aren't a turnkey build.** They expect specific paths such as `/opt/sabrina/android16`, read each other's JSON status files, and include checks tied to exact hashes from one device. Treat them as a record of what was done, and adapt them.

Replace `YOUR_DEVICE_SERIAL` and `/path/to/project` with your own values. Read a script fully before you run it, especially anything that flashes.

| Scripts | Purpose |
|---|---|
| `prepare_kernel_*`, `start_kernel_*`, `fetch_kernel_reference.py` | Kernel sources and build |
| `apply_ota_guard.py`, `apply_privacy_policy.py`, `generate_*_overrides.py`, `check_*.py` | OTA and privacy changes, and their checks |
| `prepare_development_images.py`, `prepare_cgroup_fixed_images.py` | Boot, vendor and vbmeta assembly |
| `assemble_development_super.py`, `prepare_sparse_transfer.py`, `check_sparse_chunk_transfer.py` | Super image and transfer checks |
| `prepare_watchdog_images.py` | Post-build edits that produced the tested image |
| `watchdog_trial.py`, `capture_failed_diagnostic_boot.py`, `make_debug_boot.py` | Flash, restore and log capture |
