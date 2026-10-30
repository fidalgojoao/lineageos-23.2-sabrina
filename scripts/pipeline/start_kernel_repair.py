"""Launch the isolated source preparation job with persistent evidence."""
from pathlib import Path
import subprocess
base = Path(__file__).resolve().parent
with (base / 'kernel-repair-source.log').open('a') as output:
    job = subprocess.Popen(['python3', str(base / 'prepare_kernel_repair.py')],
                           stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(f'Kernel source preparation PID {job.pid}')
