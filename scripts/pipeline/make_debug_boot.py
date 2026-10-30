"""Prepare a RAM-boot debugging image from this device's verified stock boot.
Keeps kernel, DTB, second stage and cmdline intact; does not flash anything.
USB ADB authentication remains required.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
BOOT = ROOT / "stock-boot"
stock = (BOOT / "boot.img").read_bytes()
if hashlib.sha256(stock).hexdigest() != "c4cb0f2e405227e058d367b4ced20fa49fdc0cc89686c0c8dff5b6e3fa115934":
    raise ValueError("Unexpected stock boot image")
original = gzip.decompress((BOOT / "unpacked/ramdisk").read_bytes())
position = 0
entries = {}
maximum_inode = 0
while position + 110 <= len(original):
    start = position
    header = original[position:position + 110]
    if header[:6] != b"070701":
        raise ValueError("Unexpected CPIO format")
    fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
    name = original[position + 110:position + 110 + fields[11] - 1].decode()
    data_start = (position + 110 + fields[11] + 3) & ~3
    data_end = data_start + fields[6]
    position = (data_end + 3) & ~3
    if name == "TRAILER!!!":
        trailer_start = start
        break
    entries[name] = original[data_start:data_end]
    maximum_inode = max(maximum_inode, fields[0])
else:
    raise ValueError("Missing CPIO trailer")

def entry(name, data, inode):
    encoded_name = name.encode() + b"\0"
    fields = [inode, 0o100644, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded_name), 0]
    header = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
    result = header + encoded_name
    result += b"\0" * (-len(result) % 4)
    result += data
    return result + b"\0" * (-len(data) % 4)

additions = {"force_debuggable": b"",
             "adb_debug.prop": b"ro.adb.secure=1\nro.debuggable=1\nro.force.debuggable=1\n"}
if entries.keys() & additions.keys():
    raise ValueError("Debug files unexpectedly already present")
new = original[:trailer_start]
for index, (name, data) in enumerate(additions.items(), maximum_inode + 1):
    new += entry(name, data, index)
new += entry("TRAILER!!!", b"", maximum_inode + 3)
new += b"\0" * (-len(new) % 512)
debug_ramdisk = BOOT / "debug-ramdisk.gz"
debug_ramdisk.write_bytes(gzip.compress(new, compresslevel=9, mtime=0))
arguments = shlex.split((BOOT / "mkbootimg-args.txt").read_text(encoding="utf-8-sig"))
arguments[arguments.index("--ramdisk") + 1] = str(debug_ramdisk)
output = BOOT / "boot-debug-temporary.img"
subprocess.run([sys.executable, str(ROOT / "mkbootimg-tools/mkbootimg.py"),
                *arguments, "--output", str(output)], cwd=ROOT.parent, check=True)
unpacked = BOOT / "debug-verify"
subprocess.run([sys.executable, str(ROOT / "mkbootimg-tools/unpack_bootimg.py"),
                "--boot_img", str(output), "--out", str(unpacked)], check=True, capture_output=True)
for part in ("kernel", "second", "dtb"):
    if (unpacked / part).read_bytes() != (BOOT / "unpacked" / part).read_bytes():
        raise ValueError(f"Unexpected change to {part}")
if gzip.decompress((unpacked / "ramdisk").read_bytes()) != new:
    raise ValueError("Debug ramdisk round-trip mismatch")
report = {"image": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
          "bytes": output.stat().st_size, "changes": list(additions),
          "stock_kernel_second_dtb_unchanged": True, "adb_authentication_required": True,
          "persistent_partitions_written": False}
(BOOT / "debug-image-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
