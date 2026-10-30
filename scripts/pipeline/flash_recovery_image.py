"""Write one checked image to the recovery partition. Touches no other partition and never wipes."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,time
base=Path(__file__).resolve().parent
SERIAL=__import__('os').environ['SABRINA_SERIAL'];FB='/opt/sabrina/android16/out/host/linux-x86/bin/fastboot';SIZE=25165824
parser=argparse.ArgumentParser()
parser.add_argument('--image',required=True);parser.add_argument('--sha256',required=True)
parser.add_argument('--authorized',action='store_true');args=parser.parse_args()
assert args.authorized,'pass --authorized'
def run(cmd,timeout=30):
    r=subprocess.run([FB,'-s',SERIAL,*map(str,cmd)],text=True,capture_output=True,timeout=timeout)
    return r.returncode,r.stdout+r.stderr
def getvar(name):
    code,text=run(['getvar',name],15);assert code==0,text
    match=re.search(r'^'+re.escape(name)+r':\s*(.*?)\s*$',text,re.M);assert match,text
    return match[1]
image=Path(args.image);data=image.read_bytes()
assert hashlib.sha256(data).hexdigest()==args.sha256,'image checksum mismatch'
assert len(data)==SIZE and data[:8]==b'ANDROID!','not a recovery sized boot image'
assert getvar('unlocked')=='yes' and getvar('is-userspace')=='no' and getvar('product')=='sabrina','wrong device state'
assert int(getvar('partition-size:recovery'),16)==SIZE,'partition size changed'
code,text=run(['flash','recovery',image],120);print(text,flush=True)
assert code==0 and re.search(r"Writing 'recovery'.*?OKAY",text,re.S) and 'FAILED' not in text,'flash failed'
assert getvar('unlocked')=='yes','device no longer reports unlocked'
report=dict(image=image.name,sha256=args.sha256,flashed=['recovery'],unlocked_after='yes',finished_unix=time.time())
(base/'RECOVERY-FLASH.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
code,text=run(['reboot'],20);assert code==0,text;print('rebooted')
