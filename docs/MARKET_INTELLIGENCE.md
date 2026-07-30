# Market Intelligence (M6)

Market data & intelligence under `/api/fin/market`. Instruments, quotes and news
are stored generically (`fin_market_instruments`, `fin_market_quotes`,
`fin_market_news`) with a `source` field so a **live market-data provider can be
plugged in later without schema change**. Defaults are deterministic synthetic
series.

## Endpoints

| Path | Method |
|------|--------|
| `/seed` | seed instruments spanning every asset class + quotes |
| `/instruments` | list / register instruments |
| `/quotes` | latest quote per symbol / record a quote |
| `/yield-curve` | interpolated interest/yield curve with slope & shape |
| `/news` | add / list corporate/industry/macro news |
| `/sentiment` | aggregate news sentiment & mood |
| `/calendar` | economic calendar (synthetic, provider-swappable) |
| `/dashboard` | quotes + curve + sentiment + calendar |

## Asset classes

rate · bond · equity · commodity · fx · credit · volatility. Seed instruments
include the repo rate, G-Secs, Nifty/Sensex, USD/INR, Brent, gold, IG/HY credit
spreads and India VIX.

## Yield curve

Piecewise-linear interpolation over tenor→yield points with flat extrapolation;
reports the 2s10s slope and a normal/flat/inverted shape classification.

## News sentiment & impact

A deterministic lexicon scores each headline/body to a sentiment in [−1, +1];
impact records direction, magnitude and affected entities; a short summary is
produced. `/sentiment` aggregates to a bullish/neutral/bearish mood.

## Provider architecture

Every quote and news row stores its `source`. The synthetic default can be
replaced by a gated live provider (e.g. a market-data API) that writes rows with
`source="<provider>"` — no code path or schema changes needed downstream.
```
