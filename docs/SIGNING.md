# Signing with your own keys

> **Status:** the tested build used LineageOS `test-keys` and a development AVB key. `scripts/pipeline/sign_target_files_release.py`, `apply_release_signing.py` and `prepare_recovery_menu.py` have produced release-signed images that passed offline checks, but **those images haven't been booted yet**.
>
> **Use your own keys.** This repository has no release keys and never will. Every builder generates their own, keeps them private and backs them up. Set `SABRINA_KEY_BACKUP` to a private folder outside any repository before running the signing script, and `SABRINA_SERIAL` to your device's serial for the flash scripts.

Don't ship `test-keys` builds. Those keys are public, so anyone could sign an app that the system trusts.

## What signing does and doesn't do

- **It does** protect your platform apps and make the build report `release-keys`.
- **It doesn't** make the device Google-certified, or help with Play Integrity or DRM.
- **Google's apps keep Google's signatures.** They have to, so they're excluded from re-signing. Their signatures are what let them update through Play.
- **Changing keys needs a wipe.** Use `fastboot -w` when you first switch. See [RISKS.md](RISKS.md).

## 1. Generate release keys

```bash
subject='/C=XX/ST=Unknown/L=Unknown/O=Your Name/OU=Personal/CN=Your Name'
mkdir -p ~/.android-certs
for key in releasekey platform shared media networkstack sdk_sandbox bluetooth nfc; do
  ./development/tools/make_key ~/.android-certs/$key "$subject"
done
```

Your exact key list depends on the tree, so check the `*.x509.pem` files in `build/make/target/product/security/` and any APEX keys.

Set a strong password when prompted, and store the keys **outside** the source tree.

## 2. Generate an AVB key

```bash
openssl genrsa -out ~/.android-certs/avb.pem 4096
external/avb/avbtool.py extract_public_key --key ~/.android-certs/avb.pem --output ~/.android-certs/avb_pkmd.bin
```

The bootloader is unlocked, so it doesn't check this key against a trusted one. The device boots in the `orange` state either way. The key still has to match across your images, because `vbmeta` must correctly describe each partition. The vendor fstab's `avb_keys` entry must also list your public key, which the tested build did with its development key.

## 3. Sign the target files

The product currently disables most images, so you'll need to allow `target-files-package` to build.

```bash
m target-files-package otatools
sign_target_files_apks -o \
  -d ~/.android-certs \
  out/target/product/generic/obj/PACKAGING/target_files_intermediates/*-target_files*.zip \
  signed-target-files.zip
```

Keep Google's prebuilt APKs out of re-signing. Mark them `PRESIGNED`, or use `-e Package.apk=` for each one.

Then unpack the system image from `signed-target-files.zip`, and continue with step 7 of [BUILDING.md](BUILDING.md).

## 4. Sign and verify the images

```bash
avbtool add_hashtree_footer --image system.img --partition_name system \
  --partition_size 1519427584 --algorithm SHA256_RSA4096 --key ~/.android-certs/avb.pem \
  --rollback_index 0 --hash_algorithm sha256

avbtool make_vbmeta_image --output vbmeta.img --key ~/.android-certs/avb.pem \
  --algorithm SHA256_RSA4096 --rollback_index 0 --flags 0 --padding_size 65536 \
  --include_descriptors_from_image boot.img \
  --include_descriptors_from_image dt.img \
  --include_descriptors_from_image dtbo.img \
  --include_descriptors_from_image odm.img \
  --include_descriptors_from_image product.img \
  --include_descriptors_from_image system.img \
  --include_descriptors_from_image system_dlkm.img \
  --include_descriptors_from_image vendor.img

avbtool verify_image --image vbmeta.img --key ~/.android-certs/avb.pem
```

Sign every partition with the same key, including `boot` and `vendor`. Keep the rollback index at `0`.

## Protect your keys

- **Never commit keys.** `.gitignore` excludes common key files, but check before you push.
- Back them up offline. If you lose them, future builds won't be updates to existing installs without a wipe.
- If a key leaks, generate new ones and wipe.
