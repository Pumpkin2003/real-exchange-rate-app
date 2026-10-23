
import io
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pycountry
import requests
import streamlit as st
from plotly.subplots import make_subplots

# ------------------------------------------------------------
# International Finance: Real Exchange Rate App
# IMF SDMX 3.0 data, monthly observations from January 1976
# ------------------------------------------------------------

BASE_URL = "https://api.imf.org/external/sdmx/3.0"
START_PERIOD = "1976-01"

st.set_page_config(
    page_title="Real Exchange Rate Explorer",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 Real Exchange Rate Explorer")
st.write(
    "Compare nominal and real exchange rates using monthly "
    "IMF consumer price and exchange rate data."
)

st.info(
    "Real Index = 100 × RER / average RER over the selected period. "
    "The nominal exchange rate is never normalized."
)

# Create a country menu using ISO3 codes, plus the IMF Euro area.
COUNTRIES = {
    f"{country.name} ({country.alpha_3})": country.alpha_3
    for country in pycountry.countries
}
COUNTRIES["Euro area (G163)"] = "G163"
COUNTRIES = dict(sorted(COUNTRIES.items()))

COUNTRY_LABELS = list(COUNTRIES.keys())


@st.cache_data(ttl=3600, show_spinner=False)
def get_imf_series(country_code, series_type):
    """
    Retrieve monthly observations from the IMF SDMX 3.0 API.

    CPI key: COUNTRY.CPI._T.IX.M
    ER key:  COUNTRY.XDC_USD.PA_RT.M

    ER values are local-currency units per USD.
    """
    if series_type == "CPI":
        dataflow = "CPI"
        key = f"{country_code}.CPI._T.IX.M"
    elif series_type == "ER":
        # One U.S. dollar always equals one U.S. dollar.
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

    params = {"startPeriod": START_PERIOD}
    headers = {
        "Accept": "text/csv",
        "User-Agent": "RER-Streamlit-Student-App/1.0",
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=45,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"IMF API request failed for {country_code} "
            f"({series_type}): {exc}"
        ) from exc

    if not response.content:
        raise ValueError(
            f"No {series_type} observations were returned "
            f"for {country_code}."
        )

    try:
        data = pd.read_csv(io.StringIO(response.text))
    except Exception as exc:
        raise ValueError(
            f"The IMF response for {country_code} "
            f"({series_type}) could not be read as CSV. "
            f"Response begins: {response.text[:200]}"
        ) from exc

    data.columns = [str(col).strip() for col in data.columns]

    required = {"TIME_PERIOD", "OBS_VALUE"}
    if not required.issubset(data.columns):
        raise ValueError(
            f"Unexpected IMF response columns for "
            f"{country_code} ({series_type}): "
            f"{list(data.columns)}. "
            "The IMF may have changed its data format."
        )

    # Select only the exact requested series where
    # the response contains these dimension columns.
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
            data = data[
                data[column].astype(str).str.strip() == expected
            ]

    if data.empty:
        raise ValueError(
            f"No matching monthly {series_type} "
            f"observations for {country_code}."
        )

    # Monthly timestamps and numeric observations.
    data["month"] = pd.to_datetime(
        data["TIME_PERIOD"].astype(str).str[:7] + "-01",
        errors="coerce",
    )
    data["value"] = pd.to_numeric(
        data["OBS_VALUE"], errors="coerce"
    )

    data = data[["month", "value"]].dropna()
    data = data[data["value"] > 0]

    # Duplicate monthly observations should not be
    # averaged or invented. Keep only unambiguous dates.
    if data["month"].duplicated().any():
        raise ValueError(
            f"IMF returned duplicate observations for "
            f"{country_code} ({series_type}). "
            "Please check the series selection."
        )

    data = data.sort_values("month").set_index("month")
    data.index.name = "Month"

    if data.empty:
        raise ValueError(
            f"No usable observations for "
            f"{country_code} ({series_type})."
        )

    return data["value"]


@st.cache_data(ttl=3600, show_spinner=False)
def build_dataset(code1, code2):
    if code1 == code2:
        raise ValueError("Please select two different countries.")

    p1 = get_imf_series(code1, "CPI").rename("CPI1")
    p2 = get_imf_series(code2, "CPI").rename("CPI2")

    # IMF quotation:
    # x1 = currency 1 units per USD
    # x2 = currency 2 units per USD
    #
    # Therefore S = x2 / x1:
    # currency 2 units per one unit of currency 1.

    # For the U.S., USD per USD is 1.
    x1 = (
        pd.Series(1.0, index=p1.index)
        if code1 == "USA"
        else get_imf_series(code1, "ER")
    )
    x2 = (
        pd.Series(1.0, index=p2.index)
        if code2 == "USA"
        else get_imf_series(code2, "ER")
    )

    if code1 == "USA":
        x1 = x1.rename("FX1_local_per_USD")
    else:
        x1 = x1.rename("FX1_local_per_USD")

    x2 = x2.rename("FX2_local_per_USD")

    # Join only months available in all required series.
    result = pd.concat([p1, p2, x1, x2], axis=1)
    result = result.dropna().sort_index()

    if result.empty:
        raise ValueError(
            "No months have complete CPI and exchange "
            "rate data for both selected countries."
        )

    result = result[
        (result["CPI1"] > 0)
        & (result["CPI2"] > 0)
        & (result["FX1_local_per_USD"] > 0)
        & (result["FX2_local_per_USD"] > 0)
    ].copy()

    result["S"] = (
        result["FX2_local_per_USD"]
        / result["FX1_local_per_USD"]
    )
    result["RER"] = (
        result["S"] * result["CPI1"] / result["CPI2"]
    )

    result = result.replace(
        [np.inf, -np.inf], np.nan
    ).dropna()

    return result


st.sidebar.header("Settings")

default1 = next(
    label for label, code in COUNTRIES.items()
    if code == "GBR"
)
default2 = next(
    label for label, code in COUNTRIES.items()
    if code == "USA"
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

chart_option = st.sidebar.radio(
    "Chart view",
    ["Real", "Nominal", "Both"],
    index=2,
)

code1 = COUNTRIES[country1]
code2 = COUNTRIES[country2]

if code1 == code2:
    st.warning("Choose two different countries.")
    st.stop()

with st.spinner("Downloading monthly IMF data..."):
    try:
        full_data = build_dataset(code1, code2)
    except Exception as error:
        st.error("The selected IMF data could not be loaded.")
        st.code(str(error))
        st.warning(
            "This may be due to unavailable series, a "
            "temporary IMF server error, or an API format "
            "change. Try another country pair or retry later."
        )
        st.stop()

available_months = [
    timestamp.strftime("%Y-%m")
    for timestamp in full_data.index
]

if not available_months:
    st.error("No common monthly data are available.")
    st.stop()

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
    st.error("The start month must not exceed the end month.")
    st.stop()

selected = full_data.loc[
    (full_data.index >= pd.Timestamp(start_month))
    & (full_data.index <= pd.Timestamp(end_month))
].copy()

if selected.empty:
    st.error("No complete observations in this period.")
    st.stop()

# Crucial: recompute the benchmark after EVERY
# sample period change.
rer_star = selected["RER"].mean()

if not np.isfinite(rer_star) or rer_star <= 0:
    st.error("The RER benchmark cannot be calculated.")
    st.stop()

selected["Real_Index"] = (
    100.0 * selected["RER"] / rer_star
)

st.subheader("Exchange rate comparison")

st.write(
    f"**Country 1:** {country1}  \n"
    f"**Country 2:** {country2}"
)
st.caption(
    "S is expressed as units of Country 2 currency "
    "per one unit of Country 1 currency."
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Valid months", len(selected))
metric2.metric("Average RER (RER*)", f"{rer_star:.5f}")
metric3.metric(
    "Average Real Index",
    f"{selected['Real_Index'].mean():.5f}",
)

fig = make_subplots(specs=[[{"secondary_y": True}]])

if chart_option in ("Real", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["Real_Index"],
            name="Real exchange rate index",
            mode="lines",
            line=dict(color="#1763B6", width=2),
        ),
        secondary_y=False,
    )
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="gray",
        annotation_text="Sample mean = 100",
    )

if chart_option in ("Nominal", "Both"):
    fig.add_trace(
        go.Scatter(
            x=selected.index,
            y=selected["S"],
            name="Nominal exchange rate S",
            mode="lines",
            line=dict(color="#E67E22", width=2),
        ),
        secondary_y=(
            chart_option == "Both"
        ),
    )

fig.update_layout(
    title="Real and Nominal Exchange Rates",
    xaxis_title="Month",
    template="plotly_white",
    height=520,
    legend=dict(orientation="h", y=-0.2),
    hovermode="x unified",
)

if chart_option == "Nominal":
    fig.update_yaxes(
        title_text="Currency 2 per Currency 1",
        secondary_y=False,
    )
elif chart_option == "Real":
    fig.update_yaxes(
        title_text="Real index (sample average = 100)",
        secondary_y=False,
    )
else:
    fig.update_yaxes(
        title_text="Real index (sample average = 100)",
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Currency 2 per Currency 1",
        secondary_y=True,
    )

st.plotly_chart(fig, use_container_width=True)

st.subheader("Data and calculations")

st.latex(
    r"RER_t = S_t \times \frac{P_{1,t}}{P_{2,t}}"
)
st.latex(
    r"RER^* = \frac{1}{N}\sum_{t=1}^{N}RER_t"
)
st.latex(
    r"RealIndex_t = 100 \times \frac{RER_t}{RER^*}"
)

st.write(
    "The benchmark RER* is calculated from all valid "
    "months within the selected sample period. "
    "Missing observations are excluded rather than filled."
)

export = selected.reset_index()
export["Month"] = export["Month"].dt.strftime("%Y-%m")
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

csv_data = export.to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download selected data as CSV",
    data=csv_data,
    file_name=f"rer_{code1}_{code2}.csv",
    mime="text/csv",
)

st.caption(
    "Source: International Monetary Fund (IMF), "
    "SDMX 3.0 API, CPI and Exchange Rates (ER). "
    "Monthly data are requested starting January 1976 "
    "where available. Coverage depends on the country "
    "and the IMF data series."
)

with st.expander("Methodology and limitations"):
    st.write(
        "CPI series: COUNTRY.CPI._T.IX.M. "
        "Exchange rate series: "
        "COUNTRY.XDC_USD.PA_RT.M."
    )
    st.write(
        "The IMF exchange rate is quoted in local "
        "currency units per USD. To construct S, "
        "we divide Country 2's local-currency-per-USD "
        "rate by Country 1's local-currency-per-USD rate."
    )
    st.write(
        "CPI values must be positive. Months without "
        "complete observations are excluded. "
        "Country coverage and euro-area data may "
        "start later than January 1976."
    )
    st.write(
        "The real index is relative to the selected "
        "sample mean, not an independent PPP fair-value "
        "estimate. CPI base conventions and data "
        "availability may affect cross-country levels."
    )
