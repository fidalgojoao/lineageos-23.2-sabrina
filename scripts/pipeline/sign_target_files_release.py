"""Create private release keys once, then sign the target-files package. No device operations."""
import glob,os,re,shutil,stat,subprocess,sys,time,zipfile
from pathlib import Path
K=Path('/opt/sabrina/release-keys');W=Path('/opt/sabrina/release-work');T=Path('/opt/sabrina/android16');H=T/'out/host/linux-x86'
BACKUP=Path(os.environ['SABRINA_KEY_BACKUP'])
SUBJECT='/C=XX/ST=Unknown/L=Unknown/O=LineageOS sabrina/OU=Personal/CN=LineageOS sabrina release'
def run(*a,**k):return subprocess.run([str(x) for x in a],check=True,capture_output=True,text=True,errors='replace',**k).stdout
def apk_key(base,bits=4096):
    pem=K/(base+'.private.pem');pk8=K/(base+'.pk8');x=K/(base+'.x509.pem')
    if pk8.exists():return
    run('openssl','genrsa','-out',pem,bits);run('openssl','req','-new','-x509','-sha256','-key',pem,'-out',x,'-days','10950','-subj',SUBJECT)
    run('openssl','pkcs8','-topk8','-inform','PEM','-outform','DER','-in',pem,'-out',pk8,'-nocrypt');pem.unlink()
K.mkdir(mode=0o700,exist_ok=True);W.mkdir(exist_ok=True)
Z=glob.glob(str(T/'out/target/product/generic/obj/PACKAGING/target_files_intermediates/*-target_files*.zip'));assert len(Z)==1,Z
z=zipfile.ZipFile(Z[0]);apex=[re.search(r'name="([^"]+)"',l)[1] for l in z.read('META/apexkeys.txt').decode().splitlines() if l.strip()]
for n in ('releasekey','platform','shared','media','networkstack','sdk_sandbox','bluetooth','nfc'):apk_key(n)
if not (K/'avb.pem').exists():run('openssl','genrsa','-out',K/'avb.pem',2048)
run(H/'bin/avbtool','extract_public_key','--key',K/'avb.pem','--output',K/'avb.avbpubkey')
args=[]
for a in apex:
    b='apex-'+a.removesuffix('.apex');apk_key(b)
    pay=K/(b+'.payload.pem')
    if not pay.exists():run('openssl','genrsa','-out',pay,4096)
    args+=['--extra_apks',f'{a}={K/b}','--extra_apex_payload_key',f'{a}={pay}']
for p in K.iterdir():p.chmod(0o600)
BACKUP.mkdir(exist_ok=True);n=0
for p in K.iterdir():
    shutil.copyfile(p,BACKUP/p.name);n+=1
    assert (BACKUP/p.name).read_bytes()==p.read_bytes(),p.name
print('keys',n,'backup verified')
out=W/'signed-target-files.zip';out.unlink(missing_ok=True)
env={**os.environ,'PATH':f"{H/'bin'}:{T/'prebuilts/jdk/jdk21/linux-x86/bin'}:"+os.environ['PATH'],'ANDROID_BUILD_TOP':str(T)}
java=sorted(glob.glob(str(T/'prebuilts/jdk/jdk[0-9]*/linux-x86/bin')),key=lambda p:int(re.search(r'jdk(\d+)',p)[1]));env['PATH']=f"{H/'bin'}:{java[-1]}:"+os.environ['PATH']
start=time.time();log=W/'sign.log'
with log.open('w') as s:
    r=subprocess.run([str(H/'bin/sign_target_files_apks'),'-o','-d',str(K),*args,Z[0],str(out)],cwd=T,stdout=s,stderr=subprocess.STDOUT,env=env)
t=log.read_text(errors='replace').splitlines()
print('exit',r.returncode,'minutes',round((time.time()-start)/60,1),'size',out.stat().st_size if out.exists() else None)
print('\n'.join(l[:190] for l in t if re.search(r'ERROR|Error|Traceback|error:|Warning: .*not.*sign|Cannot',l))[:1500]);print('\n'.join(l[:190] for l in t[-6:]))
assert r.returncode==0
print(run('unzip','-p',out,'SYSTEM/build.prop').count('release-keys'),'release-keys in build.prop')
