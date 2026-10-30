"""Apply optional-advertising/analytics opt-outs without disabling core Google services."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
MARKER = 'ro.build.privacy_minimized'
changed = []


def edit(path, old, new, marker):
    text = path.read_text()
    if marker in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'Unexpected source, review before editing: {path}')
    backup = BASE / 'privacy-source-backup' / path.relative_to(SOURCE)
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        backup.write_text(text)
    path.write_text(text.replace(old, new, 1))
    changed.append(str(path.relative_to(SOURCE)))


pm = SOURCE / 'frameworks/base/services/core/java/com/android/server/pm'
anchor = '''        if (pkgSetting.isSystem()) {
            configurePackageComponents(parsedPackage);
        }
'''
replacement = '''        // Apply supported optional-telemetry SDK opt-outs at every package scan,
        // including newly installed/updated apps. Do not disable Firebase messaging/auth.
        if (SystemProperties.getBoolean("ro.build.privacy_minimized", false)
                && parsedPackage instanceof com.android.internal.pm.parsing.pkg.PackageImpl) {
            final android.os.Bundle privacyMetadata = parsedPackage.getMetaData() == null
                    ? new android.os.Bundle() : new android.os.Bundle(parsedPackage.getMetaData());
            PrivacyMetadataPolicy.apply(privacyMetadata::putBoolean);
            ((com.android.internal.pm.parsing.pkg.PackageImpl) parsedPackage)
                    .setMetaData(privacyMetadata);
        }

''' + anchor
edit(pm / 'ScanPackageUtils.java', anchor, replacement, MARKER)
helper = pm / 'PrivacyMetadataPolicy.java'
if not helper.exists() or helper.read_bytes() != (BASE / 'framework/PrivacyMetadataPolicy.java').read_bytes():
    shutil.copyfile(BASE / 'framework/PrivacyMetadataPolicy.java', helper)

# Keep framework/APEX libraries and SDK Sandbox present. Only optional advertising,
# on-device personalization and federated-compute functionality is killed.
flags = {
    'packages/modules/AdServices/adservices/service-core/java/com/android/adservices/service/PhFlags.java':
        ['getGlobalKillSwitch', 'getAdIdKillSwitch', 'getAppSetIdKillSwitch'],
    'packages/modules/OnDevicePersonalization/src/com/android/ondevicepersonalization/services/PhFlags.java':
        ['getGlobalKillSwitch'],
    'packages/modules/OnDevicePersonalization/federatedcompute/src/com/android/federatedcompute/services/common/PhFlags.java':
        ['getGlobalKillSwitch'],
}
for relative, methods in flags.items():
    for method in methods:
        header = f'    public boolean {method}() {{\n'
        marker = f'// Sabrina privacy policy: {method}'
        inserted = header + f'''        {marker}
        if (android.os.SystemProperties.getBoolean("{MARKER}", false)) {{
            return true;
        }}
'''
        edit(SOURCE / relative, header, inserted, marker)

contexts = SOURCE / 'system/sepolicy/private/property_contexts'
rule = f'{MARKER} u:object_r:build_prop:s0 exact bool'
text = contexts.read_text()
if rule not in text:
    contexts.write_text(text.rstrip() + '\n\n# Custom Sabrina optional telemetry policy.\n' + rule + '\n')

classes = BASE / 'privacy-host-test-classes'
classes.mkdir(exist_ok=True)
jdk = SOURCE / 'prebuilts/jdk/jdk21/linux-x86/bin'
subprocess.run([str(jdk / 'javac'), '-d', str(classes), str(helper),
                str(BASE / 'framework/PrivacyMetadataPolicyHostTest.java')], check=True)
subprocess.run([str(jdk / 'java'), '-cp', str(classes),
                'com.android.server.pm.PrivacyMetadataPolicyHostTest'], check=True)
report = {'newly_changed_source_files': changed,
          'advertising_personalization_kill_switch_methods': flags,
          'metadata_helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
          'host_metadata_tests_passed': True, 'runtime_verified': False,
          'preserved': ['Play services APK updates', 'Play Store APK installs/updates',
                        'Firebase messaging/global Firebase defaults', 'Google sign-in and integrity',
                        'Cast/Assistant components', 'system/APEX framework libraries'],
          'limits': ['Does not eliminate all Google or application-owned network telemetry.',
                     'Crashlytics default can be overridden by an app at runtime.',
                     'Future replacement APEX modules may not contain these custom kill-switch guards.',
                     'Compatibility and traffic tests remain necessary.']}
(BASE / 'privacy-framework-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'host_metadata_tests_passed': True, 'runtime_verified': False}))
