# Sabrina policy API migration review — 29 October 2026

Status: isolated source/API migration passes strict compilation and upstream
structural/mapping tests. Actual release images and vendor integration are
unfinished. This does not approve a flash or prove hardware operation.

## Why this is a new policy port

The original Android 14 platform export includes platform permissions and
constraints, not just declarations. Retaining that export unchanged alongside
the Android 16 platform creates contradictions, including old prohibitions on
APEX metadata access that current APEX operation requires. Removing the needed
current permissions would be an incorrect way to obtain zero.

The new experiment generates the complete current public export from the actual
system, system_ext and product source recipes in user variant, using the real
version_policy compiler with API 202504. Old API-34 type imports remain available
through a compatibility bridge. The report explicitly inventories the replaced
old export: 1,714 neverallow, 168 neverallowx, 4,694 allow and 144 allowx rules,
plus their audit rules. They are replaced by current source-generated platform
policy; they are not claimed to be unchanged or semantically identical.

All current platform assertions, the freshly generated 429 public assertions
and all 39 original vendor-private assertions are enabled and unmodified.
Compiler -N is absent. No permissive domain or conditional boolean is present.
The historical mixed-API test still has 44 failures and is retained as evidence.
The zero is the strict migrated-API result, not a relabeling of that old test.

## Retained vendor permissions and scoped label repair

The 3,060 original vendor-private allow rules remain, with precisely three
target changes: hdcp_tx22, mediacodec and system_control keep their original
permission bits for oemfs. Their old versioned target also mapped to the newly
introduced bootanim_oem_file label. Only that new label, used by the three
OEM animation ZIP paths, is excluded. OEM access is retained.

The earlier classification repair keeps new animation files out of filesystem
attributes, vendor VM data out of the read-only vendor-code attribute, and
framework biometric properties out of vendor-internal property attributes.
Both old export and vendor CIL duplicate these old classification sets, so both
copies must be handled. Effective permissions change; literal preservation of
allow statements alone is not presented as proof of equivalent operation.

The three additional mapping inventory entries have documented source ownership
and no original captured public/private vendor references. They are actual new
objects, not permission exceptions: repair_mode_metadata_file (framework repair
metadata), vendor_persist_camera_prop (Lineage camera package lists), and
vendor_always_on_prop (Lineage TV backlight animation). Existing upstream and
Lineage compatibility inventories cover the other new objects. Original type
mappings and removed-type declarations remain included transitively.

## Validation evidence

- vendor-api-migration-experiment.json: strict current-API merge succeeds with
  zero assertion failures. The resulting binary is 828,671 bytes, SHA256
  a4932e746a74af2f15a78cc7eec59bb3e56477f57cb5361e5fe14a3b7af5c3c4.
- migrated-policy-validation.json: all upstream structural tests, API-34 mapping
  inventory, no-permissive and no-boolean checks pass. Existing image contexts
  were used; repeat with matching final user-build contexts.
- vendor-effective-permission-audit.json: compares actual stock and migrated
  binary ordinary allow permissions for all 105 vendor-owned domains, using
  separate processes to avoid the upstream query class's shared rule cache.
  Ordinary character/block device permissions have no reductions.

All 105 domains lose access to the obsolete task_profiles_api_file label and
overbroad vendor VM data access. Other reductions are module_request for four
radio/network domains, servicemanager FD use for two face/GNSS domains, and
Netflix legacy keystore/cgroup permissions. Current framework grants add updated
cgroup/configuration and memory interfaces. Do not automatically restore old
privileges or remove new permissions to reproduce the old binary. Kernel module
loading, Netflix/DRM and resource-profile behavior need runtime tests.

The ordinary-allow audit does not check effective extended-ioctl whitelists,
constraints, file/property relabeling, runtime services or Google certification.
Original vendor explicit allowx statements are preserved by the narrowly scoped
transformation, but that alone is not a full effective ioctl comparison.

## Integration still required

prepare_release_vendor_policy.py prepares the reproducible actual-build staging
step and refuses an unfinished or hash-mismatched release. Its source has been
syntax-checked; it has not yet been executed against a completed release image.
The vendor manifest must describe the migrated public API consistently with
plat_sepolicy_vers.txt: both become 202504. libvintf's SepolicyVersion parser
supports plain YYYYMM and the actual generated framework matrix lists 202504;
the kernel's compiled binary policy format remains 30. Preserve the original
HAL entries and vendor OS/FCM levels. Validate the actual changed manifest through
full checkvintf with the selected kernel, not only this source inspection.

Complete the matching user system image, regenerate the export and bridge
against those exact shipping CIL inputs, install matching vendor public-version
metadata and policy, and prevent stale precompiled policy reuse. Re-run strict
merge and structural/mapping checks on the integrated images and real labels.
Run independent CTS neverallow checks where available. Verify VINTF using the
selected real kernel and actual final vendor tree. Preserve original images.

The separate GSI-mount boot component changes the kernel and one first-stage
fstab entry; its matching vendor fstab is required. Final vendor filesystem
metadata, AVB signatures/rollback strategy, super layout, USB recovery and the
bounded installation/rollback sequence remain gates. No device modifications
are part of this offline review.
