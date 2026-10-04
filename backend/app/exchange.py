"""Broker errors, and the venue that will raise them.

This module used to be a CCXT/Binance adapter: ExchangeManager plus
create_exchange, get_binance_public, get_binance_testnet and get_live_exchange.
All of it was crypto, and it is gone with the crypto engine.

Two things remain, deliberately:

``ExchangeError`` and ``OrderRejected`` are still imported by oms.py, which is
on the Forex critical path: every ICT order goes through
``oms.oms.submit_market_order``. Moving them into oms.py would have been a
larger diff with no benefit, and the next module to need them is the MT5 broker
adapter, not oms.

``get_live_exchange`` no longer returns an exchange. It raises. That is the
important part of this file. oms.py's live branches called it, and with the
adapter removed they would otherwise have failed somewhere deeper with an
AttributeError or, worse, found a working CCXT venue on a machine that still had
ccxt installed. Making it refuse at the boundary means a request for live
execution stops with a message that says what is missing.

The real venue arrives with the MT5 execution module. When it does, it should
raise these two exceptions on a rejected or unreachable order so oms.py's
existing handlers keep working unchanged.
"""


class ExchangeError(Exception):
    """The venue could not be reached, or returned something unusable."""


class OrderRejected(Exception):
    """The venue understood the order and refused it."""


class NoLiveVenue(ExchangeError):
    """Live execution was requested but no venue is wired up.

    Raised instead of silently falling back to paper, because the difference
    between the two is the entire point of the request.
    """


def get_live_exchange():
    """Always raises. There is no live venue until the MT5 adapter exists."""
    raise NoLiveVenue(
        "No live execution venue is configured. The MT5 adapter is not built yet, "
        "so every order goes through the paper path in oms.py. Running AEGIS_MODE=live "
        "does not change that; it only selects the branch that now refuses."
    )