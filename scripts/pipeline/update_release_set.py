"""Copy changed files from a signed target-files zip into a release image set, then re-sign it. No USB access.

Usage: update_release_set.py <source set> <recovery.img>
"""
from pathlib import Path
import glob,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time,zipfile
T=Path('/opt/sabrina/android16');H=T/'out/host/linux-x86/bin';K=Path('/opt/sabrina/release-keys');AVB=K/'avb.pem'
SIGNED='/opt/sabrina/release-work/signed-target-files.zip'
S=Path(sys.argv[1]);RECOVERY=Path(sys.argv[2]);assert (S/'RELEASE').is_file(),'source must be a release set'
RECOVERY_SIZE=25165824;assert RECOVERY.stat().st_size==RECOVERY_SIZE and RECOVERY.read_bytes()[:8]==b'ANDROID!'
# Only what these features touch. Anything else stays exactly as it is on the device.
CHANGED=re.compile(r'SYSTEM/(framework/services\.jar|framework/oat/arm/services\.|'
    r'system_ext/etc/default-permissions/default-permissions_org\.lineageos\.updater\.xml$|'
    r'system_ext/etc/permissions/(Updater|com\.android\.tv\.settings)\.xml$|'
    r'system_ext/priv-app/(SystemUI|TvSystemUI|TvSettingsTwoPanel|Updater)/|'
    r'(priv-app|system_ext/priv-app|product/priv-app|app|product/app)/DocumentsUI/|'
    r'(etc|system_ext/etc|product/etc)/permissions/(.*documentsui.*|.*org\.lineageos\.updater.*)|'
    r'system_ext/etc/init/init\.lineage-updater\.rc$|product/etc/sysconfig/sabrina-ota-components\.xml$|'
    r'(etc|product/etc|system_ext/etc)/(sysconfig|permissions)/sabrina-ota-components\.xml$)')
def run(*a):return subprocess.run([str(x) for x in a],check=True,capture_output=True,text=True,errors='replace',env={**os.environ,'PATH':f"{H}:{os.environ['PATH']}"}).stdout
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
work=Path('/opt/sabrina/watchdog-images')/str(int(time.time()));work.mkdir();(work/'RELEASE').write_text('release keys\n')
system=work/'system.img';shutil.copyfile(S/'system.img',system)
info=run(H/'avbtool','info_image','--image',system);size=int(re.search(r'Image size:\s+(\d+)',info)[1]);run(H/'avbtool','erase_footer','--image',system)
L=work/'files';L.mkdir();debugfs=H/'debugfs_static'
def exists(path):
    return 'Type: ' in run(debugfs,'-R',f'stat {path}',system)
def mkdirs(path,label):
    edits=[];parts=path.strip('/').split('/');cur=''
    for part in parts:
        cur+='/'+part
        if not exists(cur):edits+=[f'mkdir {cur}',f'set_inode_field {cur} mode 040755',f'set_inode_field {cur} uid 0',f'set_inode_field {cur} gid 0',f'ea_set -f {label} {cur} security.selinux']
    return edits
label_dir=work/'label-dir';run(debugfs,'-R',f'ea_get -f {label_dir} /system/etc security.selinux',system)
label_file=work/'label-file';run(debugfs,'-R',f'ea_get -f {label_file} /system/etc/hosts security.selinux',system)
label_exec=work/'label-exec';run(debugfs,'-R',f'ea_get -f {label_exec} /system/bin/toybox security.selinux',system)
plan=[];i=0
with zipfile.ZipFile(SIGNED) as z:
    names=[n for n in z.namelist() if CHANGED.search(n) and not n.endswith('/')];assert any('Updater/Updater.apk' in n for n in names),'Updater missing';assert any(n.endswith('services.jar') for n in names)
    for n in names:
        i+=1;local=L/str(i);local.write_bytes(z.read(n));plan.append(('/system/'+n[7:],local,0o644,label_file))
    print('from build',len(names));print('\n'.join(n[7:] for n in names if n.endswith(('.apk','.jar','.xml','.rc'))))
# Recovery switch: applied at boot, only while persist.vendor.recovery_update is on.
shutil.copyfile(RECOVERY,L/'recovery.img');(L/'recovery.sha256').write_text(digest(RECOVERY)+'\n')
(L/'rc').write_text('''service sabrina_update_recovery /system/bin/sh /system/bin/sabrina-update-recovery.sh
    user root
    group root
    disabled
    oneshot

on property:sys.boot_completed=1 && property:persist.vendor.recovery_update=true
    start sabrina_update_recovery
''')
(L/'sh').write_text('''#!/system/bin/sh
# Write the recovery bundled with this ROM. Touches no other partition.
image=/system/etc/sabrina-recovery.img
target=/dev/block/by-name/recovery
size=%d
expected=$(cat /system/etc/sabrina-recovery.sha256)
[ "$(sha256sum "$image" | cut -d' ' -f1)" = "$expected" ] || { log -t sabrina-recovery "bundled image is damaged"; exit 1; }
[ "$(stat -c %%s "$image")" = "$size" ] || { log -t sabrina-recovery "bundled image has the wrong size"; exit 1; }
[ "$(blockdev --getsize64 "$target")" = "$size" ] || { log -t sabrina-recovery "partition has the wrong size"; exit 1; }
[ "$(sha256sum "$target" | cut -d' ' -f1)" = "$expected" ] && { log -t sabrina-recovery "already up to date"; exit 0; }
dd if="$image" of="$target" bs=1048576 conv=fsync
[ "$(sha256sum "$target" | cut -d' ' -f1)" = "$expected" ] && log -t sabrina-recovery "updated" || log -t sabrina-recovery "update failed"
'''%RECOVERY_SIZE)
plan+=[('/system/etc/sabrina-recovery.img',L/'recovery.img',0o644,label_file),('/system/etc/sabrina-recovery.sha256',L/'recovery.sha256',0o644,label_file),
       ('/system/etc/init/sabrina-recovery.rc',L/'rc',0o644,label_file),('/system/bin/sabrina-update-recovery.sh',L/'sh',0o755,label_exec)]
# Stamp this build's date, so Settings > About shows which build is installed.
now=int(time.time());stamp_date=time.strftime('%a %b %d %H:%M:%S UTC %Y',time.gmtime(now)).replace(' 0',' ',1);stamp_day=time.strftime('%Y%m%d',time.gmtime(now))
def stamp(text):
    text=re.sub(rb'^(ro(?:\.[a-z_]+)?\.build\.date)=.*$',lambda m:m[1]+b'='+stamp_date.encode(),text,flags=re.M)
    text=re.sub(rb'^(ro(?:\.[a-z_]+)?\.build\.date\.utc)=.*$',lambda m:m[1]+b'='+str(now).encode(),text,flags=re.M)
    return re.sub(rb'^((?:ro\.lineage\.(?:display\.)?version|ro\.modversion)=.*?)\d{8}',lambda m:m[1]+stamp_day.encode(),text,flags=re.M)
def prop_file(path,name):
    local=L/name;run(debugfs,'-R',f'dump {path} {local}',system)
    mode=int(re.search(r'Mode:\s+(0[0-7]+)',run(debugfs,'-R',f'stat {path}',system))[1],8);return local,mode
# Rooted debugging is on, at the user's request. With it, YouTube offered at most 1440p in testing.
prop,mode=prop_file('/system/build.prop','build.prop');text=prop.read_bytes()
prop.write_bytes(stamp(text.replace(b'ro.debuggable=0\n',b'ro.debuggable=1\n')))
assert b'ro.debuggable=1\n' in prop.read_bytes() and b'ro.adb.secure=1\n' in text;plan.append(('/system/build.prop',prop,mode,label_file))
ext,mode=prop_file('/system/system_ext/etc/build.prop','system_ext.build.prop');ext.write_bytes(stamp(ext.read_bytes()));plan.append(('/system/system_ext/etc/build.prop',ext,mode,label_file))
# Framework overlay, rebuilt from the repo so it carries the remote's global keys.
O=Path(__file__).resolve().parents[2]/'device/google/sabrina16/rro/SabrinaFrameworkOverlay'
if not O.is_dir():O=Path(os.environ.get('SABRINA_REPO','/path/to/lineageos-23-sabrina'))/'device/google/sabrina16/rro/SabrinaFrameworkOverlay'
assert (O/'res/xml/global_keys.xml').is_file(),'run apply_remote_wake.py first'
R=L/'rro';R.mkdir();framework=T/'out/target/product/generic/system/framework/framework-res.apk'
run(H/'aapt2','compile','--dir',O/'res','-o',R/'res.zip')
run(H/'aapt2','link','--no-resource-deduping','-I',framework,'--manifest',O/'AndroidManifest.xml','-o',R/'unsigned.apk',R/'res.zip')
run(H/'zipalign','-f','4',R/'unsigned.apk',R/'aligned.apk')
java=sorted(glob.glob(str(T/'prebuilts/jdk/jdk[0-9]*/linux-x86/bin/java')),key=lambda p:int(re.search(r'jdk(\d+)',p)[1]))[-1]
run(java,f'-Djava.library.path={T/"out/host/linux-x86/lib64"}','-jar',T/'out/host/linux-x86/framework/signapk.jar',K/'platform.x509.pem',K/'platform.pk8',R/'aligned.apk',L/'SabrinaFrameworkOverlay.apk')
plan.append(('/system/product/overlay/SabrinaFrameworkOverlay.apk',L/'SabrinaFrameworkOverlay.apk',0o644,label_file))
# Battery of remotes and accessories: this build's product partition turns the Bluetooth battery client off.
bas,mode=prop_file('/system/product/etc/build.prop','product.build.prop');text=bas.read_bytes()
bas.write_bytes(stamp(text.replace(b'bluetooth.profile.bas.client.enabled=false\n',b'bluetooth.profile.bas.client.enabled=true\n')))
assert b'bluetooth.profile.bas.client.enabled=true\n' in bas.read_bytes();plan.append(('/system/product/etc/build.prop',bas,mode,label_file))
edits=[]
for path,local,mode,label in plan:
    parent=path.rsplit('/',1)[0]
    new=mkdirs(parent,label_dir)
    if new:
        batch=work/'dirs.debugfs';batch.write_text('\n'.join(new)+'\n');run(debugfs,'-w','-f',batch,system)
    edits+=[f'rm {path}',f'write {local} {path}',f'set_inode_field {path} mode 0100{mode:o}',f'set_inode_field {path} uid 0',f'set_inode_field {path} gid 0',f'ea_set -f {label} {path} security.selinux']
batch=work/'release.debugfs';batch.write_text('\n'.join(edits)+'\n')
log=run(debugfs,'-w','-f',batch,system);(work/'release-debugfs.log').write_text(log);assert 'No space' not in log and 'Could not' not in log,log[-500:]
print(run('e2fsck','-f','-n',system)[-120:])
A=Path(tempfile.mkdtemp(dir='/opt/sabrina/watchdog-work'));run('mount','-o','ro,loop',system,A)
try:
    for path,local,_,_ in plan:assert digest(A/path.lstrip('/'))==digest(local),path
    with zipfile.ZipFile(A/'system/etc/security/otacerts.zip') as certs:assert certs.read(certs.namelist()[0]).strip()==(K/'releasekey.x509.pem').read_bytes().strip()
finally:run('umount',A);A.rmdir()
cmd=[H/'avbtool','add_hashtree_footer','--image',system,'--partition_name','system','--partition_size',size,'--algorithm','SHA256_RSA2048','--key',AVB,'--rollback_index','0','--hash_algorithm','sha256']
for k,v in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",info,re.M):cmd+=['--prop',k+':'+v]
run(*cmd)
names=['boot','dt','dtbo','odm','product','system','system_dlkm','vendor']
for n in names:
    if n not in('boot','system'):os.link(S/(n+'.img'),work/(n+'.img'))
shutil.rmtree(L)
for mode in ('permissive','enforcing'):
    folder=work/mode;folder.mkdir();os.link(S/mode/'boot.img',folder/'boot.img')
    cmd=[H/'avbtool','make_vbmeta_image','--output',folder/'vbmeta.img','--key',AVB,'--algorithm','SHA256_RSA2048','--rollback_index','0','--rollback_index_location','0','--flags','0','--padding_size','65536']
    for n in names:cmd+=['--include_descriptors_from_image',folder/'boot.img' if n=='boot' else work/(n+'.img')]
    run(*cmd)
# Super, using the layout from docs/BUILDING.md. Partitions are written at their image sizes.
raw=work/'super.raw.img';sparse=work/'super.sparse.img';SUPER=2084569088;GROUP=2080374784
parts=['system','vendor','product','odm','system_dlkm'];cmd=[H/'lpmake','--metadata-size','65536','--super-name','super','--metadata-slots','2','--device',f'super:{SUPER}','--group',f'amlogic_dynamic_partitions:{GROUP}','--block-size','4096','--output',raw]
total=0
for n in parts:
    b=(work/(n+'.img')).stat().st_size;total+=b;cmd+=['--partition',f'{n}:readonly:{b}:amlogic_dynamic_partitions','--image',f'{n}={work/(n+".img")}']
assert total<=GROUP,'images do not fit the group';run(*cmd);run(H/'img2simg',raw,sparse);raw.unlink()
report={n:digest(work/(n+'.img')) for n in parts};report.update(super_sparse=digest(sparse),boot=digest(work/'permissive/boot.img'),vbmeta=digest(work/'permissive/vbmeta.img'),work=str(work),used=total,group=GROUP)
V=work/'verify';V.mkdir();os.symlink(work/'permissive/boot.img',V/'boot.img');os.symlink(work/'permissive/vbmeta.img',V/'vbmeta.img')
for n in names:
    if n!='boot':os.symlink(work/(n+'.img'),V/(n+'.img'))
print(run(H/'avbtool','verify_image','--image',V/'vbmeta.img','--key',AVB)[-160:]);shutil.rmtree(V);(work/'REPORT.json').write_text(json.dumps(report,indent=1));print(json.dumps(report,indent=1))
