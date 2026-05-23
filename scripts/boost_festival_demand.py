"""
Tamil Nadu Festival Demand Booster
====================================
Adjusts demand in data/clean.json to be realistic around major Tamil Nadu festivals.
Also recomputes all lag and rolling features so the ML features stay consistent.

Festivals covered (2023 + 2024):
  - Pongal / Thai Pongal         (Jan 14, 4-day festival Jan 13-17)
  - Tamil New Year (Puthandu)     (Apr 14)
  - Vinayagar Chaturthi           (Aug 19 2023, Sep 7 2024)
  - Navaratri                     (Oct 15-24 2023, Oct 3-12 2024)
  - Diwali (Deepavali)            (Nov 12 2023, Nov 1 2024)
  - Karthigai Deepam              (Nov 27 2023, Dec 15 2024)
  - Ramzan (Eid al-Fitr)          (Apr 22 2023, Apr 10 2024)

Boost logic:
  - Products with a strong affinity to the festival get a larger multiplier
  - Boost window: ramp up 5 days before, peak on main days, taper 3 days after
  - Unit price is slightly raised on festival peak days (+3-6%) for key items
"""

import json
import math
import random
import sys
from datetime import date, timedelta
from collections import defaultdict

random.seed(42)  # reproducible

DATA_PATH = "data/clean.json"


# ---------------------------------------------------------------------------
# Festival definitions
# ---------------------------------------------------------------------------

# Each festival: (name, [main_days as date], pre_days, post_days)
# Main days = highest boost; ramp starts pre_days before, tapers post_days after

FESTIVALS = [
    # --- 2023 ---
    {
        "name": "Pongal 2023",
        "main_dates": [date(2023, 1, 13), date(2023, 1, 14), date(2023, 1, 15), date(2023, 1, 16)],
        "pre_days": 7,
        "post_days": 3,
        "product_multipliers": {
            # PONGAL items: BIG boost
            "PONGAL001": 4.5,   # Jaggery — central to Pongal dish
            "PONGAL002": 5.0,   # Sugarcane — sold on streets, gifted
            "PONGAL003": 4.0,   # Moong Dal — used in sweet pongal
            "RICE001":   3.5,   # Ponni Raw Rice — the main offering
            "RICE002":   2.5,   # Idli Rice — moderate boost
            "SPICE001":  2.5,   # Turmeric — used in rituals
            "SWEET003":  3.0,   # Ghee — poured into the pongal pot
            "OIL001":    2.0,   # Coconut Oil — cooking
            "OIL002":    2.0,   # Gingelly Oil — traditional use
            "DAL001":    1.8,   # Toor Dal — general cooking boost
            "SWEET002":  2.0,   # Cashew Nuts — sweet pongal garnish
            "SWEET001":  1.8,   # Besan — sweets
            "NEEM001":   6.0,   # Neem Leaves — ritual, Kanu Pongal decoration
            "TEA001":    1.5,
            "COFFEE001": 1.5,
            "MANGO001":  1.5,
            "SOAP001":   1.3,   # House-cleaning before festival
            "SOAP002":   1.3,
        },
        "price_bump_products": ["PONGAL001", "PONGAL002", "PONGAL003", "SWEET003", "SWEET002"],
        "price_bump_pct": 0.05,
    },
    {
        "name": "Tamil New Year 2023",
        "main_dates": [date(2023, 4, 14)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.5,
            "RICE002":   2.0,
            "DAL001":    2.0,
            "SWEET003":  2.5,   # Ghee
            "SWEET002":  2.5,   # Cashews
            "SWEET001":  2.0,
            "SPICE001":  2.0,
            "SPICE002":  1.8,
            "SPICE003":  1.8,
            "OIL001":    1.8,
            "OIL002":    1.8,
            "MANGO001":  3.0,   # Mango is the Tamil New Year fruit!
            "NEEM001":   4.0,   # Neem-mango ritual
            "SOAP001":   1.5,
            "SOAP002":   1.5,
            "TEA001":    1.5,
            "COFFEE001": 1.5,
        },
        "price_bump_products": ["MANGO001", "NEEM001", "SWEET003"],
        "price_bump_pct": 0.04,
    },
    {
        "name": "Ramzan 2023",
        "main_dates": [date(2023, 4, 22), date(2023, 4, 23)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.0,
            "DAL001":    2.5,
            "SPICE002":  2.0,
            "SPICE003":  1.8,
            "SWEET003":  2.0,   # Ghee for biryani
            "SWEET002":  2.0,   # Cashews for sweets
            "SWEET001":  2.0,   # Besan for halwa
        },
        "price_bump_products": ["SWEET003", "SWEET002"],
        "price_bump_pct": 0.03,
    },
    {
        "name": "Vinayagar Chaturthi 2023",
        "main_dates": [date(2023, 8, 19), date(2023, 8, 20)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "SWEET001":  3.0,   # Besan — Kolukattai/Modak
            "SWEET002":  2.5,   # Cashews
            "SWEET003":  2.5,   # Ghee
            "PONGAL001": 2.5,   # Jaggery — for kozhukattai
            "OIL001":    2.0,
            "RICE001":   2.0,
            "DAL001":    1.8,
            "BANANA":    3.0,   # not in dataset but...
        },
        "price_bump_products": ["SWEET001", "SWEET002", "SWEET003", "PONGAL001"],
        "price_bump_pct": 0.04,
    },
    {
        "name": "Navaratri 2023",
        "main_dates": [
            date(2023, 10, 15), date(2023, 10, 16), date(2023, 10, 17),
            date(2023, 10, 18), date(2023, 10, 19), date(2023, 10, 20),
            date(2023, 10, 21), date(2023, 10, 22), date(2023, 10, 23),
        ],
        "pre_days": 4,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.0,
            "RICE002":   1.8,
            "DAL001":    2.0,
            "SPICE001":  2.0,
            "SWEET001":  2.5,
            "SWEET002":  2.5,
            "SWEET003":  2.0,
            "OIL001":    1.8,
            "OIL002":    2.0,
            "PONGAL001": 2.0,
            "SOAP001":   1.4,
            "SOAP002":   1.4,
        },
        "price_bump_products": ["SWEET002", "SWEET003"],
        "price_bump_pct": 0.03,
    },
    {
        "name": "Diwali 2023",
        "main_dates": [date(2023, 11, 12), date(2023, 11, 13)],
        "pre_days": 7,
        "post_days": 3,
        "product_multipliers": {
            "SWEET001":  4.0,   # Besan — murukku, halwa
            "SWEET002":  4.5,   # Cashews — kaju katli, gift boxes
            "SWEET003":  4.0,   # Ghee — essential for mithai
            "PONGAL001": 3.0,   # Jaggery
            "SOAP001":   2.5,   # New clothes, bathing rituals
            "SOAP002":   2.5,
            "OIL001":    2.0,
            "OIL002":    2.5,   # Gingelly oil — Diwali head-bath tradition!
            "RICE001":   2.0,
            "SPICE001":  1.8,
            "TEA001":    1.5,
            "COFFEE001": 1.5,
        },
        "price_bump_products": ["SWEET001", "SWEET002", "SWEET003", "PONGAL001"],
        "price_bump_pct": 0.06,
    },
    {
        "name": "Karthigai Deepam 2023",
        "main_dates": [date(2023, 11, 27)],
        "pre_days": 4,
        "post_days": 1,
        "product_multipliers": {
            "OIL001":    3.5,   # Coconut oil — lamps
            "OIL002":    3.5,   # Gingelly oil — lamps
            "RICE001":   1.8,
            "SWEET003":  2.0,   # Ghee — lamps
            "SWEET001":  1.5,
            "PONGAL001": 1.8,
        },
        "price_bump_products": ["OIL001", "OIL002"],
        "price_bump_pct": 0.05,
    },
    # --- 2024 ---
    {
        "name": "Pongal 2024",
        "main_dates": [date(2024, 1, 13), date(2024, 1, 14), date(2024, 1, 15), date(2024, 1, 16)],
        "pre_days": 7,
        "post_days": 3,
        "product_multipliers": {
            "PONGAL001": 4.5,
            "PONGAL002": 5.0,
            "PONGAL003": 4.0,
            "RICE001":   3.5,
            "RICE002":   2.5,
            "SPICE001":  2.5,
            "SWEET003":  3.0,
            "OIL001":    2.0,
            "OIL002":    2.0,
            "DAL001":    1.8,
            "SWEET002":  2.0,
            "SWEET001":  1.8,
            "NEEM001":   6.0,
            "TEA001":    1.5,
            "COFFEE001": 1.5,
            "MANGO001":  1.5,
            "SOAP001":   1.3,
            "SOAP002":   1.3,
        },
        "price_bump_products": ["PONGAL001", "PONGAL002", "PONGAL003", "SWEET003", "SWEET002"],
        "price_bump_pct": 0.05,
    },
    {
        "name": "Tamil New Year 2024",
        "main_dates": [date(2024, 4, 14)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.5,
            "RICE002":   2.0,
            "DAL001":    2.0,
            "SWEET003":  2.5,
            "SWEET002":  2.5,
            "SWEET001":  2.0,
            "SPICE001":  2.0,
            "SPICE002":  1.8,
            "SPICE003":  1.8,
            "OIL001":    1.8,
            "OIL002":    1.8,
            "MANGO001":  3.0,
            "NEEM001":   4.0,
            "SOAP001":   1.5,
            "SOAP002":   1.5,
            "TEA001":    1.5,
            "COFFEE001": 1.5,
        },
        "price_bump_products": ["MANGO001", "NEEM001", "SWEET003"],
        "price_bump_pct": 0.04,
    },
    {
        "name": "Ramzan 2024",
        "main_dates": [date(2024, 4, 10), date(2024, 4, 11)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.0,
            "DAL001":    2.5,
            "SPICE002":  2.0,
            "SPICE003":  1.8,
            "SWEET003":  2.0,
            "SWEET002":  2.0,
            "SWEET001":  2.0,
        },
        "price_bump_products": ["SWEET003", "SWEET002"],
        "price_bump_pct": 0.03,
    },
    {
        "name": "Vinayagar Chaturthi 2024",
        "main_dates": [date(2024, 9, 7), date(2024, 9, 8)],
        "pre_days": 5,
        "post_days": 2,
        "product_multipliers": {
            "SWEET001":  3.0,
            "SWEET002":  2.5,
            "SWEET003":  2.5,
            "PONGAL001": 2.5,
            "OIL001":    2.0,
            "RICE001":   2.0,
            "DAL001":    1.8,
        },
        "price_bump_products": ["SWEET001", "SWEET002", "SWEET003", "PONGAL001"],
        "price_bump_pct": 0.04,
    },
    {
        "name": "Navaratri 2024",
        "main_dates": [
            date(2024, 10, 3), date(2024, 10, 4), date(2024, 10, 5),
            date(2024, 10, 6), date(2024, 10, 7), date(2024, 10, 8),
            date(2024, 10, 9), date(2024, 10, 10), date(2024, 10, 11),
        ],
        "pre_days": 4,
        "post_days": 2,
        "product_multipliers": {
            "RICE001":   2.0,
            "RICE002":   1.8,
            "DAL001":    2.0,
            "SPICE001":  2.0,
            "SWEET001":  2.5,
            "SWEET002":  2.5,
            "SWEET003":  2.0,
            "OIL001":    1.8,
            "OIL002":    2.0,
            "PONGAL001": 2.0,
            "SOAP001":   1.4,
            "SOAP002":   1.4,
        },
        "price_bump_products": ["SWEET002", "SWEET003"],
        "price_bump_pct": 0.03,
    },
    {
        "name": "Diwali 2024",
        "main_dates": [date(2024, 11, 1), date(2024, 11, 2)],
        "pre_days": 7,
        "post_days": 3,
        "product_multipliers": {
            "SWEET001":  4.0,
            "SWEET002":  4.5,
            "SWEET003":  4.0,
            "PONGAL001": 3.0,
            "SOAP001":   2.5,
            "SOAP002":   2.5,
            "OIL001":    2.0,
            "OIL002":    2.5,
            "RICE001":   2.0,
            "SPICE001":  1.8,
            "TEA001":    1.5,
            "COFFEE001": 1.5,
        },
        "price_bump_products": ["SWEET001", "SWEET002", "SWEET003", "PONGAL001"],
        "price_bump_pct": 0.06,
    },
    {
        "name": "Karthigai Deepam 2024",
        "main_dates": [date(2024, 12, 15)],
        "pre_days": 4,
        "post_days": 1,
        "product_multipliers": {
            "OIL001":    3.5,
            "OIL002":    3.5,
            "RICE001":   1.8,
            "SWEET003":  2.0,
            "SWEET001":  1.5,
            "PONGAL001": 1.8,
        },
        "price_bump_products": ["OIL001", "OIL002"],
        "price_bump_pct": 0.05,
    },
]


# ---------------------------------------------------------------------------
# Build a dict: (stock_code, date_str) -> multiplier and price_bump
# ---------------------------------------------------------------------------

def build_boost_map(festivals):
    """For each (stock_code, date), compute the overall quantity multiplier and price bump."""
    quantity_boost = defaultdict(float)  # additive multiplier (max across festivals)
    price_bump = defaultdict(float)

    for fest in festivals:
        main_dates = fest["main_dates"]
        pre = fest["pre_days"]
        post = fest["post_days"]
        product_mults = fest["product_multipliers"]
        pb_products = fest.get("price_bump_products", [])
        pb_pct = fest.get("price_bump_pct", 0.0)

        # Build the window with a trapezoid shape
        # Ramp-up: pre_days before first main day
        # Peak: main_dates
        # Taper: post_days after last main day
        first_day = main_dates[0]
        last_day = main_dates[-1]

        # Ramp-up phase
        for i in range(pre, 0, -1):
            d = first_day - timedelta(days=i)
            factor = (pre - i + 1) / (pre + 1)  # 0.17 ... 0.83
            for prod, peak_mult in product_mults.items():
                effective_mult = 1.0 + (peak_mult - 1.0) * factor
                key = (prod, d.isoformat())
                if effective_mult > quantity_boost[key]:
                    quantity_boost[key] = effective_mult

        # Peak phase
        for d in main_dates:
            for prod, peak_mult in product_mults.items():
                key = (prod, d.isoformat())
                if peak_mult > quantity_boost[key]:
                    quantity_boost[key] = peak_mult
                # Price bump on main days
                if prod in pb_products:
                    price_key = (prod, d.isoformat())
                    if pb_pct > price_bump[price_key]:
                        price_bump[price_key] = pb_pct

        # Taper phase
        for i in range(1, post + 1):
            d = last_day + timedelta(days=i)
            factor = (post - i + 1) / (post + 1)
            for prod, peak_mult in product_mults.items():
                effective_mult = 1.0 + (peak_mult - 1.0) * factor
                key = (prod, d.isoformat())
                if effective_mult > quantity_boost[key]:
                    quantity_boost[key] = effective_mult

    return quantity_boost, price_bump


# ---------------------------------------------------------------------------
# Recompute rolling/lag features
# ---------------------------------------------------------------------------

def recompute_features(records_by_product):
    """Given a dict of product_id -> sorted list of records, recompute all features."""
    result = []
    for sc, recs in records_by_product.items():
        recs = sorted(recs, key=lambda r: r['date'])
        quantities = [r['quantity'] for r in recs]
        n = len(quantities)

        for i, r in enumerate(recs):
            qty = quantities[i]

            lag_1  = float(quantities[i-1])  if i >= 1  else 0.0
            lag_7  = float(quantities[i-7])  if i >= 7  else 0.0
            lag_14 = float(quantities[i-14]) if i >= 14 else 0.0

            window_7  = quantities[max(0, i-6):i+1]
            window_30 = quantities[max(0, i-29):i+1]

            rolling_7d_mean  = sum(window_7)  / len(window_7)
            rolling_30d_mean = sum(window_30) / len(window_30)
            rolling_7d_std   = (
                math.sqrt(sum((x - rolling_7d_mean)**2 for x in window_7) / len(window_7))
                if len(window_7) > 1 else 0.0
            )

            r['lag_1']          = round(lag_1, 10)
            r['lag_7']          = round(lag_7, 10)
            r['lag_14']         = round(lag_14, 10)
            r['rolling_7d_mean']  = round(rolling_7d_mean, 10)
            r['rolling_30d_mean'] = round(rolling_30d_mean, 10)
            r['rolling_7d_std']   = round(rolling_7d_std, 10)

            result.append(r)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading dataset...")
    with open(DATA_PATH) as f:
        data = json.load(f)
    print(f"  {len(data)} records loaded.")

    quantity_boost, price_bump = build_boost_map(FESTIVALS)
    print(f"  Festival boost map built: {len(quantity_boost)} (product, date) entries.")

    # Apply boosts
    updated = 0
    for r in data:
        sc = r['stock_code']
        date_str = r['date'][:10]  # "2023-01-14"

        key = (sc, date_str)
        mult = quantity_boost.get(key, 1.0)
        pb   = price_bump.get(key, 0.0)

        if mult > 1.0 or pb > 0.0:
            base_qty = r['quantity']
            # Apply multiplier + small noise so it doesn't look synthetic
            noise = random.uniform(0.92, 1.08)
            new_qty = max(1, round(base_qty * mult * noise))
            r['quantity'] = new_qty

            if pb > 0.0:
                r['unit_price'] = round(r['unit_price'] * (1.0 + pb), 2)

            updated += 1

    print(f"  {updated} records boosted.")

    # Recompute lag / rolling features per product
    print("Recomputing lag/rolling features...")
    by_product = defaultdict(list)
    for r in data:
        by_product[r['stock_code']].append(r)

    data = recompute_features(by_product)
    print(f"  Done. Total records: {len(data)}")

    # Save
    print(f"Saving to {DATA_PATH}...")
    with open(DATA_PATH, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    print("Done!")

    # Summary check
    print("\n=== FESTIVAL SPOT CHECK ===")
    spot_check = [
        ('PONGAL001', '2023-01-14'),
        ('PONGAL002', '2023-01-14'),
        ('OIL001',    '2023-11-27'),
        ('SWEET002',  '2023-11-12'),
        ('NEEM001',   '2023-01-14'),
        ('MANGO001',  '2023-04-14'),
        ('SWEET002',  '2024-11-01'),
        ('OIL002',    '2024-12-15'),
    ]
    lookup = {(r['stock_code'], r['date'][:10]): r for r in data}
    for sc, ds in spot_check:
        r = lookup.get((sc, ds))
        if r:
            print(f"  {sc} | {ds} | qty={r['quantity']} | price={r['unit_price']}")


if __name__ == '__main__':
    main()
