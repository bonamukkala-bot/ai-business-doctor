import pandas as pd
import numpy as np


def to_native(obj):
    """Recursively convert numpy/pandas types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_native(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def load_data():
    sales = pd.read_csv("sales_data.csv")
    inventory = pd.read_csv("inventory_data.csv")
    sales["date"] = pd.to_datetime(sales["date"])
    return sales, inventory


def analyze_profit_drop(sales: pd.DataFrame):
    """Compares last 15 days vs previous 15 days to find what's driving any profit change."""
    max_date = sales["date"].max()
    recent_start = max_date - pd.Timedelta(days=14)
    prev_start = max_date - pd.Timedelta(days=29)
    prev_end = max_date - pd.Timedelta(days=15)

    recent = sales[sales["date"] >= recent_start]
    previous = sales[(sales["date"] >= prev_start) & (sales["date"] <= prev_end)]

    recent_by_product = recent.groupby("product")["profit"].sum()
    prev_by_product = previous.groupby("product")["profit"].sum()

    comparison = pd.DataFrame({
        "recent_profit": recent_by_product,
        "previous_profit": prev_by_product
    }).fillna(0)

    comparison["change"] = comparison["recent_profit"] - comparison["previous_profit"]
    comparison["pct_change"] = np.where(
        comparison["previous_profit"] > 0,
        (comparison["change"] / comparison["previous_profit"]) * 100,
        0
    )

    total_change = comparison["change"].sum()
    top_drags = comparison.sort_values("change").head(3)

    drivers = []
    for product, row in top_drags.iterrows():
        if row["change"] < 0:
            drivers.append({
                "product": product,
                "profit_change": round(float(row["change"]), 2),
                "pct_change": round(float(row["pct_change"]), 1),
                "reasoning": f"{product} profit dropped by Rs {abs(round(row['change']))} ({abs(round(row['pct_change'],1))}% decline) in the last 15 days compared to the prior 15 days."
            })

    return {
        "total_profit_change": round(float(total_change), 2),
        "summary": f"Overall profit {'declined' if total_change < 0 else 'grew'} by Rs {abs(round(total_change))} over the last 15 days.",
        "top_drivers": drivers
    }


def recommend_stop_selling(sales: pd.DataFrame, inventory: pd.DataFrame):
    """Flags consistently low-selling, low-margin-contribution products."""
    product_stats = sales.groupby("product").agg(
        total_units=("units_sold", "sum"),
        total_profit=("profit", "sum"),
        avg_daily_units=("units_sold", "mean")
    ).reset_index()

    threshold_units = product_stats["avg_daily_units"].quantile(0.25)
    threshold_profit = product_stats["total_profit"].quantile(0.4)

    candidates = product_stats[
        (product_stats["avg_daily_units"] <= threshold_units) &
        (product_stats["total_profit"] <= threshold_profit)
    ].sort_values("total_profit")

    recommendations = []
    for _, row in candidates.iterrows():
        stock_row = inventory[inventory["product"] == row["product"]]
        current_stock = int(stock_row["current_stock"].values[0]) if not stock_row.empty else 0
        stock_capital = current_stock * float(stock_row["unit_cost"].values[0]) if not stock_row.empty else 0
        recommendations.append({
            "product": row["product"],
            "avg_daily_units": round(float(row["avg_daily_units"]), 1),
            "total_profit_90days": round(float(row["total_profit"]), 2),
            "current_stock": current_stock,
            "reasoning": f"Averages only {round(row['avg_daily_units'],1)} units/day over 90 days, contributing just Rs {round(row['total_profit'])} total profit while tying up Rs {stock_capital:.0f} in stock capital."
        })

    return recommendations[:3]


def recommend_reorder(sales: pd.DataFrame, inventory: pd.DataFrame):
    """Flags products where recent demand trend + low stock signals a reorder need."""
    max_date = sales["date"].max()
    recent_start = max_date - pd.Timedelta(days=14)
    recent = sales[sales["date"] >= recent_start]

    recent_demand = recent.groupby("product")["units_sold"].sum().reset_index()
    recent_demand["daily_avg"] = recent_demand["units_sold"] / 15
    recent_demand["projected_7day_need"] = (recent_demand["daily_avg"] * 7).round().astype(int)

    merged = recent_demand.merge(inventory[["product", "current_stock"]], on="product", how="left")
    merged["days_of_stock_left"] = np.where(
        merged["daily_avg"] > 0,
        merged["current_stock"] / merged["daily_avg"],
        999
    )

    urgent = merged[merged["days_of_stock_left"] <= 7].sort_values("days_of_stock_left")

    recommendations = []
    for _, row in urgent.iterrows():
        recommendations.append({
            "product": row["product"],
            "current_stock": int(row["current_stock"]),
            "daily_avg_demand": round(float(row["daily_avg"]), 1),
            "days_of_stock_left": round(float(row["days_of_stock_left"]), 1),
            "recommended_reorder_qty": int(row["projected_7day_need"]),
            "reasoning": f"Selling ~{round(row['daily_avg'],1)} units/day, only {round(row['days_of_stock_left'],1)} days of stock left. Reorder at least {row['projected_7day_need']} units to cover next 7 days."
        })

    return recommendations


def get_all_insights():
    sales, inventory = load_data()
    result = {
        "profit_analysis": analyze_profit_drop(sales),
        "stop_selling": recommend_stop_selling(sales, inventory),
        "reorder": recommend_reorder(sales, inventory)
    }
    return to_native(result)


if __name__ == "__main__":
    import json
    insights = get_all_insights()
    print(json.dumps(insights, indent=2, default=str))