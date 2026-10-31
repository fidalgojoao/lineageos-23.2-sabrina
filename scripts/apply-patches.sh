#!/usr/bin/env bash
# Apply this repository's release patches to an Android source tree.
# Patches in patches/diagnostic and patches/kernel are not applied here.
set -euo pipefail

usage() { echo "usage: $0 /path/to/android-source" >&2; exit 2; }
[ $# -eq 1 ] || usage
tree=$1
[ -d "$tree/.repo" ] || { echo "error: $tree is not a repo checkout" >&2; exit 1; }
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

apply() {
    local project=$1 patch=$2
    echo ">> $project: $(basename "$patch")"
    git -C "$tree/$project" apply --check "$patch"
    git -C "$tree/$project" apply "$patch"
}

apply frameworks/base "$here/patches/frameworks_base/0001-sabrina-ota-wipe-guard-and-privacy.patch"
apply frameworks/base "$here/patches/frameworks_base/0002-sabrina-hdmi-audio-and-remote-keys.patch"
apply bootable/recovery "$here/patches/bootable_recovery/0001-allow-install-anyway-on-user-builds.patch"
apply system/sepolicy "$here/patches/system_sepolicy/0001-sabrina-policy-integration.patch"
apply vendor/lineage "$here/patches/vendor_lineage/0001-build-manifest-sandbox.patch"
apply packages/modules/AdServices "$here/patches/packages_modules_AdServices/0001-privacy-kill-switches.patch"
apply packages/modules/OnDevicePersonalization "$here/patches/packages_modules_OnDevicePersonalization/0001-privacy-kill-switches.patch"
apply device/google/atv "$here/patches/device_google_atv/0001-remove-emulator-setup-props.patch"
apply packages/modules/Wifi "$here/patches/packages_modules_Wifi/0001-hidden-network-scan.patch"
apply frameworks/base "$here/patches/frameworks_base/0003-advanced-restart-and-local-update-guard.patch"
apply packages/apps/TvSettings "$here/patches/packages_apps_TvSettings/0001-buttons-battery-and-oem-text.patch"
apply packages/apps/Updater "$here/patches/packages_apps_Updater/0001-local-only-tv-updater.patch"
echo "done"
