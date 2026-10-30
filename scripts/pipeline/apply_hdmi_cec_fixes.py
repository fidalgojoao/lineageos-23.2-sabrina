"""Report HDMI audio from Amlogic's extcon state, and send the Input key over CEC."""
from pathlib import Path
B=Path('/opt/sabrina/android16/frameworks/base/services/core/java/com/android/server')
w=B/'WiredAccessoryManager.java';t=w.read_text()
assert 'AmlogicHdmiObserver' not in t
old='''    private void onSystemReady() {
'''
assert t.count(old)==1
t=t.replace(old,'''    /**
     * Amlogic reports HDMI through extcon rather than the switch class this file reads. Without
     * this, audio policy only sees the speaker device and volume keys never reach HDMI-CEC.
     */
    private final class AmlogicHdmiObserver extends UEventObserver {
        private static final String EXTCON_NAME = "ffd00000.amhdmitx";
        private int mLastState = -1;

        void init() {
            startObserving(EXTCON_NAME);
            update();
        }

        @Override
        public void onUEvent(UEventObserver.UEvent event) {
            update();
        }

        private void update() {
            final java.io.File[] entries = new java.io.File("/sys/class/extcon").listFiles();
            if (entries == null) {
                return;
            }
            for (java.io.File entry : entries) {
                try {
                    final java.io.File name = new java.io.File(entry, "name");
                    if (!EXTCON_NAME.equals(
                            java.nio.file.Files.readString(name.toPath()).trim())) {
                        continue;
                    }
                    final String value = java.nio.file.Files.readString(
                            new java.io.File(entry, "state").toPath());
                    final int state = value.contains("HDMI=1") ? 1 : 0;
                    synchronized (mLock) {
                        if (state == mLastState) {
                            return;
                        }
                        mLastState = state;
                    }
                    Slog.i(TAG, "Amlogic HDMI audio state: " + state);
                    mAudioManager.setWiredDeviceConnectionState(
                            AudioManager.DEVICE_OUT_HDMI, state, "", "hdmi");
                    return;
                } catch (java.io.IOException e) {
                    Slog.w(TAG, "Could not read " + entry, e);
                }
            }
        }
    }

    private void onSystemReady() {
        new AmlogicHdmiObserver().init();
''')
w.write_text(t)
p=B/'policy/PhoneWindowManager.java';t=p.read_text()
old='''        if (isValidGlobalKey(keyCode)
                && mGlobalKeyManager.handleGlobalKey(mContext, keyCode, event)) {
            return true;
        }
        // Specific device key handling
'''
assert t.count(old)==1
t=t.replace(old,'''        // Stock's Chromecast service forwards this key to the TV; this build has no such receiver.
        if (keyCode == KeyEvent.KEYCODE_TV_INPUT) {
            final HdmiControlManager hdmiControlManager = getHdmiControlManager();
            final HdmiPlaybackClient hdmiClient = hdmiControlManager == null
                    ? null : hdmiControlManager.getPlaybackClient();
            if (hdmiClient != null) {
                hdmiClient.sendKeyEvent(keyCode, event.getAction() == KeyEvent.ACTION_DOWN);
                return true;
            }
        }
'''+old)
p.write_text(t)
print('patched')
