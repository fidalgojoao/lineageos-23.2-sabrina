"""Watchdog trial steps. Writes only super/boot/vbmeta and wipes only with fastboot -w."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,time
base=Path(__file__).resolve().parent
SERIAL='YOUR_DEVICE_SERIAL';FB='/opt/sabrina/android16/out/host/linux-x86/bin/fastboot'
SIZES=dict(super=2084569088,boot=16777216,vbmeta=2097152,recovery=25165824)
STOCK=base.parent/'stock-recovery-bundle-UTTC.250917.004/stock-images'
parser=argparse.ArgumentParser()
parser.add_argument('step',choices=['preflight','install','update','restore','reboot'])
parser.add_argument('--mode',choices=['permissive','enforcing'],default='permissive')
parser.add_argument('--authorized',action='store_true');args=parser.parse_args()
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(cmd,timeout=30):
    r=subprocess.run([FB,'-s',SERIAL,*map(str,cmd)],text=True,capture_output=True,timeout=timeout)
    return r.returncode,r.stdout+r.stderr
def getvar(name):
    code,text=run(['getvar',name],15);assert code==0,text
    match=re.search(r'^'+re.escape(name)+r':\s*(.*?)\s*$',text,re.M);assert match,text
    return match[1]
def require_unlocked():
    value=getvar('unlocked');assert value=='yes','ABORT: unlocked='+value;return value
def preflight():
    report=dict(serial=SERIAL,unlocked=require_unlocked(),is_userspace=getvar('is-userspace'),product=getvar('product'),
        version_bootloader=getvar('version-bootloader'),max_download=int(getvar('max-download-size'),16))
    assert report['is_userspace']=='no','Not the real bootloader' and report['product']
    assert report['max_download']>=96*1024**2
    for name,size in SIZES.items():
        actual=int(getvar('partition-size:'+name),16);assert actual==size,(name,actual);report[name+'_bytes']=actual
    return report
def flash(steps):
    done=[]
    for partition,path,sha in steps:
        assert digest(path)==sha,path
    for partition,path,_ in steps:
        code,text=run(['-S','96M','flash',partition,path],900)
        print(text,flush=True)
        assert code==0 and re.search(r"Writing '"+partition+r"'.*?OKAY",text,re.S) and 'FAILED' not in text,partition
        done.append(partition)
    return done
def wipe():
    code,text=run(['-w'],300);print(text,flush=True)
    assert code==0 and 'FAILED' not in text
    for name in ['userdata','cache','metadata']:assert re.search(r"Erasing '"+name+r"'.*?OKAY",text,re.S),name
report=dict(step=args.step,mode=args.mode,started_unix=time.time(),preflight=preflight())
if args.step in('install','update','restore','reboot'):assert args.authorized
if args.step in('install','update'):
    images=json.loads((base/'WATCHDOG-IMAGE-SET.json').read_text());chosen=images['boot_variants'][args.mode]
    sparse=json.loads((base/'WATCHDOG-SPARSE.json').read_text())['artifacts']['custom']
    report['flashed']=flash([('super',sparse['path'],sparse['sha256']),('boot',chosen['boot']['path'],chosen['boot']['sha256']),
        ('vbmeta',chosen['vbmeta']['path'],chosen['vbmeta']['sha256'])])
    require_unlocked()
    if args.step=='install':wipe()
if args.step=='restore':
    report['flashed']=flash([('super','/opt/sabrina/sparse-transfer/stock-super-UNTESTED.sparse.img','3471663cb5f40729e587a1576ce25bc96bb2ca82b7feeaa15795564f882a2e2d'),
        ('boot',STOCK/'boot.img','c4cb0f2e405227e058d367b4ced20fa49fdc0cc89686c0c8dff5b6e3fa115934'),
        ('vbmeta',STOCK/'vbmeta.img','b385fad321cd8ce9d895558886c1b74833e8b3a45ddc6d898299890af0307e01')])
    require_unlocked();wipe()
report['unlocked_after']=require_unlocked()
if args.step=='reboot':
    code,text=run(['reboot'],20);assert code==0,text;report['rebooted']=True
report['finished_unix']=time.time()
(base/('WATCHDOG-TRIAL-'+args.step.upper()+'-'+args.mode.upper()+'.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
