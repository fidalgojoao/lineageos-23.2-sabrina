"""Exercise real libsparse resparse + simg2img overlay offline, never USB.

Modern AOSP removed the simg2simg CLI. This calls the same built libsparse C API
sequence as fastboot util.cpp, then uses the real multi-input simg2img tool.
"""
import ctypes as C
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest',type=Path,default=BASE/'CANDIDATE-MANIFEST.json')
parser.add_argument('--status-output',type=Path,default=BASE/'CHUNK-TRANSFER-REVIEW.json')
args = parser.parse_args()
ROOT = Path('/opt/sabrina/android16')
HOST = ROOT/'out/host/linux-x86'
LIMIT = 96*1024**2
DEVICE_LIMIT = 128*1024**2
WORK = Path('/opt/sabrina/chunk-transfer-review')/str(int(time.time()))
report = dict(started_unix=time.time(),device_modified=False,usb_accessed=False,
    ready_to_flash=False,passed=False,chunk_limit_bytes=LIMIT,
    observed_device_max_download_bytes=DEVICE_LIMIT,images={},work=str(WORK))

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()

def save():
    report['updated_unix'] = time.time()
    args.status_output.write_text(json.dumps(report,indent=2)+'\n')

try:
    assert LIMIT < DEVICE_LIMIT
    manifest_path = args.manifest
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    report['candidate_manifest_sha256'] = hashlib.sha256(manifest_bytes).hexdigest()
    library = HOST/'lib64/libsparse-host.so'
    assert library.is_file() and (HOST/'bin/simg2img').is_file()
    sparse = C.CDLL(str(library),use_errno=True)
    def sig(name,args,result):
        fn = getattr(sparse,name)
        fn.argtypes,fn.restype = args,result
        return fn
    load = sig('sparse_file_import',[C.c_int,C.c_bool,C.c_bool],C.c_void_p)
    split = sig('sparse_file_resparse',[C.c_void_p,C.c_uint,C.POINTER(C.c_void_p),C.c_int],C.c_int)
    length = sig('sparse_file_len',[C.c_void_p,C.c_bool,C.c_bool],C.c_int64)
    CALLBACK = C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_size_t)
    callback_write = sig('sparse_file_callback',[C.c_void_p,C.c_bool,C.c_bool,CALLBACK,C.c_void_p],C.c_int)
    destroy = sig('sparse_file_destroy',[C.c_void_p],None)
    report['libsparse'] = dict(path=str(library),sha256=digest(library))
    report['simg2img'] = dict(path=str(HOST/'bin/simg2img'),sha256=digest(HOST/'bin/simg2img'))
    sources = [('custom',manifest['super_sparse'],manifest['super_raw']['sha256']),
               ('stock',manifest['stock_recovery_sparse'],manifest['stock_recovery_sparse']['original_raw_sha256'])]
    WORK.mkdir(parents=True,exist_ok=False)
    for name,entry,raw_hash in sources:
        report['active_image'] = name
        save()
        folder = WORK/name
        folder.mkdir()
        source = Path(entry['path'])
        assert source.stat().st_size == entry['bytes'] and digest(source) == entry['sha256']
        chunks = []
        pointers = []
        fd = os.open(source,os.O_RDONLY)
        original = None
        try:
            original = load(fd,True,False)
            assert original,'libsparse import failed'
            assert length(original,False,False) == entry['original_raw_bytes']
            count = split(original,LIMIT,None,0)
            assert 1 < count < 128,'Unexpected resparse output count'
            array = (C.c_void_p*count)()
            produced = split(original,LIMIT,array,count)
            assert produced == count,'libsparse boundary count changed'
            pointers = [array[i] for i in range(count)]
            assert all(pointers)
            for number,pointer in enumerate(pointers):
                path = folder/f'part-{number:03d}.sparse.img'
                encoded_size = length(pointer,True,False)
                assert 0 < encoded_size <= LIMIT < DEVICE_LIMIT
                assert length(pointer,False,False) == entry['original_raw_bytes']
                output_fd = os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
                callback_errors = []
                def store_bytes(private,data,size):
                    try:
                        assert data or size == 0,'Unexpected sparse-mode hole callback'
                        offset = 0
                        while offset < size:
                            chunk = C.string_at(data+offset,min(size-offset,1024**2))
                            consumed = 0
                            while consumed < len(chunk):
                                written = os.write(output_fd,chunk[consumed:])
                                assert written > 0
                                consumed += written
                            offset += len(chunk)
                        return 0
                    except Exception as error:
                        callback_errors.append(str(error))
                        return -5
                writer = CALLBACK(store_bytes)
                try:
                    # Match FastBootDriver::Download exactly. sparse_file_write
                    # would split blocks at 64MiB and add headers after len()
                    # prediction; fastboot uses this callback API instead.
                    assert callback_write(pointer,True,False,writer,None) == 0,'libsparse chunk callback failed'
                    assert not callback_errors,callback_errors
                finally:
                    os.close(output_fd)
                assert path.stat().st_size == encoded_size
                chunks.append(dict(path=str(path),bytes=encoded_size,sha256=digest(path),
                    logical_bytes=entry['original_raw_bytes']))
        finally:
            for pointer in pointers:
                destroy(pointer)
            if original:
                destroy(original)
            os.close(fd)
        overlay = folder/'overlay-roundtrip.raw.img'
        command = [str(HOST/'bin/simg2img'),*[part['path'] for part in chunks],str(overlay)]
        result = subprocess.run(command,capture_output=True,text=True,timeout=600)
        (folder/'simg2img-overlay.log').write_text(result.stdout+result.stderr)
        assert result.returncode == 0,'Real simg2img multi-input overlay failed'
        actual = digest(overlay)
        assert overlay.stat().st_size == entry['original_raw_bytes'] and actual == raw_hash
        assert digest(source) == entry['sha256'],'Source input changed unexpectedly'
        report['images'][name] = dict(source=entry,chunk_count=len(chunks),chunks=chunks,
            maximum_chunk_bytes=max(part['bytes'] for part in chunks),
            overlay_raw=str(overlay),overlay_bytes=overlay.stat().st_size,
            overlay_sha256=actual,expected_raw_sha256=raw_hash,overlay_matches_original_raw=True)
        save()
    paths = ['system/core/fastboot/fastboot.cpp','system/core/fastboot/util.cpp',
             'system/core/fastboot/fastboot_driver.cpp','system/core/libsparse/sparse.cpp',
             'system/core/libsparse/include/sparse/sparse.h','system/core/libsparse/simg2img.cpp',
             'system/libbase/include/android-base/parseint.h']
    report.update(passed=True,maximum_chunk_bytes=max(v['maximum_chunk_bytes'] for v in report['images'].values()),
        source_files_sha256={name:digest(ROOT/name) for name in paths},
        source_review=dict(explicit_sparse_limit_overrides_auto_query=True,
            byte_count_M_is_binary_MiB=True,uses_standard_fastboot_resparse_API_sequence=True,
            standard_client_chunk_crc=False,actual_device_data_transfer_performed=False),
        limitations='Proves offline chunk size and overlay reconstruction only. No DATA handshake, transfer or partition write was executed; actual flash/restore and hardware remain untested.')
except Exception as error:
    report['error'] = str(error)
    report['traceback'] = traceback.format_exc()
report.pop('active_image',None)
report['finished_unix'] = time.time()
save()
print(json.dumps({k:v for k,v in report.items() if k != 'images'},indent=2))
print(json.dumps({name:{k:v for k,v in item.items() if k not in ['chunks','source']} for name,item in report['images'].items()},indent=2))
if not report['passed']:
    raise SystemExit(1)
