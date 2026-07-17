import sys
import os

# Add parent dir to path to import analysis_engine
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis_engine import load_data, get_daily_summary, to_native


def test_daily_summary():
    # Use demo user 1 (we can just pass user_id=1, which loads demo data)
    sales, inventory = load_data(user_id=1)
    
    # For testing, if today isn't in the demo data, let's use the last date in sales
    print("Testing get_daily_summary...")
    print("Sales date range:", sales["date"].min().date(), "to", sales["date"].max().date())
    
    test_date = sales["date"].max().date()
    summary = get_daily_summary(sales, inventory, test_date=test_date)
    # Convert to native for printing
    native_summary = to_native(summary)
    print("\nDaily Summary:")
    import json
    print(json.dumps(native_summary, indent=2))


if __name__ == "__main__":
    test_daily_summary()
