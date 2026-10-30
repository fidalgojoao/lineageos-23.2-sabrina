"""Assemble and independently read back developer super; no device operations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
HOST = Path('/opt/sabrina/android16/out/host/linux-x86/bin')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-name',default='development-super-v3')
parser.add_argument('--image-report',type=Path,default=BASE/'DEVELOPMENT-IMAGE-STATUS.json')
parser.add_argument('--status-output',type=Path,default=BASE/'DEVELOPMENT-SUPER-STATUS.json')
parser.add_argument('--apex-bootstrap-diagnostics',action='store_true')
args = parser.parse_args()
assert re.fullmatch(r'development-super-[a-z0-9-]+',args.work_name)
WORK = Path('/opt/sabrina')/args.work_name
state = dict(phase='preparing',device_modified=False,ready_to_flash=False,started_unix=time.time())
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def save():
    args.status_output.write_text(json.dumps(state,indent=2)+'\n')
try:
    avb = json.loads(args.image_report.read_text())
    if 'phase' in avb:
        assert avb['phase'] == 'development_avb_set_offline_verified'
    else:
        assert avb['stage'] == 'diagnostic_system_and_root_offline_verified'
        expected=['system/bin/apexd','system/bin/init','system/etc/init/apexd.rc'] if args.apex_bootstrap_diagnostics else ['system/bin/init']
        assert avb['filesystem_content_differences'] == expected
        if args.apex_bootstrap_diagnostics:
            reviewed=json.loads((BASE/'APEX-BOOTSTRAP-DIAGNOSTIC-REVIEW.json').read_text())
            build=json.loads((BASE/'APEX-BOOTSTRAP-DIAGNOSTIC-BUILD.json').read_text())
            assert reviewed['passed'] and not build['checks_bypassed'] and not build['policy_changed']
            assert avb['bootstrap_diagnostic_artifacts']==build['artifacts']
        assert avb['all_other_selected_partition_images_byte_identical']
        assert avb['boot_kernel_unchanged'] and avb['rollback_indexes_zero'] and avb['verification_enabled']
    state['source_image_report'] = str(args.image_report)
    assert not WORK.exists(),'Preserve previous super attempts'
    WORK.mkdir()
    assert shutil.disk_usage('/mnt/d').free > 20*1024**3
    names = ['system','vendor','product','odm','system_dlkm']
    artifacts = {n:avb['artifacts'][n] for n in names}
    for name,entry in artifacts.items():
        path = Path(entry['path'])
        assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'],name
        assert entry['bytes']%4096 == 0
    assert sum(v['bytes'] for v in artifacts.values()) <= 2080374784
    output = WORK/'super-development-UNTESTED.raw.img'
    command = [str(HOST/'lpmake'),'--metadata-size=65536','--metadata-slots=2',
        '--device=super:2084569088:1048576:0','--super-name=super',
        '--group=amlogic_dynamic_partitions:2080374784','--block-size=4096',
        '--force-full-image','--output='+str(output)]
    for name,entry in artifacts.items():
        command += [f'--partition={name}:readonly:{entry["bytes"]}:amlogic_dynamic_partitions',
                    f'--image={name}={entry["path"]}']
    state.update(phase='assembling',command=command)
    save()
    p = subprocess.run(command,capture_output=True,text=True,timeout=600)
    (WORK/'lpmake.log').write_text(p.stdout+p.stderr)
    assert p.returncode == 0,'Super assembly failed'
    assert output.stat().st_size == 2084569088
    dump = subprocess.check_output([str(HOST/'lpdump'),str(output)],text=True)
    (WORK/'layout.txt').write_text(dump)
    for expected in ['Metadata max size: 65536 bytes','Metadata slot count: 2','Metadata version: 10.0','First sector: 2048']:
        assert expected in dump,expected
    table = dump.split('Partition table:',1)[1].split('Super partition layout:',1)[0]
    records = re.findall(r'  Name: (\w+)\n(.*?)(?=  Name: |\Z)',table,re.S)
    ranges,readback = [],{}
    with output.open('rb') as stream:
        for name,body in records:
            assert name in artifacts and name not in readback
            assert 'Group: amlogic_dynamic_partitions' in body and 'Attributes: readonly' in body
            extents = re.findall(r'\s+(\d+) \.\. (\d+) linear super (\d+)',body)
            assert extents
            h = hashlib.sha256()
            logical = 0
            for first,last,physical in extents:
                first,last,physical = int(first),int(last),int(physical)
                assert first == logical and last >= first and physical >= 2048
                length = (last-first+1)*512
                offset = physical*512
                assert offset+length <= output.stat().st_size
                ranges.append((offset,offset+length,name))
                stream.seek(offset)
                remaining = length
                while remaining:
                    chunk = stream.read(min(remaining,1024**2))
                    assert chunk
                    h.update(chunk)
                    remaining -= len(chunk)
                logical = last+1
            assert logical*512 == artifacts[name]['bytes'] and h.hexdigest() == artifacts[name]['sha256'],name
            readback[name] = dict(bytes=logical*512,sha256=h.hexdigest(),matches_input=True)
    assert set(readback) == set(names)
    assert all(a[1] <= b[0] for a,b in zip(sorted(ranges),sorted(ranges)[1:]))
    state.update(phase='raw_super_offline_verified',image=str(output),bytes=output.stat().st_size,
        sha256=digest(output),partitions_readback=readback,no_overlapping_extents=True,
        geometry_matches_original=True,contains_bootloader_or_env=False,
        logical_partition_bytes=sum(v['bytes'] for v in artifacts.values()),
        group_budget_bytes=2080374784,
        remaining=['USB recovery/transfer limits and unlocked AVB acceptance verification',
                   'Final installation and rollback review','Runtime hardware/DRM/GApps tests'])
except Exception as error:
    state.update(phase='failed_requires_review',error=str(error))
state['finished_unix'] = time.time()
save()
print(json.dumps(state,indent=2))
if state['phase'] != 'raw_super_offline_verified':
    raise SystemExit(1)
