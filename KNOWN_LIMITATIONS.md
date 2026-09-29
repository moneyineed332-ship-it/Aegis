# Known limitations

What this bot does **not** protect against. Read this before running it with
money, and re-check it whenever a module below changes.

This file exists because the system has a habit of reporting checks it does not
perform. An earlier `AUDIT_REPORT.md` concluded "AUDIT RESULT: PASSED"; several
of the items below were live at the time. A green field on a screen should mean
"this check ran and passed", not "nothing was asked".

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

Engine state lives in SQLite on a Fly volume. With more than one machine, each
keeps its own in-memory copy and they overwrite each other. Deploy a single
machine, or move the engine state behind a shared store.

## 3. The Sharpe scale makes the ranking weak

`optimizer.py` now scores the grid on a training window, carries the single
top-ranked candidate across an embargo to a held-out window, and reports what
happened there (`verdict`, `out_of_sample_metrics`, `sharpe_drift`).

The protocol is not the weak part. The score is: every candidate is ranked by a
Sharpe annualised on a 15m or 1h series, multiplied by 187 and 94
respectively, which is why values cluster near -50. Ranking on that number is
ranking mostly on noise, and the held-out result inherits it.

Measured on 1 988 real EURUSD 15m candles, 28 parameter sets, ranking on two
thirds and reporting the last third:

    best on training   -41.70  ->  -56.24 out-of-sample   (35 % degradation)
    grid median        -54.76  ->  -58.38

The training winner sat barely ahead of a parameter set drawn at random. On a
second series the drift was larger still: Sharpe 11.19 in training, 3.53
held out, a fall of 68 %.

Until the Sharpe scale is settled, treat `verdict: held_up` as "not refuted"
rather than "demonstrated", and do not read the composite ranking as a
performance estimate.

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

## 5. Prometheus path cardinality

`/metrics` exposes raw path labels, so cardinality grows with distinct URLs.
The scrape target is on a 10 second interval, and 10s on a single machine is
affordable, but the label set still needs templating before more instances
exist. Not re-verified since the initial audit.

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
| Take-profit at the nearest liquidity pool | `ict_signal_generator._nearest_liquidity_target` |
| Modes B, C and D selectable | `ict_dashboard.set_position_mode` |
| `can_trade` reflects a real check | `IctRiskManager.check_account_limits` |
| Dev server cannot reach production | `api.ts` dev guard |
