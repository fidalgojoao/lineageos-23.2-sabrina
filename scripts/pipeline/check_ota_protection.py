"""Gate a test candidate on OS-OTA protection and retained Google app packages."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

BASE = Path(__file__).resolve().parent
SYSTEM = Path('/opt/sabrina/android16/out/target/product/generic/system')
xml = SYSTEM / 'product/etc/sysconfig/sabrina-ota-components.xml'
root = ET.parse(xml).getroot()
disabled = {entry.get('package'): {item.get('class') for item in entry
                                 if item.tag == 'component' and item.get('enabled') == 'false'}
            for entry in root.findall('component-override')}
audited = json.loads((BASE / 'ota-component-audit.json').read_text())
for package, entries in audited.items():
    expected = {entry['name'] for entry in entries}
    if not expected <= disabled.get(package, set()):
        raise RuntimeError(f'Missing firmware-OTA component overrides for {package}')

props = (SYSTEM / 'build.prop').read_text()
if 'ro.build.firmware_ota_blocked=true\n' not in props:
    raise RuntimeError('Read-only recovery firmware-OTA guard is not enabled')
if list(SYSTEM.rglob('Updater.apk')):
    raise RuntimeError('Lineage firmware updater APK is still staged; review stale build outputs')

apps = {}
for module in ('PrebuiltGmsCorePano', 'Tubesky', 'SetupWraithPrebuilt', 'SabrinaGoogleTVLauncher'):
    matches = list((SYSTEM / 'product/priv-app').glob(f'{module}/*.apk'))
    if not matches:
        raise RuntimeError(f'Required Google setup/store/launcher APK missing: {module}')
    apps[module] = [str(path.relative_to(SYSTEM)) for path in matches]

# Look for the actual compiled class and property in shipped server code, not
# just in a source checkout. Preoptimized builds may ship code in odex/vdex.
needles = [b'com/android/server/recoverysystem/FirmwareOtaPolicy', b'ro.build.firmware_ota_blocked']
present = [False, False]
code_files = [SYSTEM / 'framework/services.jar']
code_files += list((SYSTEM / 'framework').glob('**/services.odex'))
code_files += list((SYSTEM / 'framework').glob('**/services.vdex'))
for path in code_files:
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
    raise RuntimeError('Firmware OTA policy class/property not found in shipped server code')

report = {'component_override_counts': {package: len(items) for package, items in disabled.items()},
          'recovery_guard_enabled': True, 'recovery_guard_compiled': True,
          'lineage_updater_absent': True, 'required_google_apks': apps,
          'play_services_package_disabled': False, 'runtime_verified': False,
          'scope': 'OS firmware OTAs blocked; Google APK/APEX updates are not blocked.'}
(BASE / 'candidate-ota-protection.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
