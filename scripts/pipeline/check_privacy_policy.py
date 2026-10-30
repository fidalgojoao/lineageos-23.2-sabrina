"""Check candidate privacy configuration while requiring essential Google apps."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parent
SYSTEM = Path('/opt/sabrina/android16/out/target/product/generic/system')
tree = ET.parse(SYSTEM / 'product/etc/sysconfig/sabrina-privacy-components.xml')
disabled = {entry.get('package'): {child.get('class') for child in entry
                                 if child.get('enabled') == 'false'}
            for entry in tree.getroot().findall('component-override')}
audit = json.loads((BASE / 'privacy-component-audit.json').read_text())
for package, entries in audit.items():
    if not {entry['name'] for entry in entries} <= disabled.get(package, set()):
        raise RuntimeError(f'Privacy overrides missing from candidate: {package}')
for essential in ('PrebuiltGmsCorePano', 'Tubesky', 'AndroidMediaShell', 'Katniss', 'AtvRemoteService'):
    if not list((SYSTEM / 'product/priv-app').glob(f'{essential}/*.apk')):
        raise RuntimeError(f'Core Google app missing: {essential}')
if list(SYSTEM.rglob('GoogleFeedback.apk')):
    raise RuntimeError('Optional Google feedback uploader is still staged')
if 'ro.build.privacy_minimized=true\n' not in (SYSTEM / 'build.prop').read_text():
    raise RuntimeError('Read-only privacy policy flag is missing')

needles = [b'com/android/server/pm/PrivacyMetadataPolicy',
           b'firebase_analytics_collection_deactivated',
           b'firebase_performance_collection_deactivated',
           b'ro.build.privacy_minimized']
present = [False] * len(needles)
paths = [SYSTEM / 'framework/services.jar']
paths += list((SYSTEM / 'framework').glob('**/services.odex'))
paths += list((SYSTEM / 'framework').glob('**/services.vdex'))
for path in paths:
    if not path.is_file():
        continue
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            blobs = [archive.read(name) for name in archive.namelist() if name.endswith('.dex')]
    else:
        blobs = [path.read_bytes()]
    for blob in blobs:
        present = [seen or needle in blob for seen, needle in zip(present, needles)]
if not all(present):
    raise RuntimeError('Optional analytics policy is not present in shipped server code')

report = {'scoped_privacy_components_present': True, 'google_feedback_absent': True,
          'core_google_apks_present': True, 'metadata_policy_compiled': True,
          'runtime_and_network_traffic_verified': False,
          'limits': 'Not proof of zero telemetry or compatibility with every application.'}
(BASE / 'candidate-privacy-policy.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
