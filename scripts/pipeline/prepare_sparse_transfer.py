"""Round-trip actual custom and stock sparse images; no USB transfer."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE = Path(__file__).resolve().parent
HOST = Path('/opt/sabrina/android16/out/host/linux-x86/bin')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-name',default='sparse-transfer-v3')
parser.add_argument('--custom-report',type=Path,default=BASE/'DEVELOPMENT-SUPER-STATUS.json')
parser.add_argument('--status-output',type=Path,default=BASE/'SPARSE-TRANSFER-STATUS.json')
args = parser.parse_args()
assert args.work_name.startswith('sparse-transfer-') and '/' not in args.work_name and '\\' not in args.work_name
WORK = Path('/opt/sabrina')/args.work_name
state = dict(phase='preparing',device_modified=False,ready_to_flash=False,artifacts={},started_unix=time.time())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def save():
    args.status_output.write_text(json.dumps(state,indent=2)+'\n')
try:
    assert not WORK.exists(),'Preserve earlier sparse attempts'
    WORK.mkdir()
    custom = json.loads(args.custom_report.read_text())
    assert custom['phase'] == 'raw_super_offline_verified'
    stock = json.loads((BASE.parent/'stock-recovery-bundle-UTTC.250917.004/assembled-super/verification.json').read_text())
    for name,entry in [('custom',custom),('stock',stock)]:
        if name == 'stock':
            prior_report = BASE/'avb-v2-preserved-evidence/SPARSE-TRANSFER-STATUS.json'
            if prior_report.exists():
                prior = json.loads(prior_report.read_text())
                cached = prior['artifacts']['stock']
                sparse = Path(cached['path'])
                assert prior['phase'] == 'both_sparse_roundtrips_verified' and cached['roundtrip_identical']
                assert cached['original_raw_sha256'] == entry['sha256'] and cached['original_raw_bytes'] == entry['bytes']
                assert sparse.stat().st_size == cached['bytes'] and digest(sparse) == cached['sha256']
                state['artifacts'][name] = dict(cached,reused_unchanged_verified_sparse=True,
                                               previous_roundtrip_evidence=str(prior_report))
                save()
                continue
        source = Path(entry['image'])
        assert digest(source) == entry['sha256']
        state['active_image'] = name
        save()
        sparse = WORK/(name+'-super-UNTESTED.sparse.img')
        decoded = WORK/(name+'-super-roundtrip.raw.img')
        for label,command in [('encode',[HOST/'img2simg',source,sparse]),('decode',[HOST/'simg2img',sparse,decoded])]:
            result = subprocess.run(list(map(str,command)),capture_output=True,text=True,timeout=600)
            (WORK/(name+'-'+label+'.log')).write_text(result.stdout+result.stderr)
            assert result.returncode == 0,name+' '+label+' failed'
        assert decoded.stat().st_size == entry['bytes'] and digest(decoded) == entry['sha256']
        state['artifacts'][name] = dict(path=str(sparse),bytes=sparse.stat().st_size,sha256=digest(sparse),
            original_raw_bytes=entry['bytes'],original_raw_sha256=entry['sha256'],roundtrip_identical=True)
        save()
    state.update(phase='both_sparse_roundtrips_verified',device_sparse_support_verified=False,
                 max_download_size_verified=False,remaining=['Read-only physical USB recovery/fastboot inventory',
                    'Review actual device transfer support and bootloader AVB/rollback behavior'])
except Exception as error:
    state.update(phase='failed_requires_review',error=str(error))
state.pop('active_image',None)
state['finished_unix'] = time.time()
save()
print(json.dumps(state,indent=2))
if state['phase'] != 'both_sparse_roundtrips_verified':
    raise SystemExit(1)
