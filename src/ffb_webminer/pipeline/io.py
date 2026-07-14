"""CSV/Parquet I/O helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_csv(df: pd.DataFrame, path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = None
    out = out[columns]
    out.to_csv(path, index=False, encoding="utf-8")


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
