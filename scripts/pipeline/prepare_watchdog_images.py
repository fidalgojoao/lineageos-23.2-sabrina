"""Replace only init in the cgroup-fixed set; make permissive and enforcing boots. No USB access."""
from pathlib import Path
import hashlib,json,os,re,shlex,shutil,subprocess,sys,time
base=Path(__file__).resolve().parent
host=Path('/opt/sabrina/android16/out/host/linux-x86/bin');tools=base.parent/'mkbootimg-tools'
parent=json.loads((base/'CGROUP-FIX-IMAGE-SET.json').read_text())
build=json.loads((base/'WATCHDOG-INIT-BUILD.json').read_text());assert build['compiled']
avb=json.loads((base/'DEVELOPMENT-IMAGE-STATUS.json').read_text())
key=Path(avb['artifacts']['system']['path']).parent/'development-avb-private.pem';assert key.is_file()
work=Path('/opt/sabrina/watchdog-images')/str(int(time.time()));work.mkdir(parents=True)
status=base/'WATCHDOG-IMAGE-SET.json'
state=dict(started_unix=time.time(),phase='preparing',work=str(work),device_accessed=False,ready_to_flash=False,steps={})
def save():state['updated_unix']=time.time();status.write_text(json.dumps(state,indent=2)+'\n')
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(label,cmd,allowed=(0,)):
    state['active_step']=label;save()
    r=subprocess.run(list(map(str,cmd)),text=True,capture_output=True,timeout=400,
        env={**os.environ,'PATH':str(host)+os.pathsep+os.environ.get('PATH','')})
    (work/(label+'.log')).write_text(r.stdout+r.stderr)
    state['steps'][label]=dict(exit_code=r.returncode)
    assert r.returncode in allowed,label+': '+(r.stdout+r.stderr)[-800:]
    return r.stdout+r.stderr
TIMES=r'^\s*(ctime|atime|mtime|crtime): 0x([0-9a-f]+):([0-9a-f]+)'
try:
    art=parent['artifacts']
    for name,entry in art.items():assert digest(entry['path'])==entry['sha256'],name
    init=Path(build['artifact']);assert digest(init)==build['sha256']
    source=Path(art['system']['path']);system=work/'system.img';shutil.copyfile(source,system)
    stat=run('init-stat',[host/'debugfs_static','-R','stat /system/bin/init',source])
    assert 'Mode:  0755' in stat and 'Group:  2000' in stat and 'Links: 1 ' in stat
    label=work/'init.selinux'
    run('init-label',[host/'debugfs_static','-R',f'ea_get -f {label} /system/bin/init security.selinux',source])
    assert label.read_bytes()==b'u:object_r:init_exec:s0\0'
    info=run('system-avb',[host/'avbtool','info_image','--image',source])
    run('erase-footer',[host/'avbtool','erase_footer','--image',system])
    times=re.findall(TIMES,stat,re.M);assert len(times)==4
    edits=['rm /system/bin/init',f'write {init} /system/bin/init','set_inode_field /system/bin/init mode 0100755',
        'set_inode_field /system/bin/init uid 0','set_inode_field /system/bin/init gid 2000',
        f'ea_set -f {label} /system/bin/init security.selinux']
    for name,seconds,extra in times:
        edits+=[f'set_inode_field /system/bin/init {name}_lo {int(seconds,16)}',f'set_inode_field /system/bin/init {name}_extra {int(extra,16)}']
    batch=work/'init.debugfs';batch.write_text('\n'.join(edits)+'\n')
    run('replace-init',[host/'debugfs_static','-w','-f',batch,system])
    # Android 16's EGL loader skips its wildcard search once ro.board.platform names no driver.
    prop_path='/system/product/etc/build.prop'
    prop_stat=run('prop-stat',[host/'debugfs_static','-R',f'stat {prop_path}',source])
    assert 'Type: regular' in prop_stat and 'Links: 1 ' in prop_stat
    prop_old=work/'product-build.prop.old';run('prop-dump',[host/'debugfs_static','-R',f'dump {prop_path} {prop_old}',source])
    prop_text=prop_old.read_text();assert 'ro.hardware.egl' not in prop_text
    stock_props=dict(re.findall(r'^\[([^\]]+)\]: \[([^\]]*)\]',(base.parent/'device-properties-before.txt').read_text(errors='replace'),re.M))
    assert prop_text.count('bluetooth.device.class_of_device=90,2,12')==1
    prop_text=prop_text.replace('bluetooth.device.class_of_device=90,2,12','bluetooth.device.class_of_device='+stock_props['bluetooth.device.class_of_device'])
    assert prop_text.count('ro.com.google.clientidbase=android-google\n')==1
    prop_text=prop_text.replace('ro.com.google.clientidbase=android-google\n','ro.com.google.clientidbase='+stock_props['ro.com.google.clientidbase']+'\n')
    assert prop_text.count('ro.build.characteristics=emulator')==1
    prop_text=prop_text.replace('ro.build.characteristics=emulator','ro.build.characteristics='+stock_props['ro.build.characteristics'])
    # This stack ignores Google's apply_identity_addr_after_paired, so a bonded remote's directed
    # wake-up advertising never matches a rotating local address. Use the public address instead.
    prop_new=work/'product-build.prop';prop_new.write_text(prop_text.rstrip('\n')+'\nro.hardware.egl=mali\nbluetooth.core.gap.le.privacy.enabled=false\n')
    prop_label=work/'product-build.prop.selinux'
    run('prop-label',[host/'debugfs_static','-R',f'ea_get -f {prop_label} {prop_path} security.selinux',source])
    prop_owner=re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',prop_stat);prop_mode=re.search(r'Mode:\s+(0[0-7]+)',prop_stat)[1]
    prop_edits=[f'rm {prop_path}',f'write {prop_new} {prop_path}',f'set_inode_field {prop_path} mode 010{prop_mode}',
        f'set_inode_field {prop_path} uid {prop_owner[1]}',f'set_inode_field {prop_path} gid {prop_owner[2]}',
        f'ea_set -f {prop_label} {prop_path} security.selinux']
    for name,seconds,extra in re.findall(TIMES,prop_stat,re.M):
        prop_edits+=[f'set_inode_field {prop_path} {name}_lo {int(seconds,16)}',f'set_inode_field {prop_path} {name}_extra {int(extra,16)}']
    prop_batch=work/'prop.debugfs';prop_batch.write_text('\n'.join(prop_edits)+'\n')
    run('replace-prop',[host/'debugfs_static','-w','-f',prop_batch,system])
    prop_check=work/'product-build.prop.readback';run('prop-readback',[host/'debugfs_static','-R',f'dump {prop_path} {prop_check}',system])
    assert digest(prop_check)==digest(prop_new)
    debugfs=host/'debugfs_static'
    def rm_tree(path):
        listing=run('ls'+path.replace('/','-'),[debugfs,'-R',f'ls -p {path}',system])
        commands=[]
        for mode,name in re.findall(r'^/\d+/(\d+)/\d+/\d+/([^/]+)/',listing,re.M):
            if name in('.','..'):continue
            child=path+'/'+name
            if mode.startswith('04'):rm_tree(child)
            else:commands.append(f'rm {child}')
        commands.append(f'rmdir {path}')
        batch=work/('rm'+path.replace('/','-')+'.debugfs');batch.write_text('\n'.join(commands)+'\n')
        run('rm'+path.replace('/','-'),[debugfs,'-w','-f',batch,system])
        check=run('check'+path.replace('/','-'),[debugfs,'-R',f'stat {path}',system])
        assert 'File not found' in check,path
    # Two extra setup wizards leave Android with no recognised one, so SetupWraith is denied
    # NETWORK_SETUP_WIZARD and crashes in getCurrentNetwork when leaving basic mode.
    rm_tree('/system/product/priv-app/TvProvision')
    rm_tree('/system/system_ext/priv-app/LineageSetupWizard')
    rm_tree('/system/product/app/LeanbackIME')
    # Inherited from atv_emulator_vendor.mk; stock does not set it, and it makes setup skip itself.
    ext_path='/system/system_ext/etc/build.prop'
    ext_stat=run('ext-prop-stat',[debugfs,'-R',f'stat {ext_path}',source])
    assert 'Type: regular' in ext_stat and 'Links: 1 ' in ext_stat
    ext_old=work/'ext-build.prop.old';run('ext-prop-dump',[debugfs,'-R',f'dump {ext_path} {ext_old}',source])
    ext_text=ext_old.read_text();assert ext_text.count('ro.setupwizard.mode=DISABLED\n')==1
    ext_new=work/'ext-build.prop';ext_new.write_text(ext_text.replace('ro.setupwizard.mode=DISABLED\n',''))
    ext_label=work/'ext-build.prop.selinux';run('ext-prop-label',[debugfs,'-R',f'ea_get -f {ext_label} {ext_path} security.selinux',source])
    ext_owner=re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',ext_stat);ext_mode=re.search(r'Mode:\s+(0[0-7]+)',ext_stat)[1]
    ext_edits=[f'rm {ext_path}',f'write {ext_new} {ext_path}',f'set_inode_field {ext_path} mode 010{ext_mode}',
        f'set_inode_field {ext_path} uid {ext_owner[1]}',f'set_inode_field {ext_path} gid {ext_owner[2]}',f'ea_set -f {ext_label} {ext_path} security.selinux']
    ext_batch=work/'ext-prop.debugfs';ext_batch.write_text('\n'.join(ext_edits)+'\n')
    run('replace-ext-prop',[debugfs,'-w','-f',ext_batch,system])
    ext_check=work/'ext-build.prop.readback';run('ext-prop-readback',[debugfs,'-R',f'dump {ext_path} {ext_check}',system])
    assert digest(ext_check)==digest(ext_new)
    run('rm-lineage-suw-xml',[debugfs,'-w','-R','rm /system/system_ext/etc/permissions/LineageSetupWizard.xml',system])
    def label_of(path,name):
        out=work/name;run(name,[debugfs,'-R',f'ea_get -f {out} {path} security.selinux',source]);return out
    guard=json.loads((base/'WIPE-GUARD-BUILD.json').read_text())
    tree=Path('/opt/sabrina/android16')
    for relative,expected in guard.items():
        if relative=='finished_unix':continue
        built=tree/relative;assert digest(built)==expected,relative
        path='/system/system/'+relative.split('/system/',1)[1] if False else '/system/'+relative.split('generic/system/',1)[1]
        slug=path.replace('/','-');old_stat=run('stat'+slug,[debugfs,'-R',f'stat {path}',source])
        assert 'Type: regular' in old_stat and 'Links: 1 ' in old_stat,path
        label=label_of(path,'label'+slug)
        owner=re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',old_stat);mode=re.search(r'Mode:\s+(0[0-7]+)',old_stat)[1]
        edits=[f'rm {path}',f'write {built} {path}',f'set_inode_field {path} mode 010{mode}',f'set_inode_field {path} uid {owner[1]}',
            f'set_inode_field {path} gid {owner[2]}',f'ea_set -f {label} {path} security.selinux']
        batch=work/('replace'+slug+'.debugfs');batch.write_text('\n'.join(edits)+'\n')
        run('replace'+slug,[debugfs,'-w','-f',batch,system])
        back=work/('back'+slug);run('back'+slug,[debugfs,'-R',f'dump {path} {back}',system]);assert digest(back)==expected,path
    # Stock's Google TV keyboard; Leanback stays installed as a fallback.
    gboard=Path('/opt/sabrina/stock/product/app/LatinIMEGoogleTvPrebuilt/LatinIMEGoogleTvPrebuilt.apk');assert gboard.is_file()
    app_dir='/system/product/app/LatinIMEGoogleTvPrebuilt';apk=app_dir+'/LatinIMEGoogleTvPrebuilt.apk'
    dir_label=label_of('/system/product/app','label-app-dir')
    file_label=label_of('/system/product/app/webview/webview.apk','label-app-file')
    edits=[f'mkdir {app_dir}',f'set_inode_field {app_dir} mode 040755',f'set_inode_field {app_dir} uid 0',f'set_inode_field {app_dir} gid 0',
        f'ea_set -f {dir_label} {app_dir} security.selinux',f'write {gboard} {apk}',f'set_inode_field {apk} mode 0100644',
        f'set_inode_field {apk} uid 0',f'set_inode_field {apk} gid 0',f'ea_set -f {file_label} {apk} security.selinux']
    batch=work/'gboard.debugfs';batch.write_text('\n'.join(edits)+'\n')
    run('add-gboard',[debugfs,'-w','-f',batch,system])
    back=work/'gboard.readback';run('gboard-readback',[debugfs,'-R',f'dump {apk} {back}',system]);assert digest(back)==digest(gboard)
    run('fsck',['e2fsck','-f','-n',system])
    check=work/'init.readback';run('readback',[host/'debugfs_static','-R',f'dump /system/bin/init {check}',system])
    assert digest(check)==build['sha256']
    cmd=[host/'avbtool','add_hashtree_footer','--image',system,'--partition_name','system',
        '--partition_size',art['system']['bytes'],'--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0','--hash_algorithm','sha256']
    for name,value in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",info,re.M):cmd+=['--prop',name+':'+value]
    run('sign-system',cmd)
    names=['boot','dt','dtbo','odm','product','system','system_dlkm','vendor']
    for name in names:
        if name not in ('boot','system'):os.link(art[name]['path'],work/(name+'.img'))
    old=shlex.split(run('unpack-boot',[sys.executable,tools/'unpack_bootimg.py','--boot_img',art['boot']['path'],'--out',work/'boot-original','--format','mkbootimg']))
    boot_info=run('boot-avb',[host/'avbtool','info_image','--image',art['boot']['path']])
    index=old.index('--cmdline')+1;artifacts={}
    # Both modes share one super; only boot and root vbmeta differ between trials.
    for mode,extra in [('permissive',' sabrina.selinux=permissive'),('enforcing','')]:
        folder=work/mode;folder.mkdir();new=old[:];new[index]=(new[index]+extra).strip();assert len(new[index].encode())<1536
        boot=folder/'boot.img'
        run(mode+'-pack',[sys.executable,tools/'mkbootimg.py',*new,'--output',boot])
        cmd=[host/'avbtool','add_hash_footer','--image',boot,'--partition_name','boot','--partition_size','16777216',
            '--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0','--hash_algorithm','sha256']
        for name,value in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",boot_info,re.M):cmd+=['--prop',name+':'+value]
        run(mode+'-sign',cmd)
        cmd=[host/'avbtool','make_vbmeta_image','--output',folder/'vbmeta.img','--key',key,'--algorithm','SHA256_RSA2048',
            '--rollback_index','0','--rollback_index_location','0','--flags','0','--padding_size','65536']
        for name in names:
            image=boot if name=='boot' else work/(name+'.img')
            cmd+=['--include_descriptors_from_image',image]
        run(mode+'-vbmeta',cmd)
        artifacts[mode]={p:dict(path=str(folder/(p+'.img')),bytes=(folder/(p+'.img')).stat().st_size,sha256=digest(folder/(p+'.img'))) for p in ['boot','vbmeta']}
        text=run(mode+'-vbmeta-info',[host/'avbtool','info_image','--image',folder/'vbmeta.img'])
        assert re.search(r'^Rollback Index:\s+0$',text,re.M) and re.search(r'^Flags:\s+0$',text,re.M)
    shared={n:dict(path=str(work/(n+'.img')),bytes=(work/(n+'.img')).stat().st_size,sha256=digest(work/(n+'.img'))) for n in ['system','vendor','product','odm','system_dlkm']}
    for n in ['vendor','product','odm','system_dlkm']:assert shared[n]['sha256']==art[n]['sha256']
    state.update(phase='development_avb_set_offline_verified',artifacts=shared,boot_variants=artifacts,init_sha256=build['sha256'],
        rollback_indexes_zero=True,verification_disabled=False,diagnostic_only=True)
except Exception as error:state.update(phase='stopped_requires_review',error=str(error))
state.pop('active_step',None);state['finished_unix']=time.time();save()
print(json.dumps({k:v for k,v in state.items() if k!='steps'},indent=2))
if state['phase']!='development_avb_set_offline_verified':raise SystemExit(1)
