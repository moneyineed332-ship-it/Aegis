"""Debug: check full SMC analysis output."""
from app import storage
from app.smc_ict import analyze

for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
    candles = storage.list_ohlcv_candles(sym, "1h", limit=200)
    if candles:
        r = analyze(candles)
        print(f"{sym}:")
        print(f"  signal={r['signal']}")
        print(f"  score={r['score']}")
        print(f"  market_structure={r['market_structure']}")
        print(f"  entry_zone={r['entry_zone']}")
        print(f"  reasons={r['reasons'][:3]}")
        print()