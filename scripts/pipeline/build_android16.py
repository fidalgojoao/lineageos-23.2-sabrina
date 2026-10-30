"""Wait for the guarded source fetch, then attempt the experimental TV image.

Run inside Sabrina-Android16. Does not connect to or flash any device.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
STATUS = BASE / 'BUILD-STATUS.json'
MIN_FREE = 30 * 1024**3
MAX_SECONDS = 24 * 3600


def interrupted(signum, frame):
    raise KeyboardInterrupt(f'Interrupted by signal {signum}')


def main():
    signal.signal(signal.SIGTERM, interrupted)
    state = {'phase': 'waiting_for_source', 'started_unix': time.time(),
             'device_access': False, 'flash_enabled': False, 'pid': os.getpid(),
             'build_jobs': 4}
    process = None

    def write():
        state['updated_unix'] = time.time()
        state['host_free_gib'] = round(shutil.disk_usage('/mnt/d').free / 1024**3, 1)
        STATUS.write_text(json.dumps(state, indent=2) + '\n')

    def run(command, log_name):
        nonlocal process
        with (BASE / log_name).open('w', buffering=1) as log:
            process = subprocess.Popen(command, cwd=SOURCE, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            while process.poll() is None:
                write()
                if shutil.disk_usage('/mnt/d').free < MIN_FREE:
                    raise RuntimeError('Stopped: less than 30 GiB remains on D:')
                if time.time() - state['started_unix'] > MAX_SECONDS:
                    raise RuntimeError('Stopped after 24-hour execution limit')
                time.sleep(10)
            code = process.wait()
            process = None
            if code:
                raise RuntimeError(f'{log_name}: command exited {code}')

    try:
        write()
        while True:
            try:
                source_state = json.loads((BASE / 'SOURCE-STATUS.json').read_text())
            except json.JSONDecodeError:
                # The sync process may be replacing its status during this read.
                time.sleep(1)
                continue
            if source_state['phase'] == 'synced':
                break
            if source_state['phase'] in ('failed', 'interrupted'):
                raise RuntimeError('Source download did not finish; see SOURCE-STATUS.json')
            if time.time() - state['started_unix'] > MAX_SECONDS:
                raise RuntimeError('Source download wait exceeded 24 hours')
            time.sleep(20)
            write()
        state['phase'] = 'preparing_build'
        write()
        subprocess.run(['python3', str(BASE / 'apply_build_fixes.py')], check=True)
        subprocess.run(['python3', str(BASE / 'apply_ota_guard.py')], check=True)
        subprocess.run(['python3', str(BASE / 'apply_privacy_policy.py')], check=True)
        subprocess.run(['python3', str(BASE / 'apply_policy_restrictions.py')], check=True)
        subprocess.run(['python3', str(BASE / 'materialize_device.py')], check=True)
        revision = subprocess.check_output(['git', '-C', 'vendor/gapps_tv', 'rev-parse', 'HEAD'],
                                           cwd=SOURCE, text=True).strip()
        if revision != '378d98196fe90f7ba5da6ef925ebc23d5434e030':
            raise RuntimeError('Unexpected TV Google-app source revision')
        # A separate swap file avoids changing the user's global WSL configuration.
        # Leave it available for incremental builds; record whether activation works.
        swap = SOURCE.parent / 'build.swap'
        if not swap.exists():
            if shutil.disk_usage('/mnt/d').free < 70 * 1024**3:
                raise RuntimeError('Not enough disk for build swap plus reserve')
            subprocess.run(['fallocate', '-l', '24G', str(swap)], check=True)
            swap.chmod(0o600)
            subprocess.run(['mkswap', str(swap)], check=True, stdout=subprocess.DEVNULL)
        active_swaps = Path('/proc/swaps').read_text()
        if str(swap) not in active_swaps:
            result = subprocess.run(['swapon', str(swap)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError('Build swap could not activate: ' + result.stderr.strip())
        state['phase'] = 'compiling'
        write()
        # No brunch/OTA target: only the system image and host checking/packing tools.
        run(['bash', '-lc', 'set -e; source build/envsetup.sh; '
             'source vendor/lineage/vars/aosp_target_release; '
             'lunch lineage_gsi_sabrina16 "$aosp_target_release" userdebug; '
             'm -j4 systemimage checkvintf lpmake lpdump secilc'], 'build-systemimage.log')
        state['compilation_complete'] = True
        state['build_percentage'] = 100
        image = SOURCE / 'out/target/product/generic/system.img'
        state['image'] = str(image)
        state['system_image_bytes'] = image.stat().st_size
        with image.open('rb') as stream:
            state['system_image_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        state['phase'] = 'checking_static_compatibility'
        write()
        # Independent gates must all run: a VINTF failure must not conceal a
        # policy failure or leave a stale privacy result from an earlier image.
        failures = []
        state['static_checks'] = {}
        for interpreter, script, log_name in [
                ('python3', 'check_ota_protection.py', 'candidate-ota-protection.log'),
                ('python3', 'check_privacy_policy.py', 'candidate-privacy-policy.log'),
                ('bash', 'check_candidate.sh', 'candidate-vintf.log'),
                ('python3', 'check_candidate_policy.py', 'candidate-selinux.log')]:
            try:
                run([interpreter, str(BASE / script)], log_name)
            except RuntimeError as error:
                # Resource/time limits still stop immediately.
                if ': command exited ' not in str(error):
                    raise
                failures.append(str(error))
                state['static_checks'][script] = 'failed'
            else:
                state['static_checks'][script] = 'passed'
            write()
        candidate_system = SOURCE / 'out/target/product/generic/system'
        build_properties = (candidate_system / 'build.prop').read_text()
        if 'ro.system.build.version.sdk=36\n' not in build_properties:
            raise RuntimeError('Candidate system is not Android 16/API 36')
        image = SOURCE / 'out/target/product/generic/system.img'
        # Verified OTA dynamic group: 2,080,374,784 bytes. Retain vendor, odm and
        # system_dlkm and reserve at least 4 MiB for an unused product placeholder.
        budget = 2080374784 - 132784128 - 3641344 - 348160 - 4194304
        state['system_image_bytes'] = image.stat().st_size
        state['repacked_system_budget_bytes'] = budget
        if image.stat().st_size > budget:
            raise RuntimeError('Compiled image exceeds the physical dynamic-partition budget')
        state['android_sdk'] = 36
        state['dynamic_group_size_budget_check'] = 'passed_not_an_installation_layout_check'
        with image.open('rb') as stream:
            state['system_image_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if failures:
            state['validation_state'] = 'failed_not_ready_to_flash'
            raise RuntimeError('; '.join(failures))
        state['phase'] = 'compiled_static_checks_passed_hardware_untested'
        state['image'] = str(image)
    except BaseException as error:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        state['phase'] = 'stopped' if isinstance(error, KeyboardInterrupt) else 'failed'
        state['error'] = str(error)
    write()
    print(json.dumps(state, indent=2), flush=True)


if __name__ == '__main__':
    main()
