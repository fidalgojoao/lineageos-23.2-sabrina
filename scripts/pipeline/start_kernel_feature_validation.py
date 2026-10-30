from pathlib import Path
import subprocess
base = Path(__file__).resolve().parent
with (base / 'kernel-feature-validation-driver.log').open('a') as output:
    job = subprocess.Popen(['python3', str(base / 'follow_kernel_feature_validation.py')],
                           stdin=subprocess.DEVNULL, stdout=output,
                           stderr=subprocess.STDOUT, start_new_session=True)
print(f'Post-build offline validation worker PID {job.pid}')
