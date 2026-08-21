"""Free API data routes."""

from fastapi import APIRouter

from .. import free_apis

router = APIRouter(prefix="/api/v1/free", tags=["free-apis"])


@router.get("/coingecko/global")
def get_coingecko_global() -> dict:
    return free_apis.coingecko_global()


@router.get("/coingecko/trending")
def get_coingecko_trending() -> list[dict]:
    return free_apis.coingecko_trending()


@router.get("/coingecko/gainers")
def get_coingecko_gainers() -> list[dict]:
    return free_apis.coingecko_top_gainers()


@router.get("/coingecko/losers")
def get_coingecko_losers() -> list[dict]:
    return free_apis.coingecko_top_losers()


@router.get("/defillama/tvl")
def get_defillama_tvl() -> dict:
    return free_apis.defillama_tvl()


@router.get("/defillama/yields")
def get_defillama_yields() -> list[dict]:
    return free_apis.defillama_yields()


@router.get("/defillama/chains")
def get_defillama_chains() -> list[dict]:
    return free_apis.defillama_chains()


@router.get("/defillama/protocols")
def get_defillama_protocols() -> list[dict]:
    return free_apis.defillama_top_protocols()


@router.get("/perpfinder/funding")
def get_perpfinder_funding() -> list[dict]:
    return free_apis.perpfinder_funding_rates()


@router.get("/perpfinder/liquidations")
def get_perpfinder_liquidations() -> list[dict]:
    return free_apis.perpfinder_liquidations()


@router.get("/perpfinder/open-interest")
def get_perpfinder_oi() -> list[dict]:
    return free_apis.perpfinder_open_interest()


@router.get("/mempool/fees")
def get_mempool_fees() -> dict:
    return free_apis.mempool_fees()


@router.get("/polymarket/crypto")
def get_polymarket_crypto() -> list[dict]:
    return free_apis.polymarket_crypto_markets()


@router.get("/dexscreener/trending")
def get_dexscreener_trending() -> list[dict]:
    return free_apis.dexscreener_trending()


@router.get("/fear-greed/historical")
def get_fear_greed_historical(limit: int = 30) -> list[dict]:
    return free_apis.fear_greed_historical(limit)


@router.get("/blockstream")
def get_blockstream() -> dict:
    return free_apis.blockstream_info()


@router.get("/finnhub/quote")
def get_finnhub_quote(symbol: str = "AAPL") -> dict:
    return free_apis.finnhub_stock_quote(symbol)


@router.get("/finnhub/candle")
def get_finnhub_candle(symbol: str = "AAPL", resolution: str = "D", days_back: int = 30) -> list[dict]:
    return free_apis.finnhub_stock_ohlcv(symbol, resolution, days_back)


@router.get("/finnhub/news")
def get_finnhub_news(category: str = "general") -> list[dict]:
    return free_apis.finnhub_general_news(category)


@router.get("/finnhub/company-news")
def get_finnhub_company_news(symbol: str = "AAPL", days_back: int = 7) -> list[dict]:
    return free_apis.finnhub_company_news(symbol, days_back)


@router.get("/finnhub/earnings")
def get_finnhub_earnings(symbol: str = "AAPL", limit: int = 8) -> list[dict]:
    return free_apis.finnhub_earnings(symbol, limit)


@router.get("/finnhub/insider")
def get_finnhub_insider(symbol: str = "AAPL", days_back: int = 30) -> dict:
    return free_apis.finnhub_insider_sentiment(symbol, days_back)


@router.get("/finnhub/recommendations")
def get_finnhub_recommendations(symbol: str = "AAPL") -> list[dict]:
    return free_apis.finnhub_recommendations(symbol)


@router.get("/finnhub/forex")
def get_finnhub_forex(base: str = "USD") -> dict:
    return free_apis.finnhub_forex_rates(base)


@router.get("/all")
def get_free_all_data() -> dict:
    return {
        "coingecko_global": free_apis.coingecko_global(),
        "coingecko_trending": free_apis.coingecko_trending(),
        "fear_greed": free_apis.fear_greed_historical(),
    }
