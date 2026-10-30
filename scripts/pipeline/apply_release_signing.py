"""Carry release signatures into the final image set and re-sign AVB. Writes files only; no USB access."""
from pathlib import Path
import glob,gzip,hashlib,io,json,os,re,shlex,shutil,subprocess,sys,tempfile,time,zipfile
base=Path(__file__).resolve().parent;tools=base.parent/'mkbootimg-tools';T=Path('/opt/sabrina/android16');H=T/'out/host/linux-x86'
K=Path('/opt/sabrina/release-keys');AVB=K/'avb.pem'
status=base/'WATCHDOG-IMAGE-SET.json';src=json.loads(status.read_text());assert src['phase']=='development_avb_set_offline_verified'
S=Path(src['work']);assert not (S/'RELEASE').exists(),'source is already a release set'
U=glob.glob(str(T/'out/target/product/generic/obj/PACKAGING/target_files_intermediates/*-target_files*.zip'))[0];Z='/opt/sabrina/release-work/signed-target-files.zip'
work=Path('/opt/sabrina/watchdog-images')/str(int(time.time()));work.mkdir();(work/'RELEASE').write_text('release keys\n')
env={**os.environ,'PATH':str(H/'bin')+os.pathsep+os.environ['PATH']}
def run(*a):return subprocess.run([str(x) for x in a],check=True,capture_output=True,text=True,errors='replace',env=env).stdout
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
java=sorted(glob.glob(str(T/'prebuilts/jdk/jdk[0-9]*/linux-x86/bin/java')),key=lambda p:int(re.search(r'jdk(\d+)',p)[1]))[-1]
debugfs=H/'bin/debugfs_static';system=work/'system.img';shutil.copyfile(S/'system.img',system)
info=run(H/'bin/avbtool','info_image','--image',system);size=int(re.search(r'Image size:\s+(\d+)',info)[1]);run(H/'bin/avbtool','erase_footer','--image',system)
zu,zs=zipfile.ZipFile(U),zipfile.ZipFile(Z);nu={i.filename:i for i in zu.infolist() if not i.is_dir()};ns={i.filename:i for i in zs.infolist() if not i.is_dir()}
changed=[n for n in ns if n.startswith('SYSTEM/') and (nu[n].CRC!=ns[n].CRC or nu[n].file_size!=ns[n].file_size)]
A=Path(tempfile.mkdtemp(dir='/opt/sabrina/watchdog-work'));run('mount','-o','ro,loop',S/'system.img',A)
L=work/'signed-files';L.mkdir();plan={};removed=[];textual=[]
ALLOWED_ABSENT={'product/app/LeanbackIME/LeanbackIME.apk','product/priv-app/TvProvision/TvProvision.apk','system_ext/priv-app/LineageSetupWizard/LineageSetupWizard.apk'}
ALLOWED_PROP={'build.prop','product/etc/build.prop','system_ext/etc/build.prop'}
try:
    for n in changed:
        r=n[7:];p=A/'system'/r;out=L/hashlib.sha1(r.encode()).hexdigest()
        if not p.exists():
            assert r in ALLOWED_ABSENT,'unexpected absent '+r;removed.append(r);continue
        cur=p.read_bytes()
        if cur==zu.read(n):out.write_bytes(zs.read(n))
        else:
            assert r in ALLOWED_PROP,'unexpected difference '+r
            new=cur.replace(b'test-keys',b'release-keys');assert new!=cur,r;out.write_bytes(new);textual.append(r)
        plan['/system/'+r]=out
    # Overlays added after the build package, signed with the matching release certificate.
    for name,folder,certname in (('SabrinaFrameworkOverlay','rro-fw','platform'),('SabrinaTvSettingsOverlay','rro-ts','platform'),('SabrinaWifiOverlay','rro-wf','releasekey')):
        out=L/(name+'.apk');run(java,f'-Djava.library.path={H/"lib64"}','-jar',H/'framework/signapk.jar',K/(certname+'.x509.pem'),K/(certname+'.pk8'),f'/opt/sabrina/watchdog-work/{folder}/aligned.apk',out)
        assert (A/'system/product/overlay'/(name+'.apk')).is_file();plan[f'/system/product/overlay/{name}.apk']=out
    for path,local in plan.items():assert local.stat().st_size>0,path
finally:run('umount',A);A.rmdir()
edits=[]
for path,local in plan.items():
    st=run(debugfs,'-R',f'stat {path}',system);assert 'Type: regular' in st and 'Links: 1 ' in st,path
    owner=re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',st);mode=re.search(r'Mode:\s+(0[0-7]+)',st)[1]
    label=local.with_suffix('.label');run(debugfs,'-R',f'ea_get -f {label} {path} security.selinux',system);assert label.stat().st_size>0,path
    edits+=[f'rm {path}',f'write {local} {path}',f'set_inode_field {path} mode 010{mode}',f'set_inode_field {path} uid {owner[1]}',f'set_inode_field {path} gid {owner[2]}',f'ea_set -f {label} {path} security.selinux']
batch=work/'release.debugfs';batch.write_text('\n'.join(edits)+'\n');log=run(debugfs,'-w','-f',batch,system)
(work/'release-debugfs.log').write_text(log);assert 'No space' not in log and 'Could not' not in log,log[-400:]
run('e2fsck','-f','-n',system)
A=Path(tempfile.mkdtemp(dir='/opt/sabrina/watchdog-work'));run('mount','-o','ro,loop',system,A)
try:
    for path,local in plan.items():assert digest(A/path.lstrip('/'))==digest(local),path
    prop=(A/'system/build.prop').read_text(errors='replace');assert 'ro.build.tags=release-keys' in prop and 'test-keys' not in prop
    assert (A/'system/product/priv-app/TVAxel/TVAxel.apk').is_file() and (A/'system/framework/services.jar').is_file()
    with zipfile.ZipFile(A/'system/etc/security/otacerts.zip') as certs:assert certs.read(certs.namelist()[0]).strip()==(K/'releasekey.x509.pem').read_bytes().strip()
    print('ota cert is the release key, tags release-keys, files',len(plan),'props',textual,'kept removed',removed)
finally:run('umount',A);A.rmdir()
cmd=[H/'bin/avbtool','add_hashtree_footer','--image',system,'--partition_name','system','--partition_size',size,'--algorithm','SHA256_RSA2048','--key',AVB,'--rollback_index','0','--hash_algorithm','sha256']
for k,v in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",info,re.M):cmd+=['--prop',k+':'+v.replace('test-keys','release-keys')]
run(*cmd)
names=['boot','dt','dtbo','odm','product','system','system_dlkm','vendor']
for n in names:
    if n not in('boot','system'):os.link(S/(n+'.img'),work/(n+'.img'))
shutil.copytree(S/'boot-original',work/'boot-original')
def parse(b):
    e=[];i=0
    while True:
        assert b[i:i+6]==b'070701'
        f=[int(b[i+6+8*n:i+14+8*n],16) for n in range(13)];s=i+110;nm=b[s:s+f[11]-1].decode();d=(s+f[11]+3)&~3
        e.append(dict(name=nm,fields=f,data=b[d:d+f[6]]));i=(d+f[6]+3)&~3
        if nm=='TRAILER!!!':return e
def build(entries):
    o=io.BytesIO()
    for x in entries:
        f=list(x['fields']);f[6]=len(x['data']);n=x['name'].encode()+b'\0';f[11]=len(n)
        o.write(b'070701'+b''.join(b'%08x'%v for v in f)+n);o.write(b'\0'*(-o.tell()&3));o.write(x['data']);o.write(b'\0'*(-o.tell()&3))
    o.write(b'\0'*(-o.tell()&255));return o.getvalue()
artifacts={}
pub=(K/'avb.avbpubkey').read_bytes()
for mode in ('permissive','enforcing'):
    src_boot=S/mode/'boot.img';t=work/('boot-'+mode);old=shlex.split(run(sys.executable,tools/'unpack_bootimg.py','--boot_img',src_boot,'--out',t,'--format','mkbootimg'))
    binfo=run(H/'bin/avbtool','info_image','--image',src_boot)
    entries=parse(gzip.decompress((t/'ramdisk').read_bytes()));hits=[e for e in entries if e['name'].endswith('sabrina-development.avbpubkey')];assert hits,'development key not in ramdisk'
    for e in hits:e['data']=pub
    (t/'ramdisk').write_bytes(gzip.compress(build(entries),9,mtime=0))
    folder=work/mode;folder.mkdir();boot=folder/'boot.img'
    run(sys.executable,tools/'mkbootimg.py',*old,'--output',boot)
    cmd=[H/'bin/avbtool','add_hash_footer','--image',boot,'--partition_name','boot','--partition_size','16777216','--algorithm','SHA256_RSA2048','--key',AVB,'--rollback_index','0','--hash_algorithm','sha256']
    for k,v in re.findall(r"^    Prop: (\S+) -> '([^']*)'$",binfo,re.M):cmd+=['--prop',k+':'+v.replace('test-keys','release-keys')]
    run(*cmd)
    cmd=[H/'bin/avbtool','make_vbmeta_image','--output',folder/'vbmeta.img','--key',AVB,'--algorithm','SHA256_RSA2048','--rollback_index','0','--rollback_index_location','0','--flags','0','--padding_size','65536']
    for n in names:cmd+=['--include_descriptors_from_image',boot if n=='boot' else work/(n+'.img')]
    run(*cmd)
    text=run(H/'bin/avbtool','info_image','--image',folder/'vbmeta.img');assert re.search(r'^Rollback Index:\s+0$',text,re.M) and re.search(r'^Flags:\s+0$',text,re.M)
    artifacts[mode]={p:dict(path=str(folder/(p+'.img')),bytes=(folder/(p+'.img')).stat().st_size,sha256=digest(folder/(p+'.img'))) for p in('boot','vbmeta')}
    shutil.rmtree(t)
shared={n:dict(path=str(work/(n+'.img')),bytes=(work/(n+'.img')).stat().st_size,sha256=digest(work/(n+'.img'))) for n in('system','vendor','product','odm','system_dlkm')}
shutil.rmtree(L)
shutil.copyfile(status,base/'WATCHDOG-IMAGE-SET.before-release.json')
state=dict(src,work=str(work),artifacts=shared,boot_variants=artifacts,release_signed=True,finished_unix=time.time());state.pop('steps',None);status.write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(dict(work=str(work),boot=artifacts['permissive']['boot']['sha256'][:16],vbmeta=artifacts['permissive']['vbmeta']['sha256'][:16],system=shared['system']['sha256'][:16]),indent=1))
