# SELinux policy migration review

Written 29 October 2026. This is a technical record for anyone continuing the SELinux work.

## Summary

- **Done:** the vendor policy was moved to Android 16's policy API, and it compiles with zero assertion failures and passes the upstream checks.
- **Not done:** it hasn't been put into real images or run on a device. **This doesn't prove it works, and isn't approval to flash it.** The builds tested on the device are still permissive.

## Why the policy had to be ported

The Android 14 platform export contains platform permissions and rules, not just declarations. Keeping it next to the Android 16 platform creates contradictions, such as old bans on the APEX metadata access that current APEX needs. Deleting the current permissions to silence those errors would be wrong.

So the port:

- generates the current public export from the real system, system_ext and product sources (user variant), using the real `version_policy` compiler with API 202504
- keeps old API-34 types available through a compatibility bridge
- replaces the old export's 1,714 `neverallow`, 168 `neverallowx`, 4,694 `allow` and 144 `allowx` rules, plus their audit rules, with the generated policy. These are **not** claimed to mean the same thing

**Nothing was weakened to reach zero failures:**

- All current platform assertions, the 429 generated public assertions and the 39 original vendor-private assertions are on and unmodified.
- Compiler `-N` isn't used, and there's no permissive domain or conditional boolean.
- The old mixed-API test still has 44 failures, and is kept as evidence. The zero comes from the strict migrated test, not from relabelling that one.

## What changed for vendor permissions

**Allow rules:** the 3,060 original vendor-private allow rules stay, with three target changes. `hdcp_tx22`, `mediacodec` and `system_control` keep their `oemfs` permissions, but no longer reach the new `bootanim_oem_file` label, used by the three OEM animation ZIP paths.

**Classification repairs:**

- New animation files stay out of filesystem attributes.
- Vendor VM data stays out of the read-only vendor-code attribute.
- Framework biometric properties stay out of vendor-internal property attributes.

The old export and the vendor CIL both duplicate these sets, so both copies have to be handled. Effective permissions do change, so keeping the `allow` lines isn't proof of equal behaviour.

**New mapping entries**, all new objects rather than permission exceptions, with no references in the original vendor policy:

| Object | Owner |
|---|---|
| `repair_mode_metadata_file` | Framework repair metadata |
| `vendor_persist_camera_prop` | Lineage camera package lists |
| `vendor_always_on_prop` | Lineage TV backlight animation |

## Evidence

| Report | Result |
|---|---|
| `vendor-api-migration-experiment.json` | Strict merge succeeds with zero assertion failures. Binary: 828,671 bytes, SHA256 `a4932e746a74af2f15a78cc7eec59bb3e56477f57cb5361e5fe14a3b7af5c3c4` |
| `migrated-policy-validation.json` | Upstream structural tests, the API-34 mapping inventory, and the no-permissive and no-boolean checks pass. It used existing image contexts, so repeat it with the final user build's |
| `vendor-effective-permission-audit.json` | Compares stock and migrated `allow` permissions for all 105 vendor-owned domains. Ordinary character and block device permissions have no reductions |

These reports aren't in this repository.

**Permissions that were reduced:**

- All 105 domains lose the obsolete `task_profiles_api_file` label and overbroad vendor VM data access.
- Four radio and network domains lose `module_request`.
- Two face and GNSS domains lose `servicemanager` FD use.
- Netflix loses legacy keystore and cgroup permissions.

Framework grants add updated cgroup, configuration and memory interfaces. Don't automatically restore old permissions or remove new ones just to match the old binary. Kernel module loading, Netflix and DRM, and resource profiles need testing on a device.

**The audit doesn't cover:** extended ioctl whitelists, constraints, file and property relabelling, runtime services or Google certification. Vendor `allowx` statements are preserved, but that isn't a full ioctl comparison.

## What's left

1. Build the matching user system image, and regenerate the export and bridge from its exact CIL files.
2. Install matching vendor policy and version metadata, and prevent stale precompiled policy being reused. The staging script, `prepare_release_vendor_policy.py`, has only been syntax-checked, and isn't in this repository.
3. Update the vendor manifest so that it and `plat_sepolicy_vers.txt` both say `202504`. Keep the original HAL entries and vendor OS and FCM levels. The kernel's binary policy format stays at 30.
4. Re-run the strict merge and the structural and mapping checks on the final images, with real labels.
5. Run CTS `neverallow` checks where available.
6. Run full `checkvintf` with the real kernel and final vendor tree.
7. Confirm the remaining pieces: the kernel with its matching fstabs, vendor filesystem metadata, AVB signatures and rollback, the super layout, USB recovery, and a bounded install and rollback sequence.
8. Keep the original images throughout.
