"""Add a hang watchdog to diagnostic init and compile it; no device operations."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
base=Path(__file__).resolve().parent;src=Path('/opt/sabrina/android16')
init_cpp=src/'system/core/init/init.cpp';selinux_cpp=src/'system/core/init/selinux.cpp'
work=Path('/opt/sabrina/watchdog-work/init')/str(int(time.time()));work.mkdir(parents=True)
status=base/'WATCHDOG-INIT-BUILD.json'
def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state=dict(started_unix=time.time(),stage='patching',device_accessed=False,work=str(work))
def save():status.write_text(json.dumps(state,indent=2)+'\n')
WATCHDOG=r'''
// Sabrina diagnostic only: a silent hang loses all logs. Report the boot gates, then return to the
// bootloader with a warm reset so the retained console survives and recovery is never entered.
static void SabrinaLogBootGates(int elapsed) {
    static const char* const kProps[] = {
            "apexd.status", "keystore.module_hash.sent", "vold.post_fs_data_done",
            "ro.crypto.state", "odsign.key.done", "odsign.verification.done", "sys.usb.config",
            "init.svc.ueventd", "init.svc.vold", "init.svc.apexd", "init.svc.keystore2",
            "init.svc.vendor.keymint-default", "init.svc.vendor.tee_supplicant",
            "init.svc.hwservicemanager", "init.svc.servicemanager", "init.svc.surfaceflinger",
            "init.svc.bootanim", "init.svc.zygote", "init.svc.odsign"};
    std::string line = StringPrintf("sabrina_watchdog: t=%d", elapsed);
    for (const char* prop : kProps) {
        line += StringPrintf(" %s=%s", prop, android::base::GetProperty(prop, "-").c_str());
    }
    LOG(ERROR) << line;
}

static void SabrinaDumpProcesses() {
    std::unique_ptr<DIR, decltype(&closedir)> proc(opendir("/proc"), closedir);
    if (!proc) return;
    while (dirent* entry = readdir(proc.get())) {
        if (entry->d_name[0] < '0' || entry->d_name[0] > '9') continue;
        std::string base = StringPrintf("/proc/%s/", entry->d_name), stat, wchan;
        if (!android::base::ReadFileToString(base + "stat", &stat)) continue;
        android::base::ReadFileToString(base + "wchan", &wchan);
        // Kernel threads have an empty cmdline and only add noise to the retained console.
        std::string cmdline;
        android::base::ReadFileToString(base + "cmdline", &cmdline);
        if (cmdline.empty()) continue;
        LOG(ERROR) << "sabrina_watchdog: proc " << stat.substr(0, 64) << " wchan=" << wchan;
    }
}

static void SabrinaDumpLogcat() {
    pid_t child = fork();
    if (child == 0) {
        int kmsg = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
        if (kmsg < 0) _exit(1);
        dup2(kmsg, STDOUT_FILENO);
        dup2(kmsg, STDERR_FILENO);
        alarm(20);  // logd may be the component that is stuck.
        execl("/system/bin/logcat", "logcat", "-d", "-b", "all", "-v", "threadtime", "*:W",
              static_cast<char*>(nullptr));
        _exit(1);
    }
    std::this_thread::sleep_for(25s);
}

static void SabrinaHangWatchdog() {
    int limit = 300;
    for (int elapsed = 30; elapsed <= limit; elapsed += 30) {
        if (WaitForProperty("sys.boot_completed", "1", 30s)) {
            LOG(ERROR) << "sabrina_watchdog: boot completed after about " << elapsed << "s";
            return;
        }
        SabrinaLogBootGates(elapsed);
        // First-boot dexopt can be slow once the framework is starting; that is not a hang.
        if (android::base::GetProperty("init.svc.zygote", "") == "running") limit = 900;
    }
    LOG(ERROR) << "sabrina_watchdog: boot incomplete; capturing state and entering bootloader";
    SabrinaDumpLogcat();
    SabrinaDumpProcesses();
    SabrinaLogBootGates(limit);
    sync();
    std::this_thread::sleep_for(500ms);
    syscall(__NR_reboot, LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2, LINUX_REBOOT_CMD_RESTART2,
            "bootloader");
}

static void StartSecondStageBootMonitor(int timeout_sec) {'''
try:
    text=init_cpp.read_text();assert 'SabrinaHangWatchdog' not in text
    shutil.copy2(init_cpp,work/'init.cpp.before');shutil.copy2(selinux_cpp,work/'selinux.cpp.before')
    anchor='\nstatic void StartSecondStageBootMonitor(int timeout_sec) {';assert text.count(anchor)==1
    text=text.replace(anchor,WATCHDOG)
    anchor='    PropertyInit();\n';assert text.count(anchor)==1
    text=text.replace(anchor,anchor+'    std::thread(&SabrinaHangWatchdog).detach();\n')
    anchor='#include <sys/eventfd.h>\n';assert text.count(anchor)==1
    text=text.replace(anchor,'#include <linux/reboot.h>\n'+anchor+'#include <sys/syscall.h>\n#include <sys/wait.h>\n')
    init_cpp.write_text(text)
    text=selinux_cpp.read_text()
    old='bool IsEnforcing() {\n    if (ALLOW_PERMISSIVE_SELINUX) {'
    assert text.count(old)==1
    # Diagnostic only: the boot image's command line selects the mode for one trial.
    selinux_cpp.write_text(text.replace(old,'bool IsEnforcing() {\n    if (true /* SABRINA_DIAGNOSTIC_PERMISSIVE_CMDLINE */) {'))
    log=base/'build-watchdog-init.log'
    cmd=[str(src/'prebuilts/build-tools/linux-x86/bin/ninja'),'-f','out/combined-lineage_gsi_sabrina16.ninja','-j4','out/target/product/generic/system/bin/init']
    state.update(stage='compiling',command=cmd,log=str(log));save()
    with log.open('w') as stream:
        r=subprocess.run(cmd,cwd=src,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,'NINJA_STATUS':'[%f/%t] '},timeout=7000)
    state['exit_code']=r.returncode;assert r.returncode==0,'compile failed; see log'
    artifact=work/'init-watchdog-UNTESTED';shutil.copy2(src/'out/target/product/generic/system/bin/init',artifact)
    state.update(stage='compiled',compiled=True,artifact=str(artifact),sha256=digest(artifact),bytes=artifact.stat().st_size)
except Exception as error:state.update(stage='failed',error=str(error))
state['finished_unix']=time.time();save();print(json.dumps(state,indent=2))
if state['stage']!='compiled':raise SystemExit(1)
