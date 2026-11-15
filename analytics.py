"""Small, reusable data transformations for the Excel Insight dashboard."""
from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.io as pio

BG = "#101827"
PAPER = "#131F31"
TEXT = "#EAF1FF"
MUTED = "#A2B0C4"
BLUE = "#56B8FF"
PURPLE = "#9184FF"
TEAL = "#42D8C4"


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Remove fully empty rows/columns and normalize column names."""
    clean = df.dropna(axis=0, how="all").dropna(axis=1, how="all").copy()
    seen: dict[str, int] = {}
    names: list[str] = []
    for col in clean.columns:
        name = str(col).strip() or "Column"
        seen[name] = seen.get(name, 0) + 1
        names.append(f"{name} ({seen[name]})" if seen[name] > 1 else name)
    clean.columns = names
    return clean.reset_index(drop=True)


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]


def date_columns(df: pd.DataFrame) -> list[str]:
    """Suggest date columns, without interpreting arbitrary numeric IDs as dates."""
    hints = ("date", "datum", "time", "تاریخ", "fecha", "jour")
    result = []
    for name in df.columns:
        column = df[name]
        if pd.api.types.is_datetime64_any_dtype(column):
            result.append(name)
        elif (pd.api.types.is_object_dtype(column) or pd.api.types.is_string_dtype(column)) and any(
            token in name.lower() for token in hints
        ):
            parsed = pd.to_datetime(column, errors="coerce", dayfirst=True)
            if parsed.notna().sum() >= max(1, int(column.notna().sum() * 0.7)):
                result.append(name)
    return result


def category_columns(df: pd.DataFrame) -> list[str]:
    dates = set(date_columns(df))
    return [
        col for col in df.columns
        if (pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])
            or isinstance(df[col].dtype, pd.CategoricalDtype))
        and col not in dates
    ]


def filtered_frame(
    df: pd.DataFrame,
    metric: str,
    category: str | None = None,
    selected_categories: list[str] | None = None,
    date: str | None = None,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Produce chart-ready data without overwriting the input workbook's data."""
    out = df.copy()
    out["_metric"] = pd.to_numeric(out[metric], errors="coerce")
    if category is not None:
        out["_category"] = out[category].astype("string").fillna("(Unknown)")
        if selected_categories:
            out = out.loc[out["_category"].isin(selected_categories)].copy()
    if date is not None:
        out["_date"] = pd.to_datetime(out[date], errors="coerce", dayfirst=True)
        if start_date is not None and end_date is not None:
            d = out["_date"].dt.date
            out = out.loc[(d >= start_date) & (d <= end_date)].copy()
    return out.loc[out["_metric"].notna()].copy()


def summary_stats(df: pd.DataFrame) -> dict[str, float | int]:
    values = df["_metric"]
    return {
        "total": float(values.sum()),
        "average": float(values.mean()),
        "rows": int(len(df)),
        "max": float(values.max()),
    }


def style_chart(fig, height: int = 340):
    fig.update_layout(
        template="plotly_dark", paper_bgcolor=PAPER, plot_bgcolor=PAPER,
        font=dict(family="Arial, sans-serif", color=TEXT, size=12),
        margin=dict(l=20, r=22, t=48, b=26),
        height=height, showlegend=False,
        title_font=dict(size=16, color=TEXT),
        xaxis=dict(showgrid=True, gridcolor="rgba(180,200,230,0.10)", zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(180,200,230,0.10)", zeroline=False),
    )
    return fig


def create_charts(df: pd.DataFrame, metric: str, category: str | None, date: str | None, aggregate: str, secondary: str | None):
    """Build three readable charts, selecting sensible alternatives for missing fields."""
    figures: list[tuple[str, object]] = []
    agg_func = "sum" if aggregate == "Sum" else "mean"

    if date is not None and "_date" in df.columns:
        dated = df.dropna(subset=["_date"])
        if not dated.empty:
            monthly = dated.assign(Month=dated["_date"].dt.to_period("M").dt.to_timestamp())
            monthly = monthly.groupby("Month", as_index=False)["_metric"].agg(agg_func)
            fig = px.line(monthly, x="Month", y="_metric", markers=True, title=f"Monthly {aggregate.lower()} · {metric}")
            fig.update_traces(line=dict(color=BLUE, width=3), marker=dict(size=7, color=PURPLE),
                              hovertemplate="%{x|%b %Y}<br>%{y:,.2f}<extra></extra>")
            fig.update_xaxes(title_text=None)
            fig.update_yaxes(title_text=metric)
            figures.append(("trend", style_chart(fig, 365)))

    if category is not None and "_category" in df.columns:
        grouped = df.groupby("_category", as_index=False)["_metric"].agg(agg_func)
        grouped = grouped.sort_values("_metric", ascending=False).head(8)
        if not grouped.empty:
            fig = px.bar(grouped, x="_metric", y="_category", orientation="h",
                         title=f"Top categories · {aggregate.lower()} of {metric}",
                         color="_metric", color_continuous_scale=["#5175E9", "#8D7CF8", "#52BDF6"])
            fig.update_layout(coloraxis_showscale=False)
            fig.update_yaxes(title_text=None, categoryorder="total ascending")
            fig.update_xaxes(title_text=metric)
            fig.update_traces(hovertemplate="%{y}<br>%{x:,.2f}<extra></extra>")
            figures.append(("categories", style_chart(fig)))

    fig = px.histogram(df, x="_metric", nbins=18, title=f"Value distribution · {metric}", color_discrete_sequence=[TEAL])
    fig.update_xaxes(title_text=metric)
    fig.update_yaxes(title_text="Rows")
    fig.update_traces(hovertemplate="Value: %{x}<br>Rows: %{y}<extra></extra>")
    figures.append(("distribution", style_chart(fig)))

    if len(figures) < 3:
        if secondary is not None and secondary in df.columns and secondary != metric:
            plot_df = df.copy()
            plot_df["_secondary"] = pd.to_numeric(plot_df[secondary], errors="coerce")
            plot_df = plot_df.dropna(subset=["_secondary"])
            if not plot_df.empty:
                fig = px.scatter(plot_df, x="_secondary", y="_metric", title=f"Relationship · {secondary} vs {metric}",
                                 color_discrete_sequence=[PURPLE], opacity=0.72)
                fig.update_xaxes(title_text=secondary)
                fig.update_yaxes(title_text=metric)
                figures.append(("relationship", style_chart(fig)))
        if len(figures) < 3:
            fig = px.box(df, y="_metric", title=f"Spread & outliers · {metric}", points="outliers",
                         color_discrete_sequence=[PURPLE])
            fig.update_xaxes(title_text=None)
            fig.update_yaxes(title_text=metric)
            figures.append(("spread", style_chart(fig)))

    if len(figures) < 3:
        biggest = df.nlargest(8, "_metric").copy()
        biggest["Record"] = [f"Row {int(i) + 2}" for i in biggest.index]
        fig = px.bar(biggest, x="_metric", y="Record", orientation="h",
                     title=f"Largest observations · {metric}", color_discrete_sequence=[BLUE])
        fig.update_yaxes(title_text=None, categoryorder="total ascending")
        fig.update_xaxes(title_text=metric)
        figures.append(("largest", style_chart(fig)))

    return figures[:3]


def as_excel_bytes(df: pd.DataFrame) -> bytes:
    """Export only source columns, not internal helper columns."""
    generated = {"_metric", "_category", "_date", "_secondary"}
    clean = df.loc[:, [c for c in df.columns if c not in generated]]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        clean.to_excel(writer, index=False, sheet_name="Filtered data")
    return output.getvalue()


def as_html_report(figures, stats, filename: str, metric: str, selected_rows: int) -> bytes:
    """A standalone, offline Plotly report. Dynamic text is HTML-escaped."""
    plots = []
    for idx, (_, fig) in enumerate(figures):
        plots.append(pio.to_html(fig, full_html=False, include_plotlyjs=True if idx == 0 else False,
                                 config={"displaylogo": False, "responsive": True}))
    cards = (
        ("Total", f"{stats['total']:,.2f}"), ("Average", f"{stats['average']:,.2f}"),
        ("Rows", f"{stats['rows']:,}"), ("Max", f"{stats['max']:,.2f}")
    )
    cards_html = "".join(f'<section class="card"><small>{escape(label)}</small><strong>{value}</strong></section>'
                         for label, value in cards)
    plots_html = "".join(f'<section class="chart">{html}</section>' for html in plots)
    doc = f'''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Excel Insight | Report</title><style>
body{{background:#0B1220;color:#EAF1FF;font:15px Arial,sans-serif;margin:0}}
main{{max-width:1250px;margin:auto;padding:32px 22px}}
h1{{font-size:33px;letter-spacing:-.5px;margin:0 0 8px}}
p{{color:#A2B0C4;margin:0 0 28px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:20px 0 22px}}
.card,.chart{{background:#131F31;border:1px solid #233148;border-radius:16px;padding:20px}}
.card small{{display:block;color:#A2B0C4;margin-bottom:12px}}.card strong{{font-size:25px}}
.chart{{margin-bottom:16px;padding:6px}}footer{{font-size:12px;color:#8494AA;margin-top:24px}}
</style></head><body><main><h1>Excel Insight</h1>
<p>Offline interactive report · Source: {escape(filename)} · Metric: {escape(metric)} · {selected_rows:,} valid rows</p>
<div class="cards">{cards_html}</div>{plots_html}
<footer>Generated by Excel Insight Dashboard · No external chart service needed.</footer></main></body></html>'''
    return doc.encode("utf-8")
