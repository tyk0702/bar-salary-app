from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlencode

import pandas as pd


FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScNydbSJ03cCZd4_rs56zaq-CDSqRa5wVp5d_D1nqZTkYZ7Cg/formResponse"

FORM_ENTRIES = {
    "date": "entry.2065842886",
    "name": "entry.1983050011",
    "hourly_rate": "entry.137452632",
    "hours": "entry.347515091",
    "sales": "entry.1200084478",
    "commission_rate": "entry.1030999587",
}


def to_number(value: Any) -> float:
    """Convert spreadsheet-style values such as '1,200' or blanks to float."""
    if value is None:
        return 0.0

    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0

    parsed = pd.to_numeric(text, errors="coerce")
    if pd.isna(parsed):
        return 0.0
    return float(parsed)


def calculate_salary(hourly_rate: Any, hours: Any, sales: Any, commission_rate: Any) -> float:
    hourly_pay = to_number(hourly_rate) * to_number(hours)
    commission_pay = to_number(sales) * to_number(commission_rate)
    return max(hourly_pay, commission_pay)


def build_submission_url(
    input_date: date,
    name: str,
    hourly_rate: Any,
    hours: Any,
    sales: Any,
    commission_rate: Any,
) -> str:
    params = {
        FORM_ENTRIES["date"]: input_date.strftime("%Y-%m-%d"),
        FORM_ENTRIES["name"]: name.strip(),
        FORM_ENTRIES["hourly_rate"]: hourly_rate,
        FORM_ENTRIES["hours"]: hours,
        FORM_ENTRIES["sales"]: sales,
        FORM_ENTRIES["commission_rate"]: commission_rate,
        "submit": "Submit",
    }
    return f"{FORM_URL}?{urlencode(params)}"


def normalize_work_records(df_raw: pd.DataFrame | None) -> pd.DataFrame:
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.loc[:, ~df_raw.columns.duplicated()].copy()
    records = []
    column_count = len(df.columns)

    for row in df.itertuples(index=False, name=None):
        timestamp = row[0] if column_count > 0 else ""
        input_date = row[1] if column_count > 1 else ""

        parsed_date = pd.to_datetime(input_date, errors="coerce")
        if pd.isna(parsed_date):
            parsed_date = pd.to_datetime(timestamp, errors="coerce")
        if pd.isna(parsed_date):
            continue

        records.append(
            {
                "確定日付": parsed_date,
                "名前": str(row[2]).strip() if column_count > 2 and str(row[2]).strip() else "不明",
                "時給": to_number(row[3] if column_count > 3 else 0),
                "勤務時間": to_number(row[4] if column_count > 4 else 0),
                "個人売上": to_number(row[5] if column_count > 5 else 0),
                "歩合率": to_number(row[6] if column_count > 6 else 0),
            }
        )

    return pd.DataFrame(records)


def add_week_columns(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return records.copy()

    result = records.copy()
    result["週開始"] = result["確定日付"].apply(
        lambda value: value - pd.Timedelta(days=(value.weekday() + 1) % 7)
    )
    result["週ラベル"] = result["週開始"].dt.strftime("%Y-%m-%d (日)〜")
    return result


def summarize_salary(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    work_df = records.copy()
    work_df["時給計算"] = work_df["時給"] * work_df["勤務時間"]
    work_df["歩合計算"] = work_df["個人売上"] * work_df["歩合率"]

    summary = (
        work_df.groupby("名前", as_index=False)
        .agg({"勤務時間": "sum", "個人売上": "sum", "時給計算": "sum", "歩合計算": "sum"})
    )
    summary["最終支給額"] = summary[["時給計算", "歩合計算"]].max(axis=1)
    summary["計算方法"] = summary.apply(
        lambda row: "歩合" if row["歩合計算"] > row["時給計算"] else "時給保障",
        axis=1,
    )
    return summary
