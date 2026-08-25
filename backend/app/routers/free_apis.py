"""Free API data routes."""

import logging

from fastapi import APIRouter, HTTPException

from .. import free_apis

router = APIRouter(prefix="/api/v1/free", tags=["free-apis"])

logger = logging.getLogger(__name__)


@router.get("/coingecko/global")
def get_coingecko_global() -> dict:
    try:
        return free_apis.coingecko_global()
    except Exception as exc:
        logger.warning("coingecko_global failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/coingecko/trending")
def get_coingecko_trending() -> list[dict]:
    try:
        return free_apis.coingecko_trending()
    except Exception as exc:
        logger.warning("coingecko_trending failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/coingecko/gainers")
def get_coingecko_gainers() -> list[dict]:
    try:
        return free_apis.coingecko_top_gainers()
    except Exception as exc:
        logger.warning("coingecko_gainers failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/coingecko/losers")
def get_coingecko_losers() -> list[dict]:
    try:
        return free_apis.coingecko_top_losers()
    except Exception as exc:
        logger.warning("coingecko_losers failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/defillama/tvl")
def get_defillama_tvl() -> dict:
    try:
        return free_apis.defillama_tvl()
    except Exception as exc:
        logger.warning("defillama_tvl failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/defillama/yields")
def get_defillama_yields() -> list[dict]:
    try:
        return free_apis.defillama_yields()
    except Exception as exc:
        logger.warning("defillama_yields failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/defillama/chains")
def get_defillama_chains() -> list[dict]:
    try:
        return free_apis.defillama_chains()
    except Exception as exc:
        logger.warning("defillama_chains failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/defillama/protocols")
def get_defillama_protocols() -> list[dict]:
    try:
        return free_apis.defillama_top_protocols()
    except Exception as exc:
        logger.warning("defillama_protocols failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/perpfinder/funding")
def get_perpfinder_funding() -> list[dict]:
    try:
        return free_apis.perpfinder_funding_rates()
    except Exception as exc:
        logger.warning("perpfinder_funding failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/perpfinder/liquidations")
def get_perpfinder_liquidations() -> list[dict]:
    try:
        return free_apis.perpfinder_liquidations()
    except Exception as exc:
        logger.warning("perpfinder_liquidations failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/perpfinder/open-interest")
def get_perpfinder_oi() -> list[dict]:
    try:
        return free_apis.perpfinder_open_interest()
    except Exception as exc:
        logger.warning("perpfinder_oi failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/mempool/fees")
def get_mempool_fees() -> dict:
    try:
        return free_apis.mempool_fees()
    except Exception as exc:
        logger.warning("mempool_fees failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/polymarket/crypto")
def get_polymarket_crypto() -> list[dict]:
    try:
        return free_apis.polymarket_crypto_markets()
    except Exception as exc:
        logger.warning("polymarket_crypto failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/dexscreener/trending")
def get_dexscreener_trending() -> list[dict]:
    try:
        return free_apis.dexscreener_trending()
    except Exception as exc:
        logger.warning("dexscreener_trending failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/fear-greed/historical")
def get_fear_greed_historical(limit: int = 30) -> list[dict]:
    try:
        return free_apis.fear_greed_historical(limit)
    except Exception as exc:
        logger.warning("fear_greed_historical failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/blockstream")
def get_blockstream() -> dict:
    try:
        return free_apis.blockstream_info()
    except Exception as exc:
        logger.warning("blockstream failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/quote")
def get_finnhub_quote(symbol: str = "AAPL") -> dict:
    try:
        return free_apis.finnhub_stock_quote(symbol)
    except Exception as exc:
        logger.warning("finnhub_quote failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/candle")
def get_finnhub_candle(symbol: str = "AAPL", resolution: str = "D", days_back: int = 30) -> list[dict]:
    try:
        return free_apis.finnhub_stock_ohlcv(symbol, resolution, days_back)
    except Exception as exc:
        logger.warning("finnhub_candle failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/news")
def get_finnhub_news(category: str = "general") -> list[dict]:
    try:
        return free_apis.finnhub_general_news(category)
    except Exception as exc:
        logger.warning("finnhub_news failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/company-news")
def get_finnhub_company_news(symbol: str = "AAPL", days_back: int = 7) -> list[dict]:
    try:
        return free_apis.finnhub_company_news(symbol, days_back)
    except Exception as exc:
        logger.warning("finnhub_company_news failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/earnings")
def get_finnhub_earnings(symbol: str = "AAPL", limit: int = 8) -> list[dict]:
    try:
        return free_apis.finnhub_earnings(symbol, limit)
    except Exception as exc:
        logger.warning("finnhub_earnings failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/insider")
def get_finnhub_insider(symbol: str = "AAPL", days_back: int = 30) -> dict:
    try:
        return free_apis.finnhub_insider_sentiment(symbol, days_back)
    except Exception as exc:
        logger.warning("finnhub_insider failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/recommendations")
def get_finnhub_recommendations(symbol: str = "AAPL") -> list[dict]:
    try:
        return free_apis.finnhub_recommendations(symbol)
    except Exception as exc:
        logger.warning("finnhub_recommendations failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/finnhub/forex")
def get_finnhub_forex(base: str = "USD") -> dict:
    try:
        return free_apis.finnhub_forex_rates(base)
    except Exception as exc:
        logger.warning("finnhub_forex failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")


@router.get("/all")
def get_free_all_data() -> dict:
    try:
        return {
            "coingecko_global": free_apis.coingecko_global(),
            "coingecko_trending": free_apis.coingecko_trending(),
            "fear_greed": free_apis.fear_greed_historical(),
        }
    except Exception as exc:
        logger.warning("get_free_all_data failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream API error: {exc}")
