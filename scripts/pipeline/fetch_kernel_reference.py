"""Fetch bounded official source metadata only; never flash or alter the kernel."""
import base64
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

BASE = Path(__file__).resolve().parent
DEST = BASE / 'reference' / 'official-kernel'
DEST.mkdir(parents=True, exist_ok=True)
requests = {
    'nest-readme.md': 'https://nest-open-source.googlesource.com/manifests/+/refs/heads/main/README.md?format=TEXT',
    'sabrina-499393.xml': 'https://nest-open-source.googlesource.com/manifests/+/refs/heads/main/chromecast_with_google_tv_4k/499393.xml?format=TEXT',
    'sabrina-462145.xml': 'https://nest-open-source.googlesource.com/manifests/+/refs/heads/main/chromecast_with_google_tv_4k/462145.xml?format=TEXT',
    'amlogic-driver-tree.json': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/?format=JSON',
    'gki-manifest.xml': 'https://android.googlesource.com/kernel/manifest/+/refs/heads/common-android14-5.15/default.xml?format=TEXT',
    'stock-commit.json': 'https://android.googlesource.com/kernel/common/+/f4a1f03072af?format=JSON',
    'build.config.sabrina': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/build.config.sabrina?format=TEXT',
    'build.config.amlogic': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/build.config.amlogic?format=TEXT',
    'amlogic-auto-patches.json': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/?format=JSON',
    'amlogic-common-patches.json': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/common14-5.15/?format=JSON',
    'sabrina_fragment.defconfig': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/arch/arm64/configs/sabrina_fragment.defconfig?format=TEXT',
    'amlogic_upgrade_u.defconfig': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/arch/arm64/configs/amlogic_upgrade_u.defconfig?format=TEXT',
    'lunch_patches.txt': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/common14-5.15/lunch_patches.txt?format=TEXT',
    'common-patch-tree.json': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/common14-5.15/common/?format=JSON',
    'amlogic_utils.sh': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/amlogic_utils.sh?format=TEXT',
    'kernel-environment-patches.json': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/common14-5.15/common/01_env/?format=JSON',
    'auto_patch.sh': 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver/+/997cd70d4a7705a53d751b3703cf0e9a600e42bc/auto_patch/auto_patch.sh?format=TEXT',
}
report = {'purpose': 'Source provenance investigation, not proof of stock ABI compatibility', 'downloads': []}
for name, url in requests.items():
    entry = {'file': name, 'url': url}
    try:
        # Reuse pinned successful downloads; do not repeatedly fetch unchanged
        # manifests during scheduled investigations. Refresh mutable branches.
        pinned = '/refs/heads/' not in url and name != 'stock-commit.json'
        if pinned and (DEST / name).is_file():
            data = (DEST / name).read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=20) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError('Metadata response exceeded size limit')
            if url.endswith('format=TEXT'):
                data = base64.b64decode(data, validate=True)
        (DEST / name).write_bytes(data)
        entry.update(status='downloaded', bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        entry.update(status='failed', error=str(error))
    report['downloads'].append(entry)
    print(name, entry['status'], flush=True)
    (DEST / 'fetch-report.json').write_text(json.dumps(report, indent=2) + '\n')
