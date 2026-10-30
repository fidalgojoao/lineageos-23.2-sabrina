"""Honour stock's notification panel setting for long press Home; Lineage's actions have no such entry."""
from pathlib import Path
p=Path('/opt/sabrina/android16/frameworks/base/services/core/java/com/android/server/policy/PhoneWindowManager.java');t=p.read_text()
assert 'config_longPressOnHomeBehavior) == LONG_PRESS_HOME_NOTIFICATION_PANEL' not in t
old='''                    // If long press home will launch assistant,
                    // it should pass this right invocation type.
                    performKeyAction(mHomeLongPressAction, event,
                            AssistUtils.INVOCATION_TYPE_HOME_BUTTON_LONG_PRESS);
                    mHomeConsumed = true;
'''
assert t.count(old)==1
t=t.replace(old,'''                    if (mContext.getResources().getInteger(
                            com.android.internal.R.integer.config_longPressOnHomeBehavior)
                            == LONG_PRESS_HOME_NOTIFICATION_PANEL) {
                        // Google TV opens Quick Settings here. Lineage's Action list can't express it.
                        toggleNotificationPanel();
                    } else {
                        // If long press home will launch assistant,
                        // it should pass this right invocation type.
                        performKeyAction(mHomeLongPressAction, event,
                                AssistUtils.INVOCATION_TYPE_HOME_BUTTON_LONG_PRESS);
                    }
                    mHomeConsumed = true;
''')
p.write_text(t);print('patched')
