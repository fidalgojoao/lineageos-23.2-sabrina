"""Merge channel history read from storage before using it, so it's available before connecting."""
from pathlib import Path
p=Path('/opt/sabrina/android16/packages/modules/Wifi/service/java/com/android/server/wifi/WifiScoreCard.java');t=p.read_text()
old='''        List<Integer> getFrequencies(Long ageInMills) {
            List<Integer> results = new ArrayList<>();
'''
new='''        List<Integer> getFrequencies(Long ageInMills) {
            // Without this, stored channels stay unread until a connection event needs them.
            finishPendingRead();
            List<Integer> results = new ArrayList<>();
'''
if new in t:print('already patched');raise SystemExit
assert t.count(old)==1
p.write_text(t.replace(old,new));print('patched')
