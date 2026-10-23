
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pycountry
import requests
import streamlit as st
from plotly.subplots import make_subplots

# International Finance - Real Exchange Rate App

BASE_URL = "https://api.imf.org/external/sdmx/3.0"
START_PERIOD = "1976-01"

st.set_page_config(
    page_title="Real Exchange Rate Explorer",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 Real Exchange Rate Explorer")
st.write(
    "Compare nominal and real exchange rates using "
    "monthly IMF CPI and exchange rate data."
)

st.info(
    "Real Index = 100 × RER / average RER. "
    "Nominal exchange rates are shown in actual currency units."
)

COUNTRIES = {
    f"{c.name} ({c.alpha_3})": c.alpha_3
    for c in pycountry.countries
}
COUNTRIES["Euro area (G163)"] = "G163"
COUNTRIES = dict(sorted(COUNTRIES.items()))


@st.cache_data(ttl=3600, show_spinner=False)
def get_imf_series(country_code, series_type):
    """Download one monthly IMF series."""

    if series_type == "CPI":
        dataflow = "CPI"
        key = f"{country_code}.CPI._T.IX.M"
    elif series_type == "ER":
        if country_code == "USA":
            return None
        dataflow = "ER"
        key = f"{country_code}.XDC_USD.PA_RT.M"
    else:
        raise ValueError("Unknown series type.")

    url = (
        f"{BASE_URL}/data/dataflow/IMF.STA/"
        f"{dataflow}/+/{key}"
    )

    try:
        response = requests.get(
            url,
            params={"startPeriod": START_PERIOD},
            headers={"Accept": "text/csv"},
            timeout=45,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not download {series_type} "
            f"for {country_code}: {exc}"
        ) from exc

    try:
        data = pd.read_csv(
            io.StringIO(response.text)
        )
    except Exception as exc:
        raise ValueError(
            f"IMF response could not be parsed: {exc}"
        ) from exc

    data.columns = [
        str(column).strip()
        for column in data.columns
    ]

    if not {"TIME_PERIOD", "OBS_VALUE"}.issubset(data.columns):
        raise ValueError(
            "Unexpected IMF response format. "
            f"Columns: {list(data.columns)}"
        )

    # Filter dimensions when included in the response.
    filters = {
        "COUNTRY": country_code,
        "FREQUENCY": "M",
    }

    if series_type == "CPI":
        filters.update({
            "INDEX_TYPE": "CPI",
            "COICOP_1999": "_T",
            "TYPE_OF_TRANSFORMATION": "IX",
        })
    else:
        filters.update({
            "INDICATOR": "XDC_USD",
            "TYPE_OF_TRANSFORMATION": "PA_RT",
        })

    for column, expected in filters.items():
        if column in data.columns:
            data = data.loc[
                data[column].astype(str).str.strip()
                == expected
            ]

    if data.empty:
        raise ValueError(
            f"No matching {series_type} data "
            f"for {country_code}."
        )

    # Handle both YYYY-MM and YYYY-MMM month formats.
    periods = (
        data["TIME_PERIOD"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"^(\d{4})-M(\d{2})$",
            r"\1-\2",
            regex=True,
        )
    )

    data["month"] = pd.to_datetime(
        periods.str[:7] + "-01",
        errors="coerce",
    )

    data["value"] = pd.to_numeric(
        data["OBS_VALUE"],
        errors="coerce",
    )

    # Restrict the dataset to January 1976 onward.
    data = data.loc[
        data["month"] >= pd.Timestamp("1976-01-01")
    ]
    data = data.loc[data["value"] > 0]

    # Remove only exact duplicates.
    data = data.drop_duplicates(
        subset=["month", "value"]
    )

    # Different values for the same month cannot
    # safely be resolved by averaging.
    conflicts = data.loc[
        data["month"].duplicated(keep=False)
    ]

    if not conflicts.empty:
        example = conflicts.head(6).to_string(index=False)
        raise ValueError(
            f"Conflicting monthly IMF observations "
            f"for {country_code} ({series_type}).\n"
            f"{example}"
        )

    if data.empty:
        raise ValueError(
            f"No usable {series_type} observations "
            f"for {country_code}."
        )

    data = data.sort_values("month")
    data = data.set_index("month")
    data.index.name = "Month"

    return data["value"]


@st.cache_data(ttl=3600, show_spinner=False)
def build_dataset(code1, code2):
    """Combine CPI and currency data by month."""

    if code1 == code2:
        raise ValueError(
            "Choose two different countries."
        )

    p1 = get_imf_series(code1, "CPI").rename("CPI1")
    p2 = get_imf_series(code2, "CPI").rename("CPI2")

    if code1 == "USA":
        x1 = pd.Series(1.0, index=p1.index)
    else:
        x1 = get_imf_series(code1, "ER")

    if code2 == "USA":
        x2 = pd.Series(1.0, index=p2.index)
    else:
        x2 = get_imf_series(code2, "ER")

    x1 = x1.rename("FX1_local_per_USD")
    x2 = x2.rename("FX2_local_per_USD")

    df = pd.concat(
        [p1, p2, x1, x2],
        axis=1,
    ).dropna()

    if df.empty:
        raise ValueError(
            "No common months with complete CPI "
            "and exchange rate data."
        )

    df = df.loc[
        (df["CPI1"] > 0)
        & (df["CPI2"] > 0)
        & (df["FX1_local_per_USD"] > 0)
        & (df["FX2_local_per_USD"] > 0)
    ].copy()

    # Country 2 currency per Country 1 currency.
    df["S"] = (
        df["FX2_local_per_USD"]
        / df["FX1_local_per_USD"]
    )

    # Real exchange rate.
    df["RER"] = (
        df["S"] * df["CPI1"] / df["CPI2"]
    )

    df = df.replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna()

    return df.sort_index()


# Sidebar settings
st.sidebar.header("Settings")

labels = list(COUNTRIES.keys())

default1 = next(
    label for label in labels
    if COUNTRIES[label] == "GBR"
)
default2 = next(
    label for label in labels
    if COUNTRIES[label] == "USA"
)

country1 = st.sidebar.selectbox(
    "Country 1",
    labels,
    index=labels.index(default1),
)

country2 = st.sidebar.selectbox(
    "Country 2",
    labels,
    index=labels.index(default2),
)

chart_option = st.sidebar.radio(
    "Chart view",
    ["Real", "Nominal", "Both"],
    index=2,
)

code1 = COUNTRIES[country1]
code2 = COUNTRIES[country2]

if code1 == code2:
    st.warning("Please choose two different countries.")
    st.stop()

with st.spinner("Downloading monthly IMF data..."):
    try:
        full_data = build_dataset(code1, code2)
    except Exception as error:
        st.error(
            "The selected IMF data could not be loaded."
        )
        st.code(str(error))
        st.warning(
            "The IMF data may be unavailable, contain "
            "conflicting observations, or the API may "
            "have changed. Please check the error above."
        )
        st.stop()

# Restrict all data to January 1976 onward.
full_data = full_data.loc[
    full_data.index >= pd.Timestamp("1976-01-01")
].copy()

if full_data.empty:
    st.error("No complete monthly observations found.")
    st.stop()

available_months = [
    month.strftime("%Y-%m")
    for month in full_data.index
]

st.sidebar.subheader("Sample period")

start_month = st.sidebar.selectbox(
    "Start month",
    available_months,
    index=0,
)

end_month = st.sidebar.selectbox(
    "End month",
    available_months,
    index=len(available_months) - 1,
)

if start_month > end_month:
    st.error(
        "Start month must be before end month."
    )
    st.stop()

selected = full_data.loc[
    (full_data.index >= pd.Timestamp(start_month))
    & (full_data.index <= pd.Timestamp(end_month))
].copy()

if selected.empty:
    st.error("No valid months in selected period.")
    st.stop()

# Recalculate the benchmark with each date change.
rer_star = selected["RER"].mean()

if not np.isfinite(rer_star) or rer_star <= 0:
    st.error("Invalid RER benchmark.")
    st.stop()

selected["Real_Index"] = (
    100 * selected["RER"] / rer_star
)

st.subheader("Exchange Rate Comparison")

st.write(
    f"**Country 1:** {country1}  \n"
    f"**Country 2:** {country2}"
)

st.caption(
    "S = units of Country 2 currency "
    "per one unit of Country 1 currency."
)

col1, col2, col3 = st.columns(3)

col1.metric("Valid months", len(selected))
col2.metric(
    "Average RER",
    f"{rer_star:.5f}",
)
col3.metric(
    "Average Real Index",
    f"{selected['Real_Index'].mean():.5f}",
)

# Interactive chart
fig = make_subplots(
    specs=[[{"secondary_y": True}]]
)

if chart_option in ("Real", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["Real_Index"],
            mode="lines",
            name="Real exchange rate index",
        ),
        secondary_y=False,
    )

    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="gray",
    )

if chart_option in ("Nominal", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["S"],
            mode="lines",
            name="Nominal exchange rate S",
        ),
        secondary_y=(chart_option == "Both"),
    )

fig.update_layout(
    title="Real and Nominal Exchange Rates",
    xaxis_title="Month",
    template="plotly_white",
    hovermode="x unified",
    height=500,
)

if chart_option == "Both":
    fig.update_yaxes(
        title_text="Real index",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Currency 2 per Currency 1",
        secondary_y=True,
    )
elif chart_option == "Real":
    fig.update_yaxes(
        title_text="Real index",
        secondary_y=False,
    )
else:
    fig.update_yaxes(
        title_text="Currency 2 per Currency 1",
        secondary_y=False,
    )

st.plotly_chart(
    fig,
    use_container_width=True,
)

st.subheader("Data and Calculations")

st.latex(
    r"RER_t = S_t \frac{P_{1,t}}{P_{2,t}}"
)

st.latex(
    r"RER^* = \frac{1}{N}\sum_t RER_t"
)

st.latex(
    r"RealIndex_t = 100\frac{RER_t}{RER^*}"
)

st.write(
    "The real index uses the average RER across "
    "valid months in the selected sample period."
)

export = selected.reset_index()

export["Month"] = (
    export["Month"].dt.strftime("%Y-%m")
)
export["RER_benchmark"] = rer_star

export = export[
    [
        "Month",
        "CPI1",
        "CPI2",
        "FX1_local_per_USD",
        "FX2_local_per_USD",
        "S",
        "RER",
        "RER_benchmark",
        "Real_Index",
    ]
]

st.dataframe(
    export,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Download selected data as CSV",
    data=export.to_csv(index=False).encode("utf-8"),
    file_name=f"rer_{code1}_{code2}.csv",
    mime="text/csv",
)

st.caption(
    "Data source: International Monetary Fund (IMF), "
    "SDMX 3.0 API. Monthly CPI and exchange rate data "
    "from January 1976 where available."
)

with st.expander("Methodology and limitations"):
    st.write(
        "CPI series: COUNTRY.CPI._T.IX.M"
    )
    st.write(
        "Exchange rate series: "
        "COUNTRY.XDC_USD.PA_RT.M"
    )
    st.write(
        "The IMF reports exchange rates as local "
        "currency per U.S. dollar. The application "
        "converts these rates to Country 2 currency "
        "per Country 1 currency."
    )
    st.write(
        "Only valid observations are used. Missing "
        "observations are not interpolated."
    )
    st.write(
        "The real index is normalized using the "
        "selected sample average, not an independently "
        "estimated fair-value exchange rate."
    )
