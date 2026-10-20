"""Run one or more SQL files against the read-only source.

    python src/run_sql.py sql/01_extract.sql
"""
import sys
import time
from pathlib import Path

from db import PROJECT, connect


def main(paths):
    con = connect()
    for p in paths:
        sql = Path(p).read_text()
        start = time.time()
        print(f"running {p} ...", flush=True)
        con.execute(sql)
        print(f"  done in {time.time() - start:.0f}s")


if __name__ == "__main__":
    import os
    os.chdir(PROJECT)  # so relative output paths in SQL resolve to the project
    main(sys.argv[1:])
