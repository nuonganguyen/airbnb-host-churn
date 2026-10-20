"""Prove the source data was never modified.

    python src/fingerprint.py           # record size + mtime of every source file
    python src/fingerprint.py --check   # compare against the recorded manifest
"""
import csv
import os
import sys

from db import LOCAL, SOURCE_DIR

MANIFEST = LOCAL / "source_manifest.csv"


def scan():
    rows = {}
    for root, _, files in os.walk(SOURCE_DIR):
        for f in files:
            # macOS writes ._* and .DS_Store sidecars to exFAT drives on its own
            if f.startswith("._") or f == ".DS_Store":
                continue
            p = os.path.join(root, f)
            st = os.stat(p)
            rows[os.path.relpath(p, SOURCE_DIR)] = (str(st.st_size), str(int(st.st_mtime)))
    return rows


def main():
    current = scan()
    if "--check" not in sys.argv:
        LOCAL.mkdir(exist_ok=True)
        with open(MANIFEST, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "size", "mtime"])
            for path, (size, mtime) in sorted(current.items()):
                w.writerow([path, size, mtime])
        print(f"recorded {len(current)} files -> {MANIFEST}")
        return

    with open(MANIFEST, newline="") as fh:
        saved = {r["path"]: (r["size"], r["mtime"]) for r in csv.DictReader(fh)}
    changed = [p for p in saved if p in current and current[p] != saved[p]]
    missing = [p for p in saved if p not in current]
    added = [p for p in current if p not in saved]
    for label, items in (("CHANGED", changed), ("MISSING", missing), ("NEW", added)):
        for p in items:
            print(f"{label}: {p}")
    if changed or missing or added:
        sys.exit(1)
    print(f"OK - all {len(saved)} source files unchanged")


if __name__ == "__main__":
    main()
