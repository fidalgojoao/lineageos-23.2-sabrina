"""Guarded matching user/release rebuild; never connects to the Chromecast."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

BASE = Path(__file__).resolve().parent
ROOT = Path('/opt/sabrina/android16')
STATUS = BASE/'RELEASE-BUILD-STATUS.json'
MIN_FREE = 35*1024**3
MAX_SECONDS = 24*3600

def main():
    state = {'phase':'preparing','pid':os.getpid(),'started_unix':time.time(),
             'variant':'user','jobs':4,'device_modified':False,'ready_to_flash':False,
             'compilation_complete':False,'final_policy_integration_required':True}
    child = None
    def save():
        state['updated_unix'] = time.time()
        state['host_free_gib'] = round(shutil.disk_usage('/mnt/d').free/1024**3,1)
        STATUS.write_text(json.dumps(state,indent=2)+'\n')
    def stop(signum,frame):
        raise KeyboardInterrupt(f'Interrupted by signal {signum}')
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        # Do not accidentally start a second worker.
        if STATUS.exists():
            old = json.loads(STATUS.read_text())
            if old.get('phase') in ['preparing','compiling'] and old.get('pid') != os.getpid():
                try:
                    os.kill(old['pid'],0)
                except ProcessLookupError:
                    pass
                else:
                    raise RuntimeError('A release worker already exists; inspect it before restarting')
        review = json.loads((BASE/'migrated-policy-validation.json').read_text())
        assert review['all_passed'],'Policy structural validation must pass before this rebuild'
        migration = json.loads((BASE/'vendor-api-migration-experiment.json').read_text())
        assert migration['strict_migrated_api_merge_passed'] and migration['compiler_assertions_enabled']
        assert migration['original_vendor_private_assertions_preserved']
        assert shutil.disk_usage('/mnt/d').free > MIN_FREE+5*1024**3
        save()
        old_image = ROOT/'out/target/product/generic/system.img'
        preserved = ROOT/'out/sabrina-preserved/system-userdebug-20261028'
        preserved.mkdir(parents=True,exist_ok=True)
        destination = preserved/'system.img'
        old_state = json.loads((BASE/'BUILD-STATUS.json').read_text())
        expected = old_state['system_image_sha256']
        if not destination.exists():
            assert hashlib.file_digest(old_image.open('rb'),'sha256').hexdigest() == expected
            shutil.copyfile(old_image,destination)
        assert hashlib.file_digest(destination.open('rb'),'sha256').hexdigest() == expected
        state['preserved_previous_image'] = {'path':str(destination),'bytes':destination.stat().st_size,'sha256':expected}
        for name in ['BUILD-STATUS.json','PORT-READINESS.json','vendor-api-migration-experiment.json','migrated-policy-validation.json']:
            output = preserved/name
            if not output.exists():
                shutil.copyfile(BASE/name,output)
        with (BASE/'release-build-preparation.log').open('w') as log:
            for name in ['apply_build_fixes.py','apply_ota_guard.py','apply_privacy_policy.py',
                         'apply_policy_restrictions.py','materialize_device.py']:
                subprocess.run(['python3',str(BASE/name)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        swap = ROOT.parent/'build.swap'
        assert swap.exists(),'Preserved build swap is missing'
        if str(swap) not in Path('/proc/swaps').read_text():
            subprocess.run(['swapon',str(swap)],check=True)
        command = ['bash','-lc','set -e; source build/envsetup.sh; '
                   'source vendor/lineage/vars/aosp_target_release; '
                   'lunch lineage_gsi_sabrina16 "$aosp_target_release" user; '
                   'm -j4 systemimage checkvintf lpmake lpdump secilc sepolicy-analyze '
                   'libsepolwrap sepolicy_tests treble_sepolicy_tests general_sepolicy.conf']
        state.update(phase='compiling',command=command,log=str(BASE/'build-systemimage-user.log'))
        save()
        with (BASE/'build-systemimage-user.log').open('w',buffering=1) as log:
            child = subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            state['compiler_wrapper_pid'] = child.pid
            while child.poll() is None:
                save()
                if shutil.disk_usage('/mnt/d').free < MIN_FREE:
                    raise RuntimeError('Stopped below 35 GiB host disk reserve')
                if time.time()-state['started_unix'] > MAX_SECONDS:
                    raise RuntimeError('Stopped after 24-hour runtime limit')
                time.sleep(10)
            state['exit_code'] = child.wait()
            child = None
        if state['exit_code']:
            raise RuntimeError('Release compilation failed; inspect build-systemimage-user.log')
        props = (ROOT/'out/target/product/generic/system/build.prop').read_text()
        assert 'ro.system.build.version.sdk=36\n' in props
        assert 'ro.system.build.type=user\n' in props
        image = ROOT/'out/target/product/generic/system.img'
        state.update(phase='release_compiled_requires_policy_integration_and_final_checks',
                     compilation_complete=True,compilation_percentage=100,
                     image=str(image),image_bytes=image.stat().st_size,
                     image_sha256=hashlib.file_digest(image.open('rb'),'sha256').hexdigest())
    except BaseException as error:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()
        state.update(phase='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=str(error))
    state['finished_unix'] = time.time()
    save()
    print(json.dumps(state,indent=2),flush=True)

if __name__ == '__main__':
    main()
