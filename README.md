# real-exchange-rate-app

A Streamlit application for an International Finance course.

## Project

This app compares nominal and real exchange rates using
monthly data retrieved from the International Monetary Fund
(IMF) SDMX 3.0 API.

Users can select Country 1 and Country 2, including the
Euro area (IMF code G163), and choose a sample period.

## Economic methodology

Let:

- S(t) = units of Country 2 currency per unit of
  Country 1 currency
- P1(t) = Country 1 consumer price index
- P2(t) = Country 2 consumer price index

The real exchange rate is:

RER(t) = S(t) * P1(t) / P2(t)

The benchmark is the arithmetic mean of all valid RER
observations in the selected sample:

RER* = average RER(t)

The normalized real exchange rate is:

Real Index(t) = 100 * RER(t) / RER*

The real index averages 100 over the selected period.

The nominal exchange rate S(t) is shown in actual
currency units and is not normalized.

## IMF data sources

API: https://api.imf.org/external/sdmx/3.0

CPI dataflow: IMF.STA / CPI
Series: {ISO3}.CPI._T.IX.M

Exchange rate dataflow: IMF.STA / ER
Series: {ISO3}.XDC_USD.PA_RT.M

Data are requested from January 1976 onward,
subject to IMF availability.

The IMF exchange rate is local currency per USD.
The app converts it to the requested direction:

S(t) = FX2_local_per_USD / FX1_local_per_USD

For example, with the UK as Country 1 and
the US as Country 2, S is USD per GBP.

## Features

- Country 1 and Country 2 selection
- Monthly IMF CPI and exchange rate data
- Adjustable sample start and end months
- Automatic recalculation of the RER benchmark
- Real, Nominal, and Both chart options
- Separate axes for both exchange rate measures
- CSV download with input data and calculations
- Warnings for unavailable or incomplete IMF data

## Run on Streamlit Community Cloud

1. Save app.py, requirements.txt, and README.md
   in the root of a public GitHub repository.
2. Visit https://share.streamlit.io.
3. Sign in with GitHub.
4. Create a new app using the repository.
5. Set the main file path to app.py.
6. Select Python 3.12.
7. Deploy.

## Validation

Recommended test:

- Country 1: United Kingdom (GBR)
- Country 2: United States (USA)
- Check that S is USD per GBP.
- Change sample dates and check that the
  exported Real_Index averages 100.
- Verify one row manually using the CPI
  and FX columns in the CSV file.
- Test Real, Nominal, and Both views.

## Limitations

IMF data availability differs across countries.
Missing observations are not interpolated.
IMF API outages and changes may affect downloads.
The index represents sample-relative real valuation,
not a guaranteed future exchange rate forecast.

## LLM assistance

Generated with ChatGPT (GPT-6), October 22, 2026.
The prompt, model, date, deployment link, and manual
verification will be included in the assignment submission.
