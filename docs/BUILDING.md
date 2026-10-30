# Building

> **Expect to adapt things.** The tested images were made by building a system image and then editing it with scripts, not by one clean build. The late fixes are included here as source changes, but **this exact tree hasn't been through a full build and boot test.** See [the scripts README](../scripts/README.md).

## What you'll need

- Linux or WSL2, with about 500 GB free
- At least 16 GB of RAM plus swap. A 15 GB VM with no swap hung during the build, so add about 25 GB of swap
- `repo` and the [AOSP build dependencies](https://source.android.com/docs/setup/start/requirements)
- Your own copy of the stock OTA for `UTTC.250917.004`, linked from the [unlock project](https://github.com/oddsolutions/sabrina-unlock-v2)

## 1. Get the source

The tree combines AOSP tag `android-16.0.0_r4` with LineageOS `lineage-23.2`, pinned in [`manifests/`](../manifests).

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

This skips `patches/diagnostic/`, the boot watchdog and logging used for debugging, and `patches/kernel/`, which step 6 uses.

## 4. Extract the proprietary files

From your stock OTA, extract `system`, `vendor` and `product`, then run:

```bash
/path/to/this/repo/scripts/extract-proprietary.sh /path/to/stock/product device/google/sabrina16/proprietary
```

This copies the Google TV launcher, its screensaver and Gboard for TV into the tree. **Don't commit or publish these.** `.gitignore` excludes them.

## 5. Build the system image

```bash
source build/envsetup.sh
source vendor/lineage/vars/aosp_target_release
lunch lineage_gsi_sabrina16 "$aosp_target_release" user
m -j4 systemimage checkvintf lpmake lpdump
```

Sign the build with your own keys before you use it. See [SIGNING.md](SIGNING.md).

## 6. Build the kernel

The stock kernel lacks `CONFIG_DM_DEFAULT_KEY`, which Android 16's storage needs.

1. Fetch the sources for stock kernel `5.15.170-android14-11-gf4a1f03072af`: [`kernel/common`](https://android.googlesource.com/kernel/common) at `f4a1f03072af`, and the [Amlogic driver repo](https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver) from Google's [Nest open-source manifests](https://nest-open-source.googlesource.com/manifests/).
2. Use clang `r487747c` and pahole 1.23.
3. Apply the Amlogic patch set, then the two patches in [`patches/kernel/`](../patches/kernel).
4. Enable `CONFIG_DM_DEFAULT_KEY=y` on top of the stock config.
5. Check that module symbol CRCs still match stock, so the stock vendor modules keep loading. That's why the ABI patch exists.

Reference scripts: `scripts/pipeline/prepare_kernel_*.py` and `start_kernel_*.py`.

## 7. Assemble the images

The device needs matching `boot`, `super` and `vbmeta`:

| Image | How it's made |
|---|---|
| boot | Stock boot with your kernel, and a first-stage fstab without the `/product` entry |
| vendor | Stock vendor plus [`vendor-config/cgroups.json`](../device/google/sabrina16/vendor-config/cgroups.json) at `/etc/cgroups.json` (mode 0644, label `vendor_cgroup_desc_file`), plus the sepolicy and fstab adjustments |
| super | `lpmake` with the settings below. Partitions: system, vendor, product, odm, system_dlkm |
| vbmeta | Signed with your key, rollback index 0, flags 0 |

`lpmake` settings: size `2084569088`, metadata size `65536`, 2 slots, group `amlogic_dynamic_partitions` of `2080374784` bytes, block size 4096.

Reference scripts: `prepare_development_images.py`, `assemble_development_super.py` and `prepare_sparse_transfer.py`, in `scripts/pipeline/`. If you edit images instead of changing source, `prepare_watchdog_images.py` shows each edit.

**Partition sizes:**

| Partition | Bytes |
|---|---|
| super | 2,084,569,088 |
| boot | 16,777,216 |
| vbmeta | 2,097,152 |
| recovery | 25,165,824 |

## Optional: build in Play updates

To avoid updating Google's apps after every wipe, you can build your own device's Play versions into the system image. `prepare_watchdog_images.py` does this after pulling them with `adb pull`. Watch out for these:

- **Permissions:** Android enforces its privileged-permission allowlist for built-in apps, but not for Play updates, so generate entries for each app. A missing entry can stop the device booting.
- **Native libraries:** apps without `extractNativeLibs=false` need their libraries unpacked to `lib/arm/`.
- **Space:** grow the system image. The 11 apps here took about 417 MB, and `super` had about 280 MB spare.
- **Publishing:** Play's split APKs match one device's language and screen density, so build your own and **never publish them**.

## Before sharing a build

Remove the diagnostic code and test with SELinux enforcing. Don't redistribute images that contain Google's apps or vendor files.
