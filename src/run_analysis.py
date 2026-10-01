"""
Runs the whole analysis end to end:
  1. every SQL file in sql/ on DuckDB, results saved to reports/tables/
  2. the win probability model (time-based split) and the scoring of open deals
  3. the Q4 bookings forecast with its backtest
  4. all charts, saved to reports/figures/

Run it with:  python src/run_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis  # noqa: E402
import charts  # noqa: E402
import forecast  # noqa: E402
import win_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "reports" / "tables"
FIGURES = ROOT / "reports" / "figures"


def main() -> None:
    if not (ROOT / "data" / "fact_deals.csv").exists():
        sys.exit("No data found. Run  python src/generate_data.py  first.")
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    r = analysis.run_all()
    for name, df in r.items():
        if name not in ("deals", "pipeline_snapshots"):
            df.to_csv(TABLES / f"{name}.csv", index=False)

    model = win_model.run(r["deals"], r["open_pipeline"])
    model.metrics.to_csv(TABLES / "model_metrics.csv", index=False)
    model.calibration.to_csv(TABLES / "model_calibration.csv", index=False)
    model.importance.to_csv(TABLES / "model_permutation_importance.csv", index=False)
    model.coefficients.to_csv(TABLES / "model_coefficients.csv", index=False)
    model.open_scored.to_csv(TABLES / "open_deals_scored.csv", index=False)

    fc = forecast.run(r["pipeline_snapshots"], r["quarterly_bookings"], r["deals"])
    fc.backtest.to_csv(TABLES / "forecast_backtest.csv", index=False)
    pd.DataFrame([fc.next_quarter]).to_csv(TABLES / "forecast_next_quarter.csv", index=False)

    charts.funnel(r["funnel"], FIGURES / "01_funnel.png")
    charts.win_rates(r["win_rates"], FIGURES / "02_win_rates.png")
    charts.sales_cycle(r["sales_cycle"], FIGURES / "03_sales_cycle.png")
    charts.partner_pareto(r["partner_pareto"], FIGURES / "04_partner_pareto.png")
    charts.seasonality(r["seasonality"], FIGURES / "05_seasonality.png")
    charts.growth_ytd(r["yoy_ytd"], FIGURES / "06_growth_ytd.png")
    charts.channel_mix(r["channel_mix"], FIGURES / "07_channel_mix.png")
    charts.cohorts(r["cohorts"], FIGURES / "08_cohorts.png")
    charts.open_pipeline(r["pipeline_by_stage"], FIGURES / "09_open_pipeline.png")
    charts.lost_reasons(r["lost_reasons"], FIGURES / "10_lost_reasons.png")
    charts.model_calibration(model.calibration, model.metrics, FIGURES / "11_model_calibration.png")
    charts.model_importance(model.importance, FIGURES / "12_model_importance.png")
    charts.forecast_backtest(fc.backtest, fc.next_quarter, FIGURES / "13_forecast_backtest.png")

    report(r, model, fc)


def report(r: dict, model: win_model.ModelReport, fc: forecast.ForecastReport) -> None:
    deals = r["deals"]
    print(f"Deals: {len(deals):,}   closed: {int(deals.is_closed.sum()):,}   "
          f"won: {int(deals.is_won.sum()):,}   open at snapshot: {int((~deals.is_closed).sum())}\n")

    wr = r["win_rates"]
    print("Win rate by channel (closed deals, 95% Wilson interval)")
    print(wr[wr.dimension == "channel"][["value", "closed_deals", "win_rate", "ci_low", "ci_high"]]
          .to_string(index=False))

    ytd = r["yoy_ytd"]
    print("\nJan-Sep like for like")
    print(ytd[["year", "deals_created", "deals_created_yoy", "bookings", "bookings_yoy", "partner_share"]]
          .to_string(index=False, float_format=lambda x: f"{x:,.3f}" if abs(x) < 10 else f"{x:,.0f}"))

    pp = r["partner_pareto"]
    print(f"\nPartners making 80% of partner bookings: {int(pp.in_top_80pct.sum())} of {len(pp)}"
          f"   (top partner: {pp.share.iloc[0]:.1%})")

    pbs = r["pipeline_by_stage"]
    print(f"\nOpen pipeline: {pbs.pipeline_amount.sum():,.0f}   weighted: {pbs.weighted_amount.sum():,.0f}   "
          f"stuck deals: {int(pbs.stuck_deals.sum())} ({pbs.stuck_amount.sum():,.0f})")

    print(f"\nWin model, trained on {model.train_rows:,} deals closed before "
          f"{win_model.CUTOFF}, tested on {model.test_rows:,} created after it")
    print(model.metrics.to_string(index=False))

    print("\nForecast backtest")
    print(fc.backtest[["quarter", "forecast", "actual", "error_pct"]]
          .to_string(index=False, float_format=lambda x: f"{x:+.3f}" if abs(x) < 10 else f"{x:,.0f}"))
    n = fc.next_quarter
    print(f"\n{n['quarter']} bookings forecast: {n['forecast']:,.0f}   range {n['low']:,.0f} to {n['high']:,.0f}"
          f"   (open pipeline part {n['from_open_pipeline']:,.0f}, new deals part {n['run_rate_new_deals']:,.0f})")
    print("\nTables in reports/tables/, charts in reports/figures/")


if __name__ == "__main__":
    main()
