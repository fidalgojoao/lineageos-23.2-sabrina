from pathlib import Path
import subprocess
base = Path(__file__).resolve().parent
with (base / 'kernel-feature-driver.log').open('a') as output:
    job = subprocess.Popen(['python3', str(base / 'run_kernel_feature.py')],
                           stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(f'Kernel feature worker PID {job.pid}')
