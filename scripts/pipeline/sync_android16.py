"""Fetch the Android 16 source tree with a real-host disk-space limit.

Run in Sabrina-Android16. No device access, build or flashing is performed.
"""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time

BASE = Path(__file__).resolve().parent
SOURCE = Path('/opt/sabrina/android16')
MIN_FREE = 40 * 1024**3


def stop(process):
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def main():
    status_path = BASE / 'SOURCE-STATUS.json'
    started = time.time()
    status = {'phase': 'syncing', 'source': str(SOURCE),
              'started_unix': started, 'device_access': False}

    def write():
        status['updated_unix'] = time.time()
        status['host_free_gib'] = round(shutil.disk_usage('/mnt/d').free / 1024**3, 1)
        status_path.write_text(json.dumps(status, indent=2) + '\n')

    write()
    with (BASE / 'source-sync-full.log').open('a', buffering=1) as log:
        process = subprocess.Popen(
            ['repo', 'sync', '-c', '-j4', '--no-clone-bundle', '--optimized-fetch',
             '--retry-fetches=2', '--fail-fast'],
            cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                write()
                if shutil.disk_usage('/mnt/d').free < MIN_FREE:
                    status['error'] = 'Stopped before host free space dropped below 40 GiB'
                    stop(process)
                    break
                time.sleep(10)
        except BaseException:
            if process.poll() is None:
                stop(process)
            status['phase'] = 'interrupted'
            write()
            raise
        status['exit_code'] = process.wait()
    status['phase'] = 'synced' if status['exit_code'] == 0 else 'failed'
    if status['phase'] == 'synced':
        with (BASE / 'platform-manifest-pinned.xml').open('w') as manifest:
            subprocess.run(['repo', 'manifest', '-r'], cwd=SOURCE, stdout=manifest, check=True)
    write()
    print(json.dumps(status, indent=2), flush=True)


if __name__ == '__main__':
    main()
