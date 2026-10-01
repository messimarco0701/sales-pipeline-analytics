"""
The generator plants patterns on purpose (see src/generate_data.py). If the SQL is right, it finds
them. These tests also guard the two things that would quietly make the model look better than it
is: leaky features and a train/test split that mixes up time.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import analysis  # noqa: E402
import win_model  # noqa: E402


@pytest.fixture(scope="module")
def r():
    return analysis.run_all()


def test_channel_win_rates_are_ordered_and_clearly_separated(r):
    ch = r["win_rates"].query("dimension == 'channel'").set_index("value")
    assert ch.loc["Referral", "win_rate"] > ch.loc["Partner", "win_rate"] > ch.loc["Direct", "win_rate"]
    # Not just ordered: the 95% intervals do not overlap
    assert ch.loc["Referral", "ci_low"] > ch.loc["Partner", "ci_high"]
    assert ch.loc["Partner", "ci_low"] > ch.loc["Direct", "ci_high"]


def test_upsell_converts_better_than_new_business(r):
    dt = r["win_rates"].query("dimension == 'deal_type'").set_index("value")
    assert dt.loc["Upsell", "ci_low"] > dt.loc["New business", "ci_high"]


def test_august_is_the_quietest_month_every_full_year(r):
    s = r["seasonality"]
    for year in (2024, 2025):
        months = s[s["year"] == year].set_index("month")["deals_created"]
        assert months.idxmin() == 8, year


def test_partners_follow_a_pareto_curve(r):
    pp = r["partner_pareto"]
    assert pp["in_top_80pct"].sum() <= len(pp) / 2
    assert pp["share"].iloc[0] > 0.2
    assert pp["cumulative_share"].is_monotonic_increasing


def test_partner_share_rises_every_year(r):
    assert r["yoy_ytd"]["partner_share"].is_monotonic_increasing


def test_bigger_customers_take_longer_to_close(r):
    cycle = r["sales_cycle"].set_index("size_segment")["won_p50"]
    assert cycle["Micro"] < cycle["Small"] < cycle["Medium"] < cycle["Large"]


def test_funnel_only_shrinks(r):
    assert r["funnel"]["deals_reached"].is_monotonic_decreasing


def test_open_pipeline_covers_every_open_deal_once(r):
    deals, op = r["deals"], r["open_pipeline"]
    assert len(op) == int((~deals["is_closed"]).sum())
    assert op["deal_id"].is_unique


def test_model_uses_no_leaky_features():
    assert not set(win_model.FEATURES) & win_model.LEAKY


def test_time_split_trains_only_on_the_past(r):
    df = win_model.add_features(r["deals"])
    train, test = win_model.time_split(df)
    cutoff = pd.Timestamp(win_model.CUTOFF)
    assert train["close_date"].max() < cutoff <= test["created_date"].min()
    assert train["created_date"].max() < test["created_date"].min()
    assert not set(train["deal_id"]) & set(test["deal_id"])
