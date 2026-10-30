"""Build the signing tools and the target-files package; no device operations and no key use."""
from pathlib import Path
import glob,os,subprocess,time
base=Path(__file__).resolve().parent;src=Path('/opt/sabrina/android16')
log=base/'build-target-files.log'
script='set -e; source build/envsetup.sh; source vendor/lineage/vars/aosp_target_release; lunch lineage_gsi_sabrina16 "$aosp_target_release" user; m -k -j4 otatools target-files-package'
start=time.time()
with log.open('w') as stream:
    r=subprocess.run(['bash','-lc',script],cwd=src,stdout=stream,stderr=subprocess.STDOUT,timeout=28000,env={**os.environ,'NINJA_STATUS':'[%f/%t] '})
print('exit',r.returncode,'minutes',round((time.time()-start)/60,1))
print('signer',(src/'out/host/linux-x86/bin/sign_target_files_apks').exists(),'sign_apex',(src/'out/host/linux-x86/bin/sign_apex').exists())
print('target files',glob.glob(str(src/'out/target/product/generic/obj/PACKAGING/target_files_intermediates/*.zip'))[:2])
t=log.read_text(errors='replace').splitlines()
print('\n'.join(l[:220] for l in t if 'FAILED:' in l or ' error:' in l or 'ninja failed' in l)[:2500])
print('\n'.join(l[:200] for l in t[-4:]))
