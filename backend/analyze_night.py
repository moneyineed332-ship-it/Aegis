"""Analyze overnight engine data from the AEGIS database."""
import sqlite3
import json
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "aegis.db"
db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

# --- Paper Orders ---
section("PAPER ORDERS (all 11)")
rows = db.execute("SELECT * FROM paper_orders ORDER BY created_at").fetchall()
for r in rows:
    fee = r['fee'] if r['fee'] else 0
    print(f"  {r['created_at'][:19]}")
    print(f"    {r['side']:4} {r['quantity']} {r['symbol']} @ ${r['reference_price']:,.2f}")
    print(f"    status={r['status']} | strategy={r['strategy']} | notional=${r['notional']:.0f} | fee=${fee:.2f}")
    if r['reason']:
        print(f"    reason: {r['reason'][:120]}")
    print()

# --- Positions ---
section("CURRENT POSITIONS")
rows = db.execute("SELECT * FROM positions").fetchall()
if not rows:
    print("  (none)")
for r in rows:
    print(f"  {r['symbol']}: qty={r['quantity']} avg_price=${r['average_price']:,.2f}")

# --- Decision Journal ---
section("DECISION JOURNAL (6 entries)")
rows = db.execute("SELECT * FROM decision_journal ORDER BY created_at").fetchall()
for r in rows:
    d = json.loads(r['decision_json'])
    print(f"  {r['created_at'][:19]} | {r['symbol']} {r['interval']}")
    rec = d.get('recommendation', {})
    if isinstance(rec, dict):
        print(f"    action={rec.get('action','?')} confidence={rec.get('confidence','?')}")
        reason = rec.get('reason', '?')
        print(f"    reason={str(reason)[:150]}")
    risk = d.get('risk', {})
    if risk:
        print(f"    risk: {json.dumps(risk)[:120]}")
    print()

# --- Market Snapshots ---
section("MARKET SNAPSHOTS (48 total, showing last 12)")
rows = db.execute("SELECT * FROM market_snapshots ORDER BY collected_at DESC LIMIT 12").fetchall()
for r in rows:
    print(f"  {r['collected_at'][:19]} | {r['symbol']:10} = ${r['price']:>10,.2f} (source={r['source']})")

# --- Fear & Greed ---
section("FEAR & GREED INDEX (7 readings)")
rows = db.execute("SELECT * FROM fear_greed ORDER BY collected_at").fetchall()
for r in rows:
    print(f"  {r['collected_at'][:19]} | value={r['value']:>3} ({r['classification']}) source={r['source']}")

# --- Funding Rates ---
section("FUNDING RATES (7 readings)")
rows = db.execute("SELECT * FROM funding_rates ORDER BY collected_at").fetchall()
for r in rows:
    print(f"  {r['collected_at'][:19]} | {r['symbol']:10} rate={r['funding_rate']} mark=${r['mark_price']:,.2f}")

# --- Open Interest ---
section("OPEN INTEREST (6 readings)")
rows = db.execute("SELECT * FROM open_interest ORDER BY collected_at").fetchall()
for r in rows:
    oi_usd = r['open_interest_usd'] if r['open_interest_usd'] else 'N/A'
    print(f"  {r['collected_at'][:19]} | {r['symbol']:10} oi={r['open_interest']} oi_usd={oi_usd}")

# --- Memory Episodes ---
section("MEMORY EPISODES (learning, 6 entries)")
rows = db.execute("SELECT * FROM memory_episodes ORDER BY created_at").fetchall()
for r in rows:
    print(f"  {r['created_at'][:19]} | {r['symbol']} strategy={r['strategy']} fp={r['fingerprint'][:20]}")
    res = json.loads(r['result_json']) if r['result_json'] else {}
    print(f"    result: {json.dumps(res)[:150]}")
    print()

# --- Backtests ---
section("BACKTESTS (52 total, showing last 10)")
rows = db.execute("SELECT * FROM backtests ORDER BY created_at DESC LIMIT 10").fetchall()
for r in rows:
    m = json.loads(r['metrics_json'])
    oos = m.get('out_of_sample_metrics', m)
    ret = oos.get('total_return', '?')
    sharpe = oos.get('sharpe_ratio', '?')
    dd = oos.get('max_drawdown', '?')
    trades = oos.get('trade_count', '?')
    print(f"  {r['created_at'][:19]} | {r['strategy']:20} {r['symbol']:10} ret={ret} sharpe={sharpe} dd={dd} trades={trades}")

# --- Engine Log ---
section("ENGINE LOG")
cnt = db.execute("SELECT COUNT(*) as c FROM engine_log").fetchone()['c']
print(f"  Total entries: {cnt}")
if cnt > 0:
    rows = db.execute("SELECT * FROM engine_log ORDER BY created_at DESC LIMIT 30").fetchall()
    for r in rows:
        details = r['details_json'][:120] if r['details_json'] else ''
        print(f"  {r['created_at'][:19]} | [{r['severity']:7}] {r['event_type']:25} cycle={r['cycle_id'][:12]}")
        if details:
            print(f"    details: {details}")

# --- Trade Signals ---
section("TRADE SIGNALS")
cnt = db.execute("SELECT COUNT(*) as c FROM trade_signals").fetchone()['c']
print(f"  Total signals: {cnt}")
if cnt > 0:
    rows = db.execute("SELECT * FROM trade_signals ORDER BY created_at DESC LIMIT 20").fetchall()
    for r in rows:
        sig = json.loads(r['signal_json'])
        print(f"  {r['created_at'][:19]} | {r['symbol']} {r['strategy']} type={r['signal_type']} exec={r['executed']}")
        print(f"    {json.dumps(sig)[:180]}")
        print()

# --- Trade Outcomes ---
section("TRADE OUTCOMES")
cnt = db.execute("SELECT COUNT(*) as c FROM trade_outcomes").fetchone()['c']
print(f"  Total outcomes: {cnt}")
if cnt > 0:
    rows = db.execute("SELECT * FROM trade_outcomes ORDER BY opened_at").fetchall()
    for r in rows:
        print(f"  {r['opened_at'][:19]} | {r['side']} {r['quantity']} {r['symbol']} @ ${r['entry_price']:,.2f}")
        print(f"    status={r['status']} pnl={r['pnl']} pnl_pct={r['pnl_pct']} dur={r['duration_seconds']}s")
        print(f"    regime={r['regime_at_entry']} strategy={r['strategy']}")
        print()

# --- Strategy Stats ---
section("STRATEGY STATS")
cnt = db.execute("SELECT COUNT(*) as c FROM strategy_stats").fetchone()['c']
print(f"  Total: {cnt}")
if cnt > 0:
    rows = db.execute("SELECT * FROM strategy_stats").fetchall()
    for r in rows:
        stats = json.loads(r['stats_json'])
        print(f"  {r['strategy_id']}: {json.dumps(stats)[:200]}")

# --- OHLCV candles ---
section("OHLCV CANDLES SUMMARY")
rows = db.execute("SELECT symbol, interval, COUNT(*) as cnt, MIN(open_time) as first, MAX(open_time) as last FROM ohlcv_candles GROUP BY symbol, interval ORDER BY symbol, interval").fetchall()
for r in rows:
    first = str(r['first'])[:19] if r['first'] else '?'
    last = str(r['last'])[:19] if r['last'] else '?'
    print(f"  {r['symbol']:10} {r['interval']:4}: {r['cnt']:5} candles | first={first} last={last}")

# --- Engine State ---
section("ENGINE STATE")
rows = db.execute("SELECT * FROM engine_state").fetchall()
if not rows:
    print("  (empty - engine never started)")
else:
    for r in rows:
        print(f"  {r['name']}: {r['value']} (updated: {r['updated_at'][:19]})")

# --- Trailing Stops ---
section("TRAILING STOPS")
cnt = db.execute("SELECT COUNT(*) as c FROM trailing_stops_active").fetchone()['c']
print(f"  Active: {cnt}")

# --- Open Orders ---
section("OPEN ORDERS (pending)")
cnt = db.execute("SELECT COUNT(*) as c FROM open_orders").fetchone()['c']
print(f"  Pending: {cnt}")

# --- System Alerts ---
section("SYSTEM ALERTS")
cnt = db.execute("SELECT COUNT(*) as c FROM system_alerts").fetchone()['c']
print(f"  Total: {cnt}")

db.close()
