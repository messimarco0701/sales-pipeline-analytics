"""
Charts for the analysis. One function per figure, all sharing the same small style:
light surface, hairline grid, one accent color unless the chart is about telling series apart,
and a title that states the finding rather than describing the axes.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
GREY = "#c3c2b7"
# Categorical slots, always assigned in this order
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"
# Ordinal blue ramp (light to dark) for ordered categories such as years or percentiles
RAMP = ["#86b6ef", "#2a78d6", "#104281"]
CHANNEL_COLORS = {"Direct": BLUE, "Partner": ORANGE, "Referral": AQUA}

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_2,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "savefig.dpi": 150,
    "savefig.facecolor": SURFACE,
})

euro_k = FuncFormatter(lambda x, _: f"{x / 1000:,.0f}k")
pct = PercentFormatter(1.0, decimals=0)


def _titles(fig, title: str, subtitle: str | None = None) -> None:
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=13, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.012, 0.915, subtitle, ha="left", va="top", fontsize=10, color=INK_2)


def _save(fig, path: Path, top: float = 0.80) -> None:
    fig.subplots_adjust(top=top)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def _label_on(fill: str) -> str:
    """White or ink text inside a colored fill, whichever reads better (relative luminance)."""
    rgb = [int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return INK if (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) else "white"


def funnel(df: pd.DataFrame, path: Path) -> None:
    worst = df.loc[df["share_of_all_losses"].idxmax()]
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(len(df))[::-1]
    ax.barh(y, df["deals_reached"], height=0.5, color=BLUE)
    for yi, (_, r) in zip(y, df.iterrows()):
        conv = "" if pd.isna(r["conversion_from_previous"]) else f"   {r['conversion_from_previous']:.0%} of previous stage"
        ax.text(r["deals_reached"] + 40, yi, f"{r['deals_reached']:,}{conv}", va="center", color=INK_2)
    ax.set_yticks(y, df["stage"])
    ax.set_xlim(0, df["deals_reached"].max() * 1.45)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Closed deals that reached the stage")
    _titles(fig, f"Discovery is where most deals die ({worst['share_of_all_losses']:.0%} of all losses)",
            f"Only {df['conversion_from_start'].iloc[-1]:.0%} of closed deals make it from Discovery to won")
    _save(fig, path)


def win_rates(df: pd.DataFrame, path: Path) -> None:
    panels = [("channel", "Channel"), ("deal_type", "Deal type"),
              ("size_segment", "Company size"), ("product", "Product")]
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.8), sharex=True)
    for ax, (dim, label) in zip(axes, panels):
        d = df[df["dimension"] == dim].sort_values("win_rate")
        y = np.arange(len(d))
        ax.hlines(y, d["ci_low"], d["ci_high"], color=BLUE, linewidth=2, alpha=0.35)
        ax.plot(d["win_rate"], y, "o", color=BLUE, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5)
        ax.set_yticks(y, [f"{v}\nn={n:,}" for v, n in zip(d["value"], d["closed_deals"])])
        ax.set_title(label, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.grid(axis="y", visible=False)
        ax.xaxis.set_major_formatter(pct)
        ax.set_ylim(-0.6, len(d) - 0.4)
    axes[0].set_xlim(0.1, 0.65)
    ch = df[df["dimension"] == "channel"].set_index("value")["win_rate"]
    _titles(fig, f"Referral deals win {ch['Referral']:.0%} of the time, Direct only {ch['Direct']:.0%}",
            "Win rate on closed deals with 95% Wilson interval. Channel and deal type matter, product barely does")
    _save(fig, path, top=0.74)


def sales_cycle(df: pd.DataFrame, path: Path) -> None:
    d = df.set_index("size_segment").loc[["Micro", "Small", "Medium", "Large"]]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    y = np.arange(len(d))[::-1]
    ax.hlines(y, d["won_p50"], d["won_p90"], color=GREY, linewidth=2)
    for col, color, label in [("won_p50", RAMP[2], "Median"), ("won_p75", RAMP[1], "p75"), ("won_p90", RAMP[0], "p90")]:
        ax.plot(d[col], y, "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
    for yi, (seg, r) in zip(y, d.iterrows()):
        ax.text(r["won_p90"] + 6, yi, f"{r['won_p50']:.0f} / {r['won_p90']:.0f} days", va="center", color=INK_2)
    ax.set_yticks(y, d.index)
    ax.set_xlim(0, d["won_p90"].max() * 1.3)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Days from first stage to Closed Won")
    ax.legend(loc="upper right", ncols=3)
    ratio = d.loc["Large", "won_p50"] / d.loc["Micro", "won_p50"]
    _titles(fig, f"Large customers take {ratio:.0f} times longer to close than micro ones",
            "Won deals, median and p90 of the sales cycle by company size")
    _save(fig, path)


def partner_pareto(df: pd.DataFrame, path: Path) -> None:
    n80 = int(df["in_top_80pct"].sum())
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(1, len(df) + 1)
    ax.bar(x, df["share"], width=0.6, color=[BLUE if t else GREY for t in df["in_top_80pct"]])
    ax.plot(x, df["cumulative_share"], color=INK_2, linewidth=2, marker="o", markersize=4)
    ax.axhline(0.8, color=MUTED, linewidth=1)
    ax.text(0.5, 0.815, "80%", va="bottom", color=INK_2)
    ax.text(5.3, df["cumulative_share"].iloc[4] - 0.05, "Cumulative share", va="top", color=INK_2)
    ax.text(2.45, df["share"].iloc[1] + 0.01, "Share of each partner", va="bottom", color=INK_2)
    ax.set_xticks(x)
    ax.set_xlabel("Partners ranked by bookings")
    ax.yaxis.set_major_formatter(pct)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="x", visible=False)
    top = df.iloc[0]
    tail = df.loc[~df["in_top_80pct"], "share"].sum()
    _titles(fig, f"{n80} of {len(df)} partners bring 80% of partner bookings",
            f"The top partner alone is {top['share']:.0%}, more than the other {len(df) - n80} "
            f"outside the 80% group together ({tail:.0%})")
    _save(fig, path)


def seasonality(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    years = sorted(df["year"].unique())
    for year, color in zip(years, RAMP):
        d = df[df["year"] == year]
        ax.plot(d["month"], d["deals_created"], color=color, linewidth=2, marker="o", markersize=4,
                markeredgecolor=SURFACE)
        last = d.iloc[-1]
        ax.text(last["month"] + 0.15, last["deals_created"], str(year), va="center", color=INK_2)
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_ylim(0, df["deals_created"].max() * 1.15)
    ax.set_ylabel("Deals created")
    ax.grid(axis="x", visible=False)
    aug = df[df["month"] == 8]["created_index"].mean()
    _titles(fig, f"August is dead every year: about {aug:.0%} of an average month",
            "Deals created per month. Q1 and September-October are the busy windows, each year mostly above the one before")
    _save(fig, path)


def growth_ytd(df: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, col, yoy, label, fmt in [
        (axes[0], "deals_created", "deals_created_yoy", "Deals created, Jan-Sep", "{:,.0f}"),
        (axes[1], "bookings", "bookings_yoy", "Bookings (won amount), Jan-Sep", None),
    ]:
        x = np.arange(len(df))
        ax.bar(x, df[col], width=0.5, color=[GREY, GREY, BLUE])
        for xi, (_, r) in zip(x, df.iterrows()):
            value = fmt.format(r[col]) if fmt else f"{r[col] / 1e6:.2f}M"
            change = "" if pd.isna(r[yoy]) else f"\n{r[yoy]:+.0%} YoY"
            ax.text(xi, r[col] * 1.02, value + change, ha="center", va="bottom", color=INK_2)
        ax.set_xticks(x, df["year"].astype(str))
        ax.set_ylim(0, df[col].max() * 1.3)
        ax.set_title(label, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.grid(axis="x", visible=False)
        if not fmt:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M"))
    last = df.iloc[-1]
    _titles(fig, f"Bookings grow faster than deal creation: {last['bookings_yoy']:+.0%} vs {last['deals_created_yoy']:+.0%}",
            "Like for like January to September, because 2026 ends at the snapshot date")
    _save(fig, path, top=0.74)


def channel_mix(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    for ch, color in CHANNEL_COLORS.items():
        d = df[df["channel"] == ch]
        ax.plot(pd.to_datetime(d["quarter_start"]), d["share_of_quarter"], color=color, linewidth=2,
                marker="o", markersize=4, markeredgecolor=SURFACE)
        last = d.iloc[-1]
        ax.text(pd.to_datetime(last["quarter_start"]) + pd.Timedelta(days=20), last["share_of_quarter"],
                f"{ch} {last['share_of_quarter']:.0%}", va="center", color=INK_2)
    quarters = pd.to_datetime(sorted(df["quarter_start"].unique()))
    ax.set_xticks(quarters, [f"Q{q.quarter}\n{q.year}" if q.quarter == 1 else f"Q{q.quarter}" for q in quarters])
    ax.yaxis.set_major_formatter(pct)
    ax.set_ylim(0, 0.7)
    ax.set_ylabel("Share of deals created")
    ax.grid(axis="x", visible=False)
    p = df[df["channel"] == "Partner"]["share_of_quarter"]
    _titles(fig, f"Partners went from {p.iloc[0]:.0%} to {p.iloc[-1]:.0%} of new deals in under three years",
            "Share of deals created per quarter, by channel")
    _save(fig, path)


def cohorts(df: pd.DataFrame, path: Path) -> None:
    d = df.assign(cohort_month=pd.to_datetime(df["cohort_month"]))
    mature = d["open_share"] <= 0.25
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(d["cohort_month"], d["win_rate_closed"], color=GREY, linewidth=1.5)
    ax.plot(d.loc[mature, "cohort_month"], d.loc[mature, "win_rate_closed"], "o", color=BLUE, markersize=6,
            markeredgecolor=SURFACE, label="Mostly closed")
    ax.plot(d.loc[~mature, "cohort_month"], d.loc[~mature, "win_rate_closed"], "o", color=ORANGE, markersize=6,
            markeredgecolor=SURFACE, label="25% or more still open")
    for _, r in d[~mature].iterrows():
        ax.text(r["cohort_month"], r["win_rate_closed"] - 0.045, f"{r['open_share']:.0%} open",
                ha="center", color=INK_2, fontsize=9)
    ax.yaxis.set_major_formatter(pct)
    ax.set_ylim(0, 0.5)
    ax.set_ylabel("Win rate of closed deals")
    ax.legend(loc="lower left")
    ax.grid(axis="x", visible=False)
    avg = d.loc[mature, "win_rate_closed"].mean()
    _titles(fig, f"Mature cohorts win around {avg:.0%}; the youngest ones only look bad because they are still open",
            "Deals created each month and their win rate so far. Fast losses close first, so young cohorts read low")
    _save(fig, path)


def open_pipeline(df: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    y = np.arange(len(df))[::-1]
    ax.barh(y + 0.15, df["pipeline_amount"], height=0.28, color=GREY, label="Pipeline amount")
    ax.barh(y - 0.15, df["weighted_amount"], height=0.28, color=BLUE, label="Weighted by stage win rate")
    for yi, (_, r) in zip(y, df.iterrows()):
        ax.text(r["pipeline_amount"] + 8000, yi + 0.15,
                f"{r['open_deals']} deals, {r['stuck_deals']} stuck", va="center", color=INK_2, fontsize=9)
        ax.text(r["weighted_amount"] + 8000, yi - 0.15, f"p(win) {r['p_win_from_stage']:.0%}",
                va="center", color=INK_2, fontsize=9)
    ax.set_yticks(y, df["stage"])
    ax.xaxis.set_major_formatter(euro_k)
    ax.set_xlim(0, df["pipeline_amount"].max() * 1.35)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    total, weighted = df["pipeline_amount"].sum(), df["weighted_amount"].sum()
    _titles(fig, f"{total / 1e6:.2f}M of open pipeline is worth about {weighted / 1e6:.2f}M once weighted",
            "Open deals at 30 Sep 2026 by stage. Stuck = in the stage longer than 90% of past deals of the same size")
    _save(fig, path)


def lost_reasons(df: pd.DataFrame, path: Path) -> None:
    reasons = [("no_response", "No response"), ("not_a_fit", "Not a fit"), ("timing", "Timing"),
               ("no_budget", "No budget"), ("price", "Price"), ("competitor", "Competitor")]
    colors = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN]
    fig, ax = plt.subplots(figsize=(9, 3.8))
    y = np.arange(len(df))[::-1]
    left = np.zeros(len(df))
    for (col, label), color in zip(reasons, colors):
        ax.barh(y, df[col], left=left, height=0.55, color=color, label=label, edgecolor=SURFACE, linewidth=2)
        for yi, l, v in zip(y, left, df[col]):
            if v >= 0.12:
                ax.text(l + v / 2, yi, f"{v:.0%}", ha="center", va="center", color=_label_on(color), fontsize=9,
                        fontweight="bold")
        left += df[col].to_numpy()
    ax.set_yticks(y, [f"{s}\n{n:,} lost" for s, n in zip(df["stage_lost_at"], df["lost_deals"])])
    ax.xaxis.set_major_formatter(pct)
    ax.set_xlim(0, 1)
    ax.grid(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncols=6)
    late = df[df["stage_lost_at"].isin(["Proposal", "Negotiation"])]
    pc = (late["price"] + late["competitor"]) @ late["lost_deals"] / late["lost_deals"].sum()
    _titles(fig, f"Late-stage losses are about price and competitors ({pc:.0%}), early ones about silence",
            "Lost reason as share of the deals lost at each stage")
    _save(fig, path)


def model_calibration(calib: pd.DataFrame, metrics: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 0.7], [0, 0.7], color=BASELINE, linewidth=1)
    for (name, d), color in zip(calib.groupby("model", sort=False), [BLUE, ORANGE]):
        m = metrics.set_index("model").loc[name]
        ax.plot(d["mean_predicted"], d["observed_win_rate"], color=color, linewidth=2, marker="o",
                markersize=6, markeredgecolor=SURFACE,
                label=f"{name}  (AUC {m['roc_auc']:.3f}, Brier {m['brier']:.3f})")
    ax.set_xlim(0, 0.7)
    ax.set_ylim(0, 0.7)
    ax.xaxis.set_major_formatter(pct)
    ax.yaxis.set_major_formatter(pct)
    ax.set_xlabel("Predicted win probability")
    ax.set_ylabel("Observed win rate")
    ax.legend(loc="upper left", fontsize=9)
    _titles(fig, "The simple model is the better calibrated one",
            "Test set: deals created after 1 Oct 2025, in 8 equal bins")
    _save(fig, path, top=0.84)


def model_importance(imp: pd.DataFrame, path: Path) -> None:
    d = imp.sort_values("auc_drop_mean")
    fig, ax = plt.subplots(figsize=(8, 4))
    y = np.arange(len(d))
    ax.barh(y, d["auc_drop_mean"].clip(lower=0), height=0.5, color=[BLUE if v > 0.01 else GREY for v in d["auc_drop_mean"]])
    ax.errorbar(d["auc_drop_mean"].clip(lower=0), y, xerr=d["auc_drop_std"], fmt="none", ecolor=MUTED, elinewidth=1)
    ax.set_yticks(y, d["feature"])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Drop in test ROC AUC when the feature is shuffled")
    _titles(fig, "Channel and deal type carry almost all the signal",
            "Permutation importance, logistic regression, 20 repeats on the test set")
    _save(fig, path)


def forecast_backtest(backtest: pd.DataFrame, nxt: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(backtest) + 1)
    labels = list(backtest["quarter"]) + [nxt["quarter"]]
    ax.bar(x[:-1], backtest["actual"], width=0.5, color=GREY, label="Actual bookings")
    ax.plot(x[:-1], backtest["forecast"], "o", color=BLUE, markersize=8, markeredgecolor=SURFACE,
            label="Forecast made at the start of the quarter")
    ax.vlines(x[-1], nxt["low"], nxt["high"], color=BLUE, linewidth=2, alpha=0.4)
    ax.plot(x[-1], nxt["forecast"], "o", color=BLUE, markersize=8, markeredgecolor=SURFACE)
    ax.text(x[-1] + 0.12, nxt["forecast"], f"{nxt['forecast'] / 1000:,.0f}k\n({nxt['low'] / 1000:,.0f}k to {nxt['high'] / 1000:,.0f}k)",
            va="center", color=INK_2, fontsize=9)
    for xi, (_, r) in zip(x, backtest.iterrows()):
        ax.text(xi, max(r["actual"], r["forecast"]) + 30000, f"{r['error_pct']:+.0%}", ha="center", va="bottom",
                color=INK_2, fontsize=9)
    ax.set_xticks(x, labels)
    ax.set_xlim(-0.6, len(x) - 0.1)
    ax.yaxis.set_major_formatter(euro_k)
    ax.set_ylim(0, max(backtest["actual"].max(), nxt["high"]) * 1.15)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    under = int((backtest["error_pct"] > 0).sum())
    _titles(fig, f"Q4 2026 bookings: about {nxt['forecast'] / 1000:,.0f}k, with more upside than downside",
            f"Backtest error shown above each quarter. The method came in low {under} times out of {len(backtest)}")
    _save(fig, path)
