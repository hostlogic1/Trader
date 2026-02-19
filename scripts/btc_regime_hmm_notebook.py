
# --- cell 0 ---
# ====== Colab Cell 1: Install libraries ======
!pip -q install yfinance hmmlearn matplotlib pandas numpy scikit-learn

# --- cell 1 ---
# ====== Colab Cell 2: Imports ======
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

from hmmlearn.hmm import GaussianHMM

# --- cell 2 ---
# ====== Colab Cell 3: Get hourly BTC-USD data (last 730 days) ======
ticker = "BTC-USD"

df = yf.download(
    tickers=ticker,
    period="730d",
    interval="1h",
    auto_adjust=False,
    progress=False
)

# Handle yfinance MultiIndex columns (flatten using level 0)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Keep exactly: Open, High, Low, Close, Volume
required_cols = ["Open", "High", "Low", "Close", "Volume"]

# Some yfinance responses may include other columns (e.g., Adj Close); select required safely
missing = [c for c in required_cols if c not in df.columns]
if missing:
    raise ValueError(f"Missing required columns from yfinance download: {missing}. Found: {list(df.columns)}")

df = df[required_cols].copy()

# Basic cleanup
df = df.dropna()
df.head(), df.tail()

# --- cell 3 ---
# ====== Colab Cell 4: Feature Engineering (exactly 3 features) ======
data = df.copy()

data["Returns"] = data["Close"].pct_change()
data["Range"] = (data["High"] - data["Low"]) / data["Close"]
data["Vol_Change"] = data["Volume"].pct_change()

# Replace inf/-inf with NaN, then drop NaNs (as required)
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna()
data = data.replace([np.inf, -np.inf], np.nan)
data = data.dropna()

data[["Returns", "Range", "Vol_Change"]].describe()

# --- cell 4 ---
# ====== Colab Cell 5: Train HMM (7 regimes) ======
X = data[["Returns", "Range", "Vol_Change"]].values

hmm = GaussianHMM(
    n_components=7,
    covariance_type="full",
    n_iter=1000,
    random_state=42
)

hmm.fit(X)

states = hmm.predict(X)
data["State"] = states

data[["Close", "Returns", "Range", "Vol_Change", "State"]].head()

# --- cell 5 ---
# ====== Colab Cell 6: Analyze states ======
summary = (
    data.groupby("State")
        .agg(
            Mean_Return=("Returns", "mean"),
            Volatility=("Returns", "std"),
            Count=("Returns", "size")
        )
        .sort_values("Mean_Return", ascending=False)
)

print(summary.to_string(float_format=lambda x: f"{x:0.6f}"))

# --- cell 6 ---
# ====== Colab Cell 7: Visualize last 500 hours with regime coloring ======
plot_data = data.tail(500).copy()

fig, ax = plt.subplots(figsize=(14, 6))

# Line plot of Close
ax.plot(plot_data.index, plot_data["Close"], linewidth=1.5, label="BTC Close")

# Scatter colored by state
cmap = plt.cm.get_cmap("tab10", 7)  # distinct colormap with 7 bins
sc = ax.scatter(
    plot_data.index,
    plot_data["Close"],
    c=plot_data["State"],
    cmap=cmap,
    s=18,
    alpha=0.9
)

# Legend: one entry per state present in the last 500 hours
present_states = sorted(plot_data["State"].unique())
handles = [
    plt.Line2D([0], [0], marker='o', linestyle='', markersize=7, color=cmap(s), label=f"State {s}")
    for s in present_states
]
ax.legend(handles=handles, title="Detected Regime", loc="best")

ax.set_title("BTC-USD Market Regime Detection (HMM) — Last 500 Hours")
ax.set_xlabel("Time")
ax.set_ylabel("Close Price (USD)")
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
