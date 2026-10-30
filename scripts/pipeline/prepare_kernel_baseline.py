"""Prepare source-patched baseline and its matching compiler, without flashing."""
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import urllib.request

BASE = Path(__file__).resolve().parent
ROOT = Path('/opt/sabrina/kernel-repair')
STATUS = BASE / 'KERNEL-REPAIR-STATUS.json'
state = {'phase': 'preparing_baseline', 'pid': os.getpid(), 'started_unix': time.time(),
         'device_access': False, 'flash_enabled': False, 'kernel_build_started': False}

def save():
    state['updated_unix'] = time.time()
    STATUS.write_text(json.dumps(state, indent=2) + '\n')

def run(command, cwd=None):
    if shutil.disk_usage('/mnt/d').free < 40 * 1024**3:
        raise RuntimeError('Less than 40 GiB remains on D:')
    print('Executing:', ' '.join(map(str, command)), flush=True)
    subprocess.run(command, cwd=cwd, check=True, timeout=120,
                   env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})

try:
    patch_root = ROOT / 'common_drivers/auto_patch/common14-5.15'
    for original, target, commit, patch_directory in [
        ('common', 'common-patched', 'c0bad795ed1a0c02f9af7d8622ebe0cf9b446c9c', patch_root / 'common'),
        ('common_drivers', 'drivers-patched', '997cd70d4a7705a53d751b3703cf0e9a600e42bc', patch_root / 'common_drivers'),
    ]:
        source = ROOT / target
        if not source.exists():
            run(['git', 'worktree', 'add', '--detach', str(source), commit], cwd=ROOT / original)
        else:
            run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=source)
            dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True)
            if dirty.strip():
                raise RuntimeError(f'Unexpected edits in {source}; preserve them and inspect before resuming')
        applied_history = subprocess.check_output(['git', 'log', '--format=%B'], cwd=source, text=True)
        patches = sorted(patch_directory.rglob('*.patch'))
        for index, patch in enumerate(patches):
            state.update(phase='applying_official_patches', project=target,
                         patches_completed=index, patches_total=len(patches), patch=str(patch))
            save()
            change_id = re.search(r'^Change-Id: (\S+)', patch.read_text(), re.M)
            if change_id and change_id.group(1) in applied_history:
                continue
            reversed_patch = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)],
                                            cwd=source, capture_output=True)
            if reversed_patch.returncode == 0:
                # Exact reverse applicability proves the entire fix is present;
                # never remove a security fix merely to apply a duplicate.
                state.setdefault('already_present_patches', []).append({
                    'patch': str(patch), 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
                    'proof': 'git apply --reverse --check succeeded'})
                pending = subprocess.run(['git', 'am', '--show-current-patch=raw'],
                                         cwd=source, capture_output=True)
                if pending.returncode == 0:
                    # Only resume the known exact failed patch, not an unrelated am.
                    if not change_id or change_id.group(1).encode() not in pending.stdout:
                        raise RuntimeError('Unexpected pending patch state')
                    run(['git', 'am', '--skip'], cwd=source)
                save()
                continue
            run(['git', '-c', 'user.name=Sabrina kernel port',
                 '-c', 'user.email=sabrina-port@localhost', 'am', str(patch)], cwd=source)
        state['patched_' + original + '_commit'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    compiler = ROOT / 'clang-r487747c'
    state['phase'] = 'fetching_matching_compiler'
    save()
    repo = 'https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86'
    with urllib.request.urlopen(repo + '/+/refs/heads/android14-release?format=JSON', timeout=25) as response:
        ref = json.loads(response.read().decode().split('\n', 1)[1])
    revision = ref['commit']
    state['compiler_repo_commit'] = revision
    url = repo + '/+archive/' + revision + '/clang-r487747c.tar.gz'
    archive = ROOT / 'clang-r487747c.tar.gz'
    if not archive.exists():
        partial = archive.with_suffix('.gz.part')
        digest = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(url, timeout=40) as response, partial.open('wb') as stream:
            while data := response.read(4 * 1024 * 1024):
                stream.write(data)
                digest.update(data)
                count += len(data)
                state['compiler_downloaded_bytes'] = count
                save()
                if count > 3 * 1024**3 or shutil.disk_usage('/mnt/d').free < 40 * 1024**3:
                    raise RuntimeError('Compiler download exceeded size or disk reserve limit')
        partial.rename(archive)
        state['compiler_archive_sha256'] = digest.hexdigest()
    state['phase'] = 'extracting_matching_compiler'
    save()
    compiler.mkdir(exist_ok=True)
    with tarfile.open(archive, 'r:gz') as bundle:
        bundle.extractall(compiler, filter='data')
    version = subprocess.check_output([str(compiler / 'bin/clang'), '--version'], text=True)
    if '17.0.2' not in version or 'r487747c' not in version:
        raise RuntimeError('Compiler does not match stock build version')
    state.update(phase='patched_sources_and_compiler_ready_not_built', compiler_version=version,
                 remaining=['Reproduce the baseline configuration and symbol ABI',
                            'Build and validate the required kernel feature; no installation'])
except BaseException as error:
    state.update(phase='failed', error=str(error))
finally:
    save()
    print(json.dumps(state, indent=2), flush=True)
