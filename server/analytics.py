"""Pure pandas analytics logic (no MCP imports, so it is easy to test)."""
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

from server.security import PSEUDONYMIZE_COLUMNS, PIISanitizer

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = Path(os.environ.get("DATA_FILE", "data/Retail-Supply-Chain-Sales-Dataset.xlsx"))
if not DATA_FILE.is_absolute():
    DATA_FILE = BASE_DIR / DATA_FILE
MAIN_SHEET = "Retails Order Full Dataset"

ALLOWED_AGGS = {"sum", "mean", "count", "min", "max", "median", "nunique"}
MAX_ROWS = 200


@lru_cache(maxsize=1)
def load_orders() -> pd.DataFrame:
    """Load the Excel file once and cache it in memory."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE.name}")
    df = pd.read_excel(DATA_FILE, sheet_name=MAIN_SHEET)
    df.columns = [str(c).strip() for c in df.columns]
    df["Year"] = df["Order Date"].dt.year
    df["Quarter"] = df["Order Date"].dt.to_period("Q").astype(str)
    df["Month"] = df["Order Date"].dt.to_period("M").astype(str)
    df["Ship Days"] = (df["Ship Date"] - df["Order Date"]).dt.days
    return df


def _col(df: pd.DataFrame, name: str) -> str:
    lookup = {c.lower(): c for c in df.columns}
    key = str(name).strip().lower()
    if key not in lookup:
        raise ValueError(f"Unknown column '{name}'. Available: {list(df.columns)}")
    return lookup[key]


def _apply_filters(df, filters=None, date_from=None, date_to=None):
    if filters:
        for name, val in filters.items():
            c = _col(df, name)
            vals = val if isinstance(val, list) else [val]
            df = df[df[c].astype(str).str.lower().isin([str(v).lower() for v in vals])]
    if date_from:
        df = df[df["Order Date"] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df["Order Date"] <= pd.to_datetime(date_to)]
    return df


def _records(df: pd.DataFrame) -> list:
    df = PIISanitizer.sanitize_dataframe(df)
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_float_dtype(df[c]):
            df[c] = df[c].round(2)
    return df.where(pd.notnull(df), None).to_dict(orient="records")


def dataset_info() -> dict:
    df = load_orders()
    cats = {}
    for c in df.columns:
        if (pd.api.types.is_string_dtype(df[c]) and df[c].nunique() <= 20
                and c.lower() not in PSEUDONYMIZE_COLUMNS):
            cats[c] = sorted(df[c].dropna().unique().tolist())
    return {
        "file": DATA_FILE.name,
        "sheet": MAIN_SHEET,
        "rows": len(df),
        "columns": {c: str(t) for c, t in df.dtypes.items()},
        "date_range": [str(df["Order Date"].min().date()), str(df["Order Date"].max().date())],
        "categorical_values": cats,
        "derived_columns": ["Year", "Quarter", "Month", "Ship Days"],
        "notes": "Customer Name and Retail Sales People are pseudonymized in outputs.",
    }


def preview(n=5, filters=None, date_from=None, date_to=None) -> dict:
    df = _apply_filters(load_orders(), filters, date_from, date_to)
    n = max(1, min(int(n), 50))
    return {"matching_rows": len(df), "rows": _records(df.head(n))}


def kpis(filters=None, date_from=None, date_to=None) -> dict:
    df = _apply_filters(load_orders(), filters, date_from, date_to)
    if df.empty:
        return {"matching_rows": 0}
    sales, profit = df["Sales"].sum(), df["Profit"].sum()
    return {
        "matching_rows": len(df),
        "orders": int(df["Order ID"].nunique()),
        "customers": int(df["Customer ID"].nunique()),
        "total_sales": round(float(sales), 2),
        "total_profit": round(float(profit), 2),
        "profit_margin_pct": round(float(profit / sales * 100), 2) if sales else None,
        "avg_discount_pct": round(float(df["Discount"].mean() * 100), 2),
        "avg_ship_days": round(float(df["Ship Days"].mean()), 2),
        "return_rate_pct": round(float((df["Returned"].astype(str).str.lower() != "not").mean() * 100), 2),
    }


def aggregate(group_by, metrics=None, filters=None, date_from=None, date_to=None,
              sort_by=None, ascending=False, limit=20) -> dict:
    df = _apply_filters(load_orders(), filters, date_from, date_to)
    if df.empty:
        return {"matching_rows": 0, "rows": []}
    group_cols = [_col(df, g) for g in (group_by or [])]
    metrics = metrics or ["Sales:sum", "Profit:sum"]

    named = {}
    for m in metrics:
        col, _, agg = m.partition(":")
        agg = (agg or "sum").lower()
        if agg not in ALLOWED_AGGS:
            raise ValueError(f"Unsupported aggregation '{agg}'. Use one of {sorted(ALLOWED_AGGS)}")
        c = _col(df, col)
        named[f"{c} ({agg})"] = (c, agg)

    if group_cols:
        res = df.groupby(group_cols, dropna=False).agg(**named).reset_index()
    else:
        res = pd.DataFrame([{k: df[c].agg(a) for k, (c, a) in named.items()}])

    if "Sales (sum)" in res and "Profit (sum)" in res:
        res["Profit Margin %"] = (res["Profit (sum)"] / res["Sales (sum)"] * 100).round(2)

    sort_col = _col(res, sort_by) if sort_by else (list(named)[0] if group_cols else None)
    if sort_col:
        res = res.sort_values(sort_col, ascending=bool(ascending))
    limit = max(1, min(int(limit), MAX_ROWS))
    return {"matching_rows": len(df), "groups_returned": min(len(res), limit),
            "total_groups": len(res), "rows": _records(res.head(limit))}
