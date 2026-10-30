"""Generate scoped privacy overrides; never disable a shared GMS API broker."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
KINDS = {'activity', 'activity-alias', 'service', 'receiver', 'provider'}


def manifest_components(path):
    current = None
    found = []
    for line in path.read_text().splitlines():
        tag = re.match(r'^( *)E: ([\w-]+)', line)
        if tag:
            depth, kind = len(tag[1]), tag[2]
            if current and depth <= current[0]:
                current = None
            if kind in KINDS:
                current = depth, kind
            continue
        name = re.match(r'^( *)A: .*android:name\([^)]*\)="([^"]+)"', line)
        if name and current and len(name[1]) == current[0] + 2:
            found.append({'kind': current[1], 'name': name[2]})
    return found


prefixes = ('com.google.android.gms.analytics.', 'com.google.android.gms.measurement.',
            'com.google.android.gms.ads.identifier.', 'com.google.android.gms.adid.service.',
            'com.google.android.gms.ads.measurement.', 'com.google.android.gms.clearcut.',
            'com.google.android.gms.feedback.')
gms = [entry for entry in manifest_components(BASE / 'gapps-gms-manifest.txt')
       if entry['kind'] in ('service', 'receiver', 'provider')
       and entry['name'].startswith(prefixes)]
if not gms:
    raise RuntimeError('No dedicated optional GMS telemetry components were found')
report = {'com.google.android.gms': gms}
android_name = '{http://schemas.android.com/apk/res/android}name'
for relative, prefix in [
    ('packages/apps/LineageParts/AndroidManifest.xml', 'org.lineageos.lineageparts.lineagestats.'),
    ('packages/modules/OnDevicePersonalization/AndroidManifest.xml', ''),
]:
    manifest = ET.parse(SOURCE / relative).getroot()
    package = manifest.get('package')
    found = []
    for component in manifest.find('application'):
        if component.tag not in ('service', 'receiver', 'provider'):
            continue
        name = component.get(android_name)
        if not name:
            continue
        if name.startswith('.'):
            name = package + name
        elif '.' not in name:
            name = package + '.' + name
        if not prefix or name.startswith(prefix):
            found.append({'kind': component.tag, 'name': name})
    if not found:
        raise RuntimeError(f'No optional components found in {relative}')
    report[package] = found

root = ET.Element('config')
for package, entries in report.items():
    node = ET.SubElement(root, 'component-override', package=package)
    for entry in entries:
        if package == 'com.google.android.gms' and not entry['name'].startswith(prefixes):
            raise RuntimeError('Refusing to disable an unrelated GMS component')
        ET.SubElement(node, 'component', {'class': entry['name'], 'enabled': 'false'})
ET.indent(root)
ET.ElementTree(root).write(BASE / 'device/permissions/sabrina-privacy-components.xml',
                           encoding='utf-8', xml_declaration=True)
(BASE / 'privacy-component-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({package: len(entries) for package, entries in report.items()}, indent=2))
