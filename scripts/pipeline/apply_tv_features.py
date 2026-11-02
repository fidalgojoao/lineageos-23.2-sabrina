"""Add Advanced restart, the local-only Updater and its recovery switch to the source tree."""
from pathlib import Path
T=Path('/opt/sabrina/android16')
def edit(rel,pairs):
    p=T/rel;t=p.read_text();changed=False
    for old,new in pairs:
        if (new and new in t) or (not new and old not in t):continue
        assert t.count(old)==1,(rel,old[:60],t.count(old));t=t.replace(old,new);changed=True
    if changed:p.write_text(t)
    print('patched' if changed else 'already patched',rel)

# Advanced restart switch in Settings > System > Buttons.
S='packages/apps/TvSettings/Settings/'
edit(S+'res/xml/buttons.xml',[('''    <com.android.tv.settings.widget.SwitchWithSoundPreference
        android:key="press_volume_up_and_down_to_mute"''','''    <com.android.tv.settings.widget.SwitchWithSoundPreference
        android:key="advanced_reboot"
        android:order="2"
        android:title="@string/advanced_restart_title"
        android:summary="@string/advanced_restart_summary"
        android:defaultValue="false" />

    <com.android.tv.settings.widget.SwitchWithSoundPreference
        android:key="press_volume_up_and_down_to_mute"''')])
edit(S+'res/values/lineage_strings.xml',[('''    <!-- Volume up and down to mute [CHAR LIMIT=60] -->''','''    <!-- Power menu entries for recovery and bootloader [CHAR LIMIT=60] -->
    <string name="advanced_restart_title">Advanced restart</string>
    <string name="advanced_restart_summary">Show options for restarting into recovery or bootloader</string>
    <!-- Volume up and down to mute [CHAR LIMIT=60] -->''')])
edit(S+'AndroidManifest.xml',[('''    <uses-permission android:name="android.permission.WRITE_SECURE_SETTINGS"/>''','''    <uses-permission android:name="android.permission.WRITE_SECURE_SETTINGS"/>
    <uses-permission android:name="lineageos.permission.WRITE_SECURE_SETTINGS"/>''')])
edit(S+'src/com/android/tv/settings/system/ButtonsFragment.java',[('''        findPreference(KEY_PRESS_VOLUME_UP_AND_DOWN_TO_MUTE).setOnPreferenceChangeListener(''','''        TwoStatePreference advancedRestart = findPreference(KEY_ADVANCED_RESTART);
        advancedRestart.setChecked(LineageSettings.Secure.getInt(context.getContentResolver(),
                LineageSettings.Secure.ADVANCED_REBOOT, 0) == 1);
        advancedRestart.setOnPreferenceChangeListener(
            (preference, newValue) -> {
                LineageSettings.Secure.putInt(context.getContentResolver(),
                        LineageSettings.Secure.ADVANCED_REBOOT, (Boolean) newValue ? 1 : 0);
                return true;
            });

        findPreference(KEY_PRESS_VOLUME_UP_AND_DOWN_TO_MUTE).setOnPreferenceChangeListener('''),
 ('''    private static final String KEY_PRESS_VOLUME_UP_AND_DOWN_TO_MUTE =''','''    private static final String KEY_ADVANCED_RESTART = "advanced_reboot";
    private static final String KEY_PRESS_VOLUME_UP_AND_DOWN_TO_MUTE ='''),
 ('''import androidx.preference.ListPreference;''','''import androidx.preference.ListPreference;
import androidx.preference.TwoStatePreference;''')])

edit(S+'res/xml/buttons.xml',[('''android:key="press_volume_up_and_down_to_mute"
        android:order="2"''','''android:key="press_volume_up_and_down_to_mute"
        android:order="3"''')])

# On TV, list recovery and bootloader beside Power off and Restart instead of in a submenu.
edit('frameworks/base/packages/SystemUI/src/com/android/systemui/globalactions/GlobalActionsDialogLite.java',[
 ('''    private boolean shouldShowRestartSubmenu() {
        return PowerMenuUtils.isAdvancedRestartPossible(mContext);
    }''','''    private boolean shouldShowRestartSubmenu() {
        return PowerMenuUtils.isAdvancedRestartPossible(mContext) && !isTelevision();
    }

    private boolean shouldShowRestartActionsInline() {
        return PowerMenuUtils.isAdvancedRestartPossible(mContext) && isTelevision();
    }

    private boolean isTelevision() {
        return mContext.getPackageManager().hasSystemFeature(PackageManager.FEATURE_LEANBACK);
    }'''),
 ('''        // replace power and restart with a single power options action, if needed
''','''        if (shouldShowRestartActionsInline() && tempActions.contains(restartAction)) {
            int inlineIndex = tempActions.indexOf(restartAction) + 1;
            tempActions.add(inlineIndex, blAction);
            tempActions.add(inlineIndex, recAction);
        }

        // replace power and restart with a single power options action, if needed
''')])

# Let the OTA guard pass only a package the Updater imported and our own key signed.
R='frameworks/base/services/core/java/com/android/server/recoverysystem/'
edit(R+'FirmwareOtaPolicy.java',[
 ('''    static boolean blocksRecoveryCommand(boolean firmwareOtaBlocked, String command) {''','''    private static final String LOCAL_UPDATE_DIR = "/data/lineageos_updates/";
    private static final String BLOCK_MAP_ARGUMENT = "--update_package=@/cache/recovery/block.map";

    /** True only for the Updater's own imported package, signed by a key in otacerts.zip. */
    static boolean isVerifiedLocalUpdate(String command) {
        if (command == null || !List.of(command.split("\\n")).contains(BLOCK_MAP_ARGUMENT)) {
            return false;
        }
        try {
            File file = new File(FileUtils.readTextFile(
                    RecoverySystem.UNCRYPT_PACKAGE_FILE, 0, null).trim());
            if (!file.getCanonicalPath().startsWith(LOCAL_UPDATE_DIR)) {
                return false;
            }
            RecoverySystem.verifyPackage(file, null, null);
            return true;
        } catch (IOException | GeneralSecurityException e) {
            return false;
        }
    }

    static boolean blocksRecoveryCommand(boolean firmwareOtaBlocked, String command,
            boolean verifiedLocalUpdate) {'''),
 ('''            if (argument.equals("--update_package") || argument.startsWith("--update_package=")) {
                return true;''','''            if (argument.equals("--update_package") || argument.startsWith("--update_package=")) {
                if (!verifiedLocalUpdate) {
                    return true;
                }'''),
 ('''package com.android.server.recoverysystem;
''','''package com.android.server.recoverysystem;

import android.os.FileUtils;
import android.os.RecoverySystem;

import java.io.File;
import java.io.IOException;
import java.security.GeneralSecurityException;
import java.util.List;
''')])
edit(R+'RecoverySystemService.java',[('''        if (isSetup && FirmwareOtaPolicy.blocksRecoveryCommand(firmwareOtaBlocked, command)) {''','''        if (isSetup && FirmwareOtaPolicy.blocksRecoveryCommand(firmwareOtaBlocked, command,
                firmwareOtaBlocked && FirmwareOtaPolicy.isVerifiedLocalUpdate(command))) {''')])

# Updater: local packages only. No update server, no background checks, no internet permission.
U='packages/apps/Updater/app/src/main/'
J=U+'java/org/lineageos/updater/'
edit(U+'AndroidManifest.xml',[('''    <uses-permission android:name="android.permission.INTERNET" />
''','')])
edit(J+'UpdaterReceiver.java',[('''            UpdatesCheckWorker.schedulePeriodicCheck(context);
''','')])
edit(J+'UpdatesViewModel.kt',[('''        viewModelScope.launch {
            networkMonitor.networkState
                .distinctUntilChangedBy { it.isOnline }
                .onEach { networkState ->
                    _uiState.update { it.copy(isOnline = networkState.isOnline) }
                }
                .filter { it.isOnline }
                .collect { fetchUpdates() }
        }
''','')])
edit(J+'UpdatesScaffoldActivity.kt',[
 ('''        UpdatesCheck(
            model = model,
            uiState = updatesCheckUiState,
            onCheckClick = onRefreshClick,
        )
''',''),
 ('''            isUpdatesCheckStatusVisible = updatesCheckUiState.isStatusVisible,''','''            isUpdatesCheckStatusVisible = false,'''),
 ('''    val preferencesSummary = stringResource(R.string.preferences_summary)
''','''    val updateRecoverySummary = stringResource(R.string.menu_update_recovery_summary)
    val context = androidx.compose.ui.platform.LocalContext.current
    val repository =
        remember { (context.applicationContext as UpdaterApplication).userPreferencesRepository }
    var recoveryUpdateEnabled by remember { mutableStateOf(repository.getRecoveryUpdateEnabled()) }
'''),
 ('''        Preference(object : PreferenceModel {
            override val title = stringResource(R.string.menu_preferences)
            override val summary = { preferencesSummary }
            override val onClick = onPreferencesClick
        })
''','''        SwitchPreference(object : SwitchPreferenceModel {
            override val title = stringResource(R.string.menu_update_recovery)
            override val summary = { updateRecoverySummary }
            override val checked = { recoveryUpdateEnabled }
            override val onCheckedChange: (Boolean) -> Unit = { value ->
                recoveryUpdateEnabled = value
                repository.setRecoveryUpdateEnabled(value)
            }
        })
'''),
 ('''import com.android.settingslib.spa.widget.scaffold.SettingsScaffold''','''import com.android.settingslib.spa.widget.preference.SwitchPreference
import com.android.settingslib.spa.widget.preference.SwitchPreferenceModel
import com.android.settingslib.spa.widget.scaffold.SettingsScaffold''')])

# Device tree: ship the Updater and a file picker, and stop disabling the Updater's components.
D='device/google/sabrina16/'
p=T/D/'Android.bp';t=p.read_text()
lines=[l for l in t.splitlines(True) if not ('Exclude the inherited ROM updater' in l or l.strip()=='"Updater",')]
if ''.join(lines)!=t:p.write_text(''.join(lines));print('patched Android.bp')
p=T/D/'permissions/sabrina-ota-components.xml';t=p.read_text()
for c in ('preferences.PreferencesActivity','UpdatesActivity','controller.UpdaterService','UpdaterReceiver'):
    t=t.replace(f'    <component class="org.lineageos.updater.{c}" enabled="false" />\n','')
p.write_text(t);assert 'ExportUpdateService' in t
p=T/D/'lineage_gsi_sabrina16.mk';t=p.read_text()
if 'DocumentsUI' not in t:p.write_text(t.rstrip('\n')+'\n\n# File picker for the Updater\'s local update.\nPRODUCT_PACKAGES += DocumentsUI\n');print('patched product')
print('done')
