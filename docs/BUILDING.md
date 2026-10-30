# Building

> **Expect to adapt things.** The tested images were made by building a system image and then editing it through an image pipeline, not by one clean build. The final device tree here includes those late fixes as source changes, but **that exact tree hasn't yet been through a full build and boot test.** See [the scripts README](../scripts/README.md).

## Requirements

- A Linux build host, or WSL2, with about 500 GB free
- At least 16 GB of RAM plus swap. Soong hung a 15 GB VM with no swap, so add about 25 GB
- `repo`, and the [AOSP build dependencies](https://source.android.com/docs/setup/start/requirements)
- Your own copy of the stock OTA for `UTTC.250917.004`, linked from the [unlock project](https://github.com/oddsolutions/sabrina-unlock-v2)

## 1. Get the source

The tested tree combines AOSP tag `android-16.0.0_r4` with LineageOS `lineage-23.2`, pinned in [`manifests/`](../manifests).

```bash
mkdir android16 && cd android16
repo init -u https://github.com/LineageOS/android.git -b lineage-23.2
cp /path/to/this/repo/manifests/platform-manifest-pinned.xml .repo/manifests/sabrina-pinned.xml
repo init -m sabrina-pinned.xml
mkdir -p .repo/local_manifests
cp /path/to/this/repo/manifests/gapps-local-manifest.xml .repo/local_manifests/
repo sync -c -j4
```

The local manifest adds [MindTheGapps' `vendor_gapps_tv`](https://github.com/MindTheGapps/vendor_gapps_tv), which supplies the Google apps. Those files come from that project, not this one.

## 2. Add the device tree

```bash
cp -r /path/to/this/repo/device/google/sabrina16 device/google/
```

## 3. Apply the patches

```bash
/path/to/this/repo/scripts/apply-patches.sh "$PWD"
```

Patches in `patches/diagnostic/` aren't applied. They're the boot watchdog and logging used for debugging. See [ROOT-CAUSES.md](ROOT-CAUSES.md).

## 4. Extract the proprietary files

From your stock OTA, extract `system`, `vendor` and `product`, then run:

```bash
/path/to/this/repo/scripts/extract-proprietary.sh /path/to/stock/product device/google/sabrina16/proprietary
```

This copies the Google TV launcher and Gboard for TV into the tree. **Don't commit these or publish them.** The repository's `.gitignore` excludes them.

## 5. Build the system image

```bash
source build/envsetup.sh
source vendor/lineage/vars/aosp_target_release
lunch lineage_gsi_sabrina16 "$aosp_target_release" user
m -j4 systemimage checkvintf lpmake lpdump
```

Before you use the build, sign it with your own keys. See [SIGNING.md](SIGNING.md).

## 6. Build the kernel

The stock kernel lacks `CONFIG_DM_DEFAULT_KEY`, which this Android 16 storage path requires.

1. Fetch the sources for stock kernel `5.15.170-android14-11-gf4a1f03072af`: [`kernel/common`](https://android.googlesource.com/kernel/common) at `f4a1f03072af`, and the [Amlogic driver repo](https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver) from Google's [Nest open-source manifests](https://nest-open-source.googlesource.com/manifests/).
2. Use clang `r487747c` and pahole 1.23.
3. Apply the Amlogic patch set, then the two patches in [`patches/kernel/`](../patches/kernel).
4. Enable `CONFIG_DM_DEFAULT_KEY=y` on top of the stock config.
5. Check that module symbol CRCs still match stock, so the stock vendor modules keep loading. The ABI patch exists for this reason.

Reference scripts: `scripts/pipeline/prepare_kernel_*.py`, `start_kernel_*.py`.

## 7. Assemble the images

A device build needs matching `boot`, `super` and `vbmeta`:

- **boot:** stock boot with your kernel, and a first-stage fstab without the `/product` entry.
- **vendor:** stock vendor plus [`vendor-config/cgroups.json`](../device/google/sabrina16/vendor-config/cgroups.json) at `/etc/cgroups.json` (mode 0644, label `vendor_cgroup_desc_file`), plus the sepolicy and fstab adjustments.
- **super:** `lpmake` with size `2084569088`, metadata size `65536`, 2 slots, group `amlogic_dynamic_partitions` of `2080374784` bytes, block size 4096. Partitions: system, vendor, product, odm, system_dlkm.
- **vbmeta:** signed with your key, rollback index 0, flags 0.

Reference scripts: `scripts/pipeline/prepare_development_images.py`, `assemble_development_super.py`, `prepare_sparse_transfer.py`.

If you use the image pipeline instead of source changes, `prepare_watchdog_images.py` shows each post-build edit.

## Sizes

| Partition | Bytes |
|---|---|
| super | 2,084,569,088 |
| boot | 16,777,216 |
| vbmeta | 2,097,152 |
| recovery (untouched) | 25,165,824 |

## Before publishing a build

Remove the diagnostic code and test with SELinux enforcing. Don't redistribute images that contain Google's apps or vendor files.
