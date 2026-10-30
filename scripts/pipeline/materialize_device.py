"""Stage the experimental framework-only device target in the Linux source tree.

Run inside Sabrina-Android16. This copies build inputs only; it never flashes.
"""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
STOCK = Path('/opt/sabrina/stock')
TARGET = Path('/opt/sabrina/android16/device/google/sabrina16')


def extract_entries(source, target, selector):
    tree = ET.parse(source)
    root = ET.Element(tree.getroot().tag)
    for element in tree.getroot():
        if selector(element):
            root.append(element)
    if not len(root):
        raise ValueError(f'No matching Google TV configuration in {source}')
    ET.indent(root)
    ET.ElementTree(root).write(target, encoding='utf-8', xml_declaration=True)


def main():
    inventory = json.loads((BASE / 'stock-inventory.json').read_text())
    known = {entry['path']: entry['sha256'] for entry in inventory['files']}
    needed = [
        'product/priv-app/TVLauncherXPrebuilt/TVLauncherXPrebuilt.apk',
        'system/system/etc/vintf/compatibility_matrix.4.xml',
        'product/etc/permissions/privapp-permissions-atv-amati-product.xml',
        'product/etc/default-permissions/default-permissions-amati.xml',
        'product/etc/sysconfig/amati_experience.xml',
    ]
    for relative in needed:
        with (STOCK / relative).open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != known[relative]:
            raise ValueError(f'Stock input hash mismatch: {relative}')
    shutil.copytree(BASE / 'device', TARGET, dirs_exist_ok=True)
    (TARGET / 'proprietary').mkdir(exist_ok=True)
    (TARGET / 'compatibility').mkdir(exist_ok=True)
    shutil.copyfile(STOCK / needed[0], TARGET / 'proprietary/TVLauncherXPrebuilt.apk')
    shutil.copyfile(STOCK / needed[1], TARGET / 'compatibility/compatibility_matrix.4.xml')
    launcher = 'com.google.android.apps.tv.launcherx'
    extract_entries(STOCK / needed[2], TARGET / 'permissions/privapp-permissions-sabrina-launcher.xml',
                    lambda entry: entry.get('package') == launcher)
    extract_entries(STOCK / needed[3], TARGET / 'permissions/sabrina-launcher-defaults.xml',
                    lambda entry: entry.get('package') == launcher)
    # Retain only the launcher's existing Google TV identity/background settings.
    # The source also advertises Fast Pair/admin: don't claim those work here yet.
    extract_entries(STOCK / needed[4], TARGET / 'permissions/sabrina-google-tv.xml',
                    lambda entry: entry.get('name') == 'com.google.android.feature.AMATI_EXPERIENCE'
                    or entry.get('package') == launcher)
    print(f'Staged experimental device target: {TARGET}')


if __name__ == '__main__':
    main()
