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

## 3. Optimiser and lab evaluate in-sample

`optimizer.py` and `lab.py` report the best result over the data they were
measured on. Treat their output as a hypothesis, not a validated edge. This has
not been re-verified since the initial audit.

## 4. Position modes B, C and D are unreachable

`fixed_tp` (mode A) is what runs. The partial, breakeven and
trailing-structural modes exist in `position_manager.py` but nothing selects
them, and the take-profit picks the furthest available liquidity level rather
than the nearest. Not re-verified since the initial audit.

## 5. Not re-verified since the initial audit

Items carried forward without being re-checked in the recent work. They are
listed so they are not mistaken for covered ground: optimiser/lab (3), ICT modes
and TP selection (4), Prometheus path cardinality.

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
| Dev server cannot reach production | `api.ts` dev guard |
