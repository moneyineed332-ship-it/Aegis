# Known limitations

What this bot does **not** protect against. Read this before running it with
money, and re-check it whenever a module below changes.

This file exists because the system has a habit of reporting checks it does not
perform. An earlier `AUDIT_REPORT.md` concluded "AUDIT RESULT: PASSED"; several
of the items below were live at the time. A green field on a screen should mean
"this check ran and passed", not "nothing was asked".

## Scope

One strategy engine: ICT/SMC Forex on EURUSD, GBPUSD and XAUUSD, fed by
MetaTrader5 with a Yahoo Finance fallback for hosts where MT5 cannot run. The
crypto engine is gone. Intended deployment is a **single** machine (see 2).

Two things about that target are not built yet and are the reason this file
still matters:

- **MT5 is Windows-only and requires an open terminal.** The `MetaTrader5`
  Python package has no Linux build, so the execution path cannot run on Fly.
  The bot must run on a Windows host, always on.
- **There is no order execution at all.** `mt5_connector.py` is read-only:
  `fetch_ohlcv`, `fetch_tick`, `get_symbol_info`, no `order_send` anywhere in the
  repository. `position_manager.open_position()` logs "Position opened" and
  returns a `PositionUpdate`; it simulates. `get_live_exchange()` now raises
  deliberately, so any request for live execution stops at that boundary with a
  message rather than finding a stray venue. Until the MT5 adapter exists, every
  order goes through the paper path in `oms.py`.

---

## 1. No economic-news protection

**Status: accepted. There is no news source, and the gate cannot block a trade.**

Two independent reasons:

- `refresh_news_calendar()` has no caller, so the calendar is never populated.
- The only producer is `_generate_mock_calendar()`, and `is_trading_blocked()`
  skips events with `source == "mock"` on purpose, so approximate dates cannot
  stop real trading. That design choice is correct and is kept.

Consequence: **the risk around high-impact news is unmanaged.** A release
minutes before a high-impact event can move through a stop loss.

The decision is to accept this rather than wire a source. Finnhub's economic
calendar is a paid add-on, and connecting an unverified external feed to a risk
gate is worse than a known gap. The simulated calendar was deliberately **not**
wired in: it would not arm the gate and would look as though it had.

What you get instead of protection:

- `GET /api/ict/dashboard/news-status` reports `news_filter_armed: false` and why.
- `IctRiskManager` logs one WARNING per process.
- `RiskStatus.not_evaluated` and `scope` separate "not blocked" from
  "not protected".

The numbers make this small in absolute terms: risk per trade is 0.5 % of equity,
0.25 EUR on 50 EUR. The exposure is a gap in the intended *process*, not a
plausible route to a large loss.

**To remove this limitation**: implement a real calendar source, and
`NewsFilter.is_armed()` will start reporting `True` on its own. No call site has
to change.

## 2. Single-instance state

Engine state lives in SQLite. With more than one machine, each keeps its own
in-memory copy and they overwrite each other. Deploy a single machine, or move
the engine state behind a shared store.

This is now a deployment constraint rather than a preference. MT5 is Windows-only
(see Scope), the bot has to stay up, and scaling out would need the state moved
first. A Windows VPS is the shape that fits: one machine, one terminal, one
account.

## 3. Sharpe figures need their scale read alongside them

`optimizer.py` now scores the grid on a training window, carries the single
top-ranked candidate across an embargo to a held-out window, and reports what
happened there (`verdict`, `out_of_sample_metrics`, `sharpe_drift`).

The annualised Sharpe was briefly suspected of being itself a defect: a 15m
series multiplies by 187 and a 1h series by 94, so values cluster near -50 and
looked like noise. That suspicion was wrong and has been retracted. Every
candidate in a run shares one `interval`, so `sqrt(ppy)` is a constant
multiplier and cancels out of the ranking. Over a 28-set grid the top five came
out in the same order annualised and per-period, and the same strategy on the
same candles gives an identical per-period Sharpe of `-0.22637` at both 15m and
1h, with the annual figures differing by exactly the ratio of the square roots.
The promotion thresholds in `lab.py` compare annual to annual, so nothing
needed rescaling and the ranking is unchanged.

What the extreme magnitudes did cause was unreadable output. A bare `-41.70`
gives no hint that it is an annual figure, so results now carry
`sharpe_per_period`, `annualisation_factor` and `sharpe_interval`. Two caveats
remain worth reading:

- The annualisation assumes independent, identically distributed per-period
  returns. With a few dozen trades that assumption does not hold and the annual
  figure drifts upward. It is left as the reported value because it is the
  consistent scale across intervals.
- The extreme magnitudes are not a measurement artefact. They say the tested
  strategies have no edge after costs: per-period Sharpe around `-0.22`, which
  annualises to the `-40` range on 15m. The held-out degradation found
  earlier (Sharpe `11.19` in training to `3.53` out of sample, a fall of 68 %)
  is selection variance, which the out-of-sample protocol addresses, not a
  scaling problem.

Until a strategy clears those thresholds, `verdict: held_up` should be read as
"not refuted" rather than "demonstrated".

## 4. No strategy currently qualifies on out-of-sample evidence

The paper-candidate gate in `lab.py` used to read
`metrics.get("out_of_sample_metrics", metrics)`, so a run with no held-out
portion was judged on the data its own parameters were picked from. It is now
fixed: only out-of-sample metrics are read, and a run without them is refused
as "no evidence" rather than silently substituted.

On the 52 stored backtests that had already inverted the result:

    eligible on real out-of-sample evidence        0
    eligible ONLY through the in-sample fallback    7

The gate was promoting exactly the runs with no evidence behind them, and
refusing every walk-forward run that did have a held-out portion. After the fix
it promotes nothing, because nothing in the store clears the thresholds out of
sample. That is the real state of the research, and it is unchanged by the fix:
no strategy has demonstrated a paper-worthy edge.

## 5. Unauthenticated memory growth in the metrics registry

**Accepted risk, not fixed.** The previous text here was wrong about why, so the
correction matters more than the item.

`metrics_middleware` in `main.py` labels `request.url.path` for every request
whose path starts with `/api/`, including requests that match no route. The
registry behind it is a plain dict in `app/metrics.py` with no cap and no
eviction, so **each distinct path is permanent**:

- 1 series for `http_requests_total`, multiplied by `status` (200, 401, 404,
  422, 429 each get their own)
- 14 series for `http_request_duration_seconds`: 11 buckets, `+Inf`, `_count`
  and `_sum`

That is roughly 1-2 KB per distinct path, and `render()` walks the whole
registry on every scrape.

The earlier version of this note blamed the 10 second scrape interval, and that
was wrong. The interval has nothing to do with it: scraping every 10 s costs the
same as scraping every 60 s. What costs is serialising a registry that has
grown, which is a function of its size, not of how often it is read.

**Why it is not urgent.** The application does not invent paths. Its roughly
175 routes are fixed, so absent anyone deliberately feeding it, the registry is
bounded at a few MB and stays there. Trading is not affected either way.

**What accepting it means.** Fly hands out publicly reachable `*.fly.dev`
hostnames, and any request to `/api/<anything>` returns a cheap 404 **with no
token check**, while permanently adding a label set. Growth is therefore an
unauthenticated, unbounded memory increase, with a restart as the only remedy
once under way. The failure is gradual: rising RSS, then slower `/metrics`
scrapes, then an OOM kill from Fly. It is not a trading fault, and nothing about
it is exercised by the test suite today.

**Revisit if** process RSS climbs without plateauing, if `/metrics` scrape
latency rises, if the machine is OOM-killed, or when moving beyond a single
instance, where each machine holds its own registry and both the memory and the
serialisation cost multiply.

**Cheapest mitigations, neither applied.** Resolving each path to its route
template before labelling would drop the label set to about 175 entries, at the
cost of ignoring genuinely unmatched requests. A hard cap on distinct paths,
above which new ones are not labelled, bounds the growth in half a dozen lines
and keeps scraping healthy without changing what the existing routes report.

## 6. The legacy Donchian branch is still in the engine

`config.FOCUSED_MODE` defaults to true and selects a Donchian path in
`engine.py` that belongs to the removed crypto engine. It is not inert:

- `smc_ict.analyze()` is skipped on that branch, and `engine.py:480` gates the
  whole ICT pipeline on `_last_smc_analysis` being non-empty. So a run with
  `FOCUSED_MODE=true` and `ICT_MODE=false` never reaches
  `_init_ict_pipeline()`. The production `fly.toml` sets `ICT_MODE=true` and
  `FOCUSED_MODE=false`, which is why this has not bitten yet.
- Its default symbol list is now the ICT instruments, because the previous
  default was `PAXGUSDT,BTCUSDT,ETHUSDT` and `fetch_ohlcv` now refuses those,
  so any default-config run raised `ValueError` inside the analysis task.

It should be deleted rather than left as a trap. It was not done here because
`engine.py` is the most load-bearing file in the repository and the removal wants
the ICT pipeline tests read first.

---

## What *is* covered

For contrast, the protections that were found broken during audit and now hold,
each with a test pinning it:

| Area | Enforced by |
|---|---|
| No order without a risk manager | `engine._execute_ict_trade` refuses |
| No position on unmanaged risk | `IctRiskManager.check_all_limits` |
| Notional caps derived from capital | `config._resolve_notional_caps` |
| Liveness probe never rate-limited | `rate_limit.LIVENESS_LIMIT` |
| Event loop not starved by the engine | `scheduler` lock + `asyncio.to_thread` |
| State never crosses modes or symbols | `engine._MODE_SCOPED_STATE_KEYS`, `regime._HYSTERESIS` |
| Market closures are not data corruption | `data_quality._is_expected_closure` |
| Every instrument can actually trade | `IctRiskManager._init_default_limits` clamp |
| Admin token never in a URL | `deps.issue_ws_ticket` |
| Financial reads require the token | `test_route_auth_inventory` |
| No paper candidate without held-out evidence | `lab.promotion_decision` |
| Optimiser candidates measured out of sample | `optimizer._search` |
| Tasks run on the first tick after a restart | `scheduler._loop` |
| Sharpe reported with the scale it was computed on | `optimizer._sharpe_scale` |
| API docs and schema not served publicly | `config.EXPOSE_API_DOCS` |
| Take-profit at the nearest liquidity pool | `ict_signal_generator._nearest_liquidity_target` |
| Modes B, C and D selectable | `ict_dashboard.set_position_mode` |
| `can_trade` reflects a real check | `IctRiskManager.check_account_limits` |
| Dev server cannot reach production | `api.ts` dev guard |
| A non-Forex symbol cannot reach a data source | `market_data.fetch_ohlcv` raises |
| Live execution cannot silently find a venue | `exchange.get_live_exchange` raises |
| Tests do not depend on the trading calendar | `tests/conftest.py` pins the session clock |
