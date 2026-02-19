from __future__ import annotations

"""HMM-based regime detection (optional).

This module is *optional* because hmmlearn may not be installed in the VPS environment.
We keep it here so we can enable it when dependencies are available.

Notebook reference: BTC_Market_Regime_HMM.ipynb
Features: returns, range, volume change.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class HMMRegimeResult:
    state: pd.Series
    state_prob: Optional[pd.DataFrame]
    feature_df: pd.DataFrame


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["Returns"] = data["Close"].pct_change()
    data["Range"] = (data["High"] - data["Low"]) / data["Close"]
    data["Vol_Change"] = data["Volume"].pct_change()
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    return data[["Returns", "Range", "Vol_Change"]]


def fit_predict_hmm(df: pd.DataFrame, n_states: int = 7, random_state: int = 42) -> HMMRegimeResult:
    try:
        from hmmlearn.hmm import GaussianHMM
    except Exception as e:
        raise RuntimeError(
            "hmmlearn is not installed. Install hmmlearn to enable HMM regimes."
        ) from e

    feat = build_features(df)
    X = feat.values

    hmm = GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=1000,
        random_state=random_state,
    )
    hmm.fit(X)

    states = hmm.predict(X)
    state = pd.Series(states, index=feat.index, name="State")

    # Optional probabilities (can be used as confidence)
    try:
        probs = hmm.predict_proba(X)
        prob_df = pd.DataFrame(probs, index=feat.index, columns=[f"S{i}" for i in range(n_states)])
    except Exception:
        prob_df = None

    return HMMRegimeResult(state=state, state_prob=prob_df, feature_df=feat)
