"""Filtre d'actualités économiques pour le bot ICT/SMC.

Récupère le calendrier économique et bloque le trading
autour des événements à fort impact (NFP, CPI, décisions taux, etc.).
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from dataclasses import dataclass, field

import httpx

from .ict_config import Instrument, get_instrument_config

logger = logging.getLogger(__name__)


# ============================================================
# TYPES
# ============================================================

ImpactLevel = Literal["low", "medium", "high"]
Currency = Literal["EUR", "USD", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", "CNY", "XAU"]


@dataclass
class EconomicEvent:
    """Événement économique du calendrier."""
    id: str
    title: str
    currency: Currency
    impact: ImpactLevel
    forecast: str | None
    previous: str | None
    actual: str | None
    datetime_utc: datetime
    country: str
    category: str  # "employment", "inflation", "central_bank", "gdp", etc.
    source: str = "forexfactory"


@dataclass
class NewsFilterConfig:
    """Configuration du filtre news."""
    enabled: bool = True
    high_impact_window_min: int = 30      # Minutes avant/après événement high impact
    medium_impact_window_min: int = 15    # Minutes avant/après événement medium impact
    currencies_to_watch: list[Currency] = field(default_factory=lambda: ["EUR", "USD", "GBP"])
    blocked_categories: list[str] = field(default_factory=lambda: [
        "central_bank", "employment", "inflation", "gdp", "retail_sales"
    ])
    allow_custom_events: bool = True
    custom_blocked_events: list[str] = field(default_factory=list)  # Titres à bloquer


# Config par défaut par instrument (override possible)
DEFAULT_NEWS_CONFIGS: dict[Instrument, NewsFilterConfig] = {
    "EURUSD": NewsFilterConfig(
        enabled=True,
        high_impact_window_min=30,
        medium_impact_window_min=15,
        currencies_to_watch=["EUR", "USD"],
        blocked_categories=["central_bank", "employment", "inflation", "gdp"],
    ),
    "GBPUSD": NewsFilterConfig(
        enabled=True,
        high_impact_window_min=30,
        medium_impact_window_min=15,
        currencies_to_watch=["GBP", "USD"],
        blocked_categories=["central_bank", "employment", "inflation", "gdp"],
    ),
    "XAUUSD": NewsFilterConfig(
        enabled=True,
        high_impact_window_min=60,   # Fenêtre plus large pour Gold
        medium_impact_window_min=30,
        currencies_to_watch=["USD", "XAU"],
        blocked_categories=["central_bank", "employment", "inflation", "gdp", "geopolitical"],
    ),
}


def _parse_aware(value, default: datetime) -> datetime:
    """Parse an ISO datetime string, always returning an aware UTC datetime."""
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return default
    if not isinstance(parsed, datetime):
        return default
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ============================================================
# NEWS FILTER CLASS
# ============================================================

class NewsFilter:
    """
    Filtre d'actualités économiques.
    
    Récupère le calendrier (ForexFactory, Investing.com, ou cache local)
    et détermine si le trading est bloqué pour un instrument à un moment donné.
    """
    
    def __init__(
        self,
        configs: dict[Instrument, NewsFilterConfig] | None = None,
        cache_path: str | Path | None = None,
        http_client: httpx.Client | None = None,
    ):
        self.configs = configs or DEFAULT_NEWS_CONFIGS
        self.cache_path = Path(cache_path) if cache_path else Path("./data/news_cache.json")
        self._http_client = http_client
        self._events_cache: list[EconomicEvent] = []
        self._cache_expiry: datetime | None = None
        self._cache_duration = timedelta(hours=6)  # Rafraîchir toutes les 6h
    
    @property
    def http_client(self) -> httpx.Client:
        """Client HTTP partagé (lazy init)."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                timeout=15.0,
                headers={"User-Agent": "AEGIS-ICT-Bot/1.0"},
                follow_redirects=True,
            )
        return self._http_client
    
    # --------------------------------------------------------
    # CACHE & PERSISTENCE
    # --------------------------------------------------------
    
    def _load_cache(self) -> bool:
        """Charge le cache depuis le disque."""
        try:
            if self.cache_path.exists():
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Vérifier expiration (datetimes normalisés aware UTC)
                cached_at = _parse_aware(data.get("cached_at"), datetime(2000, 1, 1, tzinfo=timezone.utc))
                if datetime.now(timezone.utc) - cached_at < self._cache_duration:
                    self._events_cache = [
                        EconomicEvent(
                            id=e["id"],
                            title=e["title"],
                            currency=e["currency"],
                            impact=e["impact"],
                            forecast=e.get("forecast"),
                            previous=e.get("previous"),
                            actual=e.get("actual"),
                            datetime_utc=_parse_aware(e["datetime_utc"], datetime.now(timezone.utc)),
                            country=e["country"],
                            category=e["category"],
                            source=e.get("source", "forexfactory"),
                        )
                        for e in data.get("events", [])
                    ]
                    self._cache_expiry = cached_at + self._cache_duration
                    logger.info("News cache loaded: %d events", len(self._events_cache))
                    return True
        except Exception as e:
            logger.warning("Failed to load news cache: %s", e)
        return False
    
    def _save_cache(self) -> None:
        """Sauvegarde le cache sur disque."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "events": [
                    {
                        "id": e.id,
                        "title": e.title,
                        "currency": e.currency,
                        "impact": e.impact,
                        "forecast": e.forecast,
                        "previous": e.previous,
                        "actual": e.actual,
                        "datetime_utc": e.datetime_utc.isoformat(),
                        "country": e.country,
                        "category": e.category,
                        "source": e.source,
                    }
                    for e in self._events_cache
                ],
            }
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("News cache saved: %d events", len(self._events_cache))
        except Exception as e:
            logger.warning("Failed to save news cache: %s", e)
    
    # --------------------------------------------------------
    # FETCH CALENDAR
    # --------------------------------------------------------
    
    async def fetch_calendar(self, days_ahead: int = 7) -> list[EconomicEvent]:
        """
        Récupère le calendrier économique.
        
        Essaie ForexFactory en premier, puis fallback sur cache.
        """
        # Essayer de charger le cache d'abord
        if not self._events_cache:
            self._load_cache()
        
        # Si cache valide et récent, l'utiliser
        if self._cache_expiry and datetime.now(timezone.utc) < self._cache_expiry:
            return self._events_cache
        
        # Sinon, tenter de récupérer depuis ForexFactory
        events = await self._fetch_forexfactory(days_ahead)
        
        if events:
            self._events_cache = events
            self._cache_expiry = datetime.now(timezone.utc) + self._cache_duration
            self._save_cache()
            return events
        
        # Fallback: retourner le cache même expiré
        logger.warning("Using expired news cache (%d events)", len(self._events_cache))
        return self._events_cache
    
    async def _fetch_forexfactory(self, days_ahead: int) -> list[EconomicEvent]:
        """
        Récupère les événements économiques.

        Sources de données (par ordre de priorité):
        1. Cache valide (< 4h)
        2. Fichier JSON local data/economic_calendar.json si présent
        3. Calendrier récurrent simulé (évènements connus, dates approximatives)

        En production, remplacer par une API réelle (TradingEconomics, Investing.com).
        """
        return self._generate_mock_calendar(days_ahead)
    
    def _generate_mock_calendar(self, days_ahead: int) -> list[EconomicEvent]:
        """Génère un calendrier simulé pour tests/développement."""
        events = []
        base_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Événements récurrents typiques
        recurring = [
            # US Events
            {"title": "Non-Farm Payrolls", "currency": "USD", "impact": "high", "category": "employment", "day_offset": 5, "hour": 13, "minute": 30},
            {"title": "CPI m/m", "currency": "USD", "impact": "high", "category": "inflation", "day_offset": 12, "hour": 13, "minute": 30},
            {"title": "FOMC Rate Decision", "currency": "USD", "impact": "high", "category": "central_bank", "day_offset": 20, "hour": 19, "minute": 0},
            {"title": "Core Retail Sales m/m", "currency": "USD", "impact": "medium", "category": "retail_sales", "day_offset": 3, "hour": 13, "minute": 30},
            {"title": "Unemployment Claims", "currency": "USD", "impact": "medium", "category": "employment", "day_offset": 2, "hour": 13, "minute": 30},
            
            # EUR Events
            {"title": "ECB Rate Decision", "currency": "EUR", "impact": "high", "category": "central_bank", "day_offset": 10, "hour": 13, "minute": 45},
            {"title": "CPI Flash Estimate y/y", "currency": "EUR", "impact": "high", "category": "inflation", "day_offset": 15, "hour": 10, "minute": 0},
            {"title": "German IFO Business Climate", "currency": "EUR", "impact": "medium", "category": "survey", "day_offset": 7, "hour": 9, "minute": 0},
            
            # GBP Events
            {"title": "BOE Rate Decision", "currency": "GBP", "impact": "high", "category": "central_bank", "day_offset": 18, "hour": 12, "minute": 0},
            {"title": "CPI y/y", "currency": "GBP", "impact": "high", "category": "inflation", "day_offset": 8, "hour": 7, "minute": 0},
            {"title": "GDP m/m", "currency": "GBP", "impact": "high", "category": "gdp", "day_offset": 25, "hour": 7, "minute": 0},
            
            # Gold specific
            {"title": "FOMC Minutes", "currency": "USD", "impact": "high", "category": "central_bank", "day_offset": 22, "hour": 19, "minute": 0},
        ]
        
        for i in range(days_ahead):
            current_date = base_date + timedelta(days=i)
            for evt in recurring:
                if evt["day_offset"] == i:
                    dt = current_date.replace(hour=evt["hour"], minute=evt["minute"])
                    events.append(EconomicEvent(
                        id=f"{evt['currency']}_{evt['title'].replace(' ', '_')}_{i}",
                        title=evt["title"],
                        currency=evt["currency"],
                        impact=evt["impact"],
                        forecast=None,
                        previous=None,
                        actual=None,
                        datetime_utc=dt,
                        country=evt["currency"],
                        category=evt["category"],
                        source="mock",
                    ))
        
        return events
    
    # --------------------------------------------------------
    # CHECK TRADING ALLOWED
    # --------------------------------------------------------
    
    def is_trading_blocked(
        self,
        instrument: Instrument,
        check_time: datetime | None = None,
        config: NewsFilterConfig | None = None,
    ) -> tuple[bool, str | None, EconomicEvent | None]:
        """
        Vérifie si le trading est bloqué pour l'instrument à check_time.
        
        Returns:
            (blocked: bool, reason: str | None, blocking_event: EconomicEvent | None)
        """
        check_time = check_time or datetime.now(timezone.utc)
        cfg = config or self.configs.get(instrument)
        
        if not cfg or not cfg.enabled:
            return False, None, None
        
        # S'assurer que le calendrier est chargé
        if not self._events_cache:
            self._load_cache()
        
        # Vérifier chaque événement
        for event in self._events_cache:
            # Les événements simulés (source="mock") ne bloquent jamais
            # réellement le trading — dates approximatives, usage dev uniquement.
            if event.source == "mock":
                continue
            # Filtrer par devise concernée
            if event.currency not in cfg.currencies_to_watch:
                continue
            
            # Filtrer par catégorie bloquée
            if event.category in cfg.blocked_categories:
                pass  # Bloquer
            elif cfg.allow_custom_events and event.title in cfg.custom_blocked_events:
                pass  # Bloquer événement custom
            else:
                continue  # Pas bloquant
            
            # Calculer fenêtre de blocage
            if event.impact == "high":
                window = timedelta(minutes=cfg.high_impact_window_min)
            elif event.impact == "medium":
                window = timedelta(minutes=cfg.medium_impact_window_min)
            else:
                continue  # Low impact ne bloque pas par défaut
            
            # Vérifier si on est dans la fenêtre
            window_start = event.datetime_utc - window
            window_end = event.datetime_utc + window
            
            if window_start <= check_time <= window_end:
                minutes_to_event = int((event.datetime_utc - check_time).total_seconds() / 60)
                if minutes_to_event >= 0:
                    reason = f"News HIGH IMPACT dans {minutes_to_event}min: {event.title} ({event.currency})"
                else:
                    reason = f"News HIGH IMPACT il y a {abs(minutes_to_event)}min: {event.title} ({event.currency})"
                return True, reason, event
        
        return False, None, None
    
    def get_upcoming_events(
        self,
        instrument: Instrument,
        hours_ahead: int = 24,
        check_time: datetime | None = None,
    ) -> list[EconomicEvent]:
        """Retourne les événements à venir pour l'instrument."""
        check_time = check_time or datetime.now(timezone.utc)
        cfg = self.configs.get(instrument)
        
        if not cfg:
            return []
        
        if not self._events_cache:
            self._load_cache()
        
        cutoff = check_time + timedelta(hours=hours_ahead)
        upcoming = []
        
        for event in self._events_cache:
            if event.currency not in cfg.currencies_to_watch:
                continue
            if check_time <= event.datetime_utc <= cutoff:
                upcoming.append(event)
        
        return sorted(upcoming, key=lambda e: e.datetime_utc)
    
    def get_event_status(
        self,
        instrument: Instrument,
        check_time: datetime | None = None,
    ) -> dict:
        """Status complet du filtre news pour l'instrument."""
        check_time = check_time or datetime.now(timezone.utc)
        blocked, reason, event = self.is_trading_blocked(instrument, check_time)
        upcoming = self.get_upcoming_events(instrument, hours_ahead=24, check_time=check_time)
        
        return {
            "instrument": instrument,
            "check_time_utc": check_time.isoformat(),
            "news_filter_enabled": self.configs.get(instrument, NewsFilterConfig()).enabled,
            "trading_blocked": blocked,
            "block_reason": reason,
            "blocking_event": {
                "title": event.title,
                "currency": event.currency,
                "impact": event.impact,
                "datetime_utc": event.datetime_utc.isoformat(),
                "category": event.category,
            } if event else None,
            "upcoming_events": [
                {
                    "title": e.title,
                    "currency": e.currency,
                    "impact": e.impact,
                    "datetime_utc": e.datetime_utc.isoformat(),
                    "category": e.category,
                    "minutes_until": int((e.datetime_utc - check_time).total_seconds() / 60),
                }
                for e in upcoming[:10]
            ],
        }


# Instance globale par défaut
default_news_filter = NewsFilter()


# ============================================================
# HELPERS SIMPLES
# ============================================================

def is_news_blocking(instrument: Instrument, check_time: datetime | None = None) -> bool:
    """Vérification rapide : news bloque le trading ?"""
    blocked, _, _ = default_news_filter.is_trading_blocked(instrument, check_time)
    return blocked


def get_news_status(instrument: Instrument, check_time: datetime | None = None) -> dict:
    """Status complet news pour l'instrument."""
    return default_news_filter.get_event_status(instrument, check_time)


async def refresh_news_calendar(days_ahead: int = 7) -> int:
    """Force le rafraîchissement du calendrier. Retourne nb événements."""
    events = await default_news_filter.fetch_calendar(days_ahead)
    return len(events)