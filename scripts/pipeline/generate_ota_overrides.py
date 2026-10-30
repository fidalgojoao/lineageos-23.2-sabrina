"""Disable only OTA components declared by the exact app versions being built."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
KINDS = {'activity', 'activity-alias', 'service', 'receiver', 'provider'}


def components(path):
    found = []
    current = None
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


root = ET.Element('config')
report = {}
for package, path, prefix in [
    ('com.google.android.gms', BASE / 'gapps-gms-manifest.txt', 'com.google.android.gms.update.'),
    ('com.google.android.tungsten.setupwraith', BASE / 'gapps-setupwraith-manifest.txt',
     'com.android.systemupdateservice.'),
]:
    selected = [entry for entry in components(path) if entry['name'].startswith(prefix)]
    if not selected:
        raise RuntimeError(f'No OTA components found for {package}; review manifest parser')
    override = ET.SubElement(root, 'component-override', package=package)
    for entry in selected:
        ET.SubElement(override, 'component', {'class': entry['name'], 'enabled': 'false'})
    report[package] = selected

manifest = ET.parse(SOURCE / 'packages/apps/Updater/app/src/main/AndroidManifest.xml').getroot()
package = manifest.get('package')
android_name = '{http://schemas.android.com/apk/res/android}name'
override = ET.SubElement(root, 'component-override', package=package)
report[package] = []
for child in manifest.find('application'):
    if child.tag not in KINDS:
        continue
    name = child.get(android_name)
    if name.startswith('.'):
        name = package + name
    elif '.' not in name:
        name = package + '.' + name
    ET.SubElement(override, 'component', {'class': name, 'enabled': 'false'})
    report[package].append({'kind': child.tag, 'name': name})

ET.indent(root)
output = BASE / 'device/permissions/sabrina-ota-components.xml'
ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)
(BASE / 'ota-component-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({package: len(items) for package, items in report.items()}, indent=2))
