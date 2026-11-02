"""Add an Input button switch to Remotes & Accessories: when on, the Input button switches the TV to this device over HDMI-CEC."""
from pathlib import Path
import os
S=Path('/opt/sabrina/android16/packages/apps/TvSettings/Settings')
A='src/com/android/tv/settings/accessories/'
def edit(rel,pairs):
    p=S/rel;t=p.read_text();changed=False
    for old,new in pairs:
        if new in t:continue
        assert t.count(old)==1,(rel,old[:60],t.count(old));t=t.replace(old,new);changed=True
    if changed:p.write_text(t)
    print('patched' if changed else 'already patched',rel)
edit('AndroidManifest.xml',[('''    <uses-permission android:name="android.permission.WRITE_SECURE_SETTINGS"/>
''','''    <uses-permission android:name="android.permission.WRITE_SECURE_SETTINGS"/>
    <uses-permission android:name="android.permission.HDMI_CEC"/>
''')])
edit('res/values/lineage_strings.xml',[('''    <!-- Volume up and down to mute [CHAR LIMIT=60] -->''','''    <!-- Remotes & Accessories: the remote's Input button switches the TV to this device [CHAR LIMIT=60] -->
    <string name="input_button_switch_title">Input button switches to this device</string>
    <string name="input_button_switch_summary">Pressing Input on the remote switches the TV to this device over HDMI-CEC</string>
    <!-- Volume up and down to mute [CHAR LIMIT=60] -->''')])
edit(A+'ConnectedDevicesSliceBroadcastReceiver.java',[
 ('''    static final String ACTIVE_AUDIO_OUTPUT = "ACTIVE_AUDIO_OUTPUT";
''','''    static final String ACTIVE_AUDIO_OUTPUT = "ACTIVE_AUDIO_OUTPUT";
    static final String INPUT_BUTTON_SWITCH = "INPUT_BUTTON_SWITCH";
    /** Read by GlobalKeyReceiver: 1 makes the Input button switch the TV to this device. */
    public static final String INPUT_BUTTON_SWITCH_SETTING = "sabrina_input_button_switch";
'''),
 ('''                    case FIND_MY_REMOTE_PHYSICAL_BUTTON_ENABLED_SETTING -> {''','''                    case INPUT_BUTTON_SWITCH -> {
                        Settings.Secure.putInt(context.getContentResolver(),
                                INPUT_BUTTON_SWITCH_SETTING, isChecked ? 1 : 0);
                        context.getContentResolver().notifyChange(
                                ConnectedDevicesSliceUtils.GENERAL_SLICE_URI, null);
                    }
                    case FIND_MY_REMOTE_PHYSICAL_BUTTON_ENABLED_SETTING -> {'''),
 ('''import android.content.Intent;
''','''import android.content.Intent;
import android.provider.Settings;
''')])
edit(A+'ConnectedDevicesSliceProvider.java',[
 ('''        if (isOfficialRemoteSettingsUriValid) {
            psb.addPreference(new RowBuilder()
                    .setKey(KEY_OFFICIAL_REMOTE)''','''        if (isIrSettingsUriValid) {
            // Directly below "Set up remote buttons", where its Input button is configured.
            addInputButtonSwitch(psb);
        }
        if (isOfficialRemoteSettingsUriValid) {
            psb.addPreference(new RowBuilder()
                    .setKey(KEY_OFFICIAL_REMOTE)'''),
 ('''    private void updateFmr(PreferenceSliceBuilder psb) {''','''    /** When on, the remote's Input button switches the TV to this device over HDMI-CEC. */
    private void addInputButtonSwitch(PreferenceSliceBuilder psb) {
        final Context context = getContext();
        final boolean isOn = Settings.Secure.getInt(context.getContentResolver(),
                ConnectedDevicesSliceBroadcastReceiver.INPUT_BUTTON_SWITCH_SETTING, 0) == 1;
        final Intent intent = new Intent(ACTION_TOGGLE_CHANGED)
                .setClass(context, ConnectedDevicesSliceBroadcastReceiver.class)
                .putExtra(EXTRA_TOGGLE_TYPE, ConnectedDevicesSliceBroadcastReceiver.INPUT_BUTTON_SWITCH)
                .putExtra(EXTRA_TOGGLE_STATE, !isOn);
        final PendingIntent pendingIntent = PendingIntent.getBroadcast(context,
                INPUT_BUTTON_SWITCH_REQUEST_CODE, intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        psb.addPreference(new RowBuilder()
                .setKey(KEY_INPUT_BUTTON_SWITCH)
                .setTitle(getString(R.string.input_button_switch_title))
                .setSubtitle(getString(R.string.input_button_switch_summary))
                .addSwitch(pendingIntent, getString(R.string.input_button_switch_title), isOn));
    }

    private void updateFmr(PreferenceSliceBuilder psb) {'''),
 ('''    static final String KEY_EXTRAS_DEVICE = "extra_devices";''','''    static final String KEY_EXTRAS_DEVICE = "extra_devices";
    private static final String KEY_INPUT_BUTTON_SWITCH = "input_button_switch";
    private static final int INPUT_BUTTON_SWITCH_REQUEST_CODE = 0x5ab1;''')])
p=S/(A+'ConnectedDevicesSliceProvider.java');t=p.read_text()
if 'import android.provider.Settings;' not in t:
    old='import android.os.Bundle;\n';assert t.count(old)==1;p.write_text(t.replace(old,old+'import android.provider.Settings;\n'));print('patched provider import')
edit('src/com/android/tv/settings/GlobalKeyReceiver.java',[
 ('''                case KeyEvent.KEYCODE_PAIRING:
                    sendPairingIntent(context, event);
                    return;''','''                case KeyEvent.KEYCODE_PAIRING:
                    sendPairingIntent(context, event);
                    return;
                case KeyEvent.KEYCODE_TV_INPUT:
                    if (event.getAction() == KeyEvent.ACTION_UP) {
                        switchTvToThisDevice(context);
                    }
                    return;'''),
 ('''    private static void sendPairingIntent(Context context, KeyEvent event) {''','''    /** With the Input button switch on, asks the TV over HDMI-CEC to show this device. */
    private static void switchTvToThisDevice(Context context) {
        if (Settings.Secure.getInt(context.getContentResolver(),
                ConnectedDevicesSliceBroadcastReceiver.INPUT_BUTTON_SWITCH_SETTING, 0) != 1) {
            return;
        }
        final HdmiControlManager hdmi = context.getSystemService(HdmiControlManager.class);
        final HdmiPlaybackClient playback = hdmi != null ? hdmi.getPlaybackClient() : null;
        if (playback == null) {
            Log.w(TAG, "No HDMI-CEC playback device");
            return;
        }
        playback.oneTouchPlay(result -> Log.i(TAG, "Switch TV to this device: " + result));
    }

    private static void sendPairingIntent(Context context, KeyEvent event) {'''),
 ('''import android.content.Intent;
import android.util.Log;''','''import android.content.Intent;
import android.hardware.hdmi.HdmiControlManager;
import android.hardware.hdmi.HdmiPlaybackClient;
import android.provider.Settings;
import android.util.Log;'''),
 ('''import android.view.KeyEvent;
''','''import android.view.KeyEvent;

import com.android.tv.settings.accessories.ConnectedDevicesSliceBroadcastReceiver;
''')])
# Send the Input button to TV Settings, even while asleep, instead of the absent Live Channels app.
G=Path(os.environ.get('SABRINA_REPO','/path/to/lineageos-23-sabrina'))/'device/google/sabrina16/rro/SabrinaFrameworkOverlay/res/xml/global_keys.xml'
t=G.read_text();old='''    <key keyCode="KEYCODE_TV_INPUT" component="com.google.android.tv/.receiver.GlobalKeyReceiver" />'''
new='''    <key keyCode="KEYCODE_TV_INPUT" component="com.android.tv.settings/.GlobalKeyReceiver" dispatchWhenNonInteractive="true" />'''
if new not in t:assert t.count(old)==1;G.write_text(t.replace(old,new));print('patched global_keys.xml')
print('done')
