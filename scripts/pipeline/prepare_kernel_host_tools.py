"""Acquire Google's matching pahole and verify actual host linker probes."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

BASE = Path(__file__).resolve().parent
ROOT = Path('/opt/sabrina/kernel-repair')
TOOLS = ROOT / 'host-tools'
TOOLS.mkdir(exist_ok=True)
repo = 'https://android.googlesource.com/kernel/prebuilts/build-tools'
with urllib.request.urlopen(repo + '/+/refs/heads/main-kernel-build-2023?format=JSON', timeout=25) as response:
    commit = json.loads(response.read().decode().split('\n', 1)[1])['commit']
with urllib.request.urlopen(repo + '/+/' + commit + '/linux-x86/bin/pahole?format=TEXT', timeout=25) as response:
    data = base64.b64decode(response.read(16 * 1024 * 1024), validate=True)
pahole = TOOLS / 'pahole'
pahole.write_bytes(data)
pahole.chmod(0o755)
runtime_dir = TOOLS / 'lib64'
runtime_dir.mkdir(exist_ok=True)
runtime_path = 'linux-x86/lib64/libc++.so'
for attempt in range(3):
    with urllib.request.urlopen(repo + '/+/' + commit + '/' + runtime_path + '?format=TEXT', timeout=25) as response:
        runtime = base64.b64decode(response.read(32 * 1024 * 1024), validate=True)
    if runtime.startswith(b'\x7fELF'):
        break
    target = runtime.decode().strip()
    if '/' in target or not target.startswith('libc++.so.'):
        raise RuntimeError('Unexpected published runtime symlink')
    runtime_path = 'linux-x86/lib64/' + target
else:
    raise RuntimeError('Unresolved compiler runtime')
(runtime_dir / 'libc++.so').write_bytes(runtime)
env = dict(os.environ)
env['LD_LIBRARY_PATH'] = str(runtime_dir)
version = subprocess.check_output([str(pahole), '--version'], text=True, env=env).strip()
print('Published pahole:', version, flush=True)
env['PATH'] = str(ROOT / 'clang-r487747c/bin') + os.pathsep + env['PATH']
results = {}
for static in [False, True]:
    command = [str(ROOT / 'common-patched/scripts/cc-can-link.sh'),
               str(ROOT / 'clang-r487747c/bin/clang'), '--target=aarch64-linux-gnu', '-fuse-ld=lld']
    if static:
        command.append('-static')
    result = subprocess.run(command, env=env)
    results['static' if static else 'dynamic'] = result.returncode == 0
report = {'pahole_version': version, 'pahole_source_commit': commit,
          'pahole_sha256': hashlib.sha256(data).hexdigest(), 'compiler_link_probes': results,
          'ready_to_flash': False}
(BASE / 'kernel-host-tools-report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
if version != 'v1.23' or not all(results.values()):
    raise RuntimeError('Host probes/version still differ from stock; investigate without overriding the checks')
