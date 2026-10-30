"""Apply the Sabrina recovery-only OTA guard to the actual Android source tree."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
SERVICE = SOURCE / 'frameworks/base/services/core/java/com/android/server/recoverysystem'
file = SERVICE / 'RecoverySystemService.java'
old = '''    private boolean setupOrClearBcb(boolean isSetup, String command) {
        mContext.enforceCallingOrSelfPermission(android.Manifest.permission.RECOVERY, null);
'''
new = old + '''
        // Firmware OTAs can relock this custom Sabrina installation. App/APEX updates
        // do not use recovery --update_package and remain unaffected.
        final boolean firmwareOtaBlocked = "true".equalsIgnoreCase(
                mInjector.systemPropertiesGet("ro.build.firmware_ota_blocked"));
        if (isSetup && FirmwareOtaPolicy.blocksRecoveryCommand(firmwareOtaBlocked, command)) {
            Slog.w(TAG, "Recovery firmware OTA installation is disabled by this build");
            return false;
        }
'''
text = file.read_text()
if 'FirmwareOtaPolicy.blocksRecoveryCommand' not in text:
    if text.count(old) != 1:
        raise RuntimeError('Unexpected recovery service source; review before patching')
    (BASE / 'RecoverySystemService.original.java').write_text(text)
    file.write_text(text.replace(old, new, 1))
shutil.copyfile(BASE / 'framework/FirmwareOtaPolicy.java', SERVICE / 'FirmwareOtaPolicy.java')

contexts = SOURCE / 'system/sepolicy/private/property_contexts'
rule = 'ro.build.firmware_ota_blocked u:object_r:build_prop:s0 exact bool'
text = contexts.read_text()
if rule not in text:
    (BASE / 'property_contexts.original').write_text(text)
    contexts.write_text(text.rstrip() + '\n\n# Custom Sabrina firmware OTA guard.\n' + rule + '\n')

test_root = SOURCE / 'frameworks/base/services/tests/servicestests/src/com/android/server/recoverysystem'
fake = test_root / 'RecoverySystemServiceTestable.java'
text = fake.read_text()
if 'mFirmwareOtaBlocked' not in text:
    old_field = '        private String mCtlStart = null;'
    new_field = old_field + '''
        private boolean mFirmwareOtaBlocked;

        public void setFirmwareOtaBlocked(boolean blocked) {
            mFirmwareOtaBlocked = blocked;
        }
'''
    old_branch = '            } else if (RecoverySystemService.AB_UPDATE.equals(key)) {'
    new_branch = '''            } else if ("ro.build.firmware_ota_blocked".equals(key)) {
                return Boolean.toString(mFirmwareOtaBlocked);
''' + old_branch
    if text.count(old_field) != 1 or text.count(old_branch) != 1:
        raise RuntimeError('Unexpected test property injector')
    fake.write_text(text.replace(old_field, new_field, 1).replace(old_branch, new_branch, 1))

tests = test_root / 'RecoverySystemServiceTest.java'
text = tests.read_text()
if 'setupBcb_firmwareOtaBlocked' not in text:
    anchor = '    @Test\n    public void setupBcb_success() throws Exception {'
    extra = '''    @Test
    public void setupBcb_firmwareOtaBlocked() throws Exception {
        mSystemProperties.setFirmwareOtaBlocked(true);
        assertFalse(mRecoverySystemService.setupBcb("--update_package=/data/update.zip"));
        assertEquals(null, mSystemProperties.getCtlStart());
        verifyNoMoreInteractions(mUncryptSocket, mIPowerManager);
    }

    @Test
    public void rebootRecoveryWithCommand_firmwareOtaBlocked() throws Exception {
        mSystemProperties.setFirmwareOtaBlocked(true);
        mRecoverySystemService.rebootRecoveryWithCommand("--update_package=/data/update.zip");
        assertEquals(null, mSystemProperties.getCtlStart());
        verifyNoMoreInteractions(mUncryptSocket, mIPowerManager);
    }

    @Test
    public void setupBcb_wipeAllowedWhenFirmwareOtaBlocked() throws Exception {
        mSystemProperties.setFirmwareOtaBlocked(true);
        when(mUncryptSocket.getPercentageUncrypted()).thenReturn(100);
        assertTrue(mRecoverySystemService.setupBcb("--wipe_data\\n--reason=FactoryReset"));
        verify(mUncryptSocket).sendCommand("--wipe_data\\n--reason=FactoryReset");
    }

    @Test
    public void setupBcb_otaAllowedWhenFirmwareOtaGuardOff() throws Exception {
        when(mUncryptSocket.getPercentageUncrypted()).thenReturn(100);
        assertTrue(mRecoverySystemService.setupBcb("--update_package=/data/update.zip"));
        verify(mUncryptSocket).sendCommand("--update_package=/data/update.zip");
    }

'''
    if text.count(anchor) != 1:
        raise RuntimeError('Unexpected recovery service test source')
    tests.write_text(text.replace(anchor, extra + anchor, 1))

classes = BASE / 'ota-host-test-classes'
classes.mkdir(exist_ok=True)
jdk = SOURCE / 'prebuilts/jdk/jdk21/linux-x86/bin'
subprocess.run([str(jdk / 'javac'), '-d', str(classes),
                str(SERVICE / 'FirmwareOtaPolicy.java'),
                str(BASE / 'framework/FirmwareOtaPolicyHostTest.java')], check=True)
subprocess.run([str(jdk / 'java'), '-cp', str(classes),
                'com.android.server.recoverysystem.FirmwareOtaPolicyHostTest'], check=True)
report = {'recovery_service_sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
          'helper_sha256': hashlib.sha256((SERVICE / 'FirmwareOtaPolicy.java').read_bytes()).hexdigest(),
          'property_context_declared': True, 'host_policy_tests_passed': 11,
          'instrumentation_tests_added_not_run': 4,
          'device_tested': False, 'play_services_package_disabled': False,
          'scope': 'Recovery firmware update_package commands only; APK and APEX installers untouched.'}
(BASE / 'ota-framework-guard-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
