"""Offline board-config repair in a separate vendor image; never accesses USB."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,sys,time
base=Path(__file__).resolve().parent;root=Path('/opt/sabrina/android16')
host=root/'out/host/linux-x86/bin'
parent=json.loads((base/'DIAGNOSTIC-IMAGE-SET-STATUS.json').read_text())
native=json.loads((base/'CGROUP-OVERRIDE-NATIVE-VALIDATION.json').read_text())
assert native['passed'] and native['only_schedtune_optional_changed'] and not native['mounts_attempted']
override=base/'device/vendor-config/cgroups.json'
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert digest(override)==native['override_sha256']
work=Path('/opt/sabrina/cgroup-fixed-images')/str(int(time.time()));work.mkdir(parents=True)
state=dict(started_unix=time.time(),phase='preparing',work=str(work),device_accessed=False,
    firmware_written=False,ready_to_flash=False,runtime_boot_proven=False,steps={})
status=base/'CGROUP-FIX-IMAGE-SET.json'
def save():state['updated_unix']=time.time();status.write_text(json.dumps(state,indent=2)+'\n')
def run(label,cmd,allowed=(0,)):
    state['active_step']=label;save()
    r=subprocess.run(list(map(str,cmd)),text=True,capture_output=True,timeout=240,
        env={**os.environ,'PATH':str(host)+os.pathsep+os.environ.get('PATH','')})
    (work/(label+'.log')).write_text(r.stdout+r.stderr)
    state['steps'][label]=dict(exit_code=r.returncode)
    assert r.returncode in allowed,label+': '+r.stderr[-800:]
    return r.stdout+r.stderr
try:
    assert shutil.disk_usage('/mnt/d').free>40*1024**3
    source_device=root/'device/google/sabrina16'
    (source_device/'vendor-config').mkdir(exist_ok=True)
    source_config=source_device/'vendor-config/cgroups.json'
    assert not source_config.exists() or source_config.read_bytes()==override.read_bytes()
    shutil.copyfile(override,source_config)
    product=source_device/'lineage_gsi_sabrina16.mk'
    text=product.read_text();(work/'source-product-before.mk').write_text(text)
    copy_line='    device/google/sabrina16/vendor-config/cgroups.json:$(TARGET_COPY_OUT_VENDOR)/etc/cgroups.json'
    if copy_line not in text:
        product.write_text(text+'\n# Board-specific optional legacy controller; also included by the offline vendor assembler.\nPRODUCT_COPY_FILES += \\\n'+copy_line+'\n')
    sys.path.insert(0,str(root/'system/sepolicy/tests'))
    import policy
    binary=Path('/opt/sabrina/bootloop-offline-audit/1793298448/strict_runtime_order.bin')
    assert digest(binary)=='a4932e746a74af2f15a78cc7eec59bb3e56477f57cb5361e5fe14a3b7af5c3c4'
    pol=policy.Policy(str(binary),None,str(root/'out/host/linux-x86/lib64/libsepolwrap.so'))
    allowed=set()
    for rule in pol.QueryTERule(scontext=['init'],tcontext=['vendor_cgroup_desc_file']):
        if rule.flavor=='allow' and rule.tclass=='file':allowed.update(rule.perms)
    assert {'read','open','getattr'}.issubset(allowed)
    state['existing_init_config_permissions']=sorted(allowed)
    source=Path(parent['artifacts']['vendor']['path']);assert digest(source)==parent['artifacts']['vendor']['sha256']
    vendor=work/'vendor.img';shutil.copyfile(source,vendor)
    avbinfo=run('original-vendor-avb',[host/'avbtool','info_image','--image',source])
    run('erase-copy-footer',[host/'avbtool','erase_footer','--image',vendor])
    before_stat=run('original-etc-directory',[host/'debugfs_static','-R','stat /etc',source])
    assert 'Type: directory' in before_stat
    timestamps=re.findall(r'^\s*(ctime|atime|mtime|crtime): 0x([0-9a-f]+):([0-9a-f]+)',before_stat,re.M)
    assert len(timestamps)==4
    label=work/'cgroups.selinux';label.write_bytes(b'u:object_r:vendor_cgroup_desc_file:s0\0')
    commands=[f'write {override} /etc/cgroups.json','set_inode_field /etc/cgroups.json mode 0100644',
        'set_inode_field /etc/cgroups.json uid 0','set_inode_field /etc/cgroups.json gid 0',
        f'ea_set -f {label} /etc/cgroups.json security.selinux']
    for name,seconds,extra in timestamps:
        commands += [f'set_inode_field /etc {name}_lo {int(seconds,16)}',f'set_inode_field /etc {name}_extra {int(extra,16)}',
            f'set_inode_field /etc/cgroups.json {name}_lo {int(seconds,16)}',f'set_inode_field /etc/cgroups.json {name}_extra {int(extra,16)}']
    batch=work/'add-config.debugfs';batch.write_text('\n'.join(commands)+'\n')
    run('add-board-config',[host/'debugfs_static','-w','-f',batch,vendor])
    run('check-filesystem',['e2fsck','-f','-n',vendor])
    readback=work/'config.readback'
    run('readback-config',[host/'debugfs_static','-R',f'dump /etc/cgroups.json {readback}',vendor])
    assert digest(readback)==digest(override)
    meta=run('readback-metadata',[host/'debugfs_static','-R','stat /etc/cgroups.json',vendor])
    assert 'Type: regular' in meta and 'Mode:  0644' in meta and re.search(r'User:\s+0\s+Group:\s+0',meta)
    actual_label=work/'config.readback.selinux'
    run('readback-label',[host/'debugfs_static','-R',f'ea_get -f {actual_label} /etc/cgroups.json security.selinux',vendor])
    assert actual_label.read_bytes()==label.read_bytes()
    actual_dir=run('readback-directory',[host/'debugfs_static','-R','stat /etc',vendor])
    assert re.findall(r'^\s*(ctime|atime|mtime|crtime): 0x([0-9a-f]+):([0-9a-f]+)',actual_dir,re.M)==timestamps
    for name,image in [('before',source),('after',vendor)]:
        folder=work/(name+'-root');folder.mkdir()
        run('extract-'+name,[host/'debugfs_static','-R',f'rdump / {folder}',image])
    def inventory(folder):
        out={}
        for p in folder.rglob('*'):
            key=str(p.relative_to(folder))
            if p.is_symlink():out[key]=['symlink',os.readlink(p)]
            elif p.is_file():out[key]=['file',digest(p)]
            elif p.is_dir():out[key]=['directory']
        return out
    before=inventory(work/'before-root');after=inventory(work/'after-root')
    assert 'etc/cgroups.json' not in before
    assert set(after)-set(before)=={'etc/cgroups.json'} and set(before).issubset(after)
    assert all(after[name]==entry for name,entry in before.items())
    state['vendor_filesystem_added_files']=['etc/cgroups.json']
    state['all_existing_vendor_file_bytes_and_symlinks_unchanged']=True
    avb=json.loads((base/'DEVELOPMENT-IMAGE-STATUS.json').read_text())
    key=Path(avb['artifacts']['system']['path']).parent/'development-avb-private.pem'
    cmd=[host/'avbtool','add_hashtree_footer','--image',vendor,'--partition_name','vendor',
        '--partition_size','268435456','--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0','--hash_algorithm','sha256']
    for name,value in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",avbinfo,re.M):cmd+=['--prop',name+':'+value]
    run('sign-fixed-vendor',cmd)
    names=['boot','dt','dtbo','odm','product','system','system_dlkm','vendor']
    for name in names:
        if name=='vendor':continue
        entry=parent['artifacts'][name];assert digest(entry['path'])==entry['sha256']
        os.link(entry['path'],work/(name+'.img'))
    cmd=[host/'avbtool','make_vbmeta_image','--output',work/'vbmeta.img','--key',key,
        '--algorithm','SHA256_RSA2048','--rollback_index','0','--rollback_index_location','0','--flags','0','--padding_size','65536']
    for name in names:cmd+=['--include_descriptors_from_image',work/(name+'.img')]
    run('sign-matching-root',cmd)
    run('verify-root-and-eight-images',[host/'avbtool','verify_image','--image',work/'vbmeta.img','--key',key])
    for name in ['vendor','vbmeta']:
        text=run('verify-info-'+name,[host/'avbtool','info_image','--image',work/(name+'.img')])
        assert re.search(r'^Rollback Index:\s+0$',text,re.M) and re.search(r'^Flags:\s+0$',text,re.M)
    artifacts={name:dict(path=str(work/(name+'.img')),bytes=(work/(name+'.img')).stat().st_size,
        sha256=digest(work/(name+'.img'))) for name in names+['vbmeta']}
    for name in names:
        if name!='vendor':assert artifacts[name]['sha256']==parent['artifacts'][name]['sha256']
    state.update(phase='development_avb_set_offline_verified',artifacts=artifacts,
        scope='prospective_device_specific_cgroup_fix',kernel_and_system_byte_identical=True,
        policy_changed=False,launch_api_changed=False,new_rollback_indexes=0,verification_disabled=False,
        vendor_config_label='u:object_r:vendor_cgroup_desc_file:s0',vendor_config_sha256=digest(override),
        native_parser_validation='CGROUP-OVERRIDE-NATIVE-VALIDATION.json',
        required_runtime_validation=['CgroupSetup completes and creates system/apps subtrees','ueventd and apexd-bootstrap actually start',
            'Remaining Android16 boot, hardware, DRM, Google apps, OTA/privacy and legacy scheduling behavior'],
        flash_hold='DEVICE-WRITE-HOLD.json')
except Exception as error:state.update(phase='stopped_requires_review',error=str(error))
state.pop('active_step',None);state['finished_unix']=time.time();save()
print(json.dumps({k:v for k,v in state.items() if k not in ['steps','artifacts']},indent=2))
if state['phase']!='development_avb_set_offline_verified':raise SystemExit(1)
