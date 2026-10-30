from pathlib import Path
import subprocess
import sys
base = Path(__file__).resolve().parent
with (base / 'kernel-baseline-build-driver.log').open('a') as output:
    job = subprocess.Popen(['python3', str(base / 'run_kernel_baseline.py')] + sys.argv[1:],
                           stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(f'Baseline configuration/build worker PID {job.pid}')
