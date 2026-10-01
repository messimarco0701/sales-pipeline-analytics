"""
Quarterly bookings forecast: how much will we book next quarter?

Bookings in a quarter come from two places, and they behave differently:

  1. Deals already open when the quarter starts. Here we know the deal, its stage and its amount,
     so the forecast is the open pipeline weighted by the historical rate at which a deal open in
     that stage at a quarter end was won within the following quarter (amount weighted, because
     big deals convert less and close slower).
  2. Deals created and won inside the quarter. They do not exist yet, so the best guess is a
     seasonal naive run rate: what the same quarter delivered last year, scaled by how much deal
     creation has grown year over year in the latest quarter.

The backtest replays the method at every past quarter end using only what was known on that
date (stage rates come only from earlier snapshots whose next quarter had already finished).
The forecast range is the point estimate stretched by the smallest and largest error the method
made in the backtest, so the range reflects how wrong this method has actually been, not a
textbook assumption.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def quarter_start(ts: pd.Timestamp) -> pd.Timestamp:
    return ts.to_period("Q").start_time


def stage_rates(snapshots: pd.DataFrame, before: pd.Timestamp) -> pd.Series:
    """Amount-weighted P(won within next quarter | open in stage at quarter end), from fully observed snapshots."""
    known = snapshots[(snapshots["as_of"] + pd.offsets.QuarterEnd(1) <= before)
                      & snapshots["won_next_quarter"].notna()]
    won_amount = known["amount"].where(known["won_next_quarter"].astype(bool), 0)
    return won_amount.groupby(known["stage"]).sum() / known.groupby("stage")["amount"].sum()


def forecast_quarter(as_of: pd.Timestamp, snapshots: pd.DataFrame, quarterly: pd.DataFrame,
                     deals: pd.DataFrame) -> dict:
    target = as_of + pd.Timedelta(days=1)                      # first day of the quarter to forecast
    rates = stage_rates(snapshots, before=as_of)
    open_now = snapshots[snapshots["as_of"] == as_of]
    pipeline_part = (open_now["amount"] * open_now["stage"].map(rates).fillna(0)).sum()

    same_q_last_year = target - pd.DateOffset(years=1)
    run_rate_ly = quarterly.loc[quarterly["quarter_start"] == same_q_last_year,
                                "created_and_won_in_quarter"]
    # Growth of deal creation in the last finished quarter vs the same quarter a year before
    created_q = deals.groupby(deals["created_date"].dt.to_period("Q")).size()
    last_q = as_of.to_period("Q")
    growth = created_q.get(last_q, float("nan")) / created_q.get(last_q - 4, float("nan"))
    run_rate_part = float(run_rate_ly.iloc[0]) * growth if len(run_rate_ly) else float("nan")

    actual = quarterly.loc[quarterly["quarter_start"] == target, "bookings"]
    return {
        "quarter": f"{target.year}-Q{target.quarter}",
        "as_of": as_of.date(),
        "open_deals": len(open_now),
        "open_pipeline": open_now["amount"].sum(),
        "from_open_pipeline": pipeline_part,
        "run_rate_new_deals": run_rate_part,
        "creation_growth": growth,
        "forecast": pipeline_part + run_rate_part,
        "actual": float(actual.iloc[0]) if len(actual) else float("nan"),
    }


@dataclass
class ForecastReport:
    backtest: pd.DataFrame
    next_quarter: dict
    stage_rates_now: pd.Series


def run(snapshots: pd.DataFrame, quarterly: pd.DataFrame, deals: pd.DataFrame) -> ForecastReport:
    snapshots = snapshots.assign(as_of=pd.to_datetime(snapshots["as_of"]))
    quarterly = quarterly.assign(quarter_start=pd.to_datetime(quarterly["quarter_start"]))
    deals = deals.assign(created_date=pd.to_datetime(deals["created_date"]))
    as_of_dates = sorted(snapshots["as_of"].unique())
    snapshot = as_of_dates[-1]

    rows = []
    for as_of in as_of_dates[:-1]:
        row = forecast_quarter(pd.Timestamp(as_of), snapshots, quarterly, deals)
        if pd.notna(row["forecast"]):
            rows.append(row)
    backtest = pd.DataFrame(rows)
    backtest["error_pct"] = (backtest["actual"] - backtest["forecast"]) / backtest["forecast"]

    nxt = forecast_quarter(pd.Timestamp(snapshot), snapshots, quarterly, deals)
    nxt["low"] = nxt["forecast"] * (1 + backtest["error_pct"].min())
    nxt["high"] = nxt["forecast"] * (1 + backtest["error_pct"].max())
    nxt["backtest_mape"] = backtest["error_pct"].abs().mean()
    return ForecastReport(backtest, nxt, stage_rates(snapshots, before=pd.Timestamp(snapshot)))
