"""Alternate full scans with known-channel scans while a saved hidden network is out of reach."""
from pathlib import Path
p=Path('/opt/sabrina/android16/packages/modules/Wifi/service/java/com/android/server/wifi/WifiConnectivityManager.java');t=p.read_text()
new='''            } else {
                // A full scan can miss a hidden network on a DFS channel: there's little time on
                // each channel to hear a beacon and then probe for the name. Android knows the
                // channel, so try it on every other scan. Falls back to full with no history.
                if (mWifiState == WIFI_STATE_DISCONNECTED
                        && mCurrentSingleScanScheduleIndex % 2 == 1
                        && !mConfigManager.retrieveHiddenNetworkList(true).isEmpty()) {
                    isFullBandScan = false;
                }
                startSingleScan(isFullBandScan, WIFI_WORK_SOURCE,
                        getScheduledSingleScanType(mCurrentSingleScanScheduleIndex));
                mWifiMetrics.reportWifiPeriodicScan(mWifiState == WIFI_STATE_CONNECTED,
                        isFullBandScan,
'''
if new in t:print('already patched');raise SystemExit
# Trying known channels first was measured worse (149, 149, 8, 55, 149 s against about 29 s).
known_first='''            } else {
                // A full scan can miss a hidden network on a DFS channel: there's little time on
                // each channel to hear a beacon and then probe for the name. Android knows the
                // channel, so try it first, then on every other scan. Falls back to full with no
                // history, which is why the first two scans both try it.
                if (mWifiState == WIFI_STATE_DISCONNECTED
                        && (mCurrentSingleScanScheduleIndex < 2
                                || mCurrentSingleScanScheduleIndex % 2 == 1)
                        && !mConfigManager.retrieveHiddenNetworkList(true).isEmpty()) {
                    isFullBandScan = false;
                }
                startSingleScan(isFullBandScan, WIFI_WORK_SOURCE,
                        getScheduledSingleScanType(mCurrentSingleScanScheduleIndex));
                mWifiMetrics.reportWifiPeriodicScan(mWifiState == WIFI_STATE_CONNECTED,
                        isFullBandScan,
'''
old='''            } else {
                startSingleScan(isFullBandScan, WIFI_WORK_SOURCE,
                        getScheduledSingleScanType(mCurrentSingleScanScheduleIndex));
                mWifiMetrics.reportWifiPeriodicScan(mWifiState == WIFI_STATE_CONNECTED,
                        isFullBandScan,
'''
found=known_first if known_first in t else old
assert t.count(found)==1
p.write_text(t.replace(found,new));print('patched')
