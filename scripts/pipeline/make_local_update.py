"""Build the signed zip the Updater installs. It never contains bootloader, env, logo or recovery.

Usage: make_local_update.py <release set> <output.zip> [--with-recovery]
"""
from pathlib import Path
import glob,re,subprocess,sys,tempfile,time,zipfile
T=Path('/opt/sabrina/android16');H=T/'out/host/linux-x86';K=Path('/opt/sabrina/release-keys')
S=Path(sys.argv[1]);OUT=Path(sys.argv[2]);assert (S/'RELEASE').is_file(),'release sets only'
BINARY=T/'out/target/product/generic/obj/EXECUTABLES/updater_intermediates/updater'
PARTS=['system','vendor','product','odm','system_dlkm'];GROUP='amlogic_dynamic_partitions';GROUP_SIZE=2080374784
sizes={n:(S/(n+'.img')).stat().st_size for n in PARTS};assert sum(sizes.values())<=GROUP_SIZE
def prop(name):
    p=subprocess.run(['debugfs','-R','cat /system/build.prop',str(S/'system.img')],capture_output=True,text=True,errors='replace').stdout
    return re.search('^'+re.escape(name)+'=(.*)$',p,re.M)[1]
def varint(v):
    o=bytearray()
    while True:
        b=v&127;v>>=7
        o.append(b|(128 if v else 0))
        if not v:return bytes(o)
def field(num,value):
    if isinstance(value,int):return varint(num<<3)+varint(value)
    if isinstance(value,str):value=value.encode()
    return varint(num<<3|2)+varint(len(value))+value
now=int(time.time());patch=prop('ro.build.version.security_patch');sdk=prop('ro.build.version.sdk');fp=prop('ro.build.fingerprint')
post=field(1,'sabrina')+field(2,fp)+field(4,now)+field(5,sdk)+field(6,patch)
pre=field(1,'sabrina')
# OtaMetadata: type=BLOCK(2), precondition=5, postcondition=6. See ota_metadata.proto.
metadata_pb=field(1,2)+field(5,pre)+field(6,post)
metadata='\n'.join(['ota-required-cache=0','ota-type=BLOCK','post-build='+fp,'post-sdk-level='+sdk,'post-security-patch-level='+patch,f'post-timestamp={now}','pre-device=sabrina'])+'\n'
op=['remove_all_groups',f'add_group {GROUP} {GROUP_SIZE}']
for n in PARTS:op+=[f'add {n} {GROUP}',f'resize {n} {sizes[n]}']
script=['assert(getprop("ro.product.device") == "sabrina" || abort("This package is for sabrina only."););',
 'assert(getprop("ro.boot.flash.locked") != "1" || abort("Refusing to install on a locked device."););',
 'ui_print("Updating LineageOS 23.2 for sabrina");',
 'assert(update_dynamic_partitions(package_extract_file("dynamic_partitions_op_list")));']
for n in PARTS:script+=[f'ui_print("Writing {n}");',f'package_extract_file("{n}.img", map_partition("{n}")) || abort("Failed to write {n}.");']
script+=['ui_print("Writing boot");','package_extract_file("boot.img", "/dev/block/by-name/boot") || abort("Failed to write boot.");',
 'ui_print("Writing vbmeta");','package_extract_file("vbmeta.img", "/dev/block/by-name/vbmeta") || abort("Failed to write vbmeta.");','ui_print("Done");']
text='\n'.join(script)+'\n'
for bad in ('bootloader','"env"','/env','logo','recovery'):assert bad not in text,bad
with tempfile.TemporaryDirectory(dir='/opt/sabrina/release-work') as d:
    raw=Path(d)/'unsigned.zip'
    with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        z.writestr('META-INF/com/android/metadata',metadata);z.writestr(zipfile.ZipInfo('META-INF/com/android/metadata.pb'),metadata_pb)
        z.writestr('META-INF/com/google/android/updater-script',text);z.write(BINARY,'META-INF/com/google/android/update-binary')
        z.writestr('dynamic_partitions_op_list','\n'.join(op)+'\n')
        for n in PARTS:z.write(S/(n+'.img'),n+'.img')
        z.write(S/'permissive/boot.img','boot.img');z.write(S/'permissive/vbmeta.img','vbmeta.img')
    java=sorted(glob.glob(str(T/'prebuilts/jdk/jdk[0-9]*/linux-x86/bin/java')),key=lambda p:int(re.search(r'jdk(\d+)',p)[1]))[-1]
    subprocess.run([java,'-Xmx4g',f'-Djava.library.path={H/"lib64"}','-jar',H/'framework/signapk.jar','-w',K/'releasekey.x509.pem',K/'releasekey.pk8',raw,OUT],check=True)
with zipfile.ZipFile(OUT) as z:
    names=z.namelist();assert z.testzip() is None
    for bad in ('bootloader','env','logo','recovery','dtb','dtbo'):assert not any(Path(n).stem==bad for n in names),bad
print(OUT,OUT.stat().st_size);print('\n'.join(names))
