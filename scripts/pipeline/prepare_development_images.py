"""Prepare a consistent developer-signed image set offline; never flash it.

Flags remain zero (verification enabled). All new rollback indexes are zero.
Acceptance of the developer key by the unlocked device remains unverified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
ROOT = Path('/opt/sabrina/android16')
HOST = ROOT/'out/host/linux-x86/bin'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-name',default='development-images-v4')
parser.add_argument('--boot-report',type=Path,default=BASE/'feature-boot-gsi-mount-component/verification.json')
parser.add_argument('--development-key',type=Path)
args = parser.parse_args()
assert re.fullmatch(r'development-images-[a-z0-9-]+',args.work_name)
WORK = Path('/opt/sabrina')/args.work_name
STOCK = BASE.parent/'stock-recovery-bundle-UTTC.250917.004/stock-images'
AVB = HOST/'avbtool'
report = dict(phase='preparing',device_modified=False,ready_to_flash=False,
              verification_disabled=False,new_rollback_indexes=0,steps={},started_unix=time.time())
env = dict(os.environ,PATH=str(HOST)+os.pathsep+os.environ.get('PATH',''))
def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def save():
    (BASE/'DEVELOPMENT-IMAGE-STATUS.json').write_text(json.dumps(report,indent=2)+'\n')
def run(name,command):
    report['active_step'] = name
    save()
    p = subprocess.run(list(map(str,command)),env=env,capture_output=True,text=True,timeout=600)
    (WORK/(name+'.log')).write_text(p.stdout+p.stderr)
    report['steps'][name] = dict(exit_code=p.returncode)
    assert p.returncode == 0,f'{name} failed; inspect preserved log'
    return p.stdout
try:
    assert not WORK.exists(),'Preserve previous image attempts'
    WORK.mkdir(parents=True)
    assert shutil.disk_usage('/mnt/d').free > 40*1024**3
    release = json.loads((BASE/'RELEASE-BUILD-STATUS.json').read_text())
    vendor = json.loads((BASE/'VENDOR-INTEGRATION-STATUS.json').read_text())
    assert release['compilation_complete'] and vendor['phase'] == 'integrated_metadata_and_contents_verified'
    assert json.loads((BASE/'integrated-candidate-policy.json').read_text())['all_static_policy_checks_passed']
    assert json.loads((BASE/'release-kernel-vintf.json').read_text())['compatible']
    boot = json.loads(args.boot_report.read_text())
    key = WORK/'development-avb-private.pem'
    if args.development_key:
        assert args.development_key.is_file() and args.development_key.is_absolute()
        shutil.copyfile(args.development_key,key)
    else:
        run('generate-development-key',['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',key])
    key.chmod(0o600)
    run('extract-development-public-key',[AVB,'extract_public_key','--key',key,'--output',WORK/'development-avb-public.bin'])
    if boot.get('developer_public_key_sha256'):
        assert digest(WORK/'development-avb-public.bin') == boot['developer_public_key_sha256'],'Ramdisk trust key must match every new AVB signature'
    sources = {'system':(Path(release['image']),release['image_sha256']),
               'vendor':(Path(vendor['image']),vendor['image_sha256']),
               'boot':(Path(boot['image']),boot['sha256'])}
    source_hashes = {}
    for name,(source,expected) in sources.items():
        assert digest(source) == expected,name
        shutil.copyfile(source,WORK/(name+'.img'))
        source_hashes[str(source)] = expected
    # Rebuild only the system AVB envelope: filesystem bytes are unchanged.
    system = WORK/'system.img'
    original = run('original-system-info',[AVB,'info_image','--image',system])
    fs_bytes = int(re.search(r'^Original image size:\s+(\d+)',original,re.M)[1])
    with system.open('rb') as stream:
        filesystem_hash = hashlib.sha256(stream.read(fs_bytes)).hexdigest()
    run('erase-copy-system-footer',[AVB,'erase_footer','--image',system])
    properties = (ROOT/'out/target/product/generic/system/build.prop').read_text()
    props = dict(line.split('=',1) for line in properties.splitlines() if '=' in line and not line.startswith('#'))
    command = [AVB,'add_hashtree_footer','--image',system,'--partition_name','system',
               '--partition_size',str(release['image_bytes']),'--algorithm','SHA256_RSA2048','--key',key,
               '--rollback_index','0','--hash_algorithm','sha256']
    patch = re.search(r"Prop: com.android.build.system.security_patch -> '([^']+)'",original)
    assert patch,'Retain the actual completed image security patch metadata'
    for name,value in [('os_version','16'),('fingerprint',props['ro.system.build.fingerprint']),
                       ('security_patch',patch[1])]:
        command += ['--prop','com.android.build.system.'+name+':'+value]
    run('sign-copy-system',command)
    with system.open('rb') as stream:
        assert hashlib.sha256(stream.read(fs_bytes)).hexdigest() == filesystem_hash
    maximum = run('sha256-vendor-max-size',[AVB,'add_hashtree_footer','--partition_size','268435456',
                    '--hash_algorithm','sha256','--calc_max_image_size'])
    assert vendor['image_bytes'] <= int(maximum.strip())
    def retained_properties(name):
        text = run('stock-properties-'+name,[AVB,'info_image','--image',STOCK/(name+'.img')])
        pairs = re.findall(r"^    Prop: (\S+) -> '([^']*)'$",text,re.M)
        assert pairs,'Expected original AVB metadata for '+name
        return [part for k,v in pairs for part in ['--prop',k+':'+v]]
    vendor_properties = retained_properties('vendor')
    boot_properties = retained_properties('boot')
    run('sign-copy-vendor',[AVB,'add_hashtree_footer','--image',WORK/'vendor.img','--partition_name','vendor',
          '--partition_size','268435456','--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0',
          '--hash_algorithm','sha256',*vendor_properties])
    run('sign-copy-boot',[AVB,'add_hash_footer','--image',WORK/'boot.img','--partition_name','boot',
          '--partition_size','16777216','--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0',
          '--hash_algorithm','sha256',*boot_properties])
    product = WORK/'product.img'
    with product.open('wb') as stream:
        stream.truncate(4*1024**2)
    run('make-valid-product',['mke2fs','-t','ext4','-F','-b','4096','-L','product',product])
    run('check-product',['e2fsck','-f','-n',product])
    product_props = dict(line.split('=',1) for line in (ROOT/'out/target/product/generic/system/product/etc/build.prop').read_text().splitlines()
                         if '=' in line and not line.startswith('#'))
    product_properties = [part for k,v in [('os_version',product_props['ro.product.build.version.release']),
        ('fingerprint',product_props['ro.product.build.fingerprint']),('security_patch',patch[1])]
        for part in ['--prop','com.android.build.product.'+k+':'+v]]
    run('sign-product',[AVB,'add_hashtree_footer','--image',product,'--partition_name','product',
          '--partition_size','8388608','--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0',
          '--hash_algorithm','sha256',*product_properties])
    manifest = json.loads((STOCK.parent/'manifest.json').read_text())
    known = {e['path']:e for e in manifest['files']}
    retained = ['dt','dtbo','odm','system_dlkm']
    for name in retained:
        source = STOCK/(name+'.img')
        expected = known['stock-images/'+name+'.img']['sha256']
        assert digest(source) == expected
        shutil.copyfile(source,WORK/(name+'.img'))
        source_hashes[str(source)] = expected
    names = ['boot','dt','dtbo','odm','product','system','system_dlkm','vendor']
    command = [AVB,'make_vbmeta_image','--output',WORK/'vbmeta.img','--key',key,
               '--algorithm','SHA256_RSA2048','--rollback_index','0','--rollback_index_location','0','--flags','0',
               '--padding_size','65536']
    for name in names:
        command += ['--include_descriptors_from_image',WORK/(name+'.img')]
    run('sign-development-root',command)
    info = run('development-root-info',[AVB,'info_image','--image',WORK/'vbmeta.img'])
    assert re.search(r'^Rollback Index:\s+0$',info,re.M) and re.search(r'^Flags:\s+0$',info,re.M)
    assert 'Chain Partition descriptor:' not in info
    assert sorted(re.findall(r'Partition Name:\s+(\S+)',info)) == sorted(names)
    run('verify-root-and-all-partitions',[AVB,'verify_image','--image',WORK/'vbmeta.img','--key',key])
    for name in ['boot','system','vendor','product']:
        info = run('info-'+name,[AVB,'info_image','--image',WORK/(name+'.img')])
        assert re.search(r'^Rollback Index:\s+0$',info,re.M)
        assert re.search(r'^Flags:\s+0$',info,re.M)
        assert re.search(r'^\s+Hash Algorithm:\s+sha256$',info,re.M)
        run('verify-'+name,[AVB,'verify_image','--image',WORK/(name+'.img'),'--key',key])
    assert all(digest(Path(path)) == expected for path,expected in source_hashes.items())
    artifacts = {name:dict(path=str(WORK/(name+'.img')),bytes=(WORK/(name+'.img')).stat().st_size,
                          sha256=digest(WORK/(name+'.img'))) for name in names+['vbmeta']}
    report.update(phase='development_avb_set_offline_verified',artifacts=artifacts,
        system_filesystem_bytes=fs_bytes,system_filesystem_sha256=filesystem_hash,
        all_eight_root_descriptors_verified=True,original_inputs_unchanged=True,selected_boot_report=str(args.boot_report),
        every_new_hash_descriptor_sha256=True,original_vendor_and_boot_avb_properties_retained=True,
        product_avb_properties_source='Actual Android16 framework product build; separate ext4 placeholder remains unmounted',
        retained_stock_partitions=retained,developer_public_key_sha256=digest(WORK/'development-avb-public.bin'),
        bootloader_key_acceptance_verified=False,persistent_rollback_behavior_verified=False,
        remaining=['Final super assembly and independent extent readback','Physical USB recovery and unlocked AVB acceptance review',
                   'Installation/rollback review and runtime hardware tests'])
except Exception as error:
    report.update(phase='failed_requires_review',error=str(error))
report.pop('active_step',None)
report['finished_unix'] = time.time()
save()
print(json.dumps(report,indent=2))
if report['phase'] != 'development_avb_set_offline_verified':
    raise SystemExit(1)
