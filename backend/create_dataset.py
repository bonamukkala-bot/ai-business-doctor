import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

products = [
    {"name": "Basmati Rice 5kg", "cost": 350, "price": 480, "category": "Staples"},
    {"name": "Sunflower Oil 1L", "cost": 120, "price": 165, "category": "Staples"},
    {"name": "Toor Dal 1kg", "cost": 90, "price": 130, "category": "Staples"},
    {"name": "Maggi Noodles Pack", "cost": 45, "price": 65, "category": "Snacks"},
    {"name": "Lays Chips Large", "cost": 35, "price": 55, "category": "Snacks"},
    {"name": "Amul Milk 1L", "cost": 48, "price": 58, "category": "Dairy"},
    {"name": "Amul Butter 500g", "cost": 210, "price": 265, "category": "Dairy"},
    {"name": "Britannia Bread", "cost": 28, "price": 40, "category": "Bakery"},
    {"name": "Colgate Toothpaste", "cost": 65, "price": 95, "category": "Personal Care"},
    {"name": "Dove Soap Pack", "cost": 80, "price": 115, "category": "Personal Care"},
    {"name": "Surf Excel 1kg", "cost": 140, "price": 190, "category": "Household"},
    {"name": "Harpic Toilet Cleaner", "cost": 75, "price": 105, "category": "Household"},
    {"name": "Parle-G Biscuits", "cost": 20, "price": 30, "category": "Snacks"},
    {"name": "Tata Tea Gold 1kg", "cost": 380, "price": 470, "category": "Staples"},
    {"name": "Fresh Curd 500g (Expiring Item)", "cost": 25, "price": 35, "category": "Dairy"},
]

start_date = datetime(2026, 4, 1)
days = 90

rows = []
for day_offset in range(days):
    date = start_date + timedelta(days=day_offset)
    for idx, p in enumerate(products):
        base_units = np.random.poisson(lam=20)

        # Bake in patterns for the AI to discover:

        # Pattern 1: "Fresh Curd" is a slow-mover with declining sales + expiring soon (reorder/stop-sell candidate)
        if p["name"].startswith("Fresh Curd"):
            base_units = max(0, int(base_units * 0.25 * (1 - day_offset/180)))

        # Pattern 2: "Tata Tea Gold" sales have been dropping last 20 days (profit drop driver)
        if p["name"] == "Tata Tea Gold 1kg" and day_offset > 70:
            base_units = int(base_units * 0.4)

        # Pattern 3: "Lays Chips" sales spiking last 15 days (fast-mover, reorder needed)
        if p["name"] == "Lays Chips Large" and day_offset > 75:
            base_units = int(base_units * 2.2)

        # Pattern 4: "Harpic Toilet Cleaner" consistently low seller (stop-selling candidate)
        if p["name"] == "Harpic Toilet Cleaner":
            base_units = max(0, int(base_units * 0.3))

        units_sold = max(0, base_units + np.random.randint(-3, 4))
        revenue = units_sold * p["price"]
        cost_total = units_sold * p["cost"]
        profit = revenue - cost_total

        rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "product": p["name"],
            "category": p["category"],
            "units_sold": units_sold,
            "unit_cost": p["cost"],
            "unit_price": p["price"],
            "revenue": revenue,
            "cost": cost_total,
            "profit": profit
        })

sales_df = pd.DataFrame(rows)
sales_df.to_csv("sales_data.csv", index=False)

# Current inventory snapshot (as of last day)
inventory_rows = []
for p in products:
    if p["name"].startswith("Fresh Curd"):
        current_stock = 8  # low, expiring
    elif p["name"] == "Lays Chips Large":
        current_stock = 25  # low relative to spiking demand
    elif p["name"] == "Harpic Toilet Cleaner":
        current_stock = 300  # overstocked, slow seller
    else:
        current_stock = np.random.randint(150, 300)

    inventory_rows.append({
        "product": p["name"],
        "category": p["category"],
        "current_stock": current_stock,
        "unit_cost": p["cost"],
        "unit_price": p["price"]
    })

inventory_df = pd.DataFrame(inventory_rows)
inventory_df.to_csv("inventory_data.csv", index=False)

print("Datasets created:")
print(f"  sales_data.csv -> {len(sales_df)} rows")
print(f"  inventory_data.csv -> {len(inventory_df)} rows")
print("\nSample sales data:")
print(sales_df.head())
print("\nInventory snapshot:")
print(inventory_df)