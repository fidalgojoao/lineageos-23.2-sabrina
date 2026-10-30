from pathlib import Path
import subprocess
base = Path(__file__).resolve().parent
with (base / 'kernel-baseline-preparation.log').open('a') as output:
    job = subprocess.Popen(['python3', str(base / 'prepare_kernel_baseline.py')],
                           stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(f'Kernel baseline preparation PID {job.pid}')
