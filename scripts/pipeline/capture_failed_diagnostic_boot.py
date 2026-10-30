"""After complete stock restore, RAM-boot original kernel and collect prior logs."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,zipfile,re
base=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--status-name',default='FAILED-DIAGNOSTIC-CAPTURE.json')
parser.add_argument('--work-prefix',default='failed-diagnostic-capture')
parser.add_argument('--purpose',default='Capture preceding approved Android16 diagnostic failure')
parser.add_argument('--restore-status',default='BOOTLOOP-DIAGNOSTIC-RESTORE-EXECUTION.json')
args=parser.parse_args()
assert '/' not in args.status_name and '\\' not in args.status_name
assert args.work_prefix.replace('-','').isalnum()
assert '/' not in args.restore_status and '\\' not in args.restore_status
serial='YOUR_DEVICE_SERIAL'
fb='/opt/sabrina/android16/out/host/linux-x86/bin/fastboot'
adb='/path/to/host-tools'
restored=json.loads((base/args.restore_status).read_text())
assert restored['phase']=='all_three_partitions_written_unlocked_verified_no_reboot'
assert restored['completed_partitions']==['super','boot','vbmeta'] and restored['unlocked_verified']
capture_build=base/'WATCHDOG-INIT-BUILD.json'
if args.work_prefix=='watchdog-capture':
    entry=json.loads(capture_build.read_text())['capture_image']
    image=Path(entry['path']);assert hashlib.sha256(image.read_bytes()).hexdigest()==entry['sha256']
else:
    image=base.parent/'stock-boot/boot-debug-temporary.img'
    assert hashlib.sha256(image.read_bytes()).hexdigest()=='6399b1dc4186e88a896b5f0f9988a4ab15a537f7e7e8ea3b4b9d15a0ace535e0'
work=base/(args.work_prefix+'-'+str(int(time.time())));work.mkdir()
status=base/args.status_name
state=dict(started_unix=time.time(),phase='ram_booting_original_stock_kernel',work=str(work),
    purpose=args.purpose,
    firmware_flashed_by_capture=False,power_removed=False,additional_wipe=False,
    restore_execution=str(base/args.restore_status))
def save():
    state['updated_unix']=time.time();status.write_text(json.dumps(state,indent=2)+'\n')
def run(cmd,timeout=20):return subprocess.run(cmd,text=True,capture_output=True,timeout=timeout)
def shell(*args):return run([adb,'-s',serial,'shell',*args])
save()
r=run([fb,'-s',serial,'boot',str(image)],30)
state['ram_boot']=dict(exit_code=r.returncode,output=r.stdout+r.stderr);save()
assert r.returncode==0 and 'OKAY' in r.stdout+r.stderr
deadline=time.time()+180
while time.time()<deadline:
    r=run([adb,'devices'])
    if serial+'\tdevice' in r.stdout:
        kernel=shell('uname','-r').stdout.strip()
        if kernel:
            assert kernel=='5.15.170-android14-11-gf4a1f03072af',kernel
            state['kernel']=kernel
            break
    time.sleep(3)
else:raise RuntimeError('Original stock diagnostic ADB absent; inspect without reboot')
state['selinux']=shell('getenforce').stdout.strip()
assert state['selinux']=='Enforcing'
state['phase']='collecting_retained_logs';save()
r=shell('logcat','-L','-d','-b','all')
(work/'retained-logcat.txt').write_text(r.stdout+r.stderr)
while time.time()<deadline:
    wifi=shell('svc','wifi','disable')
    if wifi.returncode==0 and 'Can\'t find service' not in wifi.stdout+wifi.stderr:
        break
    time.sleep(3)
shell('settings','put','global','ota_disable_automatic_update','1')
windows_work=subprocess.check_output(['wslpath','-w',str(work)],text=True).strip()
r=run([adb,'-s',serial,'bugreport',windows_work],360)
(work/'bugreport-command.log').write_text(r.stdout+r.stderr)
assert r.returncode==0,r.stderr
archive=next(work.glob('*.zip'))
state['bugreport']=dict(path=str(archive),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
with zipfile.ZipFile(archive) as z:
    text=z.read(next(n for n in z.namelist() if n.startswith('bugreport-') and n.endswith('.txt'))).decode(errors='replace')
    for title,name in [('LAST KMSG','last-kmsg.txt'),('LAST LOGCAT','last-logcat.txt')]:
        match=re.search(r'^------ '+title+r'[^\n]*\n(.*?)(?=^------ )',text,re.M|re.S)
        if match:(work/name).write_text(match.group(1))
    kmsg=(work/'last-kmsg.txt').read_text() if (work/'last-kmsg.txt').exists() else ''
    state['diagnostic_markers']=[l for l in kmsg.splitlines() if 'sabrina_bootdiag' in l]
    state['selected_failure_lines']=[l for l in kmsg.splitlines() if re.search(r'panic|[Ff]atal|[Ff]ailed|[Aa]v[bB]|[Ss]elinux|[Ss]ignature|[Vv]erif|[Mm]ount|[Uu]nknown|[Ee]rror',l)][:100]
    state['last_kmsg_bytes']=len(kmsg.encode())
    retained=(work/'last-logcat.txt').read_text() if (work/'last-logcat.txt').exists() else ''
    messages=[l for l in retained.splitlines() if 'APEX_BOOTSTRAP_DIAG' in l]
    (work/'apex-bootstrap-messages.txt').write_text('\n'.join(messages)+'\n')
    state['apex_bootstrap_message_count']=len(messages)
    state['apex_bootstrap_errors']=[l for l in messages if re.search(r'\b[EF]\s+APEX_BOOTSTRAP_DIAG',l)][:100]
state.update(phase='retained_failure_logs_collected_requires_analysis',boot_completed=shell('getprop','sys.boot_completed').stdout.strip(),
    wifi_on=shell('settings','get','global','wifi_on').stdout.strip(),finished_unix=time.time())
shell('svc','wifi','disable')
state['wifi_on_after_disable']=shell('settings','get','global','wifi_on').stdout.strip()
save();print(json.dumps(state,indent=2))
