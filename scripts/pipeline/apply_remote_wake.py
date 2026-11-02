"""Let the remote's Home, Assistant and app buttons wake the device on TV, as stock does."""
from pathlib import Path
import os
T=Path('/opt/sabrina/android16')
def edit(rel,pairs):
    p=T/rel;t=p.read_text();changed=False
    for old,new in pairs:
        if new in t:continue
        assert t.count(old)==1,(rel,old[:60],t.count(old));t=t.replace(old,new);changed=True
    if changed:p.write_text(t)
    print('patched' if changed else 'already patched',rel)
edit('frameworks/base/services/core/java/com/android/server/policy/PhoneWindowManager.java',[
 ('''        int mDeviceHardwareWakeKeys = mContext.getResources().getInteger(
                org.lineageos.platform.internal.R.integer.config_deviceHardwareWakeKeys);
''','''        int mDeviceHardwareWakeKeys = mContext.getResources().getInteger(
                org.lineageos.platform.internal.R.integer.config_deviceHardwareWakeKeys);
        if (mHasFeatureLeanback) {
            // A TV remote's Home and Assistant buttons wake the device, as on stock Android TV.
            mDeviceHardwareWakeKeys |= KEY_MASK_HOME | KEY_MASK_ASSIST;
        }
'''),
 ('''                    LineageSettings.System.ASSIST_WAKE_SCREEN, 0, UserHandle.USER_CURRENT) == 1)''',
  '''                    LineageSettings.System.ASSIST_WAKE_SCREEN, mHasFeatureLeanback ? 1 : 0,
                    UserHandle.USER_CURRENT) == 1)'''),
 ('''        boolean isWakeKey = (policyFlags & WindowManagerPolicy.FLAG_WAKE) != 0
                || event.isWakeKey();
''','''        boolean isWakeKey = (policyFlags & WindowManagerPolicy.FLAG_WAKE) != 0
                || event.isWakeKey() || isTvRemoteAppKey(keyCode);
'''),
 ('''    private boolean isWakeKeyEnabled(int keyCode) {''','''    /** Stock remotes' Assistant and app buttons, which wake a TV whichever key layout the remote uses. */
    private boolean isTvRemoteAppKey(int keyCode) {
        if (!mHasFeatureLeanback) {
            return false;
        }
        switch (keyCode) {
            case KeyEvent.KEYCODE_ASSIST:
            case KeyEvent.KEYCODE_BUTTON_3:
            case KeyEvent.KEYCODE_BUTTON_4:
            case KeyEvent.KEYCODE_FEATURED_APP_1:
            case KeyEvent.KEYCODE_MACRO_1:
                return true;
        }
        return false;
    }

    private boolean isWakeKeyEnabled(int keyCode) {''')])
# The app buttons go to the launcher while asleep, so the button's action runs once the TV is on.
# This replaces TvFrameworkOverlay's list, so its keys are kept here too.
R=Path(__file__).resolve().parents[2]/'device/google/sabrina16/rro/SabrinaFrameworkOverlay/res/xml'
if not R.parent.is_dir():R=Path(os.environ.get('SABRINA_REPO','/path/to/lineageos-23-sabrina'))/'device/google/sabrina16/rro/SabrinaFrameworkOverlay/res/xml'
R.mkdir(parents=True,exist_ok=True)
(R/'global_keys.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>
<!-- Global keys for sabrina: TvFrameworkOverlay's keys, plus stock's app buttons on the remote. -->
<global_keys version="1">
    <key keyCode="KEYCODE_DVR" component="com.google.android.tv/.receiver.GlobalKeyReceiver" />
    <key keyCode="KEYCODE_GUIDE" component="com.google.android.tv/.receiver.GlobalKeyReceiver" />
    <key keyCode="KEYCODE_TV" component="com.google.android.tv/.receiver.GlobalKeyReceiver" />
    <key keyCode="KEYCODE_TV_INPUT" component="com.android.tv.settings/.GlobalKeyReceiver" dispatchWhenNonInteractive="true" />
    <key keyCode="KEYCODE_PAIRING" component="com.android.tv.settings/.GlobalKeyReceiver" dispatchWhenNonInteractive="true" />
    <key keyCode="KEYCODE_BUTTON_3" component="com.google.android.apps.tv.launcherx/.remotecontrol.GlobalKeyListener_Receiver" dispatchWhenNonInteractive="true" />
    <key keyCode="KEYCODE_MACRO_1" component="com.google.android.apps.tv.launcherx/.remotecontrol.GlobalKeyListener_Receiver" dispatchWhenNonInteractive="true" />
</global_keys>
''');print('wrote global_keys.xml')
print('done')
