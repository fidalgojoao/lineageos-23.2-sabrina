"""Fetch pinned kernel repair sources into a separate workspace. Never flashes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
ROOT = Path('/opt/sabrina/kernel-repair')
STATUS = BASE / 'KERNEL-REPAIR-STATUS.json'
state = {'phase': 'preparing', 'pid': os.getpid(), 'started_unix': time.time(),
         'device_access': False, 'flash_enabled': False, 'kernel_build_started': False}

def save():
    state['updated_unix'] = time.time()
    STATUS.write_text(json.dumps(state, indent=2) + '\n')

def run(command, cwd=None):
    if shutil.disk_usage('/mnt/d').free < 40 * 1024**3:
        raise RuntimeError('Less than 40 GiB remains on D:')
    print('Executing:', ' '.join(map(str, command)), flush=True)
    subprocess.run(command, cwd=cwd, check=True, timeout=1800,
                   env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})

try:
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, remote, revision in [
        ('common', 'https://android.googlesource.com/kernel/common',
         'c0bad795ed1a0c02f9af7d8622ebe0cf9b446c9c'),
        ('common_drivers', 'https://nest-open-source.googlesource.com/manifest_repos/amlogic-driver',
         '997cd70d4a7705a53d751b3703cf0e9a600e42bc'),
    ]:
        target = ROOT / name
        state.update(phase='fetching_source', project=name, revision=revision)
        save()
        if not (target / '.git').exists():
            run(['git', 'init', str(target)])
            run(['git', 'remote', 'add', 'origin', remote], cwd=target)
        actual = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=target,
                                capture_output=True, text=True)
        if actual.returncode or actual.stdout.strip() != revision:
            # Do not reset an existing checkout or discard any local work.
            if actual.returncode == 0:
                raise RuntimeError(f'Unexpected existing HEAD in {target}; review before changing it')
            run(['git', '-c', 'http.lowSpeedLimit=1024', '-c', 'http.lowSpeedTime=120',
                 'fetch', '--depth=1', 'origin', revision], cwd=target)
            run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=target)
        actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=target, text=True).strip()
        if actual != revision:
            raise RuntimeError('Pinned source verification failed')
    state.update(phase='sources_fetched_not_built',
                 remaining=['Match stock build configuration and patch selection',
                            'Acquire the matching clang-r487747c toolchain',
                            'Reproduce baseline kernel and module symbol CRCs',
                            'Investigate and build the required kernel feature',
                            'Validate kernel size, DTB and driver ABI; no automatic installation'])
except BaseException as error:
    state.update(phase='failed', error=str(error))
finally:
    save()
    print(json.dumps(state, indent=2), flush=True)
