#!/usr/bin/env python3
"""Build sabrina's menu recovery: stock ramdisk base and dtb, Lineage's recovery from source, our kernel.
Writes files only and touches no device. Any failed check stops the build."""
import gzip,hashlib,io,json,re,shutil,subprocess,sys,tempfile,time,zipfile,shlex
from pathlib import Path
base=Path(__file__).resolve().parent;root=base.parent;tools=root/'mkbootimg-tools'
tree=Path('/opt/sabrina/android16');host=tree/'out/host/linux-x86/bin';built=tree/'out/target/product/generic/recovery/root'
stock=root/'stock-recovery-bundle-UTTC.250917.004/stock-images/recovery.img'
images=Path(sys.argv[1]);key=Path(sys.argv[2]);out=base/'sabrina-recovery';partition=25165824
WIPE=b'ro.odm.fdr.extra_wipe_partitions=cri_data,env,param,tee\n'
USB=b'ro.recovery.batteryless=true\nro.recovery.usb.vid=18D1\nro.recovery.usb.adb.pid=D001\nro.recovery.usb.fastboot.pid=4EE0\n'
def run(*a):return subprocess.run([str(x) for x in a],check=True,capture_output=True,text=True,errors='replace').stdout
def sha(b):return hashlib.sha256(b).hexdigest()
def need(ok,why):
    if not ok:sys.exit('STOP: '+why)
def parse(b):
    entries=[];i=0
    while True:
        need(b[i:i+6]==b'070701','bad cpio magic at %d'%i)
        f=[int(b[i+6+8*n:i+14+8*n],16) for n in range(13)]
        namesize,size=f[11],f[6];s=i+110;name=b[s:s+namesize-1].decode()
        d=(s+namesize+3)&~3;e=(d+size+3)&~3
        entries.append(dict(name=name,fields=f,data=b[d:d+size]));i=e
        if name=='TRAILER!!!':return entries
def build(entries):
    o=io.BytesIO()
    for e in entries:
        f=list(e['fields']);f[6]=len(e['data']);n=e['name'].encode()+b'\0';f[11]=len(n)
        o.write(b'070701'+b''.join(b'%08x'%x for x in f)+n)
        o.write(b'\0'*(-o.tell()&3));o.write(e['data']);o.write(b'\0'*(-o.tell()&3))
    o.write(b'\0'*(-o.tell()&255));return o.getvalue()
def unpack(img,folder):return run(sys.executable,'-I',tools/'unpack_bootimg.py','--boot_img',img,'--out',folder,'--format','mkbootimg')
need(b'Always show menu if no command is specified' in (tree/'bootable/recovery/recovery.cpp').read_bytes(),'source does not open the menu by default')
need((built/'system/bin/init').is_file() and (built/'system/bin/recovery').is_file(),'built recovery incomplete')
with tempfile.TemporaryDirectory() as t:
    t=Path(t);argv=unpack(stock,t/'s');raw=gzip.decompress((t/'s/ramdisk').read_bytes());entries=parse(raw)
    need(build(entries)==raw,'cpio round trip differs from stock')
    trailer=entries.pop();by={e['name']:e for e in entries};ino=max(e['fields'][0] for e in entries)
    def blank(mode,uid=0,gid=0,size=0):
        nonlocal_ino[0]+=1;return [nonlocal_ino[0],mode,uid,gid,1,0,size,0,0,0,0,0,0]
    nonlocal_ino=[ino];added=[];replaced=[]
    def ensure_dir(name):
        parts=name.split('/')
        for n in range(1,len(parts)):
            d='/'.join(parts[:n])
            if d not in by:
                e=dict(name=d,fields=blank(0o040755),data=b'');entries.append(e);by[d]=e;added.append(d)
    def put(name,mode,data,uid=0,gid=0):
        ensure_dir(name)
        if name in by:
            e=by[name];need((e['fields'][1]&0o170000)!=0o040000,'would replace a folder '+name)
            f=e['fields'];f[1]=mode;f[2]=uid;f[3]=gid;e['data']=data;replaced.append(name)
        else:
            e=dict(name=name,fields=blank(mode,uid,gid),data=data);entries.append(e);by[name]=e;added.append(name)
    for p in sorted(built.rglob('*')):
        rel=str(p.relative_to(built))
        if p.is_dir() and not p.is_symlink():continue
        if rel.startswith('system/bin/'):uid,gid,perm=0,2000,0o755
        elif rel.startswith('system/lib/'):uid,gid,perm=0,0,0o644
        else:uid,gid,perm=0,0,0o644
        if p.is_symlink():put(rel,0o120777,str(p.readlink()).encode(),uid,gid)
        else:put(rel,0o100000|perm,p.read_bytes(),uid,gid)
    for p in sorted((tree/'bootable/recovery/res-xhdpi/images').iterdir()):put('res/images/'+p.name,0o100644,p.read_bytes())
    # The stock Google plugin wiped env after a factory reset; Lineage's default plugin must replace it.
    ui=by['system/lib/librecovery_ui_ext.so']['data'];need(b'extra_wipe_partitions' not in ui and b'ChromecastDevice' not in ui,'stock wipe plugin still present')
    prop=by['prop.default'];need(prop['data'].count(WIPE)==1,'wipe list line not found once')
    prop['data']=prop['data'].replace(WIPE,b'')
    if b'ro.recovery.usb.vid' not in prop['data']:prop['data']=prop['data'].rstrip(b'\n')+b'\n'+USB
    name=zipfile.ZipFile(io.BytesIO(by['system/etc/security/otacerts.zip']['data'])).namelist();need(len(name)==1,'unexpected otacerts layout')
    # Only zips signed with the owner's release key verify; Google's OTAs do not.
    pem=Path(sys.argv[3]).read_bytes();need(b'BEGIN CERTIFICATE' in pem,'release certificate missing');z=io.BytesIO()
    with zipfile.ZipFile(z,'w',zipfile.ZIP_STORED) as a:
        i=zipfile.ZipInfo(name[0],(1980,1,1,0,0,0));i.compress_type=zipfile.ZIP_STORED;a.writestr(i,pem)
    by['system/etc/security/otacerts.zip']['data']=z.getvalue()
    new_raw=build(entries+[trailer]);(t/'ramdisk').write_bytes(gzip.compress(new_raw,9,mtime=0))
    kernel=images/'boot-original/kernel';need(kernel.is_file(),'our kernel missing')
    need(sha((t/'s/dtb').read_bytes())==sha((images/'boot-original/dtb').read_bytes()),'our dtb differs from recovery dtb')
    cmd=shlex.split(argv);p=[];i=0
    while i<len(cmd):
        p.append(cmd[i])
        if cmd[i]=='--kernel':p.append(str(kernel));i+=1
        elif cmd[i]=='--ramdisk':p.append(str(t/'ramdisk'));i+=1
        i+=1
    need('--recovery_dtbo' in p and str(kernel) in p,'mkbootimg arguments incomplete')
    run(sys.executable,tools/'mkbootimg.py',*p,'--output',t/'recovery.img')
    info=run(host/'avbtool','info_image','--image',stock);props=re.findall(r"Prop: (\S+) -> '(.*)'",info);need(props,'stock footer properties missing')
    sign=[host/'avbtool','add_hash_footer','--image',t/'recovery.img','--partition_name','recovery','--partition_size',partition,'--algorithm','SHA256_RSA2048','--key',key,'--rollback_index','0','--hash_algorithm','sha256']
    for k,v in props:sign+=['--prop',f'{k}:{v}']
    run(*sign)
    result=(t/'recovery.img').read_bytes();need(len(result)==partition,'image is not partition sized')
    # Everything below rereads the finished image.
    argv2=unpack(t/'recovery.img',t/'n')
    for f in ('dtb','second','recovery_dtbo'):need((t/'n'/f).read_bytes()==(t/'s'/f).read_bytes(),f+' changed')
    need((t/'n/kernel').read_bytes()==kernel.read_bytes(),'kernel is not ours')
    strip=lambda s:re.sub(r'--(kernel|ramdisk|second|dtb|recovery_dtbo) \S+','',s).split();need(strip(argv)==strip(argv2),'boot header changed')
    final={e['name']:e for e in parse(gzip.decompress((t/'n/ramdisk').read_bytes()))}
    for n in ('init','system/bin/init','system/bin/recovery','system/bin/linker','system/bin/adbd','system/bin/fastbootd','res/images/font_menu.png','sepolicy','system/etc/init/hw/init.rc','plat_file_contexts','prop.default','lib/modules/modules.load.recovery','lib/modules/amlogic-input.ko','lib/modules/dwc_otg.ko','system/etc/security/otacerts.zip'):need(n in final,'missing '+n)
    need(final['system/bin/recovery']['data']==(built/'system/bin/recovery').read_bytes(),'recovery differs from build')
    for n,e in final.items():
        need(b'by-name/env' not in e['data'] or n=='system/bin/systemcontrol_static' or n.endswith('file_contexts'),'env writer in '+n)
    need(b'extra_wipe_partitions' not in final['prop.default']['data'],'wipe list present')
    need(b'Install anyway?' in final['system/bin/recovery']['data'],'Install anyway prompt missing')
    need(b'ask_to_continue_unverified(Device* device) {\n  // The caller only asks' in (tree/'bootable/recovery/recovery.cpp').read_bytes(),'Install anyway patch missing from source')
    google=Path('/opt/sabrina/watchdog-work/reccmp/stock/r/system/etc/security/otacerts.zip')
    need(zipfile.ZipFile(google).read(name[0]) not in zipfile.ZipFile(io.BytesIO(final['system/etc/security/otacerts.zip']['data'])).read(name[0]),'Google OTA key still trusted')
    need(pem in zipfile.ZipFile(io.BytesIO(final['system/etc/security/otacerts.zip']['data'])).read(name[0]),'OTA key not replaced')
    verify=subprocess.run([str(host/'avbtool'),'verify_image','--image',str(t/'recovery.img'),'--key',str(key)],capture_output=True,text=True,errors='replace');need(verify.returncode==0,'AVB failed '+verify.stderr[-300:])
    check=run(host/'avbtool','info_image','--image',t/'recovery.img')
    out.mkdir(exist_ok=True);stamp=int(time.time());fin=out/f'recovery-menu-{stamp}.img';fin.write_bytes(result);need(sha(fin.read_bytes())==sha(result),'written image differs')
    report=dict(built_unix=stamp,image=fin.name,bytes=len(result),sha256=sha(result),kernel_sha256=sha(kernel.read_bytes()),added=len(added),replaced=len(replaced),ramdisk_gz_bytes=(t/'ramdisk').stat().st_size,payload_bytes=int(re.search(r'Original image size:\s+(\d+)',check)[1]),systemcontrol_kept='system/bin/systemcontrol_static' in final,flashed=False)
    (out/f'recovery-menu-{stamp}.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
