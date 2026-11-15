"""Excel Insight Dashboard · Simple analytics from your Excel workbook."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from analytics import (
    as_excel_bytes, as_html_report, category_columns, create_charts, date_columns,
    filtered_frame, numeric_columns, prepare_frame, summary_stats,
)

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "sample_data" / "sample_sales.xlsx"

st.set_page_config(page_title="Excel Insight | Data Dashboard", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
.block-container {max-width: 1300px; padding-top: 1.8rem; padding-bottom: 3rem;}
[data-testid="stSidebar"] {border-right: 1px solid #253149;}
.hero {border: 1px solid #2C3850; background: linear-gradient(115deg,#18263E,#121D31 65%,#251D49);
       padding: 27px 32px; border-radius: 22px; margin-bottom: 19px;}
.eyebrow {color:#77CDFF; font-size:12px; font-weight:750; letter-spacing:2.1px; margin:0 0 9px;}
.hero h1 {font-size:42px; letter-spacing:-1.4px; line-height:1.1; margin:0 0 10px; color:#FFFFFF;}
.hero p {font-size:15px; color:#B8C6DB; max-width:750px; margin:0; line-height:1.7;}
.meta-line {color:#98A8BF;font-size:13px;margin:4px 0 16px;}
.section-note {font-size:13px;color:#9FAFC7;}
[data-testid="stMetric"] {border:1px solid #28374F;border-radius:15px;background:#131F31;
                           padding:17px 19px; min-height:116px;}
[data-testid="stMetricLabel"] {color:#ADC0D6;}
[data-testid="stMetricValue"] {color:#F7FAFF;}
div[data-testid="stPlotlyChart"] {border:1px solid #28374F;border-radius:15px;overflow:hidden;}
[data-testid="stFileUploader"] {border-radius:14px;}
.stDownloadButton button {border-radius:10px;}
</style>
""", unsafe_allow_html=True)

st.markdown('''<div class="hero"><div class="eyebrow">EXCEL INSIGHT / INTERACTIVE ANALYTICS</div>
<h1>Understand your data, instantly.</h1>
<p>Drop in an Excel workbook, choose your columns, and explore a clean, interactive dashboard. No coding, no database, no account.</p></div>''', unsafe_allow_html=True)


st.markdown(
    """
    <div style="text-align:right; margin:0 0 24px; color:#B8C6DB; font-size:14px;">
        Designed & Developed by
        <strong style="color:#77CDFF;">Saman Farshad</strong>
        <span style="color:#8EA3C2;"> | Python & Data Science</span>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner=False)
def workbook_sheets(raw: bytes) -> list[str]:
    with pd.ExcelFile(BytesIO(raw), engine="openpyxl") as book:
        return book.sheet_names


@st.cache_data(show_spinner=False)
def load_sheet(raw: bytes, sheet: str) -> pd.DataFrame:
    return prepare_frame(pd.read_excel(BytesIO(raw), sheet_name=sheet, engine="openpyxl"))


st.sidebar.markdown("## Data source")
uploaded = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"],
                                    help="Use a workbook with one header row and tabular data.")
if uploaded is not None:
    raw_bytes = uploaded.getvalue()
    source_name = uploaded.name
    demo_mode = False
else:
    demo_mode = st.sidebar.toggle("Explore with sample data", value=True)
    if not demo_mode:
        st.info("Upload an Excel file in the left sidebar, or enable the sample dataset to explore the dashboard.")
        st.stop()
    raw_bytes = DEMO.read_bytes()
    source_name = DEMO.name

try:
    sheets = workbook_sheets(raw_bytes)
    selected_sheet = st.sidebar.selectbox("Worksheet", sheets)
    frame = load_sheet(raw_bytes, selected_sheet)
except Exception as exc:
    st.error(f"The workbook could not be opened. Check that it is a valid .xlsx file. ({type(exc).__name__})")
    st.stop()

if frame.empty:
    st.warning("This worksheet does not contain any data rows.")
    st.stop()

metrics = numeric_columns(frame)
if not metrics:
    st.warning("No numeric columns were found. In Excel, make sure the metric column contains numbers, not text.")
    st.dataframe(frame.head(15), width="stretch", hide_index=True)
    st.stop()

available_dates = date_columns(frame)
available_categories = category_columns(frame)

st.sidebar.markdown("## Chart settings")
metric_default = next((i for i, col in enumerate(metrics) if col.lower() in ("revenue", "sales", "amount", "total")), 0)
metric = st.sidebar.selectbox("Measure", metrics, index=metric_default)
agg = st.sidebar.selectbox("Aggregate by", ["Sum", "Average"], index=0)

cat_options = ["(None)"] + available_categories
cat_default = next((i for i, col in enumerate(cat_options) if col.lower() in ("category", "region", "segment")), 0)
cat_choice = st.sidebar.selectbox("Group by", cat_options, index=cat_default)
category = None if cat_choice == "(None)" else cat_choice

date_options = ["(None)"] + available_dates
date_choice = st.sidebar.selectbox("Date column", date_options, index=1 if available_dates else 0)
date = None if date_choice == "(None)" else date_choice

selected_categories: list[str] = []
if category:
    available_values = frame[category].astype("string").fillna("(Unknown)").value_counts().index.tolist()
    selected_categories = st.sidebar.multiselect("Filter groups (optional)", available_values[:40], default=[],
                                                  help="Leave empty to include all groups. Showing up to 40 common values.")

start_date, end_date = None, None
if date:
    parsed_dates = pd.to_datetime(frame[date], errors="coerce", dayfirst=True).dropna()
    if not parsed_dates.empty:
        start, end = parsed_dates.min().date(), parsed_dates.max().date()
        date_range = st.sidebar.date_input("Date range", value=(start, end), min_value=start, max_value=end)
        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_date, end_date = date_range
    else:
        st.sidebar.caption("No valid dates found; choose another date field.")
        date = None

other_metrics = [name for name in metrics if name != metric]
secondary = next((name for name in other_metrics if name.lower() in ("profit", "cost", "quantity", "units")),
                 other_metrics[0] if other_metrics else None)

filtered = filtered_frame(frame, metric, category, selected_categories, date, start_date, end_date)
if filtered.empty:
    st.warning("No valid rows match these filters. Try a different column or date range.")
    st.stop()

stats = summary_stats(filtered)
unit_count = f"{len(filtered):,} of {len(frame):,} rows"
st.caption(f"📄 {source_name} · Sheet: {selected_sheet} · {unit_count} analyzed")

col1, col2, col3, col4 = st.columns(4, gap="small")
with col1:
    st.metric("Total · " + metric, f"{stats['total']:,.2f}")
with col2:
    st.metric("Average per row", f"{stats['average']:,.2f}")
with col3:
    st.metric("Valid rows", f"{stats['rows']:,}")
with col4:
    st.metric("Highest value", f"{stats['max']:,.2f}")

st.markdown("### Visual overview")
charts = create_charts(filtered, metric, category, date, agg, secondary)
config = {"displayModeBar": False, "responsive": True}

st.plotly_chart(charts[0][1], width="stretch", config=config, key="main_chart")
left, right = st.columns(2, gap="medium")
with left:
    st.plotly_chart(charts[1][1], width="stretch", config=config, key="detail_a")
with right:
    st.plotly_chart(charts[2][1], width="stretch", config=config, key="detail_b")

st.markdown("### Export your results")
st.caption("Export the filtered source rows to Excel, or save a standalone interactive HTML report that opens offline.")
export_col1, export_col2 = st.columns(2, gap="medium")
with export_col1:
    st.download_button("⬇ Download filtered Excel", data=as_excel_bytes(filtered),
                       file_name="excel_insight_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="stretch")
with export_col2:
    st.download_button("⬇ Download interactive HTML report", data=as_html_report(charts, stats, source_name, metric, len(filtered)),
                       file_name="excel_insight_report.html", mime="text/html", width="stretch")

with st.expander("Preview filtered data"):
    export_view = filtered.loc[:, [c for c in filtered.columns if c not in {"_metric", "_category", "_date", "_secondary"}]]
    st.dataframe(export_view.head(200), width="stretch", hide_index=True)
    if len(export_view) > 200:
        st.caption("Preview limited to 200 rows. Excel download contains all filtered rows.")

st.caption("Excel Insight · Streamlit + Pandas + Plotly · Files are processed in the app session; no external AI API is used.")
