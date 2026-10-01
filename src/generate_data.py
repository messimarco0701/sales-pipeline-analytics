"""
Generates a synthetic B2B sales dataset shaped like a CRM export, as a small star schema.

The numbers are invented, but the patterns are the ones I see in real pipelines:
seasonality (busy Q1 and autumn, dead August), channels that convert at different
rates, partners that follow a Pareto curve, bigger customers taking longer to close,
deals that die at every stage for different reasons.

Patterns are planted on purpose so the analysis has something real to find,
and so the findings can be checked against what was planted.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 7
START = date(2024, 1, 1)
SNAPSHOT = date(2026, 9, 30)
N_COMPANIES = 2600
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

STAGES = ["Discovery", "Qualified", "Proposal", "Negotiation"]
REGIONS = {"Nord-Ovest": 0.34, "Nord-Est": 0.24, "Centro": 0.22, "Sud e Isole": 0.20}
SECTORS = ["Manufacturing", "Retail", "Logistics", "Professional services", "Healthcare",
           "Construction", "Food & beverage", "IT services", "Finance", "Hospitality"]
PRODUCTS = {"Core": (0.50, 60), "Flex": (0.35, 95), "Premium": (0.15, 150)}  # share, fee per employee
LOST_REASONS = {
    "Discovery": {"No response": 0.5, "Not a fit": 0.3, "Timing": 0.2},
    "Qualified": {"No budget": 0.45, "Timing": 0.3, "No response": 0.25},
    "Proposal": {"Price": 0.45, "Competitor": 0.3, "No budget": 0.25},
    "Negotiation": {"Price": 0.4, "Competitor": 0.45, "Timing": 0.15},
}
# Monthly weight of new opportunities: budgets are set in Q1, renewals in autumn, August is empty
SEASONALITY = {1: 1.35, 2: 1.25, 3: 1.15, 4: 0.95, 5: 0.95, 6: 0.85,
               7: 0.70, 8: 0.30, 9: 1.30, 10: 1.40, 11: 1.20, 12: 0.60}

fake = Faker("it_IT")
Faker.seed(SEED)
rng = random.Random(SEED)


def pick(weights: dict):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def size_segment(employees: int) -> str:
    if employees < 10:
        return "Micro"
    if employees < 50:
        return "Small"
    if employees < 250:
        return "Medium"
    return "Large"


def build_dimensions():
    owners = pd.DataFrame([
        {"owner_id": i + 1, "owner_name": name, "team": team}
        for i, (name, team) in enumerate([
            ("Giulia Rinaldi", "Direct Sales"), ("Luca Moretti", "Direct Sales"),
            ("Sara Bellini", "Direct Sales"), ("Andrea Testa", "Direct Sales"),
            ("Elena Ferri", "Partner Sales"), ("Davide Greco", "Partner Sales"),
            ("Marta Colombo", "Partner Sales"), ("Paolo Riva", "Partner Sales"),
        ])
    ])

    partner_types = ["Payroll consultant", "Accounting firm", "Trade association", "Broker"]
    partners = []
    for i in range(18):
        partners.append({
            "partner_id": i + 1,
            "partner_name": f"{rng.choice(['Studio', 'Gruppo', 'Rete', 'Consulenti'])} {fake.last_name()}",
            "partner_type": partner_types[i % 4],
            "region": pick(REGIONS),
            "onboarded_date": (START + timedelta(days=rng.randint(-400, 500))).isoformat(),
            # Pareto: a few partners bring most of the business
            "_weight": 1 / (i + 1) ** 0.9,
        })

    companies = []
    for i in range(N_COMPANIES):
        employees = int(min(max(rng.lognormvariate(3.4, 1.3), 3), 4000))
        companies.append({
            "company_id": i + 1,
            "company_name": f"{fake.last_name()} {rng.choice(SECTORS).split()[0]} {rng.choice(['S.r.l.', 'S.p.A.'])}",
            "sector": rng.choice(SECTORS),
            "region": pick(REGIONS),
            "employees": employees,
            "size_segment": size_segment(employees),
        })
    return owners, partners, companies


def creation_dates(n: int) -> list[date]:
    """Draw dates with seasonality and around 20% year over year growth."""
    days = (SNAPSHOT - START).days
    weights = []
    for d in range(days + 1):
        day = START + timedelta(days=d)
        growth = 1.2 ** ((day - START).days / 365)
        weekday = 0.15 if day.weekday() >= 5 else 1.0
        weights.append(SEASONALITY[day.month] * growth * weekday)
    picks = rng.choices(range(days + 1), weights=weights, k=n)
    return sorted(START + timedelta(days=p) for p in picks)


def win_probability(channel: str, segment: str, deal_type: str, product: str) -> float:
    base = {"Direct": 0.20, "Partner": 0.31, "Referral": 0.44}[channel]
    base *= {"Micro": 0.9, "Small": 1.05, "Medium": 1.1, "Large": 0.8}[segment]
    base *= 1.6 if deal_type == "Upsell" else 1.0
    base *= {"Core": 1.05, "Flex": 1.0, "Premium": 0.85}[product]
    return min(base, 0.85)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    owners, partners, companies = build_dimensions()
    partner_ids = [p["partner_id"] for p in partners]
    partner_w = [p["_weight"] for p in partners]
    direct_owners = owners.query("team == 'Direct Sales'").owner_id.tolist()
    partner_owners = owners.query("team == 'Partner Sales'").owner_id.tolist()

    deals, history = [], []
    won_customers: dict[int, date] = {}
    dates = creation_dates(4200)

    for n, created in enumerate(dates):
        company = rng.choice(companies)
        cid = company["company_id"]
        deal_type = "Upsell" if cid in won_customers and won_customers[cid] < created else "New business"

        # Partner channel grows over time: 30% of deals in 2024, close to 45% by 2026
        partner_share = 0.30 + 0.15 * (created - START).days / (SNAPSHOT - START).days
        channel = rng.choices(["Partner", "Direct", "Referral"],
                              weights=[partner_share, 0.85 - partner_share, 0.15])[0]
        partner_id = rng.choices(partner_ids, weights=partner_w)[0] if channel == "Partner" else None
        owner_id = rng.choice(partner_owners if channel == "Partner" else direct_owners)
        product = pick({k: v[0] for k, v in PRODUCTS.items()})
        segment = company["size_segment"]

        covered = company["employees"] if deal_type == "New business" else max(3, company["employees"] // 3)
        amount = max(covered * PRODUCTS[product][1] * rng.uniform(0.8, 1.2), 1200)
        amount = round(amount, -1)

        p_win = win_probability(channel, segment, deal_type, product)
        # Each stage is passed with the same probability, so that the product equals p_win
        p_step = p_win ** (1 / 5)
        cycle = {"Micro": 35, "Small": 60, "Medium": 95, "Large": 150}[segment]
        cycle *= 0.6 if deal_type == "Upsell" else 1.0

        current = created
        stage_reached, outcome, close_date = None, None, None
        for i, stage in enumerate(STAGES):
            stage_days = max(1, int(rng.expovariate(1 / (cycle / 5))))
            history.append({"deal_id": n + 1, "stage": stage, "entered_date": current})
            stage_reached = stage
            next_date = current + timedelta(days=stage_days)
            if next_date > SNAPSHOT:
                break  # still open at snapshot
            current = next_date
            history[-1]["exited_date"] = current
            if rng.random() > p_step:
                outcome, close_date = "Closed Lost", current
                break
        else:
            closing_days = max(1, int(rng.expovariate(1 / (cycle / 5))))
            if current + timedelta(days=closing_days) <= SNAPSHOT:
                close_date = current + timedelta(days=closing_days)
                outcome = "Closed Won" if rng.random() < p_step else "Closed Lost"
                if outcome == "Closed Lost":
                    stage_reached = "Negotiation"

        if outcome:
            history.append({"deal_id": n + 1, "stage": outcome, "entered_date": close_date})
        if outcome == "Closed Won":
            won_customers.setdefault(cid, close_date)

        deals.append({
            "deal_id": n + 1,
            "deal_name": f"{company['company_name'].rsplit(' ', 1)[0].upper()} | {product.upper()} | {created.year}",
            "company_id": cid,
            "owner_id": owner_id,
            "partner_id": partner_id,
            "channel": channel,
            "deal_type": deal_type,
            "product": product,
            "created_date": created,
            "close_date": close_date,
            "stage": outcome or stage_reached,
            "last_open_stage": stage_reached,
            "is_closed": outcome is not None,
            "is_won": outcome == "Closed Won",
            "lost_reason": pick(LOST_REASONS[stage_reached]) if outcome == "Closed Lost" else None,
            "employees_covered": covered,
            "amount": amount,
        })

    pd.DataFrame(deals).astype({"partner_id": "Int64"}).to_csv(DATA_DIR / "fact_deals.csv", index=False)
    pd.DataFrame(history).to_csv(DATA_DIR / "fact_stage_history.csv", index=False)
    pd.DataFrame(companies).to_csv(DATA_DIR / "dim_company.csv", index=False)
    pd.DataFrame(partners).drop(columns="_weight").to_csv(DATA_DIR / "dim_partner.csv", index=False)
    owners.to_csv(DATA_DIR / "dim_owner.csv", index=False)

    df = pd.DataFrame(deals)
    closed = df[df.is_closed]
    print(f"Deals: {len(df)}   closed: {len(closed)}   won: {int(df.is_won.sum())}   "
          f"open: {int((~df.is_closed).sum())}")
    print("Win rate by channel:")
    print(closed.groupby("channel").is_won.mean().round(3).to_string())


if __name__ == "__main__":
    main()
