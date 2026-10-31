"""Show accessory battery in Remotes & Accessories, and reword the OEM unlocking summary."""
from pathlib import Path
S=Path('/opt/sabrina/android16/packages/apps/TvSettings/Settings')
def edit(rel,pairs):
    p=S/rel;t=p.read_text();changed=False
    for old,new in pairs:
        if new in t:continue
        assert t.count(old)==1,(rel,old[:60],t.count(old));t=t.replace(old,new);changed=True
    if changed:p.write_text(t)
    print('patched' if changed else 'already patched',rel)
edit('src/com/android/tv/settings/accessories/ConnectedDevicesSliceProvider.java',[
 ('''        pref.setSubtitle(
                isConnected
                        ? getString(R.string.bluetooth_connected_status)
                        : getString(R.string.bluetooth_disconnected_status));
''','''        pref.setSubtitle(appendBatteryLevel(device,
                isConnected
                        ? getString(R.string.bluetooth_connected_status)
                        : getString(R.string.bluetooth_disconnected_status)));
'''),
 ('''                new RowBuilder()
                        .setTitle(deviceName)
                        .setPageId(TvSettingsEnums.CONNECTED_SLICE_DEVICE_ENTRY));
''','''                new RowBuilder()
                        .setTitle(deviceName)
                        .setSubtitle(device != null ? appendBatteryLevel(device, "") : "")
                        .setPageId(TvSettingsEnums.CONNECTED_SLICE_DEVICE_ENTRY));
'''),
 ('''    private void updateConnectedDevices(PreferenceSliceBuilder psb) {
''','''    /** Adds the battery level, when the device has reported one, to a status line. */
    private String appendBatteryLevel(BluetoothDevice device, String status) {
        final int level = device.getBatteryLevel();
        if (level < 0) {
            return status;
        }
        final String battery = getContext().getString(R.string.accessory_battery, level);
        return status.isEmpty() ? battery : status + " \\u2022 " + battery;
    }

    private void updateConnectedDevices(PreferenceSliceBuilder psb) {
''')])
edit('res/values/strings.xml',[('''>Connect to the internet or contact your carrier</string>''','''>Allow the bootloader to be unlocked</string>''')])
print('done')
