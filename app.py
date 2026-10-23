
import io

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pycountry
import requests
import streamlit as st
from plotly.subplots import make_subplots


# ============================================================
# THE DEVIL WEARS FOREX
# Real & Nominal Exchange Rate Explorer
# International Finance Project
# ============================================================

BASE_URL = "https://api.imf.org/external/sdmx/3.0"
START_PERIOD = "1976-01"

BLACK = "#0D0D10"
PANEL = "#19171C"
PINK = "#F4B7D2"
SILVER = "#E7E3E7"
MUTED = "#B9B4BB"
BORDER = "#353039"


# ------------------------------------------------------------
# PAGE CONFIGURATION
# ------------------------------------------------------------

st.set_page_config(
    page_title="The Devil Wears Forex",
    page_icon="🩷",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ------------------------------------------------------------
# BLACK SATIN & BABY PINK DESIGN
# ------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Main background */
    .stApp {
        background-color: #0D0D10;
        color: #F9F6F8;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #171519;
        border-right: 1px solid #353039;
    }

    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p {
        color: #E7E3E7 !important;
    }

    /* Headings */
    h1, h2, h3 {
        color: #F4B7D2 !important;
        letter-spacing: -0.4px;
    }

    h1 {
        font-weight: 650 !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #19171C;
        border: 1px solid #353039;
        padding: 20px;
        border-radius: 16px;
    }

    [data-testid="stMetricLabel"] {
        color: #B9B4BB;
    }

    [data-testid="stMetricValue"] {
        color: #F4B7D2;
        font-weight: 600;
    }

    /* Closed select boxes */
    div[data-baseweb="select"] > div {
        background-color: #242027 !important;
        border: 1px solid #51414C !important;
        color: #FFFFFF !important;
    }

    div[data-baseweb="select"] input,
    div[data-baseweb="select"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Dropdown menu container */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    ul[role="listbox"] {
        background-color: #242027 !important;
        color: #FFFFFF !important;
    }

    /* Dropdown items */
    li[role="option"],
    div[role="option"] {
        background-color: #242027 !important;
        color: #FFFFFF !important;
    }

    li[role="option"] *,
    div[role="option"] * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    /* Hover and selected item */
    li[role="option"]:hover,
    li[aria-selected="true"],
    div[role="option"]:hover,
    div[role="option"][aria-selected="true"] {
        background-color: #493542 !important;
        color: #FFFFFF !important;
    }

    /* Streamlit popover option rows */
    [data-baseweb="menu"] {
        background-color: #242027 !important;
    }

    [data-baseweb="menu"] li {
        color: #FFFFFF !important;
    }

    [data-baseweb="menu"] li:hover {
        background-color: #493542 !important;
    }

    /* CSV download button */
    div.stDownloadButton > button {
        background-color: #F4B7D2 !important;
        color: #171017 !important;
        border: 1px solid #F4B7D2 !important;
        border-radius: 12px;
        padding: 0.65rem 1.5rem;
        font-weight: 700;
    }

    div.stDownloadButton > button:hover {
        background-color: #FFD5E6 !important;
        border-color: #FFD5E6 !important;
        color: #171017 !important;
    }

    /* Data table */
    [data-testid="stDataFrame"] {
        border: 1px solid #353039;
        border-radius: 12px;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid #353039;
        border-radius: 12px;
        background-color: #19171C;
    }

    /* Header label */
    .app-eyebrow {
        font-size: 0.75rem;
        letter-spacing: 2px;
        color: #F4B7D2;
        font-weight: 700;
        margin-bottom: 10px;
    }

    /* Subtitle */
    .app-subtitle {
        color: #B9B4BB;
        font-size: 1.05rem;
        margin-top: -8px;
        margin-bottom: 25px;
    }

    /* Information boxes */
    .section-note {
        background-color: #19171C;
        border-left: 3px solid #F4B7D2;
        border-radius: 8px;
        padding: 14px 18px;
        color: #E7E3E7;
        margin: 12px 0 24px 0;
    }

    /* Footer */
    .app-footer {
        text-align: center;
        color: #9F99A2;
        font-size: 0.85rem;
        padding-top: 30px;
        padding-bottom: 10px;
    }

    hr {
        border-color: #353039;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# HEADER
# ------------------------------------------------------------

st.markdown(
    '<div class="app-eyebrow">'
    'INTERNATIONAL FINANCE / CURRENCY ANALYTICS'
    '</div>',
    unsafe_allow_html=True,
)

st.title("The Devil Wears Forex.")

st.markdown(
    '<div class="app-subtitle">'
    'Real & Nominal Exchange Rate Explorer'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-note">'
    'Explore global currencies using monthly IMF data. '
    'Compare nominal exchange rates with real exchange '
    'rates adjusted for relative consumer prices.'
    '</div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# COUNTRY SELECTION
# ------------------------------------------------------------

COUNTRIES = {
    f"{country.name} ({country.alpha_3})": country.alpha_3
    for country in pycountry.countries
}

COUNTRIES["Euro area (G163)"] = "G163"
COUNTRIES = dict(sorted(COUNTRIES.items()))

COUNTRY_LABELS = list(COUNTRIES.keys())


# ------------------------------------------------------------
# IMF DATA DOWNLOAD
# ------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_imf_series(country_code, series_type):
    """
    Download monthly IMF CPI or exchange-rate data.

    CPI:
        COUNTRY.CPI._T.IX.M

    Exchange rate:
        COUNTRY.XDC_USD.PA_RT.M

    IMF exchange rates are local currency per USD.
    """

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

    required = {"TIME_PERIOD", "OBS_VALUE"}

    if not required.issubset(data.columns):
        raise ValueError(
            "Unexpected IMF response format. "
            f"Columns: {list(data.columns)}"
        )

    # Filter returned data dimensions.

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

    # Convert monthly IMF dates.

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

    data = data[
        ["month", "value"]
    ].dropna()

    data = data.loc[
        data["value"] > 0
    ]

    # Only use observations from January 1976 onward.

    data = data.loc[
        data["month"] >= pd.Timestamp("1976-01-01")
    ]

    # Remove exact duplicate observations.

    data = data.drop_duplicates(
        subset=["month", "value"]
    )

    # Report conflicting values instead of averaging them.

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


# ------------------------------------------------------------
# REAL EXCHANGE RATE CALCULATIONS
# ------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def build_dataset(code1, code2):
    """
    S = units of Country 2 currency
        per one unit of Country 1 currency.

    IMF FX:
        x1 = Currency 1 per USD
        x2 = Currency 2 per USD

    S = x2 / x1
    RER = S * CPI1 / CPI2
    """

    if code1 == code2:
        raise ValueError(
            "Please select two different countries."
        )

    p1 = get_imf_series(code1, "CPI").rename("CPI1")
    p2 = get_imf_series(code2, "CPI").rename("CPI2")

    # One USD always equals one USD.

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

    # Nominal exchange rate in the required direction.

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

    # Final date restriction.

    df = df.loc[
        df.index >= pd.Timestamp("1976-01-01")
    ]

    return df.sort_index()


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------

st.sidebar.markdown("## The Currency Desk")

st.sidebar.caption(
    "Select countries, sample dates, and chart type."
)

default1 = next(
    label for label in COUNTRY_LABELS
    if COUNTRIES[label] == "GBR"
)

default2 = next(
    label for label in COUNTRY_LABELS
    if COUNTRIES[label] == "USA"
)

country1 = st.sidebar.selectbox(
    "Country 1",
    COUNTRY_LABELS,
    index=COUNTRY_LABELS.index(default1),
)

country2 = st.sidebar.selectbox(
    "Country 2",
    COUNTRY_LABELS,
    index=COUNTRY_LABELS.index(default2),
)

st.sidebar.markdown("---")

chart_option = st.sidebar.radio(
    "Chart View",
    ["Real", "Nominal", "Both"],
    index=2,
)

code1 = COUNTRIES[country1]
code2 = COUNTRIES[country2]

if code1 == code2:
    st.warning(
        "Please choose two different countries."
    )
    st.stop()


# ------------------------------------------------------------
# LOAD IMF DATA
# ------------------------------------------------------------

with st.spinner("Fetching IMF data..."):
    try:
        full_data = build_dataset(code1, code2)

    except Exception as error:
        st.error(
            "The selected IMF data could not be loaded."
        )

        st.code(str(error))

        st.warning(
            "The IMF data may be temporarily unavailable, "
            "have incomplete coverage, or contain conflicting "
            "observations."
        )

        st.stop()

if full_data.empty:
    st.error(
        "No complete monthly observations found."
    )
    st.stop()


# ------------------------------------------------------------
# SAMPLE PERIOD
# ------------------------------------------------------------

available_months = [
    month.strftime("%Y-%m")
    for month in full_data.index
]

st.sidebar.subheader("Sample Period")

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
    st.error(
        "No valid months in the selected period."
    )
    st.stop()


# ------------------------------------------------------------
# BENCHMARK AND INDEX
# ------------------------------------------------------------

# Recalculate RER benchmark whenever dates change.

rer_star = selected["RER"].mean()

if not np.isfinite(rer_star) or rer_star <= 0:
    st.error("Invalid RER benchmark.")
    st.stop()

selected["Real_Index"] = (
    100.0 * selected["RER"] / rer_star
)


# ------------------------------------------------------------
# RESULTS
# ------------------------------------------------------------

st.subheader("Exchange Rate Comparison")

st.markdown(
    f"**Country 1:** {country1}  \n"
    f"**Country 2:** {country2}"
)

st.caption(
    "S is expressed as units of Country 2 currency "
    "per one unit of Country 1 currency."
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Valid Months",
    len(selected),
)

col2.metric(
    "Average RER",
    f"{rer_star:.5f}",
)

col3.metric(
    "Average Real Index",
    f"{selected['Real_Index'].mean():.5f}",
)


# ------------------------------------------------------------
# CHART
# ------------------------------------------------------------

st.subheader("Exchange Rate Trends")

fig = make_subplots(
    specs=[[{"secondary_y": True}]]
)

# Pink line = real exchange rate.

if chart_option in ("Real", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["Real_Index"],
            name="Real Exchange Rate Index",
            mode="lines",
            line=dict(
                color=PINK,
                width=2.8,
            ),
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "Real Index: %{y:.2f}"
                "<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="#777078",
        line_width=1,
    )

# Silver-white line = nominal exchange rate.

if chart_option in ("Nominal", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["S"],
            name="Nominal Exchange Rate",
            mode="lines",
            line=dict(
                color=SILVER,
                width=2.4,
            ),
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "Nominal S: %{y:.4f}"
                "<extra></extra>"
            ),
        ),
        secondary_y=(chart_option == "Both"),
    )

fig.update_layout(
    title=dict(
        text="Real & Nominal Exchange Rates",
        font=dict(
            size=19,
            color="#F9F6F8",
        ),
    ),
    xaxis_title="Month",
    template="plotly_dark",
    paper_bgcolor=BLACK,
    plot_bgcolor=PANEL,
    font=dict(
        color=SILVER,
    ),
    hovermode="x unified",
    height=540,
    margin=dict(
        l=50,
        r=50,
        t=70,
        b=65,
    ),
    legend=dict(
        orientation="h",
        y=-0.18,
        x=0,
    ),
)

fig.update_xaxes(
    gridcolor=BORDER,
    showline=True,
    linecolor="#514850",
)

fig.update_yaxes(
    gridcolor=BORDER,
    showline=True,
    linecolor="#514850",
)

if chart_option == "Both":
    fig.update_yaxes(
        title_text="Real Index (Average = 100)",
        secondary_y=False,
    )

    fig.update_yaxes(
        title_text="Currency 2 per Currency 1",
        secondary_y=True,
        showgrid=False,
    )

elif chart_option == "Real":
    fig.update_yaxes(
        title_text="Real Index (Average = 100)",
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

st.caption(
    "The real exchange rate index is normalized "
    "to an average of 100 over the selected period. "
    "The nominal exchange rate is shown in actual "
    "currency units."
)


# ------------------------------------------------------------
# METHODOLOGY
# ------------------------------------------------------------

st.markdown("---")
st.subheader("Behind the Numbers")

st.write(
    "The real exchange rate adjusts the nominal "
    "exchange rate for relative consumer price levels."
)

st.latex(
    r"RER_t = S_t \times \frac{P_{1,t}}{P_{2,t}}"
)

st.latex(
    r"RER^* = \frac{1}{N}\sum_{t=1}^{N}RER_t"
)

st.latex(
    r"RealIndex_t = 100 \times \frac{RER_t}{RER^*}"
)

st.markdown(
    '<div class="section-note">'
    'A real index above 100 indicates an RER above '
    'the selected-sample average. A value below '
    '100 indicates an RER below that average.'
    '</div>',
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# TABLE AND CSV EXPORT
# ------------------------------------------------------------

st.subheader("The Data")

st.write(
    "Monthly observations and calculations "
    "for the selected sample period."
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

csv_data = export.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="Download Data as CSV",
    data=csv_data,
    file_name=f"rer_{code1}_{code2}.csv",
    mime="text/csv",
)

st.caption(
    "The downloaded CSV contains all valid "
    "observations and calculations within "
    "the selected period."
)


# ------------------------------------------------------------
# DATA SOURCES AND LIMITATIONS
# ------------------------------------------------------------

with st.expander("Data Sources & Methodology"):
    st.write(
        "Source: International Monetary Fund (IMF), "
        "SDMX 3.0 API."
    )

    st.write(
        "CPI series: COUNTRY.CPI._T.IX.M"
    )

    st.write(
        "Exchange rate series: "
        "COUNTRY.XDC_USD.PA_RT.M"
    )

    st.write(
        "Monthly data are requested from "
        "January 1976, where available."
    )

    st.write(
        "IMF exchange rates are quoted in local "
        "currency units per U.S. dollar. "
        "The app converts them to units of "
        "Country 2 currency per unit of "
        "Country 1 currency."
    )

    st.write(
        "Months with missing or invalid inputs "
        "are excluded without interpolation."
    )

    st.write(
        "The RER benchmark changes automatically "
        "when the sample dates change."
    )

    st.write(
        "The real index is based on the selected "
        "sample average and does not independently "
        "establish fundamental fair value."
    )


# ------------------------------------------------------------
# SIMPLE FOOTER
# ------------------------------------------------------------

st.markdown(
    '<div class="app-footer">'
    'International Finance · IMF Data'
    '</div>',
    unsafe_allow_html=True,
)
