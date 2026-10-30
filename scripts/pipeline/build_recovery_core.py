"""Compile the Android 16 core programs recovery runs on; no device operations."""
from pathlib import Path
import os,subprocess
base=Path(__file__).resolve().parent;src=Path('/opt/sabrina/android16')
log=base/'build-recovery-core.log'
mods='init_second_stage.recovery linker.recovery shell_and_utilities_recovery reboot.recovery ueventd.rc.recovery'
env_setup='source build/envsetup.sh; source vendor/lineage/vars/aosp_target_release; lunch lineage_gsi_sabrina16 "$aosp_target_release" user'
script='set -e; '+env_setup+'; m -k -j4 '+mods
with log.open('w') as stream:
    r=subprocess.run(['bash','-lc',script],cwd=src,stdout=stream,stderr=subprocess.STDOUT,timeout=14000,env={**os.environ,'NINJA_STATUS':'[%f/%t] '})
root=src/'out/target/product/generic/recovery/root'
print('exit',r.returncode)
print('top',sorted(p.name for p in root.iterdir()))
print('bin',len(list((root/'system/bin').iterdir())),[n for n in ('init','linker','toybox','sh','reboot','linkerconfig') if (root/'system/bin'/n).exists()])
print('etc',sorted(p.name for p in (root/'system/etc').rglob('*'))[:30])
t=log.read_text(errors='replace');print('\n'.join(l[:190] for l in t.splitlines() if re.search(r'error|FAILED|unknown module|does not exist',l,re.I))[:1500] if False else '')
print('\n'.join(l[:190] for l in t.splitlines() if 'rror' in l or 'FAILED' in l)[:1500]);print(t[-400:])
