"""Compile Lineage's recovery and its dependencies from the source tree; no device operations."""
from pathlib import Path
import os,subprocess,time
base=Path(__file__).resolve().parent;src=Path('/opt/sabrina/android16')
log=base/'build-recovery-source.log'
script='set -e; source build/envsetup.sh; source vendor/lineage/vars/aosp_target_release; lunch lineage_gsi_sabrina16 "$aosp_target_release" user; m -j4 recovery fastbootd adbd.recovery minadbd librecovery_ui_default'
with log.open('w') as stream:
    r=subprocess.run(['bash','-lc',script],cwd=src,stdout=stream,stderr=subprocess.STDOUT,timeout=14000,env={**os.environ,'NINJA_STATUS':'[%f/%t] '})
root=src/'out/target/product/generic/recovery/root'
print('exit',r.returncode,'finished',time.time())
print('recovery binary',(root/'system/bin/recovery').is_file())
if root.is_dir():
    print('bin',sorted(p.name for p in (root/'system/bin').iterdir())[:40] if (root/'system/bin').is_dir() else [])
    print('top',sorted(p.name for p in root.iterdir()))
print(''.join(log.read_text(errors='replace').splitlines(True)[-12:])[-1400:])
