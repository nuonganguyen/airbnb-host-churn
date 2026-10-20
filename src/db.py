"""Read-only access to the Inside Airbnb data on the external drive.

Every query goes through connect(): ia.db is attached READ_ONLY, and anything
we write (extracts, features, models) lands in data_local/ on this Mac.
"""
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path("/Volumes/UKYECON/AirBnB Data")
SOURCE_DB = SOURCE_DIR / "ia.db"
LOCAL = PROJECT / "data_local"

# CITY_ID values from META.D_LOCATION
CITIES = {11: "Austin", 19: "Denver", 24: "Nashville",
          25: "New Orleans", 33: "San Diego", 38: "Seattle"}


def connect():
    if not SOURCE_DB.exists():
        raise FileNotFoundError(f"{SOURCE_DB} not found - is the UKYECON drive plugged in?")
    LOCAL.mkdir(exist_ok=True)
    con = duckdb.connect(str(LOCAL / "work.duckdb"))
    # SQLite columns are loosely typed; read as text and cast explicitly in SQL
    con.execute("INSTALL sqlite; LOAD sqlite; SET sqlite_all_varchar = true;")
    con.execute(f"ATTACH IF NOT EXISTS '{SOURCE_DB}' AS ia (TYPE sqlite, READ_ONLY)")
    return con
