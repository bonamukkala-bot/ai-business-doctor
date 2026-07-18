"""
Mock Supplier Intelligence data source.

This is a PLACEHOLDER for a real supplier API integration. There is no
real alternate-supplier data source connected to this app. Every value
returned here is clearly tagged is_demo_data=True so the frontend can
label it honestly and it can never be confused with the app's real,
verified analysis elsewhere.

The only REAL number in this module's output is current_unit_cost,
which is passed in from the caller's actual inventory data. The
"alternate supplier" name and price are synthetic. All savings figures
are computed FROM the real cost vs the synthetic one, so the arithmetic
is correct even though one input is fake.

To wire in a real supplier API later: replace the body of
get_supplier_comparison() with a real HTTP call, keep the same return
shape, and change is_demo_data to False.
"""

import random

# Bounded discount range for the mock alternate supplier — kept modest
# and realistic-looking rather than an implausible blowout discount.
MOCK_DISCOUNT_MIN_PCT = 5
MOCK_DISCOUNT_MAX_PCT = 15

MOCK_SUPPLIER_NAMES = [
    "Alt Supplier (Demo Data)",
    "Regional Wholesaler (Demo Data)",
    "Bulk Distributor Co. (Demo Data)",
]


def get_supplier_comparison(product_name: str, current_unit_cost: float) -> dict:
    """
    Returns a mock alternate-supplier comparison for one product.

    current_unit_cost is REAL (passed in from the caller's actual
    inventory data). Everything else about the "alternate supplier" is
    synthetic demo data, clearly labeled.
    """
    if current_unit_cost <= 0:
        return {
            "product": product_name,
            "is_demo_data": True,
            "data_source": "mock",
            "has_comparison": False,
            "note": "No valid current cost available to compare against.",
        }

    # Seed on product name so the same product always gets the same mock
    # alternate supplier/discount within a session, rather than a new
    # random number every request (avoids numbers flickering on refresh).
    rng = random.Random(product_name)
    discount_pct = rng.uniform(MOCK_DISCOUNT_MIN_PCT, MOCK_DISCOUNT_MAX_PCT)
    supplier_name = rng.choice(MOCK_SUPPLIER_NAMES)

    alternate_cost = round(current_unit_cost * (1 - discount_pct / 100), 2)
    price_difference = round(current_unit_cost - alternate_cost, 2)

    return {
        "product": product_name,
        "is_demo_data": True,
        "data_source": "mock",
        "has_comparison": True,
        "current_supplier_cost": round(current_unit_cost, 2),
        "alternate_supplier_name": supplier_name,
        "alternate_supplier_cost": alternate_cost,
        "price_difference": price_difference,
        "price_difference_pct": round(discount_pct, 1),
        "supplier_rating": round(rng.uniform(3.8, 4.8), 1),  # mock rating
        "confidence_note": (
            "This is demonstration data illustrating the feature's format. "
            "Connect a real supplier data source to replace these figures."
        ),
    }


def calculate_supplier_savings(current_unit_cost: float, alternate_cost: float, monthly_units: float) -> dict:
    """
    Real arithmetic on the (partly synthetic) costs above.
    monthly_units should come from real sales history when available;
    if unknown, pass 0 and savings will be 0 rather than guessed.
    """
    unit_savings = round(current_unit_cost - alternate_cost, 2)
    monthly_savings = round(unit_savings * monthly_units, 2)
    annual_savings = round(monthly_savings * 12, 2)
    return {
        "unit_savings": unit_savings,
        "monthly_savings": monthly_savings,
        "annual_savings": annual_savings,
    }