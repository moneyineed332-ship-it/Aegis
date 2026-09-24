"""ICT/SMC Signal Generator for Forex Trading Bot.

Implements complete ICT/SMC strategy with multi-timeframe analysis:
- H4/H1: Trend context and bias
- M15: Structure and setup identification
- M5: Entry confirmation

Key ICT/SMC concepts implemented:
- Market structure (HH, HL, LH, LL, BOS, CHoCH)
- Liquidity sweeps (buy-side, sell-side)
- Order Blocks (bullish, bearish with fill status)
- Fair Value Gaps (bullish, bearish with fill status)
- Premium/Discount zones
- Confluence scoring
- Session timing
"""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, List
from enum import Enum

from .ict_config import Instrument, get_instrument_config
from .indicators import market_structure, liquidity_zones, order_blocks, fair_value_gaps, swing_highs_lows

logger = logging.getLogger(__name__)


# ============================================================
# TYPES & ENUMS
# ============================================================

class SignalDirection(Enum):
    """Direction du signal."""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"


class SignalQuality(Enum):
    """Qualité du signal basée sur la confluence."""
    EXCELLENT = "excellent"  # 5+ confluence factors
    GOOD = "good"  # 3-4 confluence factors
    MODERATE = "moderate"  # 2 confluence factors
    WEAK = "weak"  # 1 confluence factor


class ConfluenceFactor(Enum):
    """Facteurs de confluence ICT/SMC."""
    TREND_ALIGNMENT = "trend_alignment"
    BOS_CHOCH = "bos_choch"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    ORDER_BLOCK = "order_block"
    FAIR_VALUE_GAP = "fair_value_gap"
    PREMIUM_DISCOUNT = "premium_discount"
    SESSION_TIMING = "session_timing"
    VOLATILITY = "volatility"
    STRUCTURE = "structure"


@dataclass
class ICTSignal:
    """Signal de trading ICT/SMC."""
    direction: SignalDirection
    quality: SignalQuality
    entry_price: float
    sl_price: float
    tp_price: float
    rr_ratio: float
    confluence_score: int  # 0-10
    confluence_factors: List[ConfluenceFactor]
    setup_type: str
    timeframe: str
    instrument: Instrument
    timestamp: datetime
    
    # ICT/SMC context
    trend_context: str  # bullish, bearish, neutral
    structure: Dict  # Market structure details
    liquidity: Dict  # Liquidity details
    fvg: Optional[Dict] = None  # FVG details
    order_block: Optional[Dict] = None  # OB details
    session: str = ""
    
    # Validation
    risk_percentage: float = 0.0
    position_size_lots: float = 0.0


# ============================================================
# ICT/SMC SIGNAL GENERATOR
# ============================================================

class ICTSignalGenerator:
    """
    Générateur de signaux ICT/SMC.
    
    Analyse multi-timeframe:
    - H4/H1: Contexte de tendance
    - M15: Structure et setup
    - M5: Confirmation d'entrée
    """
    
    def __init__(self, instrument: Instrument = "EURUSD"):
        self.instrument = instrument
        self.cfg = get_instrument_config(instrument)
        self.min_confluence_score = 6  # Minimum pour signal valide
        self.min_rr_ratio = self.cfg.min_rr_ratio
        self.target_rr_ratio = self.cfg.target_rr_ratio
        
    def generate_signal(
        self,
        candles_h4: List[Dict],
        candles_h1: List[Dict],
        candles_m15: List[Dict],
        candles_m5: List[Dict],
        current_price: float
    ) -> Optional[ICTSignal]:
        """
        Génère un signal ICT/SMC basé sur l'analyse multi-timeframe.
        
        Args:
            candles_h4: Candles H4 (contexte long terme)
            candles_h1: Candles H1 (contexte moyen terme)
            candles_m15: Candles M15 (setup)
            candles_m5: Candles M5 (confirmation)
            current_price: Prix actuel
        
        Returns:
            ICTSignal ou None si pas de signal valide
        """
        # 1. Analyser le contexte de tendance (H4/H1)
        trend_context = self._analyze_trend_context(candles_h4, candles_h1)
        
        # 2. Identifier la structure sur M15
        structure = self._analyze_structure(candles_m15)
        
        # 3. Détecter la liquidité
        liquidity = self._analyze_liquidity(candles_m15)
        
        # 4. Détecter FVG et OB
        fvg = fair_value_gaps(candles_m15, lookback=20)
        ob = order_blocks(candles_m15, lookback=20)
        
        # 5. Déterminer la direction potentielle
        potential_direction = self._determine_direction(
            trend_context, structure, liquidity, fvg, ob
        )
        
        if potential_direction == SignalDirection.NEUTRAL:
            logger.debug("No clear direction identified")
            return None
        
        # 6. Calculer les niveaux d'entrée, SL, TP
        entry, sl, tp = self._calculate_levels(
            potential_direction, structure, liquidity, fvg, ob, current_price
        )
        
        if not entry or not sl or not tp:
            logger.debug("Could not calculate valid levels")
            return None
        
        # 7. Calculer le RR ratio
        rr_ratio = self._calculate_rr_ratio(entry, sl, tp)
        
        if rr_ratio < self.min_rr_ratio:
            logger.debug(f"RR ratio {rr_ratio:.2f} below minimum {self.min_rr_ratio}")
            return None
        
        # 8. Score de confluence
        confluence_score, confluence_factors = self._calculate_confluence(
            potential_direction, trend_context, structure, liquidity, fvg, ob,
            candles_m15=candles_m15,
        )
        
        if confluence_score < self.min_confluence_score:
            logger.debug(f"Confluence score {confluence_score} below minimum {self.min_confluence_score}")
            return None
        
        # 9. Confirmation M5
        if not self._confirm_m5(candles_m5, potential_direction, entry):
            logger.debug("M5 confirmation failed")
            return None
        
        # 10. Créer le signal
        quality = self._determine_quality(confluence_score)
        
        signal = ICTSignal(
            direction=potential_direction,
            quality=quality,
            entry_price=entry,
            sl_price=sl,
            tp_price=tp,
            rr_ratio=rr_ratio,
            confluence_score=confluence_score,
            confluence_factors=confluence_factors,
            setup_type="ICT_SMC_" + potential_direction.value.upper(),
            timeframe="M15",
            instrument=self.instrument,
            timestamp=datetime.now(timezone.utc),
            trend_context=trend_context,
            structure=structure,
            liquidity=liquidity,
            fvg=fvg,
            order_block=ob,
            session=self._get_current_session()
        )
        
        logger.info(f"Signal generated: {potential_direction.value.upper()} | RR: {rr_ratio:.2f} | Confluence: {confluence_score}/10")
        
        return signal
    
    def _analyze_trend_context(self, candles_h4: List[Dict], candles_h1: List[Dict]) -> str:
        """
        Analyse le contexte de tendance sur H4 et H1.
        
        Returns:
            "bullish", "bearish", ou "neutral"
        """
        ms_h4 = market_structure(candles_h4, lookback=10)
        ms_h1 = market_structure(candles_h1, lookback=10)
        
        trend_h4 = ms_h4.get("trend", "neutral")
        trend_h1 = ms_h1.get("trend", "neutral")
        
        # Confluence de tendance
        if trend_h4 == "bullish" and trend_h1 == "bullish":
            return "bullish"
        elif trend_h4 == "bearish" and trend_h1 == "bearish":
            return "bearish"
        elif trend_h4 == "bullish" or trend_h1 == "bullish":
            return "bullish_weak"
        elif trend_h4 == "bearish" or trend_h1 == "bearish":
            return "bearish_weak"
        else:
            return "neutral"
    
    def _analyze_structure(self, candles: List[Dict]) -> Dict:
        """Analyse la structure de marché."""
        ms = market_structure(candles, lookback=10)

        return {
            "trend": ms.get("trend", "neutral"),
            "last_bos": ms.get("last_bos"),
            "last_choch": ms.get("last_choch"),
            "structure_points": ms.get("structure_points", []),
            "swing_highs_lows": swing_highs_lows(candles, lookback=10),
            "last_price": candles[-1]["close"] if candles else 0.0,
        }
    
    def _analyze_liquidity(self, candles: List[Dict]) -> Dict:
        """Analyse les zones de liquidité."""
        liq = liquidity_zones(candles, lookback=20)
        
        return {
            "buy_side_liquidity": liq.get("buy_side_liquidity", []),
            "sell_side_liquidity": liq.get("sell_side_liquidity", []),
            "recent_bull_sweep": liq.get("recent_bull_sweep"),
            "recent_bear_sweep": liq.get("recent_bear_sweep")
        }
    
    def _determine_direction(
        self,
        trend_context: str,
        structure: Dict,
        liquidity: Dict,
        fvg: Dict,
        ob: Dict
    ) -> SignalDirection:
        """
        Détermine la direction du signal basée sur l'analyse.
        
        Règles ICT/SMC:
        - Suivre la tendance (BOS dans direction de tendance)
        - Contre-trend sur CHoCH avec confluence forte
        - Liquidity sweep comme déclencheur
        """
        bias_bullish = trend_context in ["bullish", "bullish_weak"]
        bias_bearish = trend_context in ["bearish", "bearish_weak"]
        
        # market_structure() emits "bullish_bos"/"bearish_choch"-style values.
        last_bos = str(structure.get("last_bos") or "")
        last_choch = str(structure.get("last_choch") or "")
        bull_sweep = liquidity.get("recent_bull_sweep")
        bear_sweep = liquidity.get("recent_bear_sweep")

        # Préférence pour trend-following
        if bias_bullish and (last_bos.startswith("bullish") or bull_sweep):
            return SignalDirection.BUY
        elif bias_bearish and (last_bos.startswith("bearish") or bear_sweep):
            return SignalDirection.SELL

        # Contre-trend sur CHoCH avec confluence
        if bias_bullish and last_choch.startswith("bearish") and (bull_sweep or ob.get("bullish_ob")):
            return SignalDirection.BUY
        elif bias_bearish and last_choch.startswith("bullish") and (bear_sweep or ob.get("bearish_ob")):
            return SignalDirection.SELL
        
        return SignalDirection.NEUTRAL
    
    def _calculate_levels(
        self,
        direction: SignalDirection,
        structure: Dict,
        liquidity: Dict,
        fvg: Dict,
        ob: Dict,
        current_price: float
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calcule les niveaux d'entrée, SL, et TP.

        Règles ICT/SMC (Cahier des charges §8/§9):
        - Entry: au retour sur structure/OB/FVG
        - SL: sous/auf le swing low/high + buffer structure
        - TP: sur prochaine zone de liquidité (RR target)
        """
        pip = self.cfg.pip_value
        buffer_price = self.cfg.sl_structure_buffer_pips * pip

        if direction == SignalDirection.BUY:
            # Entry: sur FVG ou OB bullish (clés réelles: price_low/price_high)
            bull_fvg = fvg.get("bullish_fvg") or {}
            bull_ob = ob.get("bullish_ob") or {}

            if bull_fvg:
                entry = bull_fvg.get("price_low", current_price)
            elif bull_ob:
                entry = bull_ob.get("price_low", current_price)
            else:
                entry = current_price

            # SL: sous le swing low récent + buffer structure (§8)
            swing_lows = _swing_prices(structure.get("swing_highs_lows", {}).get("lows", []))
            if swing_lows:
                sl = min(swing_lows[-3:]) - buffer_price  # Buffer below structure
            else:
                sl = entry - (self.cfg.sl_atr_multiplier * pip * 10)  # Fallback: ATR-based

            # TP: sur zone de liquidité suivante (§9, clé réelle: price)
            buy_liq = liquidity.get("buy_side_liquidity", [])
            if buy_liq:
                tp = buy_liq[0].get("price", entry + self.cfg.target_rr_ratio * abs(entry - sl))
            else:
                tp = entry + self.cfg.target_rr_ratio * abs(entry - sl)  # RR-based fallback

        else:  # SELL
            # Entry: sur FVG ou OB bearish
            bear_fvg = fvg.get("bearish_fvg") or {}
            bear_ob = ob.get("bearish_ob") or {}

            if bear_fvg:
                entry = bear_fvg.get("price_high", current_price)
            elif bear_ob:
                entry = bear_ob.get("price_high", current_price)
            else:
                entry = current_price

            # SL: au-dessus du swing high récent + buffer structure (§8)
            swing_highs = _swing_prices(structure.get("swing_highs_lows", {}).get("highs", []))
            if swing_highs:
                sl = max(swing_highs[-3:]) + buffer_price  # Buffer above structure
            else:
                sl = entry + (self.cfg.sl_atr_multiplier * pip * 10)  # Fallback: ATR-based

            # TP: sur zone de liquidité suivante (§9)
            sell_liq = liquidity.get("sell_side_liquidity", [])
            if sell_liq:
                tp = sell_liq[0].get("price", entry - self.cfg.target_rr_ratio * abs(sl - entry))
            else:
                tp = entry - self.cfg.target_rr_ratio * abs(sl - entry)  # RR-based fallback

        return entry, sl, tp
    
    def _calculate_rr_ratio(self, entry: float, sl: float, tp: float) -> float:
        """Calcule le ratio Risk/Reward."""
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if risk == 0:
            return 0.0
        
        return reward / risk
    
    def _calculate_confluence(
        self,
        direction: SignalDirection,
        trend_context: str,
        structure: Dict,
        liquidity: Dict,
        fvg: Dict,
        ob: Dict,
        candles_m15: List[Dict] | None = None,
    ) -> tuple[int, List[ConfluenceFactor]]:
        """
        Calcule le score de confluence (0-10).

        Cahier des charges §6 — Conditions d'entrée multi-confirmations:
        - Trend alignment (2 pts): contexte global favorable
        - BOS/CHoCH (2 pts): confirmation structurelle
        - Liquidity sweep (2 pts): prise de liquidité identifiée
        - Order Block (1 pt): zone d'intérêt ICT/SMC
        - Fair Value Gap (1 pt): gap de valeur équitable
        - Premium/Discount (1 pt): prix en zone favorable
        - Session timing (1 pt): session de trading active
        - Volatility (1 pt): volatilité dans les limites
        """
        factors = []
        score = 0
        pip = self.cfg.pip_value

        # Trend alignment (2 points)
        if (direction == SignalDirection.BUY and trend_context in ["bullish", "bullish_weak"]) or \
           (direction == SignalDirection.SELL and trend_context in ["bearish", "bearish_weak"]):
            factors.append(ConfluenceFactor.TREND_ALIGNMENT)
            score += 2

        # BOS/CHoCH (2 points) — valeurs "bullish_bos"/"bearish_choch".
        last_bos = str(structure.get("last_bos") or "")
        last_choch = str(structure.get("last_choch") or "")
        if (direction == SignalDirection.BUY and last_bos.startswith("bullish")) or \
           (direction == SignalDirection.SELL and last_bos.startswith("bearish")):
            factors.append(ConfluenceFactor.BOS_CHOCH)
            score += 2
        elif (direction == SignalDirection.BUY and last_choch.startswith("bearish")) or \
             (direction == SignalDirection.SELL and last_choch.startswith("bullish")):
            factors.append(ConfluenceFactor.BOS_CHOCH)
            score += 1

        # Liquidity sweep (2 points)
        bull_sweep = liquidity.get("recent_bull_sweep")
        bear_sweep = liquidity.get("recent_bear_sweep")
        if (direction == SignalDirection.BUY and bull_sweep) or \
           (direction == SignalDirection.SELL and bear_sweep):
            factors.append(ConfluenceFactor.LIQUIDITY_SWEEP)
            score += 2

        # Order Block (1 point)
        if (direction == SignalDirection.BUY and ob.get("bullish_ob")) or \
           (direction == SignalDirection.SELL and ob.get("bearish_ob")):
            factors.append(ConfluenceFactor.ORDER_BLOCK)
            score += 1

        # Fair Value Gap (1 point)
        if (direction == SignalDirection.BUY and fvg.get("bullish_fvg")) or \
           (direction == SignalDirection.SELL and fvg.get("bearish_fvg")):
            factors.append(ConfluenceFactor.FAIR_VALUE_GAP)
            score += 1

        # Premium/Discount zone (1 point) — §6: retour dans zone institutionnelle
        swing_highs = _swing_prices(structure.get("swing_highs_lows", {}).get("highs", []))
        swing_lows = _swing_prices(structure.get("swing_highs_lows", {}).get("lows", []))
        if swing_highs and swing_lows:
            high = max(swing_highs[-5:])
            low = min(swing_lows[-5:])
            mid = (high + low) / 2
            if direction == SignalDirection.BUY:
                # Buy in discount zone (below 50%)
                if structure.get("last_price", mid) < mid:
                    factors.append(ConfluenceFactor.PREMIUM_DISCOUNT)
                    score += 1
            else:
                # Sell in premium zone (above 50%)
                if structure.get("last_price", mid) > mid:
                    factors.append(ConfluenceFactor.PREMIUM_DISCOUNT)
                    score += 1

        # Session timing (1 point)
        session = self._get_current_session()
        if session in self.cfg.enabled_sessions:
            factors.append(ConfluenceFactor.SESSION_TIMING)
            score += 1

        # Volatility filter (1 point) — §11: filtre volatilité
        # Check ATR is within acceptable range for the instrument
        if candles_m15 and len(candles_m15) >= 14:
            from .indicators import atr_single
            current_atr = atr_single(candles_m15, 14)
            if current_atr is not None and self.cfg.min_atr_pips <= current_atr / self.cfg.pip_value <= self.cfg.max_atr_pips:
                factors.append(ConfluenceFactor.VOLATILITY)
                score += 1

        return min(score, 10), factors
    
    def _confirm_m5(self, candles_m5: List[Dict], direction: SignalDirection, entry: float) -> bool:
        """
        Confirmation sur M5.
        
        Règles:
        - Prix doit s'approcher de l'entry
        - Momentum favorable
        - Pas de structure contraire
        """
        if len(candles_m5) < 5:
            return False
        
        recent_candles = candles_m5[-5:]
        current_price = recent_candles[-1]["close"]
        
        # Prix dans la zone d'entry (±0.5 pip)
        pip_value = self.cfg.pip_value
        if abs(current_price - entry) > (5 * pip_value):
            return False
        
        # Momentum favorable
        if direction == SignalDirection.BUY:
            # 3 dernières candles bullish
            bullish_count = sum(1 for c in recent_candles[-3:] if c["close"] > c["open"])
            return bullish_count >= 2
        else:
            # 3 dernières candles bearish
            bearish_count = sum(1 for c in recent_candles[-3:] if c["close"] < c["open"])
            return bearish_count >= 2
    
    def _determine_quality(self, confluence_score: int) -> SignalQuality:
        """Détermine la qualité du signal."""
        if confluence_score >= 8:
            return SignalQuality.EXCELLENT
        elif confluence_score >= 6:
            return SignalQuality.GOOD
        elif confluence_score >= 4:
            return SignalQuality.MODERATE
        else:
            return SignalQuality.WEAK
    
    def _get_current_session(self) -> str:
        """Retourne la session actuelle."""
        from .session_filter import default_session_filter
        session = default_session_filter.get_current_session()
        return session if session else "off_hours"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def generate_ict_signal(
    instrument: Instrument,
    candles_h4: List[Dict],
    candles_h1: List[Dict],
    candles_m15: List[Dict],
    candles_m5: List[Dict],
    current_price: float
) -> Optional[ICTSignal]:
    """
    Fonction helper pour générer un signal ICT/SMC.
    
    Args:
        instrument: Instrument Forex
        candles_h4: Candles H4
        candles_h1: Candles H1
        candles_m15: Candles M15
        candles_m5: Candles M5
        current_price: Prix actuel
    
    Returns:
        ICTSignal ou None
    """
    generator = ICTSignalGenerator(instrument)
    return generator.generate_signal(
        candles_h4, candles_h1, candles_m15, candles_m5, current_price
    )


# Instance par défaut pour facilité d'utilisation
default_signal_generator = ICTSignalGenerator("EURUSD")


def _swing_prices(points: List) -> List[float]:
    """Extract prices from swing points (dicts {"price": ...} or raw numbers).

    Entries without a usable price are dropped (never injected as 0.0,
    which would corrupt min/max levels and SL placement).
    """
    prices: List[float] = []
    for p in points or []:
        raw = p.get("price") if isinstance(p, dict) else p
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            prices.append(value)
    return prices
