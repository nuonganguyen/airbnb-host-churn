"""Freeze the analysis before the holdout, and verify the freeze before running it.

The freeze records every analysis setting plus a SHA-256 of each code, SQL and config
file that produces results. `--holdout` runs refuse to start if any of them changed.

    python src/freeze.py          # write the hashes into config/analysis_freeze.json
    python src/freeze.py --check  # verify without writing
"""
import hashlib
import json
import subprocess
import sys

from db import PROJECT

FREEZE = PROJECT / "config" / "analysis_freeze.json"
FROZEN_FILES = sorted(
    [p for p in (PROJECT / "src").glob("*.py") if p.name != "freeze.py"]
    + list((PROJECT / "sql").glob("*.sql"))
    + [PROJECT / "config" / "quality_policy.json"]
)


def digests():
    return {str(p.relative_to(PROJECT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN_FILES}


def write():
    spec = json.loads(FREEZE.read_text())
    spec["file_sha256"] = digests()
    spec["git_commit_at_freeze"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT,
                                                  capture_output=True, text=True).stdout.strip()
    FREEZE.write_text(json.dumps(spec, indent=2) + "\n")
    print(f"froze {len(spec['file_sha256'])} files -> {FREEZE}")


def verify():
    spec = json.loads(FREEZE.read_text())
    if "file_sha256" not in spec:
        raise SystemExit("analysis is not frozen yet: run `python src/freeze.py` first")
    now = digests()
    changed = sorted(f for f in set(spec["file_sha256"]) | set(now) if spec["file_sha256"].get(f) != now.get(f))
    if changed:
        raise SystemExit(f"frozen analysis changed since the freeze: {changed}")
    return spec


if __name__ == "__main__":
    if "--check" in sys.argv:
        verify()
        print("freeze intact")
    else:
        write()
