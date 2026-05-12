"""BTC trend signals from 1h candles — pure functional extraction from V51."""

import numpy as np
import pandas as pd
from pandas import DataFrame


def compute(btc_df: DataFrame, cfg: dict) -> dict:
    """Compute BTC trend signals from 1h candles.

    Returns dict with keys: dates, pump, dump, high_vol, vol_just_ended,
    btc_mom, btc_atr_z (all numpy arrays).

    Config keys used: btc_trend.pump_threshold, dump_threshold,
    high_vol_threshold, vol_ended_threshold, mom_period, atr_period, atr_z_window
    """
    c = cfg['btc_trend']
    mom_period = c['mom_period']
    atr_period = c['atr_period']
    atr_z_window = c['atr_z_window']
    pump_threshold = c['pump_threshold']
    dump_threshold = c['dump_threshold']
    high_vol_threshold = c['high_vol_threshold']
    vol_ended_threshold = c['vol_ended_threshold']

    mom = btc_df['close'].pct_change(mom_period)

    tr = np.maximum(
        btc_df['high'] - btc_df['low'],
        np.maximum(
            abs(btc_df['high'] - btc_df['close'].shift(1)),
            abs(btc_df['low'] - btc_df['close'].shift(1)),
        ),
    )

    atr = tr.rolling(atr_period).mean()
    atr_pct = atr / btc_df['close']
    atr_z = (atr_pct - atr_pct.rolling(atr_z_window).mean()) / atr_pct.rolling(atr_z_window).std()
    atr_z = atr_z.replace(np.nan, 0).fillna(0)

    ve = atr_z.shift(1)

    return {
        'dates': btc_df['date'].values,
        'pump': (mom > pump_threshold).values,
        'dump': (mom < dump_threshold).values,
        'high_vol': (atr_z > high_vol_threshold).values,
        'vol_just_ended': ((ve > vol_ended_threshold) & (atr_z <= vol_ended_threshold)).values,
        'btc_mom': mom.values,
        'btc_atr_z': atr_z.values,
    }


def map_to_timeframe(btc_state: dict, dataframe: DataFrame) -> DataFrame:
    """Map BTC 1h signals to pair's timeframe via forward-fill.

    Adds columns: btc_pump, btc_dump, btc_high_vol, btc_vol_ended, btc_mom, btc_atr_z
    """
    signal_map = {
        'btc_pump': 'pump',
        'btc_dump': 'dump',
        'btc_high_vol': 'high_vol',
        'btc_vol_ended': 'vol_just_ended',
        'btc_mom': 'btc_mom',
        'btc_atr_z': 'btc_atr_z',
    }

    pair_dates = pd.to_datetime(dataframe['date'])

    btc_df = pd.DataFrame(index=btc_state['dates'])
    for col_name, signal_key in signal_map.items():
        btc_df[col_name] = btc_state[signal_key]

    merged = btc_df.set_index(btc_df.index).reindex(pair_dates, method='ffill')

    for col_name in signal_map:
        dataframe[col_name] = merged[col_name].fillna(0).values

    return dataframe
