"""Prepare revision metadata outside Ninja's read-only source sandbox."""
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
rule = SOURCE / 'vendor/lineage/build/tasks/build-manifest_xml.mk'
old = '''$(INSTALLED_BUILD_MANIFEST_XML_TARGET):
\tmkdir -p $(dir $@)
\tREPO_TRACE=0 python3 .repo/repo/repo manifest -o - -r | grep -Ev "proprietary_$(MANIFEST_EXCLUDES)" > $@
'''
new = '''# Sabrina: Repo updates configuration caches; prepare the pinned manifest before
# entering Ninja's read-only sandbox and only read/filter it in the build rule.
ifeq ($(TARGET_PRODUCT),lineage_gsi_sabrina16)
$(INSTALLED_BUILD_MANIFEST_XML_TARGET): $(OUT_DIR)/sabrina-source-manifest.xml
\tmkdir -p $(dir $@)
\tgrep -Ev "proprietary_$(MANIFEST_EXCLUDES)" $< > $@
else
''' + old + '''endif
'''
text = rule.read_text()
if 'sabrina-source-manifest.xml' not in text:
    if text.count(old) != 1:
        raise RuntimeError('Unexpected manifest build rule; review before patching')
    (BASE / 'build-manifest_xml.original.mk').write_text(text)
    rule.write_text(text.replace(old, new, 1))
output = SOURCE / 'out/sabrina-source-manifest.xml'
temporary = output.with_suffix('.xml.tmp')
with temporary.open('w') as stream:
    subprocess.run(['repo', 'manifest', '-r'], cwd=SOURCE, stdout=stream, check=True)
projects = ET.parse(temporary).getroot().findall('project')
if not projects or any(not re.fullmatch('[0-9a-f]{40}', item.get('revision', ''))
                       for item in projects):
    raise RuntimeError('Source manifest is not fully pinned')
if not output.exists() or output.read_bytes() != temporary.read_bytes():
    temporary.replace(output)
else:
    temporary.unlink()
print(f'Prepared {len(projects)} pinned project revisions; build sandbox remains enabled.')
