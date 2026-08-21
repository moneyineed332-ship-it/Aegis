"""Package instruments - Configurations spécifiques par instrument."""

from .eurusd import EURUSD_CONFIG
from .gbpusd import GBPUSD_CONFIG
from .xauusd import XAUUSD_CONFIG

__all__ = ["EURUSD_CONFIG", "GBPUSD_CONFIG", "XAUUSD_CONFIG"]

# Mapping pour accès facile
INSTRUMENT_CONFIGS = {
    "EURUSD": EURUSD_CONFIG,
    "GBPUSD": GBPUSD_CONFIG,
    "XAUUSD": XAUUSD_CONFIG,
}


def get_config(symbol: str):
    """Récupère la config pour un symbole."""
    return INSTRUMENT_CONFIGS.get(symbol.upper())