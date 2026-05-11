"""dYdX exchange subclass"""

import logging

import ccxt

from freqtrade.enums import MarginMode, TradingMode
from freqtrade.exceptions import DDosProtection, OperationalException, TemporaryError
from freqtrade.exchange import Exchange
from freqtrade.exchange.common import retrier
from freqtrade.exchange.exchange_types import FtHas


logger = logging.getLogger(__name__)


class Dydx(Exchange):
    """dYdX v4 exchange class.
    Contains adjustments needed for Freqtrade to work with this exchange.
    """

    _ft_has: FtHas = {
        "ohlcv_has_history": True,
        "trades_has_history": False,
        "tickers_have_bid_ask": False,
        "stoploss_on_exchange": False,
        "marketOrderRequiresPrice": True,
    }
    _ft_has_futures: FtHas = {
        "uses_leverage_tiers": False,
        "funding_fee_candle_limit": 500,
        "mark_ohlcv_price": "futures",
    }

    _supported_trading_mode_margin_pairs: list[tuple[TradingMode, MarginMode]] = [
        (TradingMode.FUTURES, MarginMode.CROSS),
    ]

    @retrier
    def additional_exchange_init(self) -> None:
        """
        Additional exchange initialization logic.
        Enables sandbox mode if configured.
        """
        try:
            sandbox = self._api.options.get("sandboxMode", False)
            if sandbox:
                self._api.set_sandbox_mode(True)
                self._api_async.set_sandbox_mode(True)
                logger.info("dYdX sandbox (testnet) mode enabled.")
        except ccxt.DDoSProtection as e:
            raise DDosProtection(e) from e
        except (ccxt.OperationFailed, ccxt.ExchangeError) as e:
            raise TemporaryError(
                f"Error in additional_exchange_init due to {e.__class__.__name__}. Message: {e}"
            ) from e
        except ccxt.BaseError as e:
            raise OperationalException(e) from e
