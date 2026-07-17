import pandas as pd
import numpy as np
from analysis_engine import load_data

# Load the current data
sales, inventory = load_data(user_id=1)

# Get max_date from dataset
max_date = sales["date"].max()
print(f"1. max_date used: {max_date.strftime('%Y-%m-%d')}")

# Find Fresh Curd in inventory
product_name = "Fresh Curd 500g (Expiring Item)"
fresh_curd_inv = inventory[inventory["product"] == product_name]
if fresh_curd_inv.empty:
    print(f"{product_name} not found in inventory!")
else:
    current_stock = int(fresh_curd_inv["current_stock"].values[0])
    print(f"2. current_stock: {current_stock} units")

# Calculate the average daily sales rate exactly as recommend_reorder does
recent_start = max_date - pd.Timedelta(days=14)
recent = sales[sales["date"] >= recent_start]
fresh_curd_recent = recent[recent["product"] == product_name]

if fresh_curd_recent.empty:
    print(f"No recent sales data for {product_name} in last 14 days")
    avg_daily_sales_rate = 0
else:
    total_units_sold = fresh_curd_recent["units_sold"].sum()
    avg_daily_sales_rate = total_units_sold / 15  # exactly as in line 294
    print(f"3. average_daily_sales_rate: {avg_daily_sales_rate} (total_units_sold: {total_units_sold} / 15 days)")

print(f"4. Exact formula from line 298-302:")
print("   merged['days_of_stock_left'] = np.where(")
print("       merged['daily_avg'] > 0,")
print("       merged['current_stock'] / merged['daily_avg'],")
print("       999")
print("   )")

# Calculate the final days_of_stock_left value
if avg_daily_sales_rate > 0:
    days_of_stock_left = current_stock / avg_daily_sales_rate
    print(f"5. Final days_of_stock_left: {days_of_stock_left}")
    print(f"   Calculation: {current_stock} / {avg_daily_sales_rate} = {days_of_stock_left}")
else:
    days_of_stock_left = 999
    print(f"5. Final days_of_stock_left: {days_of_stock_left} (no recent sales, set to 999)")

# Show the raw data for verification
print(f"\n--- RAW DATA FOR VERIFICATION ---")
print(f"Fresh Curd recent sales (last 14 days):")
if not fresh_curd_recent.empty:
    print(fresh_curd_recent[["date", "units_sold"]].to_string(index=False))
else:
    print("No recent sales data")
print(f"\nFresh Curd inventory data:")
print(fresh_curd_inv.to_string(index=False))
