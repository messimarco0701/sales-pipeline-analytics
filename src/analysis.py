"""
Runs the SQL files in sql/ against the CSVs in data/ with DuckDB.

Each numbered file answers one business question and ends with a SELECT; its result comes back
as a DataFrame named after the file (01_funnel.sql -> "funnel"). Files can also create tables
that later files use (09 builds open_pipeline, 10 reads it), so they run in order on one connection.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"
SNAPSHOT = date(2026, 9, 30)


def connect(data_dir: Path = DATA_DIR) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    run_file(con, SQL_DIR / "00_staging.sql", data_dir)
    return con


def run_file(con: duckdb.DuckDBPyConnection, path: Path, data_dir: Path = DATA_DIR):
    sql = (path.read_text(encoding="utf-8")
           .replace("{data_dir}", data_dir.as_posix())
           .replace("{snapshot}", SNAPSHOT.isoformat()))
    return con.execute(sql)


def run_all(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    con = connect(data_dir)
    results = {}
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        if path.name.startswith("00_"):
            continue
        name = path.stem.split("_", 1)[1]
        results[name] = run_file(con, path, data_dir).df()
    results["deals"] = con.execute("SELECT * FROM deals ORDER BY deal_id").df()
    con.close()
    return results
