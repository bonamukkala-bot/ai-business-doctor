import pandas as pd
import datetime
import os
from analysis_engine import load_data, normalize_date_series

# Load the current data
sales, inventory = load_data(user_id=1)

# Print basic dataset info
print("=" * 60)
print("DATASET DATE ANALYSIS")
print("=" * 60)
print(f"Total records: {len(sales)}")
print(f"Unique products: {sales['product'].nunique()}")

# Get the date range
min_date = sales["date"].min()
max_date = sales["date"].max()
today = datetime.date.today()

print(f"\nDate Range in Dataset:")
print(f"  Min Date: {min_date.strftime('%Y-%m-%d')}")
print(f"  Max Date: {max_date.strftime('%Y-%m-%d')}")
print(f"  Today's Reference Date: {today.strftime('%Y-%m-%d')}")

# Calculate the span
date_span = (max_date - min_date).days
print(f"  Date Span: {date_span} days")

# Print dates used in health score calculations
print(f"\n" + "=" * 60)
print("DATES USED IN HEALTH SCORE CALCULATIONS")
print("=" * 60)

# Profit drop analysis dates (last 15 days vs previous 15 days)
recent_start = max_date - pd.Timedelta(days=14)
prev_start = max_date - pd.Timedelta(days=29)
prev_end = max_date - pd.Timedelta(days=15)

print(f"Profit Drop Analysis (15-day comparison):")
print(f"  Recent period: {recent_start.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
print(f"  Previous period: {prev_start.strftime('%Y-%m-%d')} to {prev_end.strftime('%Y-%m-%d')}")

# Reorder analysis dates (last 14 days)
reorder_start = max_date - pd.Timedelta(days=14)
print(f"\nReorder Analysis (14-day demand):")
print(f"  Analysis period: {reorder_start.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

# Anomaly detection dates
last7_start = max_date - pd.Timedelta(days=6)
prev7_start = max_date - pd.Timedelta(days=13)
prev7_end = max_date - pd.Timedelta(days=7)

print(f"\nAnomaly Detection (7-day comparison):")
print(f"  Last 7 days: {last7_start.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
print(f"  Previous 7 days: {prev7_start.strftime('%Y-%m-%d')} to {prev7_end.strftime('%Y-%m-%d')}")

# Forecast analysis dates (30 days back, 15 forward)
forecast_start = max_date - pd.Timedelta(days=29)
forecast_end = max_date + pd.Timedelta(days=15)

print(f"\nProfit Forecast (30-day historical, 15-day forward):")
print(f"  Historical period: {forecast_start.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
print(f"  Forecast period: {max_date.strftime('%Y-%m-%d')} to {forecast_end.strftime('%Y-%m-%d')}")

# Validation checks
print(f"\n" + "=" * 60)
print("VALIDATION CHECKS")
print("=" * 60)

# Check if dates span roughly 90 days
if 80 <= date_span <= 100:
    print(f"✓ Date span ({date_span} days) looks correct for ~90 day dataset")
else:
    print(f"✗ Date span ({date_span} days) may be incorrect (expected ~90 days)")

# Check if max_date is in the past
if max_date.date() <= today:
    print(f"✓ Max date ({max_date.strftime('%Y-%m-%d')}) is not in the future")
else:
    print(f"✗ Max date ({max_date.strftime('%Y-%m-%d')}) is in the future!")

# Check if dates are not all identical
if sales["date"].nunique() > 1:
    print(f"✓ Dataset contains {sales['date'].nunique()} unique dates (not all identical)")
else:
    print(f"✗ All dates are identical!")

# Check if min_date is reasonable (not too far in the past)
min_date_age = (today - min_date.date()).days
if min_date_age <= 120:
    print(f"✓ Min date is {min_date_age} days ago (reasonable)")
else:
    print(f"✗ Min date is {min_date_age} days ago (may be too old)")

print(f"\n" + "=" * 60)
