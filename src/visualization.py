"""
Visualization Module for DataChat
====================================

LEARNING NOTES:
--------------
The Conversational Analytics API can return chart specifications
in Vega-Lite format. Vega-Lite is a high-level visualization grammar
that describes charts as JSON objects.

Altair is the Python library that implements Vega-Lite. Streamlit has
native support for Altair charts via st.altair_chart().

RENDERING PIPELINE:
1. API returns a chart spec (Vega-Lite JSON) in the response
2. We parse the JSON into a Python dictionary
3. We create an Altair chart from the spec
4. Streamlit renders it natively

SUPPORTED CHART TYPES (by the API):
- Fully supported: Line, area, bar (all variants), scatter, pie
- Partially supported: Maps, heatmaps, tooltips

WHY ALTAIR?
- It's Google's recommended library for rendering CA API chart specs
- Streamlit has native st.altair_chart() support
- It's built on Vega-Lite (same spec the API produces)
- Beautiful defaults, responsive, interactive
"""

import logging
from typing import Optional

import altair as alt
import pandas as pd

logger = logging.getLogger(__name__)


def render_chart_from_spec(chart_spec: dict) -> Optional[alt.Chart]:
    """
    Create an Altair chart from a Vega-Lite specification.

    LEARNING NOTE:
    alt.Chart.from_dict() can directly consume a Vega-Lite JSON spec.
    This is the bridge between the API's output and Streamlit's rendering.

    IMPORTANT FIX:
    The Conversational Analytics API returns Vega-Lite v5 specs, but
    Streamlit's Vega renderer uses v6. Some spec features are incompatible:
    - `transform` with `window`/`sort` creates derived fields that fail
    - Empty `sort: {}` objects in encoding cause issues
    We clean these before rendering to ensure compatibility.

    Args:
        chart_spec: Vega-Lite specification dictionary

    Returns:
        Altair chart object, or None if parsing fails
    """
    try:
        if not chart_spec:
            return None

        # Validate: ensure some form of data is present
        data = chart_spec.get("data", {})
        if isinstance(data, dict):
            has_data = (
                data.get("values")
                or data.get("name")
                or data.get("url")
                or "datasets" in chart_spec
            )
            if not has_data:
                logger.warning("Chart spec has no data source — skipping")
                return None

        # Clean spec for Vega-Lite v5 → v6 compatibility
        spec = _clean_vega_spec(chart_spec)

        chart = alt.Chart.from_dict(spec)
        logger.info("Chart rendered from Vega-Lite spec")
        return chart

    except Exception as e:
        logger.warning(f"Failed to render chart from spec: {e}")
        return None


def _clean_vega_spec(spec: dict) -> dict:
    """
    Clean a Vega-Lite spec for compatibility with Streamlit's renderer.

    The Conversational Analytics API produces v5 specs, but Streamlit
    uses Vega-Lite v6. This function resolves known incompatibilities:
    1. Window transforms that fail in v6
    2. Empty sort objects
    3. Unix timestamps in seconds (Vega expects milliseconds)
    """
    import copy
    spec = copy.deepcopy(spec)

    # Remove transform with window functions (causes "Infinite extent" errors)
    # The data.values already contains the processed/sorted data
    if "transform" in spec:
        transforms = spec["transform"]
        has_window = any(
            "window" in t or "sort" in t
            for t in transforms
            if isinstance(t, dict)
        )
        if has_window:
            del spec["transform"]
            logger.info("Removed incompatible window transform from chart spec")

    # Clean empty sort objects in encoding (causes rendering issues)
    encoding = spec.get("encoding", {})
    for axis_key in ("x", "y", "color", "theta"):
        axis = encoding.get(axis_key, {})
        if isinstance(axis, dict) and "sort" in axis:
            if axis["sort"] == {} or axis["sort"] is None:
                del axis["sort"]

    # Fix temporal data: API returns Unix timestamps in SECONDS,
    # but Vega-Lite expects MILLISECONDS for temporal fields
    _fix_temporal_data(spec)

    # Ensure schema points to a compatible version
    if "$schema" in spec:
        spec["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"

    return spec


def _fix_temporal_data(spec: dict) -> None:
    """
    Fix Unix timestamps in chart data from seconds to milliseconds.

    The Conversational Analytics API returns timestamps as Unix epoch
    in SECONDS (e.g., 1561939200 = July 1, 2019), but Vega-Lite expects
    temporal values in MILLISECONDS (e.g., 1561939200000).

    We detect temporal fields from the encoding and multiply by 1000.
    """
    encoding = spec.get("encoding", {})
    data = spec.get("data", {})
    values = data.get("values", [])

    if not values:
        return

    # Find temporal field names from encoding
    temporal_fields = []
    for axis_key in ("x", "y", "color"):
        axis = encoding.get(axis_key, {})
        if isinstance(axis, dict) and axis.get("type") == "temporal":
            field = axis.get("field")
            if field:
                temporal_fields.append(field)

    if not temporal_fields:
        return

    # Check if values look like Unix seconds (roughly 1e9 to 2e9 range)
    for field in temporal_fields:
        sample_vals = [
            row.get(field) for row in values[:5]
            if isinstance(row, dict) and isinstance(row.get(field), (int, float))
        ]
        if sample_vals and all(1e8 < v < 3e9 for v in sample_vals):
            # Convert seconds to milliseconds
            for row in values:
                if isinstance(row, dict) and isinstance(row.get(field), (int, float)):
                    row[field] = row[field] * 1000
            logger.info(f"Converted temporal field '{field}' from seconds to milliseconds")


def create_chart_from_data(
    data: dict,
    chart_type: str = "auto",
    x_column: Optional[str] = None,
    y_column: Optional[str] = None,
    title: str = "",
) -> Optional[alt.Chart]:
    """
    Create an Altair chart from parsed data when no chart spec is available.

    LEARNING NOTE:
    Sometimes the API returns data without a chart spec (especially
    for simple queries). This function creates a reasonable chart
    automatically based on the data shape and types.

    This is a FALLBACK — the API's native chart specs are preferred
    because they're optimized for the specific question asked.
    """
    try:
        df = data_to_dataframe(data)
        if df is None or df.empty:
            return None

        # Auto-detect chart type if not specified
        if chart_type == "auto":
            chart_type = _detect_best_chart_type(df, x_column, y_column)

        # Auto-detect x and y columns if not specified
        if x_column is None or y_column is None:
            x_column, y_column = _auto_select_columns(df)

        if x_column is None or y_column is None:
            return None

        # Apply Google-inspired styling
        base = alt.Chart(df).properties(
            title=title,
            width="container",
            height=400,
        )

        if chart_type == "bar":
            chart = base.mark_bar(color="#4285F4").encode(
                x=alt.X(x_column, sort="-y"),
                y=alt.Y(y_column),
                tooltip=[x_column, y_column],
            )
        elif chart_type == "line":
            chart = base.mark_line(color="#4285F4", point=True).encode(
                x=alt.X(x_column),
                y=alt.Y(y_column),
                tooltip=[x_column, y_column],
            )
        elif chart_type == "pie":
            chart = base.mark_arc().encode(
                theta=alt.Theta(y_column, type="quantitative"),
                color=alt.Color(x_column, type="nominal"),
                tooltip=[x_column, y_column],
            )
        elif chart_type == "scatter":
            chart = base.mark_circle(color="#4285F4", size=60).encode(
                x=alt.X(x_column),
                y=alt.Y(y_column),
                tooltip=[x_column, y_column],
            )
        else:  # Default to bar
            chart = base.mark_bar(color="#4285F4").encode(
                x=alt.X(x_column),
                y=alt.Y(y_column),
                tooltip=[x_column, y_column],
            )

        return chart.interactive()

    except Exception as e:
        logger.warning(f"Failed to create chart from data: {e}")
        return None


def data_to_dataframe(data: dict) -> Optional[pd.DataFrame]:
    """
    Convert API data result to a pandas DataFrame.

    LEARNING NOTE:
    The API returns data in a simple format:
    {"columns": ["col1", "col2"], "rows": [[val1, val2], ...]}

    We convert this to a DataFrame for:
    1. Easy display with st.dataframe()
    2. Chart creation with Altair
    3. CSV download functionality
    """
    try:
        if not data:
            return None

        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if not columns and not rows:
            return None

        if columns:
            df = pd.DataFrame(rows, columns=columns)
        else:
            df = pd.DataFrame(rows)

        # Try to convert numeric columns
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass

        # Convert Unix timestamp columns to human-readable dates
        # The API often returns date/month columns as Unix epoch seconds
        # (e.g., 1704067200 = Jan 1, 2024). We detect and convert these.
        df = _convert_timestamp_columns(df)

        return df

    except Exception as e:
        logger.warning(f"Failed to convert data to DataFrame: {e}")
        return None


def _convert_timestamp_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect columns containing Unix timestamps and convert to readable dates.

    LEARNING NOTE:
    The Conversational Analytics API returns date columns as Unix epoch
    seconds (e.g., 1704067200 = Jan 1, 2024). These are meaningless to
    users in a data table. We detect them using:
    1. Column name hints (date, month, year, time, created, updated)
    2. Value range check (Unix seconds are roughly 1e9 to 2e9 for 2001-2033)

    We format them as readable dates for display while keeping the
    original values available for charting.
    """
    date_hints = ("date", "month", "year", "time", "created", "updated", "day", "week", "quarter")

    for col in df.columns:
        col_lower = str(col).lower()
        # Check if column name suggests a date/time field
        if not any(hint in col_lower for hint in date_hints):
            continue

        # Check if values look like Unix timestamps in seconds
        if df[col].dtype not in ("int64", "float64", "int32", "float32"):
            continue

        sample = df[col].dropna().head(5)
        if sample.empty:
            continue

        if sample.apply(lambda v: 1e9 < v < 3e9).all():
            try:
                # Convert Unix seconds to datetime
                df[col] = pd.to_datetime(df[col], unit="s").dt.strftime("%b %Y")
                logger.info(f"Converted timestamp column '{col}' to readable dates")
            except Exception as e:
                logger.warning(f"Failed to convert column '{col}': {e}")

    return df


def _detect_best_chart_type(
    df: pd.DataFrame,
    x_column: Optional[str] = None,
    y_column: Optional[str] = None,
) -> str:
    """
    Auto-detect the best chart type based on data characteristics.

    LEARNING NOTE:
    This mirrors the logic the Conversational Analytics API uses
    to select chart types based on question keywords:
    - Trend/change → line chart
    - Compare/variance → bar chart
    - Distribution/proportion → pie chart
    - Correlation → scatter plot
    """
    num_rows = len(df)
    num_cols = len(df.columns)

    # If only 2 columns and few rows → bar chart
    if num_cols == 2 and num_rows <= 20:
        return "bar"

    # If date-like column exists → line chart
    for col in df.columns:
        if df[col].dtype == "datetime64[ns]" or "date" in col.lower() or "month" in col.lower():
            return "line"

    # If many categories → bar chart
    if num_rows <= 10:
        return "bar"

    # Default
    return "bar"


def _auto_select_columns(
    df: pd.DataFrame,
) -> tuple[Optional[str], Optional[str]]:
    """
    Auto-select x and y columns from a DataFrame.
    x = first non-numeric column (category/label)
    y = first numeric column (metric/value)
    """
    x_col = None
    y_col = None

    for col in df.columns:
        if df[col].dtype in ["object", "string", "category"] and x_col is None:
            x_col = col
        elif df[col].dtype in ["int64", "float64", "int32", "float32"] and y_col is None:
            y_col = col

    # Fallback: use first two columns
    if x_col is None and len(df.columns) >= 2:
        x_col = df.columns[0]
    if y_col is None and len(df.columns) >= 2:
        y_col = df.columns[1] if df.columns[1] != x_col else df.columns[0]

    return x_col, y_col
