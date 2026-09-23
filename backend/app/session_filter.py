"""Filtre de sessions horaires pour le bot ICT/SMC.

Gère les sessions de trading (Asiatique, Londres, New York, Overlap)
et détermine si le trading est autorisé à un moment donné.
"""

from datetime import datetime, time, timezone, timedelta
from typing import Literal
from .ict_config import (
    TRADING_SESSIONS,
    SessionName,
    Instrument,
    get_instrument_config,
    DEFAULT_ENABLED_SESSIONS,
)


class SessionFilter:
    """
    Filtre de sessions de trading.
    
    Vérifie si on est dans une session autorisée pour un instrument donné.
    Supporte les sessions personnalisées par instrument.
    """
    
    def __init__(self, custom_sessions: dict[Instrument, list[SessionName]] | None = None):
        """
        Args:
            custom_sessions: Sessions activées par instrument (override config par défaut)
        """
        self.sessions = TRADING_SESSIONS
        self.enabled_sessions = custom_sessions or DEFAULT_ENABLED_SESSIONS
    
    def _parse_time(self, time_str: str) -> time:
        """Parse 'HH:MM' en objet time."""
        h, m = map(int, time_str.split(":"))
        return time(h, m)
    
    def _is_time_in_range(self, current: time, start: time, end: time) -> bool:
        """Vérifie si current est dans [start, end], gérant le passage minuit."""
        if start <= end:
            return start <= current <= end
        # Session traverse minuit (ex: 22:00 - 02:00)
        return current >= start or current <= end
    
    # Priority order: narrowest/most significant sessions first, so that
    # "overlap" (13-17) is not shadowed by "london"/"new_york" and "london"
    # wins over "asian" on 08:00-09:00 (both match, only london is enabled).
    _SESSION_PRIORITY: tuple = ("overlap", "london", "new_york", "asian")

    def get_current_session(self, now: datetime | None = None) -> SessionName | None:
        """
        Retourne la session active actuellement.

        Returns:
            Nom de la session ou None si hors session
        """
        now = now or datetime.now(timezone.utc)
        current_time = now.time()

        ordered = [s for s in self._SESSION_PRIORITY if s in self.sessions]
        ordered += [s for s in self.sessions if s not in ordered]
        for session_name in ordered:
            session_data = self.sessions[session_name]
            start = self._parse_time(session_data["open"])
            end = self._parse_time(session_data["close"])
            if self._is_time_in_range(current_time, start, end):
                return session_name  # type: ignore

        return None
    
    def is_session_active(
        self,
        instrument: Instrument,
        session_names: list[SessionName] | None = None,
        now: datetime | None = None
    ) -> bool:
        """
        Vérifie si une session autorisée est active pour l'instrument.
        
        Args:
            instrument: Instrument à vérifier
            session_names: Sessions autorisées (si None, utilise config)
            now: Datetime UTC à vérifier
        
        Returns:
            True si dans une session autorisée
        """
        now = now or datetime.now(timezone.utc)
        current_session = self.get_current_session(now)
        
        if current_session is None:
            return False
        
        sessions_to_check = session_names or self.enabled_sessions.get(instrument, [])
        return current_session in sessions_to_check
    
    def get_active_sessions_for_instrument(
        self,
        instrument: Instrument,
        now: datetime | None = None
    ) -> list[SessionName]:
        """Retourne la liste des sessions actives pour l'instrument."""
        current = self.get_current_session(now)
        if current is None:
            return []
        enabled = self.enabled_sessions.get(instrument, [])
        return [current] if current in enabled else []
    
    def time_until_next_session(
        self,
        instrument: Instrument,
        now: datetime | None = None
    ) -> timedelta | None:
        """
        Temps avant la prochaine session autorisée pour l'instrument.
        
        Returns:
            timedelta jusqu'au début de la prochaine session, ou None si dans une session
        """
        now = now or datetime.now(timezone.utc)
        
        # Si déjà dans une session autorisée
        if self.is_session_active(instrument, now=now):
            return timedelta(0)
        
        enabled = self.enabled_sessions.get(instrument, [])
        if not enabled:
            return None
        
        # Trouver la prochaine session
        current_time = now.time()
        next_start = None
        next_date = now.date()
        
        for session_name in enabled:
            session_data = self.sessions[session_name]
            start = self._parse_time(session_data["open"])
            
            # Combiner date + heure
            session_start = datetime.combine(next_date, start, tzinfo=timezone.utc)
            
            # Si déjà passé aujourd'hui, essayer demain
            if session_start <= now:
                session_start = datetime.combine(next_date + timedelta(days=1), start, tzinfo=timezone.utc)
            
            if next_start is None or session_start < next_start:
                next_start = session_start
        
        if next_start:
            return next_start - now
        
        return None
    
    def get_session_info(self, instrument: Instrument, now: datetime | None = None) -> dict:
        """
        Informations complètes sur l'état des sessions.
        
        Returns:
            Dict avec session actuelle, sessions autorisées, prochaine session, etc.
        """
        now = now or datetime.now(timezone.utc)
        current = self.get_current_session(now)
        enabled = self.enabled_sessions.get(instrument, [])
        active = current in enabled if current else False
        next_in = self.time_until_next_session(instrument, now)
        
        return {
            "instrument": instrument,
            "current_utc": now.isoformat(),
            "current_session": current,
            "enabled_sessions": enabled,
            "is_trading_allowed": active,
            "time_until_next_session_seconds": next_in.total_seconds() if next_in else None,
            "next_session_at": (now + next_in).isoformat() if next_in else None,
            "sessions_detail": {
                name: {
                    "open": data["open"],
                    "close": data["close"],
                    "enabled": name in enabled,
                    "active": name == current,
                }
                for name, data in self.sessions.items()
            }
        }


# Instance globale par défaut
default_session_filter = SessionFilter()


# ============================================================
# HELPERS SIMPLES
# ============================================================

def is_trading_allowed(instrument: Instrument, now: datetime | None = None) -> bool:
    """Vérification rapide : trading autorisé maintenant ?"""
    return default_session_filter.is_session_active(instrument, now=now)


def get_current_session(now: datetime | None = None) -> SessionName | None:
    """Session active actuellement."""
    return default_session_filter.get_current_session(now)


def get_session_status(instrument: Instrument, now: datetime | None = None) -> dict:
    """Status complet des sessions pour l'instrument."""
    return default_session_filter.get_session_info(instrument, now)