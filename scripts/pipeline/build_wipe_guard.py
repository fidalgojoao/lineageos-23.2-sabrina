"""Block recovery wipes as well as firmware OTAs, then compile only services.jar and its dexpreopt output."""
from pathlib import Path
import hashlib,json,os,subprocess,time
base=Path(__file__).resolve().parent;src=Path('/opt/sabrina/android16')
policy=src/'frameworks/base/services/core/java/com/android/server/recoverysystem/FirmwareOtaPolicy.java'
test=src/'frameworks/base/services/tests/servicestests/src/com/android/server/recoverysystem/RecoverySystemServiceTest.java'
text=policy.read_text()
old='''            if (argument.equals("--update_package") || argument.startsWith("--update_package=")) {
                return true;
            }
'''
assert text.count(old)==1
policy.write_text(text.replace(old,'''            if (argument.equals("--update_package") || argument.startsWith("--update_package=")) {
                return true;
            }
            // Stock recovery's factory reset also resets env, which relocks this device.
            // Userdata must be wiped with fastboot -w instead.
            if (argument.equals("--wipe_data") || argument.equals("--prompt_and_wipe_data")) {
                return true;
            }
'''))
text=test.read_text()
old='''    public void setupBcb_wipeAllowedWhenFirmwareOtaBlocked() throws Exception {
        mSystemProperties.setFirmwareOtaBlocked(true);
        when(mUncryptSocket.getPercentageUncrypted()).thenReturn(100);
        assertTrue(mRecoverySystemService.setupBcb("--wipe_data\\n--reason=FactoryReset"));
        verify(mUncryptSocket).sendCommand("--wipe_data\\n--reason=FactoryReset");
    }
'''
assert text.count(old)==1
test.write_text(text.replace(old,'''    public void setupBcb_wipeBlockedWhenFirmwareOtaBlocked() throws Exception {
        mSystemProperties.setFirmwareOtaBlocked(true);
        assertFalse(mRecoverySystemService.setupBcb("--wipe_data\\n--reason=FactoryReset"));
        assertFalse(mRecoverySystemService.setupBcb("--prompt_and_wipe_data\\n--reason=RescueParty"));
        assertEquals(null, mSystemProperties.getCtlStart());
        verifyNoMoreInteractions(mUncryptSocket, mIPowerManager);
    }
'''))
out='out/target/product/generic/system/framework/'
targets=[out+'services.jar',out+'oat/arm/services.odex',out+'oat/arm/services.vdex',out+'oat/arm/services.art']
log=base/'build-wipe-guard.log'
script='set -e; source build/envsetup.sh; source vendor/lineage/vars/aosp_target_release; lunch lineage_gsi_sabrina16 "$aosp_target_release" user; m -j4 '+' '.join(targets)
with log.open('w') as stream:
    r=subprocess.run(['bash','-lc',script],cwd=src,stdout=stream,stderr=subprocess.STDOUT,timeout=7000,env={**os.environ,'NINJA_STATUS':'[%f/%t] '})
assert r.returncode==0,'build failed; see '+str(log)
report={t.rsplit('/',1)[1]:hashlib.sha256((src/t).read_bytes()).hexdigest() for t in targets}
report['guard_compiled']=True;report['finished_unix']=time.time()
(base/'WIPE-GUARD-BUILD.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
