import pandas as pd

from analytics import (
    as_excel_bytes, as_html_report, category_columns, create_charts,
    date_columns, filtered_frame, numeric_columns, prepare_frame, summary_stats,
)


def sample_frame():
    return pd.DataFrame({
        "Date": pd.to_datetime(["2026-01-01", "2026-01-17", "2026-02-05"]),
        "Region": ["North", "South", "North"],
        "Revenue": [100, 200, 300],
        "Profit": [25, 50, 70],
    })


def test_suggested_fields():
    frame = sample_frame()
    assert numeric_columns(frame) == ["Revenue", "Profit"]
    assert date_columns(frame) == ["Date"]
    assert category_columns(frame) == ["Region"]


def test_filters_and_kpis():
    frame = filtered_frame(sample_frame(), "Revenue", "Region", ["North"], "Date")
    assert summary_stats(frame) == {"total": 400.0, "average": 200.0, "rows": 2, "max": 300.0}


def test_three_charts_and_exports():
    frame = filtered_frame(sample_frame(), "Revenue", "Region", date="Date")
    charts = create_charts(frame, "Revenue", "Region", "Date", "Sum", "Profit")
    assert len(charts) == 3
    assert as_excel_bytes(frame).startswith(b"PK")
    report = as_html_report(charts, summary_stats(frame), "sales.xlsx", "Revenue", 3)
    assert b"<html" in report
    assert b"plotly" in report


def test_column_cleanup():
    frame = pd.DataFrame([[1, None], [2, None]], columns=[" Value ", " Empty "])
    assert list(prepare_frame(frame).columns) == ["Value"]


def test_single_numeric_column_has_three_charts():
    frame = pd.DataFrame({"Value": [3, 6, 9, 12]})
    filtered = filtered_frame(frame, "Value")
    charts = create_charts(filtered, "Value", None, None, "Sum", None)
    assert len(charts) == 3
