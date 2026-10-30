"""Reconstruct full-OTA ext4 partitions for offline porting; never touches a device."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import brotli

OTA_SHA256 = "8aacf5f69036c7b881756f031b45834b1770a6973debe07fc8b8d832d9f0c5c2"


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def reconstruct(archive, partition, out):
    lines = archive.read(partition + ".transfer.list").decode("ascii").splitlines()
    if int(lines[0]) != 4 or int(lines[2]) or int(lines[3]):
        raise ValueError("Only full version-4 transfers without stashes are supported")
    ranges = []
    for line in lines[4:]:
        command, encoded = line.split()
        if command != "new":
            raise ValueError(f"Unsupported transfer operation: {command}")
        values = [int(x) for x in encoded.split(",")]
        if values[0] != len(values) - 1 or values[0] % 2:
            raise ValueError("Malformed range set")
        ranges.extend(zip(values[1::2], values[2::2]))
    # Reject overlaps and reversed ranges before creating output.
    previous = 0
    for start, end in sorted(ranges):
        if start < previous or end <= start:
            raise ValueError("Invalid or overlapping ranges")
        previous = end
    expected_bytes = sum(end - start for start, end in ranges) * 4096
    if expected_bytes != int(lines[1]) * 4096:
        raise ValueError("Block count mismatch")
    raw = brotli.decompress(archive.read(partition + ".new.dat.br"))
    if len(raw) != expected_bytes:
        raise ValueError("Decompressed transfer size mismatch")
    target = out / (partition + ".img")
    with target.open("xb") as image:
        offset = 0
        for start, end in ranges:
            size = (end - start) * 4096
            image.seek(start * 4096)
            image.write(memoryview(raw)[offset:offset + size])
            offset += size
    return {"partition": partition, "bytes": target.stat().st_size,
            "sha256": digest(target)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ota", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--partitions", nargs="+", default=["vendor", "odm", "system_dlkm"])
    args = parser.parse_args()
    if digest(args.ota) != OTA_SHA256:
        raise ValueError("Input is not the previously signature-verified stock OTA")
    args.output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.ota) as archive:
        report = [reconstruct(archive, p, args.output) for p in args.partitions]
    (args.output / "partitions.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
